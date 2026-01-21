"""Test sensor value caching functionality."""
import time
from unittest.mock import MagicMock
import pytest
from homeassistant.const import STATE_UNKNOWN, STATE_UNAVAILABLE
from custom_components.hangar_assistant.sensor import HangarSensorBase


class MockSensor(HangarSensorBase):
    """Mock sensor subclass for testing."""
    
    @property
    def name(self):
        """Return sensor name."""
        return "Test Sensor"


def test_cache_hit():
    """Test that cached values are returned within TTL."""
    mock_hass = MagicMock()
    mock_state = MagicMock()
    mock_state.state = "25.5"
    mock_hass.states.get.return_value = mock_state
    
    config = {"name": "Test"}
    global_settings = {"cache_ttl_seconds": 60}
    sensor = MockSensor(mock_hass, config, global_settings)
    
    # First call should hit the state machine
    value1 = sensor._get_sensor_value("sensor.test")
    assert value1 == 25.5
    assert mock_hass.states.get.call_count == 1
    
    # Second call within TTL should use cache
    value2 = sensor._get_sensor_value("sensor.test")
    assert value2 == 25.5
    # State machine should not be called again
    assert mock_hass.states.get.call_count == 1


def test_cache_miss_after_ttl():
    """Test that cache expires after TTL."""
    mock_hass = MagicMock()
    mock_state1 = MagicMock()
    mock_state1.state = "25.5"
    mock_state2 = MagicMock()
    mock_state2.state = "26.0"
    
    # Return different values on successive calls
    mock_hass.states.get.side_effect = [mock_state1, mock_state2]
    
    config = {"name": "Test"}
    global_settings = {"cache_ttl_seconds": 1}  # 1 second TTL for fast test
    sensor = MockSensor(mock_hass, config, global_settings)
    
    # First call
    value1 = sensor._get_sensor_value("sensor.test")
    assert value1 == 25.5
    
    # Wait for cache to expire
    time.sleep(1.1)
    
    # Second call should fetch new value
    value2 = sensor._get_sensor_value("sensor.test")
    assert value2 == 26.0
    assert mock_hass.states.get.call_count == 2


def test_cache_different_entities():
    """Test that different entities have separate cache entries."""
    mock_hass = MagicMock()
    
    mock_state1 = MagicMock()
    mock_state1.state = "25.5"
    mock_state2 = MagicMock()
    mock_state2.state = "30.0"
    
    def get_state(entity_id):
        if entity_id == "sensor.temp":
            return mock_state1
        elif entity_id == "sensor.pressure":
            return mock_state2
        return None
    
    mock_hass.states.get.side_effect = get_state
    
    config = {"name": "Test"}
    global_settings = {"cache_ttl_seconds": 60}
    sensor = MockSensor(mock_hass, config, global_settings)
    
    # Get values for different entities
    temp = sensor._get_sensor_value("sensor.temp")
    pressure = sensor._get_sensor_value("sensor.pressure")
    
    assert temp == 25.5
    assert pressure == 30.0
    assert mock_hass.states.get.call_count == 2
    
    # Both should be cached
    temp2 = sensor._get_sensor_value("sensor.temp")
    pressure2 = sensor._get_sensor_value("sensor.pressure")
    
    assert temp2 == 25.5
    assert pressure2 == 30.0
    # No additional calls to state machine
    assert mock_hass.states.get.call_count == 2


def test_cache_unavailable_state():
    """Test that unavailable states are not cached."""
    mock_hass = MagicMock()
    mock_state = MagicMock()
    mock_state.state = STATE_UNAVAILABLE
    mock_hass.states.get.return_value = mock_state
    
    config = {"name": "Test"}
    global_settings = {"cache_ttl_seconds": 60}
    sensor = MockSensor(mock_hass, config, global_settings)
    
    # First call with unavailable state
    value1 = sensor._get_sensor_value("sensor.test")
    assert value1 is None
    
    # Second call should still query state machine (not cached)
    value2 = sensor._get_sensor_value("sensor.test")
    assert value2 is None
    assert mock_hass.states.get.call_count == 2


def test_cache_unknown_state():
    """Test that unknown states are not cached."""
    mock_hass = MagicMock()
    mock_state = MagicMock()
    mock_state.state = STATE_UNKNOWN
    mock_hass.states.get.return_value = mock_state
    
    config = {"name": "Test"}
    global_settings = {"cache_ttl_seconds": 60}
    sensor = MockSensor(mock_hass, config, global_settings)
    
    # First call with unknown state
    value1 = sensor._get_sensor_value("sensor.test")
    assert value1 is None
    
    # Second call should still query state machine (not cached)
    value2 = sensor._get_sensor_value("sensor.test")
    assert value2 is None
    assert mock_hass.states.get.call_count == 2


