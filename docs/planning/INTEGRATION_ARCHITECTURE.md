# External Integrations Architecture

## Overview

This document describes the unified architecture for managing external data sources (APIs, XML feeds, etc.) in Hangar Assistant.

## Design Principles

1. **Centralized Management**: All integrations configured through single menu
2. **Backward Compatibility**: Existing installations must not break
3. **Respectful Data Access**: Always cache, never poll unnecessarily
4. **Graceful Degradation**: Integration failures don't break core functionality
5. **User Control**: Easy enable/disable, clear configuration
6. **Fail Safe**: Core aviation sensors continue working even if all integrations fail

## Configuration Structure

### Location
All integration settings stored in `entry.data["integrations"]` namespace.

### Schema
```python
entry.data["integrations"] = {
    "openweathermap": {
        "enabled": bool,              # Master toggle
        "api_key": str,               # Password field, empty if not configured
        "cache_enabled": bool,        # Enable persistent caching
        "update_interval": int,       # Minutes between API calls (default: 10)
        "cache_ttl": int,             # Cache validity minutes (default: 10)
        "consecutive_failures": int,  # Track failures for auto-disable
        "last_error": str,            # Last error message
        "last_success": str           # ISO timestamp of last successful fetch
    },
    "notams": {
        "enabled": bool,              # Master toggle (default: True for new installs)
        "update_time": str,           # "HH:MM" format (default: "02:00")
        "cache_days": int,            # Days to retain cached NOTAMs (default: 7)
        "last_update": str,           # ISO timestamp of last successful update
        "consecutive_failures": int,  # Track failures for alerts
        "last_error": str,            # Last error message
        "stale_cache_allowed": bool   # Allow using expired cache on failure (default: True)
    }
}
```

## Graceful Degradation & Error Handling

### Failure Modes by Integration Type

**Paid APIs (OpenWeatherMap):**
- **Failure threshold**: 3 consecutive failures
- **Action**: Automatically disable integration, preserve last successful cache
- **User notification**: Persistent notification with error details
- **Recovery**: User must manually re-enable after fixing issue (e.g., invalid API key)
- **Reasoning**: Avoid wasting API calls and charges on broken configuration

**Free Services (NOTAMs):**
- **Failure threshold**: Unlimited (keep trying)
- **Action**: Use stale cache data if available, create warning sensor
- **User notification**: Warning-level log message, sensor shows stale data age
- **Recovery**: Automatic on next scheduled update
- **Reasoning**: Stale NOTAMs better than no NOTAMs; service is free

### Error Handling Implementation

**OpenWeatherMap Client (`utils/openweathermap.py`):**
```python
async def get_weather_data(self, latitude: float, longitude: float) -> Optional[Dict]:
    """Fetch weather data with graceful failure handling."""
    try:
        # Try API call
        data = await self._fetch_from_api(latitude, longitude)
        
        if data:
            # Success - reset failure counter
            await self._reset_failure_counter()
            return data
            
    except Exception as e:
        _LOGGER.error("OWM API request failed: %s", e)
        await self._increment_failure_counter(str(e))
        
        # Check if we should auto-disable
        if await self._should_auto_disable():
            await self._auto_disable_integration(
                "OpenWeatherMap disabled after 3 consecutive failures. "
                "Please check your API key and re-enable in Settings → Integrations."
            )
            
        # Return cached data if available
        cached = self._read_persistent_cache(latitude, longitude)
        if cached:
            _LOGGER.warning("Using cached OWM data due to API failure")
            return cached
            
    return None
    
async def _increment_failure_counter(self, error_msg: str) -> None:
    """Track consecutive failures."""
    integrations = self.entry.data.get("integrations", {})
    owm_config = integrations.get("openweathermap", {})
    
    failures = owm_config.get("consecutive_failures", 0) + 1
    owm_config["consecutive_failures"] = failures
    owm_config["last_error"] = error_msg
    
    new_data = {**self.entry.data, "integrations": integrations}
    self.hass.config_entries.async_update_entry(self.entry, data=new_data)
    
async def _reset_failure_counter(self) -> None:
    """Reset failure counter on successful fetch."""
    integrations = self.entry.data.get("integrations", {})
    owm_config = integrations.get("openweathermap", {})
    
    owm_config["consecutive_failures"] = 0
    owm_config["last_error"] = None
    owm_config["last_success"] = datetime.now().isoformat()
    
    new_data = {**self.entry.data, "integrations": integrations}
    self.hass.config_entries.async_update_entry(self.entry, data=new_data)
    
async def _should_auto_disable(self) -> bool:
    """Check if integration should be auto-disabled."""
    integrations = self.entry.data.get("integrations", {})
    owm_config = integrations.get("openweathermap", {})
    return owm_config.get("consecutive_failures", 0) >= 3
    
async def _auto_disable_integration(self, message: str) -> None:
    """Automatically disable integration after repeated failures."""
    integrations = self.entry.data.get("integrations", {})
    owm_config = integrations.get("openweathermap", {})
    
    owm_config["enabled"] = False
    
    new_data = {**self.entry.data, "integrations": integrations}
    self.hass.config_entries.async_update_entry(self.entry, data=new_data)
    
    # Create persistent notification
    await self.hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "title": "Hangar Assistant: Integration Disabled",
            "message": message,
            "notification_id": "hangar_assistant_owm_disabled"
        }
    )
    
    _LOGGER.error("Auto-disabled OWM integration: %s", message)
```

