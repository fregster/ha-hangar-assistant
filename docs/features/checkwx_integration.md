# CheckWX Aviation Weather Integration

## Overview

CheckWX integration provides official aviation weather data (METAR and TAF) directly from aviation weather stations worldwide. This gives you the same professional weather information that pilots rely on for flight planning and pre-flight briefings. The integration appears automatically when you configure airfields with valid ICAO codes and is completely free for personal use (up to 3,000 requests per day).

CheckWX complements your existing weather sensors by providing official aviation-formatted observations and forecasts that match what you'd see in professional aviation apps or briefing services.

## Getting Started

### Prerequisites

- **ICAO code for your airfield**: Your airfield must have a 4-letter ICAO code (e.g., EGHP for Popham, KJFK for New York JFK, EDDM for Munich)
- **Internet connection**: CheckWX requires internet access to fetch weather data
- **Free CheckWX account**: Sign up at [checkwx.com](https://www.checkwx.com) (takes 2 minutes)

### When CheckWX Is Used

CheckWX automatically provides weather data for any airfield where you've configured an ICAO code. You'll see three new sensors appear for each airfield:
- **METAR sensor**: Current weather observations (updated every 15 minutes)
- **TAF sensor**: Terminal aerodrome forecasts (updated every 6 hours)
- **Station Info sensor**: Airfield details (elevation, location, name)

## Step-by-Step Setup Guide

### Step 1: Sign Up for Free CheckWX Account

1. Go to [https://www.checkwx.com](https://www.checkwx.com)
2. Click **"Sign Up"** in the top right
3. Enter your email and create a password
4. Confirm your email address (check your inbox)
5. Log in to your new account

**Time required**: 2 minutes

### Step 2: Get Your API Key

1. Log in to CheckWX
2. Navigate to **"Dashboard"** or **"API"** section
3. Find your API key (looks like: `abc123def456ghi789jkl`)
4. Click **"Copy"** to copy it to your clipboard
5. Keep this window open (you'll need to paste this in a moment)

**Important**: Treat your API key like a password. Don't share it publicly or commit it to version control.

### Step 3: Configure CheckWX in Hangar Assistant

1. Open Home Assistant
2. Go to **Settings** → **Devices & Services** → **Hangar Assistant**
3. Click **"Configure"**
4. Select **"Integrations"** from the menu
5. In the **CheckWX** section:
   - Toggle **"Enable CheckWX"** to **ON**
   - Paste your API key in the **"API Key"** field
   - Set **"Update Interval"** (default: 15 minutes for METAR, 6 hours for TAF)
   - Toggle **"Enable Caching"** to **ON** (recommended to respect rate limits)
6. Click **"Submit"**

Hangar Assistant will test your API key immediately and show a success message if it works.

### Step 4: Enable CheckWX for Your Airfields

CheckWX only works for airfields with ICAO codes configured:

1. Go to **Settings** → **Devices & Services** → **Hangar Assistant** → **"Configure"**
2. Select **"Manage Airfields"** from the menu
3. Choose the airfield you want to enable CheckWX for
4. Ensure the **"ICAO Code"** field has a valid 4-letter code (e.g., EGHP)
5. Click **"Submit"**
6. Repeat for each airfield

**What happens next**: Within 15 minutes, three new sensors will appear for each airfield with an ICAO code.

## What Gets Created

CheckWX automatically creates three sensors for each airfield with an ICAO code:

### METAR Sensor

**Entity ID**: `sensor.{airfield}_metar`  
**Example**: `sensor.popham_metar`

**What it shows**: Raw METAR observation (current weather at the airfield)

**Example value**:
```
EGHP 221350Z 27008KT 9999 FEW025 SCT040 09/05 Q1013
```

**Attributes**:
- `raw_text`: The full METAR text
- `observation_time`: When the observation was made
- `temperature`: Temperature in °C
- `dewpoint`: Dew point in °C
- `wind_speed`: Wind speed in knots
- `wind_direction`: Wind direction in degrees
- `visibility`: Visibility in meters
- `clouds`: Cloud layers with heights
- `barometer`: QNH pressure in hPa

**Update frequency**: Every 15 minutes (or your configured interval)

### TAF Sensor

**Entity ID**: `sensor.{airfield}_taf`  
**Example**: `sensor.popham_taf`

**What it shows**: Terminal Aerodrome Forecast (predicted weather for next 24-30 hours)

**Example value**:
```
TAF EGHP 221100Z 2212/2312 27010KT 9999 FEW030 SCT050
     TEMPO 2214/2218 5000 -RA BKN015
     BECMG 2220/2222 30015G25KT
```

**Attributes**:
- `raw_text`: Full TAF text
- `issue_time`: When the forecast was issued
- `valid_from`: Forecast start time
- `valid_to`: Forecast end time
- `forecast_periods`: Parsed forecast periods with conditions

**Update frequency**: Every 6 hours (TAFs update less frequently than METARs)

### Station Info Sensor

**Entity ID**: `sensor.{airfield}_station_info`  
**Example**: `sensor.popham_station_info`

**What it shows**: Airfield metadata (elevation, coordinates, full name)

**Attributes**:
- `icao`: ICAO code (e.g., EGHP)
- `iata`: IATA code if available (e.g., LHR)
- `name`: Full airfield name (e.g., "Popham Airfield")
- `elevation_ft`: Field elevation in feet
- `elevation_m`: Field elevation in meters
- `latitude`: Decimal degrees
- `longitude`: Decimal degrees
- `country`: Country code (e.g., "GB")

**Update frequency**: Cached for 7 days (station info rarely changes)

## Troubleshooting

### Problem: "Invalid API Key" Error

**Symptoms**: After entering your CheckWX API key, you see an error message saying the key is invalid.

**Solutions**:
1. **Check for extra spaces**: Ensure you didn't copy any extra spaces before or after the API key
2. **Verify the key**: Log in to CheckWX and compare the key character-by-character
3. **Check account status**: Ensure your CheckWX account is active and email confirmed
4. **Try a new key**: Generate a new API key in CheckWX dashboard
5. **Check internet connection**: Ensure Home Assistant can reach the internet

**How to verify**: Go to [https://api.checkwx.com/metar/KJFK](https://api.checkwx.com/metar/KJFK?x-api-key=YOUR_KEY) (replace YOUR_KEY) in your browser. You should see METAR data, not an error.

### Problem: No Weather Data Appearing

**Symptoms**: CheckWX is enabled and API key works, but no METAR/TAF sensors appear for your airfield.

**Solutions**:
1. **Check ICAO code**: Ensure your airfield has a valid 4-letter ICAO code configured
   - Go to **Settings** → **Devices & Services** → **Hangar Assistant** → **Configure** → **Manage Airfields**
   - Verify the ICAO field is filled (e.g., EGHP, not "Popham")
2. **Wait 15 minutes**: Sensors are created on the first successful update (may take one update cycle)
3. **Check station availability**: Not all airfields publish METAR/TAF (small private fields may not have them)
   - Test at [https://www.checkwx.com/weather/EGHP](https://www.checkwx.com/weather/EGHP) (replace EGHP with your code)
4. **Restart Home Assistant**: Sometimes entities need a restart to appear
   - Go to **Developer Tools** → **YAML** → **Restart**
5. **Check logs**: Look for CheckWX errors in **Settings** → **System** → **Logs**

### Problem: Rate Limit Warnings

**Symptoms**: You see warnings in Home Assistant logs about approaching CheckWX rate limits.

**Explanation**: CheckWX free tier allows 3,000 requests per day. With default settings (15 min METAR updates for 5 airfields), you'll use about 480 requests per day—well within limits.

**Solutions**:
1. **Enable caching**: Ensure **"Enable Caching"** is toggled ON in Integrations settings (prevents duplicate requests)
2. **Increase update interval**: Change METAR update interval from 15 minutes to 30 minutes
   - Go to **Settings** → **Devices & Services** → **Hangar Assistant** → **Configure** → **Integrations**
   - Set **"Update Interval (minutes)"** to 30
3. **Reduce airfield count**: If you have many airfields, consider disabling CheckWX for ones you rarely use
4. **Monitor usage**: Check your CheckWX dashboard for actual daily usage stats

**Rate limit calculation**:
- 1 airfield, 15-min updates: ~96 requests/day
- 5 airfields, 15-min updates: ~480 requests/day
- 10 airfields, 15-min updates: ~960 requests/day

### Problem: ICAO Code Not Found

**Symptoms**: CheckWX returns "station not found" for your airfield's ICAO code.

**Solutions**:
1. **Verify the ICAO code**: Double-check the 4-letter code is correct
   - Search at [https://airportcodes.aero](https://airportcodes.aero) or [SkyVector](https://skyvector.com)
2. **Check if station reports weather**: Not all airports publish METAR/TAF
   - Military airfields may not publish publicly
   - Small private airfields may not have weather reporting equipment
3. **Use nearby airfield**: If your field doesn't have METAR, use the nearest airfield with weather reporting
   - Configure a second airfield for weather data
   - Use that airfield's CheckWX sensors for planning
4. **Supplement with OpenWeatherMap**: For fields without official weather, use OpenWeatherMap instead
   - See [OpenWeatherMap Integration](openweathermap_integration.md) documentation

**Example**: Popham (EGHP) publishes METAR but not TAF. The METAR sensor will work, but TAF sensor will show "unavailable"—this is normal.

## FAQ

### What's the difference between CheckWX and OpenWeatherMap?

**CheckWX**:
- **Official aviation weather**: METAR and TAF in standard aviation format
- **From aviation weather stations**: Same data used by professional pilots
- **Free for personal use**: 3,000 requests/day (sufficient for home use)
- **Requires ICAO code**: Only works for airfields with official weather stations
- **Updated by meteorologists**: Data verified and quality-controlled

**OpenWeatherMap**:
- **General-purpose weather**: Temperature, wind, forecasts for any location
- **From weather models**: Computer-generated predictions
- **Paid API**: Requires subscription for One Call API 3.0
- **Works anywhere**: Can provide weather for any coordinates (lat/lon)
- **More data points**: Minutely precipitation, 48-hour hourly forecasts, UV index

**Recommendation**: Use both! CheckWX for official aviation weather (what pilots trust), OpenWeatherMap for enhanced forecasts and locations without METAR.

### Do I need to pay for CheckWX?

**No, CheckWX is free for personal use.**

**Free tier includes**:
- 3,000 API requests per day (resets at midnight UTC)
- Access to all worldwide METAR, TAF, and station data
- No credit card required
- Sufficient for 1-10 airfields with default update intervals

**When you might need paid tier**:
- If you monitor 20+ airfields with frequent updates
- If you're running a commercial flight school or business
- If you want shorter update intervals (e.g., every 5 minutes)

**For typical home users**: Free tier is more than enough. You'll use 100-500 requests per day depending on how many airfields you monitor.

### How many API calls does Hangar Assistant use?

**Default configuration** (15-minute METAR updates, 6-hour TAF updates):

| Airfields | METAR Requests/Day | TAF Requests/Day | Total/Day |
|-----------|-------------------|------------------|-----------|
| 1         | 96                | 4                | 100       |
| 3         | 288               | 12               | 300       |
| 5         | 480               | 20               | 500       |
| 10        | 960               | 40               | 1,000     |

**With caching enabled** (recommended): Reduces requests during Home Assistant restarts and reloads. May cut usage by 10-20%.

**If you increase update interval to 30 minutes**: Halves the METAR requests (48 per airfield per day instead of 96).

**CheckWX free tier**: 3,000 requests/day—easily supports 5-10 airfields.

### Can I use CheckWX without OpenWeatherMap?

**Yes, absolutely.** CheckWX and OpenWeatherMap are completely independent.

**CheckWX alone provides**:
- Official METAR observations (temperature, wind, pressure, clouds)
- TAF forecasts (predicted conditions for next 24-30 hours)
- Airfield station information

**You might want BOTH if**:
- Your airfield lacks METAR/TAF (small private fields)
- You want enhanced forecasts (hourly, daily, precipitation timing)
- You need government weather alerts
- You want UV index, air quality, or detailed wind forecasts

**You only need CheckWX if**:
- Your airfields all have ICAO codes and publish METAR/TAF
- You prefer official aviation weather over model-based forecasts
- You're on a budget (CheckWX is free, OWM One Call requires subscription)

See [OpenWeatherMap Integration](openweathermap_integration.md) for details on the optional OWM integration.

### What if my airfield doesn't have an ICAO code?

**Options**:

1. **Use a nearby airfield with METAR**: Configure the nearest airfield that publishes weather (within 10-20 miles)
   - Add it as a second airfield in Hangar Assistant
   - Use its CheckWX sensors for weather planning
   - Adjust for local conditions (elevation differences, terrain effects)

2. **Use OpenWeatherMap instead**: Provides weather for any location by lat/lon
   - See [OpenWeatherMap Integration](openweathermap_integration.md)
   - Set airfield's `weather_data_source` to `"openweathermap"` or `"sensors"`

3. **Use Home Assistant weather sensors**: Connect weather station hardware
   - Personal weather stations (PWS)
   - Netatmo, Davis Instruments, Ambient Weather, etc.
   - Configure sensor entity IDs in Hangar Assistant

**Example scenario**: You fly from a small grass strip (no ICAO code). The nearest towered airport (10 miles away) is KJFK. Configure KJFK as a second airfield to get official weather, then adjust mentally for your strip's elevation and local terrain.

### Does CheckWX work worldwide?

**Yes**, CheckWX provides weather data for any airfield that publishes METAR/TAF, regardless of country.

**Coverage includes**:
- **United States**: All airports with AWOS/ASOS weather reporting
- **United Kingdom**: UK Met Office reporting stations
- **Europe**: EUROCONTROL network stations
- **Australia**: BoM (Bureau of Meteorology) stations
- **Canada**: NAV CANADA stations
- **Rest of world**: ICAO member states with weather reporting

**Not covered**:
- Private airstrips without weather equipment
- Military bases with restricted weather access
- Small airfields in developing countries without infrastructure

**To check if your airfield is supported**: Search your ICAO code at [https://www.checkwx.com/weather/EGHP](https://www.checkwx.com/weather/EGHP) (replace EGHP). If you see METAR data, it's supported.

### How do I read METAR and TAF?

**METAR example**: `EGHP 221350Z 27008KT 9999 FEW025 SCT040 09/05 Q1013`

**Decoded**:
- `EGHP`: Airfield ICAO code (Popham)
- `221350Z`: Observation time (22nd day, 1350 UTC)
- `27008KT`: Wind from 270° at 8 knots
- `9999`: Visibility 10km or more (9999 = excellent)
- `FEW025 SCT040`: Few clouds at 2,500 ft, scattered clouds at 4,000 ft
- `09/05`: Temperature 9°C, dew point 5°C
- `Q1013`: QNH pressure setting 1013 hPa

**Resources for learning METAR/TAF**:
- [NOAA METAR Guide](https://www.aviationweather.gov/metar/help)
- [SkyVector METAR Decoder](https://skyvector.com)
- Your flight training materials (METAR decoding is required for pilot licenses)

**Tip**: Hangar Assistant's AI Briefing feature automatically decodes METAR/TAF into plain English for you.

## Best Practices

### For Student Pilots

**Use CheckWX to learn official weather formats:**
- Compare CheckWX METAR with decoded weather sensors to learn interpretation
- Practice decoding METAR before each simulated cross-country flight
- Use TAF to plan "what if" scenarios (if weather deteriorates, what's my alternate?)
- Cross-reference CheckWX with your instructor's weather briefings

**Recommended configuration**:
- Enable CheckWX for your training airfield
- Add 2-3 nearby airports (your cross-country destinations)
- Set update interval to 15 minutes (default) to see real-time changes

**Learning exercise**: Create an automation that sends you a notification when METAR changes significantly (wind shift >30°, visibility drops below 5km).

### For Private Pilots

**CheckWX is essential for VFR flight planning:**
- Check METAR before every flight (no excuses—it's automatic now)
- Use TAF to plan departure and return times (avoid deteriorating conditions)
- Monitor multiple airfields along your route
- Set up alerts for conditions outside your personal minimums

**Recommended configuration**:
- Enable CheckWX for your home airfield + frequent destinations
- Configure dashboard to show METAR prominently
- Create automation: alert if clouds drop below your VFR minima (e.g., <1,500 ft AGL)
- Use AI Briefing feature for automated pre-flight weather summaries

**Safety tip**: Always cross-reference CheckWX data with official NOTAMs and aviation weather briefings (1800-WX-BRIEF in US, NATS in UK). Hangar Assistant supplements but doesn't replace official briefings.

### For Commercial Pilots

**CheckWX provides required weather data for professional operations:**
- Monitor airfields along charter/scheduled routes
- Archive METAR/TAF data for post-flight analysis and record-keeping
- Integrate with automation for automated weather checks
- Use for passenger briefings ("Current conditions at destination...")

**Recommended configuration**:
- Enable CheckWX for all airfields in your area of operations
- Set update interval to 15 minutes (stay current)
- Create dashboard view with all route airfields visible
- Export METAR/TAF data for flight logs and company reports

**Compliance note**: CheckWX provides official weather data, but always follow your company's weather briefing procedures and regulatory requirements (e.g., Part 135 weather minimums in the US).

### For Glider Pilots

**TAF forecasts are critical for soaring conditions:**
- Use TAF to predict thermal development and cloud base trends
- Monitor multiple airfields to understand regional weather patterns
- Track wind direction changes (sea breeze fronts, convergence lines)
- Plan cross-country flights using en-route METAR for wind and cloud base

**Recommended configuration**:
- Enable CheckWX for your gliding site + cross-country turning points
- Set TAF update interval to 6 hours (default)
- Create automation: alert when TAF predicts favorable soaring conditions (e.g., TEMPO with thermal clouds)
- Use dashboard to display cloud base trends over time

**Soaring tip**: Combine CheckWX TAF with OpenWeatherMap hourly forecast for detailed thermal predictions. TAF gives official outlook, OWM provides hourly temperature trends for thermal strength.

## Technical Details (Advanced)

<details>
<summary>Click to expand technical implementation details</summary>

### Entity Naming Convention

CheckWX sensors use this pattern:

```
sensor.{airfield_slug}_metar
sensor.{airfield_slug}_taf
sensor.{airfield_slug}_station_info
```

Where `{airfield_slug}` is the airfield name converted to lowercase with spaces replaced by underscores.

**Examples**:
- Airfield: "Popham" → `sensor.popham_metar`
- Airfield: "New York JFK" → `sensor.new_york_jfk_metar`
- Airfield: "Shoreham (EGKA)" → `sensor.shoreham_egka__metar`

### Caching Behavior

**Multi-level cache architecture**:
1. **In-memory cache**: Stores last successful response per ICAO code (survives config reloads)
2. **Persistent file cache**: `config/.storage/hangar_assistant_cache/checkwx_{icao}.json` (survives restarts)

**Cache TTLs (Time To Live)**:
- **METAR**: 15 minutes (matches typical METAR update frequency)
- **TAF**: 6 hours (TAFs updated every 6 hours by meteorologists)
- **Station info**: 7 days (station data rarely changes)

**Cache lookup priority**:
1. Check in-memory cache (TTL not expired) → return cached data
2. Check persistent file cache (TTL not expired) → load into memory → return data
3. Call CheckWX API → store in both caches → return fresh data

**Cache invalidation**:
- Manual: Use `hangar_assistant.clear_cache` service
- Automatic: TTL expiration triggers fresh API call
- Restart: Persistent cache survives, in-memory cache rebuilt

**Why caching matters**:
- Protects against rate limits during Home Assistant restarts
- Reduces API calls by 80-90% (most requests hit cache)
- Ensures weather data available even if CheckWX API is temporarily unavailable

### API Endpoints Used

**CheckWX API base**: `https://api.checkwx.com`

**Endpoints**:
- **METAR**: `GET /metar/{icao}/decoded`
- **TAF**: `GET /taf/{icao}/decoded`
- **Station**: `GET /station/{icao}`

**Headers**:
```
X-API-Key: {your_api_key}
Accept: application/json
```

**Response format**: JSON with decoded aviation weather data

**Error handling**:
- 401 Unauthorized → Invalid API key (alert user)
- 404 Not Found → ICAO code not found (log warning, sensor shows "unavailable")
- 429 Too Many Requests → Rate limit exceeded (use cached data, alert user)
- 503 Service Unavailable → CheckWX API down (use cached data, log error)

### Rate Limit Tracking

Hangar Assistant tracks your CheckWX API usage:

**Stored in config entry**:
```python
entry.data["integrations"]["checkwx"]["rate_limit"] = {
    "requests_today": 142,
    "last_reset": "2026-01-22T00:00:00Z",
    "warning_threshold": 2850  # 95% of 3000
}
```

**Warning system**:
- At 95% of daily limit (2,850 requests): Warning logged, persistent notification created
- At 100% of limit (3,000 requests): API calls paused until midnight UTC reset

**Viewing your usage**:
- Check Home Assistant logs for daily summary
- View `sensor.checkwx_api_usage` (if implemented)
- Check CheckWX dashboard: [https://www.checkwx.com/dashboard](https://www.checkwx.com/dashboard)

### Sensor Attributes

**METAR Sensor** (`sensor.{airfield}_metar`):

| Attribute | Type | Example | Description |
|-----------|------|---------|-------------|
| `raw_text` | string | `"EGHP 221350Z 27008KT..."` | Raw METAR observation |
| `observation_time` | ISO datetime | `"2026-01-22T13:50:00Z"` | When observation was made |
| `temperature` | float | `9.0` | Temperature (°C) |
| `dewpoint` | float | `5.0` | Dew point (°C) |
| `wind_speed` | int | `8` | Wind speed (knots) |
| `wind_direction` | int | `270` | Wind direction (degrees) |
| `wind_gust` | int | `15` | Gust speed (knots, if present) |
| `visibility` | int | `9999` | Visibility (meters) |
| `clouds` | list | `[{"coverage": "FEW", "altitude": 2500}]` | Cloud layers |
| `barometer` | float | `1013.25` | QNH pressure (hPa) |
| `flight_category` | string | `"VFR"` | VFR/MVFR/IFR/LIFR |
| `icao` | string | `"EGHP"` | ICAO code |

**TAF Sensor** (`sensor.{airfield}_taf`):

| Attribute | Type | Example | Description |
|-----------|------|---------|-------------|
| `raw_text` | string | `"TAF EGHP 221100Z..."` | Raw TAF forecast |
| `issue_time` | ISO datetime | `"2026-01-22T11:00:00Z"` | Forecast issued time |
| `valid_from` | ISO datetime | `"2026-01-22T12:00:00Z"` | Forecast start |
| `valid_to` | ISO datetime | `"2026-01-23T12:00:00Z"` | Forecast end |
| `forecast_periods` | list | `[{...}, {...}]` | Parsed forecast periods |
| `icao` | string | `"EGHP"` | ICAO code |

**Station Info Sensor** (`sensor.{airfield}_station_info`):

| Attribute | Type | Example | Description |
|-----------|------|---------|-------------|
| `icao` | string | `"EGHP"` | ICAO code |
| `iata` | string | `"LHR"` | IATA code (if available) |
| `name` | string | `"Popham Airfield"` | Full station name |
| `elevation_ft` | int | `550` | Field elevation (feet) |
| `elevation_m` | float | `167.6` | Field elevation (meters) |
| `latitude` | float | `51.1947` | Latitude (decimal degrees) |
| `longitude` | float | `-1.2353` | Longitude (decimal degrees) |
| `country` | string | `"GB"` | Country code (ISO 3166) |

### Integration with AI Briefing

When CheckWX is enabled, AI Briefing automatically includes:
- Current METAR conditions (decoded into plain English)
- TAF forecast summary (predicted changes in next 6-12 hours)
- Trend analysis (improving/deteriorating/stable weather)
- GO/NO-GO recommendations based on official aviation weather

**Prompt enhancement**:
```
Current weather (METAR): {decoded_metar}
Forecast (TAF): {decoded_taf}
```

AI uses official aviation weather data to provide more accurate and regulation-compliant briefings.

### Configuration Structure

CheckWX settings stored in `entry.data["integrations"]["checkwx"]`:

```python
{
    "enabled": True,
    "api_key": "abc123def456ghi789jkl",
    "cache_enabled": True,
    "metar_update_interval": 15,  # minutes
    "taf_update_interval": 360,   # minutes (6 hours)
    "station_cache_days": 7,      # days
    "rate_limit": {
        "requests_today": 142,
        "last_reset": "2026-01-22T00:00:00Z"
    }
}
```

**Per-airfield**: No per-airfield settings required. CheckWX automatically enabled for any airfield with valid ICAO code.

### Services

**`hangar_assistant.clear_cache`**: Clears CheckWX cache (forces fresh API calls)

```yaml
service: hangar_assistant.clear_cache
data:
  integration: checkwx
  icao: EGHP  # Optional: clear specific airfield only
```

**`hangar_assistant.refresh_weather`**: Manually triggers weather update (bypasses update interval)

```yaml
service: hangar_assistant.refresh_weather
data:
  airfield: Popham  # Or ICAO code: EGHP
```

### Automation Example

**Alert when METAR changes significantly**:

```yaml
alias: CheckWX METAR Change Alert
description: Notify when wind or visibility changes significantly
trigger:
  - platform: state
    entity_id: sensor.popham_metar
    attribute: wind_direction
    # Trigger if wind direction changes by 30+ degrees
condition:
  - condition: template
    value_template: >
      {% set old_dir = trigger.from_state.attributes.wind_direction | int %}
      {% set new_dir = trigger.to_state.attributes.wind_direction | int %}
      {% set diff = (new_dir - old_dir) | abs %}
      {{ diff > 30 and diff < 330 }}
action:
  - service: notify.mobile_app_your_phone
    data:
      title: "Wind Shift at Popham"
      message: >
        Wind changed from {{ trigger.from_state.attributes.wind_direction }}° 
        to {{ trigger.to_state.attributes.wind_direction }}°.
        Current METAR: {{ states('sensor.popham_metar') }}
```

**Dashboard card showing all CheckWX sensors**:

```yaml
type: vertical-stack
title: Popham Weather (CheckWX)
cards:
  - type: markdown
    content: |
      **METAR**: {{ states('sensor.popham_metar') }}
      
      **Temperature**: {{ state_attr('sensor.popham_metar', 'temperature') }}°C
      **Wind**: {{ state_attr('sensor.popham_metar', 'wind_direction') }}° at {{ state_attr('sensor.popham_metar', 'wind_speed') }} kt
      **Visibility**: {{ state_attr('sensor.popham_metar', 'visibility') }} m
      **Clouds**: {{ state_attr('sensor.popham_metar', 'clouds') }}
      **QNH**: {{ state_attr('sensor.popham_metar', 'barometer') }} hPa
      
      **TAF**: {{ states('sensor.popham_taf') }}
      
      Valid: {{ state_attr('sensor.popham_taf', 'valid_from') }} to {{ state_attr('sensor.popham_taf', 'valid_to') }}
```

</details>

## Related Documentation

- **[Setup Wizard](setup_wizard.md)**: Initial configuration of Hangar Assistant (includes CheckWX setup)
- **[OpenWeatherMap Integration](openweathermap_integration.md)**: Alternative/complementary weather data source
- **[NOTAM Integration](notam_integration.md)**: Aviation notices and airspace restrictions
- **[AI Briefing](ai_briefing.md)**: Automated weather briefings using CheckWX data
- **[Glass Cockpit Dashboard](glass_cockpit_dashboard.md)**: Visualizing CheckWX sensors in dashboard

**Planning & Development**:
- **[CheckWX Integration Plan](../implemented/checkwx_integration_plan.md)**: Original planning document (developer-focused, now implemented)

**External Resources**:
- **[CheckWX Official Documentation](https://api.checkwx.com/documentation/)**: API reference and technical details
- **[METAR Decoder](https://www.aviationweather.gov/metar/help)**: NOAA guide to reading METAR reports
- **[TAF Guide](https://www.aviationweather.gov/taf/help)**: Understanding terminal aerodrome forecasts

## Version History

### v1.0 (Current)
- Initial CheckWX integration release
- METAR, TAF, and Station Info sensors
- Multi-level caching (memory + persistent file)
- Rate limit tracking and warnings
- Free tier support (3,000 requests/day)
- Integration with AI Briefing system

### Planned Enhancements
- **Graphical METAR decoder**: Visual representation of cloud layers, visibility, wind
- **Historical weather archive**: Store METAR/TAF history for trend analysis
- **Alert sensors**: Binary sensors for VFR/MVFR/IFR transitions
- **PIREP integration**: Pilot weather reports (if CheckWX adds support)
- **SIGMET/AIRMET**: Significant meteorological information (future CheckWX API feature)

---

**Questions or issues?** Please report bugs or request features on the [GitHub Issues](https://github.com/your-repo/ha-hangar-assistant/issues) page.

**Need help?** Join the [Home Assistant Community Forum](https://community.home-assistant.io/) and tag your question with `hangar-assistant`.
