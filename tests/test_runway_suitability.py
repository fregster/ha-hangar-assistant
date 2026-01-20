"""Tests for the RunwaySuitabilitySensor."""
import pytest
from unittest.mock import MagicMock
from homeassistant.core import HomeAssistant

from custom_components.hangar_assistant.sensor import RunwaySuitabilitySensor


@pytest.fixture
def mock_hass():
    """Create mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    return hass


def test_runway_suitability_matrix_best_runway(mock_hass):
    """Runway suitability returns best runway and matrix details."""
    config = {
        "name": "Test Airfield",
        "runways": "09, 18",
        "wind_sensor": "sensor.wind",
        "wind_dir_sensor": "sensor.wind_dir",
    }

    sensor = RunwaySuitabilitySensor(mock_hass, config, {})

    mock_hass.states.get.side_effect = lambda entity_id: {
        "sensor.wind": MagicMock(state="20"),
        "sensor.wind_dir": MagicMock(state="140"),
    }.get(entity_id)

    assert sensor.native_value == "18"

    attrs = sensor.extra_state_attributes
    matrix = attrs.get("runway_matrix", [])
    assert attrs.get("runways_evaluated") == 2
    assert matrix

    by_runway = {item["runway"]: item for item in matrix}
    assert by_runway["18"]["crosswind"] < by_runway["09"]["crosswind"]
    assert attrs.get("min_crosswind") == by_runway["18"]["crosswind"]
