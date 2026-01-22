# AI Coding Agent Instructions: Hangar Assistant

## Table of Contents
- [Project Overview](#project-overview)
- [Architecture & Data Model](#architecture--data-model)
- [Backward Compatibility & Defaults](#backward-compatibility--defaults)
- [External Integrations Architecture](#external-integrations-architecture)
- [OpenWeatherMap Integration (Optional Feature)](#openweathermap-integration-optional-feature)
- [Key Patterns](#key-patterns)
- [Security Best Practices](#security-best-practices)
- [Performance Best Practices](#performance-best-practices)
- [UI/UX Guidelines for Non-Technical Users](#uiux-guidelines-for-non-technical-users)
- [Code Documentation Standards](#code-documentation-standards)
- [Feature Documentation Standards](#feature-documentation-standards)
- [Entity Implementation Patterns](#entity-implementation-patterns)
- [Services Development](#services-development)
- [Utility Modules](#utility-modules)
- [Developer Workflow & Testing](#developer-workflow--testing)
- [Error Detection & Prevention](#error-detection--prevention)

---

## Project Overview
Hangar Assistant is a Home Assistant integration for aviation safety and compliance.
- **Domain**: `hangar_assistant`
- **Dependencies**: `fpdf2` (via `manifest.json`)
- **Versioning**: `YYYYNN.V.H` format (e.g., `2601.1.0`). Hotfix defaults to 0.

## Architecture & Data Model
- **Single ConfigEntry**: Configuration is centralized. `entry.data` holds `airfields` (list), `hangars` (list), and `aircraft` (list).
- **Hangar System**: Hangars belong to airfields. Aircraft can link to hangars (which implies their airfield) or directly to airfields (legacy).
- **Data Hierarchy**: Airfield → Hangar → Aircraft. Sensor fallback: hangar sensor → airfield sensor → global sensor.
- **Dynamic Entities**: `sensor.py` and `binary_sensor.py` iterate over config lists in `async_setup_entry` to create entities.
- **Device Grouping**: Entities for a specific airfield or aircraft share `device_info` linked via `_id_slug`.
- **Unique IDs**: Generated as `{_id_slug}_{class_name_lower}` (e.g., `ksfo_densityaltsensor`). Hangars use `{airfield_slug}_{hangar_slug}`.

## Backward Compatibility & Defaults

**CRITICAL PRINCIPLE**: Existing installations must NEVER break due to updates. End users have invested significant effort in their setup. Forcing reinstalls, migrations, or configuration changes is unacceptable.

### Default Values
- **Every new configuration option MUST have a sensible default** that maintains existing behavior:
  - New features default to disabled or use traditional/conservative settings
  - New sensor parameters use safe fallbacks (e.g., `default=0`, `default=None`, `default=""`)
  - Unit preferences default to aviation units (existing behavior)
  - New boolean flags default to `False` unless explicitly enabling is required for safety
  
  Example (✓ correct):
  ```python
  unit_preference = settings.get("unit_preference", DEFAULT_UNIT_PREFERENCE)  # Defaults to aviation
  timeout = config.get("timeout_seconds", 30)  # Safe default if missing
  ```

### Graceful Degradation
- **Handle missing config keys**: Always use `.get()` with defaults, never direct dictionary access
- **Validate and coerce types**: Check if values exist and are the expected type before use
- **Fallback behavior**: If a new feature is unavailable, degrade gracefully:
  ```python
  if global_setting := settings.get("feature_flag"):
      # Use new feature
  else:
      # Use original behavior
  ```
- **Skip optional sensors**: If required config is missing, skip sensor creation but don't error:
  ```python
  if all required fields present:
      entities.append(NewSensor(...))
  # Don't append if missing - user can add later via config
  ```

### Data Migrations
- **Automatic migrations**: If config structure changes, migrate in `async_setup_entry()` BEFORE using data
- **Non-destructive**: Never delete user data; transform it in-place or create new fields
- **Document migrations**: Add comments explaining version-specific migration logic

  Example:
  ```python
  # Migrate old config format to new (v2601.2.0+)
  if "elevation_ft" in airfield and "elevation" not in airfield:
      airfield["elevation"] = airfield["elevation_ft"] * 0.3048  # Convert to meters
  ```

### Testing for Compatibility
- **Test upgrade paths**: Include test cases for existing (old) configurations:
  ```python
  def test_sensor_works_without_new_setting():
      """Test sensor works when new optional setting is missing."""
      config = {"name": "Popham"}  # Deliberately omit new field
      sensor = DensityAltSensor(mock_hass, config, {})
      assert sensor is not None  # Must not crash
  ```
- **Verify existing entities still work**: After adding new features, ensure all existing sensors/binary sensors still report correct values
- **Cross-version testing**: Test with config from previous version to ensure no breaking changes

### Adding New Features Safely
1. **Add setting with default**: `setting = config.get("feature", DEFAULT_VALUE)`
2. **Make conditionally optional**: Use new feature IF present, else use original logic
3. **Include migration code**: If changing data structure, migrate old → new format automatically
4. **Test without new feature**: Verify sensors work if user hasn't configured new setting yet
5. **Document changes**: Note in release notes which features are optional vs. mandatory

### Version-Specific Behavior
- **Feature flags for major changes**: Use version checks if needed for compatibility
- **Log migration actions**: Inform users (debug level) when migrations occur
  ```python
  _LOGGER.debug("Migrating config from v2600 format: converting elevation to meters")
  ```

### Examples of CORRECT Approaches
✓ Unit preference system: Defaults to aviation (existing behavior), users opt-in to SI  
✓ Optional sensors: Only created if required config present, gracefully skipped if missing  
✓ New parameters: All have defaults, `.get()` used throughout, no required migrations  
✓ Global settings: Stored in settings dict with defaults for any missing keys  

### Examples of INCORRECT Approaches  
✗ Forcing a config format change without automatic migration  
✗ Removing fields from config without providing fallback values  
✗ Making a previously optional parameter required  
✗ Creating sensors/entities that fail if new features not configured  
✗ Changing default behavior without version-specific handling

## External Integrations Architecture

**Centralized Management Pattern:**
All external data sources (APIs, XML feeds, etc.) are managed through a unified "Integrations" configuration menu. This provides:
- Consistent UI/UX for enabling/disabling integrations
- Centralized credential management
- Uniform caching and rate limit strategies
- Clear migration path for new features

**Configuration Structure:**
```python
entry.data["integrations"] = {
    "openweathermap": {
        "enabled": bool,
        "api_key": str,  # password field
        "cache_enabled": bool,
        "update_interval": int,  # minutes
        "cache_ttl": int  # minutes
    },
    "notams": {
        "enabled": bool,  # free service, toggle only
        "update_time": str,  # "02:00" (HH:MM format)
        "cache_days": int  # days to retain
    }
}
```

**Default Behavior (Backward Compatibility):**
- **New installs**: Free integrations (NOTAM) enabled by default
- **Existing installs**: Integrations remain in current state (migration preserves settings)
- **Migration strategy**: Settings automatically moved from global to integrations namespace

**Rate Limiting & Caching:**
- **Paid APIs (OWM)**: Multi-level cache (memory + persistent), configurable update intervals
- **Free Services (NOTAM)**: Daily scheduled updates at configured time, persistent cache only
- **Respectful scraping**: Always cache, never poll more than necessary
- **Restart protection**: Persistent cache prevents API calls during HA restarts

**Integration Client Pattern:**
Each integration has a dedicated client class in `utils/` directory:
- `utils/openweathermap.py` - OWM API client
- `utils/notam.py` - NOTAM XML parser and cache manager
- Common interface: `get_data()`, `clear_cache()`, `get_cache_stats()`

**Graceful Degradation (CRITICAL):**
All integrations MUST implement graceful failure handling:
- **Paid APIs (OWM)**: Auto-disable after 3 consecutive failures, preserve cache, notify user
- **Free Services (NOTAM)**: Use stale cache indefinitely, create warning sensor, keep trying
- **Failure tracking**: Store `consecutive_failures`, `last_error`, `last_success` in config
- **User notification**: Persistent notifications for critical issues, warning sensors for non-critical
- **Recovery**: Automatic for free services, manual re-enable for paid APIs after fixing issue
- **Core sensors**: Must continue working even if all integrations fail

## OpenWeatherMap Integration (Optional Feature)

The integration includes optional OpenWeatherMap (OWM) One Call API 3.0 support for professional weather data.

### Configuration Architecture

**Global Settings** (entry.data["settings"]):
- `openweathermap_api_key`: Optional API key (password field, empty string if not configured)
- `openweathermap_enabled`: Boolean (default: False) - master toggle
- `openweathermap_cache_enabled`: Boolean (default: True) - enable persistent caching
- `openweathermap_update_interval`: Integer (default: 10) - minutes between API calls
- `openweathermap_cache_ttl`: Integer (default: 10) - minutes cache remains valid

**Per-Airfield Settings** (airfield config):
- `weather_data_source`: String (default: "sensors") - options: "sensors", "openweathermap", "hybrid", "sensors_backup_owm"
- `use_owm_forecast`: Boolean (default: True) - create forecast sensors
- `use_owm_alerts`: Boolean (default: True) - create alert binary sensors

### Data Source Modes

| Mode | Behavior |
|------|----------|
| `"sensors"` | Use only HA sensors (default, current behavior) |
| `"openweathermap"` | Use only OWM API, ignore sensors |
| `"hybrid"` | OWM primary, fallback to sensors if OWM fails |
| `"sensors_backup_owm"` | Sensors primary, fallback to OWM if sensors unavailable |

### Caching Strategy

**Critical for rate limit protection:**
- **Two-level cache**: In-memory (session) + persistent file (survives restarts)
- **Persistent cache location**: `hass.config.path("hangar_assistant_cache/")`
- **Cache lookup order**: Memory cache → Persistent file → API call
- **Rate limit tracking**: Warns at 950/1000 daily calls
- **Restart protection**: Persistent cache prevents API calls during HA restarts/reloads

### OWM Data Points

**Current Weather** (replaces/augments sensor data):
- Temperature, dew point, pressure, wind (speed/direction/gust)
- Visibility, cloud coverage, humidity, UV index
- Weather description and icon

**Forecast Data** (new sensors):
- `sensor.{airfield}_weather_forecast_hourly`: 48-hour hourly forecast (JSON)
- `sensor.{airfield}_weather_forecast_daily`: 8-day daily forecast (JSON)
- `sensor.{airfield}_precipitation_forecast`: Minutes until next rain
- `sensor.{airfield}_uv_index`: Current UV index

**Alerts** (new binary sensors):
- `binary_sensor.{airfield}_government_weather_alert`: Active government weather warnings
- Attributes include sender, event type, severity, start/end times, description

### Implementation Patterns

**Sensor with OWM fallback:**
```python
def _get_temperature(self):
    """Get temperature with OWM fallback."""
    data_source = self.config.get("weather_data_source", "sensors")
    
    if data_source == "openweathermap":
        return self._get_owm_temperature()
    elif data_source == "sensors":
        return self._get_sensor_temperature()
    elif data_source == "hybrid":
        owm_temp = self._get_owm_temperature()
        return owm_temp if owm_temp is not None else self._get_sensor_temperature()
    elif data_source == "sensors_backup_owm":
        sensor_temp = self._get_sensor_temperature()
        return sensor_temp if sensor_temp is not None else self._get_owm_temperature()
```

**Backward Compatibility:**
- If no API key configured, OWM features completely hidden in UI
- All existing sensors work unchanged
- Per-airfield `weather_data_source` defaults to `"sensors"`
- No breaking changes for existing installations

### AI Briefing Enhancement

When OWM enabled, AI briefings include:
- 6-hour forecast trends
- 3-day daily forecast
- Government weather alerts
- Precipitation timing ("Rain in 42 minutes")
- Enhanced GO/NO-GO recommendations based on forecast

### Testing Requirements

**OWM-specific tests:**
- `test_openweathermap.py`: Client initialization, caching, API interactions, data extraction
- Mock API responses for all test scenarios
- Test cache hit/miss scenarios
- Test rate limit protection
- Test backward compatibility (sensors work without OWM)

**Integration tests:**
- Test sensor creation with different `weather_data_source` modes
- Test fallback behavior
- Test forecast sensor attributes
- Test alert sensor state transitions

✓ Global settings: Stored in settings dict with defaults for any missing keys  

### Examples of INCORRECT Approaches  
✗ Forcing a config format change without automatic migration  
✗ Removing fields from config without providing fallback values  
✗ Making a previously optional parameter required  
✗ Creating sensors/entities that fail if new features not configured  
✗ Changing default behavior without version-specific handling

## Key Patterns
- **Slugification**: Consistent ID generation: `_id_slug = (config.get("name") or config.get("reg")).lower().replace(" ", "_")`.
- **Sibling Entity Reference**: Sensors reference each other using constructed entity IDs (e.g., `HangarMasterSafetyAlert` monitors `sensor.{_id_slug}_weather_data_age`).
- **Base Class**: `HangarSensorBase` handles device registration, `_id_slug` generation, and safe state retrieval (`_get_sensor_value`).
- **Aviation Formulas**:
  - DA: `4000 + (120 * (temp - 15))` ft
  - Cloud Base: `((t - dp) / 2.5) * 1000` ft
  - Carb Risk: "Serious" if `T < 25` and `Spread < 5`.

## Security Best Practices

**CRITICAL PRINCIPLE**: Security must be considered at every level of development. This integration handles user data, external API credentials, and file system operations that require careful security considerations.

### Sensitive Data Protection

**Never log or expose sensitive data:**
- API keys, passwords, tokens, secrets must NEVER appear in logs
- Implement sanitization helpers to scrub sensitive fields before logging
- Use `selector.TextSelectorType.PASSWORD` for all credential inputs in config flow
- Store credentials in `entry.data` with clear naming (`*_api_key`, `*_password`, `*_token`)

**Example - Log Sanitization:**
```python
def _sanitize_config_for_logging(config: dict) -> dict:
    """Remove sensitive data before logging config."""
    sanitized = config.copy()
    sensitive_keys = ["api_key", "password", "token", "secret"]
    for key in sensitive_keys:
        if key in sanitized:
            sanitized[key] = "***REDACTED***"
    return sanitized

_LOGGER.debug("Config loaded: %s", _sanitize_config_for_logging(config))
```

### Input Sanitization

**ALL user input used in file paths MUST be sanitized:**
- Whitelist pattern: `^[a-zA-Z0-9_-]+$` for identifiers
- Never trust user input for file operations
- Validate against path traversal attacks (`..`, `/`, `\`, absolute paths)
- Use `pathlib.Path` for safe path construction

**Example - Path Sanitization:**
```python
import re
from pathlib import Path

def sanitize_filename(user_input: str) -> str:
    """Sanitize user input for safe file naming.
    
    Args:
        user_input: Raw user input (airfield name, aircraft reg, etc.)
    
    Returns:
        Sanitized string safe for file paths
    
    Raises:
        ValueError: If input contains no valid characters
    """
    # Remove all characters except alphanumeric, underscore, hyphen
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', user_input)
    
    if not sanitized:
        raise ValueError(f"Invalid input for filename: {user_input}")
    
    # Limit length to prevent filesystem issues
    return sanitized[:255]

# Usage in cache file naming
cache_key = sanitize_filename(airfield_name)
cache_file = cache_dir / f"{cache_key}.json"
```

### Async File Operations

**ALL file I/O in async functions MUST use executor jobs:**
- Never use blocking `open()`, `json.load()`, `json.dump()`, `yaml.load()`, `yaml.dump()` directly
- Always wrap file operations in `hass.async_add_executor_job()`
- This applies to: reading config files, writing cache files, loading templates, PDF generation

**Example - Async File Operations:**
```python
# ❌ WRONG - Blocks event loop
async def load_config_wrong():
    with open(config_path, 'r') as f:
        return json.load(f)

# ✅ CORRECT - Non-blocking
async def load_config_correct(hass: HomeAssistant, config_path: str):
    def _read_file():
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    return await hass.async_add_executor_job(_read_file)
```

### Exception Handling

**Use specific exception types, never broad catches:**
- Catch specific exceptions: `OSError`, `json.JSONDecodeError`, `ValueError`, etc.
- Use `except Exception` ONLY when truly necessary with explicit justification
- Always log unexpected exceptions with full context
- Never silence exceptions without logging

**Example - Proper Exception Handling:**
```python
# ❌ WRONG - Masks all errors
try:
    data = process_data()
except Exception:
    pass

# ✅ CORRECT - Specific and informative
try:
    data = process_data()
except json.JSONDecodeError as e:
    _LOGGER.error("Invalid JSON in data file: %s", e)
    return None
except OSError as e:
    _LOGGER.error("File system error: %s", e)
    return None
except ValueError as e:
    _LOGGER.warning("Invalid data format: %s", e)
    return default_data
```

### External Data Security

**Validate and sanitize all external data:**
- XML parsing must use `defusedxml` library or secure ElementTree configuration
- Validate API responses before processing (check status, content-type, structure)
- Implement rate limiting for external service calls
- Use timeouts on all HTTP requests (default: 30 seconds)

**Example - Secure XML Parsing:**
```python
# ❌ WRONG - Vulnerable to XXE attacks
import xml.etree.ElementTree as ET
tree = ET.fromstring(xml_content)

# ✅ CORRECT - Protected against XXE
try:
    from defusedxml import ElementTree as DefusedET
    tree = DefusedET.fromstring(xml_content)
except ImportError:
    import xml.etree.ElementTree as ET
    # Disable external entity expansion
    parser = ET.XMLParser()
    parser.entity = {}  # Disable entities
    tree = ET.fromstring(xml_content, parser=parser)
```

### Error Transparency

**Never fail silently on security boundaries:**
- Permission failures must notify users via persistent notifications
- Cache directory creation failures require user notification
- API key validation failures must be surfaced to user
- Log all security-relevant events at WARNING or ERROR level

**Example - User Notifications:**
```python
from homeassistant.components.persistent_notification import create

async def handle_cache_permission_error(hass: HomeAssistant):
    """Notify user of cache permission failure."""
    _LOGGER.error(
        "Cannot create cache directory - check permissions: %s",
        cache_dir
    )
    
    await create(
        hass,
        message=(
            "Hangar Assistant cannot create cache directory. "
            f"Please check permissions for: {cache_dir}"
        ),
        title="Hangar Assistant: Cache Error",
        notification_id="hangar_cache_permission_error"
    )
```

### Security Testing Requirements

**All security-sensitive code must have unit tests:**
- Test input sanitization with malicious inputs (`../etc/passwd`, `../../`, absolute paths)
- Test exception handling with corrupted/malicious data
- Test API key sanitization in log output
- Test XML parsing with XXE attack vectors
- Test file operations fail gracefully without permissions

**Example - Security Test:**
```python
def test_sanitize_filename_blocks_path_traversal():
    """Test filename sanitization blocks path traversal attacks."""
    malicious_inputs = [
        "../../../etc/passwd",
        "../../config",
        "/absolute/path",
        "contains/slash",
        "has\\backslash",
    ]
    
    for malicious in malicious_inputs:
        result = sanitize_filename(malicious)
        assert ".." not in result
        assert "/" not in result
        assert "\\" not in result
        assert not result.startswith("/")
```

### Security Checklist for Code Reviews

Before merging any PR, verify:
- [ ] No API keys/passwords/tokens in logs
- [ ] All user input sanitized before file operations
- [ ] All file I/O wrapped in executor jobs
- [ ] Specific exception types used (not broad catches)
- [ ] External data validated and sanitized
- [ ] Permission failures notify users
- [ ] Security tests added for new features

## Performance Best Practices

**CRITICAL PRINCIPLE**: Performance optimization must maintain code quality, security, and readability. Never sacrifice maintainability for marginal performance gains.

### Caching Strategies

**Template caching with mtime checks:**
- Cache expensive operations like YAML template loading
- Use file modification time (mtime) to detect changes
- Only reload when source file actually changes

**Example - Dashboard Template Caching:**
```python
import time
from pathlib import Path

# Module-level cache
_dashboard_template_cache: Optional[str] = None
_dashboard_template_mtime: Optional[float] = None

async def _load_dashboard_template(hass: HomeAssistant) -> Optional[str]:
    """Load dashboard template with mtime-based caching.
    
    Performance: 40-60% faster on cache hits, eliminates redundant file I/O.
    """
    global _dashboard_template_cache, _dashboard_template_mtime
    
    template_path = Path(__file__).parent / "dashboard_templates" / "glass_cockpit.yaml"
    
    try:
        current_mtime = template_path.stat().st_mtime
        
        # Cache hit if file unchanged
        if (_dashboard_template_cache is not None 
            and _dashboard_template_mtime == current_mtime):
            return _dashboard_template_cache
        
        # Cache miss - reload and update
        def _read():
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        content = await hass.async_add_executor_job(_read)
        _dashboard_template_cache = content
        _dashboard_template_mtime = current_mtime
        
        return content
        
    except OSError as e:
        _LOGGER.error("Failed to load dashboard template: %s", e)
        return None
```

### JSON Optimization

**Use orjson for performance-critical JSON operations:**
- orjson is 2-5x faster than standard json library
- Always provide fallback to standard json
- Use for: cache serialization, large data structures, frequent JSON operations

**Example - Optimized JSON Serialization:**
```python
try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    import json
    HAS_ORJSON = False

def _serialize_json(self, data: Dict[str, Any]) -> bytes:
    """Serialize to JSON with orjson optimization (2-5x faster).
    
    Args:
        data: Dictionary to serialize
    
    Returns:
        JSON as bytes (orjson) or UTF-8 encoded string (json)
    """
    if HAS_ORJSON:
        return orjson.dumps(data)
    else:
        return json.dumps(data).encode('utf-8')

def _deserialize_json(self, json_bytes: bytes) -> Dict[str, Any]:
    """Deserialize JSON with orjson optimization.
    
    Args:
        json_bytes: JSON data as bytes
    
    Returns:
        Deserialized dictionary
    """
    if HAS_ORJSON:
        return orjson.loads(json_bytes)
    else:
        return json.loads(json_bytes.decode('utf-8'))
```

### Memory Cache Management

**LRU eviction with OrderedDict:**
- Prevent unbounded memory growth in caches
- Use OrderedDict for efficient LRU (Least Recently Used) eviction
- Set reasonable limits based on data size (default: 1000 entries)

**Example - LRU Memory Cache:**
```python
from collections import OrderedDict

class CacheManager:
    """Cache with LRU eviction to prevent memory bloat."""
    
    def __init__(self, max_memory_entries: int = 1000):
        self._memory_cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_memory_entries = max_memory_entries
    
    def get(self, key: str) -> Optional[Any]:
        """Get from cache and update LRU order."""
        if key in self._memory_cache:
            # Move to end (most recently used)
            self._memory_cache.move_to_end(key)
            return self._memory_cache[key]
        return None
    
    def set(self, key: str, value: CacheEntry) -> None:
        """Set cache entry with LRU eviction."""
        # Update existing or add new
        if key in self._memory_cache:
            self._memory_cache.move_to_end(key)
        
        self._memory_cache[key] = value
        
        # Evict oldest if over limit
        while len(self._memory_cache) > self._max_memory_entries:
            # popitem(last=False) removes oldest (FIFO for LRU)
            evicted_key, _ = self._memory_cache.popitem(last=False)
            _LOGGER.debug("Evicted cache entry: %s", evicted_key)
```

### Optimizing File I/O

**Eliminate redundant cache reads:**
- Read cache file once, reuse data in fallback paths
- Don't re-read the same file on failure

**Example - Efficient Cache Reads:**
```python
# ❌ WRONG - Reads cache twice
async def fetch_data(self):
    cached = await self._read_cache()
    if cached:
        return cached
    
    try:
        return await self._fetch_from_api()
    except Exception:
        # BAD: Reads cache file again!
        return await self._read_cache()

# ✅ CORRECT - Reads cache once
async def fetch_data(self):
    # Single cache read
    cached = await self._read_cache()
    if cached:
        return cached
    
    try:
        return await self._fetch_from_api()
    except Exception:
        # Reuse already-loaded cache data
        stale = await self._read_stale_cache()
        return stale if stale else []
```

### Sensor State Caching

**Cache computed sensor states to reduce redundant calculations:**
- Use TTL (time-to-live) for cache expiry
- LRU eviction for memory safety
- Cache invalidation on config changes

**Example - Sensor State Cache (already implemented in sensor.py):**
```python
from collections import OrderedDict
from homeassistant.util import dt as dt_util

class HangarSensorBase(SensorEntity):
    """Base sensor with state caching."""
    
    # Shared cache across all sensor instances
    _state_cache: OrderedDict[str, tuple] = OrderedDict()
    _cache_ttl_seconds = 60
    _max_cache_entries = 50
    
    def _get_cached_state(self, cache_key: str) -> Optional[Any]:
        """Get cached state if still valid."""
        if cache_key in self._state_cache:
            cached_value, cached_time = self._state_cache[cache_key]
            age = (dt_util.utcnow() - cached_time).total_seconds()
            
            if age < self._cache_ttl_seconds:
                # Move to end for LRU
                self._state_cache.move_to_end(cache_key)
                return cached_value
        
        return None
    
    def _cache_state(self, cache_key: str, value: Any) -> None:
        """Cache state value with LRU eviction."""
        self._state_cache[cache_key] = (value, dt_util.utcnow())
        self._state_cache.move_to_end(cache_key)
        
        # Evict oldest if over limit
        while len(self._state_cache) > self._max_cache_entries:
            self._state_cache.popitem(last=False)
```

### Performance Testing Requirements

**All performance optimizations must include benchmarks:**
- Measure baseline before optimization
- Verify improvement with realistic data
- Test memory usage (cache growth, eviction)
- Profile CPU usage for expensive operations

**Example - Performance Test:**
```python
import time

def test_template_caching_performance():
    """Verify template caching provides measurable speedup."""
    # Clear cache
    global _dashboard_template_cache, _dashboard_template_mtime
    _dashboard_template_cache = None
    _dashboard_template_mtime = None
    
    # First load (cache miss)
    start = time.time()
    result1 = await _load_dashboard_template(hass)
    uncached_time = time.time() - start
    
    # Second load (cache hit)
    start = time.time()
    result2 = await _load_dashboard_template(hass)
    cached_time = time.time() - start
    
    # Verify caching works
    assert result1 == result2
    # Cached should be at least 40% faster
    assert cached_time < (uncached_time * 0.6)
```

### Performance Checklist for Code Reviews

Before merging performance optimizations, verify:
- [ ] Baseline performance measured
- [ ] Optimization provides ≥20% improvement
- [ ] Memory usage bounded (LRU eviction in place)
- [ ] No impact on code complexity (≤15 cognitive complexity)
- [ ] Security not compromised (async file I/O, input validation maintained)
- [ ] Backward compatible (fallbacks for optional dependencies)
- [ ] Performance tests added
- [ ] Documentation updated

## UI/UX Guidelines for Non-Technical Users

**CRITICAL PRINCIPLE**: Hangar Assistant users are pilots, not programmers. Every interface, configuration option, and error message must be designed for aviation professionals who may have limited technical knowledge.

### User-Centered Design Principles

**1. Aviation Language, Not Technical Jargon**
- ✅ CORRECT: "ICAO code (e.g., EGHP for Popham)"
- ❌ WRONG: "Enter string matching pattern ^[A-Z]{4}$"
- ✅ CORRECT: "Your aircraft registration (tail number)"
- ❌ WRONG: "Aircraft identifier (alphanumeric string)"

**2. Real-Time Validation with Helpful Feedback**
- Show validation status as user types (✅/❌ icons)
- Error messages must explain WHAT is wrong and HOW to fix it
- Provide examples of correct format in error messages
- Never show technical error traces to users

Example validation patterns:
```python
# ✅ CORRECT - Helpful error message
"ICAO codes are exactly 4 characters (e.g., EGHP, KJFK)"

# ❌ WRONG - Technical error
"ValueError: invalid ICAO format"
```

**3. Progressive Disclosure**
- Start simple: Show only essential fields initially
- Use "Show Advanced" toggles for optional/expert settings
- Group related settings together logically
- Provide defaults for everything - never leave users guessing

**4. Tooltips and Inline Help**
- Every non-obvious field needs a tooltip (💬 icon)
- Tooltips should be concise (1-2 sentences)
- Link to detailed documentation for complex topics
- Use aviation terminology pilots understand

Example tooltip patterns:
```yaml
# ✅ CORRECT
"💬 MTOW: Maximum Takeoff Weight from your Aircraft POH.
    Used to calculate performance margins and safety alerts."

# ❌ WRONG
"MTOW: Max weight parameter"
```

**5. Templates and Auto-Population**
- Provide aircraft type templates (Cessna 172, PA-28, etc.)
- Auto-populate from APIs when possible (CheckWX station data)
- Show what was auto-populated and allow editing
- Never force users to manually enter data that can be fetched

**6. Error Prevention Over Error Handling**
- Validate inputs before submission
- Disable invalid options rather than showing errors
- Use dropdowns/selectors instead of free-text where possible
- Provide sensible defaults that work for most users

**7. Clear Success Indicators**
- Show what was created after each step (sensor count, entity IDs)
- Provide "what's next" guidance after completion
- Confirm actions with visual feedback (✅ Success messages)
- Test connections immediately and show results

### Configuration Flow Best Practices

**Structure:**
1. **Welcome Screen** - Explain what integration does, time estimate
2. **Essential Settings** - Only absolutely required fields
3. **Optional Enhancements** - APIs, advanced features (clearly marked optional)
4. **Confirmation** - Show summary before creating
5. **Success Screen** - What was created, next steps

**Field Design:**
```python
# Always provide:
# 1. Clear label in plain language
# 2. Helpful description/tooltip
# 3. Example value
# 4. Default value (if applicable)
# 5. Real-time validation

data_schema = vol.Schema({
    vol.Required("icao", description="ICAO Code"): str,
    # Add tooltip: "4-letter airport code (e.g., EGHP, KJFK)"
    # Add placeholder: "EGHP"
    # Add validation: Real-time check + helpful errors
})
```

**Multi-Step Wizards:**
- Show progress indicator ("Step 3 of 7")
- Allow going back to previous steps
- Save progress automatically
- Provide "Skip" option for optional steps
- Show completion percentage

### Error Messages for Pilots

**Pattern: Problem → Explanation → Solution**

✅ **CORRECT Examples:**
```
"❌ ICAO code must be uppercase
   You entered: 'eghp'
   Try: 'EGHP'"

"❌ API connection failed
   CheckWX could not be reached. Check your API key.
   Get a free key at: https://checkwxapi.com/signup"

"❌ Aircraft registration format not recognized
   You entered: 'ABCD'
   Examples: G-ABCD (UK), N12345 (US), D-EFGH (Germany)"
```

❌ **WRONG Examples:**
```
"Invalid input"
"Error 422: Unprocessable Entity"
"TypeError: expected str, got NoneType"
```

### Dashboard and Entity Naming

**Entity ID Patterns:**
- Use aircraft registration slugs: `sensor.g_abcd_fuel_endurance`
- Use airfield name slugs: `sensor.popham_density_altitude`
- Never use GUIDs or random strings
- Keep names under 50 characters

**Friendly Names:**
- Natural language: "Popham Density Altitude"
- Include aircraft reg: "G-ABCD Fuel Endurance"
- Avoid abbreviations unless universally understood (MTOW, VFR)

**Attribute Names:**
- Use aviation terms: `crosswind_component` not `x_wind`
- Include units: `temperature_c`, `altitude_ft`
- Spell out: `last_updated_time` not `last_upd_t`

### Dashboard Design Principles

**Layout:**
- Group by function: Weather → Performance → Safety → Fuel
- Use cards, not tables (easier on mobile)
- Show most critical info at top
- Use color coding: 🟢 Safe → 🟡 Caution → 🔴 Warning

**Data Visualization:**
- Always show units (not just numbers)
- Use gauges for ranges (DA, cloud base)
- Use badges for status (VFR/MVFR/IFR)
- Animated icons for real-time data (wind)

**Mobile-First:**
- Touch-friendly buttons (minimum 44px)
- Readable text sizes (16px+ body text)
- No horizontal scrolling
- Works in portrait and landscape

### Onboarding Experience

**First-Time Setup:**
1. **Welcome** - Show value proposition, time estimate
2. **Quick Start Templates** - "UK PPL", "US Sport Pilot", "Glider"
3. **Guided Wizard** - Step-by-step with validation
4. **Auto-Population** - Fetch from APIs (CheckWX, OWM)
5. **Success Screen** - Show what was created, next steps

**Setup Wizard Principles:**
- ≤15 minutes from install to functional dashboard
- No step should require reading documentation
- Provide templates for common aircraft types
- Auto-populate whenever possible
- Show progress throughout

### Accessibility

**For Non-Technical Users:**
- No assumptions of HA knowledge required
- Explain integration concepts in aviation terms
- Link to detailed docs for complex features
- Provide visual examples (screenshots)

**For Screen Readers:**
- All icons have text alternatives
- Form labels properly associated
- Error messages announced
- Status changes announced

### Documentation Requirements

Every new feature must include:
- **User-facing**: Plain language explanation (no code)
- **Examples**: Real-world scenarios pilots understand
- **Tooltips**: Inline help for every field
- **Screenshots**: Visual guides for config flows
- **Troubleshooting**: Common issues with solutions

### Testing with Non-Technical Users

Before releasing UI/UX changes:
- [ ] Can a pilot configure it without documentation?
- [ ] Are all error messages helpful and actionable?
- [ ] Does auto-population work where expected?
- [ ] Are defaults sensible for most users?
- [ ] Is mobile experience smooth?
- [ ] Does it work on first try (80%+ success rate)?

## Code Documentation Standards

**All new classes and functions must include comprehensive docstrings** that follow this format:

### Class Docstrings
```python
class MyClass:
    """Brief one-line description of what the class does.
    
    Longer description explaining the purpose, key responsibilities, and how it fits into the system.
    
    Inputs (if applicable):
        - config_param: Description and expected type
        - another_param: Description and expected type
    
    Outputs/Behavior:
        - Brief description of what the class produces or manages
        - Key properties or methods
    
    Used by:
        - Dashboard cards
        - Automation triggers
        - Other systems that depend on this class
    
    Example:
        - Specific usage example if helpful
    """
```

### Function Docstrings
```python
def my_function(param1: str, param2: int) -> bool:
    """Brief description of what the function does.
    
    Longer explanation of the function's purpose, algorithm, or key behavior.
    
    Args:
        param1: Description and expected format/range
        param2: Description and expected format/range
    
    Returns:
        Description of return value and when it occurs
    
    Raises:
        ValueError: When inputs are invalid
    """
```

**Key Documentation Principles:**
- **Purpose**: Clearly state what the code does and why it exists
- **Inputs**: Document all parameters with types and expected values/ranges
- **Outputs**: Explain return values or behavior changes
- **Context**: Mention how the code integrates with the broader system
- **Examples**: Include usage examples for complex functions/classes
- **Comments**: Use inline comments for non-obvious logic or calculations (especially aviation formulas)

## Feature Documentation Standards

**CRITICAL PRINCIPLE**: Every feature that users interact with MUST have user-centric documentation in `docs/features/`. This ensures features remain accessible, maintainable, and understandable to non-technical pilots.

### Documentation Location & Organization

**User-facing features**: `docs/features/{feature_name}.md`
- Setup wizard, dashboard installation, AI briefings, NOTAM integration, etc.
- Focus: What users see, how to use it, troubleshooting user issues

**Developer documentation**: `docs/development/{topic}.md`
- Architecture decisions, migration guides, code quality reviews
- Focus: Implementation details, technical design, developer workflows

**API & Integration references**: `docs/api/{service_name}.md` (future)
- External API documentation, integration protocols
- Focus: Technical specifications for integrations

**Release notes**: `docs/releases/RELEASE_NOTES_{version}.md`
- What changed, breaking changes, upgrade instructions
- Focus: Version-specific changes and migration paths

### Required Documentation Elements

Every feature document MUST include:

1. **Overview**
   - What the feature does in 2-3 sentences
   - Why it exists (user benefit, safety improvement)
   - When it appears or how to access it
   - Example: "The Setup Wizard guides you through first-time configuration in 7 steps, appearing automatically when no airfields are configured."

2. **Step-by-Step Usage**
   - Complete walkthrough of user journey
   - Screenshots or examples for each step
   - What users see at each stage
   - Expected outcomes
   - Example: "Step 1: Welcome Screen → Shows overview and time estimate (2-5 minutes)"

3. **Troubleshooting**
   - Common issues users encounter
   - Clear problem → solution format
   - Real error messages users see (not code exceptions)
   - Links to related troubleshooting docs
   - Example: "Problem: Wizard won't appear. Solution: Check if airfields already configured in Settings → Devices & Services → Hangar Assistant."

4. **FAQ**
   - 5-10 frequently asked questions
   - Practical questions users actually ask
   - Direct answers without jargon
   - Example: "Q: Can I change settings later? A: Yes, go to Settings → Devices & Services → Hangar Assistant → Configure."

5. **Best Practices**
   - Tailored guidance for different user types (student pilot, private pilot, glider pilot, etc.)
   - Tips for optimal usage
   - Common mistakes to avoid
   - Real-world scenarios
   - Example: "Student Pilots: Start with one airfield and practice aircraft. Add more as you gain experience."

6. **Technical Details** (Optional, collapsible)
   - For advanced users who want deeper understanding
   - Config entry structure, entity naming patterns
   - Integration with other features
   - Customization options
   - Example: "Advanced: Dashboard state persists per-device using localStorage. Override with URL parameters for fixed displays."

7. **Related Documentation**
   - Links to complementary features
   - External references (aviation regulations, API docs)
   - Next steps or advanced usage
   - Example: "Related: [Aircraft Templates](aircraft_templates.md), [Dashboard Customization](dashboard_guide.md)"

### Writing Style Guidelines

**Transform Technical → User-Friendly:**

✅ **CORRECT Examples:**
```
Technical: "SetupWizardState class tracks completed_steps as a Set"
User: "The wizard remembers which steps you've completed so you can return later"

Technical: "async_step_welcome() returns Form with schema validation"
User: "Step 1 shows an overview of what you'll configure (takes 2-5 minutes)"

Technical: "ICAO validation uses regex pattern ^[A-Z]{4}$"
User: "Enter your 4-letter airport code (e.g., EGHP for Popham)"

Technical: "Background task scheduled with 2-second delay for entry initialization"
User: "Dashboard installs automatically in the background without blocking the wizard"

Technical: "Entity IDs generated using _slugify() for consistency"
User: "Sensors named after your airfield (e.g., sensor.popham_density_altitude)"
```

❌ **WRONG Examples:**
```
"The config flow instantiates HangarAssistantConfigFlow"
"Uses vol.Schema for form validation"
"Raises ConfigEntryNotReady on initialization failure"
"Implements async_setup_entry() pattern"
```

**Key Principles:**
- **Aviation language, not code**: "ICAO code" not "4-character string identifier"
- **User benefits, not implementation**: "Automatically fetches weather" not "Calls OpenWeatherMap API with caching"
- **Examples over theory**: Show EGHP, KJFK, not just "4 letters"
- **Progressive disclosure**: Essential info first, advanced details in collapsible sections
- **Actionable guidance**: "Do this" not "You could potentially consider"

### Documentation Update Requirements

**CRITICAL**: Code changes that affect user experience MUST update feature documentation.

**When to update docs:**
- ✅ New wizard step added → Update setup_wizard.md step-by-step section
- ✅ Error message changed → Update troubleshooting section
- ✅ New configuration option → Add to FAQ and best practices
- ✅ UI flow modified → Update step-by-step walkthrough
- ✅ New entity created → Document in "what gets created" section
- ✅ Service behavior changed → Update usage instructions

**Update checklist:**
1. **Overview**: Does high-level description still match feature?
2. **Steps**: Do walkthrough steps reflect actual UI flow?
3. **Troubleshooting**: Are error messages and solutions current?
4. **FAQ**: Do answers reflect new behavior?
5. **Best Practices**: Do recommendations align with new capabilities?
6. **Technical Details**: Are entity IDs, config structure accurate?
7. **Related Docs**: Are cross-references still valid?

**Don't update docs for:**
- ❌ Internal refactoring (no user-visible change)
- ❌ Code comment improvements
- ❌ Test additions (unless exposing new user-facing behavior)
- ❌ Performance optimizations (unless user-noticeable)

### Documentation Structure Example

Based on `docs/features/setup_wizard.md` (established pattern):

```markdown
# Feature Name

## Overview
[2-3 sentence description of what, why, when]

## Getting Started
[Prerequisites, access method, initial setup]

## Step-by-Step Guide
### Step 1: [Name]
[What user sees, what to enter, what happens]

### Step 2: [Name]
[Continue for all steps]

## After Completion
[What was created, immediate next steps]

## Troubleshooting
### Problem: [Specific issue]
**Symptoms**: [What user sees]
**Solution**: [Exact steps to fix]

## FAQ
### [Question users actually ask]?
[Direct answer in plain language]

## Best Practices
### For [User Type 1]
[Tailored recommendations]

### For [User Type 2]
[Different recommendations]

## Technical Details (Advanced)
<details>
<summary>Click to expand</summary>

[Technical architecture, entity structure, customization options]

</details>

## Related Documentation
- [Link to related feature]
- [Link to external reference]

## Version History
### v1.0 (Current)
- Initial release
- [Key features]

### Planned Enhancements
- [Future improvements]
```

### Validation & Quality Checks

Before merging new feature documentation:

**Content Completeness:**
- [ ] All 7 required sections present (Overview, Usage, Troubleshooting, FAQ, Best Practices, Technical, Related)
- [ ] No technical jargon without plain-language explanation
- [ ] Real examples provided (ICAO codes, aircraft regs, etc.)
- [ ] Links to related docs valid and working

**User Accessibility:**
- [ ] Can a non-technical pilot understand without reading code?
- [ ] Are error messages shown as users see them (not code exceptions)?
- [ ] Do troubleshooting steps actually solve the problem?
- [ ] Are best practices actionable and specific?

**Synchronization:**
- [ ] Documentation matches current UI flow
- [ ] Entity IDs and sensor names accurate
- [ ] Screenshots (if present) show current interface
- [ ] Version history updated

**Style Compliance:**
- [ ] Aviation terminology used consistently
- [ ] Transformation from technical to user-friendly complete
- [ ] Examples use real-world values (EGHP, G-ABCD, etc.)
- [ ] Progressive disclosure: simple first, advanced later

### Documentation Maintenance Workflow

**For new features:**
1. Implement code and tests
2. Create `docs/features/{feature}.md` using template above
3. Transform technical implementation into user benefits
4. Add troubleshooting for anticipated issues
5. Include FAQ based on user research or common questions
6. Link from related docs

**For feature updates:**
1. Make code changes
2. Identify affected documentation sections
3. Update user-facing descriptions to match new behavior
4. Add new troubleshooting if issues discovered
5. Update FAQ if new questions arise
6. Review cross-references

**For major refactors:**
1. If user experience unchanged: No doc updates needed
2. If UI flow changes: Update step-by-step guide
3. If entities renamed: Update technical details section
4. If behavior changes: Update overview and best practices

### Example: Phase 2-4 Documentation Consolidation

**Before (Developer-focused):**
- `PHASE_2_3_COMPLETION_SUMMARY.md`: Technical implementation details
- `PHASE_4_COMPLETION_SUMMARY.md`: Service handler specifications
- Audience: Developers
- Content: Code structure, test results, implementation notes

**After (User-focused):**
- `docs/features/setup_wizard.md`: Comprehensive user guide
- Audience: Pilots using the integration
- Content: How to use wizard, troubleshooting, best practices, FAQ
- Consolidates 3 phases into single maintainable document

**Transformation highlights:**
```markdown
Before: "async_step_general_settings() collects unit preferences and defaults"
After: "Step 2: Choose your preferred units (aviation standard or metric)"

Before: "CheckWX integration validates API key via test request"
After: "We'll test your CheckWX API key to ensure it works (free signup available)"

Before: "Dashboard installation spawns background task with 2s delay"
After: "Dashboard installs automatically in the background - you can continue using Home Assistant"
```

## Entity Implementation Patterns
- **Safety Alerts**: `HangarMasterSafetyAlert` (Binary Sensor, class `SAFETY`) triggers if weather data > 30 mins old or Carb Risk is "Serious Risk".
- **File Management**: PDFs stored in `hass.config.path("www/hangar/")`. `manual_cleanup` service handles deletion.
- **AI Prompts**: All AI-related prompts (system prompts, briefing templates) must be stored as `.txt` files in the `custom_components/hangar_assistant/prompts/` directory. Do not hardcode complex prompts in Python code.
- **Reference Documentation**: Context-specific reference materials are stored as `.txt` files in `custom_components/hangar_assistant/references/`. These include:
  - `vfr.txt`: UK CAA Visual Flight Rules (VFR) requirements and minima
  - Other aviation regulations and compliance standards
  - Use these files as authoritative sources when implementing rules-based features
- **Config Flow**: `HangarAssistantConfigFlow` (single instance). `HangarOptionsFlowHandler` handles updates (`airfield`, `aircraft` menus) using `EntitySelector`.
- **Time Tracking**: `async_track_time_change` used for briefing schedules in `__init__.py`.

### Sensor Implementation
- Derive from `SensorEntity` (imported from `homeassistant.components.sensor`)
- Filter config entries by type in `async_setup_entry()` before creating entities
- Access Home Assistant state machine via `self.hass.states.get(entity_id)` for sensor reads
- Name pattern: `f"{config['name']} {metric_name}"` (e.g., "The Airfield Carb Risk")
- **Best Runway Logic**: Uses `BestRunwaySensor` to calculate optimal runway based on wind and provides `crosswind_component` as an attribute.
- **Map Integration**: Sensors for airfields should include `latitude` and `longitude` attributes to enable automatic plotting on map cards.

### Select Entity Implementation
- Derive from `SelectEntity` (imported from `homeassistant.components.select`)
- Provides built-in dropdowns for airfield, aircraft, and pilot selection without requiring user-created input_select helpers
- Options derived from config entry data: `entry.data.get("airfields")`, `entry.data.get("aircraft")`, etc.
- Uses `_slugify()` helper for consistent ID generation from names/registrations
- Pattern: `f"select.{entity_type}_selector"` (e.g., `select.airfield_selector`)
- Stores selected value in state; updates when user changes selection via UI
- Device grouping: All selectors share a common device info for dashboard organization
- Used by: Dashboard cards for dynamic filtering and context switching

### Dashboard & UI
- Template located in `dashboard_templates/glass_cockpit.yaml`.
- Uses Mushroom cards and ApexCharts (suggest these to users).
- Performance sliders: Uses `input_number` helpers (user-defined) to drive dynamic ground roll adjustments.

**Dashboard State Management (Per-Device Selection):**
- Each device/browser maintains independent airfield/aircraft view using `hangar_state_manager.js`
- Priority system: URL params → localStorage → config defaults → auto-detection
- **Fixed displays**: Use URL parameters for permanent selection
  - Example: `http://homeassistant:8123/hangar-glass-cockpit?airfield=popham&aircraft=g_abcd`
- **Interactive users**: Browser localStorage preserves last selection
- **Config defaults**: Set in Settings → General Settings → Default Dashboard Airfield/Aircraft
- **Backward compatibility**: Select entities remain functional for automations
- Implementation file: `dashboard_templates/hangar_state_manager.js`

## Services Development

Services are defined in `services.yaml` and registered in `__init__.py`. All services must follow Home Assistant service patterns:

### Service Registration Pattern
```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up integration and register services."""
    
    async def handle_service(call: ServiceCall) -> None:
        """Handle service call."""
        # Extract parameters
        param = call.data.get("param_name", default_value)
        # Perform action
        await async_do_something(param)
    
    hass.services.async_register(DOMAIN, "service_name", handle_service)
```

### Available Services

**manual_cleanup**: Purges aviation records (PDFs) older than specified retention period
- Parameters: `retention_months` (1-24, default: 7)
- Implementation: Scans `www/hangar/` directory, deletes files older than threshold
- Usage: Automation or manual maintenance

**rebuild_dashboard**: Forces fresh generation of dashboard from template
- Parameters: None
- Implementation: Regenerates dashboard YAML from `dashboard_templates/glass_cockpit.yaml`
- Usage: After config changes or template updates

**refresh_ai_briefings**: Manually triggers AI briefing generation
- Parameters: None
- Implementation: Calls AI API with current weather/NOTAM data for all airfields
- Usage: On-demand briefing updates outside scheduled times

**speak_briefing**: Speaks current AI briefing via TTS
- Parameters: `tts_entity_id` (required), `media_player_entity_id` (optional)
- Implementation: Retrieves briefing text, calls TTS service, plays on media player
- Usage: Voice briefing delivery; defaults to browser player if available

### Service Best Practices
- Always use `async def` for service handlers
- Validate parameters with `.get()` and defaults
- Log service calls at debug level: `_LOGGER.debug(f"Service called: {call.data}")`
- Raise `ServiceValidationError` for invalid parameters (from `homeassistant.exceptions`)
- Use `hass.async_add_executor_job()` for blocking I/O operations
- Update related entities after service completion: `async_write_ha_state()`

## Utility Modules

Common functionality is organized in `utils/` directory:

### units.py - Unit Conversion
Provides conversion between aviation and SI units:
- **UnitPreference class**: Manages global unit preference (aviation/SI)
- **Conversion constants**: `FEET_TO_METERS`, `KNOTS_TO_KPH`, `POUNDS_TO_KG`
- **Conversion functions**: Bidirectional conversion with preference awareness
- Used by: All sensors for consistent unit display based on user preference
- Pattern: `convert_distance(value, from_unit, to_unit, preference)`

### i18n.py - Internationalization
Handles translation and localization:
- **SUPPORTED_LANGS**: `["en", "de", "es", "fr"]`
- **COMMON_LABELS**: Dictionary of reusable translated strings for UI elements
- **get_available_languages()**: Returns list of available language packs
- **validate_translations()**: Ensures deep key parity across all language files
- Used by: Config flow for localized labels, validation tests
- Pattern: `label = COMMON_LABELS["key"][lang]`

### pdf_generator.py - PDF Generation
Generates aviation compliance documents:
- **CAP1590BGenerator**: UK CAA cost-sharing declaration PDF
- Uses `fpdf2` library for PDF creation
- Stores output in `hass.config.path("www/hangar/")`
- Pattern: `generator.generate(output_path, pilot, aircraft, passengers, flight_details)`
- File naming: `{date}_{flight_type}_{airfield}.pdf`
- Cleanup: Managed by `manual_cleanup` service

### openweathermap.py - Weather API Integration
Provides professional weather data with robust caching:
- **OpenWeatherMapClient**: Client for OpenWeatherMap One Call API 3.0
- **Multi-level caching**: In-memory + persistent file-based caching
- **Rate limit protection**: Tracks API calls per day, warns at 950/1000 limit
- **Persistent cache directory**: `hass.config.path("hangar_assistant_cache/")`
- **Cache TTL**: Configurable (default: 10 minutes, matches OWM update frequency)
- **Data extraction methods**: `extract_current_weather()`, `extract_hourly_forecast()`, `extract_daily_forecast()`, `extract_minutely_forecast()`, `extract_alerts()`
- **Cache management**: `clear_cache()`, `get_cache_stats()`
- **Survives restarts**: Persistent cache protects against API limit breaches during system restarts
- Used by: Weather sensors, forecast sensors, alert sensors, AI briefing enrichment
- Pattern: 
  ```python
  client = OpenWeatherMapClient(api_key, hass, cache_enabled=True)
  data = await client.get_weather_data(latitude, longitude)
  current = client.extract_current_weather(data)
  ```

### notam.py - NOTAM Data Integration
Provides aviation NOTAM (Notice to Airmen) data with graceful degradation:
- **NOTAMClient**: Client for UK NATS PIB XML feed (https://pibs.nats.co.uk/operational/pibs/PIB.xml)
- **XML parsing**: ElementTree-based parsing of PIB format NOTAMs
- **Persistent caching**: JSON file cache with configurable retention (1-30 days)
- **Graceful degradation**: Uses stale cache indefinitely on network failures
- **Failure tracking**: Tracks consecutive failures in config entry for monitoring
- **Location filtering**: Filter by ICAO code or geographic proximity (Haversine distance)
- **Cache directory**: `hass.config.path("hangar_assistant_cache/notams.json")`
- **Scheduled updates**: Daily updates via `async_track_time_change` in `__init__.py`
- **Key methods**:
  - `fetch_notams()` → Returns `Tuple[List[Dict], bool]` (notams, is_stale)
  - `filter_by_location()` → Filter by ICAO or lat/lon with radius
  - `clear_cache()` → Manual cache removal
  - `get_cache_stats()` → Returns cache age, size, count
- **NOTAM structure**: Each NOTAM dict contains:
  - `id`: NOTAM identifier (e.g., "A0001/25")
  - `location`: ICAO code (e.g., "EGKA")
  - `category`: Type (AERODROME, AIRSPACE, NAVIGATION, etc.)
  - `start_time`: ISO datetime string
  - `end_time`: ISO datetime string
  - `text`: Human-readable NOTAM text
  - `q_code`: Q-code classification (optional)
  - `latitude`: Decimal degrees (optional)
  - `longitude`: Decimal degrees (optional)
- Used by: Airfield NOTAM sensors, AI briefing system
- Pattern:
  ```python
  client = NOTAMClient(hass, cache_days=7, entry=config_entry)
  notams, is_stale = await client.fetch_notams()
  filtered = client.filter_by_location(notams, icao="EGKA", latitude=51.3, longitude=-0.7, radius_nm=50)
  ```
- **Backward compatibility**: Sensors only created if NOTAM integration enabled in config

### hangar_helpers.py - Hangar Management & Backward Compatibility
Provides hangar-aware sensor fallback and aircraft-airfield resolution:
- **get_aircraft_airfield()**: Resolves airfield for aircraft with hangar → direct airfield → None priority
- **get_aircraft_hangar()**: Returns hangar config if aircraft assigned to hangar
- **get_hangar_sensor_value()**: Core fallback logic for environment sensors (hangar → airfield → global)
- **find_hangar_by_name()**: Locates hangar config by name
- **get_airfield_for_hangar()**: Gets airfield config for a hangar
- **get_hangar_temperature()**: Convenience function for temperature with full fallback chain
- **get_hangar_humidity()**: Convenience function for humidity with full fallback chain
- Used by: Sensors needing location-based data, migration logic, automation helpers
- Pattern:
  ```python
  from custom_components.hangar_assistant.utils.hangar_helpers import get_aircraft_airfield
  
  airfield = get_aircraft_airfield(aircraft_config, hangars, airfields)
  temp = get_hangar_sensor_value(hass, "temp_sensor", hangar, airfield, global_sensor)
  ```

### Brand Directory
Contains branding assets:
- Integration logo and icons for HACS/HA UI
- Used by Home Assistant for integration marketplace display
- Files: `icon.png`, `logo.png` (if present)

## Developer Workflow & Testing

### Unit Testing Best Practices
- **Mandatory Test Coverage**: For any code edits, new functions, or new classes, you MUST create or update corresponding unit tests. Tests must be added to the appropriate test file in the `tests/` directory.
- **Use Mocks, Not Real HA System**: Create unit tests with `unittest.mock` (MagicMock, patch) rather than requiring the full Home Assistant system. Mock `hass`, `states`, and `config_entries` as needed.
- **Mock Architecture Example**:
  ```python
  from unittest.mock import MagicMock
  mock_hass = MagicMock()
  mock_hass.states = MagicMock()
  mock_hass.states.get.return_value = MagicMock(state="15")
  sensor = DensityAltSensor(mock_hass, config, entry_data)
  ```
- **Avoid Integration Loader**: Do NOT use `hass.config_entries.flow.async_init()` or similar integration discovery features in unit tests—the integration may not be discoverable in test environments. Instead, instantiate flow handlers directly and mock their dependencies.
- **Property Patching**: Cannot patch class properties directly. Instead, create mock instances with properties set via `MagicMock` attributes (e.g., `mock_entry.data = {"key": "value"}`).
- **Timezone Awareness**: Use `homeassistant.util.dt.utcnow()` for timezone-aware datetimes in tests (not `datetime.utcnow()`).

### Test Documentation Standards

**CRITICAL PRINCIPLE**: Test code is read more often than written. Every test must clearly communicate its purpose, methodology, and validation criteria to future maintainers.

**All test modules, classes, functions, and fixtures must include comprehensive docstrings** following this format:

#### Test Module Docstrings
```python
"""Tests for <feature/component name>.

This module tests <high-level description of what's being tested> including:
- <Key test category 1>
- <Key test category 2>
- <Key test category 3>

Test Strategy:
    - <Approach taken (mocking, integration, etc.)>
    - <Key dependencies and how they're handled>
    - <Any special considerations>

Coverage:
    - <What aspects are covered>
    - <Edge cases tested>
    - <Known limitations if any>
"""
```

#### Test Class Docstrings
```python
class TestFeatureName:
    """Test suite for <specific feature or component>.
    
    Tests <detailed description of what this test suite validates>,
    including <key behaviors> and <edge cases>.
    
    Test Approach:
        - <Mocking strategy>
        - <Setup/teardown requirements>
        - <Shared fixtures used>
    
    Scenarios Covered:
        - <Scenario 1>
        - <Scenario 2>
        - <Scenario 3>
    """
```

#### Test Function Docstrings
```python
def test_specific_behavior():
    """Test that <specific behavior> works correctly when <conditions>.
    
    This test validates:
        - <What is being validated>
        - <Expected behavior>
        - <Edge case handling if applicable>
    
    Setup:
        - <Mock configuration>
        - <Test data created>
    
    Validation:
        - <What assertions verify>
        - <Why this matters>
    
    Expected Result:
        - <Clear statement of expected outcome>
    """
```

#### Test Fixture Docstrings
```python
@pytest.fixture
def mock_component():
    """Create a mock <component> for testing <feature>.
    
    Provides:
        - <What the fixture returns>
        - <Default configuration>
        - <Behavior characteristics>
    
    Used By:
        - <Test functions that use this fixture>
    
    Example:
        ```python
        def test_something(mock_component):
            result = mock_component.method()
            assert result == expected
        ```
    
    Returns:
        <Type and description of returned object>
    """
```

#### Key Test Documentation Principles

**Purpose Over Implementation:**
- Explain WHAT is being tested and WHY, not just HOW
- State expected behavior in human terms
- Describe the scenario being validated

**Clarity for Maintainers:**
- Assume reader is unfamiliar with the code
- Explain setup/mocking strategy explicitly
- Document why specific test data values are used

**Validation Documentation:**
- State what each assertion verifies
- Explain the significance of test outcomes
- Document edge cases and boundary conditions

**Examples:**

✓ **CORRECT - Comprehensive Test Documentation:**
```python
def test_density_altitude_calculation_high_temp():
    """Test density altitude calculation with high temperature conditions.
    
    This test validates the aviation density altitude formula:
    DA = 4000 + (120 * (T - 15)) feet
    
    Scenario:
        - Temperature: 30°C (significantly above ISA standard 15°C)
        - Expected high density altitude due to warm air
    
    Validation:
        - Asserts DA = 5800 feet (4000 + 120*(30-15))
        - Confirms formula accuracy for hot weather conditions
        - Verifies pilot will see degraded aircraft performance warning
    
    Expected Result:
        Density altitude of 5800 feet, indicating aircraft performance
        degradation of approximately 1800 feet above field elevation.
    """
    temp_celsius = 30
    expected_da = 5800
    
    result = calculate_density_altitude(temp_celsius)
    
    assert result == expected_da, \
        f"Expected DA {expected_da} for temp {temp_celsius}°C"
```

✗ **INCORRECT - Minimal Documentation:**
```python
def test_density_altitude():
    """Test density altitude."""
    result = calculate_density_altitude(30)
    assert result == 5800
```

✓ **CORRECT - Well-Documented Fixture:**
```python
@pytest.fixture
def mock_hass_with_weather_sensors():
    """Create a mock Home Assistant instance with weather sensor data.
    
    Provides:
        - Mock hass instance with state machine configured
        - Temperature sensor: 15°C (ISA standard)
        - Dew point sensor: 10°C (moderate humidity)
        - Pressure sensor: 1013.25 hPa (standard pressure)
    
    Used By:
        - test_weather_calculations
        - test_carb_icing_risk
        - test_density_altitude_sensor
    
    The temperature/dew point spread of 5°C represents moderate
    carburetor icing risk conditions, useful for testing safety alerts.
    
    Returns:
        MagicMock: Configured Home Assistant instance with weather sensors
    """
    mock_hass = MagicMock()
    mock_hass.states = MagicMock()
    
    # Configure temperature sensor
    temp_state = MagicMock()
    temp_state.state = "15"
    mock_hass.states.get.return_value = temp_state
    
    return mock_hass
```

✗ **INCORRECT - Minimal Fixture Documentation:**
```python
@pytest.fixture
def mock_hass():
    """Mock hass."""
    mock = MagicMock()
    return mock
```

#### Test Naming Conventions

Test function names must be descriptive and follow this pattern:
- `test_<feature>_<condition>_<expected_result>`
- Example: `test_carb_risk_cold_temp_high_humidity_returns_serious_risk`

**Examples:**

✓ **CORRECT - Descriptive Names:**
- `test_runway_selection_strong_crosswind_returns_most_aligned_runway`
- `test_cache_expired_data_triggers_api_refresh`
- `test_missing_sensor_data_falls_back_to_global_setting`

✗ **INCORRECT - Vague Names:**
- `test_runway`
- `test_cache_works`
- `test_sensor`

#### Documentation Completeness Checklist

Before committing test code, verify:
- [ ] Module docstring explains what component is tested and strategy used
- [ ] Test class docstrings describe scope and scenarios covered
- [ ] Test functions have docstrings explaining what, why, and expected outcome
- [ ] Fixtures document what they provide and why setup is configured that way
- [ ] Test names are descriptive and self-explanatory
- [ ] Complex assertions include comments explaining validation logic
- [ ] Edge cases are explicitly documented with reasoning

### Local Development & Testing
- **Development Environment**: Solutions are developed locally on the developer's machine.
- **Remote Testing**: Code is tested on a remote Home Assistant server before release to ensure real-world integration with actual HA instances.
- **Testing**: Local unit tests in `tests/` directory. Run with `pytest`.
  - Run all tests: `.venv/bin/pytest tests/`
  - Run with coverage: `.venv/bin/pytest tests/ --cov=custom_components/hangar_assistant`

### Test File Reference

| Test File | Purpose | Coverage |
|-----------|---------|----------|
| `test_formulas.py` | Pure Python aviation math (DA, cloud base, carb risk) | Formula accuracy, edge cases |
| `test_binary_sensor.py` | Binary sensor logic (safety alerts, warnings) | State determination, mocked dependencies |
| `test_sensor_coverage.py` | Sensor entity creation and attributes | All sensor types, device info, unique IDs |
| `test_sensor_setup_coverage.py` | Sensor platform setup flow | `async_setup_entry()`, entity registration |
| `test_sensor_unit_preference.py` | Unit conversion in sensors | Aviation vs SI units, preference handling |
| `test_sensor_caching.py` | Sensor state caching behavior | Performance optimization, cache invalidation |
| `test_config_flow.py` | Config flow user interactions | Form validation, data storage |
| `test_config_flow_coverage.py` | Config flow edge cases | Error handling, partial configs |
| `test_config_flow_init.py` | Options flow initialization | Flow handler setup without errors |
| `test_hangar_config_flow.py` | Hangar config flow and helpers | Hangar CRUD, sensor fallback, backward compat |
| `test_enhanced_logic.py` | Complex integration logic | Multi-sensor interactions, mocked HA system |
| `test_integration.py` | End-to-end integration tests | Full setup flow, entity coordination |
| `test_select_entities.py` | Select entity implementation | Dropdown options, state updates |
| `test_services.py` | Service handlers and registration | Service calls, parameter validation |
| `test_pdf_generator.py` | PDF generation functionality | CAP1590B output, file creation |
| `test_pdf_edge_cases.py` | PDF generation edge cases | Missing data, special characters |
| `test_unit_conversion.py` | Unit conversion utilities | `units.py` functions, preference system |
| `test_i18n_labels.py` | Translation label availability | COMMON_LABELS completeness |
| `test_languages.py` | Language pack validation | Deep key parity across all languages |
| `test_json_validation.py` | JSON file structure | Valid JSON, no duplicates/concatenation |
| `test_config_validation.py` | Config entry validation | Schema compliance, required fields |
| `test_input_validation.py` | User input sanitization | XSS prevention, type coercion |
| `test_error_handling.py` | Exception handling | Graceful degradation, error messages |
| `test_scenarios.py` | Real-world usage scenarios | Complete workflows, integration tests |
| `test_performance_margin.py` | Aircraft performance calculations | Margin of safety, ground roll adjustments |
| `test_runway_suitability.py` | Runway selection logic | Wind component calculations, suitability |
| `test_code_quality_validation.py` | Code quality checks | Complexity, async usage, clean imports |
| `test_notam_client.py` | NOTAM client functionality | XML parsing, caching, location filtering, graceful degradation |
| `test_integration_config_flow.py` | Integrations config flow | OWM/NOTAM settings, migration, backward compatibility |

### GitHub & Continuous Integration
- **Repository**: All code changes are pushed to GitHub repository.
- **GitHub Actions CI/CD**: Automated workflows run on every commit/PR:
  - **Code Validation** (`validate.yml`): Runs Hassfest validation and HACS compliance checks.
  - **Linting**: flake8 and mypy type checking on all Python files.
  - **Release Tests**: Automated tests execute against the code to verify functionality.
- **Deployment**: GitHub Actions handles automated releases and package distribution to HACS (Home Assistant Community Store).
- **Version Management**: Follows `YYYYNN.V.H` format (e.g., `2601.1.0`). GitHub Actions tags releases and creates release notes.

### New Sensor Workflow
1. Subclass `HangarSensorBase`.
2. Implement `name` property and logic.
3. Add to `async_setup_entry` in `sensor.py`.
4. Write unit tests in `tests/` covering the new functionality.
5. Run local tests: `.venv/bin/pytest tests/`
6. Run flake8 and mypy for code quality.
7. Deploy to remote Home Assistant server for integration testing.
8. Push to GitHub and let CI/CD pipeline validate.

## Error Detection & Prevention

### Type Checking (MyPy)
The project uses **mypy** for static type checking. This catches many errors before runtime:

**Run locally before committing:**
```bash
.venv/bin/mypy custom_components/hangar_assistant --ignore-missing-imports
```

**Common issues caught by mypy:**
- Assigning to read-only properties (e.g., `self.config_entry = value` when it's a property)
- Type mismatches in function arguments/returns
- Accessing non-existent attributes on objects
- None vs non-None type violations

**Key pattern - Home Assistant OptionsFlow:**
The `OptionsFlow` base class from Home Assistant defines `config_entry` as a read-only property. Do NOT try to assign to it directly:

❌ WRONG:
```python
def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
    super().__init__()
    self.config_entry = config_entry  # ERROR: property has no setter
```

✓ CORRECT:
```python
def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
    super().__init__()
    # Store as private attribute if you need to reference it
    self._config_entry = config_entry
```

### Linting (Flake8)
Catches syntax errors, undefined names, and code complexity issues:

**Run locally:**
```bash
.venv/bin/flake8 custom_components/hangar_assistant --count --select=E9,F63,F7,F82 --show-source --statistics
```

### Unit Tests
Tests catch logical errors and integration issues:

**Run locally:**
```bash
.venv/bin/pytest tests/ -v --strict-warnings
```

**CRITICAL: Test warnings are considered failures.** All tests must pass with zero warnings. Common warning sources:
- Unawaited coroutines (fix async mocking properly)
- ResourceWarnings (ensure proper cleanup in async tests)
- DeprecationWarnings (update deprecated API usage immediately)
- RuntimeWarnings (fix async context manager mocking)

If tests show warnings, the test suite is considered failing even if all assertions pass.

**Best practices for config flow testing:**
- Mock the `ConfigEntry` and `HA` objects properly
- Test that `__init__` completes without errors
- Verify that data methods (`_entry_data()`, `_entry_options()`) work correctly
- Test with partial/missing config to ensure graceful handling

Example:
```python
def test_options_flow_init():
    """Test OptionsFlowHandler initialization without errors."""
    mock_entry = MagicMock(spec=config_entries.ConfigEntry)
    mock_entry.data = {"airfields": []}
    mock_entry.options = {}
    
    # Should initialize without raising AttributeError
    handler = HangarOptionsFlowHandler(mock_entry)
    assert handler._config_entry is mock_entry
```

### Pre-commit Validation Checklist
Before pushing code, run this locally:

```bash
# 1. Type checking
.venv/bin/mypy custom_components/hangar_assistant --ignore-missing-imports

# 2. Syntax & quality
.venv/bin/flake8 custom_components/hangar_assistant --count --select=E9,F63,F7,F82 --show-source --statistics

# 3. All tests (warnings treated as failures)
.venv/bin/pytest tests/ -v --strict-warnings

# 4. Complex checks
.venv/bin/flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127
```

### CI/CD Pipeline
The GitHub Actions pipeline runs automatically on every commit and performs:
1. **Hassfest**: Official Home Assistant validation
2. **Flake8**: Code quality checks
3. **MyPy**: Type checking (catches property assignment errors)
4. **Pytest**: All unit tests must pass

**If CI/CD fails after your changes:**
- Check the specific error message in GitHub Actions logs
- Run the same check locally to reproduce
- Fix locally and verify with tools above
- Push corrected code

### Home Assistant API Patterns to Watch
These commonly cause runtime errors if not properly typed/used:

1. **Read-only properties**: Check HA documentation for `@property` vs `@property.setter`
2. **Config entry data**: Always use `.get()` with defaults, never direct dictionary access
3. **State machine access**: Handle `None` and "unavailable" states gracefully
4. **Async functions**: All `async_*` methods must be awaited in async context
5. **Event listeners**: Remember to call `async_on_remove()` to prevent memory leaks

### Code Quality & SonarLint Standards

To maintain a high-quality codebase and pass automated analysis, follow these rules:

- **Refactor for Complexity**: Keep functions focused. If a function's cognitive complexity exceeds 15 (e.g., deeply nested logic, many branches), refactor it into smaller, descriptive private methods.
- **Clean Async Usage**:
    - Only use the `async` keyword if the function contains an `await` statement.
    - Never perform blocking I/O (like `open()`, `os.*`, or `yaml.load()`) directly in an `async` function. Always wrap them in `hass.async_add_executor_job`.
- **Unused Parameters**: If a required callback parameter (like `now` in `async_track_time_change` or `call` in service handlers) is not used, prefix it with an underscore (e.g., `_now`, `_call`) or omit it if the API allows.
- **Exception Handling**:
    - Avoid catching redundant exceptions (e.g., don't catch `OSError` and `FileNotFoundError` in the same block, as `FileNotFoundError` is a subclass of `OSError`).
    - Use specific exceptions rather than a broad `Exception` where possible.
- **Clean Imports**: Remove any unused imports. If an import is only needed for type checking, use `if TYPE_CHECKING:`.

### Localization & Translations Guidance

To ensure a consistent, high-quality multilingual UI, follow these rules:

- **English is the source of truth**: Add or change UI strings first in `custom_components/hangar_assistant/strings.json` and `translations/en.json`. Treat English as the default pack.
- **Complete translations in all packs**: Mirror every English key to `translations/de.json`, `translations/es.json`, and `translations/fr.json` with fully translated values. Do **not** leave English placeholders in non-English packs once translations exist.
- **No duplicate or concatenated JSON**: Each translation file must contain a single JSON object only. Do not paste the English file beneath or alongside a translation; validate with `pytest tests/test_json_validation.py -q` after edits.
- **Fallback only when necessary**: If a precise translation truly isn’t available, you may temporarily copy the English string—but track and replace it with a proper translation as soon as possible. Document any temporary English entries in the PR description.
- **No hardcoded text**: Do not hardcode user-facing strings in Python or YAML. Use the HA translation framework (strings.json + translations/*.json) for config flows and entity names.
- **Deep key completeness**: Ensure each non-English pack contains all keys present in the English pack (including nested `options.step.*.*.data` and `menu_options`). A unit test must verify deep key parity across all packs.
- **When generating new content with AI**: Default to English phrasing, then translate into the available language packs where possible. Keep aviation terminology clear and consistent across languages.
- **Review and QA**: After changing translations, run `pytest` to confirm deep key completeness and that config flows render without placeholders.

### Automated Translation via Background Agent

**When to use automated translation:**
- Adding new translation keys across multiple language files
- Updating existing translations after English source changes
- Completing partial translations with missing keys
- Initial translation of new features

**Pattern for invoking translation agent:**

Use `runSubagent` tool to delegate translation work to a background agent. The agent should:
1. Read the English source (`translations/en.json`)
2. Identify missing or outdated keys in target language files
3. Translate keys to German, Spanish, and French
4. Update translation files with proper JSON structure
5. Validate with `pytest tests/test_json_validation.py` and `pytest tests/test_languages.py`

**Example agent invocation:**
```python
# When you need translations updated
await runSubagent(
    description="Translate new keys to all languages",
    prompt="""
    Task: Update all translation files with new English keys
    
    1. Read translations/en.json to get the source English text
    2. Identify new keys that need translation:
       - Compare en.json with de.json, es.json, fr.json
       - Find keys present in en.json but missing in other files
    
    3. Translate the missing keys:
       - German (de.json): Professional aviation German
       - Spanish (es.json): Professional aviation Spanish  
       - French (fr.json): Professional aviation French
       - Preserve aviation terminology (ICAO codes, units, etc.)
       - Keep formatting consistent (e.g., "(e.g., EGHP)")
    
    4. Update each translation file:
       - Add new keys in the same nested structure as en.json
       - Maintain alphabetical order within each section
       - Preserve existing translations (only add/update changed keys)
    
    5. Validate changes:
       - Run: pytest tests/test_json_validation.py -q
       - Run: pytest tests/test_languages.py -q
       - Ensure all tests pass before completing
    
    Context:
    - English source: custom_components/hangar_assistant/translations/en.json
    - Target files: translations/de.json, translations/es.json, translations/fr.json
    - Aviation context: Use standard aviation terminology across languages
    - Quality standard: Professional pilot-facing translations
    
    Expected Result:
    All translation files updated with new keys, tests passing, ready for commit.
    """
)
```

**Translation agent requirements:**
- **Aviation context awareness**: Agent must understand aviation terminology and preserve it correctly
- **JSON structure preservation**: Maintain deep nesting, alphabetical order, no duplicates
- **Quality validation**: Run tests before completing (json_validation, languages, deep key parity)
- **Existing translation preservation**: Only add/update changed keys, don't replace entire files
- **Professional tone**: Translations must match the professional pilot-facing style

**Validation checklist after automated translation:**
- [ ] All tests pass: `pytest tests/test_json_validation.py tests/test_languages.py -q`
- [ ] Deep key parity verified (all en.json keys present in de/es/fr)
- [ ] No English placeholders in non-English files (except documented temporary ones)
- [ ] Aviation terminology preserved correctly in all languages
- [ ] JSON structure valid (no duplicates, proper nesting)
- [ ] Alphabetical order maintained within sections

**When NOT to use automated translation:**
- ❌ Nuanced error messages requiring cultural context
- ❌ Marketing copy or documentation (use feature docs in English only)
- ❌ Aviation regulatory text requiring legal precision (keep English, link to official translations)
- ❌ Initial feature development (translate manually to ensure accuracy first time)

**Best practices:**
- Review agent translations for aviation accuracy before committing
- Test config flows in each language after automated translation
- Document any aviation terms that should NOT be translated
- Use agent for bulk updates, manual review for critical user-facing text
