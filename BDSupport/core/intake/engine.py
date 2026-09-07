"""core/intake/engine.py

Drives a structured-intake Q&A from menu selection to a compiled ticket:
ask each field for the chosen category in order (skipping optional ones on
"skip"), then hand back the compiled issue text so the caller (rag/flow.py)
can create the ticket directly - no RAG, no confidence threshold, no
yes/no confirmation, since these categories were never going to be answered
from a knowledge base anyway.
"""
from __future__ import annotations

from typing import Dict, List, Optional, TypedDict

from core.i18n import t as _t
from core.intake import state as intake_state
from core.intake.categories import CATEGORIES, IntakeCategory, field_label


class IntakeStepResult(TypedDict, total=False):
    done: bool
    prompt: str
    issue_type: str
    issue_text: str


def _is_skip(text: str, language: str) -> bool:
    words = {w.strip().lower() for w in (_t("intake_skip_words", language) or "").split(",") if w.strip()}
    return (text or "").strip().lower() in words


def _prompt_for(category: IntakeCategory, index: int, language: str) -> Optional[str]:
    if index >= len(category.fields):
        return None
    field = category.fields[index]
    prompt = _t(field.prompt_key, language)
    if field.optional:
        prompt = f"{prompt}"
    return prompt


def start_intake(phone: str, category_id: str, language: str) -> Optional[str]:
    """Begin structured intake for this category. Returns the first field's
    prompt, or None if category_id isn't a structured-intake category."""
    category = CATEGORIES.get(category_id)
    if not category:
        return None
    intake_state.start(phone, category_id, category.issue_type)
    return _prompt_for(category, 0, language)


def handle_reply(phone: str, text: str, language: str) -> Optional[IntakeStepResult]:
    """Record `text` as the answer to the current field and advance.

    Returns None if there's no active intake for this phone. Otherwise
    returns an IntakeStepResult: done=False with the next prompt, or
    done=True with the compiled issue_type/issue_text once every field has
    an answer (optional fields may be "skip"ped, which is stored as-is so
    the compiled ticket still shows what was asked and that it was skipped).
    """
    state = intake_state.get(phone)
    if not state:
        return None

    category = CATEGORIES.get(state["category_id"])
    if not category:
        # Unknown/stale category - bail out rather than getting stuck.
        intake_state.clear(phone)
        return None

    index = int(state.get("current_index", 0))
    if index < len(category.fields):
        field = category.fields[index]
        answer = "(skipped)" if (field.optional and _is_skip(text, language)) else (text or "").strip()
        state = intake_state.record_answer(phone, field.key, answer) or state
        index = int(state.get("current_index", 0))

    next_prompt = _prompt_for(category, index, language)
    if next_prompt is not None:
        return {"done": False, "prompt": next_prompt}

    issue_text = compile_issue(category, state.get("answers", {}))
    intake_state.clear(phone)
    return {"done": True, "issue_type": category.issue_type, "issue_text": issue_text}


def compile_issue(category: IntakeCategory, answers: Dict[str, str]) -> str:
    lines: List[str] = [f"[{category.issue_type}]"]
    for field in category.fields:
        value = answers.get(field.key, "Not provided")
        lines.append(f"{field_label(category, field.key)}: {value}")
    return "\n".join(lines)


def compile_partial(state: Dict) -> str:
    """Same as compile_issue, but tolerant of an incomplete answers dict -
    used by the stale-intake sweep to finalize a ticket from whatever the
    user answered before going silent."""
    category = CATEGORIES.get(state.get("category_id", ""))
    if not category:
        return "[Unknown]\n(no answers captured)"
    return compile_issue(category, state.get("answers", {}) or {})
