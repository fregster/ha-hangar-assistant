# OpenWeatherMap API Integration Plan

## Executive Summary

Add optional OpenWeatherMap (OWM) One Call API 3.0 integration to provide:
- **Backup data source** when local sensors are unavailable
- **Default data source** for airfields without sensor configuration
- **Forecast data** (48hr hourly + 8 day daily)
- **Government weather alerts** from national met services
- **Minutely precipitation forecast** for departure timing
- **AI briefing enrichment** with forecast and alert data

**Principle**: Non-breaking, optional, enhances existing functionality without replacing it.

---

## 1. Configuration Architecture

### 1.1 Global Settings (Integration Level)

**Location**: Settings → Global Configuration → General Settings

```yaml
# New fields in settings:
openweathermap_api_key: Optional[str]
  - Description: "OpenWeatherMap API Key (optional)"
  - Help text: "Sign up at openweathermap.org for free tier (1000 calls/day)"
  - Validation: Length check, format validation
  
openweathermap_enabled: bool
  - Description: "Enable OpenWeatherMap Integration"
  - Default: False
  - Only visible if API key provided

openweathermap_update_interval: int
  - Description: "Update Interval (minutes)"
  - Default: 10
  - Range: 5-60
  - Help: "OWM data updates every 10 minutes. More frequent calls use API quota."
```

### 1.2 Per-Airfield Settings

**Location**: Airfield Add/Edit form

```yaml
# New optional field for each airfield:
weather_data_source: SelectSelector
  - Options:
    * "sensors" - Use Home Assistant sensors (default, current behavior)
    * "openweathermap" - Use OWM API exclusively
    * "hybrid" - OWM primary, fallback to sensors
    * "sensors_backup_owm" - Sensors primary, fallback to OWM
  - Default: "sensors" (backward compatible)
  - Only visible if OWM API key configured globally

use_owm_forecast: bool
  - Description: "Include OWM forecast data"
  - Default: True
  - Enables hourly/daily forecast sensors
  
use_owm_alerts: bool
  - Description: "Include government weather alerts"
  - Default: True
  - Creates alert binary sensor
```

### 1.3 Data Source Priority Matrix

| Configuration | Behavior |
|---------------|----------|
| **No API Key** | Sensors only (current behavior) |
| **API Key + "sensors"** | Sensors only, OWM disabled for this airfield |
| **API Key + "openweathermap"** | OWM only, sensors ignored |
| **API Key + "hybrid"** | OWM primary, fallback to sensors if OWM unavailable |
| **API Key + "sensors_backup_owm"** | Sensors primary, fallback to OWM if sensors unavailable |

---

## 2. Data Points Mapping

### 2.1 Current Weather (Sensor Replacement/Augmentation)

| Data Point | OWM API Field | HA Sensor Replacement | Unit | Priority |
|------------|---------------|----------------------|------|----------|
| Temperature | `current.temp` | `temp_sensor` | °C/°F | High |
| Dew Point | `current.dew_point` | `dp_sensor` | °C/°F | High |
| Pressure (QNH) | `current.pressure` | `pressure_sensor` or `global_pressure_sensor` | hPa | Critical |
| Wind Speed | `current.wind_speed` | `wind_sensor` | m/s, kt, mph | High |
| Wind Direction | `current.wind_deg` | `wind_dir_sensor` | degrees | High |
| Wind Gust | `current.wind_gust` | N/A (new) | m/s, kt, mph | Medium |
| Visibility | `current.visibility` | N/A (new) | km/mi | Medium |
| Cloud Coverage | `current.clouds` | N/A (new) | % | Medium |
| Humidity | `current.humidity` | N/A (new) | % | Low |
| UV Index | `current.uvi` | N/A (new) | index | Low |

### 2.2 New Sensors (OWM-Only Features)

#### **Forecast Sensors**

