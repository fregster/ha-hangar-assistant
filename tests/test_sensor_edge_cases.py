"""Edge case tests for sensor platform.

Covers caching behavior, handling of unavailable/unknown/non-numeric states,
cache eviction, and global sensor fallback in `DensityAltSensor`.
"""
from unittest.mock import MagicMock
import time
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

from custom_components.hangar_assistant.sensor import (
    HangarSensorBase,
    DensityAltSensor,
)


class TestHangarSensorBaseEdgeCases:
    """Edge-case tests for HangarSensorBase helper methods."""

    def _make_base(self, cache_ttl: int = 60):
        hass = MagicMock()
        hass.states = MagicMock()
        config = {"name": "Test Airfield"}
        settings = {"cache_ttl_seconds": cache_ttl}
        return hass, HangarSensorBase(hass, config, settings)

    def test_get_sensor_value_caches_within_ttl(self):
        """Successive reads within TTL return cached value, not new state."""
        hass, base = self._make_base(cache_ttl=60)

        first_state = MagicMock(state="10.0")
        second_state = MagicMock(state="20.0")
        hass.states.get.side_effect = [first_state, second_state]

        v1 = base._get_sensor_value("sensor.temp")
        v2 = base._get_sensor_value("sensor.temp")

        assert v1 == 10.0
        assert v2 == 10.0  # still cached

    def test_get_sensor_value_unavailable_returns_none(self):
        """Unavailable states are ignored and return None."""
        hass, base = self._make_base()
        hass.states.get.return_value = MagicMock(state=STATE_UNAVAILABLE)

        v = base._get_sensor_value("sensor.temp")
        assert v is None

    def test_get_sensor_value_unknown_returns_none(self):
        """Unknown states are ignored and return None."""
        hass, base = self._make_base()
        hass.states.get.return_value = MagicMock(state=STATE_UNKNOWN)

        v = base._get_sensor_value("sensor.temp")
        assert v is None

    def test_get_sensor_value_non_numeric_returns_none(self):
        """Non-numeric state strings are handled safely and return None."""
        hass, base = self._make_base()
        hass.states.get.return_value = MagicMock(state="abc")

        v = base._get_sensor_value("sensor.temp")
        assert v is None

    def test_sensor_cache_eviction_removes_oldest(self):
        """Cache evicts oldest entries after exceeding 50 keys."""
        hass, base = self._make_base()

        # Provide numeric states for each sensor id
        def make_state(val: float):
            s = MagicMock()
            s.state = str(val)
            return s

        # Fill >50 entries
        states = [make_state(i) for i in range(55)]
        hass.states.get.side_effect = states

        for i in range(55):
            base._get_sensor_value(f"sensor.temp_{i}")
            # small sleep to ensure increasing timestamps
            time.sleep(0.001)

        # Cache should cap at 50 entries
        assert len(base._sensor_cache) == 50


class TestDensityAltitudeGlobalFallback:
    """Test `DensityAltSensor` uses global pressure sensor if local missing."""

    def test_uses_global_pressure_when_missing_local(self):
        """If `pressure_sensor` missing, falls back to `global_pressure_sensor`."""
        hass = MagicMock()
        hass.states = MagicMock()

        def state_for(entity_id: str):
            s = MagicMock()
            if entity_id == "sensor.temp":
                s.state = "15.0"  # ISA temp at sea level
            elif entity_id == "sensor.pressure_global":
                s.state = "1013.25"  # Standard pressure
            else:
                s.state = "0"
            return s

        def states_get(eid):
            return state_for(eid)

        hass.states.get.side_effect = states_get

        config = {
            "name": "Popham",
            "elevation": 100,  # meters
            "temp_sensor": "sensor.temp",
            # intentionally omit local pressure_sensor
        }
        settings = {
            "unit_preference": "aviation",
            "global_pressure_sensor": "sensor.pressure_global",
        }

        sensor = DensityAltSensor(hass, config, settings)
        value = sensor.native_value

        # Should have used the global pressure sensor
        hass.states.get.assert_any_call("sensor.pressure_global")
        assert value is not None

    def test_missing_temp_returns_none(self):
        """If temp sensor missing/unavailable, DA returns None."""
        hass = MagicMock()
        hass.states = MagicMock()
        hass.states.get.return_value = MagicMock(state=STATE_UNAVAILABLE)

        config = {
            "name": "Popham",
            "elevation": 100,
            # temp_sensor intentionally missing
        }
        settings = {
            "unit_preference": "aviation",
        }

        sensor = DensityAltSensor(hass, config, settings)
        value = sensor.native_value
        assert value is None
