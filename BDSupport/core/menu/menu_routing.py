from core.i18n import t, menu_items


def show_menu_options(context=None, language: str = "en"):
    """
    Return a short, numbered menu to present to users on first interaction or low-confidence.
    """
    return [t("menu_welcome", language)] + menu_items(language)


def process_menu_selection(selection: str, language: str = "en"):
    """Interpret a simple numeric or textual selection and return (reply_text, meta).

    meta may contain keys that help route the request.
    """
    sel = (selection or "").strip().lower()

    # 1: Report a Problem
    if sel in ("1", "one", "report", "system", "issue", "report a system issue", "report a problem"):
        return (t("menu_reply_1", language), {"menu_selected": "1"})

    # 2: Get Help Using SPICE
    if sel in ("2", "two", "help", "using", "get help", "get help using spice"):
        return (t("menu_reply_2", language), {"menu_selected": "2"})

    # 3: Check System Status
    if sel in ("3", "three", "status", "system status", "check system status"):
        try:
            from config.settings import settings
            url = getattr(settings, "SUPPORT_DOCS_URL", "")
        except Exception:
            url = ""
        note = t("menu_reply_3_with_url", language).format(url=url) if url else t("menu_reply_3_no_url", language)
        return (note, {"menu_selected": "3"})

    # 4: Feature request
    if sel in ("4", "four", "feature", "request", "feature request", "request a feature", "suggest an improvement"):
        return (t("menu_reply_4", language), {"menu_selected": "4"})

    # 5: Training & Guides
    if sel in ("5", "five", "training", "guides", "user guides", "training & user guides", "training & guides"):
        try:
            from config.settings import settings
            url = getattr(settings, "SUPPORT_DOCS_URL", "")
        except Exception:
            url = ""
        note = t("menu_reply_5_with_url", language).format(url=url) if url else t("menu_reply_5_no_url", language)
        return (note, {"menu_selected": "5"})

    # fallback: ask user to clarify
    return (t("menu_fallback", language), {"menu_selected": None})