**`sensor.{airfield}_weather_forecast_hourly`**
- State: JSON array of 48 hourly forecasts
- Attributes:
  ```python
  {
    "forecast": [
      {
        "datetime": "2026-01-21T15:00:00",
        "temperature": 12.5,
        "dew_point": 8.2,
        "pressure": 1013,
        "wind_speed": 15,
        "wind_direction": 270,
        "wind_gust": 20,
        "visibility": 10,
        "clouds": 45,
        "precipitation_probability": 0.15,
        "weather": "broken clouds"
      },
      // ... 47 more hours
    ],
    "source": "OpenWeatherMap",
    "last_updated": "2026-01-21T14:35:00"
  }
  ```

**`sensor.{airfield}_weather_forecast_daily`**
- State: JSON array of 8 daily forecasts
- Attributes:
  ```python
  {
    "forecast": [
      {
        "date": "2026-01-21",
        "temp_min": 8.1,
        "temp_max": 15.3,
        "temp_morning": 9.5,
        "temp_day": 14.2,
        "temp_evening": 12.1,
        "temp_night": 8.8,
        "pressure": 1013,
        "wind_speed": 12,
        "wind_direction": 250,
        "clouds": 60,
        "precipitation_probability": 0.3,
        "precipitation_mm": 2.5,
        "summary": "Expect a day of partly cloudy with rain",
        "sunrise": "2026-01-21T07:45:00",
        "sunset": "2026-01-21T16:30:00"
      },
      // ... 7 more days
    ]
  }
  ```

**`sensor.{airfield}_precipitation_forecast`**
- State: Minutes until next precipitation (0 if currently raining, 60+ if no rain in next hour)
- Attributes:
  ```python
  {
    "minutely_forecast": [
      {"time": "14:35", "precipitation": 0},
      {"time": "14:36", "precipitation": 0},
      // ... 60 minutes
    ],
    "next_rain_minutes": 42,
    "rain_duration_minutes": 15,
    "max_intensity": 1.2  # mm/h
  }
  ```
- Use case: "Can I complete pre-flight before rain starts?"

#### **Alert Sensors**

**`binary_sensor.{airfield}_government_weather_alert`**
- Device class: `SAFETY`
- State: ON if active alert, OFF if none
- Attributes:
  ```python
  {
    "active_alerts": [
      {
        "sender": "UK Met Office",
        "event": "Wind Warning",
        "severity": "Moderate",
        "start": "2026-01-21T18:00:00",
        "end": "2026-01-22T06:00:00",
        "description": "Strong winds expected. Gusts up to 50mph possible.",
        "tags": ["Wind"]
      }
    ],
    "alert_count": 1,
    "highest_severity": "Moderate"
  }
  ```

**`sensor.{airfield}_uv_index`**
- Device class: `MEASUREMENT`
- State: Current UV index (0-11+)
- Attributes:
  ```python
  {
    "level": "Moderate",  # Low, Moderate, High, Very High, Extreme
    "max_today": 4.2,
    "recommendation": "Wear sunglasses and sunscreen if flying VFR"
  }
  ```

### 2.3 Data Enrichment (Existing Sensors)

When OWM is enabled, **augment** existing sensor attributes:

**Example: `sensor.{airfield}_density_altitude`**
```python
# Current attributes:
{
  "temperature": 15,
  "pressure": 1013,
  "elevation": 120
}

# WITH OWM enrichment:
{
  "temperature": 15,
  "pressure": 1013,
  "elevation": 120,
  "data_source": "openweathermap",  # NEW
  "forecast_1hr": 1450,  # NEW: DA in 1 hour
  "forecast_3hr": 1520,  # NEW: DA in 3 hours
  "trend": "increasing"  # NEW
}
```

---

## 3. User Workflows & Use Cases

### 3.1 Scenario: Remote Airfield Without Sensors

**User**: Has an airfield but no weather station integration

**Workflow**:
1. User configures airfield with name, lat/lon, elevation, runways
2. User does NOT configure temp/dp/pressure/wind sensors
3. User adds OWM API key in General Settings
4. **Result**: All sensors automatically use OWM data
   - No sensor setup required
   - Immediate weather data
   - All calculations (DA, carb risk, runway selection) work

**Dashboard shows**:
- Current weather from OWM
- Forecast for next 48 hours
- Government alerts if any
- All aviation calculations function normally

