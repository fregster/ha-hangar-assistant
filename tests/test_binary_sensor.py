"""Tests for binary sensors."""
import pytest
from unittest.mock import MagicMock
from homeassistant.core import HomeAssistant
from custom_components.hangar_assistant.binary_sensor import (
    AircraftCrosswindAlert,
    HangarMasterSafetyAlert,
)
from custom_components.hangar_assistant.const import DEFAULT_STALE_WEATHER_MINUTES


@pytest.fixture
def mock_hass():
    """Create mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    return hass


def test_safety_alert_logic(mock_hass):
    """Test safety alert logic."""
    config = {"name": "Test Airfield"}
    sensor = HangarMasterSafetyAlert(mock_hass, config)

    # Mock internal IDs
    sensor._freshness_id = "sensor.test_airfield_weather_data_age"
    sensor._carb_id = "sensor.test_airfield_carb_risk"

    # Case 1: All Good
    mock_hass.states.get.side_effect = lambda entity_id: {
        "sensor.test_airfield_weather_data_age": MagicMock(state="10"),
        "sensor.test_airfield_carb_risk": MagicMock(state="Low Risk")
    }.get(entity_id)

    assert sensor.is_on is False

    # Case 2: Stale Data
    mock_hass.states.get.side_effect = lambda entity_id: {
        "sensor.test_airfield_weather_data_age": MagicMock(state="45"),
        "sensor.test_airfield_carb_risk": MagicMock(state="Low Risk")
    }.get(entity_id)

    assert sensor.is_on is True


def test_aircraft_crosswind_alert_within_limit(mock_hass):
    """Crosswind alert stays off when within aircraft envelope."""
    airfield = {
        "name": "Test Airfield",
        "runways": "09, 27",
        "wind_sensor": "sensor.wind",
        "wind_dir_sensor": "sensor.wind_dir",
    }
    aircraft = {
        "reg": "G-TEST",
        "max_xwind": 15,
    }

    alert = AircraftCrosswindAlert(mock_hass, aircraft, airfield, {})

    mock_hass.states.get.side_effect = lambda entity_id: {
        "sensor.wind": MagicMock(state="10"),
        "sensor.wind_dir": MagicMock(state="90"),
    }.get(entity_id)

    assert alert.is_on is False
    attrs = alert.extra_state_attributes
    assert attrs["best_runway"] == "09"
    assert attrs["within_limit"] is True


def test_aircraft_crosswind_alert_exceeds_limit(mock_hass):
    """Crosswind alert turns on when limits exceeded."""
    airfield = {
        "name": "Test Airfield",
        "runways": "09, 27",
        "wind_sensor": "sensor.wind",
        "wind_dir_sensor": "sensor.wind_dir",
    }
    aircraft = {
        "reg": "G-TEST",
        "max_xwind": 10,
    }

    alert = AircraftCrosswindAlert(mock_hass, aircraft, airfield, {})

    mock_hass.states.get.side_effect = lambda entity_id: {
        "sensor.wind": MagicMock(state="20"),
        "sensor.wind_dir": MagicMock(state="180"),
    }.get(entity_id)

    assert alert.is_on is True


def test_safety_alert_respects_threshold_attribute(mock_hass):
    """Master safety alert uses freshness threshold guardrail attribute."""
    config = {"name": "Test Airfield"}
    sensor = HangarMasterSafetyAlert(mock_hass, config, {"stale_weather_minutes": DEFAULT_STALE_WEATHER_MINUTES})

    freshness_state = MagicMock(state="40")
    freshness_state.attributes = {"threshold_minutes": 50}

    sensor._freshness_id = "sensor.test_airfield_weather_data_age"
    sensor._carb_id = "sensor.test_airfield_carb_risk"
    mock_hass.states.get.side_effect = lambda entity_id: {
        "sensor.test_airfield_weather_data_age": freshness_state,
        "sensor.test_airfield_carb_risk": MagicMock(state="Low Risk"),
    }.get(entity_id)

    assert sensor.is_on is False
