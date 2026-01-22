"""Targeted tests for DensityAltSensor to cover branches.

Covers:
- InHg pressure path (<500) for PA calculation
- Advisory attributes: caution and warning thresholds
"""
import pytest
from unittest.mock import MagicMock

from custom_components.hangar_assistant.sensor import DensityAltSensor


def _make_hass_with_states(mapping):
    hass = MagicMock()
    hass.states = MagicMock()

    def _get(eid):
        val = mapping.get(eid)
        s = MagicMock()
        s.state = str(val) if val is not None else "0"
        return s

    hass.states.get.side_effect = _get
    return hass


def test_density_altitude_inhg_branch_returns_zero_at_isa():
    """At sea level ISA (15C, 29.92 inHg), DA should be ~0 ft."""
    hass = _make_hass_with_states({
        "sensor.temp": 15.0,
        "sensor.press": 29.92,  # inHg path (<500)
    })
    config = {
        "name": "Sea Level",
        "elevation": 0,  # meters
        "temp_sensor": "sensor.temp",
        "pressure_sensor": "sensor.press",
    }
    settings = {"unit_preference": "aviation"}

    sensor = DensityAltSensor(hass, config, settings)
    value = sensor.native_value
    assert value == 0


def test_density_altitude_advisory_caution_at_3000ft():
    """DA of 3000 ft should set advisory severity to 'caution'."""
    # Sea level, pressure standard hPa, temp 40C → DA = 120*(40-15)=3000 ft
    hass = _make_hass_with_states({
        "sensor.temp": 40.0,
        "sensor.press": 1013.25,
    })
    config = {
        "name": "Sea Level",
        "elevation": 0,
        "temp_sensor": "sensor.temp",
        "pressure_sensor": "sensor.press",
    }
    settings = {"unit_preference": "aviation"}

    sensor = DensityAltSensor(hass, config, settings)
    attrs = sensor.extra_state_attributes
    assert attrs["da_severity"] == "caution"
    assert attrs["da_status"] == "Elevated DA"


def test_density_altitude_advisory_warning_at_6000ft():
    """DA of 6000 ft should set advisory severity to 'warning'."""
    # Sea level, pressure standard hPa, temp 65C → DA = 120*(65-15)=6000 ft
    hass = _make_hass_with_states({
        "sensor.temp": 65.0,
        "sensor.press": 1013.25,
    })
    config = {
        "name": "Sea Level",
        "elevation": 0,
        "temp_sensor": "sensor.temp",
        "pressure_sensor": "sensor.press",
    }
    settings = {"unit_preference": "aviation"}

    sensor = DensityAltSensor(hass, config, settings)
    attrs = sensor.extra_state_attributes
    assert attrs["da_severity"] == "warning"
    assert attrs["da_status"] == "High DA"
