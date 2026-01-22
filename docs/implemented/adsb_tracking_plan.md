# ADS-B Aircraft Tracking Integration

**Status**: IMPLEMENTED - Released in v2601.5.0 (22 January 2026)  
**Original Planning Date**: 22 January 2026  
**Location**: Moved from docs/planning/ to docs/implemented/

## Quick Links
- Implementation:
  - Core manager: [custom_components/hangar_assistant/utils/adsb_manager.py](custom_components/hangar_assistant/utils/adsb_manager.py)
  - Device trackers: [custom_components/hangar_assistant/utils/adsb_device_tracker.py](custom_components/hangar_assistant/utils/adsb_device_tracker.py)
  - Data sources: [custom_components/hangar_assistant/utils/dump1090_client.py](custom_components/hangar_assistant/utils/dump1090_client.py), [custom_components/hangar_assistant/utils/opensky_client.py](custom_components/hangar_assistant/utils/opensky_client.py), [custom_components/hangar_assistant/utils/ogn_client.py](custom_components/hangar_assistant/utils/ogn_client.py)
  - Config flow: [custom_components/hangar_assistant/adsb_config_flow.py](custom_components/hangar_assistant/adsb_config_flow.py)
  - Dashboard: [custom_components/hangar_assistant/dashboard_templates/glass_cockpit.yaml](custom_components/hangar_assistant/dashboard_templates/glass_cockpit.yaml)
- Tests: [tests/test_adsb_integration.py](tests/test_adsb_integration.py); [tests/test_adsb_device_tracker.py](tests/test_adsb_device_tracker.py); [tests/test_opensky_client.py](tests/test_opensky_client.py)
- Documentation: [docs/features/adsb_tracking.md](../features/adsb_tracking.md)

## Implementation Summary
- Multi-source ADS-B manager with deduplication and caching
- Device tracker manager emitting aircraft positions for dashboards
- Config flow coverage for OpenSky, dump1090, and OGN defaults
- Dashboard map integration for ADS-B/FLARM aircraft
- Unit tests covering manager, clients, and device tracker helper
- Backward compatible opt-in feature (disabled by default)

