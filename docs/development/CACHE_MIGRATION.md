# Cache Manager Migration Guide

## Overview

This document outlines the migration from multiple disparate caching implementations to the unified `CacheManager` system.

## Current State (Before Migration)

### 1. OpenWeatherMap Client Cache
**Location**: `utils/openweathermap.py`

**Pattern**:
- Two-level caching (memory + persistent)
- TTL-based expiration (10 minutes default)
- Per-coordinate caching
- API call tracking
- Lazy directory initialization

**Code Example**:
```python
# Current implementation
self._memory_cache: Dict[str, tuple[Dict[str, Any], datetime]] = {}
self.cache_dir = Path(hass.config.path("hangar_assistant_cache"))

# Cache key: "51.2_-1.2"
cache_key = f"{latitude}_{longitude}"
self._memory_cache[cache_key] = (data, datetime.now())
```

**Issues**:
- Custom cache logic duplicated
- No standard interface
- Statistics tracking is custom
- Expiration logic reimplemented

### 2. NOTAM Client Cache
**Location**: `utils/notam.py`

**Pattern**:
- Persistent-only caching
- Retention-based expiration (days)
- Single global file (`notams.json`)
- Stale cache fallback
- Failure tracking

**Code Example**:
```python
# Current implementation
self.cache_dir = Path(hass.config.path("hangar_assistant_cache"))
self.cache_file = self.cache_dir / "notams.json"

# Stale cache allowed on failure
stale_notams = self._read_stale_cache()
if stale_notams:
    return stale_notams, True
```

**Issues**:
- Different cache interface than OWM
- Stale cache logic not reusable
- Global file limits scalability

### 3. Sensor Value Cache
**Location**: `sensor.py`

**Pattern**:
- Memory-only caching
- TTL-based expiration (60 seconds default)
- Per-entity-id caching
- Session-scoped only

**Code Example**:
```python
# Current implementation
self._sensor_cache: dict[str, tuple[float, float]] = {}  # {entity_id: (value, timestamp)}

cached_value, cached_time = self._sensor_cache[entity_id]
if current_time - cached_time < cache_ttl:
    return cached_value
```

**Issues**:
- Lost on restart (no persistence)
- Limited to sensor platform
- No statistics or monitoring

## Migration Plan

### Phase 1: Create Unified Cache Manager ✅ DONE

Created `utils/cache_manager.py` with:
- Generic `CacheManager` class
- `CacheEntry` with metadata support
- Multi-level caching (memory + persistent)
- Stale cache fallback
- Statistics and monitoring
- Namespace isolation

### Phase 2: Migrate OpenWeatherMap Client

**Changes Required**:

1. **Import CacheManager**:
```python
from .cache_manager import CacheManager
```

2. **Replace initialization**:
```python
# OLD
self.cache_dir = Path(hass.config.path("hangar_assistant_cache"))
self._memory_cache: Dict[str, tuple[Dict[str, Any], datetime]] = {}

# NEW
self._cache = CacheManager(
    hass,
    namespace="weather",
    memory_enabled=True,
    persistent_enabled=cache_enabled,
    ttl_minutes=cache_ttl_minutes
)
```

3. **Replace cache operations**:
```python
# OLD - Set
cache_key = f"{latitude}_{longitude}"
self._memory_cache[cache_key] = (data, datetime.now())
self._write_persistent_cache(latitude, longitude, data)

# NEW - Set
cache_key = f"{latitude:.4f}_{longitude:.4f}"
await self._cache.set(
    cache_key,
    data,
    metadata={"api_calls": self._api_calls_today}
)

# OLD - Get
if cache_key in self._memory_cache:
    cached_data, cached_time = self._memory_cache[cache_key]
    if datetime.now() - cached_time < self.cache_ttl:
        return cached_data

# NEW - Get
data = await self._cache.get(cache_key)
if data:
    return data
```

4. **Replace statistics**:
```python
# OLD
def get_cache_stats(self):
    return {
        "memory_cache_entries": len(self._memory_cache),
        "api_calls_today": self._api_calls_today,
        # Custom stats...
    }

# NEW
def get_cache_stats(self):
    stats = self._cache.get_stats()
    stats["api_calls_today"] = self._api_calls_today
    return stats
```

**Benefits**:
- Reduces code by ~150 lines
- Consistent interface
- Better statistics
- Automatic cleanup

### Phase 3: Migrate NOTAM Client

**Changes Required**:

1. **Import CacheManager**:
```python
from .cache_manager import CacheManager
```

2. **Replace initialization**:
```python
# OLD
self.cache_dir = Path(hass.config.path("hangar_assistant_cache"))
self.cache_file = self.cache_dir / "notams.json"

# NEW
self._cache = CacheManager(
    hass,
    namespace="notam",
    memory_enabled=False,  # Persistent only
    persistent_enabled=True,
    ttl_minutes=cache_days * 24 * 60  # Convert days to minutes
)
```

