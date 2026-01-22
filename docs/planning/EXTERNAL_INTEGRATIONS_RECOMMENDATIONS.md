# External Integrations Recommendations for Hangar Assistant

**Document Version**: 1.0  
**Date**: 21 January 2026  
**Status**: Planning / Recommendations

---

## Table of Contents
- [Current Integrations](#current-integrations)
- [High Priority Recommendations](#high-priority-recommendations)
- [Medium Priority Recommendations](#medium-priority-recommendations)
- [Future Considerations](#future-considerations)
- [Implementation Architecture](#implementation-architecture)
- [Cost Analysis](#cost-analysis)

---

## Current Integrations

### Implemented
1. **OpenWeatherMap (OWM) One Call API 3.0** *(Optional, Paid)*
   - Current weather data
   - 48-hour hourly forecast
   - 8-day daily forecast
   - Government weather alerts
   - UV index
   - Precipitation forecasting
   - **Status**: Fully implemented with multi-level caching

2. **UK NATS NOTAM (PIB XML Feed)** *(Free)*
   - Aviation Notices to Airmen
   - Location filtering (ICAO + proximity)
   - Daily scheduled updates
   - Persistent caching with graceful degradation
   - **Status**: Fully implemented

3. **Home Assistant Sensors** *(Native)*
   - Weather station data
   - Generic sensors for temperature, pressure, humidity, wind
   - **Status**: Primary data source with OWM as optional enhancement

---

## High Priority Recommendations

### 1. METAR/TAF Official Aviation Weather ⭐⭐⭐⭐⭐

**Description**: Official Meteorological Aerodrome Reports and Terminal Aerodrome Forecasts from aviation authorities.

**Benefits**:
- Industry-standard aviation weather format
- Accepted for official flight planning
- More reliable than consumer weather APIs
- TAF provides aviation-specific forecasts (typically 9-30 hours)
- Includes essential aviation data: cloud layers, visibility, wind shear

**Data Sources**:
- **NOAA Aviation Weather Center** (US) - FREE
  - API: `https://aviationweather.gov/api/data/metar`
  - `https://aviationweather.gov/api/data/taf`
- **UK Met Office DataPoint** (UK) - FREE (with registration)
  - API key required, generous limits
- **CheckWX Aviation Weather API** - FREE tier available
  - Clean REST API, 1000 requests/day free

**Implementation Complexity**: LOW
- Simple text parsing (METAR/TAF format is standardized)
- Cache-friendly (METARs update hourly, TAFs every 6 hours)
- No complex data structures

**Integration Priority**: **CRITICAL**
- Pilots expect METAR/TAF as the authoritative aviation weather source
- Complements OWM (OWM for trends/forecasts, METAR/TAF for official data)
- Essential for professional flight operations

**Recommended Approach**:
```python
# utils/aviation_weather.py
class AviationWeatherClient:
    """METAR/TAF client with multi-source fallback."""
    
    async def get_metar(self, icao: str) -> Optional[str]:
        """Fetch METAR for ICAO code."""
        # Try NOAA → CheckWX → Cache
        
    async def get_taf(self, icao: str) -> Optional[str]:
        """Fetch TAF for ICAO code."""
```

**Sensors Created**:
- `sensor.{airfield}_metar`: Raw METAR text
- `sensor.{airfield}_metar_decoded`: Parsed METAR data (JSON attributes)
- `sensor.{airfield}_taf`: Raw TAF text
- `sensor.{airfield}_taf_decoded`: Parsed TAF with trends
- `binary_sensor.{airfield}_conditions_vfr`: IFR/MVFR/VFR classification

---

### 2. Aviation Fuel Prices (Avgas & Jet-A) ⭐⭐⭐⭐

**Description**: Current fuel prices at airfields for trip planning and cost estimation.

**Benefits**:
- Trip cost calculation
- Find cheapest nearby fuel
- Track price trends over time
- Essential for cross-country planning

**Data Sources**:
- **AirNav.com** - FREE (scraping) or paid API
  - Comprehensive US coverage
  - Includes FBO information
- **Fuel Buddy** (Europe) - Potential API partnership
- **Skydemon Fuel Prices** - May have API access
- **Community-driven approach**: User-submitted prices via service call

**Implementation Complexity**: MEDIUM
- Web scraping requires careful rate limiting
- Data structure varies by source
- Prices need date/time stamps for freshness

**Integration Priority**: **HIGH**
- Frequently requested feature by pilots
- Differentiates from other weather-only apps
- Enables cost-based trip planning

**Recommended Approach**:
```python
# utils/fuel_prices.py
class FuelPriceClient:
    """Multi-source fuel price aggregator."""
    
    async def get_price(self, icao: str, fuel_type: str) -> Optional[Dict]:
        """Returns: {price, currency, date_reported, source}"""
        
    async def find_cheapest_nearby(self, lat, lon, radius_nm, fuel_type):
        """Find cheapest fuel within radius."""
```

**Sensors Created**:
- `sensor.{airfield}_avgas_price`: Current Avgas price
- `sensor.{airfield}_jeta_price`: Current Jet-A price
- `sensor.{airfield}_fuel_price_age`: Hours since last update
- `sensor.{airfield}_nearest_cheap_fuel`: Nearest cheapest fuel location

**User Submission Service**:
```yaml
service: hangar_assistant.report_fuel_price
data:
  airfield: EGKA
  fuel_type: avgas
  price: 2.45
  currency: GBP
```

---

### 3. ADS-B Aircraft Tracking ⭐⭐⭐⭐

**Description**: Real-time aircraft position tracking using Automatic Dependent Surveillance-Broadcast data.

**Benefits**:
- Track your own aircraft when flying
- Monitor airfield traffic
- Flight time logging automation
- Detect when aircraft enters/leaves hangar area
- Trigger maintenance reminders based on actual flight hours

**Data Sources**:
- **OpenSky Network** - FREE (academic/non-commercial)
  - REST API: `https://opensky-network.org/api/`
  - 4000 API credits/day (anonymous), more with account
- **ADS-B Exchange** - FREE API with registration
  - Global coverage, community-driven
- **FlightAware** - Paid API, excellent coverage
- **Local ADS-B Receiver** - FREE if user operates own receiver
  - Dump1090, FlightRadar24 feeder integration

**Implementation Complexity**: MEDIUM
- REST APIs are straightforward
- Websocket option for real-time updates
- Requires aircraft registration → ICAO24 mapping

**Integration Priority**: **HIGH**
- Enables automation based on flight activity
- Unique feature for Home Assistant aviation integration
- Supports maintenance tracking workflow

**Recommended Approach**:
```python
# utils/adsb_client.py
class ADSBClient:
    """ADS-B tracking with multi-source support."""
    
    async def get_aircraft_position(self, icao24: str) -> Optional[Dict]:
        """Returns: {lat, lon, altitude, velocity, heading, on_ground}"""
        
    async def get_airfield_traffic(self, lat, lon, radius_nm) -> List[Dict]:
        """Get all aircraft within radius."""
```

**Entities Created**:
- `device_tracker.{aircraft_reg}`: Aircraft location
- `sensor.{aircraft_reg}_altitude`: Current altitude
- `sensor.{aircraft_reg}_groundspeed`: Current speed
- `binary_sensor.{aircraft_reg}_in_flight`: True when airborne
- `binary_sensor.{aircraft_reg}_at_home_airfield`: Within radius of home base

**Automation Examples**:
```yaml
# Log flight when aircraft lands
- alias: "Log Flight Time"
  trigger:
    platform: state
    entity_id: binary_sensor.g_abcd_in_flight
    from: 'on'
    to: 'off'
  action:
    service: hangar_assistant.log_flight
    data:
      aircraft: G-ABCD
      duration: "{{ trigger.for }}"
```

---

### 4. Sunrise/Sunset/Civil Twilight ⭐⭐⭐⭐

**Description**: Official sunrise/sunset times and civil twilight calculations for VFR night rating compliance.

**Benefits**:
- VFR night rating compliance (30 mins after sunset → 30 mins before sunrise)
- Automatic GO/NO-GO based on daylight requirements
- Civil twilight for PPL night rating operations
- Essential for UK CAA VFR minima

**Data Sources**:
- **Home Assistant Sun Integration** - FREE (already available!)
  - `sun.sun` entity with sunrise/sunset
  - Nautical/civil twilight via attributes
- **USNO Astronomical Applications** - FREE
  - API: `https://aa.usno.navy.mil/api/`
  - More precise calculations

**Implementation Complexity**: VERY LOW
- HA sun integration already provides data
- Simple time comparisons
- Calculations can be done locally

**Integration Priority**: **CRITICAL**
- Required for UK VFR compliance
- Easy to implement (mostly already available)
- Essential for automated safety alerts

**Recommended Approach**:
```python
# Extend existing binary_sensor.py
class DaylightSuitabilitySensor(BinarySensorEntity):
    """Check if sufficient daylight for VFR operations."""
    
    def _check_daylight(self):
        # UK: 30 mins after sunrise → 30 mins before sunset
        # Night rating: Civil twilight end → Civil twilight start
```

**Entities Created**:
- `binary_sensor.{airfield}_vfr_daylight`: True if VFR daylight conditions
- `binary_sensor.{airfield}_night_rating_required`: True if night rating needed
- `sensor.{airfield}_minutes_until_vfr_end`: Countdown to VFR night

---

## Medium Priority Recommendations

### 5. SIGMET/AIRMET ⭐⭐⭐

**Description**: Significant Meteorological Information and Airmen's Meteorological Information - official weather hazard warnings for aviation.

**Benefits**:
- Severe weather warnings (icing, turbulence, convection)
- Area forecasts for meteorological hazards
- More specific than general weather alerts

**Data Sources**:
- **NOAA Aviation Weather Center** - FREE
- **UK Met Office WAFC** - FREE (with registration)
- **ICAO SIGMET feed** - FREE

**Implementation Complexity**: MEDIUM
- Text parsing required
- Geographic polygon matching
- Time-based validity periods

**Integration Priority**: MEDIUM
- Complements existing weather data
- Less critical than METAR/TAF
- Useful for cross-country planning

---

### 6. Airport/Airfield Database ⭐⭐⭐

**Description**: Comprehensive airfield information database with runway details, frequencies, services, and facilities.

**Benefits**:
- Auto-populate airfield configuration
- Runway length/surface/slope validation
- Operating hours and restrictions
- Contact frequencies (tower, ground, AFIS)

**Data Sources**:
- **OurAirports.com** - FREE, open data
  - CSV/JSON download, no API
  - Global coverage, updated regularly
- **FAA Airport Data** (US) - FREE
  - Official US airport database
- **UK AIP (eAIP)** - FREE but complex XML

**Implementation Complexity**: MEDIUM
- One-time database import
- Periodic updates (quarterly)
- Local SQLite database or JSON file

**Integration Priority**: MEDIUM
- Improves user experience (less manual config)
- Enables validation (runway length vs aircraft performance)
- Foundation for future features

---

### 7. PIREPs (Pilot Reports) ⭐⭐⭐

**Description**: Real pilot-reported weather conditions, turbulence, and icing reports.

**Benefits**:
- Real-world conditions from actual flights
- Icing and turbulence reports
- More accurate than model predictions

**Data Sources**:
- **NOAA Aviation Weather Center** - FREE
  - `/api/data/pirep`
- **CheckWX** - FREE tier

**Implementation Complexity**: LOW
- Simple text parsing
- Geographic/time filtering

**Integration Priority**: MEDIUM
- Valuable but not essential
- Complements METAR/TAF/SIGMET

---

### 8. Aircraft Maintenance Tracking ⭐⭐⭐

**Description**: Integration with maintenance tracking systems and service bulletins.

**Benefits**:
- Automatic maintenance reminders
- Airworthiness directive tracking
- Service bulletin notifications
- Flight hours/cycles tracking

**Data Sources**:
- **FAA Service Difficulty Reports** - FREE
- **EASA Airworthiness Directives** - FREE
- **Aircraft Logs** - User-provided API integration
- **Savvy Aviation** - Paid API (if available)

**Implementation Complexity**: HIGH
- Requires aircraft-specific data models
- Complex regulatory compliance logic
- Integration with user's maintenance logs

**Integration Priority**: MEDIUM
- Long-term strategic feature
- Requires significant development
- High value for professional operators

---

### 9. Weather Radar/Satellite Imagery ⭐⭐

**Description**: Visual weather radar and satellite images for convective weather avoidance.

**Benefits**:
- Visual representation of precipitation
- Storm cell identification
- Animated radar loops

**Data Sources**:
- **RainViewer API** - FREE
  - Global radar coverage
  - Simple API, well-documented
- **OpenWeatherMap** - Already integrated!
  - Maps API available
- **UK Met Office WMS** - FREE
  - Weather layers via WMS

**Implementation Complexity**: MEDIUM
- Image/tile serving
- Dashboard card integration
- Overlay on map

**Integration Priority**: LOW-MEDIUM
- Nice-to-have visualization
- HA Lovelace already supports image cards
- May be redundant with existing weather data

---

## Future Considerations

### 10. Flight Planning Integration ⭐⭐

**Description**: Integration with flight planning services for route optimization, fuel calculation, and NOTAM briefing.

**Potential Partners**:
- **SkyDemon** (popular in UK/Europe)
- **ForeFlight** (US standard)
- **RocketRoute**
- **Avplan** (Australia)

**Challenges**:
- APIs may not be publicly available
- Requires commercial partnerships
- Complex data models

---

### 11. Weight & Balance Calculator ⭐⭐

**Description**: Interactive weight and balance calculations with envelope checking.

**Benefits**:
- Pre-flight compliance checks
- Passenger/cargo configuration optimization
- CG envelope visualization

**Implementation**: 
- Could be local calculation (no external API)
- Requires aircraft-specific data entry

---

### 12. Weather Routing Optimization ⭐⭐

**Description**: AI-powered route optimization based on weather forecasts, winds aloft, and fuel efficiency.

**Potential Approach**:
- Use OWM forecast data
- Integrate winds aloft (NOAA, etc.)
- Local optimization algorithms

---

## Implementation Architecture

### Centralized Integration Management

All external integrations should follow the established "Integrations" configuration pattern:

```python
entry.data["integrations"] = {
    "metar_taf": {
        "enabled": bool,
        "source": str,  # "noaa", "checkwx", "metoffice"
        "api_key": str,  # if required
        "update_interval": int,
        "cache_ttl": int
    },
    "fuel_prices": {
        "enabled": bool,
        "source": str,  # "airnav", "community"
        "update_interval": int,
        "allow_user_submissions": bool
    },
    "adsb": {
        "enabled": bool,
        "source": str,  # "opensky", "adsbexchange", "local"
        "api_key": str,
        "aircraft_icao24": str,  # per-aircraft config
        "update_interval": int
    },
    "sigmet_airmet": {
        "enabled": bool,
        "source": str,
        "update_interval": int
    }
}
```

### Client Pattern

Each integration gets a dedicated client in `utils/`:

```
utils/
├── aviation_weather.py    # METAR/TAF client
├── fuel_prices.py         # Fuel price aggregator
├── adsb_client.py         # ADS-B tracking
├── sigmet_client.py       # SIGMET/AIRMET parser
└── airport_database.py    # Airfield info lookup
```

### Caching Strategy

All integrations must implement:
1. **Memory cache** (session-level, LRU eviction)
2. **Persistent cache** (survives restarts)
3. **Graceful degradation** (use stale data on failure)
4. **Rate limiting** (respect API limits)

---

## Cost Analysis

### Free Tier Services (Recommended Priority)

| Service | Cost | Rate Limit | Priority |
|---------|------|------------|----------|
| NOAA METAR/TAF | FREE | No official limit | ⭐⭐⭐⭐⭐ |
| CheckWX | FREE | 1000 req/day | ⭐⭐⭐⭐⭐ |
| OpenSky Network | FREE | 4000 credits/day | ⭐⭐⭐⭐ |
| NATS NOTAM | FREE | No limit | ✅ Implemented |
| Sun Integration | FREE | Local | ⭐⭐⭐⭐ |
| OurAirports | FREE | N/A (download) | ⭐⭐⭐ |
| RainViewer | FREE | 500 req/min | ⭐⭐ |

### Paid Services (Optional Enhancement)

| Service | Cost | Benefit | Priority |
|---------|------|---------|----------|
| OpenWeatherMap | $0.0012/call | Professional weather | ✅ Implemented |
| FlightAware | $89/mo | Superior ADS-B tracking | ⭐⭐ |
| ForeFlight API | Partnership | Flight planning integration | ⭐ (future) |

### Community Contribution Model

For fuel prices and maintenance logs, consider a community-driven approach:
- Users submit data via services
- Aggregate and anonymize
- Share back to community
- Optional: Central database with user opt-in

---

## Recommended Implementation Roadmap

### Phase 1: Aviation Weather (Q1 2026)
1. **METAR/TAF Integration** (2-3 days)
   - NOAA client implementation
   - METAR parsing library
   - Sensors and attributes
2. **Daylight/Twilight Sensors** (1 day)
   - Use existing HA sun integration
   - VFR daylight binary sensors
   - Night rating requirement detection

### Phase 2: Aircraft Tracking (Q2 2026)
3. **ADS-B Integration** (3-4 days)
   - OpenSky Network client
   - Device tracker entities
   - Flight logging automation
4. **SIGMET/AIRMET** (2 days)
   - NOAA SIGMET parser
   - Geographic filtering
   - Alert sensors

### Phase 3: Trip Planning (Q3 2026)
5. **Fuel Prices** (3-4 days)
   - Multi-source scraping/API
   - User submission service
   - Price comparison sensors
6. **Airport Database** (2-3 days)
   - OurAirports import
   - Local SQLite database
   - Auto-configuration helper

### Phase 4: Advanced Features (Q4 2026)
7. **PIREPs** (2 days)
8. **Weather Radar Overlay** (3 days)
9. **Maintenance Tracking** (long-term)

---

## Success Metrics

Track adoption and value of each integration:

- **Usage rate**: % of users enabling each integration
- **API call efficiency**: Cache hit ratio, API costs
- **User feedback**: GitHub issues, feature requests
- **Automation triggers**: How often entities are used in automations
- **Performance impact**: Load times, memory usage

---

## Backward Compatibility

**CRITICAL**: All new integrations must:
- Default to **disabled** for existing installations
- Provide sensible defaults when enabled
- Never break existing sensor functionality
- Include migration logic if config structure changes
- Gracefully degrade if API unavailable

---

## Conclusion

### Immediate Next Steps (High ROI)
1. ✅ **METAR/TAF integration** - Industry standard, free, easy implementation
2. ✅ **Daylight/twilight sensors** - Quick win using existing HA features
3. ✅ **ADS-B tracking** - Unique differentiator, enables powerful automations

### Strategic Priorities
- Focus on **free, reliable data sources** first
- Prioritize **aviation-specific** data over general weather
- Enable **automation and compliance** use cases
- Maintain **performance and reliability** standards

### Competitive Advantage
- Most weather apps are standalone - HA integration enables **automation**
- Community-driven data (fuel prices, user reports) creates **network effect**
- **Compliance-focused** features (VFR minima, night rating) serve professional pilots
- **All-in-one** aviation platform within Home Assistant ecosystem

The recommended integrations would transform Hangar Assistant from a weather dashboard into a comprehensive aviation safety and operations platform, while maintaining the core principles of reliability, backward compatibility, and graceful degradation.
