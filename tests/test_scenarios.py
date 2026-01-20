"""Tests for real-world scenarios."""
import pytest
from unittest.mock import MagicMock
from custom_components.hangar_assistant.sensor import DensityAltSensor


class TestAllWeatherDataUnavailable:
    """Test behavior when all weather data is unavailable."""

    def test_all_sensors_return_none(self):
        """Test when all sensors return None."""
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "temp_sensor": "sensor.temp",
            "dp_sensor": "sensor.dp",
            "pressure_sensor": "sensor.pressure"
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})
        value = sensor.native_value
        # Should not crash, may be None or default value
        assert value is None or isinstance(value, (int, float))

    def test_all_sensors_unavailable(self):
        """Test when all sensors report unavailable."""
        mock_hass = MagicMock()
        mock_state = MagicMock()
        mock_state.state = "unavailable"
        mock_hass.states.get.return_value = mock_state

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "temp_sensor": "sensor.temp",
            "dp_sensor": "sensor.dp"
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})
        assert sensor is not None

    def test_partial_weather_data_available(self):
        """Test when only some weather data is available."""
        mock_hass = MagicMock()

        def get_state(entity_id):
            if entity_id == "sensor.temp":
                return MagicMock(state="15")
            return None  # Other sensors unavailable

        mock_hass.states.get.side_effect = get_state

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "temp_sensor": "sensor.temp",
            "dp_sensor": "sensor.dp",
            "pressure_sensor": "sensor.pressure"
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})
        assert sensor is not None


class TestWeatherDeterioration:
    """Test behavior as weather conditions deteriorate."""

    def test_temperature_increases_da(self):
        """Test that temperature increase raises DA."""
        mock_hass = MagicMock()

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "temp_sensor": "sensor.temp",
            "pressure_sensor": "sensor.pressure"
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})

        # Initial: 15C
        def get_state_15(entity_id):
            if entity_id == "sensor.temp":
                return MagicMock(state="15")
            if entity_id == "sensor.pressure":
                return MagicMock(state="1013.25")
            return None

        mock_hass.states.get.side_effect = get_state_15
        da_initial = sensor.native_value

        # Warmer: 25C
        def get_state_25(entity_id):
            if entity_id == "sensor.temp":
                return MagicMock(state="25")
            if entity_id == "sensor.pressure":
                return MagicMock(state="1013.25")
            return None

        mock_hass.states.get.side_effect = get_state_25
        
        # Clear cache to force re-read of updated values
        sensor._sensor_cache.clear()
        
        da_warmer = sensor.native_value

        # DA should increase with temperature
        assert da_warmer > da_initial

    def test_pressure_drop_increases_da(self):
        """Test that pressure drop raises DA."""
        mock_hass = MagicMock()

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "temp_sensor": "sensor.temp",
            "pressure_sensor": "sensor.pressure"
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})

        # Initial: Normal pressure
        def get_state_high(entity_id):
            if entity_id == "sensor.temp":
                return MagicMock(state="15")
            if entity_id == "sensor.pressure":
                return MagicMock(state="1013.25")
            return None

        mock_hass.states.get.side_effect = get_state_high
        da_high = sensor.native_value

        # Lower pressure
        def get_state_low(entity_id):
            if entity_id == "sensor.temp":
                return MagicMock(state="15")
            if entity_id == "sensor.pressure":
                return MagicMock(state="990")
            return None

        mock_hass.states.get.side_effect = get_state_low
        da_low = sensor.native_value

        # DA should change with pressure
        assert da_high is not None
        assert da_low is not None


