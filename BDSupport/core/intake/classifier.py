"""core/intake/classifier.py

Lightweight, deterministic keyword classifier that recognizes when a
free-text message already describes one of the structured-intake
categories (core/intake/categories.py), even when the user skipped the
menu entirely and just typed their issue straight away. Deliberately NOT an
LLM call - it runs on every RAG-fallback message, so it needs to be free
and instant, and the categories below are exactly the concrete, recurring
request types the year of ticket history showed up overwhelmingly (account
lockouts, SK/SS/CC/location updates, dashboard/report asks, app bugs) -
simple keyword matching catches the large majority of them without needing
a model call.
"""
from __future__ import annotations

import re
from typing import Optional

_PATTERNS = {
    "1": re.compile(
        r"\b(log ?in|login|logged in|password|locked|disabled|unlock(ed)?|"
        r"invalid (credential|phone|password)|can'?t (log ?in|access|login)|"
        r"forgot(ten)? password|account (is )?(locked|disabled))\b", re.I,
    ),
    "2": re.compile(
        r"\b(sk|ss|cc|chcp|mhealth|shebika|shasthya kormi|union|upazila|"
        r"village|community clinic|health worker)\b", re.I,
    ),
    "3": re.compile(
        r"\b(quicksight|dashboard|report|incentive|glass sold|ncd report|"
        r"ncd service|glass sale)\b", re.I,
    ),
    "4": re.compile(
        r"\b(crash(ed|ing)?|not working|bug|qr code|qr scan|sync(ing)?|"
        r"not opening|white screen|freeze(s|ing)?|app (is )?broken)\b", re.I,
    ),
}

# Checked in this order - account/access and SK/SS/CC/location phrasing is
# distinctive enough to check first, before the broader app-problem net
# (category 4) that could otherwise shadow a more specific match.
_ORDER = ["1", "2", "3", "4"]


def classify(text: str) -> Optional[str]:
    """Return the structured-intake category id this free text most likely
    belongs to, or None if nothing matches confidently. Only ever returns
    one of the categories in core/intake/categories.py - category 7
    ("something else") is intentionally never auto-detected here, since it
    exists precisely to catch what this classifier can't recognize."""
    t = (text or "").strip()
    if not t:
        return None
    for category_id in _ORDER:
        if _PATTERNS[category_id].search(t):
            return category_id
    return None
