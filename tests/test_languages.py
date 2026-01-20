"""Test language discovery utility."""
from pathlib import Path
import json


def test_language_files_exist():
    """Verify all language translation files exist and are valid JSON."""
    translations_dir = Path(__file__).parent.parent / "custom_components" / "hangar_assistant" / "translations"

    expected_languages = ["en", "de", "es", "fr"]
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
    """Verify all language files have the same structure (deep keys)."""
    translations_dir = Path(__file__).parent.parent / "custom_components" / "hangar_assistant" / "translations"

    # Load all language files
    files = {
        "en": json.load(open(translations_dir / "en.json")),
        "de": json.load(open(translations_dir / "de.json")),
        "es": json.load(open(translations_dir / "es.json")),
        "fr": json.load(open(translations_dir / "fr.json")),
    }

    def collect_deep_keys(obj, parent=""):
        keys = set()
        if isinstance(obj, dict):
            for k, v in obj.items():
                path = f"{parent}.{k}" if parent else k
                keys.add(path)
                keys |= collect_deep_keys(v, path)
        elif isinstance(obj, list):
            # Lists should generally not appear in translation schema; skip
            pass
        return keys

    en_deep = collect_deep_keys(files["en"])

    for lang_code in ["de", "es", "fr"]:
        lang_deep = collect_deep_keys(files[lang_code])
        missing = sorted([k for k in en_deep if k not in lang_deep])
        assert not missing, f"Language {lang_code} missing keys: {missing[:10]}{' ...' if len(missing) > 10 else ''}"

    print("✓ All languages contain the full set of English keys (deep)")

    print("✓ All language files have consistent structure")


if __name__ == "__main__":
    test_language_files_exist()
    test_language_file_completeness()
    print("\n✓ All language tests passed!")
