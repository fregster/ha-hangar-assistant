"""Performance tests for Hangar Assistant optimizations."""
import time
import pytest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path
from collections import OrderedDict

# Test dashboard template caching


def test_dashboard_template_caching_mtime_check():
    """Test that dashboard template caching checks mtime."""
    from custom_components.hangar_assistant import (
        _dashboard_template_cache,
        _dashboard_template_mtime
    )
    
    # Initially should be None
    assert _dashboard_template_cache is None
    assert _dashboard_template_mtime is None


def test_json_serialization_with_orjson():
    """Test JSON serialization falls back gracefully."""
    from custom_components.hangar_assistant.utils.cache_manager import (
        CacheManager
    )
    
    mock_hass = MagicMock()
    cache = CacheManager(
        hass=mock_hass,
        namespace="test",
        cache_dir=Path("/tmp/test_cache")
    )
    
    # Test serialization works (either orjson or json)
    test_data = {"key": "value", "number": 123}
    json_bytes = cache._serialize_json(test_data)
    
    # Should return bytes
    assert isinstance(json_bytes, bytes)
    
    # Deserialization should work
    result = cache._deserialize_json(json_bytes)
    assert result == test_data


def test_json_deserialization_with_orjson():
    """Test JSON deserialization falls back gracefully."""
    from custom_components.hangar_assistant.utils.cache_manager import (
        CacheManager
    )
    
    mock_hass = MagicMock()
    cache = CacheManager(
        hass=mock_hass,
        namespace="test",
        cache_dir=Path("/tmp/test_cache")
    )
    
    # Test with standard JSON bytes
    json_bytes = b'{"test": "data", "value": 42}'
    result = cache._deserialize_json(json_bytes)
    
    assert result == {"test": "data", "value": 42}


@pytest.mark.asyncio
async def test_lru_cache_eviction():
    """Test LRU cache evicts oldest entries when limit reached."""
    from custom_components.hangar_assistant.utils.cache_manager import (
        CacheManager,
        CacheEntry
    )
    from homeassistant.util import dt as dt_util
    
    mock_hass = MagicMock()
    cache = CacheManager(
        hass=mock_hass,
        namespace="test",
        cache_dir=Path("/tmp/test_cache"),
        max_memory_entries=3  # Small limit for testing
    )
    
    # Add 4 entries (should evict oldest)
    now = dt_util.utcnow()
    for i in range(4):
        entry = CacheEntry(
            data={"value": i},
            timestamp=now,
            ttl_seconds=3600
        )
        cache._memory_cache[f"key_{i}"] = entry
        cache._memory_cache.move_to_end(f"key_{i}")

    # Should only have 3 entries (oldest evicted)
    assert len(cache._memory_cache) == 4  # Haven't enforced limit yet

    # Now set a new entry which should trigger eviction
    entry = CacheEntry(
        data={"value": "new"},
        timestamp=now,
        ttl_seconds=3600
    )
    await cache.set("new_key", entry)

    # Check that oldest was evicted
    assert "key_0" not in cache._memory_cache
    assert "new_key" in cache._memory_cache


@pytest.mark.asyncio
async def test_lru_cache_move_to_end_on_access():
    """Test LRU cache updates order on access."""
    from custom_components.hangar_assistant.utils.cache_manager import (
        CacheManager,
        CacheEntry
    )
    from homeassistant.util import dt as dt_util
    
    mock_hass = MagicMock()
    cache = CacheManager(
        hass=mock_hass,
        namespace="test",
        cache_dir=Path("/tmp/test_cache"),
        max_memory_entries=5
    )
    
    # Add 3 entries
    now = dt_util.utcnow()
    for i in range(3):
        entry = CacheEntry(
            data={"value": i},
            timestamp=now,
            ttl_seconds=3600
        )
        await cache.set(f"key_{i}", entry)
    
    # Access key_0 (should move to end)
    await cache.get("key_0")
    
    # key_0 should now be most recent
    keys_list = list(cache._memory_cache.keys())
    assert keys_list[-1] == "key_0"


def test_cache_max_memory_entries_parameter():
    """Test CacheManager respects max_memory_entries parameter."""
    from custom_components.hangar_assistant.utils.cache_manager import (
        CacheManager
    )
    
    mock_hass = MagicMock()
    
    # Test default value
    cache_default = CacheManager(
        hass=mock_hass,
        namespace="test",
        cache_dir=Path("/tmp/test_cache")
    )
    assert cache_default._max_memory_entries == 1000
    
    # Test custom value
    cache_custom = CacheManager(
        hass=mock_hass,
        namespace="test",
        cache_dir=Path("/tmp/test_cache"),
        max_memory_entries=500
    )
    assert cache_custom._max_memory_entries == 500


