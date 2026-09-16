_LANGUAGE_NAMES = {"en": "English", "de": "German"}


def language_instruction(language: str) -> str:
    lang = (language or "en").strip().lower()
    if lang not in ("de",):
        return ""
    name = _LANGUAGE_NAMES.get(lang, lang)
    return (
        f"\n\nIMPORTANT: Respond entirely in {name}. Use natural, correct {name} "
        f"business terminology for all names, labels, and text you generate "
        f"(task names, gateway questions, explanations, summaries, etc.). "
        f"Element IDs and XML tag/attribute names must remain in English as required "
        f"by the BPMN 2.0 XML spec - only human-readable text (name=\"...\" attributes, "
        f"prose) should be in {name}."
    )
