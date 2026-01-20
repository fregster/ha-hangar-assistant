"""Tests for binary sensors."""
import pytest
from unittest.mock import MagicMock
from homeassistant.core import HomeAssistant
from custom_components.hangar_assistant.binary_sensor import (
    HangarMasterSafetyAlert
)


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

    # Case 3: Serious Carb Risk
    mock_hass.states.get.side_effect = lambda entity_id: {
        "sensor.test_airfield_weather_data_age": MagicMock(state="5"),
        "sensor.test_airfield_carb_risk": MagicMock(state="Serious Risk")
    }.get(entity_id)

    assert sensor.is_on is True