### 3.2 Scenario: Primary Sensors with OWM Backup

**User**: Has local weather station but wants redundancy

**Workflow**:
1. User configures airfield with local sensors (temp, DP, pressure, wind)
2. User adds OWM API key
3. User sets airfield data source to `"sensors_backup_owm"`
4. **Result**: Uses local sensors, switches to OWM if sensors fail

**Failure handling**:
```python
# Example: Temperature sensor becomes unavailable
if temp_sensor.state in ["unavailable", "unknown", None]:
    # Fall back to OWM
    temperature = owm_data["current"]["temp"]
    _LOGGER.info("Using OWM temperature as backup")
```

### 3.3 Scenario: OWM Primary for Accuracy

**User**: Local sensors are low-quality; prefers OWM professional data

**Workflow**:
1. User sets data source to `"openweathermap"`
2. Local sensors ignored
3. **Result**: All data from OWM, more accurate pressure/visibility

### 3.4 Scenario: Forecast-Based Planning

**User**: Planning flights for next 3 days

**Workflow**:
1. User opens dashboard
2. Views 8-day forecast card (new)
3. Sees:
   - Daily highs/lows
   - Precipitation probability
   - Wind forecast
   - Government alerts
4. **Result**: Can plan flights around weather windows

**Dashboard card example**:
```yaml
type: custom:apexcharts-card
header:
  title: "3-Day Forecast"
series:
  - entity: sensor.popham_weather_forecast_daily
    data_generator: |
      return entity.attributes.forecast.map(day => {
        return [new Date(day.date).getTime(), day.temp_max];
      });
```

### 3.5 Scenario: AI Briefing Enhancement

**User**: Requests AI pre-flight briefing

**Workflow**:
1. User triggers `refresh_ai_briefings` service or scheduled automation
2. AI retrieves:
   - Current weather (existing)
   - **OWM forecast data** (new)
   - **Government alerts** (new)
   - **Precipitation timing** (new)
3. AI briefing includes:

**Current briefing** (without OWM):
> "Current conditions at Popham: Temperature 12°C, dew point 8°C, QNH 1013hPa. Wind 270° at 12kt gusting 18kt. Density altitude 1250ft. Carb risk: Moderate. Runway 03 recommended (2kt crosswind)."

**Enhanced briefing** (with OWM):
> "Current conditions at Popham: Temperature 12°C, dew point 8°C, QNH 1013hPa. Wind 270° at 12kt gusting 18kt. Density altitude 1250ft. Carb risk: Moderate. Runway 03 recommended (2kt crosswind).
>
> **Forecast**: Temperature dropping to 9°C by 18:00, wind increasing to 15kt gusting 22kt from 260°. Rain expected in 42 minutes, lasting approximately 15 minutes.
>
> **Alert**: UK Met Office Wind Warning active 18:00-06:00 tomorrow. Gusts up to 50mph expected.
>
> **Recommendation**: Complete pre-flight within next 40 minutes to avoid rain. Consider delaying departure until after 18:00 due to wind warning."

---

## 4. Technical Implementation

### 4.1 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Config Flow                               │
│  - Global: OWM API key, enabled, update interval            │
│  - Per-airfield: data_source, use_forecast, use_alerts     │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              OWM Data Coordinator                            │
│  - Fetches data every N minutes                             │
│  - Caches responses                                          │
│  - Manages API rate limits                                   │
│  - Handles errors gracefully                                 │
└─────────────────────┬───────────────────────────────────────┘
                      │
         ┌────────────┴───────────┬──────────────┐
         ▼                        ▼              ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────┐
│  Current Sensors │   │ Forecast Sensors │   │Alert Sensors │
│  (augmented)     │   │   (new)          │   │   (new)      │
└──────────────────┘   └──────────────────┘   └──────────────┘
         │                        │                    │
         └────────────┬───────────┴────────────────────┘
                      ▼
          ┌───────────────────────┐
          │   Dashboard Display   │
          └───────────────────────┘
```

### 4.2 Core Components

#### **File: `utils/openweathermap.py`**

```python
"""OpenWeatherMap API integration for Hangar Assistant."""
from typing import Optional, Dict, Any
import aiohttp
import logging
from datetime import datetime, timedelta