## Table of Contents
- [Executive Summary](#executive-summary)
- [User Benefits](#user-benefits)
- [Technical Architecture](#technical-architecture)
- [Data Sources & Abstraction Layer](#data-sources--abstraction-layer)
- [Entity Design](#entity-design)
- [Dashboard Integration](#dashboard-integration)
- [Privacy & Security Considerations](#privacy--security-considerations)
- [Configuration Flow](#configuration-flow)
- [Implementation Phases](#implementation-phases)
- [Testing Strategy](#testing-strategy)
- [Future Enhancements](#future-enhancements)

---

## Executive Summary

**What**: Real-time aircraft tracking using ADS-B (Automatic Dependent Surveillance-Broadcast) data for airfield traffic awareness and individual aircraft location monitoring.

**Why**: Pilots need situational awareness of nearby traffic patterns, and aircraft owners want to track their aircraft when leased/rented or flown by others.

**How**: Multi-source abstraction layer supporting:
- **Local**: dump1090 JSON output (for users with ADS-B receivers)
- **API**: FlightRadar24 API and FlightAware's AeroAPI
- **Optional**: ADS-B Exchange, OpenSky Network

**Key Features**:
- RADAR-style map overlay showing aircraft within configurable radius of airfield
- Device tracker entities for linked aircraft (appear on Home Assistant map)
- Traffic count sensors (total, by altitude band, by direction)
- Nearest aircraft sensor with distance/bearing
- Historical track logging for safety analysis
- Integration with existing dashboard system

---

## User Benefits

### For Airfield Operators/Pilots
- **Real-time traffic awareness**: See who's in the pattern before you taxi
- **Pattern monitoring**: Track circuit traffic density for optimal departure timing
- **Safety enhancement**: Avoid conflicts by knowing where other aircraft are
- **Historical analysis**: Review traffic patterns for specific times/days
- **Weather correlation**: Cross-reference traffic with weather conditions

### For Aircraft Owners
- **Location tracking**: Know where your aircraft is when others fly it
- **Flight monitoring**: See departure/arrival times, route, altitude
- **Maintenance logging**: Track hours flown automatically from ADS-B data
- **Theft detection**: Alert if aircraft moves unexpectedly
- **Insurance compliance**: Provide flight logs for insurance requirements

### For Flight Schools/Clubs
- **Fleet tracking**: Monitor all club aircraft on single dashboard
- **Utilization metrics**: Track which aircraft are most/least used
- **Safety oversight**: Review student pilot patterns and behaviors
- **Cost allocation**: Accurate flight time tracking for billing

---

## Technical Architecture

### Overview
```
┌─────────────────────────────────────────────────────────────┐
│                    Home Assistant                            │
│  ┌────────────────────────────────────────────────────┐    │
│  │         Hangar Assistant Integration               │    │
│  │                                                     │    │
│  │  ┌──────────────────────────────────────────────┐  │    │
│  │  │      ADSBClientBase (Abstraction Layer)      │  │    │
│  │  └───────────────────┬──────────────────────────┘  │    │
│  │                      │                              │    │
│  │         ┌────────────┼────────────┬────────────┐   │    │
│  │         │            │            │            │   │    │
│  │   ┌─────▼─────┐ ┌───▼────┐ ┌────▼───┐ ┌──────▼──┐ │    │
│  │   │Dump1090   │ │FlightR.│ │FlightA.│ │OpenSky  │ │    │
│  │   │Client     │ │Client  │ │Client  │ │Client   │ │    │
│  │   └───────────┘ └────────┘ └────────┘ └─────────┘ │    │
│  │                                                     │    │
│  │  ┌──────────────────────────────────────────────┐  │    │
│  │  │            Entity Manager                    │  │    │
│  │  │  - Device Trackers (per aircraft)            │  │    │
│  │  │  - Sensors (traffic count, nearest aircraft) │  │    │
│  │  │  - Binary Sensors (aircraft in pattern)      │  │    │
│  │  └──────────────────────────────────────────────┘  │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

**1. ADSBClientBase (Abstract Base Class)**
- Common interface for all data sources
- Standardized aircraft data model
- Caching strategy (memory + persistent)
- Rate limit protection
- Error handling and graceful degradation
- **Data source prioritization and deduplication**

**2. Data Source Clients** (Priority Order)
- `Dump1090Client`: Local receiver integration (JSON feed) - **PRIORITY 1** (always preferred)
- `OpenSkyClient`: OpenSky Network REST API (free, rate limited, includes FLARM) - **PRIORITY 2** (enabled by default)
- `OGNClient`: Open Gliding Network (free, glider-focused FLARM data) - **PRIORITY 3** (enabled by default)
- `ADSBExchangeClient`: ADS-B Exchange API v2 (free tier available, rate limited) - **PRIORITY 4** (disabled by default)
- `FlightRadar24Client`: FR24 API (paid tier required for real-time) - **PRIORITY 5** (disabled by default)
- `FlightAwareClient`: AeroAPI (paid subscription) - **PRIORITY 6** (disabled by default)

**3. Entity Managers**
- `ADSBAircraftTracker`: Device tracker for individual aircraft
- `ADSBTrafficSensor`: Traffic count and stats for airfields
- `ADSBNearestSensor`: Closest aircraft to airfield
- `ADSBAircraftInPatternBinarySensor`: Detects if aircraft is circling airfield

**4. Data Source Prioritization & Deduplication**

**Problem**: Multiple data sources can report the same aircraft (e.g., dump1090 sees local aircraft, OpenSky sees same aircraft via network receivers).

**Solution**: Priority-based deduplication system:

1. **Query all enabled sources in parallel** (performance optimization)
2. **Deduplicate by ICAO24 hex code** (unique aircraft identifier)
3. **Priority order** (highest priority wins):
   - **Local dump1090**: Most accurate (direct reception), lowest latency
   - **OpenSky Network**: Good coverage, includes FLARM (gliders)
   - **Open Gliding Network**: Glider-specific, FLARM only
   - **FlightRadar24**: Commercial quality, paid only
   - **FlightAware**: USA-focused, paid only

4. **Merge non-conflicting data**: If higher-priority source missing data (e.g., no aircraft type), fill from lower-priority source

**Example Deduplication**:
```python
aircraft_by_icao24 = {}

for source in [dump1090, opensky, ogn, fr24, flightaware]:
    if not source.enabled:
        continue
    
    aircraft_list = await source.get_aircraft_near_location(...)
    
    for aircraft in aircraft_list:
        icao24 = aircraft.icao24
        
        if icao24 not in aircraft_by_icao24:
            # New aircraft, add it
            aircraft_by_icao24[icao24] = aircraft
        else:
            # Duplicate, merge missing data from lower-priority source
            existing = aircraft_by_icao24[icao24]
            if not existing.aircraft_type and aircraft.aircraft_type:
                existing.aircraft_type = aircraft.aircraft_type
            # Keep position/speed from higher-priority source
```

**User Control**: Config option to disable deduplication (show all sources separately) for debugging.

---

## Data Sources & Abstraction Layer

### ADSBClientBase Interface
```python
class ADSBClientBase:
    """Abstract base class for ADS-B data sources.
    
    All clients must implement this interface for consistent behavior.
    
    Inputs:
        - hass: Home Assistant instance
        - config: Client-specific configuration
        - cache_enabled: Enable/disable caching
        - cache_ttl_seconds: Cache lifetime (default: 30 seconds for real-time)
    
    Outputs:
        - Standardized aircraft data dictionaries
        - Cache statistics
        - Health monitoring data
    
    Used by:
        - Device tracker entities
        - Sensor entities
        - Dashboard components
    """
    
    @abstractmethod
    async def get_aircraft_by_registration(self, registration: str) -> Optional[AircraftData]:
        """Get data for specific aircraft by registration (e.g., G-ABCD).
        
        Args:
            registration: Aircraft registration/tail number
        
        Returns:
            AircraftData dict or None if not found
        """
        pass
    
    @abstractmethod
    async def get_aircraft_by_icao24(self, icao24: str) -> Optional[AircraftData]:
        """Get data for specific aircraft by ICAO 24-bit address.
        
        Args:
            icao24: ICAO 24-bit transponder hex code (e.g., "4CA1E3")
        
        Returns:
            AircraftData dict or None if not found
        """
        pass
    
    @abstractmethod
    async def get_aircraft_near_location(
        self,
        latitude: float,
        longitude: float,
        radius_nm: float = 10
    ) -> List[AircraftData]:
        """Get all aircraft within radius of location.
        
        Args:
            latitude: Center point latitude
            longitude: Center point longitude
            radius_nm: Search radius in nautical miles
        
        Returns:
            List of AircraftData dicts within radius
        """
        pass
    
    @abstractmethod
    async def clear_cache(self) -> None:
        """Clear all cached data."""
        pass
    
    @abstractmethod
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring."""
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test connection to data source.
        
        Returns:
            True if connection successful, False otherwise
        """
        pass
```

### AircraftData Model
```python
@dataclass
class AircraftData:
    """Standardized aircraft data structure across all sources.
    
    All fields optional except those marked as required.
    Clients should populate as many fields as available from their source.
    """
    
    # Identification (at least one required)
    registration: Optional[str] = None  # e.g., "G-ABCD", "N12345"
    icao24: Optional[str] = None        # ICAO 24-bit hex code (e.g., "4CA1E3")
    callsign: Optional[str] = None      # Flight callsign (e.g., "BAW123")
    
    # Position (required for mapping)
    latitude: float                     # Decimal degrees
    longitude: float                    # Decimal degrees
    altitude_ft: Optional[int] = None   # Altitude above sea level (feet)
    
    # Velocity
    ground_speed_kts: Optional[int] = None  # Ground speed (knots)
    vertical_rate_fpm: Optional[int] = None # Vertical rate (feet per minute)
    track_deg: Optional[int] = None         # True track (degrees, 0-360)
    heading_deg: Optional[int] = None       # True heading (degrees, 0-360)
    
    # Aircraft Type
    aircraft_type: Optional[str] = None     # ICAO type code (e.g., "C172", "PA28")
    aircraft_description: Optional[str] = None  # Human readable (e.g., "Cessna 172")
    
    # Source Metadata
    source: str                         # "dump1090", "flightradar24", "flightaware", "opensky"
    last_seen: datetime                 # UTC timestamp of last position update
    squawk: Optional[str] = None        # Transponder squawk code (e.g., "7000")
    on_ground: Optional[bool] = None    # Is aircraft on ground?
    
    # Extended Data (source-dependent)
    origin_airport: Optional[str] = None    # ICAO code of departure airport
    destination_airport: Optional[str] = None  # ICAO code of arrival airport
    distance_nm: Optional[float] = None     # Distance from reference point (nautical miles)
    bearing_deg: Optional[int] = None       # Bearing from reference point (degrees)
```

### Data Source Implementations

#### 1. Dump1090Client (Local ADS-B Receiver)
**Data Source**: dump1090 JSON output (local network)  
**Cost**: Free (hardware required)  
**Update Rate**: 1-2 seconds  
**Coverage**: ~150nm radius (line-of-sight dependent)

**Configuration**:
```python
{
    "source": "dump1090",
    "enabled": True,
    "host": "192.168.1.100",  # dump1090 host IP
    "port": 8080,             # Default dump1090 web port
    "endpoint": "/data/aircraft.json",  # Default JSON endpoint
    "update_interval": 2,     # Seconds between polls
    "timeout": 5              # Connection timeout
}
```

**Advantages**:
- Real-time data (no API delays)
- No rate limits
- No recurring costs
- Complete control over data
- Works offline

**Limitations**:
- Requires hardware investment (RTL-SDR dongle ~£30, antenna)
- Limited to line-of-sight coverage
- No historical data
- No aircraft type/registration lookup without additional database
- Setup complexity for non-technical users

**Implementation Notes**:
- Parse `aircraft.json` format from dump1090
- Supplement with local aircraft database for registration/type lookup
- Cache last 100 seen aircraft in memory for pattern detection
- Support multiple dump1090 instances (e.g., multiple sites)

#### 2. FlightRadar24Client (API Integration)
**Data Source**: FlightRadar24 Data API  
**Cost**: Business subscription (~$500/month minimum)  
**Update Rate**: Real-time (configurable, 5-30 seconds)  
**Coverage**: Global

**Configuration**:
```python
{
    "source": "flightradar24",
    "enabled": False,  # Disabled by default (expensive)
    "api_key": "...",  # Business API key
    "subscription_tier": "business",  # "business", "enterprise"
    "update_interval": 10,  # Seconds between API calls
    "cache_ttl": 30,        # Cache TTL in seconds
    "rate_limit_per_minute": 600  # Tier-dependent
}
```

**Advantages**:
- Global coverage
- Rich aircraft metadata (type, registration, photos)
- Flight plan data (origin/destination)
- Historical track data
- Reliable uptime

**Limitations**:
- Expensive (not suitable for hobbyists)
- API rate limits
- Requires internet connection
- Subscription required

**Implementation Notes**:
- Implement strict rate limiting (stay under API quota)
- Multi-level caching (memory + persistent)
- Graceful degradation to local data if quota exceeded
- Track API usage in sensor for monitoring

#### 3. FlightAwareClient (AeroAPI Integration)
**Data Source**: FlightAware AeroAPI v4  
**Cost**: Starter ($80/month), Standard ($250/month), Enterprise ($500/month)  
**Update Rate**: Real-time (5-15 seconds)  
**Coverage**: Global (USA/Canada best, worldwide available)

**Configuration**:
```python
{
    "source": "flightaware",
    "enabled": False,  # Disabled by default
    "api_key": "...",  # AeroAPI key
    "subscription_tier": "starter",  # "starter", "standard", "enterprise"
    "update_interval": 15,  # Seconds
    "cache_ttl": 30,
    "rate_limit_per_hour": 500  # Tier-dependent
}
```

**Advantages**:
- More affordable than FR24 for basic use
- Excellent USA/Canada coverage
- Rich metadata (photos, aircraft details)
- Historical data available
- REST API (easier integration)

**Limitations**:
- Still expensive for hobbyists
- Best coverage in North America
- Rate limits
- Requires internet

**Implementation Notes**:
- Use `/flights/{ident}/position` endpoint for tracking
- Use `/airports/{icao}/flights` for airfield traffic
- Implement pagination for large result sets
- Cache aggressively to stay under rate limits

#### 4. OpenSkyClient (Free Community Network) - **DEFAULT ENABLED**
**Data Source**: OpenSky Network REST API  
**Cost**: Free (anonymous), Free+ (with account), Premium ($10/month)  
**Update Rate**: 10 seconds (anonymous), 5 seconds (with account/premium)  
**Coverage**: Global (variable quality)  
**Data Types**: ADS-B + FLARM (gliders included)

**Configuration**:
```python
{
    "source": "opensky",
    "enabled": True,  # ✅ ENABLED BY DEFAULT (free, no key required)
    "username": None,  # Optional (free account for higher limits)
    "password": None,  # Optional (free account for higher limits)
    "update_interval": 10,  # 10s anonymous, 5s with account
    "cache_ttl": 60,
    "daily_credit_limit": 400,  # Anonymous: 400 credits/day
    "with_account_limit": 4000  # With free account: 4000 credits/day
}
```

**Rate Limit Details**:
- **Anonymous**: 400 API credits per day (~400 requests with bbox filter)
- **Free Account**: 4000 API credits per day (10x increase, no cost)
- **Premium**: No published limit (~unlimited for reasonable use)
- **Credit Cost**: Varies by query type (simple queries = 1 credit, complex = 4 credits)
- **Reset**: Daily at 00:00 UTC

**Advantages**:
- FREE for basic use (anonymous)
- FREE account gives 10x rate limit increase (no credit card)
- Global coverage
- Includes FLARM data (glider tracking)
- Academic/research-friendly
- Premium tier affordable ($10/month)

**Limitations**:
- Aggressive rate limiting on free tier
- Data quality varies by region
- Limited historical data on free tier
- No flight plan data
- Requires internet

**Implementation Notes**:
- Use `/states/all` endpoint with bounding box filter
- Implement exponential backoff on rate limit errors
- Cache heavily (60+ second TTL on anonymous, 30s with account)
- Encourage users to create free account (10x rate limit increase)
- Provide clear credit usage tracking in diagnostics sensor
- Show "Create Free Account" prompt when approaching daily limit

#### 5. OGNClient (Open Gliding Network) - **DEFAULT ENABLED**
**Data Source**: Open Gliding Network APRS feed  
**Cost**: 100% Free (community-operated)  
**Update Rate**: 5-10 seconds (real-time APRS)  
**Coverage**: Europe (excellent), USA (growing), glider-focused  
**Data Types**: FLARM only (gliders, motor gliders, some towplanes)

**Configuration**:
```python
{
    "source": "ogn",
    "enabled": True,  # ✅ ENABLED BY DEFAULT (free, no key required)
    "aprs_server": "aprs.glidernet.org",
    "aprs_port": 14580,
    "aprs_filter": "r/lat/lon/radius",  # APRS radius filter
    "update_interval": 10,  # seconds
    "cache_ttl": 30,
    "callsign": "HA-HANGAR",  # Client identification
    "use_ddb": True  # Use OGN Device Database for aircraft type lookup
}
```

**Advantages**:
- 100% FREE, no rate limits
- Real-time APRS feed (very low latency)
- Excellent glider coverage in Europe
- Includes glider type database (OGN DDB)
- No signup or API key required
- Community-supported (donations welcome)
- FLARM-equipped aircraft only (privacy-conscious pilots)

**Limitations**:
- FLARM devices only (no pure ADS-B)
- Coverage varies by region (best in Europe)
- Requires APRS client implementation
- Less reliable than commercial APIs
- No historical data
- No flight plan data

**Implementation Notes**:
- Use Python `aprslib` for APRS connection
- Parse APRS packets to extract position, altitude, speed
- Use OGN Device Database (DDB) for aircraft type/registration lookup
- Implement automatic reconnection (APRS can disconnect)
- Filter by geographic radius (reduce bandwidth)
- Respect community guidelines (no excessive polling)

**OGN APRS Packet Example**:
```
FLRDD1234>APRS,qAS,RECEIVER:/093045h5123.45N/00123.45W'123/045/A=002500 !W12! id06DD1234 +020fpm +0.5rot 5.5dB 0e -0.3kHz gps2x3
```

**Parsed Data**:
- ICAO24: `DD1234` (FLARM ID)
- Position: `51.3908°N, 1.3908°W`
- Altitude: `2500ft`
- Ground speed: `45kts`
- Track: `123°`
- Vertical rate: `+20fpm`
- Turn rate: `+0.5°/s` (useful for pattern detection)

**Use Cases**:
- Glider tracking at soaring sites
- Gliding club fleet management
- Towplane tracking (if FLARM-equipped)
- Cross-country glider monitoring
- Thermal activity visualization (multiple gliders circling)

#### 6. ADSBExchangeClient (Community ADS-B Network)
**Data Source**: ADS-B Exchange API v2 (via RapidAPI)  
**Cost**: Free tier (limited), Paid tiers ($5-50/month)  
**Update Rate**: Real-time (5-10 seconds depending on tier)  
**Coverage**: Global (excellent, community-contributed)  
**Data Types**: ADS-B only (no FLARM)

**Configuration**:
```python
{
    "source": "adsbexchange",
    "enabled": False,  # Disabled by default (requires RapidAPI key)
    "api_key": "",  # RapidAPI key
    "subscription_tier": "free",  # "free", "basic", "pro", "ultra"
    "update_interval": 10,  # seconds
    "cache_ttl": 30,
    "rate_limit_per_day": 500,  # Free tier limit
    "use_rapidapi": True  # ADS-B Exchange uses RapidAPI
}
```

**Pricing Tiers (via RapidAPI)**:
- **Free**: 500 requests/day, 10 requests/minute (good for testing)
- **Basic**: $5/month, 10,000 requests/day, 100 requests/minute
- **Pro**: $20/month, 100,000 requests/day, 500 requests/minute
- **Ultra**: $50/month, 1,000,000 requests/day, 2000 requests/minute

**Advantages**:
- Community-driven (similar philosophy to OpenSky)
- Free tier available (500 requests/day sufficient for hobbyists)
- Affordable paid tiers (start at $5/month)
- Excellent global coverage (large receiver network)
- Real-time data (low latency)
- Rich metadata (aircraft type, registration, photos via links)
- Military aircraft filtering options
- No complex authentication (RapidAPI key only)

**Limitations**:
- Requires RapidAPI account (extra step vs. direct API)
- Free tier limited (500 requests/day = ~1 aircraft every 3 minutes)
- No FLARM data (ADS-B only)
- Rate limits enforced strictly
- Commercial use requires paid tier

**Implementation Notes**:
- Use RapidAPI endpoint: `https://adsbexchange-com1.p.rapidapi.com/v2/`
- Endpoints available:
  - `/lat/{lat}/lon/{lon}/dist/{dist}/` - Aircraft within radius
  - `/icao/{icao}/` - Track specific aircraft
  - `/registration/{reg}/` - Search by registration
- Include RapidAPI headers: `x-rapidapi-key`, `x-rapidapi-host`
- Implement request counting (track daily usage)
- Cache aggressively on free tier (30-60s TTL)
- Graceful degradation when daily limit reached
- Show upgrade prompt when approaching free tier limit

**API Response Format**:
```json
{
  "ac": [
    {
      "hex": "4ca1e3",
      "type": "adsb_icao",
      "flight": "GABCD",
      "r": "G-ABCD",
      "t": "C172",
      "desc": "Cessna 172 Skyhawk",
      "alt_baro": 2500,
      "alt_geom": 2480,
      "gs": 95,
      "track": 180,
      "baro_rate": -320,
      "squawk": "7000",
      "lat": 51.2345,
      "lon": -1.2345,
      "seen_pos": 0.5,
      "seen": 0.2
    }
  ],
  "total": 1,
  "ctime": 1737560000,
  "ptime": 1737559990
}
```

**Rate Limit Handling**:
```python
if response.status == 429:
    # Rate limited
    _LOGGER.warning("ADS-B Exchange rate limit reached")
    remaining_time = self._calculate_reset_time()
    
    if self._subscription_tier == "free":
        # Show upgrade prompt
        await self._notify_upgrade_option(
            f"Daily limit reached. Upgrade to Basic ($5/mo) for 20x more requests."
        )
    
    return await self._read_stale_cache()
```

**Request Tracking**:
```python
class ADSBExchangeClient:
    def __init__(self, ...):
        self._requests_today = 0
        self._requests_reset_time = datetime.utcnow().replace(
            hour=0, minute=0, second=0
        ) + timedelta(days=1)
    
    async def _increment_request_count(self):
        """Track API usage for rate limit monitoring."""
        # Reset counter at midnight UTC
        if datetime.utcnow() >= self._requests_reset_time:
            self._requests_today = 0
            self._requests_reset_time += timedelta(days=1)
        
        self._requests_today += 1
        
        # Warn at 80% of limit
        if self._subscription_tier == "free" and self._requests_today >= 400:
            _LOGGER.warning(
                "ADS-B Exchange: %d/500 requests used today",
                self._requests_today
            )
```

**Comparison to OpenSky**:
- **Coverage**: ADS-B Exchange often better (larger receiver network)
- **Cost**: OpenSky free tier more generous (4000 vs 500 requests with account)
- **Data**: ADS-B Exchange includes richer metadata (aircraft descriptions)
- **Philosophy**: Both community-driven, but ADS-B Exchange monetizes more
- **Ease**: OpenSky simpler (no RapidAPI middleman)

**Recommended For**:
- Users who exceed OpenSky free tier limits
- Users wanting richer aircraft metadata
- Professional operations willing to pay $5-20/month
- Regions with better ADS-B Exchange coverage

---

## Entity Design

### 1. Device Tracker Entities (Per Aircraft)

**Entity ID Pattern**: `device_tracker.{aircraft_slug}`  
**Example**: `device_tracker.g_abcd_aircraft`

**Purpose**: Track individual aircraft location on Home Assistant map.

**Attributes**:
```python
{
    "registration": "G-ABCD",
    "icao24": "4CA1E3",
    "callsign": "GABCD",
    "altitude_ft": 2500,
    "ground_speed_kts": 95,
    "vertical_rate_fpm": -300,
    "track_deg": 180,
    "heading_deg": 182,
    "aircraft_type": "C172",
    "aircraft_description": "Cessna 172 Skyhawk",
    "squawk": "7000",
    "on_ground": False,
    "last_seen": "2026-01-22T14:32:15Z",
    "source": "dump1090",
    "distance_from_home_nm": 12.3,
    "bearing_from_home_deg": 045,
    "nearest_airfield": "EGHP",
    "nearest_airfield_distance_nm": 3.2,
    "flight_time_today_hours": 1.8
}
```

**State**: `home`, `away`, `airborne`, `unknown`

**Device Info**: Groups with aircraft entity (links to existing aircraft device)

### 2. Traffic Count Sensor (Per Airfield)

**Entity ID Pattern**: `sensor.{airfield_slug}_aircraft_traffic_count`  
**Example**: `sensor.popham_aircraft_traffic_count`

**Purpose**: Show total aircraft within monitoring radius of airfield.

**State**: Integer (number of aircraft)

**Attributes**:
```python
{
    "total_aircraft": 8,
    "aircraft_by_altitude": {
        "pattern": 3,          # < 1500ft AGL
        "traffic_altitude": 4, # 1500-5000ft
        "cruise": 1            # > 5000ft
    },
    "aircraft_by_direction": {
        "inbound": 2,   # Heading toward airfield
        "outbound": 3,  # Heading away
        "transiting": 3 # Crossing/parallel
    },
    "aircraft_on_ground": 0,
    "aircraft_list": [
        {
            "registration": "G-ABCD",
            "altitude_ft": 1200,
            "distance_nm": 3.5,
            "bearing_deg": 180,
            "track_deg": 360
        }
        # ... more aircraft
    ],
    "monitoring_radius_nm": 10,
    "last_updated": "2026-01-22T14:32:15Z",
    "data_source": "dump1090"
}
```

**Use Cases**:
- Pattern congestion alerts
- Dashboard traffic display
- Historical trend analysis
- Automation triggers

### 3. Nearest Aircraft Sensor (Per Airfield)

**Entity ID Pattern**: `sensor.{airfield_slug}_nearest_aircraft`  
**Example**: `sensor.popham_nearest_aircraft`

**Purpose**: Identify closest aircraft to airfield.

**State**: Registration or "None" if no aircraft within radius

**Attributes**:
```python
{
    "registration": "G-EFGH",
    "icao24": "4CA2F8",
    "distance_nm": 1.2,
    "bearing_deg": 270,
    "altitude_ft": 800,
    "ground_speed_kts": 65,
    "track_deg": 090,
    "vertical_rate_fpm": -400,
    "aircraft_type": "PA28",
    "aircraft_description": "Piper PA-28 Cherokee",
    "likely_landing": True,  # Calculated based on descent rate + track alignment
    "time_to_airfield_minutes": 2.3,
    "last_seen": "2026-01-22T14:32:15Z"
}
```

### 4. Aircraft In Pattern Binary Sensor (Per Aircraft/Airfield)

**Entity ID Pattern**: `binary_sensor.{aircraft_slug}_in_pattern_{airfield_slug}`  
**Example**: `binary_sensor.g_abcd_in_pattern_popham`

**Purpose**: Detect if aircraft is circling airfield (pattern work).

**State**: `on` (in pattern), `off` (not in pattern)

**Device Class**: `motion`

**Attributes**:
```python
{
    "pattern_detected": True,
    "circuit_direction": "left",  # "left" or "right" hand
    "legs_completed": 2.5,  # Number of circuit legs flown
    "average_altitude_ft": 1000,
    "pattern_entry_time": "2026-01-22T14:15:00Z",
    "time_in_pattern_minutes": 17.2,
    "circuits_count": 2,  # Full circuits completed
    "last_downwind_time": "2026-01-22T14:30:12Z",
    "estimated_landing_time": "2026-01-22T14:35:00Z"
}
```

**Detection Logic**:
- Aircraft within 3nm of airfield
- Altitude < 2000ft AGL
- Circular/rectangular track pattern
- Track changes indicating legs (crosswind, downwind, base, final)
- Repeated pattern behavior

---

## Dashboard Integration

### Map Card Overlay

**RADAR-Style Traffic Display**:
```yaml
type: map
title: Popham Traffic
entities:
  # All aircraft device trackers within radius
  - device_tracker.g_abcd_aircraft
  - device_tracker.g_efgh_aircraft
  - device_tracker.g_ijkl_aircraft
  # Airfield location marker
  - zone.popham_airfield
dark_mode: true
hours_to_show: 0.5  # Last 30 minutes track history
aspect_ratio: "1:1"
```

**Traffic Dashboard Card**:
```yaml
type: vertical-stack
cards:
  - type: glance
    title: Popham Traffic
    entities:
      - entity: sensor.popham_aircraft_traffic_count
        name: Aircraft Nearby
      - entity: sensor.popham_nearest_aircraft
        name: Nearest Aircraft
      - entity: binary_sensor.g_abcd_in_pattern_popham
        name: G-ABCD in Pattern
  
  - type: custom:apexcharts-card
    title: Traffic Altitude Distribution
    series:
      - entity: sensor.popham_aircraft_traffic_count
        attribute: aircraft_by_altitude
        type: column
        
  - type: entities
    title: Aircraft Details
    entities:
      - sensor.popham_nearest_aircraft
```

### Glass Cockpit Integration

Add new section to existing `glass_cockpit.yaml` template:

```yaml
# Traffic Awareness Section (ADS-B)
- type: conditional
  conditions:
    - entity: sensor.{airfield}_aircraft_traffic_count
      state_not: "0"
  card:
    type: vertical-stack
    cards:
      - type: custom:mushroom-title-card
        title: "⚠️ Traffic Alert"
        subtitle: "{{states('sensor.popham_aircraft_traffic_count')}} aircraft nearby"
        
      - type: map
        entities:
          # Dynamically populated device trackers
        aspect_ratio: "16:9"
        hours_to_show: 0.25  # 15 minutes track
```

---

## Privacy & Security Considerations

### Data Handling

**Public ADS-B Data**:
- All ADS-B data is **public information** broadcast in the clear
- No privacy expectations for aircraft with transponders enabled
- Comply with GDPR for any stored personal data (pilot names, etc.)

**User Consent**:
- **Opt-in for individual aircraft tracking**: Users must explicitly enable tracking for their aircraft
- **Clear data usage disclosure**: Explain what data is collected and how it's used
- **Data retention policy**: Default 7-day retention for historical tracks, user configurable

**Security Best Practices**:
- **API keys stored securely**: Use Home Assistant secrets/password fields
- **Rate limit all data sources**: Prevent abuse/excessive costs
- **Sanitize all inputs**: Protect against injection attacks in registration/ICAO24 searches
- **No sensitive info in logs**: Sanitize logs of API keys, user locations

### Flight School/Club Considerations

**Multi-User Environments**:
- **Permission-based access**: Only show aircraft user has permission to track
- **Audit logging**: Log who accessed which aircraft data (optional, configurable)
- **Anonymization option**: Strip pilot names from public displays

**Insurance/Legal Compliance**:
- **Data export**: Allow export of flight logs for insurance claims
- **Accuracy disclaimer**: Clearly state ADS-B data is provided "as-is"
- **No liability**: Integration for awareness only, not primary navigation

---

## Configuration Flow

### Setup Wizard Integration

Add ADS-B configuration to existing setup wizard (Phase 7):

**Step: "ADS-B Aircraft Tracking" (Optional)**

1. **Introduction**:
   ```
   Enable real-time aircraft tracking with ADS-B data.
   
   Benefits:
   • See nearby traffic on a map
   • Track your aircraft when others fly it
   • Pattern congestion alerts
   
   Data sources available:
   • Local receiver (dump1090) - FREE, requires hardware
   • OpenSky Network - FREE, limited rate
   • FlightRadar24 - Paid subscription required
   • FlightAware - Paid subscription required
   ```

2. **Data Source Selection**:
   ```
   Select ADS-B data source:
   
   ○ Local dump1090 receiver (recommended for pilots with hardware)
   ○ OpenSky Network (free, best for testing)
   ○ FlightRadar24 API (paid, best coverage)
   ○ FlightAware AeroAPI (paid, good USA coverage)
   ○ Skip ADS-B setup (can enable later)
   ```

3. **Source-Specific Configuration**:

   **If dump1090**:
   - dump1090 Host: `192.168.1.100`
   - Port: `8080` (default)
   - Test Connection: [button]

   **If OpenSky**:
   - Use anonymous (free): ☑
   - Username: (optional, for premium)
   - Password: (optional, for premium)
   - Test Connection: [button]

   **If FlightRadar24/FlightAware**:
   - API Key: [password field]
   - Subscription Tier: [dropdown]
   - Test Connection: [button]

4. **Airfield Traffic Configuration**:
   ```
   Enable traffic monitoring for airfields?
   ☑ Show aircraft near airfields on map
   
   Monitoring radius: [slider: 5-50nm, default: 10nm]
   Update interval: [dropdown: 5s, 10s, 30s, 60s]
   
   Traffic alerts:
   ☑ Notify when traffic exceeds threshold
   Alert threshold: [number: 5 aircraft]
   ```

5. **Individual Aircraft Tracking**:
   ```
   Track specific aircraft?
   
   Add aircraft to track:
   Registration/Tail: G-ABCD
   ICAO 24-bit (optional): 4CA1E3
   Nickname: "My Cessna"
   
   [+ Add Another Aircraft]
   
   Note: Only aircraft configured here will appear as device trackers.
   You can add more later in Settings.
   ```

6. **Privacy Settings**:
   ```
   Privacy & Data Retention
   
   Historical track retention: [dropdown: 1, 3, 7, 14, 30 days]
   
   ☐ Export flight logs for insurance
   ☐ Share anonymized data with community (OpenSky contributors)
   ```

### Options Flow (Reconfiguration)

**Menu: "ADS-B Settings"**
- **Data Sources**: Add/remove/configure data sources
- **Tracked Aircraft**: Add/remove aircraft, update ICAO24 codes
- **Airfield Traffic**: Adjust monitoring radius, thresholds
- **Advanced**: Cache settings, rate limits, diagnostics

---

## Implementation Phases

### Phase 1: Core Architecture + Free Data Sources (v2601.5.0)
**Duration**: 3-4 weeks  
**Focus**: Foundation with dump1090, OpenSky, and OGN support

**Deliverables**:
- [ ] `ADSBClientBase` abstract class with deduplication logic
- [ ] `AircraftData` dataclass model (ADS-B + FLARM fields)
- [ ] `Dump1090Client` implementation (local receiver, priority 1)
- [ ] `OpenSkyClient` implementation (free API, priority 2, default enabled)
- [ ] `OGNClient` implementation (APRS feed, priority 3, default enabled)
- [ ] Data source prioritization and deduplication system
- [ ] Configuration flow (ADS-B setup wizard step)
- [ ] Basic device tracker entity (per aircraft)
- [ ] Rate limit tracking (OpenSky credits, OGN connection health)
- [ ] Integration with existing dashboard templates
- [ ] Unit tests for client base, Dump1090, OpenSky, OGN
- [ ] Documentation: feature guide, setup instructions, FLARM explanation

**Success Criteria**:
- Users with dump1090 can see their aircraft on HA map
- Users without hardware can use OpenSky/OGN (free, enabled by default)
- Deduplication prevents duplicate aircraft markers
- OpenSky rate limits respected (no ban, credit tracking works)
- OGN APRS connection stable and reconnects automatically
- Gliders visible via OpenSky and OGN (FLARM data)
- Configuration flow guides user through setup
- All tests pass with >80% coverage
- Documentation explains ADS-B vs FLARM clearly

### Phase 2: Airfield Traffic Sensors (v2601.6.0)
**Duration**: 2 weeks  
**Focus**: Traffic awareness for airfields (moved from Phase 3)

**Deliverables**:
- [ ] Traffic count sensor (per airfield)
- [ ] Nearest aircraft sensor (per airfield)
- [ ] Traffic altitude/direction breakdowns
- [ ] Pattern detection algorithm (in-pattern binary sensor)
- [ ] Dashboard card templates for traffic display
- [ ] Map overlay integration
- [ ] Automation examples (traffic alerts)
- [ ] Unit tests for traffic sensors
- [ ] Documentation: traffic monitoring guide

**Success Criteria**:
- Airfields show accurate traffic counts (ADS-B + FLARM)
- Pattern detection works for circuit traffic
- Dashboard displays traffic clearly
- Automation examples functional

### Phase 3: Additional API Support (v2602.1.0)
**Duration**: 2-3 weeks  
**Focus**: ADS-B Exchange, FlightRadar24, and FlightAware integration

**Deliverables**:
- [ ] `ADSBExchangeClient` implementation (RapidAPI)
- [ ] `FlightRadar24Client` implementation
- [ ] `FlightAwareClient` implementation
- [ ] Multi-tier subscription handling (free/paid)
- [ ] API usage tracking and quota warnings
- [ ] Enhanced aircraft metadata (types, photos, flight plans)
- [ ] Config flow for API credentials
- [ ] Cost estimation tools (API call projections)
- [ ] RapidAPI integration (ADS-B Exchange specific)
- [ ] Unit tests for all API clients
- [ ] Documentation: API setup guides, cost analysis, comparison matrix

**Success Criteria**:
- All three APIs integrated and functional
- API quotas respected, usage tracked (including RapidAPI limits)
- Users can compare API costs vs. dump1090
- Clear value proposition for each tier (free, $5, $20, $50+)
- ADS-B Exchange free tier usable for hobbyists (500 req/day)

### Phase 4: Advanced Features (v2602.2.0)
**Duration**: 3-4 weeks  
**Focus**: Enhanced tracking and analysis

**Deliverables**:
- [ ] Historical track logging (persistent storage)
- [ ] Flight log export (CSV, GPX formats)
- [ ] Pattern analytics (circuit count, leg timing)
- [ ] Flight time tracking (Hobbs alternative)
- [ ] Maintenance hour tracking integration
- [ ] Multi-source fallback (primary + backup sources)
- [ ] Fleet management dashboard (flight schools)
- [ ] AI briefing integration (mention nearby traffic)
- [ ] Advanced automation examples
- [ ] Comprehensive documentation

**Success Criteria**:
- Historical data persists across restarts
- Flight logs exportable for insurance
- Multi-source failover works seamlessly
- Fleet dashboard functional for clubs

---

## Testing Strategy

### Unit Tests

**test_adsb_client_base.py**:
- Test abstract base class interface
- Test common utility functions (distance, bearing calculations)
- Test cache management (memory + persistent)
- Test error handling patterns

**test_dump1090_client.py**:
- Test JSON parsing from dump1090 format
- Test connection handling (success, timeout, invalid host)
- Test aircraft data extraction
- Test bounding box filtering

**test_opensky_client.py**:
- Test API response parsing
- Test rate limit handling (backoff, retry)
- Test authentication (anonymous vs. premium)
- Test cache behavior (free tier aggressive caching)

**test_flightradar24_client.py**:
- Test API authentication
- Test real-time position updates
- Test aircraft search by registration/ICAO24
- Test quota tracking and warnings

**test_flightaware_client.py**:
- Test AeroAPI v4 endpoints
- Test pagination handling
- Test flight plan data extraction
- Test error handling (API downtime, invalid keys)

**test_aircraft_tracker.py**:
- Test device tracker entity creation
- Test state updates (home, away, airborne)
- Test attribute population
- Test device info linking

**test_traffic_sensor.py**:
- Test traffic count calculations
- Test altitude band categorization
- Test direction analysis (inbound/outbound)
- Test nearest aircraft detection

**test_pattern_detection.py**:
- Test circuit pattern recognition
- Test leg identification (crosswind, downwind, base, final)
- Test circuit counting
- Test false positive prevention

**Integration Tests**:
- Test multi-source failover
- Test complete setup flow (wizard → entities created)
- Test dashboard card rendering
- Test automation triggers

### Manual Testing Scenarios

**Scenario 1: First-Time Setup (No Hardware)**:
1. Install integration
2. Run setup wizard
3. Select OpenSky (free)
4. Configure tracking for one aircraft
5. Verify aircraft appears on map
6. Check rate limit handling after 10 minutes

**Scenario 2: Local Receiver Setup**:
1. Configure dump1090 on Raspberry Pi
2. Add integration, select dump1090
3. Enter local IP address
4. Test connection
5. Verify real-time updates (< 5 second latency)
6. Check cache behavior after disconnect

**Scenario 3: Airfield Traffic Monitoring**:
1. Enable traffic sensors for airfield
2. Adjust monitoring radius to 10nm
3. Wait for aircraft to enter radius
4. Verify traffic count increases
5. Check nearest aircraft sensor updates
6. Test pattern detection (simulated circuit)

**Scenario 4: Multi-Source Failover**:
1. Configure dump1090 as primary
2. Configure OpenSky as backup
3. Disconnect dump1090
4. Verify failover to OpenSky
5. Reconnect dump1090
6. Verify return to primary source

---

## Frequently Asked Questions (FAQ)

### What's the difference between ADS-B and FLARM?

**ADS-B (Automatic Dependent Surveillance-Broadcast)**:
- **Used by**: Commercial aircraft, most powered aircraft (mandatory in controlled airspace)
- **Broadcast**: Position, altitude, speed, callsign, aircraft type
- **Range**: 150+ nm (line-of-sight)
- **Frequency**: 1090 MHz (Mode S) or 978 MHz (UAT in USA)
- **Cost**: ADS-B transponders £1500-5000

**FLARM (Flight Alarm)**:
- **Used by**: Gliders, motor gliders, some light aircraft (voluntary)
- **Broadcast**: Position, altitude, speed, climb rate, turn rate (collision avoidance focus)
- **Range**: 5-10 km (shorter range, power-efficient)
- **Frequency**: 868 MHz (Europe) or 915 MHz (USA/Australia)
- **Cost**: FLARM units £500-1500 (cheaper than ADS-B)
- **Privacy**: Many glider pilots prefer FLARM over ADS-B (less public tracking)

**Why Both Matter**:
- **Airfield traffic monitoring**: See both ADS-B-equipped powered aircraft AND FLARM-equipped gliders
- **Gliding sites**: Most traffic is FLARM-only (gliders don't have ADS-B)
- **Collision avoidance**: FLARM provides turn rate data (useful for pattern detection)

**Data Sources**:
- **dump1090**: ADS-B only (1090 MHz receivers)
- **OpenSky Network**: ADS-B + FLARM (network aggregates both)
- **Open Gliding Network**: FLARM only (glider-focused)
- **ADS-B Exchange**: ADS-B only (no FLARM)
- **FR24/FlightAware**: Primarily ADS-B (limited FLARM coverage)

### Do I need hardware to use ADS-B tracking?

**No!** Phase 1 includes free API options that work without hardware:
- **OpenSky Network**: Enabled by default, 400 requests/day anonymous (4000 with free account)
- **Open Gliding Network**: Enabled by default, unlimited (community-operated)

You can track aircraft immediately after installation with zero cost.

**However**, local hardware (dump1090) is recommended if you want:
- Real-time updates (1-2 second latency vs. 10-30 seconds via API)
- Offline operation (no internet required)
- Best coverage in your local area (150+ nm radius)
- No rate limits

Hardware investment: ~£100 for RTL-SDR receiver + antenna.

### Will I see duplicate aircraft if I enable multiple sources?

**No.** Hangar Assistant includes intelligent deduplication:
- Aircraft identified by ICAO24 hex code (unique identifier)
- Priority system: dump1090 (local) > OpenSky > OGN > FR24 > FlightAware
- Higher-priority source data always used for position/speed
- Lower-priority sources fill in missing metadata (aircraft type, registration)

You can disable deduplication in settings if you want to see all sources separately (useful for debugging).

### Why is OpenSky/OGN enabled by default?

**Free and Safe**:
- Both are 100% free (no credit card, no API key required)
- No cost risk (won't accidentally charge you)
- Rate limits tracked automatically (won't get you banned)
- Graceful degradation (uses cached data if rate limited)

**Immediate Value**:
- Users can track aircraft right after installation
- No hardware setup required
- Global coverage (not just your local area)

**Easy to Disable**: Can be turned off in settings if not wanted.

### How do I increase OpenSky rate limits?

**Create a free OpenSky Network account**:
1. Go to https://opensky-network.org/register
2. Sign up (no credit card required)
3. Verify email
4. Add username/password to Hangar Assistant settings
5. Rate limit increases from 400 → 4000 credits/day (10x increase)

No cost, takes 2 minutes. Highly recommended if using OpenSky as primary source.

### Should I use OpenSky or ADS-B Exchange?

**Both are good options.** Choose based on your needs:

**Use OpenSky Network if**:
- You want 100% free tracking (4000 requests/day with free account)
- You need FLARM data (glider tracking)
- You prefer simpler setup (no RapidAPI account)
- You're a hobbyist with light usage

**Use ADS-B Exchange if**:
- You need more than 4000 requests/day
- You want richer aircraft metadata (better descriptions, photos)
- Better coverage in your region (varies by location)
- Willing to pay $5-50/month for higher limits
- Commercial use (paid tier recommended)

**Cost Comparison**:
- OpenSky free account: 4000 req/day = track ~8 aircraft continuously (one update every 10s each)
- ADS-B Exchange free: 500 req/day = track 1 aircraft (one update every 3 minutes)
- ADS-B Exchange Basic ($5/mo): 10,000 req/day = track ~20 aircraft continuously

**Coverage Comparison**:
- Varies by region (both have large receiver networks)
- Generally similar coverage worldwide
- Some areas have better ADS-B Exchange coverage, others better OpenSky

**Recommendation**: Start with OpenSky (free account, very generous limits). Add ADS-B Exchange later if you need more capacity or better metadata.

### Can I track gliders with this integration?

**Yes!** Glider tracking is fully supported:
- **Open Gliding Network (OGN)**: FLARM-equipped gliders (enabled by default)
- **OpenSky Network**: Some FLARM data aggregated from network receivers
- **dump1090**: Only if glider has ADS-B transponder (rare)

**Best for Glider Sites**:
- Enable OGN (default) for all FLARM-equipped gliders in your area
- OGN provides excellent coverage at popular soaring sites in Europe
- Includes glider type database (know if it's a Discus, ASW20, etc.)

**Note**: Not all gliders have FLARM. Some older gliders or private owners may not broadcast position.

## Future Enhancements

### Phase 5+: Advanced Features

**1. Predictive Analytics**:
- Predict landing time based on current track/descent rate
- Estimate pattern entry/exit times
- Forecast traffic density (time-of-day patterns)

**2. Weather Integration**:
- Cross-reference traffic with weather conditions
- Alert if aircraft near thunderstorms (via OWM alerts)
- Show wind arrows on traffic map

**3. AI Briefing Enhancement**:
- Include nearby traffic in briefings
- Mention pattern congestion
- Suggest optimal departure times to avoid traffic

**4. Community Features**:
- Share aircraft tracking with club members (permission-based)
- Community airfield traffic dashboards
- Aggregate statistics (busiest times, popular routes)

**5. Mobile App Integration**:
- Home Assistant mobile app notifications for traffic alerts
- Push notifications when your aircraft moves
- Geofencing (alert if aircraft leaves permitted area)

**6. Advanced Sensors**:
- `sensor.{aircraft}_total_flight_hours_today`
- `sensor.{aircraft}_last_flight_duration`
- `sensor.{aircraft}_average_ground_speed`
- `sensor.{airfield}_peak_traffic_time`
- `binary_sensor.{aircraft}_theft_alert` (unexpected movement)

**7. Export/Reporting**:
- PDF flight logs (insurance compliance)
- CSV export for maintenance tracking
- GPX export for track visualization in ForeFlight/SkyDemon
- Integration with pilot logbook apps

**8. Additional Data Sources**:
- ADS-B Exchange API
- Local Mode-S/ADS-B databases (aircraft type lookup)
- FAA/CAA registration databases (ownership lookup)

---

## Cost Analysis

### Hardware Costs (One-Time)

**Local ADS-B Receiver** (dump1090):
- RTL-SDR dongle: £25-35
- ADS-B antenna: £20-80 (depends on quality)
- Raspberry Pi 4 (optional, can run on existing system): £40-60
- **Total**: ~£85-175 one-time

**Alternative**: FlightAware Pro Stick Plus: £55 (includes filtered SDR + antenna)

### API Subscription Costs (Monthly/Annual)

**OpenSky Network**:
- Anonymous (free): £0/month, 400 requests/day
- Free Account: £0/month, 4000 requests/day (10x increase)
- Premium: £10/month, faster updates, more requests

**ADS-B Exchange**:
- Free: £0/month, 500 requests/day
- Basic: £5/month, 10,000 requests/day
- Pro: £20/month, 100,000 requests/day
- Ultra: £50/month, 1,000,000 requests/day

**FlightRadar24**:
- Business: ~£500/month minimum (varies by usage)
- Enterprise: £1000+/month (unlimited)

**FlightAware AeroAPI**:
- Starter: £80/month (500 requests/hour)
- Standard: £250/month (2000 requests/hour)
- Enterprise: £500/month (custom limits)

### Cost Comparison for Typical User

**Hobbyist Pilot (Single Aircraft)**:
- **Recommended**: OpenSky Network (free account)
- **Cost**: £0/month (4000 requests/day = track 1 aircraft every 5-10 seconds all day)
- **Coverage**: Global
- **Alternative**: Local dump1090 receiver (~£100 one-time) for real-time local tracking

**Active Pilot (Multiple Aircraft, Frequent Tracking)**:
- **Recommended**: ADS-B Exchange Basic
- **Cost**: £5/month (10,000 requests/day)
- **Coverage**: Global, better than OpenSky in many regions
- **Alternative**: OpenSky Premium (£10/month) for FLARM support

**Flight School (10 Aircraft, Busy Airfield)**:
- **Recommended**: Local dump1090 + ADS-B Exchange Pro
- **Cost**: ~£150 hardware one-time + £20/month API
- **Coverage**: Local excellent (dump1090), global backup (API)
- **Alternative**: dump1090 + OpenSky free account (£0 ongoing)

**Commercial Operation (Fleet Tracking, Multiple Sites)**:
- **Recommended**: FlightAware Standard API
- **Cost**: £250/month
- **Coverage**: Global, high reliability, flight plan data
- **Budget Alternative**: ADS-B Exchange Ultra (£50/month, 1M requests/day)

---

## Migration & Backward Compatibility

### Existing Installations

**CRITICAL**: ADS-B tracking is a **new feature**, not a replacement.

**Compatibility Guarantees**:
- ✅ Existing sensors/entities unaffected
- ✅ No breaking changes to existing config
- ✅ Opt-in only (disabled by default)
- ✅ Can be added/removed without affecting other features

**Configuration Structure**:
```python
entry.data["integrations"]["adsb"] = {
    "enabled": False,  # ADS-B tracking disabled by default (opt-in feature)
    "deduplication": True,  # Enable data source deduplication (recommended)
    "sources": {
        "dump1090": {
            "enabled": False,  # Requires hardware, user must configure
            "priority": 1,     # Highest priority (local, most accurate)
            "host": "",
            "port": 8080,
            # ...
        },
        "opensky": {
            "enabled": True,   # ✅ Enabled by default (free, no key)
            "priority": 2,     # Second priority (after local)
            "username": None,  # Optional for higher rate limits
            "password": None,
            "daily_credit_limit": 400,
            "credits_used_today": 0,
            "credits_reset_time": "00:00 UTC",
            # ...
        },
        "ogn": {
            "enabled": True,   # ✅ Enabled by default (free, no key)
            "priority": 3,     # Third priority (glider-focused)
            "aprs_server": "aprs.glidernet.org",
            "aprs_port": 14580,
            # ...
        },
        "adsbexchange": {
            "enabled": False,  # Requires RapidAPI key
            "priority": 4,     # Fourth priority
            "api_key": "",     # RapidAPI key
            "subscription_tier": "free",
            "requests_today": 0,
            "daily_limit": 500,
            # ...
        },
        "flightradar24": {
            "enabled": False,  # Paid API, disabled by default
            "priority": 5,
            # ...
        },
        "flightaware": {
            "enabled": False,  # Paid API, disabled by default
            "priority": 6,
            # ...
        }
    },
    "tracked_aircraft": [],  # List of aircraft configs
    "airfield_traffic": {
        "enabled": True,  # Enable traffic sensors for airfields
        "radius_nm": 10,
        "update_interval": 30,  # seconds
        "include_flarm": True,  # Include FLARM-equipped aircraft (gliders)
        "min_altitude_ft": 0,   # Minimum altitude to display (filter ground vehicles)
        "max_altitude_ft": 10000  # Maximum altitude (filter high-altitude traffic)
    }
}
```

---

## Documentation Requirements

### User-Facing Documentation

**docs/features/adsb_tracking.md**:
- Overview and benefits
- Comparison of data sources (dump1090, OpenSky, FR24, FlightAware)
- Step-by-step setup guide
- Dashboard integration examples
- Troubleshooting guide
- FAQ

**docs/features/adsb_hardware_setup.md**:
- dump1090 installation guide (Raspberry Pi)
- Antenna placement recommendations
- Network configuration
- Performance tuning

**docs/features/adsb_api_comparison.md**:
- Detailed cost comparison
- Coverage maps
- Feature matrix
- Recommendations by use case

### Developer Documentation

**docs/development/adsb_architecture.md**:
- Technical architecture overview
- Client abstraction layer design
- Data flow diagrams
- Extension points for new sources

**API reference** (inline docstrings):
- All client classes fully documented
- Data models explained
- Example usage for each client

### Translation Keys

Add to `strings.json` and all language packs:
```json
{
  "config": {
    "step": {
      "adsb_setup": {
        "title": "ADS-B Aircraft Tracking",
        "description": "Enable real-time aircraft tracking...",
        "data": {
          "enabled": "Enable ADS-B Tracking",
          "source": "Data Source",
          "monitoring_radius": "Monitoring Radius (nm)"
        }
      },
      "adsb_dump1090": {
        "title": "dump1090 Configuration",
        "description": "Configure local ADS-B receiver...",
        "data": {
          "host": "dump1090 Host",
          "port": "Port",
          "endpoint": "JSON Endpoint"
        }
      }
      // ... more steps
    }
  },
  "entity": {
    "device_tracker": {
      "aircraft": {
        "name": "{registration} Aircraft",
        "state": {
          "home": "At Home Base",
          "away": "Away",
          "airborne": "Airborne",
          "unknown": "Unknown"
        }
      }
    },
    "sensor": {
      "aircraft_traffic_count": {
        "name": "Aircraft Traffic",
        "state": { "description": "Number of aircraft within monitoring radius" }
      },
      "nearest_aircraft": {
        "name": "Nearest Aircraft",
        "state": { "description": "Closest aircraft to airfield" }
      }
    },
    "binary_sensor": {
      "aircraft_in_pattern": {
        "name": "{registration} in Pattern",
        "state": {
          "on": "Aircraft flying pattern",
          "off": "Not in pattern"
        }
      }
    }
  }
}
```

---

## Success Metrics

### Phase 1 (dump1090 Support)
- [ ] 80%+ test coverage
- [ ] 10+ beta testers successfully configured
- [ ] Average setup time < 15 minutes (for users with dump1090)
- [ ] Zero critical bugs in first 2 weeks
- [ ] Documentation completeness score: 90%+

### Phase 2 (OpenSky Integration)
- [ ] Free tier users stay under rate limits
- [ ] 90%+ uptime for OpenSky API calls
- [ ] Graceful degradation tested and working
- [ ] 5+ users successfully using OpenSky as primary source

### Phase 3 (Traffic Sensors)
- [ ] Pattern detection accuracy: 95%+ (vs. manual verification)
- [ ] Traffic count accuracy: ±1 aircraft
- [ ] False positive rate < 5% (pattern detection)
- [ ] Dashboard cards render correctly on mobile

### Phase 4 (Paid APIs)
- [ ] Both APIs integrated and tested
- [ ] Quota tracking accurate (±1%)
- [ ] Cost estimation within 10% of actual
- [ ] 3+ users successfully using paid APIs

### Long-Term Success
- [ ] 100+ active installations within 6 months
- [ ] 80%+ user satisfaction (survey)
- [ ] Feature requests prioritized and tracked
- [ ] Community contributions (bug reports, PRs)

---

## Risk Assessment

### Technical Risks

**Risk**: API rate limits exceeded, users blocked  
**Mitigation**: Aggressive caching, quota tracking, auto-disable on repeated failures

**Risk**: dump1090 JSON format changes break integration  
**Mitigation**: Version detection, graceful handling of unknown fields, unit tests with multiple format versions

**Risk**: Pattern detection false positives (alerts when aircraft not in pattern)  
**Mitigation**: Tune detection algorithm, require multiple confirming behaviors, user-adjustable sensitivity

**Risk**: Device tracker entities flood HA map with too many markers  
**Mitigation**: User-configurable monitoring radius, filter by altitude/type, hide non-tracked aircraft

### User Experience Risks

**Risk**: Setup too complex for non-technical users  
**Mitigation**: Guided wizard, test connection buttons, clear error messages, video tutorials

**Risk**: Expensive API subscriptions prevent adoption  
**Mitigation**: Promote free options (dump1090, OpenSky), provide clear cost analysis, recommend hardware investment

**Risk**: Users expect real-time but get delayed data (API lag)  
**Mitigation**: Set clear expectations in docs, show data age in UI, explain limitations of each source

### Privacy/Legal Risks

**Risk**: GDPR compliance concerns with storing aircraft positions  
**Mitigation**: Clear data retention policies, user consent, anonymization options, data export

**Risk**: Users track aircraft without owner permission  
**Mitigation**: Disclaimer that ADS-B is public data, recommend permission for private aircraft

**Risk**: Insurance disputes over flight log accuracy  
**Mitigation**: Clear disclaimer that data is "as-is", not certified for legal/insurance use

---

## Community Feedback Integration

### Beta Testing Plan

**Phase 1 Beta** (dump1090 support):
- Recruit 10-15 users with existing dump1090 setups
- Test on Raspberry Pi, x86 Linux, Docker environments
- Focus: Setup ease, reliability, performance

**Phase 2 Beta** (OpenSky):
- Recruit 20+ users without dump1090 hardware
- Mix of free and premium tier users
- Focus: Rate limit handling, cache behavior, API reliability

**Phase 3 Beta** (Traffic sensors):
- Recruit flight schools with busy airfields
- Test pattern detection accuracy with real circuit traffic
- Focus: False positives, dashboard usability, automation examples

**Feedback Collection**:
- GitHub issues (bug reports, feature requests)
- Community forum discussions
- Anonymous usage surveys
- Analytics (if user opts in)

---

## Conclusion

ADS-B aircraft tracking adds significant value to Hangar Assistant by providing real-time situational awareness for pilots and airfield operators. The multi-source abstraction layer ensures flexibility (free options for hobbyists, paid options for professionals) while maintaining consistent UX.

**Key Success Factors**:
1. **Accessible**: Free options (dump1090, OpenSky) ensure broad adoption
2. **Flexible**: Multiple data sources prevent vendor lock-in
3. **Privacy-conscious**: Clear data policies, user consent, opt-in only
4. **Well-documented**: Step-by-step guides for all skill levels
5. **Reliable**: Graceful degradation, caching, error handling

**Next Steps**:
1. Review plan with stakeholders/community
2. Validate technical approach with Home Assistant core team
3. Create detailed task breakdown for Phase 1
4. Set up development environment (dump1090 test instance)
5. Begin implementation: `ADSBClientBase` and `Dump1090Client`

---

**Document Version**: 1.0  
**Last Updated**: 22 January 2026  
**Status**: Awaiting review and approval for Phase 1 implementation
