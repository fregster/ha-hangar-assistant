"""Test suite for unified cache manager."""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from custom_components.hangar_assistant.utils.cache_manager import (
    CacheEntry,
    CacheManager,
)


class TestCacheEntry:
    """Test CacheEntry class."""

    def test_cache_entry_creation(self):
        """Test creating a cache entry."""
        data = {"test": "value"}
        cached_at = datetime.now()
        ttl = timedelta(minutes=10)
        metadata = {"source": "test"}

        entry = CacheEntry(data, cached_at, ttl, metadata)

        assert entry.data == data
        assert entry.cached_at == cached_at
        assert entry.expires_at == cached_at + ttl
        assert entry.metadata == metadata

    def test_cache_entry_no_expiration(self):
        """Test cache entry without expiration."""
        data = {"test": "value"}
        cached_at = datetime.now()

        entry = CacheEntry(data, cached_at, ttl=None)

        assert entry.expires_at is None
        assert not entry.is_expired()

    def test_cache_entry_is_expired(self):
        """Test expiration check."""
        data = {"test": "value"}
        cached_at = datetime.now() - timedelta(minutes=15)
        ttl = timedelta(minutes=10)

        entry = CacheEntry(data, cached_at, ttl)

        assert entry.is_expired()

    def test_cache_entry_not_expired(self):
        """Test non-expired entry."""
        data = {"test": "value"}
        cached_at = datetime.now()
        ttl = timedelta(minutes=10)

        entry = CacheEntry(data, cached_at, ttl)

        assert not entry.is_expired()

    def test_cache_entry_age_seconds(self):
        """Test age calculation."""
        data = {"test": "value"}
        cached_at = datetime.now() - timedelta(seconds=30)

        entry = CacheEntry(data, cached_at)

        age = entry.age_seconds()
        assert 29 <= age <= 31  # Allow 1 second tolerance

    def test_cache_entry_serialization(self):
        """Test to_dict serialization."""
        data = {"test": "value"}
        cached_at = datetime.now()
        ttl = timedelta(minutes=10)
        metadata = {"api_calls": 5}

        entry = CacheEntry(data, cached_at, ttl, metadata)
        serialized = entry.to_dict()

        assert serialized["data"] == data
        assert serialized["cached_at"] == cached_at.isoformat()
        assert serialized["expires_at"] == (cached_at + ttl).isoformat()
        assert serialized["metadata"] == metadata

    def test_cache_entry_deserialization(self):
        """Test from_dict deserialization."""
        cached_at = datetime.now()
        expires_at = cached_at + timedelta(minutes=10)
        data_dict = {
            "data": {"test": "value"},
            "cached_at": cached_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "metadata": {"source": "test"},
        }

        entry = CacheEntry.from_dict(data_dict)

        assert entry.data == {"test": "value"}
        assert entry.cached_at == cached_at
        assert entry.expires_at == expires_at
        assert entry.metadata == {"source": "test"}

    def test_cache_entry_deserialization_no_expiration(self):
        """Test deserialization without expiration."""
        cached_at = datetime.now()
        data_dict = {
            "data": {"test": "value"},
            "cached_at": cached_at.isoformat(),
            "expires_at": None,
        }

        entry = CacheEntry.from_dict(data_dict)

        assert entry.data == {"test": "value"}
        assert entry.expires_at is None