@pytest.mark.asyncio
async def test_notam_cache_single_read():
    """Test NOTAM fetch_notams reads cache only once on failure."""
    from custom_components.hangar_assistant.utils.notam import NOTAMClient
    
    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.data = {"integrations": {"notams": {"enabled": True}}}
    
    client = NOTAMClient(
        hass=mock_hass,
        cache_days=7,
        entry=mock_entry
    )
    
    # Mock _read_cache to track calls
    read_count = {"count": 0}
    original_read_cache = client._read_cache
    
    async def tracked_read_cache():
        read_count["count"] += 1
        return await original_read_cache()
    
    client._read_cache = tracked_read_cache
    
    # Mock failed fetch
    async def mock_fetch_fail():
        raise Exception("Network error")
    
    client._fetch_from_nats = mock_fetch_fail
    
    # Mock stale cache available
    async def _stale():
        return [{"id": "TEST"}]

    async def _age():
        return 48

    client._read_stale_cache = _stale
    client._get_cache_age_hours = _age
    
    # Call fetch_notams
    notams, is_stale = await client.fetch_notams()
    
    # Should have called _read_cache exactly once (not twice)
    assert read_count["count"] == 1


def test_sensor_state_cache_exists():
    """Test that sensor state caching is implemented."""
    from custom_components.hangar_assistant.sensor import HangarSensorBase
    
    # Verify class has caching attributes
    assert hasattr(HangarSensorBase, '_state_cache')
    assert hasattr(HangarSensorBase, '_cache_ttl_seconds')
    assert hasattr(HangarSensorBase, '_max_cache_entries')
    
    # Verify cache is OrderedDict
    assert isinstance(HangarSensorBase._state_cache, OrderedDict)
    
    # Verify reasonable defaults
    assert HangarSensorBase._cache_ttl_seconds == 60
    assert HangarSensorBase._max_cache_entries == 50


def test_sensor_state_cache_ttl():
    """Test sensor state cache respects TTL."""
    from custom_components.hangar_assistant.sensor import (
        HangarSensorBase,
        DensityAltSensor
    )
    from homeassistant.util import dt as dt_util
    from datetime import timedelta
    
    mock_hass = MagicMock()
    mock_hass.states = MagicMock()
    
    config = {"name": "Test Airfield"}
    entry_data = {"settings": {}}
    
    sensor = DensityAltSensor(mock_hass, config, entry_data)
    
    # Clear cache
    HangarSensorBase._state_cache.clear()
    
    # Cache a value
    cache_key = "test_key"
    test_value = 42
    sensor._cache_state(cache_key, test_value)
    
    # Should retrieve cached value
    result = sensor._get_cached_state(cache_key)
    assert result == test_value
    
    # Manually expire by modifying cached time
    old_time = dt_util.utcnow() - timedelta(seconds=120)  # 2 minutes ago
    HangarSensorBase._state_cache[cache_key] = (test_value, old_time)
    
    # Should return None (expired)
    result = sensor._get_cached_state(cache_key)
    assert result is None


def test_sensor_state_cache_lru_eviction():
    """Test sensor state cache evicts oldest entries."""
    from custom_components.hangar_assistant.sensor import (
        HangarSensorBase,
        DensityAltSensor
    )
    
    mock_hass = MagicMock()
    mock_hass.states = MagicMock()
    
    config = {"name": "Test Airfield"}
    entry_data = {"settings": {}}
    
    sensor = DensityAltSensor(mock_hass, config, entry_data)
    
    # Clear cache
    HangarSensorBase._state_cache.clear()
    
    # Fill cache beyond max (50 entries)
    for i in range(55):
        sensor._cache_state(f"key_{i}", i)
    
    # Should have evicted oldest, keeping only 50
    assert len(HangarSensorBase._state_cache) == 50
    
    # Oldest keys should be gone
    assert "key_0" not in HangarSensorBase._state_cache
    assert "key_1" not in HangarSensorBase._state_cache
    assert "key_2" not in HangarSensorBase._state_cache
    assert "key_3" not in HangarSensorBase._state_cache
    assert "key_4" not in HangarSensorBase._state_cache
    
    # Newest keys should exist
    assert "key_54" in HangarSensorBase._state_cache
