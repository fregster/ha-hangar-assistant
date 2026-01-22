# ADS-B Tracking - Phase 1 Implementation Tasks

**Phase**: Phase 1 - Core Architecture + Free Data Sources  
**Target Version**: v2601.5.0  
**Duration**: 3-4 weeks  
**Status**: Planning  
**Last Updated**: 22 January 2026

---

## Overview

Phase 1 establishes the foundational architecture for ADS-B tracking with **three data sources**:
1. **Local dump1090 receiver** (ADS-B only, requires hardware)
2. **OpenSky Network API** (ADS-B + FLARM, free, enabled by default)
3. **Open Gliding Network APRS** (FLARM only, free, enabled by default)

This provides immediate value (free APIs work out-of-box) while supporting local hardware for users who want best performance.

**Key Features**:
- Data source prioritization (dump1090 > OpenSky > OGN)
- Automatic deduplication (no duplicate aircraft markers)
- Rate limit protection (OpenSky 400 credits/day anonymous)
- Free account encouragement (OpenSky 10x rate limit increase)
- Glider tracking support (FLARM via OpenSky + OGN)

**Success Criteria**:
- Users can track aircraft immediately after installation (OpenSky/OGN enabled by default)
- Users with dump1090 hardware get priority local data
- Deduplication prevents duplicate markers on map
- Rate limits respected (no bans, clear credit tracking)
- Gliders visible via FLARM data sources
- 80%+ test coverage
- Complete documentation (explains ADS-B vs FLARM)

---

## Task Breakdown

### 1. Data Models & Base Architecture

#### Task 1.1: Create AircraftData dataclass
**File**: `custom_components/hangar_assistant/utils/adsb_models.py` (new)  
**Priority**: High  
**Estimated Time**: 2 hours  
**Dependencies**: None

**Requirements**:
- [ ] Create `AircraftData` dataclass following project patterns
- [ ] Include all fields from plan: registration, ICAO24, position, velocity, type
- [ ] Add FLARM-specific fields: `turn_rate_deg_s`, `is_flarm`, `flarm_id`
- [ ] Add validation methods (`validate_registration`, `validate_icao24`)
- [ ] Add utility methods (`distance_to`, `bearing_to`, `is_airborne`)
- [ ] Include comprehensive docstrings (inputs, outputs, use cases)
- [ ] Add type hints for all fields
- [ ] Support both ADS-B and FLARM data (flexible optional fields)

**Validation**:
```python
def test_aircraft_data_creation():
    """Test AircraftData can be created with valid data."""
    data = AircraftData(
        registration="G-ABCD",
        icao24="4CA1E3",
        latitude=51.2,
        longitude=-1.2,
        altitude_ft=1500,
        source="dump1090",
        last_seen=datetime.utcnow()
    )
    assert data.registration == "G-ABCD"
    assert data.is_airborne() is True  # altitude > 0
```

#### Task 1.2: Create ADSBClientBase abstract class
**File**: `custom_components/hangar_assistant/utils/adsb_client_base.py` (new)  
**Priority**: High  
**Estimated Time**: 5 hours  
**Dependencies**: Task 1.1

**Requirements**:
- [ ] Define abstract base class with interface methods from plan
- [ ] Implement common utility functions (distance calculation, bearing, bounding box)
- [ ] Add cache management base methods (memory + persistent pattern from OWM)
- [ ] Include error handling patterns (graceful degradation)
- [ ] Add connection testing framework (`test_connection` method)
- [ ] Implement cache statistics tracking (`get_cache_stats`)
- [ ] **Add deduplication logic** (`deduplicate_aircraft_by_icao24`)
- [ ] **Add data source priority system** (configurable priority per client)
- [ ] **Add data merging** (merge non-conflicting fields from multiple sources)
- [ ] Add comprehensive docstrings for abstract methods

**Interface Methods Required**:
```python
@abstractmethod
async def get_aircraft_by_registration(self, registration: str) -> Optional[AircraftData]:
    pass

@abstractmethod
async def get_aircraft_by_icao24(self, icao24: str) -> Optional[AircraftData]:
    pass

@abstractmethod
async def get_aircraft_near_location(
    self, latitude: float, longitude: float, radius_nm: float = 10
) -> List[AircraftData]:
    pass
```

**Validation**:
- Abstract methods raise `NotImplementedError` if not overridden
- Utility functions (distance, bearing) match known values (use aviation formula tests)
- Cache methods follow OWM pattern (LRU eviction, persistent file)

#### Task 1.3: Create integration configuration structure
**File**: `custom_components/hangar_assistant/const.py` (update)  
**Priority**: Medium  
**Estimated Time**: 1 hour  
**Dependencies**: None

**Requirements**:
- [ ] Add `CONF_ADSB_*` constants for configuration keys
- [ ] Define default values (cache TTL, update intervals, radius)
- [ ] Add validation schemas for config entries