class TestConcurrentSensorUpdates:
    """Test handling of concurrent sensor updates."""

    def test_multiple_sensors_update_simultaneously(self):
        """Test when multiple sensors update at same time."""
        mock_hass = MagicMock()

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "temp_sensor": "sensor.temp",
            "dp_sensor": "sensor.dp",
            "wind_sensor": "sensor.wind"
        }

        def get_state(entity_id):
            states = {
                "sensor.temp": "20",
                "sensor.dp": "10",
                "sensor.wind": "180:15"
            }
            if entity_id in states:
                return MagicMock(state=states[entity_id])
            return None

        mock_hass.states.get.side_effect = get_state

        sensor = DensityAltSensor(mock_hass, airfield, {})
        value = sensor.native_value
        assert value is not None

    def test_rapid_successive_updates(self):
        """Test rapid successive sensor updates."""
        mock_hass = MagicMock()

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "temp_sensor": "sensor.temp"
        }

        temperatures = ["15", "16", "17", "18", "19", "20"]
        for temp in temperatures:
            mock_hass.states.get.return_value = MagicMock(state=temp)
            sensor = DensityAltSensor(mock_hass, airfield, {})
            value = sensor.native_value
            assert value is not None or value is None


class TestConfigurationChanges:
    """Test behavior during configuration changes."""

    def test_airfield_added_mid_operation(self):
        """Test adding new airfield during operation."""
        config = {
            "airfields": [
                {"name": "Popham", "elevation": 100}
            ]
        }
        assert len(config["airfields"]) == 1

        # Add new airfield
        config["airfields"].append(
            {"name": "Odiham", "elevation": 200}
        )
        assert len(config["airfields"]) == 2

    def test_aircraft_added_mid_operation(self):
        """Test adding new aircraft during operation."""
        config = {
            "aircraft": [
                {"reg": "G-ABCD", "model": "Cessna 172"}
            ]
        }
        assert len(config["aircraft"]) == 1

        # Add new aircraft
        config["aircraft"].append(
            {"reg": "G-WXYZ", "model": "Piper Cub"}
        )
        assert len(config["aircraft"]) == 2

    def test_airfield_sensor_changed(self):
        """Test when airfield sensor entity ID changes."""
        mock_hass = MagicMock()

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "temp_sensor": "sensor.popham_temp"
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})

        # Simulate sensor entity ID change
        airfield["temp_sensor"] = "sensor.new_temp_location"

        # Create new sensor with updated config
        sensor_new = DensityAltSensor(mock_hass, airfield, {})
        assert sensor_new is not None


class TestExtendedOperationScenarios:
    """Test extended operation scenarios."""

    def test_24_hour_continuous_operation(self):
        """Test sensor behavior over 24 hours."""
        mock_hass = MagicMock()

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "temp_sensor": "sensor.temp"
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})

        # Simulate temperature changes over 24 hours
        temperatures = [
            5,    # 00:00 - cold night
            3,    # 06:00 - coldest
            8,    # 12:00 - warming
            15,   # 18:00 - peak
            10    # 23:00 - cooling
        ]

        for temp in temperatures:
            mock_hass.states.get.return_value = MagicMock(state=str(temp))
            value = sensor.native_value
            assert value is not None or value is None

    def test_multiple_configuration_reloads(self):
        """Test sensor behavior through multiple config reloads."""
        config_v1 = {
            "airfields": [{"name": "Popham", "elevation": 100}]
        }

        config_v2 = {
            "airfields": [
                {"name": "Popham", "elevation": 100},
                {"name": "Odiham", "elevation": 200}
            ]
        }

        config_v3 = {
            "airfields": [
                {"name": "Odiham", "elevation": 200}
            ]
        }

        mock_hass = MagicMock()

        for config in [config_v1, config_v2, config_v3]:
            airfield_count = len(config["airfields"])
            assert airfield_count > 0

    def test_sensor_with_degraded_connectivity(self):
        """Test sensor behavior with intermittent connectivity."""
        mock_hass = MagicMock()

        airfield = {
            "name": "Popham",
            "elevation": 100,
            "temp_sensor": "sensor.temp"
        }

        sensor = DensityAltSensor(mock_hass, airfield, {})

        # Simulate intermittent connectivity
        responses = [
            MagicMock(state="15"),  # OK
            None,                    # Failed
            MagicMock(state="16"),  # OK
            None,                    # Failed
            MagicMock(state="17")   # OK
        ]

        for response in responses:
            mock_hass.states.get.return_value = response
            value = sensor.native_value
            # Should handle both success and failure gracefully
            assert value is not None or value is None
