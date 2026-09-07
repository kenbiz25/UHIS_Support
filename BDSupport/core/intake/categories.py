"""core/intake/categories.py

Defines the structured-intake categories: the ones from the first-touch
menu that skip RAG entirely and go straight from a short Q&A to a ticket,
because they're operational requests (unlock this account, add this SS,
give me this report) rather than "how do I..." questions a knowledge base
could ever answer.

Each field is (key, i18n_prompt_key, optional). Categories 5 (Get Help) and
6 (Training & Guides) are deliberately NOT here - they keep the old
RAG/doc-link behavior in rag/flow.py.
"""
from __future__ import annotations

from typing import Dict, List, NamedTuple, Optional


class IntakeField(NamedTuple):
    key: str
    prompt_key: str
    optional: bool = False


class IntakeCategory(NamedTuple):
    category_id: str
    issue_type: str
    fields: List[IntakeField]


CATEGORIES: Dict[str, IntakeCategory] = {
    "1": IntakeCategory(
        category_id="1",
        issue_type="Account & Access",
        fields=[
            IntakeField("account_id", "intake_1_account_id"),
            IntakeField("problem", "intake_1_problem"),
        ],
    ),
    "2": IntakeCategory(
        category_id="2",
        issue_type="SK/SS/CC & Location Update",
        fields=[
            IntakeField("location", "intake_2_location"),
            IntakeField("change_details", "intake_2_change_details"),
            IntakeField("mhealth_number", "intake_2_mhealth_number", optional=True),
        ],
    ),
    "3": IntakeCategory(
        category_id="3",
        issue_type="Dashboard & Report Access",
        fields=[
            IntakeField("request", "intake_3_request"),
            IntakeField("contact_email", "intake_3_contact_email"),
        ],
    ),
    "4": IntakeCategory(
        category_id="4",
        issue_type="App Functionality Issue",
        fields=[
            IntakeField("problem", "intake_4_problem"),
            IntakeField("feature", "intake_4_feature"),
            IntakeField("device_info", "intake_4_device_info", optional=True),
        ],
    ),
    "7": IntakeCategory(
        category_id="7",
        issue_type="General/Other",
        fields=[
            IntakeField("problem", "intake_7_problem"),
        ],
    ),
}

# Categories 5 (Get Help Using SPICE) and 6 (Training & Guides) keep the
# pre-existing canned/RAG behavior - not structured intake.
NON_INTAKE_CATEGORIES = {"5", "6"}


def get_category(category_id: str) -> Optional[IntakeCategory]:
    return CATEGORIES.get(category_id)


def field_label(category: IntakeCategory, key: str) -> str:
    """Human-readable label for a field key, for compiling the final ticket
    text (e.g. "account_id" -> "Account Id")."""
    return key.replace("_", " ").title()