**NOTAM Client (`utils/notam.py`):**
```python
async def fetch_notams(self) -> Tuple[List[Dict], bool]:
    """Fetch NOTAMs with stale cache fallback.
    
    Returns:
        Tuple of (notams_list, is_stale_data)
    """
    try:
        # Try fresh fetch
        notams = await self._fetch_from_nats()
        
        if notams:
            # Success - reset failure counter
            await self._reset_failure_counter()
            return notams, False
            
    except Exception as e:
        _LOGGER.error("NOTAM fetch failed: %s", e)
        await self._increment_failure_counter(str(e))
        
        # Try stale cache if allowed
        stale_notams = self._read_stale_cache()
        if stale_notams:
            cache_age = self._get_cache_age_hours()
            _LOGGER.warning(
                "Using stale NOTAM cache (%d hours old) due to fetch failure",
                cache_age
            )
            return stale_notams, True
            
        # No cache available
        _LOGGER.error("No NOTAM data available (fresh or cached)")
        return [], False
        
    return [], False
    
def _read_stale_cache(self) -> Optional[List[Dict]]:
    """Read cached NOTAMs even if expired."""
    if not self.cache_file.exists():
        return None
        
    try:
        with open(self.cache_file, 'r') as f:
            cached = json.load(f)
        return cached.get("notams", [])
        
    except (OSError, json.JSONDecodeError):
        return None
        
def _get_cache_age_hours(self) -> int:
    """Get age of cached data in hours."""
    if not self.cache_file.exists():
        return 0
        
    try:
        with open(self.cache_file, 'r') as f:
            cached = json.load(f)
        cache_time = datetime.fromisoformat(cached["cached_at"])
        return int((datetime.now() - cache_time).total_seconds() / 3600)
    except:
        return 0
```

### Warning Sensors

**Integration Health Sensor:**
```python
class IntegrationHealthSensor(SensorEntity):
    """Sensor showing integration health status."""
    
    @property
    def state(self):
        """Return overall integration health."""
        integrations = self.entry.data.get("integrations", {})
        
        issues = []
        for name, config in integrations.items():
            if not config.get("enabled"):
                continue
                
            failures = config.get("consecutive_failures", 0)
            if failures > 0:
                issues.append(f"{name}: {failures} failures")
                
        if not issues:
            return "healthy"
        elif len(issues) == 1:
            return "warning"
        else:
            return "critical"
            
    @property
    def extra_state_attributes(self):
        """Include integration details."""
        integrations = self.entry.data.get("integrations", {})
        
        status = {}
        for name, config in integrations.items():
            status[name] = {
                "enabled": config.get("enabled", False),
                "consecutive_failures": config.get("consecutive_failures", 0),
                "last_error": config.get("last_error"),
                "last_success": config.get("last_success")
            }
            
        return {"integrations": status}
```

