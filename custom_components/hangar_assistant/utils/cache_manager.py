"""Unified cache manager for Hangar Assistant.

Provides consistent caching across all integration components with support for:
- Multi-level caching (memory + persistent)
- Flexible TTL and expiration strategies
- Stale cache fallback for graceful degradation
- Automatic cache directory management
- Type-safe cache operations

Used by:
- OpenWeatherMap client
- NOTAM client
- Sensor value caching
- Future integrations requiring caching

Example:
    # Create cache for weather data
    weather_cache = CacheManager(
        hass,
        namespace="weather",
        memory_enabled=True,
        persistent_enabled=True,
        ttl_minutes=10
    )

    # Store data
    await weather_cache.set("london_51.5_0.1", weather_data)

    # Retrieve data
    data = await weather_cache.get("london_51.5_0.1")

    # Allow stale fallback
    data, is_stale = await weather_cache.get_with_stale("london_51.5_0.1", max_age_hours=24)
"""

from __future__ import annotations

import json
import logging
import re
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Generic, Optional, Tuple, TypeVar

from homeassistant.core import HomeAssistant

# Try to import orjson for 2-5x faster JSON operations
try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False

# Optional import for notifications (may not be available in test env)
try:
    from homeassistant.components.persistent_notification import async_create as _async_create_notification
    HAS_NOTIFICATIONS = True
except (ImportError, ModuleNotFoundError):
    HAS_NOTIFICATIONS = False
    _async_create_notification = None

_LOGGER = logging.getLogger(__name__)

T = TypeVar('T')

# Default configuration
DEFAULT_CACHE_DIR = "hangar_assistant_cache"
DEFAULT_TTL_MINUTES = 60
DEFAULT_MEMORY_ENABLED = True
DEFAULT_PERSISTENT_ENABLED = True


