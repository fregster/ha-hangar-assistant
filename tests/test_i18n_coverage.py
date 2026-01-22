"""Coverage tests for i18n utilities.

Tests for translation discovery, language normalization, and localized
option generation.

Coverage focus:
    - get_available_languages with filesystem traversal
    - Fallback behavior for missing languages
    - Option generation with various languages
"""
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from custom_components.hangar_assistant.utils.i18n import (
    get_available_languages,
    get_language_options,
    normalize_lang,
    get_label,
    get_distance_unit_options,
    get_action_options,
    get_unit_preference_options,
    SUPPORTED_LANGS,
    COMMON_LABELS,
)


class TestGetAvailableLanguages:
    """Test language discovery from filesystem."""

    def test_discovers_all_supported_languages(self):
        """Test all supported language files are discovered."""
        # Call the actual implementation to verify it discovers languages
        result = get_available_languages()

        # Verify structure - should have at least English
        assert isinstance(result, list)
        assert all(isinstance(item, tuple) and len(item) == 2 for item in result)
        
        # If translations directory exists, verify we find languages
        if result:
            lang_codes = [code for code, _ in result]
            assert "en" in lang_codes

    def test_english_first_in_list(self):
        """Test English is always first in results."""
        result = get_available_languages()

        # English should be first if present
        if result:
            assert result[0][0] == "en"

    def test_all_results_valid_languages(self):
        """Test all returned languages are in supported list."""
        result = get_available_languages()

        for lang_code, lang_label in result:
            assert lang_code in SUPPORTED_LANGS

    def test_all_results_are_tuples(self):
        """Test all results are (code, label) tuples."""
        result = get_available_languages()

        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], str)  # code
            assert isinstance(item[1], str)  # label


class TestGetLanguageOptions:
    """Test language options dictionary generation."""

    def test_returns_dict(self):
        """Test returns dictionary format."""
        result = get_language_options()

        assert isinstance(result, dict)

    def test_maps_code_to_label(self):
        """Test dictionary maps language codes to labels."""
        result = get_language_options()

        for code, label in result.items():
            assert isinstance(code, str)
            assert isinstance(label, str)
            assert len(code) >= 2

    def test_includes_english(self):
        """Test English is always included."""
        result = get_language_options()

        # get_language_options should return a dict with language codes
        if result:  # Only test if translations directory exists
            assert "en" in result
            assert result["en"] == "English"


class TestNormalizeLang:
    """Test language code normalization."""

    @pytest.mark.parametrize(
        "input_lang,expected",
        [
            ("en", "en"),
            ("de", "de"),
            ("es", "es"),
            ("fr", "fr"),
            ("invalid", "en"),
            ("en_US", "en"),
            ("DE", "en"),  # Case-sensitive fallback
            ("", "en"),
            ("xyz", "en"),
        ],
    )
    def test_normalize_lang(self, input_lang, expected):
        """Test language normalization with various inputs."""
        result = normalize_lang(input_lang)

        assert result == expected


class TestGetLabel:
    """Test localized label retrieval."""

    def test_label_exists_for_language(self):
        """Test returns label when key and language exist."""
        result = get_label("en", "distance_unit_m")

        assert result == "Meters"

    def test_label_fallback_to_english(self):
        """Test returns English label when language not available."""
        # Use an unsupported language
        result = get_label("invalid", "distance_unit_m")

        # Should normalize to English and return English label
        assert result == "Meters"

    def test_label_missing_key_returns_key_itself(self):
        """Test returns key when label not found."""
        result = get_label("en", "nonexistent_key")

        assert result == "nonexistent_key"

    def test_all_supported_languages_have_labels(self):
        """Test all common labels are available in supported languages."""
        for key in COMMON_LABELS.keys():
            for lang in SUPPORTED_LANGS:
                result = get_label(lang, key)
                assert result is not None
                assert result != ""

    @pytest.mark.parametrize(
        "lang,key,expected",
        [
            ("en", "distance_unit_ft", "Feet"),
            ("de", "distance_unit_m", "Meter"),
            ("es", "action_delete", "Eliminar"),
            ("fr", "unit_pref_si", "Métrique (m, km/h, kg)"),
        ],
    )
    def test_various_labels_and_languages(self, lang, key, expected):
        """Test specific label/language combinations."""
        result = get_label(lang, key)

        assert result == expected


class TestGetDistanceUnitOptions:
    """Test distance unit selector options."""

    def test_returns_list_of_dicts(self):
        """Test returns list format."""
        result = get_distance_unit_options("en")

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(item, dict) for item in result)

    def test_options_have_required_fields(self):
        """Test each option has value and label."""
        result = get_distance_unit_options("en")

        for option in result:
            assert "value" in option
            assert "label" in option
            assert isinstance(option["value"], str)
            assert isinstance(option["label"], str)

    def test_english_options(self):
        """Test English distance options."""
        result = get_distance_unit_options("en")

        values = [opt["value"] for opt in result]
        assert "m" in values
        assert "ft" in values

    @pytest.mark.parametrize("lang", ["en", "de", "es", "fr"])
    def test_all_languages_supported(self, lang):
        """Test all supported languages return valid options."""
        result = get_distance_unit_options(lang)

        assert len(result) == 2
        assert all("value" in opt and "label" in opt for opt in result)


class TestGetActionOptions:
    """Test action selector options (edit/delete)."""

    def test_returns_list_with_two_options(self):
        """Test returns two action options."""
        result = get_action_options("en")

        assert isinstance(result, list)
        assert len(result) == 2

    def test_edit_and_delete_options(self):
        """Test contains edit and delete options."""
        result = get_action_options("en")

        values = [opt["value"] for opt in result]
        assert "edit" in values
        assert "delete" in values

    def test_english_labels(self):
        """Test English option labels."""
        result = get_action_options("en")

        labels = {opt["value"]: opt["label"] for opt in result}
        assert labels["edit"] == "Edit"
        assert labels["delete"] == "Delete"

    @pytest.mark.parametrize("lang", ["en", "de", "es", "fr"])
    def test_all_languages_supported(self, lang):
        """Test all supported languages return valid options."""
        result = get_action_options(lang)

        assert len(result) == 2
        assert all("value" in opt and "label" in opt for opt in result)


class TestGetUnitPreferenceOptions:
    """Test unit preference selector options."""

    def test_returns_list_with_two_options(self):
        """Test returns two unit preference options."""
        result = get_unit_preference_options("en")

        assert isinstance(result, list)
        assert len(result) == 2

    def test_aviation_and_si_options(self):
        """Test contains aviation and SI options."""
        result = get_unit_preference_options("en")

        values = [opt["value"] for opt in result]
        assert "aviation" in values
        assert "si" in values

    def test_english_labels(self):
        """Test English option labels."""
        result = get_unit_preference_options("en")

        labels = {opt["value"]: opt["label"] for opt in result}
        assert "ft" in labels["aviation"].lower()
        assert "kg" in labels["si"].lower()

    @pytest.mark.parametrize("lang", ["en", "de", "es", "fr"])
    def test_all_languages_supported(self, lang):
        """Test all supported languages return valid options."""
        result = get_unit_preference_options(lang)

        assert len(result) == 2
        assert all("value" in opt and "label" in opt for opt in result)

    def test_localized_labels_different(self):
        """Test labels differ between languages."""
        en_result = get_unit_preference_options("en")
        de_result = get_unit_preference_options("de")

        en_labels = {opt["value"]: opt["label"] for opt in en_result}
        de_labels = {opt["value"]: opt["label"] for opt in de_result}

        # At least one label should differ
        assert en_labels["aviation"] != de_labels["aviation"]
