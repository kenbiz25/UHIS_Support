import os
import json
from datetime import datetime, timedelta, timezone

from rag.flow import BotFlow
from core.tickets import csat_state


class DummyFaiss:
    dim = 1536
    def search(self, embedding, top_k=5):
        return []


class DummyLLM:
    def generate_response(self, query, docs, language='en'):
        return "Fallback answer"


class DummyWhatsApp:
    def __init__(self):
        self.sent = []

    def send_message(self, user_id, message=None):
        self.sent.append((user_id, message))


class SpyComposer:
    def answer(self, query, language=None, session_id=None):
        return "Composer reply", {"confidence": 0.9, "citations": []}


def _reset_state(user_id):
    from core.intake import state as intake_state
    from core.tickets import state as ticket_state
    intake_state.clear(user_id)
    ticket_state.clear_state(user_id)
    csat_state.clear(user_id)


def test_structured_intake_registers_csat_tracking(tmp_path, monkeypatch):
    """Completing a structured-intake ticket should start CSAT tracking for
    it immediately, independent of core/tickets/state.py's own lifecycle."""
    from core.memory import memory_service

    orig_init = memory_service.ConversationMemory.__init__

    def fake_init(self, base_dir=None):
        return orig_init(self, base_dir=str(tmp_path / "sessions"))

    monkeypatch.setattr(memory_service.ConversationMemory, "__init__", fake_init)

    def fake_create_ticket(phone, issue, conversation_summary, name="", division="", status="Open", issue_type=""):
        return 99, "SL-0099"

    import core.tickets.ticket_manager as ticket_manager
    monkeypatch.setattr(ticket_manager, "create_ticket", fake_create_ticket)

    faiss = DummyFaiss()
    llm = DummyLLM()
    whatsapp = DummyWhatsApp()
    composer = SpyComposer()

    flow = BotFlow(faiss, llm, whatsapp, composer=composer)
    user_id = "+15550000001"
    session_id = "sess-csat-1"
    _reset_state(user_id)

    from core.contacts import state as contact_state
    contact_state.set_language(user_id, "en")
    contact_state.set_contact(user_id, skipped=True)

    from core.memory.memory_service import ConversationMemory
    mem = ConversationMemory()
    mem.save_message(session_id, "assistant", "menu text")
    mem.save_message(session_id, "system", "menu_shown")

    flow.handle_message(user_id, "1", session_id=session_id)
    flow.handle_message(user_id, "01313053555", session_id=session_id)
    flow.handle_message(user_id, "account is locked", session_id=session_id)

    state = csat_state.get(user_id)
    assert state is not None
    assert state["ticket_id"] == 99
    assert state["sl_no"] == "SL-0099"
    assert "prompted_at" not in state

    _reset_state(user_id)


def test_sweep_sends_prompt_once_resolved_and_aged(monkeypatch):
    user_id = "+15550000002"
    _reset_state(user_id)

    from core.contacts import state as contact_state
    contact_state.set_language(user_id, "en")

    csat_state.start(user_id, 42, "SL-0042")

    old_solved = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()

    import core.tickets.csat_sweep as csat_sweep

    def fake_get_status(ticket_id, phone):
        assert ticket_id == 42
        assert phone == user_id
        return {"status": "Resolved", "solved_date": old_solved, "csat_submitted": False}

    monkeypatch.setattr(csat_sweep, "get_ticket_status", fake_get_status)

    sent_messages = []

    class FakeWA:
        def send_message(self, phone, message=None):
            sent_messages.append((phone, message))

    monkeypatch.setattr(csat_sweep, "_whatsapp_service", lambda: FakeWA())

    n = csat_sweep.sweep_csat(max_age_minutes=60, force=True)

    assert n == 1
    assert len(sent_messages) == 1
    assert sent_messages[0][0] == user_id
    assert "SL-0042" in sent_messages[0][1]

    state = csat_state.get(user_id)
    assert state["prompted_at"]

    _reset_state(user_id)


def test_sweep_skips_unresolved_and_already_prompted(monkeypatch):
    user_id = "+15550000003"
    _reset_state(user_id)
    csat_state.start(user_id, 7, "SL-0007")

    import core.tickets.csat_sweep as csat_sweep
    calls = {"n": 0}

    def fake_get_status(ticket_id, phone):
        calls["n"] += 1
        return {"status": "Open", "solved_date": None, "csat_submitted": False}

    monkeypatch.setattr(csat_sweep, "get_ticket_status", fake_get_status)
    sent = []
    monkeypatch.setattr(csat_sweep, "_whatsapp_service", lambda: type("WA", (), {"send_message": lambda self, *a, **k: sent.append(1)})())

    n = csat_sweep.sweep_csat(max_age_minutes=60, force=True)
    assert n == 0
    assert sent == []
    assert calls["n"] == 1

    # Now mark as already prompted - a second sweep should skip the API call entirely.
    csat_state.mark_prompted(user_id)
    n2 = csat_sweep.sweep_csat(max_age_minutes=60, force=True)
    assert n2 == 0
    assert calls["n"] == 1  # unchanged - never re-checked

    _reset_state(user_id)


def test_reply_capture_submits_rating_and_thanks_user(tmp_path, monkeypatch):
    from core.memory import memory_service

    orig_init = memory_service.ConversationMemory.__init__

    def fake_init(self, base_dir=None):
        return orig_init(self, base_dir=str(tmp_path / "sessions"))

    monkeypatch.setattr(memory_service.ConversationMemory, "__init__", fake_init)

    faiss = DummyFaiss()
    llm = DummyLLM()
    whatsapp = DummyWhatsApp()
    composer = SpyComposer()

    flow = BotFlow(faiss, llm, whatsapp, composer=composer)
    user_id = "+15550000004"
    session_id = "sess-csat-4"
    _reset_state(user_id)

    from core.contacts import state as contact_state
    contact_state.set_language(user_id, "en")
    contact_state.set_contact(user_id, skipped=True)

    csat_state.start(user_id, 55, "SL-0055")
    csat_state.mark_prompted(user_id)

    submitted = {}

    def fake_submit_csat(ticket_id, phone, rating):
        submitted["ticket_id"] = ticket_id
        submitted["phone"] = phone
        submitted["rating"] = rating
        return True

    import core.tickets.main_app_client as main_app_client
    monkeypatch.setattr(main_app_client, "submit_csat", fake_submit_csat)

    out, meta = flow.handle_message(user_id, "5", session_id=session_id)

    assert meta.get("csat_submitted") is True
    assert submitted == {"ticket_id": 55, "phone": user_id, "rating": 5}
    assert "thank" in out.lower() or "🙏" in out
    assert csat_state.get(user_id) is None

    _reset_state(user_id)