**NOTAM Staleness Sensor:**
```python
class NOTAMStalenessWarning(BinarySensorEntity):
    """Binary sensor warning when NOTAM data is stale."""
    
    @property
    def is_on(self):
        """Return True if NOTAM data is stale."""
        notam_config = self.entry.data.get("integrations", {}).get("notams", {})
        last_update = notam_config.get("last_update")
        
        if not last_update:
            return True  # Never updated
            
        update_time = datetime.fromisoformat(last_update)
        hours_old = (datetime.now() - update_time).total_seconds() / 3600
        
        # Warn if data more than 48 hours old
        return hours_old > 48
        
    @property
    def extra_state_attributes(self):
        """Include staleness details."""
        notam_config = self.entry.data.get("integrations", {}).get("notams", {})
        last_update = notam_config.get("last_update")
        
        if last_update:
            update_time = datetime.fromisoformat(last_update)
            hours_old = int((datetime.now() - update_time).total_seconds() / 3600)
        else:
            hours_old = None
            
        return {
            "hours_old": hours_old,
            "last_update": last_update,
            "last_error": notam_config.get("last_error"),
            "consecutive_failures": notam_config.get("consecutive_failures", 0)
        }
```

### User Notifications

**Persistent Notification (Critical Issues):**
- Auto-disabled integrations (OWM after 3 failures)
- Invalid credentials detected
- Service quota exceeded

**Warning Sensor (Non-Critical):**
- Stale NOTAM data (> 48 hours)
- Intermittent failures (< 3)
- Cache being used due to temporary outage

**Log Messages:**
- Debug: Successful updates, cache hits
- Info: Integration enabled/disabled, scheduled updates
- Warning: Using stale cache, temporary failures
- Error: Repeated failures, auto-disable triggered

### Recovery Procedures

**Automatic Recovery:**
- Free services (NOTAM): Keep trying at scheduled intervals
- Next successful fetch resets failure counter
- Stale cache warnings clear automatically

**Manual Recovery:**
- Paid APIs (OWM): User must re-enable after fixing issue
- Config flow shows last error message for troubleshooting
- "Test Connection" button to verify credentials before enabling

### Testing Failure Scenarios

**Unit test coverage required:**
1. Network timeout during fetch
2. Invalid API credentials
3. Malformed response data
4. Service temporarily unavailable (503)
5. Rate limit exceeded (429)
6. Cache file corruption
7. Disk full (cache write failure)
8. Multiple consecutive failures
9. Auto-disable and re-enable flow
10. Stale cache fallback

**Test helpers:**
```python
def test_owm_auto_disables_after_three_failures():
    """Test OWM auto-disables after 3 consecutive failures."""
    # Simulate 3 API failures
    for _ in range(3):
        result = await client.get_weather_data(51.2, -1.2)
        
    # Check integration disabled
    integrations = entry.data["integrations"]
    assert integrations["openweathermap"]["enabled"] is False
    assert integrations["openweathermap"]["consecutive_failures"] == 3
    
def test_notam_uses_stale_cache_on_failure():
    """Test NOTAM falls back to stale cache."""
    # Pre-populate stale cache (3 days old)
    old_notams = [{"id": "TEST", "text": "Old NOTAM"}]
    client._write_cache(old_notams)
    
    # Simulate fetch failure
    with patch.object(client, "_fetch_from_nats", side_effect=Exception("Network error")):
        notams, is_stale = await client.fetch_notams()
        
    assert notams == old_notams
    assert is_stale is True
```

## Migration Strategy

### Existing Installations (OWM)

Current OWM settings location: `entry.data["settings"]`
```python
{
    "openweathermap_api_key": str,
    "openweathermap_enabled": bool,
    "openweathermap_cache_enabled": bool,
    "openweathermap_update_interval": int,
    "openweathermap_cache_ttl": int
}
```

