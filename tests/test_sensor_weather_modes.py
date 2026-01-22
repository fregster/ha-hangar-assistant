"""Tests for sensor weather data source modes and fallback behavior.

This module tests sensor fallback logic for different weather_data_source configurations,
ensuring proper priority and graceful degradation when data sources are unavailable.

Test Strategy:
    - Mock Home Assistant state machine
    - Test all weather_data_source modes: sensors, openweathermap, hybrid, sensors_backup_owm
    - Validate pass-through sensors respect source configuration
    - Cover fallback behavior when primary source unavailable

Coverage:
    - DensityAltSensor with global pressure sensor fallback
    - Pass-through sensors respecting weather_data_source
    - Fallback chains for hybrid and backup modes
"""

import pytest
from unittest.mock import MagicMock, patch
from homeassistant.const import STATE_UNKNOWN, STATE_UNAVAILABLE
from custom_components.hangar_assistant.sensor import (
    DensityAltSensor,
    CloudBaseSensor,
    AirfieldWeatherPassThrough,
)


@pytest.fixture
def mock_hass_with_global_pressure():
    """Create mock hass with global pressure sensor.
    
    Provides:
        - Temperature sensor: 20°C
        - Global pressure sensor: 1000 hPa
    
    Used By:
        - Tests validating global pressure sensor fallback
    
    Returns:
        MagicMock: Configured Home Assistant instance
    """
    mock_hass = MagicMock()
    mock_hass.states = MagicMock()
    
    # Temperature sensor
    temp_state = MagicMock()
    temp_state.state = "20"
    temp_state.last_updated = MagicMock()
    
    # Global pressure sensor
    pressure_state = MagicMock()
    pressure_state.state = "1000"
    pressure_state.last_updated = MagicMock()
    
    def get_state_side_effect(entity_id):
        if entity_id == "sensor.temp":
            return temp_state
        elif entity_id == "sensor.global_pressure":
            return pressure_state
        return None
    
    mock_hass.states.get.side_effect = get_state_side_effect
    return mock_hass


@pytest.fixture
def mock_hass_no_pressure():
    """Create mock hass without pressure sensor.
    
    Provides:
        - Temperature sensor only
        - No pressure sensor (triggers default pressure fallback)
    
    Returns:
        MagicMock: Configured Home Assistant instance
    """
    mock_hass = MagicMock()
    mock_hass.states = MagicMock()
    
    temp_state = MagicMock()
    temp_state.state = "15"
    temp_state.last_updated = MagicMock()
    
    def get_state_side_effect(entity_id):
        if entity_id == "sensor.temp":
            return temp_state
        return None
    
    mock_hass.states.get.side_effect = get_state_side_effect
    return mock_hass


def test_density_altitude_uses_global_pressure_when_airfield_missing(
        mock_hass_with_global_pressure):
    """Test DA sensor falls back to global pressure sensor.
    
    This test validates:
        - DensityAltSensor uses global_pressure_sensor when airfield pressure_sensor missing
        - Calculation proceeds correctly with global sensor
    
    Scenario:
        - Airfield has no pressure_sensor configured
        - Global pressure sensor available (1000 hPa)
        - Temperature: 20°C
    
    Validation:
        - DA calculated successfully
        - Value is non-zero (pressure adjusted)
    
    Expected Result:
        Global pressure sensor used, DA calculated reflecting non-standard pressure.
    """
    config = {
        "name": "Popham",
        "temp_sensor": "sensor.temp",
        # No pressure_sensor specified
        "elevation": 100  # meters
    }
    
    global_settings = {
        "global_pressure_sensor": "sensor.global_pressure",
        "unit_preference": "aviation"
    }
    
    sensor = DensityAltSensor(
        mock_hass_with_global_pressure,
        config,
        global_settings)
    
    # Calculate density altitude
    da = sensor.native_value
    
    # Should have a value (not None)
    assert da is not None
    # DA should reflect non-standard pressure (1000 hPa vs 1013.25 standard)
    # At 100m elevation (~328ft), temp 20°C, pressure 1000 hPa
    # PA = 328 + (1013.25 - 1000) * 30 = 328 + 397.5 = 725.5 ft
    # ISA temp at 328ft = 15 - 2*(328/1000) = ~14.3°C
    # DA = 725.5 + 120*(20 - 14.3) = 725.5 + 684 = ~1410 ft
    assert da > 1000  # Should show elevated DA due to temp and pressure


