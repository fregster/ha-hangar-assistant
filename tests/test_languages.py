"""Test language discovery utility."""
from pathlib import Path
import json


def test_language_files_exist():
    """Verify all language translation files exist and are valid JSON."""
    translations_dir = Path(__file__).parent.parent / "custom_components" / "hangar_assistant" / "translations"

    expected_languages = ["en", "de", "fr"]
    for lang_code in expected_languages:
        lang_file = translations_dir / f"{lang_code}.json"
        assert lang_file.exists(), f"Translation file {lang_file} not found"

        # Verify JSON is valid
        with open(lang_file) as f:
            data = json.load(f)
            assert isinstance(data, dict), f"Translation file {lang_file} is not a valid JSON object"
            assert "config" in data, f"Translation file {lang_file} missing 'config' section"
            assert "options" in data, f"Translation file {lang_file} missing 'options' section"
            assert "entity" in data, f"Translation file {lang_file} missing 'entity' section"

    print("✓ All language files exist and are valid JSON")


def test_language_file_completeness():
    """Verify all language files have the same structure."""
    translations_dir = Path(__file__).parent.parent / "custom_components" / "hangar_assistant" / "translations"

    # Load all language files
    files = {
        "en": json.load(open(translations_dir / "en.json")),
        "de": json.load(open(translations_dir / "de.json")),
        "fr": json.load(open(translations_dir / "fr.json")),
    }

    # Get keys from English as reference
    en_keys = set(files["en"].keys())

    # Verify all languages have the same top-level keys
    for lang_code in ["de", "fr"]:
        lang_keys = set(files[lang_code].keys())
        assert en_keys == lang_keys, f"Language {lang_code} has different top-level keys than English"

    print("✓ All language files have consistent structure")


if __name__ == "__main__":
    test_language_files_exist()
    test_language_file_completeness()
    print("\n✓ All language tests passed!")
