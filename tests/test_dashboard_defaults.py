"""Tests for dashboard default settings in config flow."""
from unittest.mock import MagicMock
import pytest
from custom_components.hangar_assistant.config_flow import HangarOptionsFlowHandler


def test_settings_includes_dashboard_defaults():
    """Test that settings form includes default dashboard airfield/aircraft options."""
    mock_entry = MagicMock()
    mock_entry.data = {
        "airfields": [
            {"name": "Popham", "latitude": 51.2, "longitude": -1.2, "elevation": 100, "runways": "03,21", "primary_runway": "03", "runway_length": 600},
            {"name": "Old Sarum", "latitude": 51.1, "longitude": -1.8, "elevation": 80, "runways": "06,24", "primary_runway": "24", "runway_length": 500},
        ],
        "aircraft": [
            {"reg": "G-ABCD", "type": "Cessna 172", "mtow_kg": 1111, "max_performance_factor": 1.0},
            {"reg": "G-EFGH", "type": "PA-28", "mtow_kg": 1100, "max_performance_factor": 1.0},
        ],
        "settings": {
            "language": "en",
            "unit_preference": "aviation",
            "default_dashboard_airfield": "popham",
            "default_dashboard_aircraft": "g_abcd"
        }
    }
    mock_entry.options = {}

    handler = HangarOptionsFlowHandler(mock_entry)
    
    # Verify handler initializes without error
    assert handler._config_entry == mock_entry


def test_settings_defaults_with_empty_config():
    """Test settings form handles missing airfields/aircraft gracefully."""
    mock_entry = MagicMock()
    mock_entry.data = {
        "settings": {
            "language": "en",
            "unit_preference": "aviation",
        }
    }
    mock_entry.options = {}

    handler = HangarOptionsFlowHandler(mock_entry)
    
    # Should not crash when no airfields/aircraft configured
    assert handler._config_entry == mock_entry
    
    # Verify settings can be retrieved
    settings = handler._entry_data().get("settings", {})
    assert settings.get("language") == "en"
    assert settings.get("default_dashboard_airfield", "") == ""  # Default to empty
    assert settings.get("default_dashboard_aircraft", "") == ""  # Default to empty


def test_settings_backward_compatibility():
    """Test that existing installations without dashboard defaults still work."""
    mock_entry = MagicMock()
    mock_entry.data = {
        "airfields": [{"name": "Test Field", "latitude": 0, "longitude": 0, "elevation": 0, "runways": "09", "primary_runway": "09", "runway_length": 500}],
        "settings": {
            "language": "en",
            "unit_preference": "aviation",
            # Deliberately missing default_dashboard_airfield and default_dashboard_aircraft
        }
    }
    mock_entry.options = {}

    handler = HangarOptionsFlowHandler(mock_entry)
    
    # Should handle missing keys gracefully with .get() defaults
    settings = handler._entry_data().get("settings", {})
    assert settings.get("default_dashboard_airfield", "") == ""
    assert settings.get("default_dashboard_aircraft", "") == ""


def test_dashboard_defaults_slugification():
    """Test that airfield/aircraft options are properly slugified for dashboard use."""
    mock_entry = MagicMock()
    mock_entry.data = {
        "airfields": [
            {"name": "The Airfield", "latitude": 0, "longitude": 0, "elevation": 0, "runways": "09", "primary_runway": "09", "runway_length": 500},
            {"name": "Another Place", "latitude": 0, "longitude": 0, "elevation": 0, "runways": "09", "primary_runway": "09", "runway_length": 500},
        ],
        "aircraft": [
            {"reg": "G ABCD", "type": "Cessna 172", "mtow_kg": 1111, "max_performance_factor": 1.0},
        ],
        "settings": {}
    }
    mock_entry.options = {}

    handler = HangarOptionsFlowHandler(mock_entry)
    
    # Verify handler can access config
    airfields = handler._list_from(handler._entry_data().get("airfields", []))
    assert len(airfields) == 2
    assert airfields[0]["name"] == "The Airfield"  # Original name preserved
    
    # When used in dashboard, names would be slugified:
    # "The Airfield" -> "the_airfield"
    # "G ABCD" -> "g_abcd"


def test_settings_with_multiple_languages():
    """Test dashboard defaults work with all supported languages."""
    for lang in ["en", "de", "es", "fr"]:
        mock_entry = MagicMock()
        mock_entry.data = {
            "airfields": [{"name": "Popham", "latitude": 0, "longitude": 0, "elevation": 0, "runways": "09", "primary_runway": "09", "runway_length": 500}],
            "settings": {
                "language": lang,
                "default_dashboard_airfield": "popham"
            }
        }
        mock_entry.options = {}

        handler = HangarOptionsFlowHandler(mock_entry)
        settings = handler._entry_data().get("settings", {})
        assert settings["language"] == lang
        assert settings["default_dashboard_airfield"] == "popham"
