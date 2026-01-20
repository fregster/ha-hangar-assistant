"""Tests for PerformanceMarginSensor."""
import pytest
from unittest.mock import MagicMock
from homeassistant.core import HomeAssistant

from custom_components.hangar_assistant.sensor import PerformanceMarginSensor


@pytest.fixture
def mock_hass():
    """Create mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    return hass


def test_performance_margin_with_da(mock_hass):
    """Margin uses DA-adjusted roll when density altitude is available."""
    aircraft = {
        "reg": "G-TEST",
        "baseline_roll": 300,
        "linked_airfield": "Test Airfield",
    }
    airfield = {
        "name": "Test Airfield",
        "runway_length": 1000,
    }

    sensor = PerformanceMarginSensor(mock_hass, aircraft, airfield, {})

    mock_hass.states.get.side_effect = lambda entity_id: {
        "sensor.test_airfield_density_altitude": MagicMock(state="5000"),
        "sensor.test_airfield_best_runway": MagicMock(state="09"),
    }.get(entity_id)

    assert sensor.native_value == 55.0
    attrs = sensor.extra_state_attributes
    assert attrs["recommended_runway"] == "09"
    assert attrs["required_distance"] is not None


def test_performance_margin_fallback_without_da(mock_hass):
    """Margin falls back to conservative factor when DA is unavailable."""
    aircraft = {
        "reg": "G-TEST",
        "baseline_roll": 300,
        "linked_airfield": "Test Airfield",
    }
    airfield = {
        "name": "Test Airfield",
        "runway_length": 1000,
    }

    sensor = PerformanceMarginSensor(mock_hass, aircraft, airfield, {})

    mock_hass.states.get.return_value = None  # No DA available

    # Required = 300 * 1.15 = 345; margin = (1000-345)/1000 = 65.5%
    assert sensor.native_value == 65.5
    attrs = sensor.extra_state_attributes
    assert attrs["density_altitude_ft"] == 0.0
