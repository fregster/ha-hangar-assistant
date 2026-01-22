# CheckWX API Integration Plan

**Document Version**: 1.0  
**Date**: 21 January 2026  
**Status**: Planning Phase  
**Priority**: ⭐⭐⭐⭐⭐ CRITICAL

---

## Table of Contents
- [Executive Summary](#executive-summary)
- [CheckWX API Overview](#checkwx-api-overview)
- [Integration Scope](#integration-scope)
- [Technical Architecture](#technical-architecture)
- [Configuration Design](#configuration-design)
- [Implementation Phases](#implementation-phases)
- [Caching Strategy](#caching-strategy)
- [Entity Design](#entity-design)
- [Backward Compatibility](#backward-compatibility)
- [Testing Strategy](#testing-strategy)
- [Success Metrics](#success-metrics)

---

## Executive Summary

CheckWX provides professional aviation weather data (METAR, TAF, Station Info) with excellent API design and a **FREE tier** (3,000 requests/day) that makes it ideal for Hangar Assistant users. This integration would provide **official aviation weather format** data that pilots expect and trust.

### Why CheckWX?

**✅ Pros:**
- **FREE tier**: 3,000 daily requests (sufficient for most users)
- **Aviation-standard format**: METAR/TAF are industry standards
- **Decoded data**: JSON-formatted weather data (no complex parsing needed)
- **Multiple endpoints**: Station info, nearest weather, radius searches
- **Clean API**: Well-documented, REST-based, standard HTTP codes
- **Global coverage**: Any ICAO code worldwide
- **Flight category**: Automatic VFR/MVFR/IFR/LIFR classification
- **Sunrise/Sunset**: Built-in dawn/dusk/sunrise/sunset data per station

**⚠️ Considerations:**
- **Rate limits**: 3,000/day free tier (cache aggressively)
- **Requires API key**: Users must register (free)
- **Redundancy**: Overlaps with OpenWeatherMap (but aviation-specific)

### Strategic Value

1. **Pilot Trust**: METAR/TAF are the official aviation weather standards
2. **Compliance**: Required for professional flight operations
3. **Differentiation**: Aviation-specific vs. consumer weather APIs
4. **Cost-Effective**: FREE tier covers typical use cases
5. **Network Effect**: Free tier enables broad adoption

---

## CheckWX API Overview

### Pricing Tiers

| Plan | Cost | Daily Requests | Best For |
|------|------|---------------|----------|
| **Personal** | **FREE** | **3,000** | Home users, single aircraft operations |
| Professional | $7/mo | 50,000 | Flight schools, small operators |
| Enterprise | $30/mo | 500,000 | Commercial operations |

**Recommendation**: Target FREE tier initially, allow upgrade path for power users.

### Available Endpoints

#### 1. **Station Data** (7 endpoints)
- `GET /station/{icao}` - Get station info by ICAO
- `GET /station/{icao}/nearest` - Find nearest station
- `GET /station/{icao}/radius/{radius}` - Stations within radius
- `GET /station/lat/{lat}/lon/{lon}` - Nearest to coordinates
- `GET /station/lat/{lat}/lon/{lon}/radius/{radius}` - Radius from coordinates
- `GET /station/{icao}/datetime` - Local/UTC time and timezone info
- `GET /station/{icao}/suntimes` - Sunrise/sunset/dawn/dusk

**Data includes:**
- ICAO, IATA, name, location, city, country
- Latitude/longitude (decimal + degrees/minutes/seconds)
- Elevation (feet + meters)
- Airport type (Airport, Heliport, Seaplane Base, etc.)
- Magnetic variation
- Status (Operational/Closed)

#### 2. **METAR Data** (10 endpoints)
- `GET /metar/{icao}` - Plain text METAR
- `GET /metar/{icao}/decoded` - **JSON-decoded METAR**
- `GET /metar/{icao}/nearest[/decoded]` - Nearest METAR
- `GET /metar/{icao}/radius/{radius}[/decoded]` - METARs within radius
- `GET /metar/lat/{lat}/lon/{lon}[/decoded]` - Nearest to coordinates
- `GET /metar/lat/{lat}/lon/{lon}/radius/{radius}[/decoded]` - Radius from coordinates

**Decoded METAR includes:**
- Temperature (Celsius + Fahrenheit)
- Dew point (Celsius + Fahrenheit)
- Barometer (hPa, mb, inHg, kPa)
- Wind (speed in kts/kph/mph/mps, direction, gusts)
- Visibility (miles + meters)
- Clouds (layers with base altitude AGL)
- **Flight Category** (VFR, MVFR, IFR, LIFR)
- Humidity percentage
- Ceiling (feet + meters AGL)
- Weather conditions (rain, snow, fog, etc.)
- Observed timestamp (ISO format)
- Raw METAR text

#### 3. **TAF Data** (10 endpoints)
- `GET /taf/{icao}` - Plain text TAF
- `GET /taf/{icao}/decoded` - **JSON-decoded TAF**
- `GET /taf/{icao}/nearest[/decoded]` - Nearest TAF
- `GET /taf/{icao}/radius/{radius}[/decoded]` - TAFs within radius
- `GET /taf/lat/{lat}/lon/{lon}[/decoded]` - Nearest to coordinates
- `GET /taf/lat/{lat}/lon/{lon}/radius/{radius}[/decoded]` - Radius from coordinates

**Decoded TAF includes:**
- Forecast periods (from/to timestamps)
- Change indicators (FM, BECMG, TEMPO, PROB)
- Wind forecasts per period
- Visibility forecasts
- Cloud forecasts per period
- Weather conditions per period
- Icing forecasts (altitude, intensity)
- Turbulence forecasts (altitude, intensity)
- Raw TAF text

#### 4. **Additional Endpoints** (mentioned but not detailed in docs)
- AIRMETs
- SIGMETs
- PIREPs (Pilot Reports)
- NOTAMs (may overlap with existing NATS integration)

---

## Integration Scope

### Phase 1: Core Aviation Weather (Recommended for Initial Implementation)

**Priority**: ⭐⭐⭐⭐⭐

**Scope:**
1. **METAR Integration** (decoded)
   - Per-airfield METAR data
   - Automatic updates every 15-30 minutes
   - Multi-level caching (memory + persistent)
   
2. **TAF Integration** (decoded)
   - Per-airfield TAF forecast
   - Update every 6 hours
   - Parsed forecast periods
   
3. **Station Info** (one-time)
   - Auto-populate airfield configuration
   - Sunrise/sunset/dawn/dusk data
   - Timezone information

**Effort Estimate**: 4-5 days

### Phase 2: Enhanced Features (Future)

**Priority**: ⭐⭐⭐

**Scope:**
1. Nearby weather (radius searches)
2. AIRMET/SIGMET integration
3. PIREP (Pilot Reports)
4. Cross-country route weather

**Effort Estimate**: 3-4 days

---

## Technical Architecture

### Client Module

**Location**: `custom_components/hangar_assistant/utils/checkwx_client.py`

```python
"""CheckWX API Client for aviation weather data.

Provides METAR, TAF, and station information with multi-level caching
and rate limit protection.
"""

import asyncio
import aiohttp
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from collections import OrderedDict
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util


class CheckWXClient:
    """Client for CheckWX Aviation Weather API.
    
    Features:
        - METAR/TAF decoded JSON data
        - Station information lookup
        - Multi-level caching (memory + persistent)
        - Rate limit tracking (3,000/day free tier)
        - Graceful degradation (use stale cache on API failure)
    
    Rate Limits:
        - Free tier: 3,000 requests/day (resets 00:00 UTC)
        - Recommended cache TTL: 15 min for METAR, 6 hours for TAF
    """
    
    BASE_URL = "https://api.checkwx.com"
    
    def __init__(
        self,
        api_key: str,
        hass: HomeAssistant,
        cache_enabled: bool = True,
        metar_cache_minutes: int = 15,
        taf_cache_minutes: int = 360,  # 6 hours
    ):
        """Initialize CheckWX client."""
        self._api_key = api_key
        self._hass = hass
        self._cache_enabled = cache_enabled
        self._metar_cache_ttl = timedelta(minutes=metar_cache_minutes)
        self._taf_cache_ttl = timedelta(minutes=taf_cache_minutes)
        
        # Memory cache (session-level, LRU eviction)
        self._memory_cache: OrderedDict[str, tuple] = OrderedDict()
        self._max_memory_entries = 100
        
        # Rate limit tracking
        self._daily_requests = 0
        self._last_reset = dt_util.utcnow().date()
        self._rate_limit_warned = False
        
        # Persistent cache directory
        self._cache_dir = hass.config.path("hangar_assistant_cache")
    
    async def get_metar(
        self,
        icao: str,
        decoded: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Fetch METAR for ICAO code.
        
        Args:
            icao: ICAO airport code (e.g., "KJFK")
            decoded: Return decoded JSON data (True) or raw text (False)
        
        Returns:
            Decoded METAR data dict or None if unavailable
            
        Example:
            {
                "icao": "KJFK",
                "temperature": {"celsius": 0, "fahrenheit": 32},
                "dewpoint": {"celsius": -7, "fahrenheit": 19},
                "wind": {"degrees": 190, "speed_kts": 18, "gust_kts": 31},
                "flight_category": "VFR",
                "observed": "2026-01-21T19:51:00",
                "raw_text": "METAR KJFK 211951Z ...",
                ...
            }
        """
        
    async def get_taf(
        self,
        icao: str,
        decoded: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Fetch TAF for ICAO code.
        
        Args:
            icao: ICAO airport code
            decoded: Return decoded JSON data (True) or raw text (False)
        
        Returns:
            Decoded TAF data dict with forecast periods
        """
        
    async def get_station_info(self, icao: str) -> Optional[Dict[str, Any]]:
        """Fetch station information for ICAO code.
        
        Args:
            icao: ICAO airport code
        
        Returns:
            Station data including location, elevation, coordinates
        """
        
    async def get_sunrise_sunset(self, icao: str) -> Optional[Dict[str, Any]]:
        """Fetch sunrise/sunset times for ICAO code.
        
        Args:
            icao: ICAO airport code
        
        Returns:
            {
                "local": {
                    "sunrise": "07:15:00",
                    "sunset": "16:45:00",
                    "dawn": "06:42:00",
                    "dusk": "17:18:00"
                },
                "utc": {...},
                "timezone": {"tzid": "America/New_York", ...}
            }
        """
        
    async def _make_request(
        self,
        endpoint: str,
        cache_key: str,
        cache_ttl: timedelta
    ) -> Optional[Dict[str, Any]]:
        """Make API request with caching and rate limit protection.
        
        Flow:
            1. Check memory cache
            2. Check persistent cache
            3. Make API call (if cache miss/expired)
            4. Update both caches
            5. Track rate limits
        """
        
    def _check_rate_limit(self) -> bool:
        """Check if approaching rate limit (warn at 2,700/3,000)."""
        # Reset counter at 00:00 UTC
        today = dt_util.utcnow().date()
        if today > self._last_reset:
            self._daily_requests = 0
            self._last_reset = today
            self._rate_limit_warned = False
        
        # Warn at 90% of free tier limit
        if self._daily_requests >= 2700 and not self._rate_limit_warned:
            _LOGGER.warning(
                "CheckWX API: Approaching rate limit (%d/3000 requests today). "
                "Consider upgrading or increasing cache TTL.",
                self._daily_requests
            )
            self._rate_limit_warned = True
        
        return self._daily_requests < 3000
    
    def clear_cache(self, icao: Optional[str] = None) -> None:
        """Clear cache for specific ICAO or all."""
        
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics and rate limit info."""
```

---

## Configuration Design

### Integration Configuration Structure

**Location**: `entry.data["integrations"]["checkwx"]`

```python
entry.data["integrations"] = {
    "checkwx": {
        "enabled": bool,                    # Master toggle
        "api_key": str,                     # Password field, required
        
        # Cache settings
        "metar_cache_minutes": int,         # Default: 15 minutes
        "taf_cache_minutes": int,           # Default: 360 minutes (6 hours)
        "cache_enabled": bool,              # Default: True
        
        # Update intervals
        "metar_update_interval": int,       # Minutes between updates (default: 30)
        "taf_update_interval": int,         # Minutes between updates (default: 360)
        
        # Features
        "use_decoded": bool,                # Use decoded JSON (True) or raw text (False)
        "auto_populate_stations": bool,     # Auto-fill airfield info from station data
        
        # Rate limit tracking (system-managed)
        "daily_requests": int,              # Requests today
        "last_reset": str,                  # Last rate limit reset (ISO date)
    }
}
```

### Per-Airfield Configuration

**Location**: `entry.data["airfields"][n]`

```python
airfield = {
    "name": "Popham",
    "icao": "EGHP",  # REQUIRED for CheckWX integration
    
    # CheckWX-specific settings (optional, inherits from global if not set)
    "checkwx_enabled": bool,            # Override global enable (default: use global)
    "weather_data_source": str,         # "sensors", "checkwx", "owm", "hybrid"
    "use_checkwx_metar": bool,          # Create METAR sensor (default: True if enabled)
    "use_checkwx_taf": bool,            # Create TAF sensor (default: True if enabled)
}
```

### Default Values (Backward Compatibility)

```python
DEFAULT_CHECKWX_CONFIG = {
    "enabled": False,  # Opt-in for new installs
    "metar_cache_minutes": 15,
    "taf_cache_minutes": 360,
    "cache_enabled": True,
    "metar_update_interval": 30,
    "taf_update_interval": 360,
    "use_decoded": True,
    "auto_populate_stations": True,
}
```

---

## Implementation Phases

### Phase 1.1: Core Client (Day 1-2)

**Tasks:**
1. Create `utils/checkwx_client.py`
2. Implement API wrapper methods
3. Implement memory cache (OrderedDict LRU)
4. Implement persistent cache (JSON files)
5. Rate limit tracking
6. Error handling and graceful degradation

**Tests:**
- `test_checkwx_client.py` (mock API responses)
- Test cache hit/miss scenarios
- Test rate limit warnings
- Test stale cache fallback

### Phase 1.2: Config Flow Integration (Day 2-3)

**Tasks:**
1. Add CheckWX section to Integrations config menu
2. API key password field
3. Cache/update interval sliders
4. Per-airfield enable/disable toggles
5. Migration: preserve existing weather data sources

**Tests:**
- `test_integration_config_flow.py` (update existing tests)
- Test backward compatibility (existing configs work)
- Test migration (old → new format)

### Phase 1.3: METAR Sensors (Day 3-4)

**Tasks:**
1. Create `MetarSensor` class in `sensor.py`
2. Extract decoded METAR fields to sensor attributes
3. State: Flight category (VFR/MVFR/IFR/LIFR)
4. Attributes: temperature, dew point, wind, visibility, clouds, etc.
5. Update loop (every 30 min default)

**Sensors Created:**
```python
sensor.{airfield}_metar              # Main METAR sensor
  state: "VFR"  # Flight category
  attributes:
    temperature_celsius: 0
    temperature_fahrenheit: 32
    dewpoint_celsius: -7
    dewpoint_fahrenheit: 19
    wind_degrees: 190
    wind_speed_kts: 18
    wind_gust_kts: 31
    visibility_miles: 10.0
    barometer_hpa: 1028.0
    clouds: [{"code": "FEW", "base_feet_agl": 3600}, ...]
    humidity_percent: 60
    observed: "2026-01-21T19:51:00Z"
    raw_metar: "METAR KJFK 211951Z ..."
    icao: "KJFK"
```

**Tests:**
- `test_checkwx_sensors.py`
- Test sensor state and attributes
- Test update logic
- Test fallback behavior (API failure → stale cache)

### Phase 1.4: TAF Sensors (Day 4-5)

**Tasks:**
1. Create `TafSensor` class in `sensor.py`
2. Extract decoded TAF forecast periods
3. State: Overall forecast validity period
4. Attributes: Array of forecast periods with conditions

**Sensors Created:**
```python
sensor.{airfield}_taf                # Main TAF sensor
  state: "Valid 21/18:00Z to 23/00:00Z"
  attributes:
    issued: "2026-01-21T17:22:00Z"
    valid_from: "2026-01-21T18:00:00Z"
    valid_to: "2026-01-23T00:00:00Z"
    forecast_periods: [
      {
        "from": "2026-01-21T18:00:00Z",
        "to": "2026-01-21T19:00:00Z",
        "wind": {"degrees": 210, "speed_kts": 11},
        "visibility_miles": 10.0,
        "clouds": [{"code": "SCT", "base_feet_agl": 15000}]
      },
      ...
    ]
    raw_taf: "TAF KJFK 211722Z ..."
    icao: "KJFK"
```

**Tests:**
- Test TAF parsing
- Test forecast period extraction
- Test change indicators (FM, BECMG, TEMPO)

### Phase 1.5: Station Auto-Population (Day 5)

**Tasks:**
1. Service: `hangar_assistant.populate_airfield_from_icao`
2. Fetch station data when airfield added
3. Auto-fill: name, location, elevation, lat/lon, timezone
4. Optional: Sunrise/sunset sensors

**Service:**
```yaml
service: hangar_assistant.populate_airfield_from_icao
data:
  icao: "EGHP"
  overwrite_existing: false  # Don't overwrite user edits
```

**Tests:**
- Test service call
- Test data population
- Test overwrite protection

---

## Caching Strategy

### Critical Requirements

**MUST implement aggressive caching due to 3,000/day rate limit:**

- **3,000 requests/day** = 125 requests/hour = ~2 requests/minute
- **Typical user**: 2-5 airfields × 2 data types (METAR + TAF) = 4-10 requests every 30 min
- **Without caching**: Exceeds limit quickly during restarts/reloads

### Cache Design

#### Memory Cache (Session-Level)
- **Purpose**: Fast access, prevent redundant API calls in same session
- **Structure**: `OrderedDict` for LRU eviction
- **Max entries**: 100 (limit memory usage)
- **TTL**: 15 min (METAR), 360 min (TAF)
- **Eviction**: LRU when limit reached

#### Persistent Cache (Survives Restarts)
- **Purpose**: Protect against rate limit breaches during HA restarts
- **Location**: `hass.config.path("hangar_assistant_cache/checkwx/")`
- **Format**: JSON files per ICAO/data type
  - `checkwx/metar_{icao}.json`
  - `checkwx/taf_{icao}.json`
  - `checkwx/station_{icao}.json`
- **TTL**: Same as memory cache
- **Cleanup**: Remove files older than 7 days

#### Cache Lookup Order

```python
def _get_data(self, cache_key: str, cache_ttl: timedelta):
    # 1. Check memory cache
    if cache_key in self._memory_cache:
        data, timestamp = self._memory_cache[cache_key]
        if (utcnow() - timestamp) < cache_ttl:
            return data
    
    # 2. Check persistent cache
    cached_file = self._cache_dir / f"{cache_key}.json"
    if cached_file.exists():
        data, timestamp = read_cache_file(cached_file)
        if (utcnow() - timestamp) < cache_ttl:
            # Populate memory cache
            self._memory_cache[cache_key] = (data, timestamp)
            return data
    
    # 3. Make API call
    if self._check_rate_limit():
        data = await self._api_call(endpoint)
        self._cache_data(cache_key, data)
        return data
    
    # 4. Rate limit exceeded - use stale cache
    _LOGGER.warning("Rate limit exceeded, using stale cache")
    return self._get_stale_cache(cache_key)
```

### Cache Invalidation

**Automatic:**
- TTL expiry (15 min METAR, 6 hours TAF)
- Daily rate limit reset (00:00 UTC)

**Manual:**
- Service: `hangar_assistant.clear_checkwx_cache`
- Config flow: "Clear Cache" button

---

## Entity Design

### Sensor: METAR (`sensor.{airfield}_metar`)

**Platform**: `sensor.py`

**Class**: `CheckWXMetarSensor(HangarSensorBase)`

**State**: Flight category (VFR, MVFR, IFR, LIFR)

**Attributes**:
```python
{
    "icao": "KJFK",
    "observed": "2026-01-21T19:51:00Z",
    "age_minutes": 5,
    
    # Temperature
    "temperature_celsius": 0,
    "temperature_fahrenheit": 32,
    "dewpoint_celsius": -7,
    "dewpoint_fahrenheit": 19,
    "humidity_percent": 60,
    
    # Wind
    "wind_degrees": 190,
    "wind_speed_kts": 18,
    "wind_speed_kph": 33,
    "wind_gust_kts": 31,
    
    # Pressure
    "barometer_hpa": 1028.0,
    "barometer_inhg": 30.35,
    
    # Visibility
    "visibility_miles": 10.0,
    "visibility_meters": 9999,
    
    # Clouds
    "ceiling_feet": 25000,
    "clouds": [
        {"code": "FEW", "text": "Few", "base_feet_agl": 3600},
        {"code": "BKN", "text": "Broken", "base_feet_agl": 25000}
    ],
    
    # Conditions
    "conditions": [],  # Array of weather conditions (rain, fog, etc.)
    
    # Raw data
    "raw_metar": "METAR KJFK 211951Z 19018G31KT ...",
    
    # Data source
    "source": "checkwx",
    "cache_hit": true
}
```

**Device Info**: Links to airfield device

**Unique ID**: `{airfield_slug}_checkwx_metar`

### Sensor: TAF (`sensor.{airfield}_taf`)

**Platform**: `sensor.py`

**Class**: `CheckWXTafSensor(HangarSensorBase)`

**State**: Validity period (e.g., "Valid 21/18Z - 23/00Z")

**Attributes**:
```python
{
    "icao": "KJFK",
    "issued": "2026-01-21T17:22:00Z",
    "valid_from": "2026-01-21T18:00:00Z",
    "valid_to": "2026-01-23T00:00:00Z",
    "age_minutes": 120,
    
    # Forecast periods
    "forecast_periods": [
        {
            "from": "2026-01-21T18:00:00Z",
            "to": "2026-01-21T19:00:00Z",
            "change_indicator": null,
            "wind": {
                "degrees": 210,
                "speed_kts": 11,
                "gust_kts": null
            },
            "visibility_miles": 10.0,
            "clouds": [
                {"code": "SCT", "text": "Scattered", "base_feet_agl": 15000}
            ],
            "conditions": []
        },
        {
            "from": "2026-01-21T19:00:00Z",
            "to": "2026-01-22T04:00:00Z",
            "change_indicator": {"code": "FM", "text": "From"},
            "wind": {
                "degrees": 190,
                "speed_kts": 15,
                "gust_kts": 23
            },
            "visibility_miles": 10.0,
            "clouds": [
                {"code": "BKN", "text": "Broken", "base_feet_agl": 15000}
            ],
            "conditions": []
        }
        // ... more periods
    ],
    
    # Raw data
    "raw_taf": "TAF KJFK 211722Z 2118/2224 21011KT ...",
    
    # Data source
    "source": "checkwx",
    "cache_hit": true
}
```

**Device Info**: Links to airfield device

**Unique ID**: `{airfield_slug}_checkwx_taf`

### Binary Sensor: Flight Category Alert (`binary_sensor.{airfield}_flight_category_alert`)

**Platform**: `binary_sensor.py`

**Class**: `FlightCategoryAlertSensor(BinarySensorEntity)`

**State**: `on` if flight category is IFR or LIFR, `off` if VFR/MVFR

**Attributes**:
```python
{
    "flight_category": "IFR",
    "visibility_miles": 2.5,
    "ceiling_feet": 800,
    "message": "IFR conditions: Visibility 2.5 miles, Ceiling 800 feet"
}
```

**Device Class**: `safety`

**Unique ID**: `{airfield_slug}_flight_category_alert`

---

## Backward Compatibility

### CRITICAL Requirements

**✅ Existing installations must NOT break:**

1. **Default to disabled**: CheckWX integration is opt-in
2. **Preserve existing weather sources**: If user has OWM or sensors configured, continue using them
3. **No forced migrations**: Old config structure remains valid
4. **Graceful degradation**: If CheckWX fails, fall back to existing data sources
5. **No required fields**: ICAO code is optional (only needed for CheckWX)

### Migration Strategy

```python
async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config to new structure."""
    
    # Add CheckWX config if not present
    if "integrations" not in entry.data:
        entry.data["integrations"] = {}
    
    if "checkwx" not in entry.data["integrations"]:
        entry.data["integrations"]["checkwx"] = DEFAULT_CHECKWX_CONFIG.copy()
    
    # Add ICAO field to airfields (if not present)
    for airfield in entry.data.get("airfields", []):
        if "icao" not in airfield:
            airfield["icao"] = None  # User can populate later
    
    hass.config_entries.async_update_entry(entry, data=entry.data)
    return True
```

### Config Flow Additions

**New Menu Option**: "Aviation Weather (CheckWX)"

**Fields**:
- API Key (password, required to enable)
- METAR Cache Minutes (slider, 10-60, default 15)
- TAF Cache Minutes (slider, 60-720, default 360)
- METAR Update Interval (slider, 15-120, default 30)
- TAF Update Interval (slider, 180-720, default 360)
- Auto-Populate Station Data (toggle, default on)

**Per-Airfield**:
- ICAO Code (text, required for CheckWX)
- Use CheckWX for METAR (toggle, inherits from global if not set)
- Use CheckWX for TAF (toggle, inherits from global if not set)

---

## Testing Strategy

### Unit Tests

**File**: `tests/test_checkwx_client.py`

**Coverage**:
- Client initialization
- API request mocking
- Cache hit/miss scenarios
- Rate limit tracking
- Error handling (HTTP 401, 429, 500)
- Stale cache fallback
- Data extraction methods

**File**: `tests/test_checkwx_sensors.py`

**Coverage**:
- METAR sensor creation
- TAF sensor creation
- State and attribute values
- Update logic
- Backward compatibility (sensors work without CheckWX)

**File**: `tests/test_checkwx_config_flow.py`

**Coverage**:
- Config flow additions
- Migration logic
- API key validation
- Per-airfield settings

### Integration Tests

**File**: `tests/test_checkwx_integration.py`

**Coverage**:
- End-to-end METAR fetch
- End-to-end TAF fetch
- Multi-airfield scenarios
- Rate limit breach handling
- Cache persistence across restarts (mock restart)

### Manual Testing Checklist

- [ ] Fresh install with CheckWX enabled
- [ ] Upgrade from existing install (no CheckWX)
- [ ] Rate limit warning appears at 2,700 requests
- [ ] Cache survives HA restart
- [ ] Stale cache used when API unavailable
- [ ] Per-airfield enable/disable works
- [ ] METAR sensor updates every 30 minutes
- [ ] TAF sensor updates every 6 hours
- [ ] Flight category alert triggers correctly
- [ ] Clear cache service works
- [ ] Auto-populate station service works

---

## Success Metrics

### Adoption Metrics
- **Goal**: 30% of users enable CheckWX within 3 months of release
- **Metric**: Track `checkwx.enabled` in telemetry (if implemented)

### API Efficiency
- **Goal**: Average user stays under 2,000 requests/day (66% of free tier)
- **Metric**: Monitor `daily_requests` in config
- **Target cache hit ratio**: >90% for METAR, >95% for TAF

### Reliability
- **Goal**: 99% uptime (data availability)
- **Metric**: Track stale cache fallback frequency
- **Target**: <1% of requests fallback to stale cache

### User Feedback
- **Goal**: Positive sentiment on GitHub issues/discussions
- **Metric**: Monitor issues tagged `checkwx`
- **Target**: <5% bug reports related to CheckWX

---

## Cost Analysis

### Free Tier Capacity

**3,000 requests/day breakdown:**

| Scenario | Airfields | Updates/Day | Req/Day | Headroom |
|----------|-----------|-------------|---------|----------|
| Single aircraft | 1 | METAR (48) + TAF (4) | 52 | 57x over limit |
| Light user | 3 | METAR (48) + TAF (4) each | 156 | 19x over limit |
| Power user | 5 | METAR (48) + TAF (4) each | 260 | 11x over limit |
| Flight school | 10 | METAR (48) + TAF (4) each | 520 | 5.7x over limit |

**Conclusion**: Free tier is MORE than sufficient for typical Home Assistant users (1-5 airfields).

### Upgrade Path

**Professional Tier ($7/mo)**: 50,000 requests/day
- Supports 100+ airfields or high-frequency polling
- Recommended for flight schools or multi-base operators

**Enterprise Tier ($30/mo)**: 500,000 requests/day
- Commercial operations only

---

## Recommended Next Steps

### Immediate Actions (This Week)

1. **Decision**: Approve CheckWX integration for Phase 1 (METAR/TAF)
2. **Account Setup**: Create test CheckWX account (free tier)
3. **Prototype**: Quick prototype of `checkwx_client.py` (2 hours)
4. **Review**: Team review of this plan

### Implementation Timeline (Week 1-2)

- **Day 1-2**: Core client + caching
- **Day 3**: Config flow integration
- **Day 4-5**: METAR sensors + tests
- **Day 6-7**: TAF sensors + tests
- **Day 8**: Documentation + release prep

### Release Strategy

- **Beta Release**: v2601.3.0-beta (opt-in via GitHub)
- **User Testing**: 2 weeks, gather feedback
- **Stable Release**: v2601.3.0 (HACS)
- **Documentation**: Update README, add CheckWX setup guide

---

## Conclusion

CheckWX integration is a **high-value, low-risk addition** to Hangar Assistant:

✅ **FREE tier** sufficient for most users  
✅ **Aviation-standard** METAR/TAF data  
✅ **Easy implementation** (well-documented API)  
✅ **Clear caching strategy** protects rate limits  
✅ **Backward compatible** (opt-in feature)  
✅ **Pilot trust** (official weather format)  

**Recommendation**: **APPROVE for Phase 1 implementation** (METAR + TAF + Station Info)

---

## Appendix A: Example API Responses

### METAR Decoded Response
```json
{
  "results": 1,
  "data": [
    {
      "icao": "KJFK",
      "barometer": {"hg": 30.35, "hpa": 1028.0},
      "ceiling": {"feet": 25000, "meters": 7620},
      "clouds": [
        {"base_feet_agl": 3600, "code": "FEW", "text": "Few"},
        {"base_feet_agl": 25000, "code": "BKN", "text": "Broken"}
      ],
      "dewpoint": {"celsius": -7, "fahrenheit": 19},
      "temperature": {"celsius": 0, "fahrenheit": 32},
      "flight_category": "VFR",
      "humidity": {"percent": 60},
      "observed": "2026-01-21T19:51:00",
      "visibility": {"miles": 10.0, "meters": 9999.0},
      "wind": {
        "degrees": 190,
        "speed_kts": 18,
        "speed_kph": 33,
        "gust_kts": 31
      },
      "raw_text": "METAR KJFK 211951Z 19018G31KT 10SM FEW036 FEW170 BKN250 00/M07 A3035 ..."
    }
  ]
}
```

### TAF Decoded Response
```json
{
  "results": 1,
  "data": [
    {
      "icao": "KJFK",
      "timestamp": {
        "issued": "2026-01-21T17:22:00",
        "from": "2026-01-21T18:00:00",
        "to": "2026-01-23T00:00:00"
      },
      "forecast": [
        {
          "timestamp": {"from": "2026-01-21T18:00:00", "to": "2026-01-21T19:00:00"},
          "wind": {"degrees": 210, "speed_kts": 11},
          "visibility": {"miles": 10.0},
          "clouds": [{"code": "SCT", "text": "Scattered", "base_feet_agl": 15000}]
        },
        {
          "change": {"indicator": {"code": "FM", "text": "From"}},
          "timestamp": {"from": "2026-01-21T19:00:00", "to": "2026-01-22T04:00:00"},
          "wind": {"degrees": 190, "speed_kts": 15, "gust_kts": 23},
          "visibility": {"miles": 10.0},
          "clouds": [{"code": "BKN", "text": "Broken", "base_feet_agl": 15000}]
        }
      ],
      "raw_text": "TAF KJFK 211722Z 2118/2224 21011KT P6SM SCT150 FM211900 ..."
    }
  ]
}
```

### Station Response
```json
{
  "results": 1,
  "data": [
    {
      "icao": "KJFK",
      "iata": "JFK",
      "name": "John F Kennedy International Airport",
      "city": "New York",
      "country": {"code": "US", "name": "United States"},
      "elevation": {"feet": 13.0, "meters": 4.0},
      "latitude": {"decimal": 40.639},
      "longitude": {"decimal": -73.779},
      "location": "New York, New York, United States",
      "type": "Airport",
      "geometry": {
        "type": "Point",
        "coordinates": [-73.779, 40.639]
      }
    }
  ]
}
```

---

**Document End**