class CacheEntry(Generic[T]):
    """Cache entry with metadata.

    Attributes:
        data: Cached data of generic type T
        cached_at: Timestamp when data was cached
        expires_at: Timestamp when cache entry expires (None = never)
        metadata: Optional metadata dict for tracking (e.g., api_calls, source)
    """

    def __init__(
        self,
        data: T,
        cached_at: Optional[datetime] = None,
        ttl: Optional[timedelta] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
        ttl_seconds: Optional[int] = None
    ):
        """Initialize cache entry.

        Args:
            data: Data to cache
            cached_at: Timestamp when cached
            ttl: Time-to-live duration (None = never expires)
            metadata: Optional metadata dict
        """
        effective_cached_at = cached_at or timestamp or datetime.now()
        effective_ttl = ttl if ttl else (timedelta(seconds=ttl_seconds) if ttl_seconds else None)

        self.data = data
        self.cached_at = effective_cached_at
        self.expires_at = effective_cached_at + effective_ttl if effective_ttl else None
        self.metadata = metadata or {}

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        """Check if cache entry has expired.

        Args:
            now: Current time (defaults to datetime.now())

        Returns:
            True if expired, False otherwise
        """
        if self.expires_at is None:
            return False

        check_time = now or datetime.now()
        return check_time >= self.expires_at

    def age_seconds(self, now: Optional[datetime] = None) -> float:
        """Get cache entry age in seconds.

        Args:
            now: Current time (defaults to datetime.now())

        Returns:
            Age in seconds
        """
        check_time = now or datetime.now()
        # Normalise timezone awareness to prevent subtraction errors
        base_time = self.cached_at
        try:
            return (check_time - base_time).total_seconds()
        except TypeError:
            # Convert both to naive by dropping tzinfo if mismatch occurs
            ct = check_time.replace(tzinfo=None)
            bt = base_time.replace(tzinfo=None)
            return (ct - bt).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize cache entry to dict for JSON storage.

        Returns:
            Dictionary representation
        """
        return {
            "data": self.data,
            "cached_at": self.cached_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CacheEntry:
        """Deserialize cache entry from dict.

        Args:
            data: Dictionary from JSON

        Returns:
            CacheEntry instance
        """
        cached_at = datetime.fromisoformat(data["cached_at"])
        expires_at_str = data.get("expires_at")

        entry = cls(
            data=data["data"],
            cached_at=cached_at,
            metadata=data.get("metadata", {})
        )

        if expires_at_str:
            entry.expires_at = datetime.fromisoformat(expires_at_str)

        return entry


class CacheManager:
    """Unified cache manager with multi-level support.

    Provides consistent caching across the integration with support for:
    - Memory-only caching (fast, session-scoped)
    - Persistent caching (survives restarts)
    - Two-level caching (memory + persistent)
    - Stale cache fallback for graceful degradation

    Inputs:
        - hass: Home Assistant instance
        - namespace: Cache namespace (e.g., "weather", "notam", "sensors")
        - memory_enabled: Enable in-memory caching
        - persistent_enabled: Enable persistent file caching
        - ttl_minutes: Default time-to-live in minutes
        - cache_dir: Custom cache directory name (optional)

    Outputs:
        - Cached data with metadata and expiration tracking

    Used by:
        - OpenWeatherMap client for weather data
        - NOTAM client for aviation notices
        - Sensor platform for state value caching
    """

    def __init__(
        self,
        hass: HomeAssistant,
        namespace: str,
        memory_enabled: bool = DEFAULT_MEMORY_ENABLED,
        persistent_enabled: bool = DEFAULT_PERSISTENT_ENABLED,
        ttl_minutes: Optional[int] = DEFAULT_TTL_MINUTES,
        cache_dir: Optional[str] = None,
        max_memory_entries: int = 1000
    ):
        """Initialize cache manager.

        Args:
            hass: Home Assistant instance
            namespace: Cache namespace (used for directory/file naming)
            memory_enabled: Enable in-memory caching
            persistent_enabled: Enable persistent file-based caching
            ttl_minutes: Default TTL in minutes (None = never expires)
            cache_dir: Custom cache directory name (defaults to hangar_assistant_cache)
            max_memory_entries: Maximum entries in memory cache (LRU eviction)
        """
        self.hass = hass
        self.namespace = namespace
        self.memory_enabled = memory_enabled
        self.persistent_enabled = persistent_enabled
        self.ttl = timedelta(minutes=ttl_minutes) if ttl_minutes else None
        self._max_memory_entries = max_memory_entries
        # Backwards compatibility
        self.max_memory_entries = max_memory_entries

        # Cache directory setup
        cache_dir_name = cache_dir or DEFAULT_CACHE_DIR
        self.cache_dir = Path(hass.config.path(cache_dir_name)) / namespace
        self._cache_dir_initialized = False

        # In-memory cache with OrderedDict for LRU eviction
        self._memory_cache: OrderedDict[str, CacheEntry] = OrderedDict()

        # Statistics
        self._stats = {
            "memory_hits": 0,
            "persistent_hits": 0,
            "misses": 0,
            "writes": 0,
            "evictions": 0
        }

        _LOGGER.info(
            "Cache manager initialized: namespace=%s, memory=%s, persistent=%s, ttl=%s, max_entries=%d, orjson=%s",
            namespace,
            memory_enabled,
            persistent_enabled,
            f"{ttl_minutes}min" if ttl_minutes else "never",
            max_memory_entries,
            "enabled" if HAS_ORJSON else "disabled"
        )

    def _ensure_cache_dir(self) -> bool:
        """Ensure cache directory exists (lazy initialization).

        Returns:
            True if directory exists/created, False on error
        """
        if not self._cache_dir_initialized and self.persistent_enabled:
            try:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                self._cache_dir_initialized = True
                return True
            except (OSError, PermissionError) as e:
                _LOGGER.error(
                    "Failed to create cache directory for %s: %s. "
                    "Persistent caching will be disabled. Check permissions for: %s",
                    self.namespace, e, self.cache_dir
                )
                self.persistent_enabled = False
                
                # Notify user about permission issue (if available)
                if HAS_NOTIFICATIONS and _async_create_notification:
                    self.hass.async_create_task(
                        _async_create_notification(
                            self.hass,
                            message=(
                                f"Hangar Assistant cannot create cache directory for {self.namespace}. "
                                f"Persistent caching will be disabled. "
                                f"Please check permissions for: {self.cache_dir}"
                            ),
                            title="Hangar Assistant: Cache Permission Error",
                            notification_id=f"hangar_cache_{self.namespace}_permission_error"
                        )
                    )
                return False

        return self._cache_dir_initialized

    def _serialize_json(self, data: Any) -> bytes:
        """Serialize data to JSON with orjson optimization.

        Uses orjson if available for 2-5x performance improvement,
        falls back to standard json module.

        Args:
            data: Data to serialize

        Returns:
            JSON bytes
        """
        if HAS_ORJSON:
            return orjson.dumps(data)
        return json.dumps(data).encode('utf-8')

    def _deserialize_json(self, data: bytes) -> Any:
        """Deserialize JSON data with orjson optimization.

        Uses orjson if available for 2-5x performance improvement,
        falls back to standard json module.

        Args:
            data: JSON bytes to deserialize

        Returns:
            Deserialized data
        """
        if HAS_ORJSON:
            return orjson.loads(data)
        return json.loads(data.decode('utf-8'))

    def _get_cache_file_path(self, key: str) -> Path:
        """Get cache file path for key.

        Args:
            key: Cache key

        Returns:
            Path to cache file
        """
        # Comprehensive sanitization for safe filename
        # Remove all characters except alphanumeric, underscore, hyphen, and period
        safe_key = re.sub(r'[^a-zA-Z0-9_.-]', '_', key)
        
        # Prevent path traversal attacks
        safe_key = safe_key.replace("..", "_")
        
        # Limit length to prevent filesystem issues
        if len(safe_key) > 200:
            safe_key = safe_key[:200]
        
        return self.cache_dir / f"{safe_key}.json"

    async def get(
        self,
        key: str,
        default: Optional[T] = None
    ) -> Optional[T]:
        """Get value from cache.

        Checks memory cache first, then persistent cache.
        Returns None if key not found or expired.

        Args:
            key: Cache key
            default: Default value if not found

        Returns:
            Cached value or default
        """
        now = datetime.now()

        # Check memory cache first
        if self.memory_enabled and key in self._memory_cache:
            entry = self._memory_cache[key]

            if not entry.is_expired(now):
                self._stats["memory_hits"] += 1
                # Move to end for LRU (mark as recently used)
                self._memory_cache.move_to_end(key)
                _LOGGER.debug(
                    "Memory cache HIT: %s/%s (age: %.1fs)",
                    self.namespace,
                    key,
                    entry.age_seconds(now)
                )
                return entry.data
            else:
                # Expired - remove from memory cache
                del self._memory_cache[key]
                self._stats["evictions"] += 1

        # Check persistent cache
        if self.persistent_enabled:
            persistent_entry = await self._read_persistent_cache(key)

            if persistent_entry and not persistent_entry.is_expired(now):
                self._stats["persistent_hits"] += 1
                _LOGGER.debug(
                    "Persistent cache HIT: %s/%s (age: %.1fs)",
                    self.namespace,
                    key,
                    persistent_entry.age_seconds(now)
                )

                # Populate memory cache
                if self.memory_enabled:
                    self._memory_cache[key] = persistent_entry

                return persistent_entry.data

        # Cache miss
        self._stats["misses"] += 1
        _LOGGER.debug("Cache MISS: %s/%s", self.namespace, key)
        return default

    async def get_with_stale(  # type: ignore[return]
        self,
        key: str,
        max_age_hours: Optional[float] = None
    ) -> Tuple[Optional[T], bool]:
        """Get value from cache, allowing stale data.

        Returns data even if expired, up to max_age_hours old.
        Useful for graceful degradation when fresh data unavailable.

        Args:
            key: Cache key
            max_age_hours: Maximum age in hours (None = any age)

        Returns:
            Tuple of (data, is_stale)
                - data: Cached data or None
                - is_stale: True if data is expired
        """
        now = datetime.now()

        # Try normal get first
        fresh_data = await self.get(key)
        if fresh_data is not None:
            return fresh_data, False

        # Look for stale data
        entry: Optional[CacheEntry[T]] = None

        # Check memory cache
        if self.memory_enabled and key in self._memory_cache:
            entry = self._memory_cache[key]

        # Check persistent cache if not in memory
        if entry is None and self.persistent_enabled:
            entry = await self._read_persistent_cache(key)

        if entry:
            age_hours = entry.age_seconds(now) / 3600

            if max_age_hours is None or age_hours <= max_age_hours:
                _LOGGER.info(
                    "Using STALE cache: %s/%s (age: %.1f hours)",
                    self.namespace,
                    key,
                    age_hours
                )
                return entry.data, True

        # No data available (even stale)
        return (None, False)

    async def set(
        self,
        key: str,
        value: T,
        ttl_minutes: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl_minutes: Override default TTL (None uses instance default)
            metadata: Optional metadata dict
        """
        now = datetime.now()
        ttl = timedelta(minutes=ttl_minutes) if ttl_minutes else self.ttl

        entry = CacheEntry(
            data=value,
            cached_at=now,
            ttl=ttl,
            metadata=metadata
        )

        # Store in memory cache with LRU eviction
        if self.memory_enabled:
            # Implement LRU eviction if cache is full
            if len(self._memory_cache) >= self._max_memory_entries:
                # Remove oldest entry (FIFO in OrderedDict)
                oldest_key, oldest_entry = self._memory_cache.popitem(last=False)
                self._stats["evictions"] += 1
                _LOGGER.debug(
                    "LRU eviction: %s/%s (age: %.1fs)",
                    self.namespace,
                    oldest_key,
                    oldest_entry.age_seconds(now)
                )
            
            # Add to cache and move to end (most recently used)
            self._memory_cache[key] = entry
            self._memory_cache.move_to_end(key)

        # Store in persistent cache
        if self.persistent_enabled:
            await self._write_persistent_cache(key, entry)

        self._stats["writes"] += 1
        _LOGGER.debug("Cache SET: %s/%s", self.namespace, key)

    async def delete(self, key: str) -> None:
        """Delete key from cache.

        Args:
            key: Cache key to delete
        """
        # Remove from memory
        if key in self._memory_cache:
            del self._memory_cache[key]

        # Remove from persistent storage
        if self.persistent_enabled:
            cache_file = self._get_cache_file_path(key)
            if cache_file.exists():
                await self.hass.async_add_executor_job(cache_file.unlink)

        _LOGGER.debug("Cache DELETE: %s/%s", self.namespace, key)

    async def clear(self) -> None:
        """Clear all cache entries for this namespace."""
        # Clear memory cache
        self._memory_cache.clear()

        # Clear persistent cache
        if self.persistent_enabled and self._ensure_cache_dir():
            cache_files = await self.hass.async_add_executor_job(
                list, self.cache_dir.glob("*.json")
            )

            for cache_file in cache_files:
                await self.hass.async_add_executor_job(cache_file.unlink)

        _LOGGER.info("Cache CLEARED: %s", self.namespace)

    async def _read_persistent_cache(self, key: str) -> Optional[CacheEntry]:
        """Read cache entry from disk.

        Args:
            key: Cache key

        Returns:
            CacheEntry if found, None otherwise
        """
        if not self._ensure_cache_dir():
            return None

        cache_file = self._get_cache_file_path(key)

        if not cache_file.exists():
            return None

        try:
            content_bytes = await self.hass.async_add_executor_job(
                cache_file.read_bytes
            )
            data = self._deserialize_json(content_bytes)
            return CacheEntry.from_dict(data)

        except (OSError, json.JSONDecodeError, KeyError) as e:
            _LOGGER.warning(
                "Failed to read cache %s/%s: %s",
                self.namespace,
                key,
                e
            )
            return None

    async def _write_persistent_cache(
            self, key: str, entry: CacheEntry) -> None:
        """Write cache entry to disk with optimized JSON.

        Args:
            key: Cache key
            entry: Cache entry to write
        """
        if not self._ensure_cache_dir():
            return

        cache_file = self._get_cache_file_path(key)

        try:
            # Serialize with optimized JSON (orjson if available)
            data_dict = entry.to_dict()
            json_bytes = self._serialize_json(data_dict)

            def _write():
                cache_file.write_bytes(json_bytes)

            await self.hass.async_add_executor_job(_write)

        except (OSError, TypeError) as e:
            _LOGGER.warning(
                "Failed to write cache %s/%s: %s",
                self.namespace,
                key,
                e
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache statistics:
                - namespace: Cache namespace
                - memory_enabled: Memory caching enabled
                - persistent_enabled: Persistent caching enabled
                - ttl_minutes: Default TTL in minutes
                - memory_entries: Current memory cache size
                - persistent_files: Number of persistent cache files
                - memory_hits: Memory cache hit count
                - persistent_hits: Persistent cache hit count
                - misses: Cache miss count
                - writes: Cache write count
                - evictions: Cache eviction count
                - hit_rate: Overall cache hit rate percentage
        """
        total_requests = (
            self._stats["memory_hits"] +
            self._stats["persistent_hits"] +
            self._stats["misses"]
        )

        hit_rate = 0.0
        if total_requests > 0:
            hits = self._stats["memory_hits"] + self._stats["persistent_hits"]
            hit_rate = (hits / total_requests) * 100

        persistent_files = 0
        if self.persistent_enabled and self._cache_dir_initialized:
            try:
                persistent_files = len(list(self.cache_dir.glob("*.json")))
            except OSError:
                pass

        return {
            "namespace": self.namespace,
            "memory_enabled": self.memory_enabled,
            "persistent_enabled": self.persistent_enabled,
            "ttl_minutes": int(
                self.ttl.total_seconds() /
                60) if self.ttl else None,
            "memory_entries": len(
                self._memory_cache),
            "persistent_files": persistent_files,
            "memory_hits": self._stats["memory_hits"],
            "persistent_hits": self._stats["persistent_hits"],
            "misses": self._stats["misses"],
            "writes": self._stats["writes"],
            "evictions": self._stats["evictions"],
            "hit_rate": round(
                hit_rate,
                2)}

    async def cleanup_expired(self) -> int:
        """Remove expired entries from cache.

        Returns:
            Number of entries removed
        """
        now = datetime.now()
        removed = 0

        # Clean memory cache
        expired_keys = [
            key for key, entry in self._memory_cache.items()
            if entry.is_expired(now)
        ]

        for key in expired_keys:
            del self._memory_cache[key]
            removed += 1

        # Clean persistent cache
        if self.persistent_enabled and self._ensure_cache_dir():
            cache_files = await self.hass.async_add_executor_job(
                list, self.cache_dir.glob("*.json")
            )

            for cache_file in cache_files:
                try:
                    content = await self.hass.async_add_executor_job(
                        cache_file.read_text
                    )
                    data = json.loads(content)
                    entry = CacheEntry.from_dict(data)

                    if entry.is_expired(now):
                        await self.hass.async_add_executor_job(cache_file.unlink)
                        removed += 1

                except (OSError, json.JSONDecodeError, KeyError):
                    pass

        if removed > 0:
            _LOGGER.info(
                "Cleaned up %d expired cache entries: %s",
                removed,
                self.namespace)

        return removed
