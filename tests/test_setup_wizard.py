"""Tests for setup wizard functionality."""
import pytest
from unittest.mock import MagicMock
from homeassistant.config_entries import ConfigEntry

from custom_components.hangar_assistant import should_show_setup_wizard
from custom_components.hangar_assistant.validation import (
    validate_icao,
    validate_registration,
    validate_mtow,
    validate_runway_length,
    validate_api_key,
    validate_latitude,
    validate_longitude,
    format_validation_message,
)
from custom_components.hangar_assistant.templates import (
    get_aircraft_template,
    get_quick_start_template,
    list_aircraft_templates,
    apply_aircraft_template,
)


def test_should_show_wizard_first_time():
    """Test welcome screen shown for first-time users."""
    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.data = {"airfields": [], "aircraft": []}
    
    assert should_show_setup_wizard(mock_entry) is True


def test_should_skip_wizard_existing_setup():
    """Test welcome skipped for existing setups."""
    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.data = {
        "settings": {"setup_completed": True},
        "airfields": [{"name": "Test"}],
        "aircraft": [],
    }
    
    assert should_show_setup_wizard(mock_entry) is False


def test_should_skip_wizard_has_airfields():
    """Test wizard skipped if airfields exist."""
    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.data = {
        "airfields": [{"name": "Popham"}],
        "aircraft": [],
    }
    
    assert should_show_setup_wizard(mock_entry) is False


def test_should_skip_wizard_has_aircraft():
    """Test wizard skipped if aircraft exist."""
    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.data = {
        "airfields": [],
        "aircraft": [{"reg": "G-ABCD"}],
    }
    
    assert should_show_setup_wizard(mock_entry) is False


# Validation tests
def test_validate_icao_valid():
    """Test ICAO validation with valid codes."""
    valid, error = validate_icao("EGHP")
    assert valid is True
    assert error is None
    
    valid, error = validate_icao("KJFK")
    assert valid is True
    assert error is None
    
    valid, error = validate_icao("LFPG")
    assert valid is True
    assert error is None


def test_validate_icao_invalid():
    """Test ICAO validation with invalid codes."""
    # Too short
    valid, error = validate_icao("EGH")
    assert valid is False
    assert "4 characters" in error
    
    # Contains number
    valid, error = validate_icao("EGH1")
    assert valid is False
    assert "only letters" in error
    
    # Lowercase - actually valid (gets auto-converted to uppercase)
    valid, error = validate_icao("eghp")
    assert valid is True  # Auto-converts to EGHP
    assert error is None
    
    # Empty string
    valid, error = validate_icao("")
    assert valid is False
    assert "required" in error
    
    # Empty
    valid, error = validate_icao("")
    assert valid is False
    assert "required" in error


def test_validate_registration_uk():
    """Test UK registration validation."""
    valid, error = validate_registration("G-ABCD")
    assert valid is True
    assert error is None


def test_validate_registration_us():
    """Test US registration validation."""
    valid, error = validate_registration("N12345")
    assert valid is True
    assert error is None
    
    valid, error = validate_registration("N1234A")
    assert valid is True
    assert error is None


def test_validate_registration_eu():
    """Test EU registration validation."""
    valid, error = validate_registration("D-EFGH")
    assert valid is True
    assert error is None


def test_validate_registration_invalid():
    """Test invalid registration formats."""
    valid, error = validate_registration("AB")
    assert valid is False
    assert "too short" in error
    
    valid, error = validate_registration("")
    assert valid is False
    assert "required" in error


def test_validate_mtow_kg():
    """Test MTOW validation in kilograms."""
    valid, error = validate_mtow(1157, "kg")
    assert valid is True
    assert error is None
    
    # Too low
    valid, error = validate_mtow(100, "kg")
    assert valid is False
    assert "unusual" in error
    
    # Too high
    valid, error = validate_mtow(10000, "kg")
    assert valid is False
    assert "unusual" in error


def test_validate_mtow_lbs():
    """Test MTOW validation in pounds."""
    valid, error = validate_mtow(2550, "lbs")
    assert valid is True
    assert error is None


def test_validate_runway_length():
    """Test runway length validation."""
    valid, error = validate_runway_length(500, "m")
    assert valid is True
    assert error is None
    
    valid, error = validate_runway_length(1640, "ft")
    assert valid is True
    assert error is None
    
    # Too short
    valid, error = validate_runway_length(50, "m")
    assert valid is False
    assert "unusual" in error


def test_validate_api_key():
    """Test API key validation."""
    # Valid CheckWX key (32+ chars)
    valid, error = validate_api_key("a" * 32, "checkwx")
    assert valid is True
    assert error is None
    
    # Too short
    valid, error = validate_api_key("short", "checkwx")
    assert valid is False
    
    # Valid OWM key (32 hex chars)
    valid, error = validate_api_key("a" * 32, "openweathermap")
    assert valid is True
    assert error is None
    
    # Invalid OWM key (non-hex)
    valid, error = validate_api_key("z" * 32, "openweathermap")
    assert valid is False
    assert "hexadecimal" in error


def test_validate_coordinates():
    """Test latitude/longitude validation."""
    valid, error = validate_latitude(51.2017)
    assert valid is True
    assert error is None
    
    valid, error = validate_latitude(-90)
    assert valid is True
    assert error is None
    
    valid, error = validate_latitude(91)
    assert valid is False
    
    valid, error = validate_longitude(-73.7781)
    assert valid is True
    assert error is None
    
    valid, error = validate_longitude(181)
    assert valid is False


def test_format_validation_message():
    """Test validation message formatting."""
    message = format_validation_message(True, "Valid ICAO code")
    assert "✅" in message
    assert "Valid ICAO code" in message
    
    message = format_validation_message(False, "Invalid format")
    assert "❌" in message
    assert "Invalid format" in message


# Template tests
def test_get_aircraft_template():
    """Test aircraft template retrieval."""
    template = get_aircraft_template("cessna_172")
    assert template["name"] == "Cessna 172 Skyhawk"
    assert template["mtow_kg"] == 1157
    assert template["fuel_type"] == "AVGAS"


def test_get_aircraft_template_not_found():
    """Test aircraft template with invalid ID."""
    with pytest.raises(KeyError):
        get_aircraft_template("invalid_template")


def test_list_aircraft_templates():
    """Test listing all aircraft templates."""
    templates = list_aircraft_templates()
    assert len(templates) > 0
    assert any(t["id"] == "cessna_172" for t in templates)
    assert any(t["id"] == "glider_generic" for t in templates)


def test_apply_aircraft_template():
    """Test applying aircraft template with registration."""
    aircraft = apply_aircraft_template("cessna_172", "G-ABCD")
    assert aircraft["reg"] == "G-ABCD"
    assert aircraft["type"] == "Cessna 172 Skyhawk"
    assert aircraft["mtow_kg"] == 1157
    assert "fuel" in aircraft
    assert aircraft["fuel"]["type"] == "AVGAS"


def test_get_quick_start_template():
    """Test quick start template retrieval."""
    template = get_quick_start_template("uk_ppl_single")
    assert template["name"] == "UK PPL Single Aircraft"
    assert "checkwx" in template["recommended_apis"]
    assert template["aircraft_template"] == "cessna_172"


def test_glider_template_zero_fuel():
    """Test glider template has zero fuel consumption."""
    template = get_aircraft_template("glider_generic")
    assert template["fuel_type"] == "NONE"
    assert template["fuel_burn_lh"] == 0
    assert template["fuel_capacity_l"] == 0
