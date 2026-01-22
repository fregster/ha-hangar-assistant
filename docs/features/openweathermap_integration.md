# OpenWeatherMap Integration

**Feature**: Professional Weather Data with Forecasts and Alerts  
**Version**: 1.0 (v2601.1.0)  
**Status**: ✅ Available (Paid Service - Optional)

---

## Overview

The OpenWeatherMap (OWM) Integration provides access to professional-grade weather data including current conditions, hourly/daily forecasts, precipitation timing, and government weather alerts. This optional paid service enhances Hangar Assistant beyond basic sensor data with forecast trends critical for flight planning.

**Before this integration**, pilots could only see current conditions from local sensors without any forecast data, making it impossible to plan flights beyond the next hour.

**With this integration**, you get 48-hour hourly forecasts, 8-day daily forecasts, minute-by-minute precipitation predictions, UV index, and official government weather warnings - all integrated into your AI briefings and dashboard.

---

## Key Benefits

✅ **48-Hour Hourly Forecast** - Plan your flight with confidence  
✅ **8-Day Daily Outlook** - Schedule cross-country trips in advance  
✅ **Precipitation Forecast** - "Rain in 42 minutes" warnings  
✅ **Government Alerts** - Severe weather warnings (gale, snow, ice)  
✅ **Persistent Caching** - Survives restarts, protects rate limits  
✅ **AI Integration** - Forecasts automatically appear in briefings  
⚠️ **Paid Service** - ~£8-25/month depending on usage

---

## Pricing & API Access

### OpenWeatherMap One Call API 3.0

**What you need**: One Call API 3.0 subscription

**Pricing** (as of January 2026):
- **1,000 calls/day**: ~£8/month (~$10 USD)
- **2,000 calls/day**: ~£16/month (~$20 USD)
- **10,000 calls/day**: ~£80/month (~$100 USD)

**Recommended tier**: 1,000 calls/day is sufficient for most pilots:
- 1 airfield @ 10-minute updates = 144 calls/day
- 2 airfields @ 15-minute updates = 192 calls/day
- 5 airfields @ 30-minute updates = 240 calls/day