**Constants to Add**:
```python
# ADS-B Configuration Keys
CONF_ADSB = "adsb"
CONF_ADSB_ENABLED = "adsb_enabled"
CONF_ADSB_SOURCES = "adsb_sources"
CONF_ADSB_TRACKED_AIRCRAFT = "tracked_aircraft"
CONF_ADSB_AIRFIELD_TRAFFIC = "airfield_traffic"

# dump1090 Configuration
CONF_DUMP1090_HOST = "dump1090_host"
CONF_DUMP1090_PORT = "dump1090_port"
CONF_DUMP1090_ENDPOINT = "dump1090_endpoint"
CONF_DUMP1090_TIMEOUT = "dump1090_timeout"

# Defaults
DEFAULT_ADSB_CACHE_TTL = 30  # seconds
DEFAULT_ADSB_UPDATE_INTERVAL = 10  # seconds
DEFAULT_ADSB_MONITORING_RADIUS = 10  # nautical miles
DEFAULT_DUMP1090_PORT = 8080
DEFAULT_DUMP1090_ENDPOINT = "/data/aircraft.json"
DEFAULT_DUMP1090_TIMEOUT = 5  # seconds
```

---

### 2. dump1090 Client Implementation

#### Task 2.1: Create Dump1090Client class
**File**: `custom_components/hangar_assistant/utils/dump1090_client.py` (new)  
**Priority**: High  
**Estimated Time**: 6 hours  
**Dependencies**: Task 1.1, 1.2

**Requirements**:
- [ ] Inherit from `ADSBClientBase`
- [ ] Implement all abstract methods
- [ ] Parse dump1090 JSON format (`aircraft.json`)
- [ ] Handle connection errors gracefully
- [ ] Implement persistent caching (follow OWM pattern)
- [ ] Add bounding box filtering for efficiency
- [ ] Support multiple dump1090 instances (multi-site)
- [ ] Add connection health monitoring

**dump1090 JSON Format Reference**:
```json
{
  "now": 1737560000.0,
  "messages": 1234567,
  "aircraft": [
    {
      "hex": "4ca1e3",
      "squawk": "7000",
      "flight": "GABCD   ",
      "lat": 51.2345,
      "lon": -1.2345,
      "altitude": 1500,
      "vert_rate": -300,
      "track": 180,
      "speed": 95,
      "seen": 0.5
    }
  ]
}
```

**Implementation Notes**:
- Trim whitespace from `flight` field (registration)
- Handle missing fields gracefully (not all aircraft report all data)
- Calculate `last_seen` from `seen` field (seconds ago)
- Filter out ground vehicles (no aircraft type)

**Validation**:
```python
async def test_dump1090_parse_json():
    """Test parsing of dump1090 JSON format."""
    client = Dump1090Client(hass, "192.168.1.100", 8080)
    
    # Mock response with sample JSON
    mock_json = {...}
    aircraft = await client._parse_aircraft_json(mock_json)
    
    assert len(aircraft) > 0
    assert aircraft[0].registration == "G-ABCD"
    assert aircraft[0].latitude == 51.2345
```

#### Task 2.2: Add connection testing and diagnostics
**File**: `custom_components/hangar_assistant/utils/dump1090_client.py` (update)  
**Priority**: Medium  
**Estimated Time**: 2 hours  
**Dependencies**: Task 2.1

**Requirements**:
- [ ] Implement `test_connection` method
- [ ] Add health check endpoint (`/status.json` if available)
- [ ] Track connection uptime/downtime
- [ ] Log diagnostic information (message count, last update time)
- [ ] Return detailed error messages for common issues

**Connection Test Scenarios**:
- Host unreachable (network down)
- Wrong port (connection refused)
- Wrong endpoint (404 error)
- Valid connection (200 OK with data)
- Timeout (slow response)

**Diagnostics to Track**:
```python
{
    "connected": True,
    "last_update": "2026-01-22T14:30:00Z",
    "messages_today": 45678,
    "aircraft_seen": 23,
    "uptime_hours": 12.5,
    "connection_errors_today": 0
}
```

#### Task 2.3: Implement local aircraft database (optional enhancement)
**File**: `custom_components/hangar_assistant/utils/aircraft_database.py` (new)  
**Priority**: Low (optional for Phase 1)  
**Estimated Time**: 4 hours  
**Dependencies**: None