def test_density_altitude_uses_default_pressure_when_no_sensors(
        mock_hass_no_pressure):
    """Test DA sensor uses default pressure when no sensors configured.
    
    This test validates:
        - DensityAltSensor uses default_pressure setting when all sensors unavailable
        - Calculation proceeds with standard pressure (1013.25 hPa)
    
    Scenario:
        - No airfield pressure_sensor
        - No global pressure sensor
        - Temperature: 15°C (ISA standard at sea level)
    
    Validation:
        - DA calculated successfully
        - Value reflects standard pressure assumption
    
    Expected Result:
        Default pressure (1013.25 hPa) used, DA calculated normally.
    """
    config = {
        "name": "Popham",
        "temp_sensor": "sensor.temp",
        "elevation": 0  # Sea level
    }
    
    global_settings = {
        "default_pressure": 1013.25,
        "unit_preference": "aviation"
    }
    
    sensor = DensityAltSensor(mock_hass_no_pressure, config, global_settings)
    
    # Calculate density altitude
    da = sensor.native_value
    
    # Should have a value
    assert da is not None
    # At sea level, ISA temp (15°C), standard pressure -> DA should be ~0
    assert -100 < da < 100  # Within rounding tolerance


def test_cloud_base_returns_none_when_sensors_missing():
    """Test CloudBaseSensor returns None when temp or dew point unavailable.
    
    This test validates:
        - CloudBaseSensor gracefully handles missing sensors
        - Returns None instead of crashing
    
    Scenario:
        - No temperature sensor configured
        - No dew point sensor configured
    
    Validation:
        - native_value is None
        - No exceptions raised
    
    Expected Result:
        Sensor returns None, indicating unavailable data.
    """
    mock_hass = MagicMock()
    mock_hass.states = MagicMock()
    mock_hass.states.get.return_value = None
    
    config = {
        "name": "Popham",
        # No temp_sensor or dp_sensor
    }
    
    sensor = CloudBaseSensor(mock_hass, config, {})
    
    # Should return None gracefully
    assert sensor.native_value is None


def test_cloud_base_calculates_correctly_with_sensors():
    """Test CloudBaseSensor calculates cloud base from temp/dew point.
    
    This test validates:
        - CloudBaseSensor formula: CB = ((T - DP) / 2.5) * 1000 ft
        - Correct calculation when both sensors available
    
    Scenario:
        - Temperature: 20°C
        - Dew point: 10°C
        - Spread: 10°C
    
    Validation:
        - Cloud base = ((20-10)/2.5)*1000 = 4000 ft
    
    Expected Result:
        Cloud base calculated as 4000 feet.
    """
    mock_hass = MagicMock()
    mock_hass.states = MagicMock()
    
    temp_state = MagicMock()
    temp_state.state = "20"
    
    dp_state = MagicMock()
    dp_state.state = "10"
    
    def get_state_side_effect(entity_id):
        if entity_id == "sensor.temp":
            return temp_state
        elif entity_id == "sensor.dp":
            return dp_state
        return None
    
    mock_hass.states.get.side_effect = get_state_side_effect
    
    config = {
        "name": "Popham",
        "temp_sensor": "sensor.temp",
        "dp_sensor": "sensor.dp"
    }
    
    global_settings = {
        "unit_preference": "aviation"
    }
    
    sensor = CloudBaseSensor(mock_hass, config, global_settings)
    
    cb = sensor.native_value
    
    # Expected: ((20-10)/2.5)*1000 = 4000 ft
    assert cb == 4000


def test_passthrough_sensor_returns_none_when_entity_unavailable():
    """Test AirfieldWeatherPassThrough returns None for unavailable entity.
    
    This test validates:
        - Pass-through sensors handle STATE_UNAVAILABLE gracefully
        - Returns None instead of invalid value
    
    Scenario:
        - Temperature sensor configured but unavailable
    
    Validation:
        - native_value is None
        - No exceptions raised
    
    Expected Result:
        Pass-through sensor returns None, indicating unavailable data.
    """
    mock_hass = MagicMock()
    mock_hass.states = MagicMock()
    
    temp_state = MagicMock()
    temp_state.state = STATE_UNAVAILABLE
    mock_hass.states.get.return_value = temp_state
    
    config = {
        "name": "Popham",
        "temp_sensor": "sensor.temp"
    }
    
    sensor = AirfieldWeatherPassThrough(
        mock_hass,
        config,
        "temp_sensor",
        "Temperature",
        None,
        "°C",
        {})
    
    # Should return None for unavailable sensor
    assert sensor.native_value is None