**Migration approach:**
1. Check if `entry.data["integrations"]` exists
2. If not, create it and migrate OWM settings from `entry.data["settings"]`
3. Preserve all existing values (no defaults applied to existing installs)
4. Leave original settings in place for rollback capability
5. All future reads use `entry.data["integrations"]`

**Migration code location:** `__init__.py` in `async_setup_entry()`

```python
async def _migrate_to_integrations(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate OWM settings to integrations namespace."""
    if "integrations" not in entry.data:
        settings = entry.data.get("settings", {})
        
        integrations = {
            "openweathermap": {
                "enabled": settings.get("openweathermap_enabled", False),
                "api_key": settings.get("openweathermap_api_key", ""),
                "cache_enabled": settings.get("openweathermap_cache_enabled", True),
                "update_interval": settings.get("openweathermap_update_interval", 10),
                "cache_ttl": settings.get("openweathermap_cache_ttl", 10)
            },
            "notams": {
                "enabled": False,  # Existing installs: off by default
                "update_time": "02:00",
                "cache_days": 7,
                "last_update": None
            }
        }
        
        new_data = {**entry.data, "integrations": integrations}
        hass.config_entries.async_update_entry(entry, data=new_data)
        
        _LOGGER.info("Migrated OWM settings to integrations namespace")
```

### New Installations

Default settings for fresh installs:
```python
{
    "integrations": {
        "openweathermap": {
            "enabled": False,
            "api_key": "",
            "cache_enabled": True,
            "update_interval": 10,
            "cache_ttl": 10
        },
        "notams": {
            "enabled": True,  # Free service, on by default
            "update_time": "02:00",
            "cache_days": 7,
            "last_update": None
        }
    }
}
```

## Config Flow Changes

### Menu Structure

**Main menu (`async_step_init`):**
```
- Airfield
- Hangar
- Aircraft
- Pilot
- Briefing Settings
- Integrations  ← NEW
- General Settings
```

**Integrations submenu (`async_step_integrations`):**
```
- OpenWeatherMap
- NOTAMs
- [Future: METAR/TAF]
- [Future: ADS-B Exchange]
```

### Integration Forms

**OpenWeatherMap (`async_step_integrations_openweathermap`):**
- Enabled: toggle (default: False)
- API Key: password field (optional)
- Cache Enabled: toggle (default: True)
- Update Interval: selector (5, 10, 15, 30, 60 minutes)
- Cache TTL: selector (5, 10, 15, 30 minutes)

**NOTAMs (`async_step_integrations_notams`):**
- Enabled: toggle (default: True for new installs, False for existing)
- Update Time: time selector (default: "02:00")
- Cache Days: selector (1, 3, 7, 14, 30 days)
- Action: "Update Now" button

## NOTAM Integration Details

### Data Source
UK NATS Aeronautical Information Service (AIS):
- URL: `https://pibs.nats.co.uk/operational/pibs/PIB.xml`
- Format: XML
- Update frequency: Multiple times daily
- Coverage: UK airspace, aerodromes, navigation aids

### Client Architecture

**File:** `custom_components/hangar_assistant/utils/notam.py`