3. **Replace cache operations**:
```python
# OLD - Get with stale fallback
cached = self._read_cache()
if cached:
    return cached, False

stale_notams = self._read_stale_cache()
if stale_notams:
    return stale_notams, True

# NEW - Get with stale fallback
notams, is_stale = await self._cache.get_with_stale(
    "uk_notams",
    max_age_hours=cache_days * 24 * 2  # Allow 2x retention for stale
)
if notams:
    return notams, is_stale
```

4. **Simplify fetch logic**:
```python
# OLD
try:
    notams = await self._fetch_from_nats()
    if notams:
        self._write_cache(notams)
        return notams, False
except Exception as e:
    _LOGGER.error("Fetch failed: %s", e)
    stale = self._read_stale_cache()
    if stale:
        return stale, True

# NEW
try:
    notams = await self._fetch_from_nats()
    if notams:
        await self._cache.set("uk_notams", notams)
        return notams, False
except Exception as e:
    _LOGGER.error("Fetch failed: %s", e)
    return await self._cache.get_with_stale("uk_notams")
```

**Benefits**:
- Reduces code by ~100 lines
- Removes custom stale cache logic
- Enables memory caching if desired
- Better failure handling

### Phase 4: Migrate Sensor Value Cache

**Changes Required**:

1. **Import CacheManager**:
```python
from ..utils.cache_manager import CacheManager
```

2. **Replace initialization in HangarSensorBase**:
```python
# OLD
self._sensor_cache: dict[str, tuple[float, float]] = {}

# NEW
cache_ttl = self._global_settings.get("cache_ttl_seconds", DEFAULT_SENSOR_CACHE_TTL_SECONDS)
self._sensor_cache = CacheManager(
    hass,
    namespace="sensors",
    memory_enabled=True,
    persistent_enabled=False,  # Session-only
    ttl_minutes=cache_ttl / 60  # Convert seconds to minutes
)
```

3. **Replace cache operations**:
```python
# OLD
def _get_sensor_value(self, entity_id: str) -> Optional[float]:
    cache_ttl = self._global_settings.get("cache_ttl_seconds", DEFAULT_SENSOR_CACHE_TTL_SECONDS)
    current_time = time.time()
    
    if entity_id in self._sensor_cache:
        cached_value, cached_time = self._sensor_cache[entity_id]
        if current_time - cached_time < cache_ttl:
            return cached_value
    
    # Fetch value...
    self._sensor_cache[entity_id] = (value, current_time)

# NEW
async def _get_sensor_value(self, entity_id: str) -> Optional[float]:
    # Check cache
    cached = await self._sensor_cache.get(entity_id)
    if cached is not None:
        return cached
    
    # Fetch value...
    await self._sensor_cache.set(entity_id, value)
```

**Benefits**:
- Reduces code by ~30 lines
- Consistent caching interface
- Easy to enable persistence if needed
- Better statistics

### Phase 5: Configuration Consolidation

**Current Config Structure**:
```python
"settings": {
    "cache_ttl_seconds": 60,  # Sensor cache
    "openweathermap_cache_enabled": True,  # OWM persistent cache
    "openweathermap_cache_ttl": 10,  # OWM TTL (minutes)
}

"integrations": {
    "notams": {
        "cache_days": 7  # NOTAM retention
    }
}
```

**Proposed Config Structure**:
```python
"settings": {
    "cache": {
        "sensors": {
            "enabled": True,
            "memory_only": True,
            "ttl_seconds": 60
        },
        "weather": {
            "enabled": True,
            "memory_enabled": True,
            "persistent_enabled": True,
            "ttl_minutes": 10
        },
        "notams": {
            "enabled": True,
            "memory_enabled": False,
            "persistent_enabled": True,
            "retention_days": 7,
            "stale_allowed": True
        }
    }
}
```

**Migration Code** (in `__init__.py`):
```python
def migrate_cache_config(entry_data: dict) -> dict:
    """Migrate old cache config to unified structure."""
    settings = entry_data.get("settings", {})
    integrations = entry_data.get("integrations", {})
    
    # Create new cache config if not exists
    if "cache" not in settings:
        settings["cache"] = {
            "sensors": {
                "enabled": True,
                "memory_only": True,
                "ttl_seconds": settings.get("cache_ttl_seconds", 60)
            },
            "weather": {
                "enabled": settings.get("openweathermap_cache_enabled", True),
                "memory_enabled": True,
                "persistent_enabled": settings.get("openweathermap_cache_enabled", True),
                "ttl_minutes": settings.get("openweathermap_cache_ttl", 10)
            },
            "notams": {
                "enabled": True,
                "memory_enabled": False,
                "persistent_enabled": True,
                "retention_days": integrations.get("notams", {}).get("cache_days", 7),
                "stale_allowed": True
            }
        }
        
        # Remove old config keys
        settings.pop("cache_ttl_seconds", None)
        settings.pop("openweathermap_cache_enabled", None)
        settings.pop("openweathermap_cache_ttl", None)
    
    return entry_data
```

