"""Tests for i18n selector option label helpers."""
from custom_components.hangar_assistant.utils.i18n import (
    get_label,
    get_distance_unit_options,
    get_action_options,
    get_unit_preference_options,
)


def test_get_label_supported_languages():
    keys = [
        "distance_unit_m",
        "distance_unit_ft",
        "action_edit",
        "action_delete",
        "unit_pref_av",
        "unit_pref_si",
    ]
    langs = ["en", "de", "es", "fr"]
    for key in keys:
        for lang in langs:
            label = get_label(lang, key)
            assert isinstance(label, str) and len(label) > 0


def test_distance_unit_options_localized():
    opts_en = get_distance_unit_options("en")
    assert opts_en[0]["value"] == "m"
    assert "Meters" in opts_en[0]["label"]
    opts_de = get_distance_unit_options("de")
    assert "Meter" in opts_de[0]["label"]
    opts_es = get_distance_unit_options("es")
    assert "Metros" in opts_es[0]["label"]
    opts_fr = get_distance_unit_options("fr")
    assert "Mètres" in opts_fr[0]["label"]


def test_action_options_localized():
    for lang, edit_word in [("en", "Edit"), ("de", "Bearbeiten"), ("es", "Editar"), ("fr", "Modifier")]:
        opts = get_action_options(lang)
        assert any(o["label"].startswith(edit_word) for o in opts)


def test_unit_preference_options_localized():
    for lang in ["en", "de", "es", "fr"]:
        opts = get_unit_preference_options(lang)
        assert len(opts) == 2
        assert all(isinstance(o["label"], str) and len(o["label"]) > 0 for o in opts)
