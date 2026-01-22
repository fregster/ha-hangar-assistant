"""Tests for DensityAltSensor SI advisory and elevation handling.

Test Strategy:
    - Use SI unit preference to ensure unit conversion occurs
    - Provide non-zero elevation to verify altitude contribution
    - Assert advisory metadata reflects caution/warning thresholds

Coverage:
    - DensityAltSensor.native_value for SI units
    - DensityAltSensor.extra_state_attributes advisory status
"""

from unittest.mock import MagicMock

import pytest

from custom_components.hangar_assistant.sensor import DensityAltSensor


def _make_state(value: str) -> MagicMock:
    """Create a mock HA state object with the given value."""
    state = MagicMock()
    state.state = value
    return state


def test_density_altitude_si_advisory_with_elevation():
    """Test DA advisory uses SI units and reflects non-zero elevation.

    Provides temperature, pressure, and elevation so the advisory computes
    a non-zero density altitude. Verifies that SI users still receive
    High DA messaging and the internal feet thresholds drive the status.
    """
    hass = MagicMock()
    states = {
        "sensor.temp": _make_state("20"),
        "sensor.pressure": _make_state("1013.25"),
    }
    hass.states = MagicMock()
    hass.states.get.side_effect = lambda entity_id: states.get(entity_id)

    sensor = DensityAltSensor(
        hass,
        {
            "name": "Popham",
            "elevation": 500,  # metres
            "temp_sensor": "sensor.temp",
            "pressure_sensor": "sensor.pressure",
        },
        {
            "unit_preference": "si",
            "da_caution_ft": 1000,
            "da_warning_ft": 2000,
        },
    )

    value = sensor.native_value
    attrs = sensor.extra_state_attributes

    assert value is not None and value > 0
    assert attrs["da_status"] == "High DA"
    assert attrs["da_severity"] == "warning"
    assert attrs["da_unit"] == "m"
    assert attrs["da_feet"] > 2000  # ensures elevation+temp pushed above warning