class TestCacheManager:
    """Test CacheManager class."""

    @pytest.fixture
    def mock_hass(self, tmp_path):
        """Create mock Home Assistant instance."""
        hass = MagicMock()
        hass.config.path = MagicMock(return_value=str(tmp_path))
        
        # Make async_add_executor_job async for testing
        async def mock_executor_job(func, *args):
            """Mock async_add_executor_job that returns awaitable."""
            return func(*args)
        
        hass.async_add_executor_job = mock_executor_job
        return hass

    @pytest.fixture
    def cache_manager(self, mock_hass):
        """Create cache manager instance."""
        return CacheManager(
            mock_hass,
            namespace="test",
            memory_enabled=True,
            persistent_enabled=True,
            ttl_minutes=10,
        )

    def test_cache_manager_initialization(self, mock_hass):
        """Test cache manager initialization."""
        manager = CacheManager(
            mock_hass,
            namespace="weather",
            memory_enabled=True,
            persistent_enabled=False,
            ttl_minutes=5,
        )

        assert manager.namespace == "weather"
        assert manager.memory_enabled is True
        assert manager.persistent_enabled is False
        assert manager.ttl == timedelta(minutes=5)

    def test_cache_manager_no_ttl(self, mock_hass):
        """Test cache manager without TTL."""
        manager = CacheManager(
            mock_hass, namespace="test", ttl_minutes=None
        )

        assert manager.ttl is None

    @pytest.mark.asyncio
    async def test_memory_cache_set_get(self, cache_manager):
        """Test setting and getting from memory cache."""
        data = {"temperature": 15.5, "pressure": 1013}

        await cache_manager.set("london", data)
        result = await cache_manager.get("london")

        assert result == data

    @pytest.mark.asyncio
    async def test_memory_cache_miss(self, cache_manager):
        """Test cache miss returns None."""
        result = await cache_manager.get("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_memory_cache_miss_with_default(self, cache_manager):
        """Test cache miss returns default value."""
        default = {"default": "value"}
        result = await cache_manager.get("nonexistent", default)

        assert result == default

    @pytest.mark.asyncio
    async def test_memory_cache_expiration(self, cache_manager):
        """Test memory cache expiration."""
        data = {"test": "value"}

        # Set with 0.01 minute TTL (0.6 seconds)
        await cache_manager.set("test_key", data, ttl_minutes=0.01)

        # Should be available immediately
        result = await cache_manager.get("test_key")
        assert result == data

        # Wait for expiration
        await asyncio.sleep(1)

        # Should be expired and return None
        result = await cache_manager.get("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_persistent_cache_set_get(self, cache_manager):
        """Test persistent cache storage and retrieval."""
        data = {"notam": "C1234/25"}

        await cache_manager.set("notam_key", data)

        # Clear memory cache to force persistent read
        cache_manager._memory_cache.clear()

        result = await cache_manager.get("notam_key")
        assert result == data

    @pytest.mark.asyncio
    async def test_persistent_cache_file_created(self, cache_manager):
        """Test persistent cache file is created."""
        data = {"test": "value"}

        await cache_manager.set("test_key", data)

        cache_file = cache_manager._get_cache_file_path("test_key")
        assert cache_file.exists()

        # Verify file content
        content = json.loads(cache_file.read_text())
        assert content["data"] == data

    @pytest.mark.asyncio
    async def test_cache_delete(self, cache_manager):
        """Test deleting cache entry."""
        data = {"test": "value"}

        await cache_manager.set("test_key", data)
        await cache_manager.delete("test_key")

        result = await cache_manager.get("test_key")
        assert result is None

        # Verify file is deleted
        cache_file = cache_manager._get_cache_file_path("test_key")
        assert not cache_file.exists()

    @pytest.mark.asyncio
    async def test_cache_clear(self, cache_manager):
        """Test clearing all cache entries."""
        await cache_manager.set("key1", {"data": "1"})
        await cache_manager.set("key2", {"data": "2"})
        await cache_manager.set("key3", {"data": "3"})

        await cache_manager.clear()

        # All keys should be gone
        assert await cache_manager.get("key1") is None
        assert await cache_manager.get("key2") is None
        assert await cache_manager.get("key3") is None

        # All files should be deleted
        cache_files = list(cache_manager.cache_dir.glob("*.json"))
        assert len(cache_files) == 0

    @pytest.mark.asyncio
    async def test_get_with_stale_fresh_data(self, cache_manager):
        """Test get_with_stale returns fresh data."""
        data = {"test": "value"}

        await cache_manager.set("test_key", data)
        result, is_stale = await cache_manager.get_with_stale("test_key")

        assert result == data
        assert is_stale is False

    @pytest.mark.asyncio
    async def test_get_with_stale_expired_data(self, cache_manager):
        """Test get_with_stale returns stale data."""
        data = {"test": "value"}

        # Set with 0.01 minute TTL
        await cache_manager.set("test_key", data, ttl_minutes=0.01)

        # Wait for expiration
        await asyncio.sleep(1)

        # Should return stale data
        result, is_stale = await cache_manager.get_with_stale(
            "test_key", max_age_hours=24
        )

        assert result == data
        assert is_stale is True

    @pytest.mark.asyncio
    async def test_get_with_stale_too_old(self, cache_manager):
        """Test get_with_stale rejects data older than max_age."""
        data = {"test": "value"}

        # Set with immediate expiration
        await cache_manager.set("test_key", data, ttl_minutes=0.01)
        await asyncio.sleep(1)

        # Request with very short max_age
        result, is_stale = await cache_manager.get_with_stale(
            "test_key", max_age_hours=0.0001
        )

        assert result is None
        assert is_stale is False

    @pytest.mark.asyncio
    async def test_cache_with_metadata(self, cache_manager):
        """Test storing and retrieving metadata."""
        data = {"temperature": 15}
        metadata = {"api_calls": 10, "source": "openweathermap"}

        await cache_manager.set("weather_key", data, metadata=metadata)

        # Verify metadata is stored in persistent cache
        cache_file = cache_manager._get_cache_file_path("weather_key")
        content = json.loads(cache_file.read_text())

        assert content["metadata"] == metadata

    def test_cache_stats(self, cache_manager):
        """Test getting cache statistics."""
        stats = cache_manager.get_stats()

        assert stats["namespace"] == "test"
        assert stats["memory_enabled"] is True
        assert stats["persistent_enabled"] is True
        assert stats["ttl_minutes"] == 10
        assert stats["memory_entries"] == 0
        assert stats["persistent_files"] == 0
        assert stats["hit_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_cache_stats_with_data(self, cache_manager):
        """Test cache statistics with hits and misses."""
        await cache_manager.set("key1", {"data": "1"})

        # Memory hit
        await cache_manager.get("key1")

        # Clear memory, force persistent hit
        cache_manager._memory_cache.clear()
        await cache_manager.get("key1")

        # Cache miss
        await cache_manager.get("nonexistent")

        stats = cache_manager.get_stats()

        assert stats["memory_entries"] == 1
        assert stats["persistent_files"] == 1
        assert stats["memory_hits"] == 1
        assert stats["persistent_hits"] == 1
        assert stats["misses"] == 1
        assert stats["writes"] == 1
        assert stats["hit_rate"] == 66.67  # 2 hits / 3 requests

    @pytest.mark.asyncio
    async def test_cleanup_expired_entries(self, cache_manager):
        """Test cleanup of expired cache entries."""
        # Add fresh entry
        await cache_manager.set("fresh", {"data": "fresh"})

        # Add expired entry
        await cache_manager.set("expired", {"data": "expired"}, ttl_minutes=0.01)
        await asyncio.sleep(1)

        removed = await cache_manager.cleanup_expired()

        # For two-level cache, expired entry exists in both memory and persistent
        # So cleanup removes 2 copies (memory + persistent)
        assert removed == 2
        assert await cache_manager.get("fresh") is not None
        assert await cache_manager.get("expired") is None

    def test_memory_only_cache(self, mock_hass):
        """Test cache manager with memory only."""
        manager = CacheManager(
            mock_hass,
            namespace="test",
            memory_enabled=True,
            persistent_enabled=False,
        )

        assert manager.memory_enabled is True
        assert manager.persistent_enabled is False

    @pytest.mark.asyncio
    async def test_memory_only_cache_no_files(self, mock_hass):
        """Test memory-only cache doesn't create files."""
        manager = CacheManager(
            mock_hass,
            namespace="test",
            memory_enabled=True,
            persistent_enabled=False,
        )

        await manager.set("test_key", {"data": "value"})

        # No cache directory should be created
        assert not manager._cache_dir_initialized

    def test_persistent_only_cache(self, mock_hass):
        """Test cache manager with persistent only."""
        manager = CacheManager(
            mock_hass,
            namespace="test",
            memory_enabled=False,
            persistent_enabled=True,
        )

        assert manager.memory_enabled is False
        assert manager.persistent_enabled is True

    @pytest.mark.asyncio
    async def test_persistent_only_cache_no_memory(self, mock_hass):
        """Test persistent-only cache doesn't use memory."""
        manager = CacheManager(
            mock_hass,
            namespace="test",
            memory_enabled=False,
            persistent_enabled=True,
        )

        await manager.set("test_key", {"data": "value"})

        # Memory cache should be empty
        assert len(manager._memory_cache) == 0

        # Data should be in persistent cache
        result = await manager.get("test_key")
        assert result == {"data": "value"}

    @pytest.mark.asyncio
    async def test_cache_directory_creation_failure(self, mock_hass):
        """Test handling of cache directory creation failure."""
        manager = CacheManager(mock_hass, namespace="test")

        # Mock directory creation to fail
        with patch.object(Path, "mkdir", side_effect=PermissionError("Access denied")):
            result = manager._ensure_cache_dir()

        assert result is False
        assert manager.persistent_enabled is False

    @pytest.mark.asyncio
    async def test_cache_file_key_sanitization(self, cache_manager):
        """Test cache file key sanitization."""
        # Key with problematic characters
        key = "london/51.5:0.1\\test"

        await cache_manager.set(key, {"data": "value"})

        cache_file = cache_manager._get_cache_file_path(key)

        # Verify problematic characters are replaced
        assert "/" not in cache_file.name
        assert "\\" not in cache_file.name
        assert ":" not in cache_file.name

    @pytest.mark.asyncio
    async def test_corrupted_cache_file_handling(self, cache_manager):
        """Test handling of corrupted cache file."""
        # Create corrupted cache file
        cache_file = cache_manager._get_cache_file_path("corrupted")
        cache_manager._ensure_cache_dir()
        cache_file.write_text("invalid json content {{{")

        # Should return None and not crash
        result = await cache_manager.get("corrupted")
        assert result is None

    @pytest.mark.asyncio
    async def test_custom_ttl_override(self, cache_manager):
        """Test overriding default TTL per cache entry."""
        # Default TTL is 10 minutes
        await cache_manager.set("short_ttl", {"data": "value"}, ttl_minutes=0.01)

        await asyncio.sleep(1)

        # Should be expired
        result = await cache_manager.get("short_ttl")
        assert result is None

    @pytest.mark.asyncio
    async def test_namespace_isolation(self, mock_hass):
        """Test cache namespaces are isolated."""
        cache1 = CacheManager(mock_hass, namespace="weather")
        cache2 = CacheManager(mock_hass, namespace="notam")

        await cache1.set("data", {"weather": "sunny"})
        await cache2.set("data", {"notam": "active"})

        # Same key, different namespaces, different data
        result1 = await cache1.get("data")
        result2 = await cache2.get("data")

        assert result1 == {"weather": "sunny"}
        assert result2 == {"notam": "active"}

        # Verify separate directories
        assert cache1.cache_dir != cache2.cache_dir