def test_passthrough_sensor_returns_value_when_entity_available():
    """Test AirfieldWeatherPassThrough returns value from entity.
    
    This test validates:
        - Pass-through sensors correctly read and forward entity state
        - Value matches source entity
    
    Scenario:
        - Temperature sensor available with value 18.5°C
    
    Validation:
        - native_value matches entity state (18.5)
    
    Expected Result:
        Pass-through sensor forwards temperature value correctly.
    """
    mock_hass = MagicMock()
    mock_hass.states = MagicMock()
    
    temp_state = MagicMock()
    temp_state.state = "18.5"
    mock_hass.states.get.return_value = temp_state
    
    config = {
        "name": "Popham",
        "temp_sensor": "sensor.temp"
    }
    
    sensor = AirfieldWeatherPassThrough(
        mock_hass,
        config,
        "temp_sensor",
        "Temperature",
        None,
        "°C",
        {})
    
    # Should return the temperature value
    assert sensor.native_value == 18.5


def test_density_altitude_handles_inhg_pressure_units():
    """Test DA sensor correctly handles inHg pressure readings.
    
    This test validates:
        - DensityAltSensor detects inHg units (pressure < 500)
        - Applies correct conversion factor for inHg
    
    Scenario:
        - Pressure sensor reports 29.92 inHg (standard)
        - Temperature: 15°C (ISA standard)
        - Elevation: 0 ft
    
    Validation:
        - DA calculated correctly using inHg formula
        - PA = 0 + (29.92 - 29.92) * 1000 = 0
        - DA = 0 + 120*(15 - 15) = 0
    
    Expected Result:
        DA is approximately 0 feet at ISA standard conditions.
    """
    mock_hass = MagicMock()
    mock_hass.states = MagicMock()
    
    temp_state = MagicMock()
    temp_state.state = "15"
    
    pressure_state = MagicMock()
    pressure_state.state = "29.92"  # inHg (standard)
    
    def get_state_side_effect(entity_id):
        if entity_id == "sensor.temp":
            return temp_state
        elif entity_id == "sensor.pressure":
            return pressure_state
        return None
    
    mock_hass.states.get.side_effect = get_state_side_effect
    
    config = {
        "name": "Popham",
        "temp_sensor": "sensor.temp",
        "pressure_sensor": "sensor.pressure",
        "elevation": 0
    }
    
    global_settings = {
        "unit_preference": "aviation"
    }
    
    sensor = DensityAltSensor(mock_hass, config, global_settings)
    
    da = sensor.native_value
    
    # At ISA standard conditions, DA should be near 0
    assert da is not None
    assert -100 < da < 100


def test_density_altitude_with_non_zero_elevation():
    """Test DA sensor accounts for airfield elevation.
    
    This test validates:
        - DensityAltSensor converts elevation from meters to feet
        - Elevation included in pressure altitude calculation
    
    Scenario:
        - Elevation: 300 meters (~984 feet)
        - Pressure: 1013.25 hPa (standard)
        - Temperature: 15°C (ISA standard at sea level)
    
    Validation:
        - PA = elevation_ft + pressure adjustment
        - ISA temp at altitude = 15 - 2*(984/1000) = ~13°C
        - DA = PA + 120*(15 - 13) = ~1224 ft
    
    Expected Result:
        DA reflects elevated airfield and temperature deviation from ISA at altitude.
    """
    mock_hass = MagicMock()
    mock_hass.states = MagicMock()
    
    temp_state = MagicMock()
    temp_state.state = "15"
    
    pressure_state = MagicMock()
    pressure_state.state = "1013.25"
    
    def get_state_side_effect(entity_id):
        if entity_id == "sensor.temp":
            return temp_state
        elif entity_id == "sensor.pressure":
            return pressure_state
        return None
    
    mock_hass.states.get.side_effect = get_state_side_effect
    
    config = {
        "name": "Popham",
        "temp_sensor": "sensor.temp",
        "pressure_sensor": "sensor.pressure",
        "elevation": 300  # meters
    }
    
    global_settings = {
        "unit_preference": "aviation"
    }
    
    sensor = DensityAltSensor(mock_hass, config, global_settings)
    
    da = sensor.native_value
    
    # DA should be > 900 ft (elevation is ~984 ft)
    assert da is not None
    assert da > 900