```python
class NOTAMClient:
    """Client for UK NATS NOTAM XML feed with persistent caching."""
    
    def __init__(self, hass: HomeAssistant, cache_days: int = 7):
        self.hass = hass
        self.cache_days = cache_days
        self.cache_dir = hass.config.path("hangar_assistant_cache")
        self.cache_file = self.cache_dir / "notams.json"
        
    async def fetch_notams(self) -> List[Dict[str, Any]]:
        """Fetch NOTAMs from NATS or cache."""
        # Check cache first
        cached = self._read_cache()
        if cached:
            return cached
            
        # Fetch fresh data
        return await self._fetch_from_nats()
        
    async def _fetch_from_nats(self) -> List[Dict[str, Any]]:
        """Download and parse NATS PIB XML."""
        session = self.hass.helpers.aiohttp_client.async_get_clientsession()
        
        async with session.get(NATS_PIB_URL) as response:
            if response.status == 200:
                xml_content = await response.text()
                notams = self._parse_pib_xml(xml_content)
                self._write_cache(notams)
                return notams
                
        return []
        
    def _parse_pib_xml(self, xml_content: str) -> List[Dict[str, Any]]:
        """Parse PIB XML into structured NOTAM data."""
        # Use xml.etree.ElementTree for parsing
        # Extract: ID, location, category, start/end times, text
        pass
        
    def _read_cache(self) -> Optional[List[Dict[str, Any]]]:
        """Read cached NOTAMs if within retention period."""
        if not self.cache_file.exists():
            return None
            
        try:
            with open(self.cache_file, 'r') as f:
                cached = json.load(f)
                
            cache_time = datetime.fromisoformat(cached["cached_at"])
            if datetime.now() - cache_time < timedelta(days=self.cache_days):
                return cached["notams"]
                
        except (OSError, json.JSONDecodeError, KeyError):
            pass
            
        return None
        
    def _write_cache(self, notams: List[Dict[str, Any]]) -> None:
        """Write NOTAMs to persistent cache."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        cached = {
            "cached_at": datetime.now().isoformat(),
            "notams": notams
        }
        
        with open(self.cache_file, 'w') as f:
            json.dump(cached, f, indent=2)
            
    def filter_by_location(self, notams: List[Dict], icao: str = None, 
                          lat: float = None, lon: float = None,
                          radius_nm: float = 50) -> List[Dict]:
        """Filter NOTAMs by ICAO code or proximity to coordinates."""
        pass
        
    def clear_cache(self) -> None:
        """Remove cached NOTAM data."""
        if self.cache_file.exists():
            self.cache_file.unlink()
```

### Scheduled Updates

**Implementation in `__init__.py`:**
```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up integration and schedule NOTAM updates."""
    
    integrations = entry.data.get("integrations", {})
    notam_config = integrations.get("notams", {})
    
    if notam_config.get("enabled"):
        update_time = notam_config.get("update_time", "02:00")
        hour, minute = map(int, update_time.split(":"))
        
        async def update_notams(now):
            """Scheduled NOTAM update."""
            notam_client = NOTAMClient(hass, notam_config.get("cache_days", 7))
            try:
                notams = await notam_client.fetch_notams()
                _LOGGER.info("Updated %d NOTAMs at scheduled time", len(notams))
                
                # Update last_update timestamp
                new_data = {**entry.data}
                new_data["integrations"]["notams"]["last_update"] = datetime.now().isoformat()
                hass.config_entries.async_update_entry(entry, data=new_data)
                
            except Exception as e:
                _LOGGER.error("NOTAM update failed: %s", e)
        
        # Schedule daily update
        async_track_time_change(hass, update_notams, hour=hour, minute=minute)
```

### NOTAM Sensor Entities

**Sensor per airfield:**
- Entity ID: `sensor.{airfield_slug}_notams`
- State: Count of active NOTAMs within 50nm
- Attributes:
  - `notams`: List of NOTAM dicts (ID, category, text, start, end)
  - `airfield_notams`: NOTAMs specific to airfield ICAO
  - `area_notams`: NOTAMs within radius
  - `last_update`: Timestamp of last fetch

**Implementation in `sensor.py`:**
```python
class AirfieldNOTAMSensor(HangarSensorBase):
    """Sensor showing active NOTAMs for an airfield."""
    
    def __init__(self, hass, config, entry_data):
        super().__init__(hass, config, entry_data)
        self._notam_client = NOTAMClient(hass)
        
    @property
    def name(self):
        return f"{self.config['name']} NOTAMs"
        
    @property
    def icon(self):
        return "mdi:alert-circle-outline"
        
    @property
    def state(self):
        """Return count of active NOTAMs."""
        notams = self._get_active_notams()
        return len(notams) if notams else 0
        
    @property
    def extra_state_attributes(self):
        """Include NOTAM details in attributes."""
        notams = self._get_active_notams()
        
        return {
            "notams": notams,
            "airfield_notams": [n for n in notams if self._is_airfield_notam(n)],
            "area_notams": [n for n in notams if not self._is_airfield_notam(n)],
            "last_update": self._notam_client.get_cache_time()
        }
        
    def _get_active_notams(self) -> List[Dict]:
        """Get NOTAMs relevant to this airfield."""
        all_notams = self._notam_client.fetch_notams()
        
        # Filter by ICAO or coordinates
        icao = self.config.get("icao")
        lat = self.config.get("latitude")
        lon = self.config.get("longitude")
        
        return self._notam_client.filter_by_location(
            all_notams, icao=icao, lat=lat, lon=lon, radius_nm=50
        )
```

