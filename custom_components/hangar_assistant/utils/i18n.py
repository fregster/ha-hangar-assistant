"""Translation and localization utilities for Hangar Assistant."""
from pathlib import Path
from typing import Dict, List, Tuple

SUPPORTED_LANGS = ["en", "de", "es", "fr"]

# Common labels for selector options that need localization
COMMON_LABELS: Dict[str, Dict[str, str]] = {
    "distance_unit_m": {
        "en": "Meters",
        "de": "Meter",
        "es": "Metros",
        "fr": "Mètres",
    },
    "distance_unit_ft": {
        "en": "Feet",
        "de": "Fuß",
        "es": "Pies",
        "fr": "Pieds",
    },
    "action_edit": {
        "en": "Edit",
        "de": "Bearbeiten",
        "es": "Editar",
        "fr": "Modifier",
    },
    "action_delete": {
        "en": "Delete",
        "de": "Löschen",
        "es": "Eliminar",
        "fr": "Supprimer",
    },
    "unit_pref_av": {
        "en": "Aviation (ft, kt, lbs)",
        "de": "Luftfahrt (ft, kt, lbs)",
        "es": "Aviación (ft, kt, lbs)",
        "fr": "Aviation (ft, kt, lbs)",
    },
    "unit_pref_si": {
        "en": "Metric (m, km/h, kg)",
        "de": "Metrisch (m, km/h, kg)",
        "es": "Métrico (m, km/h, kg)",
        "fr": "Métrique (m, km/h, kg)",
    },
}


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


def normalize_lang(lang: str) -> str:
    """Return a supported language code with fallback to English.

    Args:
        lang: Language code like "en", "de", "es", "fr".

    Returns:
        The same code if supported, otherwise "en".
    """
    return lang if lang in SUPPORTED_LANGS else "en"


def get_label(lang: str, key: str) -> str:
    """Get a localized label for a common option key.

    Args:
        lang: Language code
        key: One of COMMON_LABELS keys like "distance_unit_m".

    Returns:
        Localized label string, defaults to English when missing.
    """
    lang = normalize_lang(lang)
    entry = COMMON_LABELS.get(key, {})
    return entry.get(lang) or entry.get("en", key)


def get_distance_unit_options(lang: str) -> List[Dict[str, str]]:
    """Return select options for distance unit with localized labels.

    Returns a list of dicts suitable for SelectOptionDict inputs.
    """
    lang = normalize_lang(lang)
    return [
        {"value": "m", "label": get_label(lang, "distance_unit_m")},
        {"value": "ft", "label": get_label(lang, "distance_unit_ft")},
    ]


def get_action_options(lang: str) -> List[Dict[str, str]]:
    """Return common action options (edit/delete) with localized labels."""
    lang = normalize_lang(lang)
    return [
        {"value": "edit", "label": get_label(lang, "action_edit")},
        {"value": "delete", "label": get_label(lang, "action_delete")},
    ]


def get_unit_preference_options(lang: str) -> List[Dict[str, str]]:
    """Return unit preference options with localized labels."""
    lang = normalize_lang(lang)
    return [
        {"value": "aviation", "label": get_label(lang, "unit_pref_av")},
        {"value": "si", "label": get_label(lang, "unit_pref_si")},
    ]
