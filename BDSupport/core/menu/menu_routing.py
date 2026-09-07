from __future__ import annotations

from typing import Optional

from core.i18n import t, menu_items
from core.intake.categories import CATEGORIES

# Selection synonyms per category, so a WhatsApp interactive-list title or a
# typed keyword routes the same as the plain number. Categories 1, 2, 3, 4
# and 7 are structured-intake categories (see core/intake/categories.py) -
# process_menu_selection only identifies which one was picked; rag/flow.py
# starts the actual field-by-field intake and creates the ticket directly
# once it's complete, with no canned reply here. Categories 5 and 6 are
# genuine "how do I..." / doc-link requests and keep a canned/dynamic reply.
_SYNONYMS = {
    "1": {"1", "one", "account", "access", "account & access", "login", "password", "unlock", "disabled", "locked"},
    "2": {
        "2", "two", "sk", "ss", "cc", "location", "add", "update",
        "add/update sk, ss, cc or location info", "mapping", "union",
    },
    "3": {"3", "three", "dashboard", "report", "reports", "quicksight", "incentive", "dashboard & reports"},
    "4": {"4", "four", "app problem", "bug", "crash", "qr", "sync"},
    "5": {"5", "five", "help", "using", "get help", "get help using spice"},
    "6": {"6", "six", "training", "guides", "training & guides"},
    "7": {"7", "seven", "other", "something else", "talk to a person", "talk to someone"},
}


def show_menu_options(context=None, language: str = "en"):
    """
    Return a short, numbered menu to present to users on first interaction or low-confidence.
    """
    return [t("menu_welcome", language)] + menu_items(language)


def _resolve(selection: str) -> Optional[str]:
    sel = (selection or "").strip().lower()
    for category_id, synonyms in _SYNONYMS.items():
        if sel in synonyms:
            return category_id
    return None


def process_menu_selection(selection: str, language: str = "en"):
    """Interpret a simple numeric or textual selection and return (reply_text, meta).

    reply_text is None for structured-intake categories (1, 2, 3, 4, 7) -
    the caller (rag/flow.py) is expected to start that category's intake
    and send its first field prompt instead. For categories 5 and 6,
    reply_text is the canned/dynamic reply, same as before.

    meta always contains "menu_selected" (the category id, or None if the
    selection wasn't recognized).
    """
    category_id = _resolve(selection)

    if category_id is None:
        return (t("menu_fallback", language), {"menu_selected": None})

    if category_id in CATEGORIES:
        # Structured intake - no canned reply; rag/flow.py drives the Q&A.
        return (None, {"menu_selected": category_id})

    if category_id == "5":
        return (t("menu_reply_help", language), {"menu_selected": "5"})

    if category_id == "6":
        try:
            from config.settings import settings
            url = getattr(settings, "SUPPORT_DOCS_URL", "")
        except Exception:
            url = ""
        note = (
            t("menu_reply_training_with_url", language).format(url=url)
            if url else t("menu_reply_training_no_url", language)
        )
        return (note, {"menu_selected": "6"})

    # Unreachable given _SYNONYMS only maps to known ids, kept as a safe fallback.
    return (t("menu_fallback", language), {"menu_selected": None})