**Sign up**: [openweathermap.org/api/one-call-3](https://openweathermap.org/api/one-call-3)

### Free Trial

OWM typically offers a free trial period (check their website). This lets you test the integration before committing to a subscription.

---

## Configuration

### Setup Process

1. **Get API Key** at [openweathermap.org/api](https://openweathermap.org/api)
2. **Subscribe to One Call API 3.0** (paid subscription)
3. **Configure in Home Assistant**:
   - Settings → Integrations → Hangar Assistant → Configure
   - Navigate to "Integrations" menu
   - Select "OpenWeatherMap"
   - Enter API key (password field - never logged)
   - Configure cache and update settings

### Global Settings

**Path**: Settings → Integrations → Hangar Assistant → Configure → Integrations → OpenWeatherMap

| Setting | Description | Default | Recommended |
|---------|-------------|---------|-------------|
| **Enabled** | Master toggle | `False` | Enable after subscribing |
| **API Key** | OWM One Call API key | `""` | 32-character hex string |
| **Cache Enabled** | Persistent file caching | `True` | **Keep enabled** (critical) |
| **Update Interval** | Minutes between API calls | `10` | 10-15 min for flying, 30 min otherwise |
| **Cache TTL** | Cache validity period | `10` | Match update interval |

### Per-Airfield Settings

Each airfield can use OWM data independently:

| Setting | Description | Default | Options |
|---------|-------------|---------|---------|
| **Weather Data Source** | Primary data source | `"sensors"` | See modes below |
| **Use OWM Forecast** | Create forecast sensors | `True` | Enable for flight planning |
| **Use OWM Alerts** | Create alert sensors | `True` | Enable for safety |

### Weather Data Source Modes

| Mode | Behavior | Best For |
|------|----------|----------|
| `"sensors"` | Use only HA sensors | No OWM subscription, local weather station |
| `"openweathermap"` | Use only OWM API | No local sensors, OWM subscription active |
| `"hybrid"` | OWM primary, sensors fallback | OWM subscription + local sensors as backup |
| `"sensors_backup_owm"` | Sensors primary, OWM fallback | Local sensors preferred, OWM for redundancy |

**Recommended**: `"hybrid"` mode if you have both sensors and OWM subscription.

---

## Rate Limit Protection (CRITICAL)

### Why Caching Matters

OWM charges per API call. Without caching, a Home Assistant restart could trigger hundreds of immediate API calls, quickly exhausting your daily limit and incurring overage charges.

### Two-Level Cache System

1. **Memory Cache** (session-based):
   - Stores recent API responses in RAM
   - Lost on restart
   - LRU eviction prevents memory bloat (max 1000 entries)

2. **Persistent File Cache**:
   - Survives restarts/reloads
   - Stored in `<config_dir>/hangar_assistant_cache/`
   - Protects against restart-induced API storms

### Cache Lookup Order

1. Check memory cache → return if valid
2. Check persistent file cache → return if valid
3. Make API call → update both caches
4. If API call fails → use stale cache

### Rate Limit Tracking

The integration tracks API calls per day and warns you at **950/1000** daily limit:

```
WARNING: OpenWeatherMap API calls approaching daily limit: 950/1000
Consider increasing update interval or reducing configured airfields.
```

**Resets**: Midnight UTC daily

---

## Entities Created

### Current Weather Sensors

When OWM is enabled and a weather data source mode uses OWM, current condition sensors are enhanced:

**Enhanced Attributes** (all existing sensors):
- `data_source`: "openweathermap", "sensors", or "hybrid"
- `owm_weather_description`: "Partly cloudy", "Light rain", "Clear sky"
- `owm_weather_icon`: "03d" (OWM icon code for UI)
- `owm_uv_index`: UV index value (0-11+)
- `owm_visibility_m`: Visibility in meters (from OWM)

### Forecast Sensors

**Entity ID**: `sensor.{airfield_slug}_weather_forecast_hourly`

**State**: Count of forecast hours available (typically 48)

**Attributes**: List of hourly forecast dictionaries:
```yaml
state: 48
attributes:
  forecast:
    - time: "2026-01-22T09:00:00Z"
      temp_c: 8
      feels_like_c: 5
      pressure_hpa: 1013
      humidity_percent: 75
      clouds_percent: 40
      wind_speed_kts: 12
      wind_deg: 270
      wind_gust_kts: 18
      pop: 0.15  # Probability of precipitation (15%)
      visibility_m: 10000
      weather: "Partly cloudy"
      weather_icon: "03d"
    - time: "2026-01-22T10:00:00Z"
      ...
```

---

**Entity ID**: `sensor.{airfield_slug}_weather_forecast_daily`

**State**: Count of forecast days available (typically 8)

**Attributes**: List of daily forecast dictionaries:
```yaml
state: 8
attributes:
  forecast:
    - date: "2026-01-22"
      temp_min_c: 4
      temp_max_c: 10
      temp_morning_c: 5
      temp_day_c: 9
      temp_evening_c: 7
      temp_night_c: 4
      pressure_hpa: 1013
      humidity_percent: 70
      wind_speed_kts: 10
      wind_deg: 250
      wind_gust_kts: 20
      clouds_percent: 50
      pop: 0.30  # 30% chance of precipitation
      rain_mm: 2.5
      weather: "Light rain"
      weather_icon: "10d"
      sunrise: "2026-01-22T07:45:00Z"
      sunset: "2026-01-22T16:30:00Z"
    - date: "2026-01-23"
      ...
```

---

**Entity ID**: `sensor.{airfield_slug}_precipitation_forecast`

**State**: Minutes until next precipitation (or "None" if no rain expected in 60 min)

**Attributes**:
```yaml
state: 42
attributes:
  intensity_mm_per_hour: 2.5
  forecast:
    - time: "2026-01-22T09:00:00Z"
      precipitation_mm: 0
    - time: "2026-01-22T09:01:00Z"
      precipitation_mm: 0
    - time: "2026-01-22T09:42:00Z"
      precipitation_mm: 0.5
    - time: "2026-01-22T09:43:00Z"
      precipitation_mm: 1.2
      ...
```

**Use Case**: "Rain starting in 42 minutes - better expedite your pre-flight!"

---

**Entity ID**: `sensor.{airfield_slug}_uv_index`

**State**: Current UV index (0-11+)

**Device Class**: `None` (custom sensor)

**Attributes**:
```yaml
state: 3
attributes:
  risk_level: "Moderate"
  recommendation: "Wear sunglasses and sunscreen"
```

**UV Index Scale**:
- 0-2: Low
- 3-5: Moderate
- 6-7: High
- 8-10: Very High
- 11+: Extreme

---

### Alert Binary Sensors

**Entity ID**: `binary_sensor.{airfield_slug}_government_weather_alert`

**State**: 
- `On` (Alert Active) - Government weather warning in effect
- `Off` (Clear) - No active warnings

**Device Class**: `safety`

**Attributes**:
```yaml
state: on
attributes:
  alert_count: 2
  alerts:
    - sender: "UK Met Office"
      event: "Strong Wind Warning"
      start: "2026-01-22T06:00:00Z"
      end: "2026-01-22T18:00:00Z"
      description: "Gale force winds expected. Gusts 35-40 knots."
      severity: "Moderate"
      tags: ["Wind", "Aviation"]
    - sender: "UK Met Office"
      event: "Ice Warning"
      start: "2026-01-23T00:00:00Z"
      end: "2026-01-23T09:00:00Z"
      description: "Freezing conditions overnight. Ice on surfaces."
      severity: "Minor"
      tags: ["Ice", "Frost"]
```

**Severity Levels**:
- `Extreme`: Life-threatening
- `Severe`: High impact
- `Moderate`: Significant impact
- `Minor`: Awareness level

---

## AI Briefing Enhancement

When OWM is enabled, AI-generated briefings include:

### 6-Hour Forecast Trends
```
FORECAST TREND (Next 6 Hours):
- 09:00: 8°C, Wind 270° 12kt G18kt, CAVOK
- 12:00: 10°C, Wind 280° 10kt G15kt, FEW040
- 15:00: 9°C, Wind 290° 8kt G12kt, SCT035 BKN050
- 18:00: 7°C, Wind 300° 6kt, OVC060

Conditions improving through morning, cloud base rising.
```

### 3-Day Daily Summary
```
OUTLOOK (3-Day):
- Thu 23 Jan: 4-10°C, W 10kt G20kt, 30% rain (2.5mm)
- Fri 24 Jan: 6-12°C, SW 8kt G15kt, Clear
- Sat 25 Jan: 8-14°C, S 5kt, Partly cloudy

Weekend looks favorable for cross-country flying.
```

### Government Alerts
```
⚠️ WEATHER ALERTS ACTIVE (2):
1. STRONG WIND WARNING (Moderate severity)
   Effective: 22 Jan 06:00-18:00 UTC
   Gale force winds expected. Gusts 35-40 knots.
   
2. ICE WARNING (Minor severity)
   Effective: 23 Jan 00:00-09:00 UTC
   Freezing conditions overnight.

RECOMMENDATION: Winds exceed your aircraft crosswind limit until 18:00.
```

### Precipitation Timing
```
PRECIPITATION FORECAST:
- Rain starting in 42 minutes (09:42 UTC)
- Intensity: Light (2.5mm/hr)
- Duration: ~3 hours

Consider departing within the hour to avoid IMC conditions.
```

---

## Use Cases

### Flight Planning Dashboard

Display forecast on Glass Cockpit:

```yaml
type: custom:apexcharts-card
header:
  title: "6-Hour Forecast - Popham"
series:
  - entity: sensor.popham_weather_forecast_hourly
    data_generator: |
      return entity.attributes.forecast.slice(0, 6).map((f) => {
        return [new Date(f.time).getTime(), f.temp_c];
      });
    name: Temperature
  - entity: sensor.popham_weather_forecast_hourly
    data_generator: |
      return entity.attributes.forecast.slice(0, 6).map((f) => {
        return [new Date(f.time).getTime(), f.wind_speed_kts];
      });
    name: Wind Speed
```

### Rain Alert Automation

Cancel flight if rain expected:

```yaml
automation:
  - alias: "Pre-Flight Rain Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.popham_precipitation_forecast
        below: 60  # Less than 60 minutes until rain
    condition:
      - condition: state
        entity_id: input_boolean.flight_scheduled
        state: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "⚠️ Rain Approaching"
          message: "Rain in {{ states('sensor.popham_precipitation_forecast') }} minutes. Review flight plan."
```

### Weather Alert Notification

Immediate alert on government warnings:

```yaml
automation:
  - alias: "Government Weather Alert"
    trigger:
      - platform: state
        entity_id: binary_sensor.popham_government_weather_alert
        to: "on"
    action:
      - service: notify.all_devices
        data:
          title: "⚠️ Weather Alert - {{ states.binary_sensor.popham_government_weather_alert.attributes.alerts[0].event }}"
          message: "{{ states.binary_sensor.popham_government_weather_alert.attributes.alerts[0].description }}"
          data:
            priority: high
            ttl: 0
```

### UV Index Safety

Remind pilot to wear sunscreen on high UV days:

```yaml
automation:
  - alias: "High UV Index Warning"
    trigger:
      - platform: numeric_state
        entity_id: sensor.popham_uv_index
        above: 6
    action:
      - service: notify.mobile_app
        data:
          message: "UV Index {{ states('sensor.popham_uv_index') }} - Wear sunscreen and sunglasses!"
```

---

## Troubleshooting

### API Key Not Working

**Symptoms**: Logs show "401 Unauthorized" errors

**Causes**:
1. API key not valid (wrong key entered)
2. One Call API 3.0 not subscribed
3. Subscription expired or payment failed
4. API key not activated yet (24-hour delay)

**Solutions**:
- Verify API key at [openweathermap.org/api_keys](https://openweathermap.org/api_keys)
- Check subscription status - must be One Call API 3.0
- Wait 24 hours after signup for activation
- Re-enter API key carefully (no spaces, full 32 characters)

### Rate Limit Exceeded

**Symptoms**: Logs show "429 Too Many Requests" or "Rate limit exceeded"

**Causes**:
1. Update interval too aggressive (every 5 minutes = 288 calls/day per airfield)
2. Too many configured airfields
3. Home Assistant restarted multiple times
4. Subscription tier too low

**Solutions**:
- Increase update interval: 10→15 or 15→30 minutes
- Reduce configured airfields (disable OWM for rarely used airfields)
- Upgrade OWM subscription tier
- Enable persistent caching (should already be enabled)
- Check rate limit tracker: `grep "API calls" home-assistant.log`

### Forecast Sensors Not Created

**Symptoms**: Current weather works but forecast sensors missing

**Causes**:
1. Airfield setting "Use OWM Forecast" disabled
2. Weather data source set to "sensors" only
3. API call failed during sensor initialization

**Solutions**:
- Check airfield settings: Settings → Airfields → Edit → OpenWeatherMap
- Enable "Use OWM Forecast"
- Change weather data source to "openweathermap" or "hybrid"
- Restart Home Assistant to reinitialize sensors
- Check logs for API errors during startup

### Stale Cache Warning

**Symptoms**: Logs show "Using stale cache" messages

**Causes**:
1. Network connectivity issues
2. OWM API temporarily unavailable
3. Rate limit exceeded (fallback to cache)
4. API subscription expired

**Solutions**:
- Check internet connectivity
- Verify OWM status: [status.openweathermap.org](https://status.openweathermap.org)
- Check API call count for rate limit issues
- Renew subscription if expired
- Cache will auto-refresh once connectivity restored

### Weather Alerts Not Appearing

**Symptoms**: Government alert sensor always "off" despite expecting alerts

**Causes**:
1. No active government weather warnings in area
2. OWM doesn't have alert data for your region (rare)
3. Alert sensor disabled in airfield settings

**Solutions**:
- Verify alerts exist: Check Met Office or local weather service
- Enable "Use OWM Alerts" in airfield settings
- Note: OWM alert coverage varies by country (best in US/UK/EU)
- Check sensor attributes manually: Developer Tools → States

---

## FAQ

### Is OpenWeatherMap required for Hangar Assistant?

**No!** OWM is completely optional. Hangar Assistant works perfectly with:
- Home Assistant weather sensors only (free)
- CheckWX API for METAR/TAF (free)
- No external APIs at all (sensor-only mode)

OWM adds forecast data and alerts, but isn't required for basic functionality.

### Can I use the free OWM tier?

**No.** The free tier doesn't include One Call API 3.0 access. You must subscribe to the paid tier (~£8-25/month) to use this integration.

**Alternative**: Use CheckWX (free) for METAR/TAF forecasts, which provide basic forecast data without cost.

### How does caching save money?

**Example without caching**:
- Home Assistant restarts
- 5 configured airfields
- Each immediately calls OWM API
- 5 × 1 call = 5 calls instantly

**With persistent caching**:
- Home Assistant restarts
- Integration checks cache files (all valid for 10 minutes)
- 5 × 0 calls = 0 calls during restart

Over a month, this saves **dozens to hundreds** of API calls, directly reducing costs.

### What happens if I exceed my rate limit?

**OWM behavior**: Returns 429 error, integration uses cached data

**Integration behavior**:
1. Logs warning message
2. Uses last cached forecast (up to `cache_ttl` old)
3. Continues retrying at next update interval
4. Creates notification at 950/1000 calls to warn you

**Cost impact**: OWM may charge overages depending on subscription tier. Monitor your API dashboard.

### Can I mix OWM and sensors?

**Yes!** That's exactly what "hybrid" mode does:

```yaml
weather_data_source: "hybrid"
```

This uses:
- **OWM for current conditions** (primary source)
- **Sensors for fallback** if OWM unavailable
- **OWM forecasts** (sensors can't provide forecasts)
- **Sensors for granular data** (if you have multiple sensors per airfield)

Best of both worlds: Forecast capability + local accuracy.

### Does this work worldwide?

**Yes**, with caveats:

**Current Weather**: Worldwide coverage (any lat/lon)

**Forecasts**: Worldwide coverage

**Weather Alerts**: Coverage varies by country:
- ✅ Excellent: US, UK, Germany, France
- ⚠️ Limited: Some EU countries, Australia
- ❌ None: Many developing nations

Check [OWM documentation](https://openweathermap.org/api/one-call-3#alerts) for your region.

### How accurate are OWM forecasts?

**Accuracy** (based on meteorological studies):
- 1-3 hours: ~90% accuracy
- 6-12 hours: ~80% accuracy
- 24 hours: ~70% accuracy
- 3+ days: ~60% accuracy

**For aviation use**:
- **Short flights (1-2 hours)**: Excellent forecast reliability
- **Cross-country (3-6 hours)**: Good, but monitor for changes
- **Multi-day planning**: Use as guidance, check official TAF/forecasts closer to departure

**Always cross-reference** with official aviation forecasts (METAR, TAF, SIGMET).

---

## Best Practices

### For VFR Day Trips

1. **10-15 minute update interval**: Balance freshness with API limits
2. **Enable all forecast sensors**: Hourly, daily, precipitation, UV
3. **Enable weather alerts**: Government warnings critical for VFR safety
4. **Hybrid mode**: Use sensors + OWM for redundancy
5. **Check 6-hour forecast**: Review trends before departure

### For Cross-Country Planning

1. **30-minute update interval**: Less frequent updates sufficient for planning
2. **8-day daily forecast**: Review destination weather trends
3. **Enable precipitation forecast**: Time departure/arrival around weather
4. **Morning briefing automation**: Daily AI briefing with 3-day outlook
5. **Monitor alerts**: Track weather systems along route

### For Flight Schools

1. **Configure instructional airfields only**: Limit API calls to frequently used locations
2. **Shared OWM account**: All instructors use same subscription (coordinate limits)
3. **Dashboard in briefing room**: Permanent forecast display for students
4. **Conservative update interval**: 30 minutes (saves costs)
5. **Automate daily briefings**: Morning briefing for all instructors

### For Cost Optimization

1. **Start with 1,000 calls/day tier**: Upgrade only if needed
2. **15-30 minute intervals**: Balance freshness vs. cost
3. **Disable OWM for unused airfields**: Only enable for actively flying locations
4. **Monitor API usage**: Check OWM dashboard weekly
5. **Use sensors as primary**: `sensors_backup_owm` mode uses OWM only when needed

---

## Technical Details

### Cache File Structure

**Location**: `<config_dir>/hangar_assistant_cache/owm_{lat}_{lon}.json`

**Format** (using orjson if available for 2-5x speed):
```json
{
  "timestamp": "2026-01-22T08:15:30Z",
  "cache_ttl_minutes": 10,
  "lat": 51.247,
  "lon": -1.234,
  "data": {
    "current": { ... },
    "hourly": [ ... ],
    "daily": [ ... ],
    "minutely": [ ... ],
    "alerts": [ ... ]
  }
}
```

### API Call Optimization

**Single call per airfield** - One API request fetches:
- Current conditions
- 48-hour hourly forecast
- 8-day daily forecast
- 60-minute minutely forecast
- Government alerts

**No redundant calls** - Persistent cache prevents duplicate requests during restarts.

**LRU memory cache** - Frequently accessed airfields kept in RAM (max 1000 entries, LRU eviction).

### Data Source Priority

When `weather_data_source: "hybrid"`:

1. **Current Conditions**:
   - Try OWM API (respect cache)
   - Fallback to sensors if OWM fails
   - Use most recent valid data

2. **Forecasts**:
   - Always from OWM (sensors can't forecast)
   - Use stale cache if API unavailable

3. **Alerts**:
   - Always from OWM
   - No fallback (sensors don't provide alerts)

### Backward Compatibility

**v2601.1.0+**: OWM integration fully optional. If not configured:
- No OWM entities created
- All features work with sensors only
- Configuration UI hides OWM-specific settings
- No API calls made

**Migration**: Existing installations with sensor-only setup unaffected by OWM addition.

---

## Related Documentation

- [NOTAM Integration](notam_integration.md) - Free UK NATS NOTAM data
- [API Integrations Overview](api_integrations.md) - Managing all external data sources
- [AI Briefing Service](ai_briefing.md) - How forecasts enhance briefings
- [Sensor Reference](../ENTITY_DESCRIPTIONS.md) - Complete entity list
- [Caching Strategy](../development/CACHING.md) - Technical caching details

---

## Version History

### v1.0 (v2601.1.0 - January 2026)
- ✅ Initial release with One Call API 3.0 support
- ✅ Current weather conditions
- ✅ 48-hour hourly forecasts
- ✅ 8-day daily forecasts
- ✅ 60-minute precipitation forecasts
- ✅ Government weather alerts
- ✅ UV index sensor
- ✅ Persistent two-level caching
- ✅ Rate limit tracking and warnings
- ✅ Four data source modes (sensors, OWM, hybrid, sensors+OWM backup)
- ✅ AI briefing integration
- ✅ orjson optimization (2-5x faster JSON)

### Planned Enhancements (v2601.2.0+)
- 🔄 Cost tracking dashboard (API calls per day/week/month)
- 🔄 Forecast accuracy tracking (compare forecast vs. actual)
- 🔄 Multi-language weather descriptions
- 🔄 Severe weather push notifications
- 🔄 Historical forecast logging (CSV export)
- 🔄 Alternative forecast providers (Weather.gov, Met Office)

---

**Last Updated**: 22 January 2026  
**Feature Version**: 1.0  
**Target Users**: Pilots requiring forecast data for flight planning  
**Difficulty Level**: Intermediate (requires paid API subscription)  
**Cost**: ~£8-25/month (~$10-30 USD) depending on usage tier
