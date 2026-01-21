"""Integration-level tests for Hangar Assistant."""
import pytest
from unittest.mock import MagicMock, patch
from homeassistant.core import HomeAssistant
from custom_components.hangar_assistant.const import DOMAIN
from custom_components.hangar_assistant.sensor import DensityAltSensor


@pytest.fixture
def mock_config_entry_data():
    return {
        "airfields": [{
            "name": "Popham",
            "latitude": 51.17,
            "longitude": -1.23,
            "elevation": 100,
            "runways": "03, 21",
            "primary_runway": "21",
            "runway_length": 800,
            "temp_sensor": "sensor.popham_temp",
            "dp_sensor": "sensor.popham_dp",
            "pressure_sensor": "sensor.popham_pressure",
            "wind_sensor": "sensor.popham_wind",
            "wind_dir_sensor": "sensor.popham_wind_dir"
        }],
        "aircraft": [{
            "reg": "G-ABCD",
            "model": "Cessna 172",
            "baseline_roll": 300,
            "linked_airfield": "Popham"
        }]
    }


def test_setup_entry(mock_config_entry_data):
    """Test that sensors are created from config entry."""
    mock_hass = MagicMock(spec=HomeAssistant)
    mock_hass.states = MagicMock()
    airfield = mock_config_entry_data["airfields"][0]

    # Test DensityAltSensor creation
    sensor = DensityAltSensor(
        mock_hass,
        airfield,
        mock_config_entry_data
    )

    assert sensor is not None
    assert sensor._attr_unique_id is not None
    assert "popham" in sensor._attr_unique_id.lower()


def test_da_calculation_updates():
    """Test that DA sensor responds to state changes."""
    mock_hass = MagicMock(spec=HomeAssistant)
    mock_hass.states = MagicMock()

    airfield = {
        "name": "Popham",
        "latitude": 51.17,
        "longitude": -1.23,
        "elevation": 100,
        "temp_sensor": "sensor.popham_temp",
        "pressure_sensor": "sensor.popham_pressure"
    }

    sensor = DensityAltSensor(mock_hass, airfield, {})

    # Mock initial temperature (15C) and pressure (1013.25 hPa)
    def get_state(entity_id):
        if entity_id == "sensor.popham_temp":
            return MagicMock(state="15")
        if entity_id == "sensor.popham_pressure":
            return MagicMock(state="1013.25")
        return None

    mock_hass.states.get.side_effect = get_state

    # Get initial DA value
    initial_da = sensor.native_value
    assert initial_da is not None

    # Now simulate temperature change to 25C
    def get_state_updated(entity_id):
        if entity_id == "sensor.popham_temp":
            return MagicMock(state="25")
        if entity_id == "sensor.popham_pressure":
            return MagicMock(state="1013.25")
        return None

    mock_hass.states.get.side_effect = get_state_updated

    # Clear cache to force re-read of updated values
    sensor._sensor_cache.clear()

    # Get updated DA value - should be higher with higher temperature
    updated_da = sensor.native_value
    assert updated_da is not None
    # Higher temperature should result in higher DA
    assert updated_da > initial_da
