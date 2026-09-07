# rag/flow.py
from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Tuple, Dict, Any
if TYPE_CHECKING:
    from core.knowledge.store_faiss import FaissStore
    from core.llm.llm_service import LLMService
    from core.whatsapp.whatsapp_service import WhatsAppService

import logging
import re

from config.settings import settings
from core.i18n import t as _t
from core.intake import engine as intake_engine
from core.intake import state as intake_state
from core.intake.categories import CATEGORIES as INTAKE_CATEGORIES

logger = logging.getLogger(__name__)

# Availability flag only — do NOT instantiate at import time (slow disk load)
try:
    from spellchecker import SpellChecker as _SpellChecker
    _SPELLCHECKER_AVAILABLE = True
except Exception:
    _SpellChecker = None  # type: ignore
    _SPELLCHECKER_AVAILABLE = False


class BotFlow:
    """High-level orchestration for handling incoming user messages.

    Behavior:
    - optionally spell-corrects user messages
    - uses RagComposer (RAG + LLM) to respond
    - uses ConversationMemory markers to avoid repeated menus and repeated follow-ups
    - replies in Bangla (Bengali) when the user writes in Bangla or explicitly requests it, English otherwise
    """

    def __init__(
        self,
        faiss_store: FaissStore,
        llm_service: LLMService,
        whatsapp_service: WhatsAppService,
        composer=None,
    ):
        self.faiss = faiss_store
        self.llm = llm_service
        self.whatsapp = whatsapp_service
        self._spell = None  # lazy-loaded on first use
        self._composer = composer

    @property
    def spell(self):
        if self._spell is None and _SPELLCHECKER_AVAILABLE:
            self._spell = _SpellChecker()
        return self._spell

    def _get_composer(self):
        if self._composer:
            return self._composer
        try:
            from rag.composer import RagComposer
            self._composer = RagComposer()
        except Exception as e:
            logger.error(f"Could not create RagComposer: {e}")
            self._composer = None
        return self._composer

    def preprocess(self, message: str) -> str:
        """Return a (possibly) corrected message for downstream processing."""
        if not message:
            return ""
        if not self.spell:
            return message

        # Safer correction: SpellChecker.correction can return None
        corrected_words = []
        for w in message.split():
            try:
                cw = self.spell.correction(w)
                corrected_words.append(cw if cw else w)
            except Exception:
                corrected_words.append(w)

        corrected = " ".join(corrected_words)
        return corrected.strip()

    def _format_outgoing(self, text: str) -> str:
        """Normalize outgoing text:
        - strip simple markdown asterisks
        - limit list items to 5 items
        - truncate by sentence boundary to ~800 chars
        """
        if not text:
            return text

        # Remove simple markdown emphasis (*bold*)
        try:
            text = re.sub(r"\*(.*?)\*", r"\1", text)
        except Exception:
            pass

        text = text.strip()

        # Detect and limit lists (numbered or bullet)
        lines = text.splitlines()
        list_start = None
        for i, line in enumerate(lines):
            if re.match(r"^\s*(?:\d+\.\s+|[-\*]\s+)", line):
                list_start = i
                break

        if list_start is not None:
            header = "\n".join(lines[:list_start]).strip()
            list_items = []
            for line in lines[list_start:]:
                m = re.match(r"^\s*(?:\d+\.\s+|[-\*]\s+)(.*)", line)
                if m:
                    item = m.group(1).strip()
                    if item:
                        list_items.append(item)
                else:
                    break

            if list_items:
                truncated = False
                if len(list_items) > 5:
                    list_items = list_items[:5]
                    truncated = True

                numbered = "\n".join([f"{i+1}. {it}" for i, it in enumerate(list_items)])
                if truncated:
                    numbered = numbered + "\n..."

                text = f"{header}\n\n{numbered}" if header else numbered

                # Flatten very short lists into plain sentence(s)
                try:
                    if len(list_items) <= 2 and sum(len(s) for s in list_items) < 200:
                        flat = " ".join(list_items).strip()
                        if flat and not flat.endswith((".", "!", "?")):
                            flat += "."
                        text = f"{header}\n\n{flat}" if header else flat
                except Exception:
                    pass

        # Safe truncation by sentence boundary (~800 chars)
        if len(text) > 800:
            try:
                sentences = re.split(r"(?<=[.!?])\s+", text)
                out = ""
                for s in sentences:
                    if len(out) + len(s) + 1 > 800:
                        break
                    out = out + (" " if out else "") + s
                text = out.strip()
                if text and not text.endswith((".", "!", "?")):
                    text += "."
            except Exception:
                text = text[:800]

        # Post-process: flatten short numbered lists to plain text
        try:
            lines2 = [l.strip() for l in text.splitlines() if l.strip()]
            if lines2 and re.match(r"^\d+\.\s+", lines2[0]) and len(lines2) <= 2 and len(text) < 200:
                flattened = " ".join([re.sub(r"^\d+\.\s+", "", l) for l in lines2]).strip()
                if flattened and not flattened.endswith((".", "!", "?")):
                    flattened += "."
                text = flattened
        except Exception:
            pass

        return text

    def _detect_bangla(self, text: str) -> bool:
        """Reply in Bangla if the user writes in Bangla/Bengali, or explicitly asks for it."""
        if not text:
            return False
        t = text.lower()
        if "bangla" in t or "bengali" in t or t.strip().startswith(("bangla:", "bengali:")):
            return True
        try:
            from adapters.llm.openai_client import detect_language
            lang, conf = detect_language(text)
            return lang == "bn" and conf >= 0.6
        except Exception:
            return False

    _BN_THANKS_RE = r"ধন্যবাদ|শুকরিয়া"
    _BN_BYE_RE = r"বিদায়|ভালো থাকবেন"
    # "কাজ করছে" ("is working") must not match its negation "কাজ করছে না"
    # ("is NOT working") - e.g. the menu's own "Report a Problem" example
    # text ("অ্যাপ কাজ করছে না") would otherwise be misread as a resolution.
    # Bangla word order is flexible, so both "ঠিক আছে এখন" and "এখন ঠিক আছে"
    # ("it's okay now" / "now it's okay") need to be covered.
    _BN_RESOLVED_RE = r"ঠিক হয়ে গেছে|সমাধান হয়েছে|কাজ করছে(?!\s*না)|ঠিক আছে এখন|এখন ঠিক আছে"
    _NEGATION_BEFORE_RE = re.compile(r"(not|n't|no|never|isn|doesn|didn|won)\s*$", re.I)
    # A trailing "but it's still broken" clause means the conversation isn't
    # actually over - "thanks"/"bye" alone shouldn't close it out from under
    # an unresolved issue.
    _UNRESOLVED_SIGNAL_RE = re.compile(
        r"\b(but|however)\b|\bstill\b|\bnot\s+(fixed|resolved|solved|working|done)\b"
        r"|কিন্তু|তবে|এখনো|এখনও",
        re.I,
    )
    # Broad, not an exact match against our own clarify_prompt text - this
    # also needs to catch the composer's own LLM-generated clarifying
    # questions (it's instructed to ask one when uncertain), which won't
    # literally match our hardcoded copy.
    _CLARIFY_SIGNAL_RE = re.compile(
        r"could you provide|please provide|i don't have enough|one brief detail|could you share|tell me a bit more|help you faster"
        r"|আরেকটু বিস্তারিত|আরও তথ্য|যথেষ্ট তথ্য নেই",
        re.I,
    )

    def _is_short_ack(self, text: str) -> bool:
        """Short acknowledgements that should not trigger follow-ups."""
        if not text:
            return False
        t = text.strip().lower()
        if len(t) > 60:
            return False
        if re.search(
            rf"\b(thank(s| you)?|than you|ty|bye|goodbye|see you|thanks a lot|ok(ay)?|k)\b|{self._BN_THANKS_RE}|{self._BN_BYE_RE}",
            t,
        ):
            return True
        if t in ("ok", "okay", "yes", "no", "sure", "হ্যাঁ", "না", "ঠিক আছে"):
            return True
        return False

    def _is_closing_message(self, text: str) -> bool:
        """Explicit conversation-ending messages."""
        if not text:
            return False
        t = text.strip().lower()
        if len(t) > 120:
            return False
        if not re.search(
            rf"\b(thank(s| you)?|than you|thanks a lot|bye|goodbye|see you|talk later)\b|{self._BN_THANKS_RE}|{self._BN_BYE_RE}",
            t,
        ):
            return False
        # "Thanks, but it's still broken" is not a goodbye - don't close out
        # from under an issue the user just said isn't fixed.
        if self._UNRESOLVED_SIGNAL_RE.search(t):
            return False
        return True

    def _is_resolution_message(self, text: str) -> bool:
        """User indicates issue is resolved or working now."""
        if not text:
            return False
        t = text.strip().lower()
        if len(t) > 200:
            return False
        # A trailing contrast/still-broken clause ("it works now, but still
        # crashes sometimes") means this isn't a clean resolution - don't
        # auto-close the ticket as Resolved on a mixed signal.
        if self._UNRESOLVED_SIGNAL_RE.search(t):
            return False
        pattern = rf"\b(resolved|fixed|worked|now works|working now|it works|it worked|problem solved|solved|all good|okay now|ok now)\b|{self._BN_RESOLVED_RE}"
        for m in re.finditer(pattern, t):
            # Skip matches immediately preceded by a negation - e.g. "not
            # solved", "isn't working now" is the opposite of a resolution.
            if self._NEGATION_BEFORE_RE.search(t[max(0, m.start() - 15):m.start()]):
                continue
            return True
        return False

    def _mem(self):
        """Best-effort ConversationMemory loader."""
        try:
            from core.memory.memory_service import ConversationMemory
            return ConversationMemory()
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Ticket helpers
    # ------------------------------------------------------------------

    _LANGUAGE_TOKEN_RE = re.compile(r"^\s*([12]|english|bangla|bengali|bn|en|বাংলা)\s*[,:\-]?\s*", re.I)

    @classmethod
    def _split_leading_language_token(cls, text: str) -> Tuple[str, str]:
        """Pull a leading language token off the combined first-touch reply
        (e.g. "1, Rahim Uddin, rahim@example.com, Dhaka" -> ("1", "Rahim
        Uddin, rahim@example.com, Dhaka")). Returns ("", text) unchanged if
        no recognizable token leads the reply, so the whole reply is
        treated as contact info and language falls back to English."""
        t = text or ""
        m = cls._LANGUAGE_TOKEN_RE.match(t)
        if m:
            return m.group(1).lower(), t[m.end():]
        return "", t

    @staticmethod
    def _is_ticket_yes(text: str) -> bool:
        t = text.strip().lower()
        return t in ("yes", "y", "yeah", "yep", "sure", "ok", "okay", "yep", "confirm")

    @staticmethod
    def _is_ticket_no(text: str) -> bool:
        t = text.strip().lower()
        return t in ("no", "n", "nope", "nah", "cancel", "never mind", "nevermind")

    @staticmethod
    def _extract_pending_issue(recent: list, marker: str = "ticket_pending") -> str:
        """Return the user message that immediately preceded the given system marker."""
        pending_idx = None
        for i, m in enumerate(recent):
            if m.get("role") == "system" and m.get("text") == marker:
                pending_idx = i

        if pending_idx is None:
            return "Issue not captured"

        # Walk backwards to find the last user message before the marker
        for m in reversed(recent[:pending_idx]):
            if m.get("role") == "user":
                return (m.get("text") or "")[:500]

        return "Issue not captured"

    @staticmethod
    def _full_transcript(recent: list) -> str:
        """Plain user/assistant transcript (system markers excluded) for
        attaching to an auto-logged ticket as its conversation-summary comment."""
        lines = [
            f"{m.get('role')}: {m.get('text', '')}"
            for m in recent
            if m.get("role") in ("user", "assistant")
        ]
        return "\n".join(lines)

    def _auto_log_ticket_on_close(self, user_id: str, session_id: str, mem, contact_state, language: str = None):
        """Every conversation should leave a record in the main tool, so a
        resolution/closing message logs a ticket (status=Resolved) with an
        LLM summary + full transcript - unless this session already has an
        open ticket tracked (from the explicit handoff/confirmation flow
        below), in which case we just note the close on that ticket instead
        of creating a duplicate."""
        if not (getattr(settings, "ENABLE_TICKETING", True) and mem and session_id):
            return
        try:
            from core.tickets import state as ticket_state
            open_state = ticket_state.get_state(user_id)
            if open_state and open_state.get("status") not in ("Resolved", "Closed"):
                try:
                    from core.tickets.main_app_client import post_message as _post_ticket_message
                    _post_ticket_message(open_state["ticket_id"], user_id, "[Conversation closed by user]", sender="system")
                except Exception:
                    pass
                return

            recent_full = mem.get_recent(session_id, limit=50)
            transcript = self._full_transcript(recent_full)
            if not transcript:
                return
            summary = mem.summarize(session_id, language=language) or transcript[:500]
            contact = (contact_state.get_contact(user_id) if contact_state else None) or {}

            from core.tickets.ticket_manager import create_ticket
            ticket_id, sl_no = create_ticket(
                user_id, summary, transcript,
                name=contact.get("name", ""), division=contact.get("division", ""),
                status="Resolved", issue_type="General/Chat (auto-closed)",
            )
            if ticket_id:
                from core.tickets import csat_state
                csat_state.start(user_id, ticket_id, sl_no or str(ticket_id))
        except Exception:
            logger.exception("Auto-log-ticket-on-close failed for %s", user_id)

    # ------------------------------------------------------------------
    # Contact intake helpers
    # ------------------------------------------------------------------

    _CONTACT_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
    _BD_DIVISIONS = ["Dhaka", "Chittagong", "Rajshahi", "Khulna", "Barisal", "Sylhet", "Rangpur", "Mymensingh"]

    @staticmethod
    def _is_contact_skip(text: str) -> bool:
        t = text.strip().lower()
        return t in ("skip", "no", "no thanks", "not now", "later", "pass", "না", "এড়িয়ে যান")

    @classmethod
    def _parse_contact_reply(cls, text: str):
        """Heuristic split of a free-text contact reply into (name, email, division).

        Not NLP - just enough for a short, prompted reply like
        "Rahim Uddin, rahim@example.com, Dhaka": pull out an email by regex,
        match one of the 8 Bangladesh divisions by name, and treat whatever
        text is left over as the name.
        """
        email_match = cls._CONTACT_EMAIL_RE.search(text)
        email = email_match.group(0) if email_match else ""
        remainder = text.replace(email, "") if email else text

        division = ""
        lower = remainder.lower()
        for div in cls._BD_DIVISIONS:
            idx = lower.find(div.lower())
            if idx != -1:
                division = div
                remainder = remainder[:idx] + remainder[idx + len(div):]
                break

        name = re.sub(r"[,\-/|]+", " ", remainder).strip()
        name = re.sub(r"\s{2,}", " ", name).strip()
        return name[:150], email, division

    def handle_message(self, user_id: str, message: str, session_id: Optional[str] = None):
        """Main entrypoint called by the webhook to handle and respond to a message."""
        raw = message or ""

        # An explicit language selection (see the language-selection step
        # below) governs by default; a strong per-message signal (native
        # Bengali script, or explicitly naming a language) still wins for
        # that one message, so pasting a Bengali error still gets a Bengali
        # reply even if English was selected.
        strong_bangla_signal = self._detect_bangla(raw)
        stored_language = None
        try:
            from core.contacts import state as contact_state
            stored_language = contact_state.get_language(user_id)
        except Exception:
            contact_state = None
        use_bangla = strong_bangla_signal or stored_language == "bn"
        language = "bn" if use_bangla else "en"

        # The spellchecker only knows English — running it on Bangla/Banglish text
        # would corrupt real words, so skip correction for Bangla input.
        cleaned = raw if use_bangla else self.preprocess(raw)

        # ✅ Critical: if session_id not provided, default it to user_id (stable per WhatsApp user)
        # This prevents "memory never works" situations.
        if not session_id:
            session_id = user_id

        # --- Memory: always save the user’s message (best-effort) ---
        mem = None
        try:
            if getattr(settings, "ENABLE_CONVERSATION_MEMORY", False) and session_id:
                mem = self._mem()
                if mem:
                    mem.save_message(session_id, "user", cleaned)
        except Exception:
            mem = None

        # --- Forward to an already-open ticket, if this phone has one ---
        # Runs on every message (not just the handoff/confirmation branches
        # below), independent of the conversation-memory window, since ticket
        # state lives in a small per-phone sidecar file (core/tickets/state.py)
        # rather than a marker scanned out of the transcript. Deliberately
        # does NOT return/short-circuit — the bot keeps trying to help below
        # even while a ticket is open (blended bot+human, not bot-silenced).
        try:
            if getattr(settings, "ENABLE_TICKETING", True):
                from core.tickets import state as ticket_state
                from core.tickets.main_app_client import post_message as _post_ticket_message
                open_state = ticket_state.get_state(user_id)
                if open_state and open_state.get("status") not in ("Resolved", "Closed"):
                    current_status = _post_ticket_message(open_state["ticket_id"], user_id, cleaned, sender="user")
                    if current_status:
                        if current_status in ("Resolved", "Closed"):
                            ticket_state.clear_state(user_id)
                        else:
                            ticket_state.set_state(user_id, open_state["ticket_id"], open_state["sl_no"], current_status)
        except Exception:
            logger.exception("Failed to forward message to open ticket for %s", user_id)

        # --- Stale-conversation safety net (best-effort, throttled) ---
        # A reported issue that never got an explicit resolution/close, or a
        # structured intake abandoned mid-way, auto-becomes an Open ticket
        # after STALE_TICKET_MINUTES of silence - see core/intake/sweep.py.
        # Piggybacking on inbound traffic like this is a supplement, not a
        # substitute, for a real scheduled run of
        # scripts/sweep_stale_conversations.py; internally throttled so it
        # doesn't re-scan on every single message.
        try:
            if getattr(settings, "ENABLE_TICKETING", True):
                from core.intake.sweep import sweep_stale
                sweep_stale()
        except Exception:
            logger.exception("Stale-conversation sweep failed")

        # Same idea, for CSAT: once the main app shows a BDSupport ticket
        # resolved for a while, send the "how did we do?" survey - see
        # core/tickets/csat_sweep.py for why this has to poll rather than
        # wait for a status this bot would otherwise never hear about.
        try:
            if getattr(settings, "ENABLE_TICKETING", True):
                from core.tickets.csat_sweep import sweep_csat
                sweep_csat()
        except Exception:
            logger.exception("CSAT sweep failed")

        # If conversation was previously closed and user sends only a short ACK, ignore.
        try:
            if getattr(settings, "ENABLE_CONVERSATION_MEMORY", False) and mem and session_id:
                recent = mem.get_recent(session_id, limit=10)
                closed = any(m.get("role") == "system" and m.get("text") == "conversation_closed" for m in recent)
                if closed and self._is_short_ack(raw):
                    return "", {"ignored": True}
        except Exception:
            pass

        # --- Combined language + contact ask: one round trip, not two ---
        # Runs first so the rest of the conversation can be shown in the
        # chosen language, and so a ticket later filed is already
        # attributable. Previously this was two sequential prompts
        # (language, then contact) - merged into a single combined message
        # so a routine "unlock my account" request doesn't burn two extra
        # round trips before it can even reach the menu. Same once-per-phone
        # + resume-with-original-message pattern as before: the recovered
        # original message is re-saved to memory so downstream steps
        # (menu, structured intake) find it too.
        try:
            if getattr(settings, "ENABLE_CONVERSATION_MEMORY", False) and mem and session_id and contact_state:
                if not contact_state.has_language_been_asked(user_id):
                    # Bangladesh is overwhelmingly Bangla-speaking, so if the
                    # very first message already strongly signals Bangla
                    # (native script, or explicitly naming the language),
                    # don't make them pick from an English-first prompt for
                    # something we can already tell - set it and move
                    # straight on, using this same message as-is. Contact
                    # info still gets asked separately below in that case
                    # (this message wasn't a reply to any prompt, so there's
                    # nothing to split a language token off of).
                    if strong_bangla_signal:
                        contact_state.set_language(user_id, "bn")
                        use_bangla = True
                        language = "bn"
                    else:
                        recent = mem.get_recent(session_id, limit=6)
                        already_asked = any(
                            m.get("role") == "system" and m.get("text") == "lang_asked" for m in recent
                        )

                        if not already_asked:
                            combined_prompt = _t("first_touch_intake", "en")
                            try:
                                self.whatsapp.send_message(user_id, message=combined_prompt)
                            except Exception:
                                pass
                            mem.save_message(session_id, "assistant", combined_prompt)
                            mem.save_message(session_id, "system", "lang_asked")
                            return combined_prompt, {"first_touch_prompt_asked": True}

                        # This message is the reply to the combined prompt -
                        # split off the leading language token and parse the
                        # remainder (if any) as the contact reply, resolving
                        # both first-touch steps in one turn.
                        lang_token, remainder = self._split_leading_language_token(cleaned)
                        chosen_lang = "bn" if lang_token in ("2", "bangla", "bengali", "bn", "বাংলা") else "en"
                        contact_state.set_language(user_id, chosen_lang)
                        use_bangla = chosen_lang == "bn"
                        language = chosen_lang

                        if not remainder.strip() or self._is_contact_skip(remainder):
                            contact_state.set_contact(user_id, skipped=True)
                        else:
                            parsed_name, parsed_email, parsed_division = self._parse_contact_reply(remainder)
                            contact_state.set_contact(user_id, name=parsed_name, email=parsed_email, division=parsed_division)

                        recent_full = mem.get_recent(session_id, limit=15)
                        pending = self._extract_pending_issue(recent_full, marker="lang_asked")
                        if pending and pending != "Issue not captured":
                            cleaned = pending
                            raw = pending
                            mem.save_message(session_id, "user", pending)
        except Exception:
            logger.exception("Combined language/contact intake step failed for %s", user_id)

        # --- Contact intake: soft, skippable ask for name/email/division ---
        # Runs once per phone, before any menu/AI reply, so a ticket this
        # conversation later files is already attributable. Phone itself is
        # already known for free (the WhatsApp sender id), so we don't ask
        # for it again - see core/contacts/state.py. Needs conversation
        # memory to remember "already asked" and to recover the question
        # that triggered the ask; skipped entirely if memory is disabled.
        try:
            if getattr(settings, "ENABLE_CONVERSATION_MEMORY", False) and mem and session_id and contact_state:
                if not contact_state.has_been_asked(user_id):
                    recent = mem.get_recent(session_id, limit=6)
                    already_asked = any(
                        m.get("role") == "system" and m.get("text") == "contact_asked" for m in recent
                    )

                    if not already_asked:
                        intake_prompt = _t("contact_intake", language)
                        try:
                            self.whatsapp.send_message(user_id, message=intake_prompt)
                        except Exception:
                            pass
                        mem.save_message(session_id, "assistant", intake_prompt)
                        mem.save_message(session_id, "system", "contact_asked")
                        return intake_prompt, {"contact_intake_asked": True, "language": language}

                    # This message is the reply to our ask - parse it and
                    # resume with the ORIGINAL question that triggered it.
                    if self._is_contact_skip(cleaned):
                        contact_state.set_contact(user_id, skipped=True)
                    else:
                        parsed_name, parsed_email, parsed_division = self._parse_contact_reply(cleaned)
                        contact_state.set_contact(user_id, name=parsed_name, email=parsed_email, division=parsed_division)

                    recent_full = mem.get_recent(session_id, limit=15)
                    pending = self._extract_pending_issue(recent_full, marker="contact_asked")
                    if pending and pending != "Issue not captured":
                        cleaned = pending
                        raw = pending
        except Exception:
            logger.exception("Contact intake step failed for %s", user_id)

        # --- Ticket confirmation: handle yes/no reply to a pending ticket request ---
        try:
            if (
                getattr(settings, "ENABLE_TICKETING", True)
                and getattr(settings, "ENABLE_CONVERSATION_MEMORY", False)
                and mem
                and session_id
            ):
                recent = mem.get_recent(session_id, limit=15)
                ticket_pending = any(
                    m.get("role") == "system" and m.get("text") == "ticket_pending"
                    for m in recent
                )
                if ticket_pending:
                    if self._is_ticket_yes(cleaned):
                        issue = self._extract_pending_issue(recent)
                        conversation_summary = mem.summarize(session_id, language=language) if mem else ""
                        from core.tickets.ticket_manager import create_ticket
                        from core.tickets import state as ticket_state
                        contact = (contact_state.get_contact(user_id) if contact_state else None) or {}
                        ticket_id, sl_no = create_ticket(
                            user_id, issue, conversation_summary,
                            name=contact.get("name", ""), division=contact.get("division", ""),
                            issue_type="Handoff Request",
                        )
                        mem.save_message(session_id, "system", "ticket_created")
                        if ticket_id:
                            if sl_no:
                                # Only real tool-backed tickets (sl_no set) can
                                # receive forwarded messages via the API — an
                                # Excel-fallback id has no ticket in the tool.
                                ticket_state.set_state(user_id, ticket_id, sl_no, "Open")
                                from core.tickets import csat_state
                                csat_state.start(user_id, ticket_id, sl_no)
                            outgoing = _t("ticket_created", language).format(ref=sl_no or ticket_id)
                        else:
                            outgoing = _t("ticket_failed", language)
                        try:
                            self.whatsapp.send_message(user_id, message=outgoing)
                        except Exception:
                            pass
                        mem.save_message(session_id, "assistant", outgoing)
                        return outgoing, {"ticket_created": bool(ticket_id), "ticket_id": ticket_id, "language": language}

                    elif self._is_ticket_no(cleaned):
                        mem.save_message(session_id, "system", "ticket_declined")
                        outgoing = _t("ticket_declined", language)
                        try:
                            self.whatsapp.send_message(user_id, message=outgoing)
                        except Exception:
                            pass
                        mem.save_message(session_id, "assistant", outgoing)
                        return outgoing, {"ticket_declined": True, "language": language}
                    # else: ambiguous reply — fall through to normal RAG flow
        except Exception:
            pass

        # --- Structured intake in progress: capture the answer, ask the
        # next field, or (once every field is answered) create the ticket
        # directly. Runs before resolution/closing detection below so an
        # intake answer that happens to contain a word like "fixed" or
        # "thanks" isn't misread as ending the conversation.
        try:
            if getattr(settings, "ENABLE_TICKETING", True) and intake_state.is_active(user_id):
                step = intake_engine.handle_reply(user_id, cleaned, language)
                if step:
                    if not step.get("done"):
                        prompt = step.get("prompt", "")
                        try:
                            self.whatsapp.send_message(user_id, message=prompt)
                        except Exception:
                            pass
                        try:
                            if mem and session_id:
                                mem.save_message(session_id, "assistant", prompt)
                        except Exception:
                            pass
                        return prompt, {"intake_prompt": True, "language": language}

                    issue_type = step.get("issue_type", "")
                    issue_text = step.get("issue_text", "")
                    transcript = ""
                    try:
                        if mem and session_id:
                            transcript = self._full_transcript(mem.get_recent(session_id, limit=50))
                    except Exception:
                        pass
                    conversation_summary = transcript or issue_text

                    from core.tickets.ticket_manager import create_ticket
                    from core.tickets import state as ticket_state
                    contact = (contact_state.get_contact(user_id) if contact_state else None) or {}
                    ticket_id, sl_no = create_ticket(
                        user_id, issue_text, conversation_summary,
                        name=contact.get("name", ""), division=contact.get("division", ""),
                        status="Open", issue_type=issue_type,
                    )
                    if ticket_id:
                        if sl_no:
                            ticket_state.set_state(user_id, ticket_id, sl_no, "Open")
                            from core.tickets import csat_state
                            csat_state.start(user_id, ticket_id, sl_no)
                        outgoing = _t("ticket_created", language).format(ref=sl_no or ticket_id)
                    else:
                        outgoing = _t("ticket_failed", language)

                    try:
                        self.whatsapp.send_message(user_id, message=outgoing)
                    except Exception:
                        pass
                    try:
                        if mem and session_id:
                            mem.save_message(session_id, "assistant", outgoing)
                            mem.save_message(session_id, "system", "ticket_created")
                    except Exception:
                        pass
                    return outgoing, {
                        "ticket_created": bool(ticket_id), "ticket_id": ticket_id,
                        "issue_type": issue_type, "language": language,
                    }
        except Exception:
            logger.exception("Structured intake step failed for %s", user_id)

        # --- CSAT reply capture: a bare 1-5 while a rating is pending ---
        # Deliberately runs after structured intake above, so a digit that's
        # actually an answer to an active intake field (e.g. "how many SS")
        # isn't misread as a stale, unrelated CSAT rating.
        try:
            if getattr(settings, "ENABLE_TICKETING", True):
                from core.tickets import csat_state
                pending = csat_state.get(user_id)
                if pending and pending.get("prompted_at"):
                    rating_text = cleaned.strip()
                    if rating_text in ("1", "2", "3", "4", "5"):
                        from core.tickets.main_app_client import submit_csat
                        ok = submit_csat(pending["ticket_id"], user_id, int(rating_text))
                        if ok:
                            csat_state.clear(user_id)
                        outgoing = _t("csat_thanks", language)
                        try:
                            self.whatsapp.send_message(user_id, message=outgoing)
                        except Exception:
                            pass
                        try:
                            if mem and session_id:
                                mem.save_message(session_id, "assistant", outgoing)
                        except Exception:
                            pass
                        return outgoing, {"csat_submitted": ok, "language": language}
        except Exception:
            logger.exception("CSAT reply capture failed for %s", user_id)

        # Resolution messages -> single closing reply, close marker, and an
        # auto-logged ticket (status=Resolved) so every conversation leaves a
        # record in the main tool, not just ones that get escalated.
        if self._is_resolution_message(cleaned):
            outgoing = _t("resolution_ack", language)
            try:
                if getattr(settings, "ENABLE_CONVERSATION_MEMORY", False) and mem and session_id:
                    mem.save_message(session_id, "assistant", outgoing)
                    mem.save_message(session_id, "system", "conversation_closed")
                    self._auto_log_ticket_on_close(user_id, session_id, mem, contact_state, language=language)
            except Exception:
                pass

            try:
                self.whatsapp.send_message(user_id, message=outgoing)
            except Exception:
                pass

            return outgoing, {"conversation_closed": True, "resolution_ack": True, "language": language}

        # Closing messages -> single closing reply, close marker, and an
        # auto-logged ticket (status=Resolved), same as resolution above.
        if self._is_closing_message(cleaned):
            outgoing = _t("closing_ack", language)
            try:
                if getattr(settings, "ENABLE_CONVERSATION_MEMORY", False) and mem and session_id:
                    mem.save_message(session_id, "assistant", outgoing)
                    mem.save_message(session_id, "system", "conversation_closed")
                    self._auto_log_ticket_on_close(user_id, session_id, mem, contact_state, language=language)
            except Exception:
                pass

            try:
                self.whatsapp.send_message(user_id, message=outgoing)
            except Exception:
                pass

            return outgoing, {"conversation_closed": True, "language": language}

        # First-touch menu (shown once automatically; "menu" re-shows it -
        # e.g. after the composer below suggests it for an operational
        # request it can't itself resolve)
        try:
            if (
                getattr(settings, "ENABLE_FIRST_TOUCH_MENU", True)
                and getattr(settings, "ENABLE_CONVERSATION_MEMORY", False)
                and mem
                and session_id
            ):
                recent = mem.get_recent(session_id, limit=20)

                # Latest of {menu_shown, menu_consumed} wins, not "ever
                # occurred" - so explicitly re-showing the menu (below)
                # genuinely re-opens selection instead of being permanently
                # blocked by an old menu_consumed marker from earlier in
                # the same session.
                menu_events = [
                    m.get("text") for m in recent
                    if m.get("role") == "system" and m.get("text") in ("menu_shown", "menu_consumed")
                ]
                last_menu_event = menu_events[-1] if menu_events else None
                menu_shown = last_menu_event in ("menu_shown", "menu_consumed")
                menu_consumed = last_menu_event == "menu_consumed"

                if cleaned.strip().lower() in ("menu", "show menu", "main menu", "মেনু"):
                    try:
                        from core.menu import menu_routing
                        menu_list = menu_routing.show_menu_options(None, language=language)
                        menu_text = "\n".join(menu_list)
                        self.whatsapp.send_message(user_id, message=menu_text)
                        mem.save_message(session_id, "assistant", menu_text)
                        mem.save_message(session_id, "system", "menu_shown")
                        return menu_text, {"menu_shown": True, "language": language}
                    except Exception:
                        pass

                # show menu only if never shown before (and not consumed)
                if not menu_shown and not menu_consumed:
                    try:
                        from core.menu import menu_routing
                        menu_list = menu_routing.show_menu_options(None, language=language)
                        menu_text = "\n".join(menu_list)
                        self.whatsapp.send_message(user_id, message=menu_text)
                        mem.save_message(session_id, "assistant", menu_text)
                        mem.save_message(session_id, "system", "menu_shown")
                        return menu_text, {"menu_shown": True, "language": language}
                    except Exception:
                        pass

                # If menu shown, process numeric selection
                if menu_shown and not menu_consumed:
                    try:
                        from core.menu.menu_routing import process_menu_selection
                        sel = cleaned.strip().lower()
                        reply, meta = process_menu_selection(sel, language=language)
                        category_id = meta.get("menu_selected")

                        if category_id is not None:
                            # Categories 1, 2, 3, 4 and 7 are structured
                            # intake: skip RAG entirely and go straight to a
                            # short Q&A that ends in a ticket, since these
                            # are operational requests (unlock this account,
                            # add this SS, pull this report) a knowledge
                            # base was never going to answer - no reason to
                            # wait on a confidence threshold or a yes/no
                            # confirmation. Categories 5/6 keep the old
                            # canned/RAG-driven reply already in `reply`.
                            if category_id in INTAKE_CATEGORIES:
                                reply = intake_engine.start_intake(user_id, category_id, language)
                            if reply:
                                try:
                                    self.whatsapp.send_message(user_id, message=reply)
                                except Exception:
                                    pass
                                try:
                                    mem.save_message(session_id, "assistant", reply)
                                    mem.save_message(session_id, "system", "menu_consumed")
                                except Exception:
                                    pass
                                return reply, {**(meta or {}), "language": language}
                    except Exception:
                        pass
        except Exception:
            pass

        # --- Auto-detect a structured-intake category from free text ---
        # A user who skips the menu numbers and just types their issue
        # straight away ("my account is locked", "add SS Sabana under SK
        # Asma") is describing exactly one of the operational categories
        # above - recognize it here too (keyword-based, not an LLM call, so
        # it's free and instant) and start that category's Q&A directly,
        # rather than handing an unanswerable question to RAG and waiting
        # on a confidence threshold or handoff phrase to notice.
        try:
            if getattr(settings, "ENABLE_TICKETING", True) and mem and session_id:
                from core.intake.classifier import classify as classify_intake
                category_id = classify_intake(cleaned)
                if category_id:
                    prompt = intake_engine.start_intake(user_id, category_id, language)
                    if prompt:
                        try:
                            self.whatsapp.send_message(user_id, message=prompt)
                        except Exception:
                            pass
                        try:
                            mem.save_message(session_id, "assistant", prompt)
                            mem.save_message(session_id, "system", "menu_consumed")
                        except Exception:
                            pass
                        return prompt, {"menu_selected": category_id, "auto_classified": True, "language": language}
        except Exception:
            logger.exception("Free-text intake classification failed for %s", user_id)

        composer = self._get_composer()
        if composer is None:
            # Last resort fallback: embeddings + FAISS + LLM service
            try:
                from adapters.llm.openai_client import get_openai
                client = get_openai()
                resp = client.embeddings.create(model="text-embedding-3-small", input=cleaned)
                embedding = resp.data[0].embedding
            except Exception as e:
                logger.error(f"Embedding failed or OpenAI client unavailable: {e}")
                embedding = [0] * getattr(self.faiss, "dim", 1536)

            docs = self.faiss.search(embedding, top_k=5)
            answer = self.llm.generate_response(cleaned, docs, language=language)

            try:
                if getattr(settings, "ENABLE_CONVERSATION_MEMORY", False) and mem and session_id:
                    mem.save_message(session_id, "assistant", answer)
            except Exception:
                pass

            try:
                self.whatsapp.send_message(user_id, message=answer)
            except Exception:
                pass

            logger.info(f"Sent reply to {user_id} (fallback LLM path)")
            return answer, {"confidence": 0.0, "language": language}

        # Use RagComposer
        try:
            answer_text, meta = composer.answer(query=cleaned, language=language, session_id=session_id)
        except Exception as e:
            logger.error(f"Composer failed: {e}")
            answer_text = "Sorry, I couldn't generate a reply right now."
            meta = {"confidence": 0.0, "citations": [], "low_confidence": True}

        # Handoff detection (kept as-is, but make sure it doesn't spam)
        try:
            user_lower = (cleaned or "").strip().lower()

            explicit_re = re.compile(
                r"\b(connect me to support|please connect.*support|connect me to an agent|escalate to support"
                r"|সাপোর্টে সংযুক্ত করুন|এজেন্টের সাথে সংযুক্ত করুন|সাপোর্টে পাঠান)\b", re.I,
            )
            mild_re = re.compile(
                r"\b(talk to support|talk to a support agent|support agent|human|talk to an agent"
                r"|মানুষের সাথে কথা|এজেন্টের সাথে কথা|সাপোর্ট এজেন্ট)\b", re.I,
            )

            handoff = False
            if explicit_re.search(user_lower):
                handoff = True
            elif mild_re.search(user_lower):
                cond = False
                if meta.get("low_confidence"):
                    cond = True

                # if we already asked a clarifying question recently, allow handoff
                if getattr(settings, "ENABLE_CONVERSATION_MEMORY", False) and mem and session_id:
                    recent_msgs = mem.get_recent(session_id, limit=6)
                    for m in recent_msgs:
                        if m.get("role") == "assistant" and self._CLARIFY_SIGNAL_RE.search(m.get("text", "")):
                            cond = True
                            break

                if cond:
                    handoff = True

            if handoff:
                meta = meta or {}
                meta["handoff"] = True

                from core.tickets import state as ticket_state
                open_state = ticket_state.get_state(user_id)
                if open_state and open_state.get("status") not in ("Resolved", "Closed"):
                    # Already has an open ticket — the message above was just
                    # forwarded to it. Asking "create a ticket?" again would
                    # be redundant and confusing.
                    outgoing = _t("handoff_open_ticket_note", language).format(ref=open_state['sl_no'])
                    try:
                        if getattr(settings, "ENABLE_CONVERSATION_MEMORY", False) and mem and session_id:
                            mem.save_message(session_id, "assistant", outgoing)
                    except Exception:
                        pass
                    try:
                        self.whatsapp.send_message(user_id, message=outgoing)
                    except Exception:
                        pass
                    return outgoing, meta

                if getattr(settings, "ENABLE_TICKETING", True):
                    outgoing = _t("handoff_ticket_offer", language)
                    try:
                        if getattr(settings, "ENABLE_CONVERSATION_MEMORY", False) and mem and session_id:
                            mem.save_message(session_id, "assistant", outgoing)
                            mem.save_message(session_id, "system", "ticket_pending")
                    except Exception:
                        pass
                else:
                    outgoing = _t("handoff_no_ticketing", language)
                    try:
                        if getattr(settings, "ENABLE_CONVERSATION_MEMORY", False) and mem and session_id:
                            mem.save_message(session_id, "assistant", outgoing)
                            mem.save_message(session_id, "system", "handoff_requested")
                    except Exception:
                        pass

                try:
                    self.whatsapp.send_message(user_id, message=outgoing)
                except Exception:
                    pass

                return outgoing, meta
        except Exception:
            pass

        # Low-confidence augmentation (kept, but avoid double-asking)
        try:
            threshold = getattr(settings, "ANSWER_CONFIDENCE_THRESHOLD", 0.55)
            fallback_note = getattr(settings, "FALLBACK_MESSAGE", "")
        except Exception:
            threshold = 0.55
            fallback_note = ""

        outgoing = answer_text
        confidence = float((meta or {}).get("confidence", 0.0))
        citations = (meta or {}).get("citations", [])

        if confidence < threshold:
            clarify = _t("clarify_prompt", language)
            already_asked = False

            if (meta or {}).get("low_confidence"):
                already_asked = True
            if (meta or {}).get("citations"):
                already_asked = True
            if clarify and clarify in outgoing:
                already_asked = True

            # prevent repeating prompt if it was asked recently
            try:
                if mem and session_id:
                    recent_msgs = mem.get_recent(session_id, limit=6)
                    for m in recent_msgs:
                        if m.get("role") == "assistant" and self._CLARIFY_SIGNAL_RE.search(m.get("text", "")):
                            already_asked = True
                            break
            except Exception:
                pass

            if not already_asked:
                if fallback_note and fallback_note not in outgoing:
                    outgoing = f"{outgoing}\n\n{fallback_note}\n\n{clarify}"
                else:
                    outgoing = f"{outgoing}\n\n{clarify}"

        # Final formatting for WhatsApp
        outgoing = self._format_outgoing(outgoing)

        # Save assistant response to memory (best-effort)
        try:
            if getattr(settings, "ENABLE_CONVERSATION_MEMORY", False) and mem and session_id:
                mem.save_message(session_id, "assistant", outgoing)
        except Exception:
            pass

        # Send message
        try:
            self.whatsapp.send_message(user_id, message=outgoing)
            logger.info(f"Sent reply to {user_id} | confidence={confidence:.3f} | citations={citations}")
        except Exception as e:
            logger.error(f"Failed sending message to {user_id}: {e}")

        meta = meta or {}
        meta.setdefault("language", language)
        return outgoing, meta