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
            "temp_sensor": "sensor.popham_temp",
            "dp_sensor": "sensor.popham_dp",
            "wind_sensor": "sensor.popham_wind",
            "wind_dir_sensor": "sensor.popham_wind_dir",
            "runways": "03,21",
            "runway_lengths": "800"
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

    # Set initial temperature (ISA + 15 at 4000ft)
    hass.states.async_set("sensor.popham_temp", "15")
    await hass.async_block_till_done()
    
    da_state = hass.states.get("sensor.popham_density_altitude")
    assert da_state.state == "4000"

    # Increase temperature by 10 degrees (should increase DA by 1200ft)
    hass.states.async_set("sensor.popham_temp", "25")
    await hass.async_block_till_done()
    
    da_state = hass.states.get("sensor.popham_density_altitude")
    assert da_state.state == "5200"