## Testing Strategy

### Unit Tests
- ✅ `test_cache_manager.py` - Comprehensive CacheManager tests
- TODO: `test_openweathermap_migration.py` - Test OWM client with new cache
- TODO: `test_notam_migration.py` - Test NOTAM client with new cache
- TODO: `test_sensor_cache_migration.py` - Test sensor caching with new cache

### Integration Tests
- TODO: Test cache persistence across HA restarts
- TODO: Test cache isolation between namespaces
- TODO: Test stale cache fallback scenarios
- TODO: Test cache statistics and monitoring

### Performance Tests
- TODO: Benchmark cache lookup times
- TODO: Benchmark memory usage
- TODO: Test cache cleanup performance

## Rollout Plan

### Step 1: Add Cache Manager (✅ DONE)
- Create `utils/cache_manager.py`
- Create `tests/test_cache_manager.py`
- Run tests: `pytest tests/test_cache_manager.py -v`

### Step 2: Migrate OpenWeatherMap (TODO)
- Update `utils/openweathermap.py`
- Update `tests/test_openweathermap.py`
- Test backward compatibility
- Verify no API limit breaches

### Step 3: Migrate NOTAM Client (TODO)
- Update `utils/notam.py`
- Update `tests/test_notam_client.py`
- Test stale cache fallback
- Verify graceful degradation

### Step 4: Migrate Sensor Cache (TODO)
- Update `sensor.py`
- Update sensor cache tests
- Test performance impact
- Verify no state lookup issues

### Step 5: Config Migration (TODO)
- Add migration function to `__init__.py`
- Update `config_flow.py`
- Test migration with existing configs
- Update documentation

### Step 6: Cleanup (TODO)
- Remove old cache code
- Update CHANGELOG.md
- Update README.md
- Create release notes

## Backward Compatibility

**Cache Files**:
- Old cache files will remain in `hangar_assistant_cache/`
- New cache files use namespace subdirectories: `hangar_assistant_cache/weather/`, `hangar_assistant_cache/notam/`
- Old files can be manually deleted after migration confirmed working

**Configuration**:
- Old config keys will be automatically migrated
- Old keys will be removed after migration
- No user action required

**API Compatibility**:
- External services continue to work unchanged
- API call tracking maintained
- Rate limit protection maintained

## Performance Impact

**Expected Improvements**:
- **Code Reduction**: ~280 lines removed across 3 files
- **Memory Usage**: Slightly higher (metadata overhead), but negligible
- **Lookup Speed**: Faster (optimized cache key sanitization)
- **Statistics**: Comprehensive hit/miss tracking
- **Maintainability**: Single caching implementation

**Potential Concerns**:
- **Migration Time**: One-time cost during first startup
- **Namespace Overhead**: Additional directory per namespace
- **Backward Compat**: Old cache files unused (can be cleaned up)

## Monitoring & Observability

**New Cache Statistics Service**:
```python
# Add service to get cache stats
async def handle_cache_stats(call):
    """Get cache statistics."""
    stats = {
        "weather": weather_cache.get_stats(),
        "notam": notam_cache.get_stats(),
        "sensors": sensor_cache.get_stats()
    }
    return stats

hass.services.async_register(DOMAIN, "cache_stats", handle_cache_stats)
```

**Dashboard Integration**:
- Add cache statistics card to dashboard
- Show hit rates, memory usage, persistent files
- Monitor stale cache usage

## Success Criteria

- ✅ All tests pass (468 tests)
- ✅ Zero warnings
- ✅ Cache manager tests pass (all 30+ tests)
- ⬜ OWM client migrated and tested
- ⬜ NOTAM client migrated and tested
- ⬜ Sensor cache migrated and tested
- ⬜ Config migration tested
- ⬜ Performance benchmarks meet targets
- ⬜ Documentation updated

## Timeline

- **Phase 1**: ✅ Complete (Cache Manager created)
- **Phase 2**: 1-2 hours (OWM migration)
- **Phase 3**: 1 hour (NOTAM migration)
- **Phase 4**: 1 hour (Sensor migration)
- **Phase 5**: 1 hour (Config migration)
- **Phase 6**: 1 hour (Cleanup and docs)

**Total Estimated Time**: 5-7 hours

## Conclusion

The unified cache manager provides:
- **Consistency**: Single caching interface
- **Flexibility**: Configurable memory/persistent caching
- **Reliability**: Stale cache fallback
- **Observability**: Comprehensive statistics
- **Maintainability**: Reduced code duplication

This migration significantly improves code quality and maintainability while maintaining backward compatibility and improving performance.