_LOGGER = logging.getLogger(__name__)

OWM_API_BASE = "https://api.openweathermap.org/data/3.0/onecall"

class OpenWeatherMapClient:
    """Client for OpenWeatherMap One Call API 3.0."""

    def __init__(self, api_key: str, session: aiohttp.ClientSession):
        """Initialize OWM client."""
        self.api_key = api_key
        self.session = session
        self._cache = {}
        self._cache_timeout = timedelta(minutes=10)

    async def get_weather_data(
        self, 
        latitude: float, 
        longitude: float,
        units: str = "metric"
    ) -> Optional[Dict[str, Any]]:
        """Fetch current weather and forecast data."""
        cache_key = f"{latitude}_{longitude}"
        
        # Check cache
        if cache_key in self._cache:
            cached_data, cached_time = self._cache[cache_key]
            if datetime.now() - cached_time < self._cache_timeout:
                _LOGGER.debug("Using cached OWM data")
                return cached_data
        
        # Fetch from API
        url = f"{OWM_API_BASE}?lat={latitude}&lon={longitude}&appid={self.api_key}&units={units}"
        
        try:
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    self._cache[cache_key] = (data, datetime.now())
                    _LOGGER.info(f"Fetched OWM data for {latitude},{longitude}")
                    return data
                elif response.status == 401:
                    _LOGGER.error("OWM API key invalid")
                    return None
                elif response.status == 429:
                    _LOGGER.warning("OWM API rate limit exceeded")
                    return None
                else:
                    _LOGGER.error(f"OWM API error: {response.status}")
                    return None
        except aiohttp.ClientError as e:
            _LOGGER.error(f"OWM API request failed: {e}")
            return None

    def extract_current_weather(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract current weather from OWM response."""
        current = data.get("current", {})
        return {
            "temperature": current.get("temp"),
            "dew_point": current.get("dew_point"),
            "pressure": current.get("pressure"),
            "wind_speed": current.get("wind_speed"),
            "wind_direction": current.get("wind_deg"),
            "wind_gust": current.get("wind_gust"),
            "visibility": current.get("visibility", 10000) / 1000,  # m to km
            "clouds": current.get("clouds"),
            "humidity": current.get("humidity"),
            "uvi": current.get("uvi"),
            "weather": current.get("weather", [{}])[0].get("description", "Unknown"),
        }

    def extract_minutely_forecast(self, data: Dict[str, Any]) -> list:
        """Extract minutely precipitation forecast."""
        return data.get("minutely", [])

    def extract_hourly_forecast(self, data: Dict[str, Any]) -> list:
        """Extract hourly forecast (48 hours)."""
        return data.get("hourly", [])

    def extract_daily_forecast(self, data: Dict[str, Any]) -> list:
        """Extract daily forecast (8 days)."""
        return data.get("daily", [])

    def extract_alerts(self, data: Dict[str, Any]) -> list:
        """Extract government weather alerts."""
        return data.get("alerts", [])
```

#### **File: `sensor.py` (modifications)**

```python
# Add to async_setup_entry():

# Check if OWM is enabled
settings = entry.data.get("settings", {})
owm_api_key = settings.get("openweathermap_api_key")
owm_enabled = settings.get("openweathermap_enabled", False)

if owm_api_key and owm_enabled:
    # Initialize OWM client
    from .utils.openweathermap import OpenWeatherMapClient
    owm_client = OpenWeatherMapClient(owm_api_key, hass.helpers.aiohttp_client.async_get_clientsession())
    hass.data[DOMAIN]["owm_client"] = owm_client

# For each airfield, check data_source preference
for airfield in airfields:
    data_source = airfield.get("weather_data_source", "sensors")
    
    if data_source in ["openweathermap", "hybrid", "sensors_backup_owm"]:
        # Create OWM-enhanced sensors
        entities.append(OWMTemperatureSensor(hass, airfield, owm_client))
        # ... other sensors
        
        # Add forecast sensors if enabled
        if airfield.get("use_owm_forecast", True):
            entities.append(OWMHourlyForecastSensor(hass, airfield, owm_client))
            entities.append(OWMDailyForecastSensor(hass, airfield, owm_client))
            entities.append(OWMPrecipitationForecastSensor(hass, airfield, owm_client))
        
        # Add alert sensor if enabled
        if airfield.get("use_owm_alerts", True):
            entities.append(OWMWeatherAlertSensor(hass, airfield, owm_client))
```

### 4.3 Sensor Classes (Examples)

```python
class OWMTemperatureSensor(SensorEntity):
    """Temperature sensor with OWM data and sensor fallback."""

    def __init__(self, hass, airfield_config, owm_client):
        """Initialize sensor."""
        self.hass = hass
        self.config = airfield_config
        self.owm_client = owm_client
        self._id_slug = airfield_config["name"].lower().replace(" ", "_")
        self._sensor_entity = airfield_config.get("temp_sensor")
        self._data_source = airfield_config.get("weather_data_source", "sensors")

    @property
    def native_value(self):
        """Return temperature value with appropriate source."""
        if self._data_source == "openweathermap":
            return self._get_owm_temperature()
        elif self._data_source == "sensors":
            return self._get_sensor_temperature()
        elif self._data_source == "hybrid":
            # OWM primary, fallback to sensor
            owm_temp = self._get_owm_temperature()
            return owm_temp if owm_temp is not None else self._get_sensor_temperature()
        elif self._data_source == "sensors_backup_owm":
            # Sensor primary, fallback to OWM
            sensor_temp = self._get_sensor_temperature()
            return sensor_temp if sensor_temp is not None else self._get_owm_temperature()

    def _get_owm_temperature(self):
        """Get temperature from OWM."""
        owm_data = self.hass.data[DOMAIN].get("owm_data", {}).get(self._id_slug)
        if owm_data:
            return owm_data.get("temperature")
        return None

    def _get_sensor_temperature(self):
        """Get temperature from HA sensor."""
        if self._sensor_entity:
            state = self.hass.states.get(self._sensor_entity)
            if state and state.state not in ["unavailable", "unknown"]:
                return float(state.state)
        return None

    @property
    def extra_state_attributes(self):
        """Return additional attributes."""
        attrs = {
            "data_source": self._determine_active_source(),
        }
        
        # Add forecast if OWM is used
        if "owm" in self._determine_active_source():
            owm_data = self.hass.data[DOMAIN].get("owm_data", {}).get(self._id_slug)
            if owm_data and "hourly_forecast" in owm_data:
                # Add 1hr and 3hr forecast temps
                hourly = owm_data["hourly_forecast"]
                if len(hourly) > 0:
                    attrs["forecast_1hr"] = hourly[0].get("temp")
                if len(hourly) > 2:
                    attrs["forecast_3hr"] = hourly[2].get("temp")
        
        return attrs
```

---

## 5. AI Briefing Enhancement

### 5.1 Current Briefing Template

**Location**: `prompts/preflight_brief.txt`

Currently includes:
- Current weather conditions
- Density altitude
- Carb ice risk
- Runway recommendation

### 5.2 Enhanced Briefing Template (with OWM)

Add new sections:

```text
You are an aviation weather briefing assistant. Generate a pre-flight briefing for:

Airfield: {airfield_name}
Aircraft: {aircraft_registration}
Current Time: {current_time}

CURRENT CONDITIONS:
{current_weather}

FORECAST (Next 6 Hours):
{hourly_forecast_summary}

FORECAST (Next 3 Days):
{daily_forecast_summary}

GOVERNMENT WEATHER ALERTS:
{active_alerts}

PRECIPITATION TIMING:
{precipitation_forecast}

Based on this information, provide:
1. Summary of current conditions and their impact on VFR flight
2. Forecast trends and any deteriorating conditions
3. Timing windows for optimal departure/arrival
4. Specific warnings or recommendations based on alerts
5. Overall GO/NO-GO recommendation with reasoning
```

### 5.3 AI Service Enhancement

```python
async def async_generate_ai_briefing(hass, airfield, aircraft):
    """Generate AI briefing with OWM forecast data."""
    
    # Get current conditions (existing)
    current = get_current_conditions(airfield)
    
    # Get OWM forecast data (new)
    owm_data = hass.data[DOMAIN].get("owm_data", {}).get(airfield["_id_slug"])
    
    if owm_data:
        # Format hourly forecast
        hourly_summary = format_hourly_forecast(owm_data["hourly_forecast"][:6])
        
        # Format daily forecast
        daily_summary = format_daily_forecast(owm_data["daily_forecast"][:3])
        
        # Format alerts
        alerts_text = format_alerts(owm_data["alerts"])
        
        # Format precipitation timing
        precip_text = format_precipitation_forecast(owm_data["minutely_forecast"])
    else:
        hourly_summary = "No forecast data available"
        daily_summary = "No forecast data available"
        alerts_text = "No active alerts"
        precip_text = "No precipitation forecast available"
    
    # Build prompt
    prompt = BRIEFING_TEMPLATE.format(
        airfield_name=airfield["name"],
        aircraft_registration=aircraft.get("reg", "Unknown"),
        current_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
        current_weather=current,
        hourly_forecast_summary=hourly_summary,
        daily_forecast_summary=daily_summary,
        active_alerts=alerts_text,
        precipitation_forecast=precip_text,
    )
    
    # Call AI API
    response = await call_ai_api(prompt)
    return response
```

---

## 6. Dashboard Integration

### 6.1 New Dashboard Cards

**Forecast Card** (requires ApexCharts):
```yaml
type: custom:apexcharts-card
header:
  title: "Temperature Forecast (48hr)"
  show: true
graph_span: 48h
series:
  - entity: sensor.popham_weather_forecast_hourly
    name: Temperature
    data_generator: |
      return entity.attributes.forecast.map(hour => {
        return [new Date(hour.datetime).getTime(), hour.temperature];
      });
```

**Weather Alert Card**:
```yaml
type: conditional
conditions:
  - entity: binary_sensor.popham_government_weather_alert
    state: "on"
card:
  type: markdown
  content: |
    ## ⚠️ Active Weather Alerts
    {% for alert in state_attr('binary_sensor.popham_government_weather_alert', 'active_alerts') %}
    **{{ alert.event }}** ({{ alert.sender }})
    {{ alert.description }}
    Valid: {{ alert.start }} to {{ alert.end }}
    {% endfor %}
```

**Precipitation Timing Card**:
```yaml
type: custom:mushroom-chips-card
chips:
  - type: template
    entity: sensor.popham_precipitation_forecast
    content: |
      {% if states('sensor.popham_precipitation_forecast') | int < 60 %}
        ☔ Rain in {{ states('sensor.popham_precipitation_forecast') }}min
      {% else %}
        ✅ No rain next hour
      {% endif %}
    icon: mdi:weather-pouring
```

---

## 7. Backward Compatibility & Migration

### 7.1 Existing Users (No Changes)

**Scenario**: User upgrades to version with OWM support but doesn't configure API key

**Behavior**:
- ✅ All existing sensors work exactly as before
- ✅ No new config required
- ✅ No breaking changes
- ✅ OWM features hidden/disabled

### 7.2 Migration Path

**For users who want OWM**:
1. Get free OWM API key (https://openweathermap.org)
2. Settings → Hangar Assistant → Configure → Global Configuration → General Settings
3. Paste API key
4. Enable OWM
5. *Optional*: Edit airfields to change data source preference
6. Reload integration

**No data loss, no reconfiguration of existing sensors required**

---

## 8. Testing Strategy

### 8.1 Unit Tests

**File**: `tests/test_openweathermap.py`

```python
def test_owm_client_fetch():
    """Test OWM client data fetch."""
    # Mock API response
    # Test successful fetch
    # Test error handling

def test_owm_data_extraction():
    """Test data extraction from OWM response."""
    # Test current weather extraction
    # Test forecast extraction
    # Test alert extraction

def test_sensor_fallback():
    """Test sensor fallback logic."""
    # Test OWM primary
    # Test sensor primary
    # Test hybrid mode
```

### 8.2 Integration Tests

```python
async def test_owm_sensor_setup():
    """Test OWM sensor setup when API key configured."""
    # Setup with OWM key
    # Verify sensors created
    # Verify data source attributes

async def test_sensor_to_owm_fallback():
    """Test fallback from sensor to OWM when sensor fails."""
    # Setup hybrid mode
    # Make sensor unavailable
    # Verify OWM data used
```

### 8.3 API Rate Limit Testing

```python
def test_rate_limit_handling():
    """Test behavior when OWM rate limit hit."""
    # Mock 429 response
    # Verify graceful degradation
    # Verify logging
```

---

## 9. Documentation Updates

### 9.1 User Documentation

**New file**: `OWM_SETUP_GUIDE.md`
- How to get API key
- Configuration steps
- Data source options explained
- Dashboard examples
- Troubleshooting

### 9.2 README Updates

Add section:
```markdown
## Optional: OpenWeatherMap Integration

Enhance Hangar Assistant with professional weather forecasts and government alerts:
- 48-hour hourly forecast
- 8-day daily forecast
- Minutely precipitation timing
- Government weather alerts from national met services
- Backup data source when sensors unavailable

See [OWM Setup Guide](OWM_SETUP_GUIDE.md) for details.
```

### 9.3 AI Briefing Documentation

Update `GEMINI.md` with example enhanced briefings

---

## 10. Implementation Timeline

### Phase 1: Core Infrastructure (Week 1)
- [ ] Create `utils/openweathermap.py` with OWMClient
- [ ] Add config flow fields (global + per-airfield)
- [ ] Add translations for new settings
- [ ] Unit tests for OWM client
- [ ] Update copilot instructions

### Phase 2: Sensor Integration (Week 2)
- [ ] Modify existing sensors to support data source switching
- [ ] Create forecast sensors (hourly, daily, precipitation)
- [ ] Create alert binary sensor
- [ ] Create UV index sensor
- [ ] Integration tests
- [ ] Documentation

### Phase 3: AI Briefing Enhancement (Week 3)
- [ ] Update briefing prompt template
- [ ] Add forecast formatting functions
- [ ] Test enhanced briefings
- [ ] User feedback iteration

### Phase 4: Dashboard & Polish (Week 4)
- [ ] Create dashboard card examples
- [ ] Update glass_cockpit.yaml template
- [ ] Complete user documentation
- [ ] Release notes
- [ ] Community announcement

---

## 11. Success Metrics

### 11.1 Adoption Metrics
- % of users who configure OWM API key
- Number of airfields using OWM as primary source
- API call volume (ensure staying under free tier)

### 11.2 Quality Metrics
- Sensor availability improvement (with fallback)
- User reports of improved forecast accuracy
- AI briefing quality feedback

### 11.3 Technical Metrics
- API error rate (target: <1%)
- Cache hit rate (target: >80%)
- Sensor state update frequency

---

## 12. Future Enhancements (Post-Launch)

### 12.1 Historical Analysis
- Use OWM historical data (47 years archive)
- "Typical weather for this date" feature
- Trend analysis

### 12.2 Advanced Forecasting
- Icing forecast (using temp + humidity)
- Turbulence forecast (using wind + terrain)
- Crosswind forecast for runway planning

### 12.3 Multi-Airfield Comparison
- "Which airfield has better weather right now?"
- Route planning based on forecast

---

## Questions for User

1. **Data Source Default**: For airfields without sensors, should OWM be automatic default (if API key exists)? Or explicit opt-in per airfield?

2. **Forecast Sensor Format**: Prefer JSON attributes (as shown) or separate sensors for each forecast hour?

3. **AI Briefing Opt-in**: Should forecast data in briefings be automatic or toggleable per airfield?

4. **Rate Limit Strategy**: If user hits 1000 calls/day limit, should we:
   - Stop updates until next day?
   - Reduce update frequency automatically?
   - Show warning and let user decide?

5. **Alert Severity**: Should we create separate binary sensors for different alert levels (e.g., `weather_alert_severe`, `weather_alert_moderate`)?
