"""Translation and localization utilities for Hangar Assistant."""
from pathlib import Path
from typing import Dict, List, Tuple


def get_available_languages() -> List[Tuple[str, str]]:
    """Discover available language packs and return as list of (code, label) tuples.

    Scans the translations directory for .json files (excluding base files like
    manifest.json) and maps them to friendly language names.

    Returns:
        List of tuples: (language_code, language_label)
        Example: [("en", "English"), ("de", "Deutsch"), ("fr", "Français")]

    Note:
        - Language codes must match JSON filename (en.json → "en")
        - Automatically sorted alphabetically with English first
        - Used by config_flow.py to dynamically populate language selector
    """
    language_map = {
        "en": "English",
        "de": "Deutsch",
        "es": "Español",
        "fr": "Français",
    }

    # Get the path to the translations directory
    translations_dir = Path(__file__).parent / "translations"

    available_langs = []
    for lang_file in sorted(translations_dir.glob("*.json")):
        lang_code = lang_file.stem
        if lang_code in language_map:
            available_langs.append((lang_code, language_map[lang_code]))

    # Ensure English is always first if available
    available_langs.sort(key=lambda x: (x[0] != "en", x[0]))

    return available_langs


def get_language_options() -> Dict[str, str]:
    """Return available languages as a dictionary for selector options.

    Returns:
        Dict mapping language code to language label
        Example: {"en": "English", "de": "Deutsch", "fr": "Français"}
    """
    return {code: label for code, label in get_available_languages()}