**Requirements**:
- [ ] Load aircraft type database (ICAO type codes → descriptions)
- [ ] Support custom user entries (user's own aircraft)
- [ ] Match ICAO24 to registration (if available)
- [ ] Lookup aircraft type from registration

**Database Sources**:
- Embedded SQLite database (BaseStation.sqb format)
- CSV file with ICAO24, registration, type
- User-provided entries in config

**Use Case**: dump1090 provides ICAO24 but not registration/type. Database fills in gaps.

**Implementation**: Copy pattern from OpenWeatherMap cache but for static data.

#### Task 2.4: Create OpenSkyClient class
**File**: `custom_components/hangar_assistant/utils/opensky_client.py` (new)  
**Priority**: High  
**Estimated Time**: 6 hours  
**Dependencies**: Task 1.1, 1.2

**Requirements**:
- [ ] Inherit from `ADSBClientBase`
- [ ] Implement all abstract methods
- [ ] Use `/states/all` endpoint with bounding box filter
- [ ] Parse OpenSky JSON format (different from dump1090)
- [ ] Implement rate limit tracking (400 credits/day anonymous, 4000 with account)
- [ ] Implement exponential backoff on 429 errors
- [ ] Support optional authentication (username/password for higher limits)
- [ ] Track daily credit usage in config entry
- [ ] Reset credit counter at 00:00 UTC
- [ ] Cache aggressively (60s TTL anonymous, 30s with account)
- [ ] Detect FLARM aircraft (specific ICAO24 prefixes)
- [ ] Add connection health monitoring

**OpenSky API Response Format**:
```json
{
  "time": 1737560000,
  "states": [
    [
      "4ca1e3",        // ICAO24
      "GABCD   ",      // Callsign
      "United Kingdom",// Origin country
      1737560000,      // Time position
      1737560000,      // Last contact
      -1.2345,         // Longitude
      51.2345,         // Latitude
      762.0,           // Baro altitude (m)
      false,           // On ground
      49.0,            // Velocity (m/s)
      180.0,           // True track (degrees)
      0.0,             // Vertical rate (m/s)
      null,            // Sensors
      762.0,           // Geo altitude (m)
      "4567",          // Squawk
      false,           // SPI
      0                // Position source
    ]
  ]
}
```

**Rate Limit Handling**:
```python
if response.status == 429:
    # Rate limited
    _LOGGER.warning("OpenSky rate limit reached, using cached data")
    self._rate_limited = True
    self._rate_limit_reset = datetime.utcnow() + timedelta(hours=1)
    return await self._read_stale_cache()
```

**Credit Tracking**:
- Simple query (bbox): 1 credit
- Track specific aircraft: 1 credit
- Update credit counter in config entry after each call
- Warn user at 350 credits (approaching limit)
- Show "Create Free Account" prompt at 380 credits

#### Task 2.5: Create OGNClient class
**File**: `custom_components/hangar_assistant/utils/ogn_client.py` (new)  
**Priority**: High  
**Estimated Time**: 7 hours  
**Dependencies**: Task 1.1, 1.2

**Requirements**:
- [ ] Inherit from `ADSBClientBase`
- [ ] Implement all abstract methods
- [ ] Use `aprslib` for APRS connection to `aprs.glidernet.org:14580`
- [ ] Parse OGN APRS packet format
- [ ] Extract position, altitude, speed, track, vertical rate, turn rate
- [ ] Implement automatic reconnection (APRS can disconnect)
- [ ] Use APRS radius filter to reduce bandwidth (`r/lat/lon/radius`)
- [ ] Query OGN Device Database (DDB) for aircraft type/registration
- [ ] Cache DDB lookups (aircraft types rarely change)
- [ ] Handle connection errors gracefully
- [ ] Track connection health (uptime, reconnection count)
- [ ] Log APRS traffic statistics (packets received, parsed, errors)

**OGN APRS Packet Parsing**:
```python
# Example packet:
# FLRDD1234>APRS,qAS,RECEIVER:/093045h5123.45N/00123.45W'123/045/A=002500 !W12! id06DD1234 +020fpm +0.5rot 5.5dB 0e -0.3kHz gps2x3

import re

APRS_PATTERN = re.compile(
    r'/(?P<time>\d{6})h'
    r'(?P<lat>\d{4}\.\d{2})(?P<lat_dir>[NS])/'
    r'(?P<lon>\d{5}\.\d{2})(?P<lon_dir>[EW])'
    r"'(?P<track>\d{3})/(?P<speed>\d{3})/"
    r'A=(?P<altitude>\d{6})'
)

EXTENSION_PATTERN = re.compile(
    r'id(?P<id>\w+) '
    r'(?P<climb>[+-]\d+)fpm '
    r'(?P<turn>[+-]\d+\.\d+)rot'
)
```

**DDB Integration**:
```python
async def _lookup_ddb(self, flarm_id: str) -> Optional[Dict[str, str]]:
    """Query OGN Device Database for aircraft details.
    
    DDB provides:
    - Aircraft registration
    - Aircraft type (e.g., "ASW 20", "Discus 2c")
    - CN (competition number)
    """
    ddb_url = f"http://ddb.glidernet.org/download/?j=1&t=1&id={flarm_id}"
    # Cache result for 24 hours (aircraft types don't change often)
```

**Connection Management**:
```python
class OGNClient(ADSBClientBase):
    def __init__(self, ...):
        self._aprs_client = None
        self._connected = False
        self._reconnect_interval = 30  # seconds
        
    async def _ensure_connected(self):
        """Ensure APRS connection is active, reconnect if needed."""
        if not self._connected or not self._aprs_client:
            await self._connect_aprs()
    
    async def _connect_aprs(self):
        """Connect to OGN APRS feed."""
        try:
            # Use aprslib to connect
            self._aprs_client = aprslib.IS(
                "HA-HANGAR",  # Callsign
                passwd="-1",   # Read-only
                host="aprs.glidernet.org",
                port=14580
            )
            self._aprs_client.set_filter(f"r/{lat}/{lon}/{radius_km}")
            self._aprs_client.connect()
            self._connected = True
            _LOGGER.info("Connected to OGN APRS feed")
        except Exception as e:
            _LOGGER.error("Failed to connect to OGN APRS: %s", e)
            self._connected = False
```

---

### 3. Data Source Manager & Deduplication

---

### 4. Data Source Manager & Deduplication

#### Task 3.1: Create ADSBDataSourceManager class
**File**: `custom_components/hangar_assistant/utils/adsb_manager.py` (new)  
**Priority**: High  
**Estimated Time**: 4 hours  
**Dependencies**: Task 1.2, 2.1, 2.4, 2.5

**Requirements**:
- [ ] Manage multiple data source clients (dump1090, OpenSky, OGN)
- [ ] Query all enabled sources in parallel (asyncio.gather)
- [ ] Implement deduplication by ICAO24 hex code
- [ ] Apply priority system (dump1090 > OpenSky > OGN)
- [ ] Merge non-conflicting data from lower-priority sources
- [ ] Provide unified interface for device trackers
- [ ] Handle partial failures (one source down, others continue)
- [ ] Track health status of all sources
- [ ] Provide diagnostics (which source provided each aircraft)

**Deduplication Algorithm**:
```python
class ADSBDataSourceManager:
    def __init__(self, hass, config):
        self.sources = []
        # Initialize clients based on enabled sources
        if config["dump1090"]["enabled"]:
            self.sources.append((1, Dump1090Client(...)))  # Priority 1
        if config["opensky"]["enabled"]:
            self.sources.append((2, OpenSkyClient(...)))   # Priority 2
        if config["ogn"]["enabled"]:
            self.sources.append((3, OGNClient(...)))       # Priority 3
        
        # Sort by priority (lower number = higher priority)
        self.sources.sort(key=lambda x: x[0])
    
    async def get_aircraft_near_location(
        self, latitude: float, longitude: float, radius_nm: float
    ) -> List[AircraftData]:
        """Get deduplicated aircraft from all enabled sources."""
        # Query all sources in parallel
        tasks = [
            source.get_aircraft_near_location(latitude, longitude, radius_nm)
            for _priority, source in self.sources
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Deduplicate by ICAO24
        aircraft_by_icao24 = {}
        
        for (priority, source), result in zip(self.sources, results):
            if isinstance(result, Exception):
                _LOGGER.warning("Source %s failed: %s", source.__class__.__name__, result)
                continue
            
            for aircraft in result:
                icao24 = aircraft.icao24
                
                if icao24 not in aircraft_by_icao24:
                    # New aircraft, add it
                    aircraft_by_icao24[icao24] = aircraft
                else:
                    # Duplicate, merge missing data
                    existing = aircraft_by_icao24[icao24]
                    self._merge_aircraft_data(existing, aircraft)
        
        return list(aircraft_by_icao24.values())
    
    def _merge_aircraft_data(self, primary: AircraftData, secondary: AircraftData):
        """Merge missing fields from secondary into primary."""
        # Only fill missing fields, never overwrite primary source data
        if not primary.aircraft_type and secondary.aircraft_type:
            primary.aircraft_type = secondary.aircraft_type
        if not primary.registration and secondary.registration:
            primary.registration = secondary.registration
        # ... merge other fields
```

**Health Status**:
```python
async def get_source_health(self) -> Dict[str, Dict[str, Any]]:
    """Get health status of all data sources."""
    health = {}
    
    for priority, source in self.sources:
        source_name = source.__class__.__name__
        health[source_name] = {
            "enabled": True,
            "priority": priority,
            "connected": await source.test_connection(),
            "cache_stats": await source.get_cache_stats(),
            "last_update": source.last_update_time,
            "error_count": source.error_count
        }
    
    return health
```

---

### 4. Device Tracker Entity

#### Task 3.1: Create ADSBAircraftTracker entity
**File**: `custom_components/hangar_assistant/device_tracker.py` (new)  
**Priority**: High  
**Estimated Time**: 5 hours  
**Dependencies**: Task 1.1, 2.1

**Requirements**:
- [ ] Derive from `TrackerEntity` (Home Assistant device tracker)
- [ ] Implement required methods (`latitude`, `longitude`, `source_type`)
- [ ] Add state logic (home, away, airborne, unknown)
- [ ] Populate attributes (altitude, speed, track, type, etc.)
- [ ] Link to aircraft device info (existing aircraft entities)
- [ ] Implement update coordination (poll at configured interval)
- [ ] Handle data staleness (mark unknown if no update for N minutes)

**State Determination**:
```python
def state(self) -> str:
    """Determine tracker state."""
    if not self._aircraft_data or self._is_stale():
        return STATE_UNKNOWN
    
    if self._aircraft_data.on_ground:
        # Check if near home airfield
        if self._distance_to_home() < 0.5:  # Within 0.5nm
            return STATE_HOME
        return "on_ground"
    
    # Airborne
    return "airborne"
```

**Attributes to Include**:
- All `AircraftData` fields
- `distance_from_home_nm`: Calculated distance to home airfield
- `bearing_from_home_deg`: Bearing to home airfield
- `nearest_airfield`: Closest configured airfield ICAO code
- `flight_time_today_hours`: Calculated from first seen today
- `data_age_seconds`: Time since last update

**Validation**:
```python
async def test_aircraft_tracker_state():
    """Test device tracker state transitions."""
    tracker = ADSBAircraftTracker(hass, config, adsb_client)
    
    # Simulate airborne aircraft
    tracker._aircraft_data = AircraftData(
        latitude=51.3,
        longitude=-1.2,
        altitude_ft=2500,
        on_ground=False,
        ...
    )
    
    assert tracker.state == "airborne"
    assert tracker.latitude == 51.3
```

#### Task 3.2: Add device tracker setup in __init__.py
**File**: `custom_components/hangar_assistant/__init__.py` (update)  
**Priority**: High  
**Estimated Time**: 2 hours  
**Dependencies**: Task 3.1

**Requirements**:
- [ ] Register device tracker platform (`device_tracker.py`)
- [ ] Create device trackers for each configured tracked aircraft
- [ ] Initialize ADSB client(s) based on enabled sources
- [ ] Set up update coordinator (async_track_time_interval)
- [ ] Handle config changes (add/remove tracked aircraft)

**Setup Pattern**:
```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hangar Assistant from config entry."""
    
    # ... existing setup ...
    
    # Initialize ADS-B tracking if enabled
    adsb_config = entry.data.get("integrations", {}).get("adsb", {})
    if adsb_config.get("enabled", False):
        await _setup_adsb_tracking(hass, entry, adsb_config)
    
    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(
        entry,
        ["sensor", "binary_sensor", "select", "device_tracker"]  # Add device_tracker
    )
```

**Update Coordinator**:
```python
async def _adsb_update_coordinator(now):
    """Poll ADS-B client and update device trackers."""
    for tracker in hass.data[DOMAIN][entry.entry_id]["adsb_trackers"]:
        await tracker.async_update()
```

---

### 5. Configuration Flow

#### Task 4.1: Add ADS-B setup step to wizard
**File**: `custom_components/hangar_assistant/config_flow.py` (update)  
**Priority**: High  
**Estimated Time**: 4 hours  
**Dependencies**: Task 1.3

**Requirements**:
- [ ] Add new wizard step: `async_step_adsb_setup`
- [ ] Show introduction with benefits and data source options
- [ ] Allow user to skip (ADS-B is optional)
- [ ] Store initial config in `entry.data["integrations"]["adsb"]`
- [ ] Follow existing wizard pattern (step tracking, progress indicator)

**Step Flow**:
1. Introduction → 2. Select Source → 3. Configure Source → 4. Add Aircraft → 5. Summary

**Form Schema**:
```python
data_schema = vol.Schema({
    vol.Optional("enable_adsb", default=False): bool,
    vol.Optional("data_source", default="dump1090"): vol.In([
        "dump1090",
        "skip"  # Other sources in later phases
    ])
})
```

#### Task 4.2: Create dump1090 configuration step
**File**: `custom_components/hangar_assistant/config_flow.py` (update)  
**Priority**: High  
**Estimated Time**: 3 hours  
**Dependencies**: Task 4.1, 2.1

**Requirements**:
- [ ] Add `async_step_adsb_dump1090` step
- [ ] Form fields: host, port, endpoint
- [ ] Test connection button (validate before proceeding)
- [ ] Show helpful error messages for common issues
- [ ] Pre-fill defaults (port 8080, endpoint /data/aircraft.json)

**Form Schema**:
```python
data_schema = vol.Schema({
    vol.Required(CONF_DUMP1090_HOST): str,
    vol.Optional(CONF_DUMP1090_PORT, default=DEFAULT_DUMP1090_PORT): int,
    vol.Optional(CONF_DUMP1090_ENDPOINT, default=DEFAULT_DUMP1090_ENDPOINT): str,
})
```

**Connection Test**:
```python
# In async_step_adsb_dump1090
if user_input is not None:
    # Test connection before saving
    client = Dump1090Client(
        self.hass,
        user_input[CONF_DUMP1090_HOST],
        user_input[CONF_DUMP1090_PORT]
    )
    
    if not await client.test_connection():
        errors["base"] = "cannot_connect"
    else:
        # Save config and proceed
        self._adsb_config["dump1090"] = user_input
        return await self.async_step_adsb_add_aircraft()
```

#### Task 4.3: Create tracked aircraft configuration step
**File**: `custom_components/hangar_assistant/config_flow.py` (update)  
**Priority**: High  
**Estimated Time**: 3 hours  
**Dependencies**: Task 4.2

**Requirements**:
- [ ] Add `async_step_adsb_add_aircraft` step
- [ ] Form to add aircraft: registration, ICAO24 (optional), nickname
- [ ] Validate registration format (country-specific patterns)
- [ ] Show list of added aircraft (allow removal)
- [ ] "Add Another" and "Done" buttons
- [ ] Link to existing aircraft entities if registration matches

**Form Schema**:
```python
data_schema = vol.Schema({
    vol.Required("registration"): str,  # e.g., G-ABCD
    vol.Optional("icao24"): str,        # e.g., 4CA1E3
    vol.Optional("nickname"): str,      # e.g., "My Cessna"
})
```

**Registration Validation**:
- UK: `^G-[A-Z]{4}$`
- USA: `^N[0-9]{1,5}[A-Z]{0,2}$`
- Germany: `^D-[A-Z]{4}$`
- Generic: Allow any format, warn if non-standard

#### Task 4.4: Add ADS-B reconfiguration to options flow
**File**: `custom_components/hangar_assistant/config_flow.py` (update)  
**Priority**: Medium  
**Estimated Time**: 2 hours  
**Dependencies**: Task 4.1-4.3

**Requirements**:
- [ ] Add "ADS-B Settings" menu option to options flow
- [ ] Allow enable/disable of ADS-B tracking
- [ ] Allow reconfiguration of dump1090 host/port
- [ ] Allow add/remove of tracked aircraft
- [ ] Show current configuration status

**Menu Structure**:
```python
"menu_options": {
    "adsb_sources": "Data Sources",
    "adsb_aircraft": "Tracked Aircraft",
    "adsb_airfield_traffic": "Airfield Traffic Settings",
    "adsb_diagnostics": "Diagnostics"
}
```

---

### 5. Dashboard Integration

#### Task 5.1: Create device tracker card template
**File**: `custom_components/hangar_assistant/dashboard_templates/adsb_map_card.yaml` (new)  
**Priority**: Medium  
**Estimated Time**: 2 hours  
**Dependencies**: Task 3.1

**Requirements**:
- [ ] Create map card YAML template for aircraft tracking
- [ ] Show all device trackers on map
- [ ] Include track history (last 30 minutes)
- [ ] Add airfield location marker
- [ ] Responsive design (mobile + desktop)

**Template Example**:
```yaml
type: map
title: Aircraft Tracking
entities:
  # Dynamically populated with device trackers
  {% for aircraft in tracked_aircraft %}
  - device_tracker.{{ aircraft.slug }}
  {% endfor %}
  # Airfield location
  - zone.home_airfield
dark_mode: true
hours_to_show: 0.5  # 30 minutes
aspect_ratio: "16:9"
default_zoom: 11
```

#### Task 5.2: Add ADS-B section to glass cockpit dashboard
**File**: `custom_components/hangar_assistant/dashboard_templates/glass_cockpit.yaml` (update)  
**Priority**: Low (nice-to-have for Phase 1)  
**Estimated Time**: 2 hours  
**Dependencies**: Task 5.1

**Requirements**:
- [ ] Add conditional section (only shows if ADS-B enabled)
- [ ] Show map card with tracked aircraft
- [ ] Show quick stats (aircraft tracked, last update)
- [ ] Link to full ADS-B dashboard

**Section Placement**: After "Fuel Management" section, before "Safety Alerts"

---

### 6. Testing

#### Task 6.1: Create unit tests for data models
**File**: `tests/test_adsb_models.py` (new)  
**Priority**: High  
**Estimated Time**: 2 hours  
**Dependencies**: Task 1.1

**Test Coverage**:
- [ ] Test `AircraftData` creation with valid data
- [ ] Test validation methods (registration, ICAO24)
- [ ] Test utility methods (distance, bearing, is_airborne)
- [ ] Test edge cases (missing fields, invalid data)
- [ ] Test serialization/deserialization

**Example Tests**:
```python
def test_aircraft_data_is_airborne():
    """Test is_airborne detection."""
    # On ground
    data = AircraftData(altitude_ft=0, on_ground=True, ...)
    assert data.is_airborne() is False
    
    # Airborne
    data = AircraftData(altitude_ft=1500, on_ground=False, ...)
    assert data.is_airborne() is True
```

#### Task 6.2: Create unit tests for ADSBClientBase
**File**: `tests/test_adsb_client_base.py` (new)  
**Priority**: High  
**Estimated Time**: 3 hours  
**Dependencies**: Task 1.2

**Test Coverage**:
- [ ] Test abstract methods raise NotImplementedError
- [ ] Test common utility functions (distance, bearing)
- [ ] Test cache management (memory + persistent)
- [ ] Test cache LRU eviction
- [ ] Test cache statistics tracking

**Mock Client Implementation**:
```python
class MockADSBClient(ADSBClientBase):
    """Mock client for testing base class."""
    
    async def get_aircraft_by_registration(self, registration):
        return AircraftData(registration=registration, ...)
    # ... implement other abstract methods
```

#### Task 6.3: Create unit tests for Dump1090Client
**File**: `tests/test_dump1090_client.py` (new)  
**Priority**: High  
**Estimated Time**: 4 hours  
**Dependencies**: Task 2.1, 2.2

**Test Coverage**:
- [ ] Test JSON parsing with sample dump1090 data
- [ ] Test connection error handling (timeout, refused, 404)
- [ ] Test cache hit/miss scenarios
- [ ] Test bounding box filtering
- [ ] Test aircraft data extraction
- [ ] Test stale data handling

**Mock HTTP Responses**:
```python
@pytest.fixture
def mock_dump1090_response():
    """Mock dump1090 aircraft.json response."""
    return {
        "now": 1737560000.0,
        "aircraft": [
            {
                "hex": "4ca1e3",
                "flight": "GABCD   ",
                "lat": 51.2,
                "lon": -1.2,
                "altitude": 1500,
                "speed": 95,
                "track": 180
            }
        ]
    }
```

#### Task 6.4: Create unit tests for device tracker
**File**: `tests/test_adsb_device_tracker.py` (new)  
**Priority**: High  
**Estimated Time**: 3 hours  
**Dependencies**: Task 3.1

**Test Coverage**:
- [ ] Test state determination (home, away, airborne, unknown)
- [ ] Test attribute population
- [ ] Test data staleness detection
- [ ] Test update coordination
- [ ] Test device info linking

#### Task 6.5: Create integration tests
**File**: `tests/test_adsb_integration.py` (new)  
**Priority**: Medium  
**Estimated Time**: 4 hours  
**Dependencies**: Task 3.2, 4.1-4.3

**Test Coverage**:
- [ ] Test complete setup flow (wizard → entities created)
- [ ] Test config entry reload (entities recreate)
- [ ] Test add/remove tracked aircraft
- [ ] Test client initialization based on config
- [ ] Test graceful handling of disabled ADS-B

**Integration Test Scenario**:
```python
async def test_adsb_setup_creates_device_trackers(hass):
    """Test ADS-B setup creates device tracker entities."""
    # Configure integration with ADS-B enabled
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "integrations": {
                "adsb": {
                    "enabled": True,
                    "sources": {
                        "dump1090": {
                            "enabled": True,
                            "host": "localhost",
                            "port": 8080
                        }
                    },
                    "tracked_aircraft": [
                        {
                            "registration": "G-ABCD",
                            "icao24": "4CA1E3"
                        }
                    ]
                }
            }
        }
    )
    
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    
    # Verify device tracker created
    state = hass.states.get("device_tracker.g_abcd_aircraft")
    assert state is not None
```

---

### 7. Documentation

#### Task 7.1: Create feature documentation
**File**: `docs/features/adsb_tracking.md` (new)  
**Priority**: High  
**Estimated Time**: 4 hours  
**Dependencies**: All above tasks

**Sections Required**:
- [ ] Overview and benefits
- [ ] Data source comparison (dump1090 vs APIs - Phase 1 only covers dump1090)
- [ ] Step-by-step setup guide
- [ ] Dashboard integration examples
- [ ] Troubleshooting guide
- [ ] FAQ
- [ ] Best practices

**Target Audience**: Pilots with basic technical knowledge

**Tone**: Aviation language, minimal jargon, clear examples

#### Task 7.2: Create hardware setup guide
**File**: `docs/features/adsb_hardware_setup.md` (new)  
**Priority**: Medium  
**Estimated Time**: 3 hours  
**Dependencies**: None

**Sections Required**:
- [ ] Hardware requirements (RTL-SDR, antenna)
- [ ] Raspberry Pi installation (Raspbian + dump1090)
- [ ] Network configuration (static IP, port forwarding)
- [ ] Antenna placement recommendations
- [ ] Performance tuning
- [ ] Troubleshooting hardware issues

**Include**:
- Shopping list with links (Amazon, eBay)
- Step-by-step terminal commands
- Screenshots of dump1090 web interface
- Expected reception range map

#### Task 7.3: Update main README
**File**: `README.md` (update)  
**Priority**: Low  
**Estimated Time**: 1 hour  
**Dependencies**: Task 7.1

**Updates Required**:
- [ ] Add ADS-B tracking to features list
- [ ] Add screenshot/GIF of aircraft tracking on map
- [ ] Update "What's New" section
- [ ] Link to ADS-B documentation

#### Task 7.4: Create release notes
**File**: `docs/releases/RELEASE_NOTES_2602_2_0.md` (new)  
**Priority**: High  
**Estimated Time**: 2 hours  
**Dependencies**: All above tasks

**Sections Required**:
- [ ] New Features: ADS-B tracking with dump1090
- [ ] Breaking Changes: None (new feature, opt-in)
- [ ] Migration Notes: None required
- [ ] Known Issues: List any Phase 1 limitations
- [ ] Future Enhancements: Preview Phase 2+ features

---

### 8. Translations

#### Task 8.1: Add English translation keys
**File**: `translations/en.json` (update)  
**Priority**: High  
**Estimated Time**: 1 hour  
**Dependencies**: Task 4.1-4.3

**Keys to Add**:
- [ ] Config flow steps (adsb_setup, adsb_dump1090, adsb_add_aircraft)
- [ ] Entity names (device_tracker.aircraft)
- [ ] Error messages (cannot_connect, invalid_registration)
- [ ] Tooltips and help text

**Pattern**: Follow existing CheckWX integration translation structure

#### Task 8.2: Translate to German, Spanish, French
**File**: `translations/{de,es,fr}.json` (update)  
**Priority**: Medium  
**Estimated Time**: 2 hours (use automated translation agent)  
**Dependencies**: Task 8.1

**Requirements**:
- [ ] Use automated translation agent (runSubagent tool)
- [ ] Preserve aviation terminology in all languages
- [ ] Validate with `pytest tests/test_languages.py`
- [ ] Verify deep key parity across all languages

---

## Validation Checklist

Before completing Phase 1, verify:

### Functionality
- [ ] dump1090 client successfully connects and parses data
- [ ] Device tracker entities appear on Home Assistant map
- [ ] Aircraft state changes correctly (home/away/airborne)
- [ ] Configuration flow guides user through setup
- [ ] Dashboard cards render correctly

### Code Quality
- [ ] All tests pass (`pytest tests/test_adsb*.py`)
- [ ] 80%+ test coverage for new code
- [ ] MyPy type checking passes (no errors)
- [ ] Flake8 linting passes (no E9/F63/F7/F82 errors)
- [ ] Code complexity ≤15 for all functions

### Documentation
- [ ] Feature documentation complete and reviewed
- [ ] Hardware setup guide tested on fresh Raspberry Pi
- [ ] Translation keys complete in all 4 languages
- [ ] Release notes drafted

### User Experience
- [ ] Setup wizard tested by non-technical user
- [ ] Error messages clear and actionable
- [ ] Dashboard cards display correctly on mobile
- [ ] Help tooltips answer common questions

### Security
- [ ] No API keys/passwords in logs
- [ ] All user input sanitized (registration, host, port)
- [ ] File operations use executor jobs (async-safe)
- [ ] Exception handling specific (no broad catches)

---

## Risk Mitigation

### Technical Risks

**Risk**: dump1090 JSON format varies between versions  
**Mitigation**: Test with multiple dump1090 versions (v3, v4, v5), handle missing fields gracefully

**Risk**: Network latency causes stale data  
**Mitigation**: Show data age in UI, mark unknown after N seconds without update

**Risk**: Cache directory permission errors  
**Mitigation**: Follow OWM pattern - lazy directory creation, graceful degradation, user notification

### User Experience Risks

**Risk**: Users don't have dump1090 hardware  
**Mitigation**: Clear documentation on hardware requirements, promote Phase 2 (OpenSky free API)

**Risk**: Setup too complex for non-technical pilots  
**Mitigation**: Step-by-step wizard, test connection buttons, video tutorial, community support

**Risk**: Expectations exceed capabilities (want global tracking)  
**Mitigation**: Set clear expectations - Phase 1 is local only, Phase 2+ adds API sources

---

## Time Estimate Summary

| Category | Tasks | Estimated Hours |
|----------|-------|-----------------|
| Data Models & Architecture | 3 | 9 hours |
| Data Source Clients | 5 | 27 hours |
| Data Source Manager | 1 | 4 hours |
| Device Tracker Entity | 2 | 7 hours |
| Configuration Flow | 4 | 14 hours |
| Dashboard Integration | 2 | 4 hours |
| Testing | 7 | 22 hours |
| Documentation | 4 | 12 hours |
| Translations | 2 | 3 hours |
| **Total** | **30 tasks** | **102 hours** |

**Estimated Duration**: 3-4 weeks (assuming 25-35 hours/week dedicated development time)

**Breakdown by Priority**:
- **High Priority** (Critical Path): 18 tasks, 75 hours
- **Medium Priority** (Important): 8 tasks, 20 hours
- **Low Priority** (Nice-to-have): 4 tasks, 7 hours

---

## Dependencies Graph

```
1.1 (AircraftData) ──┬──> 1.2 (ADSBClientBase) ──┬──> 2.1 (Dump1090Client)
                     │                           │
                     │                           └──> 3.1 (DeviceTracker)
                     │
                     └──> 6.1 (Tests: Models)
                     
2.1 (Dump1090) ──┬──> 2.2 (Connection Testing)
                 │
                 ├──> 4.2 (Config: dump1090)
                 │
                 └──> 6.3 (Tests: Dump1090)

3.1 (DeviceTracker) ──┬──> 3.2 (__init__ setup)
                      │
                      ├──> 5.1 (Dashboard Card)
                      │
                      └──> 6.4 (Tests: Tracker)

4.1 (Config: ADS-B) ──> 4.2 (Config: dump1090) ──> 4.3 (Config: Aircraft) ──> 4.4 (Options Flow)

All Config Tasks ──> 8.1 (Translations: EN) ──> 8.2 (Translations: Other)

All Development Tasks ──> 7.1 (Docs: Feature) ──> 7.4 (Release Notes)
```

---

## Next Steps

1. **Review** this task list with team/community
2. **Prioritize** any missing tasks or dependencies
3. **Set up** development environment:
   - Raspberry Pi with dump1090 installed
   - Test Home Assistant instance
   - Sample aircraft.json files for testing
4. **Begin implementation** with Task 1.1 (AircraftData dataclass)
5. **Daily standups** to track progress and blockers
6. **Weekly demos** to stakeholders (show working features)

---

**Document Version**: 1.0  
**Last Updated**: 22 January 2026  
**Status**: Ready for implementation