## Translation Keys

### strings.json
```json
{
  "config": {
    "step": {
      "integrations": {
        "title": "Integrations",
        "description": "Manage external data sources",
        "menu_options": {
          "openweathermap": "OpenWeatherMap",
          "notams": "NOTAMs"
        }
      },
      "integrations_openweathermap": {
        "title": "OpenWeatherMap Configuration",
        "description": "Configure OWM One Call API 3.0",
        "data": {
          "enabled": "Enable OpenWeatherMap",
          "api_key": "API Key",
          "cache_enabled": "Enable Caching",
          "update_interval": "Update Interval (minutes)",
          "cache_ttl": "Cache TTL (minutes)"
        }
      },
      "integrations_notams": {
        "title": "NOTAM Configuration",
        "description": "Configure UK NATS NOTAM feed",
        "data": {
          "enabled": "Enable NOTAMs",
          "update_time": "Daily Update Time",
          "cache_days": "Cache Retention (days)"
        }
      }
    }
  }
}
```

## Testing Strategy

### Unit Tests

**test_notam_client.py:**
- Test XML parsing with sample PIB data
- Test cache read/write/expiration
- Test location filtering (ICAO and coordinates)
- Test graceful handling of malformed XML
- Test network error handling

**test_integration_config_flow.py:**
- Test integrations menu creation
- Test OWM migration from settings to integrations
- Test NOTAM enable/disable
- Test backward compatibility (existing installs)

**test_notam_sensor.py:**
- Test sensor creation per airfield
- Test NOTAM filtering by proximity
- Test attribute population
- Test state updates after scheduled fetch

### Mock Data

**Sample PIB XML structure:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<PIB>
  <NOTAM>
    <ID>C0123/21</ID>
    <ICAO>EGLL</ICAO>
    <StartDate>2021-01-15T00:00:00Z</StartDate>
    <EndDate>2021-01-31T23:59:59Z</EndDate>
    <Category>AERODROME</Category>
    <Text>RWY 09L/27R CLOSED FOR MAINTENANCE</Text>
  </NOTAM>
  <!-- More NOTAMs -->
</PIB>
```

## Implementation Order

1. ✅ Update copilot instructions (warnings as failures)
2. ✅ Document integrations architecture (this file)
3. Create integration config flow menu
4. Implement OWM migration logic
5. Add NOTAM client with XML parsing
6. Implement scheduled NOTAM updates
7. Create NOTAM sensor entities
8. Add translations (EN, DE, ES, FR)
9. Write comprehensive unit tests
10. Update documentation

## Future Enhancements

### Additional Integrations
- **METAR/TAF**: Aviation weather reports (NOAA or Aviation Weather Center)
- **ADS-B Exchange**: Live traffic near airfield
- **Flight Radar 24**: Traffic alerts
- **Weather Underground**: Hyperlocal weather stations
- **Windy.com**: Wind forecasts and alerts

### Integration Features
- Health monitoring dashboard
- Integration-specific sensors (e.g., "API calls remaining")
- Batch update all integrations service
- Integration diagnostics (last update, error count, cache stats)

## Questions for User

1. Should NOTAM updates also trigger on Home Assistant restart?
2. Do you want NOTAM sensors to filter by category (e.g., only show runway/airspace NOTAMs)?
3. Should we parse NOTAM Q-codes for structured filtering?
4. Do you want NOTAM alerts as binary sensors (e.g., "Critical NOTAM Active")?
5. Should the integration menu show integration health status?