def test_cache_invalid_value():
    """Test that invalid (non-numeric) values are not cached."""
    mock_hass = MagicMock()
    mock_state = MagicMock()
    mock_state.state = "not_a_number"
    mock_hass.states.get.return_value = mock_state
    
    config = {"name": "Test"}
    global_settings = {"cache_ttl_seconds": 60}
    sensor = MockSensor(mock_hass, config, global_settings)
    
    # First call with invalid value
    value1 = sensor._get_sensor_value("sensor.test")
    assert value1 is None
    
    # Second call should still query state machine (not cached)
    value2 = sensor._get_sensor_value("sensor.test")
    assert value2 is None
    assert mock_hass.states.get.call_count == 2


def test_cache_cleanup():
    """Test that cache cleanup prevents unbounded growth."""
    mock_hass = MagicMock()
    
    config = {"name": "Test"}
    global_settings = {"cache_ttl_seconds": 60}
    sensor = MockSensor(mock_hass, config, global_settings)
    
    # Create 52 cache entries (exceeds max of 50)
    for i in range(52):
        mock_state = MagicMock()
        mock_state.state = str(i)
        mock_hass.states.get.return_value = mock_state
        
        sensor._get_sensor_value(f"sensor.test_{i}")
    
    # Cache should be capped at 50 entries
    assert len(sensor._sensor_cache) == 50


def test_cache_default_ttl():
    """Test that cache uses default TTL when not configured."""
    mock_hass = MagicMock()
    mock_state = MagicMock()
    mock_state.state = "25.5"
    mock_hass.states.get.return_value = mock_state
    
    config = {"name": "Test"}
    global_settings = {}  # No cache_ttl_seconds set
    sensor = MockSensor(mock_hass, config, global_settings)
    
    # Should use DEFAULT_SENSOR_CACHE_TTL_SECONDS (60)
    value1 = sensor._get_sensor_value("sensor.test")
    assert value1 == 25.5
    
    # Should use cache
    value2 = sensor._get_sensor_value("sensor.test")
    assert value2 == 25.5
    assert mock_hass.states.get.call_count == 1


def test_cache_configurable_ttl():
    """Test that cache TTL can be configured."""
    mock_hass = MagicMock()
    mock_state = MagicMock()
    mock_state.state = "25.5"
    mock_hass.states.get.return_value = mock_state
    
    config = {"name": "Test"}
    
    # Test with short TTL
    global_settings = {"cache_ttl_seconds": 2}
    sensor = MockSensor(mock_hass, config, global_settings)
    
    value1 = sensor._get_sensor_value("sensor.test")
    assert value1 == 25.5
    
    # Wait less than TTL
    time.sleep(1)
    value2 = sensor._get_sensor_value("sensor.test")
    assert value2 == 25.5
    # Should still be using cache
    assert mock_hass.states.get.call_count == 1


def test_cache_zero_values():
    """Test that zero values are cached correctly."""
    mock_hass = MagicMock()
    mock_state = MagicMock()
    mock_state.state = "0.0"
    mock_hass.states.get.return_value = mock_state
    
    config = {"name": "Test"}
    global_settings = {"cache_ttl_seconds": 60}
    sensor = MockSensor(mock_hass, config, global_settings)
    
    # First call
    value1 = sensor._get_sensor_value("sensor.test")
    assert value1 == 0.0
    
    # Second call should use cache
    value2 = sensor._get_sensor_value("sensor.test")
    assert value2 == 0.0
    assert mock_hass.states.get.call_count == 1


def test_cache_negative_values():
    """Test that negative values are cached correctly."""
    mock_hass = MagicMock()
    mock_state = MagicMock()
    mock_state.state = "-15.5"
    mock_hass.states.get.return_value = mock_state
    
    config = {"name": "Test"}
    global_settings = {"cache_ttl_seconds": 60}
    sensor = MockSensor(mock_hass, config, global_settings)
    
    # First call
    value1 = sensor._get_sensor_value("sensor.test")
    assert value1 == -15.5
    
    # Second call should use cache
    value2 = sensor._get_sensor_value("sensor.test")
    assert value2 == -15.5
    assert mock_hass.states.get.call_count == 1


def test_cache_none_entity():
    """Test that None entity state is handled correctly."""
    mock_hass = MagicMock()
    mock_hass.states.get.return_value = None
    
    config = {"name": "Test"}
    global_settings = {"cache_ttl_seconds": 60}
    sensor = MockSensor(mock_hass, config, global_settings)
    
    # First call with None state
    value1 = sensor._get_sensor_value("sensor.test")
    assert value1 is None
    
    # Second call should still query (None is not cached)
    value2 = sensor._get_sensor_value("sensor.test")
    assert value2 is None
    assert mock_hass.states.get.call_count == 2
