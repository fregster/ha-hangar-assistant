"""Integration-level tests for Hangar Assistant."""
import pytest
from unittest.mock import patch
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from custom_components.hangar_assistant.const import DOMAIN

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

async def test_setup_entry(hass: HomeAssistant, mock_config_entry_data):
    """Test that sensors are created from config entry."""
    with patch("homeassistant.config_entries.ConfigEntry.data", mock_config_entry_data):
        # Trigger setup (this is a simplification of the real HA test pattern)
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    # Check if airfield entities exist
    assert hass.states.get("sensor.popham_density_altitude") is not None
    assert hass.states.get("binary_sensor.popham_master_safety_alert") is not None
    
    # Check aircraft entities
    assert hass.states.get("sensor.g_abcd_calculated_ground_roll") is not None

async def test_da_calculation_updates(hass: HomeAssistant, mock_config_entry_data):
    """Test that DA sensor responds to state changes."""
    with patch("homeassistant.config_entries.ConfigEntry.data", mock_config_entry_data):
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    # Set initial temperature (15C)
    hass.states.async_set("sensor.popham_temp", "15")
    hass.states.async_set("sensor.popham_pressure", "1013.25")
    await hass.async_block_till_done()
    
    da_state = hass.states.get("sensor.popham_density_altitude")
    # Elevation 100m = 328ft. ISA = 15 - 2*(328/1000) = 14.34C.
    # PA = 328 + 0 = 328ft.
    # DA = 328 + 120 * (15 - 14.34) = 407.
    assert da_state.state == "407"

    # Increase temperature by 10 degrees (should increase DA)
    # Elevation 100m = 328ft. ISA = 15 - 2*(328/1000) = 14.34C.
    # PA = 328 + (1013.25 - 1013.25)*30 = 328ft.
    # Temp 25C is 10.66C above ISA. DA = 328 + (120 * 10.66) = 1607ft.
    hass.states.async_set("sensor.popham_temp", "25")
    await hass.async_block_till_done()
    
    da_state = hass.states.get("sensor.popham_density_altitude")
    assert da_state.state == "1607"
