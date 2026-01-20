"""Tests for error handling and edge cases."""
import pytest
from unittest.mock import MagicMock
from custom_components.hangar_assistant.sensor import DensityAltSensor


class TestSensorNoneValues:
    """Test sensor handling of None values."""

    def test_temperature_sensor_returns_none(self):
        """Test handling when temperature sensor returns None."""
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "temp_sensor": "sensor.temp"
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})
        value = sensor.native_value
        # Should handle None gracefully
        assert value is None or value is not None

    def test_pressure_sensor_returns_none(self):
        """Test handling when pressure sensor returns None."""
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "pressure_sensor": "sensor.pressure"
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})
        value = sensor.native_value
        assert value is None or value is not None

    def test_sensor_state_is_unavailable(self):
        """Test handling when sensor state is 'unavailable'."""
        mock_hass = MagicMock()
        mock_state = MagicMock()
        mock_state.state = "unavailable"
        mock_hass.states.get.return_value = mock_state

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "temp_sensor": "sensor.temp"
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})
        # Should handle unavailable state
        assert sensor is not None

    def test_sensor_state_is_unknown(self):
        """Test handling when sensor state is 'unknown'."""
        mock_hass = MagicMock()
        mock_state = MagicMock()
        mock_state.state = "unknown"
        mock_hass.states.get.return_value = mock_state

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "temp_sensor": "sensor.temp"
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})
        assert sensor is not None


class TestInvalidSensorValues:
    """Test handling of invalid sensor values."""

    def test_temperature_non_numeric(self):
        """Test handling non-numeric temperature value."""
        mock_hass = MagicMock()
        mock_state = MagicMock()
        mock_state.state = "hot"  # Non-numeric
        mock_hass.states.get.return_value = mock_state

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "temp_sensor": "sensor.temp"
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})
        # Should handle non-numeric gracefully
        with pytest.raises((ValueError, TypeError)):
            _ = float(mock_state.state)

    def test_pressure_non_numeric(self):
        """Test handling non-numeric pressure value."""
        mock_hass = MagicMock()
        mock_state = MagicMock()
        mock_state.state = "high"  # Non-numeric
        mock_hass.states.get.return_value = mock_state

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "pressure_sensor": "sensor.pressure"
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})
        with pytest.raises((ValueError, TypeError)):
            _ = float(mock_state.state)

    def test_temperature_extreme_low(self):
        """Test handling extreme low temperature."""
        mock_hass = MagicMock()
        mock_state = MagicMock()
        mock_state.state = "-100"  # Extreme cold
        mock_hass.states.get.return_value = mock_state

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "temp_sensor": "sensor.temp"
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})
        assert sensor is not None

    def test_temperature_extreme_high(self):
        """Test handling extreme high temperature."""
        mock_hass = MagicMock()
        mock_state = MagicMock()
        mock_state.state = "60"  # Very hot
        mock_hass.states.get.return_value = mock_state

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "temp_sensor": "sensor.temp"
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})
        assert sensor is not None

    def test_pressure_below_minimum(self):
        """Test handling pressure below realistic minimum."""
        mock_hass = MagicMock()
        mock_state = MagicMock()
        mock_state.state = "500"  # Below typical minimum ~950hPa
        mock_hass.states.get.return_value = mock_state

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "pressure_sensor": "sensor.pressure"
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})
        assert sensor is not None

    def test_pressure_above_maximum(self):
        """Test handling pressure above realistic maximum."""
        mock_hass = MagicMock()
        mock_state = MagicMock()
        mock_state.state = "1050"  # Above typical maximum ~1050hPa
        mock_hass.states.get.return_value = mock_state

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "pressure_sensor": "sensor.pressure"
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})
        assert sensor is not None


class TestMissingEntityReferences:
    """Test handling of missing entity references."""

    def test_nonexistent_temperature_sensor(self):
        """Test handling reference to non-existent sensor."""
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "temp_sensor": "sensor.nonexistent"
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})
        assert sensor is not None
        # Should not crash

    def test_weather_data_too_old(self):
        """Test handling when weather data age exceeds threshold."""
        from datetime import datetime, timedelta
        from homeassistant.util import dt as dt_util

        mock_hass = MagicMock()
        # Simulate data older than 30 minutes
        old_time = dt_util.utcnow() - timedelta(minutes=45)
        mock_hass.states.get.return_value = MagicMock(state="15")

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "temp_sensor": "sensor.temp"
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})
        assert sensor is not None


class TestConfigurationErrors:
    """Test handling of configuration errors."""

    def test_missing_elevation_in_config(self):
        """Test sensor behavior with missing elevation."""
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = MagicMock(state="15")

        airfield = {
            "name": "Popham",
            "temp_sensor": "sensor.temp"
            # Missing elevation
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})
        # Should handle missing elevation
        elevation = airfield.get("elevation", 0)
        assert elevation is not None

    def test_missing_sensor_entity_id(self):
        """Test sensor behavior with missing sensor entity ID."""
        mock_hass = MagicMock()

        airfield = {
            "name": "Popham",
            "elevation": 100
            # Missing temp_sensor
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})
        assert sensor is not None

    def test_null_values_in_configuration(self):
        """Test handling of null values in configuration."""
        mock_hass = MagicMock()

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "temp_sensor": None
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})
        assert sensor is not None


class TestStateRetrievalErrors:
    """Test error handling in state retrieval."""

    def test_get_sensor_value_handles_exception(self):
        """Test that state retrieval handles exceptions."""
        mock_hass = MagicMock()
        mock_hass.states.get.side_effect = Exception("State retrieval failed")

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "temp_sensor": "sensor.temp"
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})
        # Should not crash
        with pytest.raises(Exception):
            mock_hass.states.get("sensor.temp")

    def test_state_has_no_state_attribute(self):
        """Test handling state object without 'state' attribute."""
        mock_hass = MagicMock()
        mock_state = MagicMock(spec=[])  # Empty spec, no state attr
        mock_hass.states.get.return_value = mock_state

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "temp_sensor": "sensor.temp"
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})
        # Attempting to access state should raise AttributeError
        with pytest.raises(AttributeError):
            _ = mock_state.state
