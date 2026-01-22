"""OpenSky Network client for free community ADS-B data.

This module provides a client for the OpenSky Network REST API, enabling
access to global ADS-B and FLARM data with free and premium tiers.

OpenSky Network is a community-based receiver network with free access.
Free tier: 400 API credits/day anonymous, 4000 with free account.
Premium tier: $10/month for higher limits.

Architecture:
    - Connects to OpenSky Network REST API via HTTPS
    - Parses JSON state vector array into AircraftData objects
    - Priority 2 data source (free API, enabled by default)
    - Rate limit tracking and credit management
    - Supports both ADS-B and FLARM aircraft

Data Source Priority: 2 (free API, enabled by default)

API Response Format (OpenSky /states/all):
    {
        "time": 1737560000,
        "states": [
            [
                "4ca1e3",           # [0] ICAO24 (hex, lowercase)
                "GABCD   ",         # [1] Callsign (8 chars, space-padded)
                "United Kingdom",   # [2] Origin country
                1737560000,         # [3] Time position (Unix timestamp)
                1737560000,         # [4] Last contact (Unix timestamp)
                -0.4614,            # [5] Longitude
                51.4775,            # [6] Latitude
                762.0,              # [7] Barometric altitude (meters)
                False,              # [8] On ground
                49.0,               # [9] Velocity (m/s)
                180.0,              # [10] True track (degrees)
                0.0,                # [11] Vertical rate (m/s)
                None,               # [12] Sensors (array of ints)
                762.0,              # [13] Geometric altitude (meters)
                "4567",             # [14] Squawk code
                False,              # [15] Special position indicator
                0                   # [16] Position source (0=ADS-B, 1=ASTERIX, 2=MLAT, 3=FLARM)
            ]
        ]
    }

Rate Limits:
    - Anonymous: 400 credits/day (resets 00:00 UTC)
    - Free Account: 4000 credits/day (10x increase, no credit card)
    - Premium: ~unlimited for reasonable use ($10/month)
    - Bounding box query: 1 credit per call
    - Track single aircraft: 1 credit per call

Used By:
    - ADSBManager (multi-source manager)
    - Device tracker entities
    - Traffic sensors

Configuration:
    The OpenSky Network credentials are stored in global settings:
    - CONF_OPENSKY_ENABLED: Enable/disable OpenSky data source
    - CONF_OPENSKY_USERNAME: Optional username for free account (4000 credits/day)
    - CONF_OPENSKY_PASSWORD: Optional password for free account
    - Default: Enabled, anonymous (400 credits/day)

Example:
    >>> # Anonymous (400 credits/day)
    >>> config = {"username": None, "password": None}
    >>> client = OpenSkyClient(hass, config)
    >>> 
    >>> # With free account (4000 credits/day)
    >>> config = {"username": "user@example.com", "password": "pass"}
    >>> client = OpenSkyClient(hass, config)
    >>> 
    >>> # Usage
    >>> success, error = await client.test_connection()
    >>> if success:
    ...     aircraft = await client.get_aircraft_near_location(51.4775, -0.4614, 25)
    ...     print(f"Credits used today: {client.get_credit_usage()}")
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..const import (
    ADSB_PRIORITY_OPENSKY,
    DEFAULT_OPENSKY_ANONYMOUS_CREDITS_PER_DAY,
    DEFAULT_OPENSKY_AUTH_CREDITS_PER_DAY,
)
from .adsb_client_base import ADSBClientBase
from .adsb_models import AircraftData

_LOGGER = logging.getLogger(__name__)

# OpenSky Network API endpoints
OPENSKY_API_BASE_URL = "https://opensky-network.org/api"
OPENSKY_STATES_ENDPOINT = "/states/all"
OPENSKY_TIMEOUT_SECONDS = 10  # OpenSky can be slow


class OpenSkyClient(ADSBClientBase):
    """Client for OpenSky Network free community ADS-B data.
    
    Connects to OpenSky Network REST API for global aircraft tracking.
    
    Inputs:
        hass: Home Assistant instance
        config: Configuration dict with optional 'username' and 'password'
    
    Outputs:
        - AircraftData objects from OpenSky Network
        - Priority 2 for deduplication
        - Rate limit tracking and credit management
    
    Configuration:
        username: Optional OpenSky account email (default: None = anonymous)
        password: Optional OpenSky account password (default: None)
        cache_ttl: Cache duration in seconds (default: 60s anonymous, 30s with account)
    
    Rate Limits:
        Anonymous: 400 credits/day (1 credit per bbox query)
        Free Account: 4000 credits/day (10x increase, free signup)
        Premium: ~unlimited ($10/month)
    
    Example:
        >>> client = OpenSkyClient(hass, {"username": "user@example.com", "password": "pass"})
        >>> aircraft_list = await client.get_aircraft_near_location(51.5, -0.5, 25)
        >>> print(f"Credits used: {client.get_credit_usage()}")
    """
    
    def __init__(self, hass: HomeAssistant, config: Dict):
        """Initialise OpenSky Network client.
        
        Args:
            hass: Home Assistant instance
            config: Configuration dictionary with optional 'username' and 'password'
        """
        # Determine if authenticated (affects cache TTL and rate limits)
        username = config.get("username")
        password = config.get("password")
        self._is_authenticated = bool(username and password)
        
        # Set cache TTL based on authentication (authenticated = faster updates)
        cache_ttl = 30 if self._is_authenticated else 60
        
        super().__init__(
            hass=hass,
            config=config,
            priority=ADSB_PRIORITY_OPENSKY,  # Priority 2 (free API)
            cache_enabled=True,
            cache_ttl=cache_ttl,
            max_cache_entries=1000  # OpenSky can return many aircraft
        )
        
        self._username = username
        self._password = password
        self._timeout = OPENSKY_TIMEOUT_SECONDS
        
        # Rate limit tracking
        self._daily_limit = (
            DEFAULT_OPENSKY_AUTH_CREDITS_PER_DAY if self._is_authenticated
            else DEFAULT_OPENSKY_ANONYMOUS_CREDITS_PER_DAY
        )
        self._credits_used_today = 0
        self._last_reset_date = dt_util.utcnow().date()
        self._rate_limited = False
        self._rate_limit_reset_time = None
        
        # Build authentication
        self._auth = None
        if self._is_authenticated:
            self._auth = aiohttp.BasicAuth(self._username, self._password)
        
        _LOGGER.debug(
            "Initialised OpenSky Network client: %s (priority=%d, limit=%d credits/day)",
            "authenticated" if self._is_authenticated else "anonymous",
            self.priority,
            self._daily_limit
        )
    
    def get_credit_usage(self) -> Dict[str, any]:
        """Get current credit usage statistics.
        
        Returns:
            Dict with 'credits_used', 'daily_limit', 'credits_remaining', 'reset_time'
        """
        self._reset_credits_if_new_day()
        
        return {
            "credits_used": self._credits_used_today,
            "daily_limit": self._daily_limit,
            "credits_remaining": self._daily_limit - self._credits_used_today,
            "reset_time": datetime.combine(
                dt_util.utcnow().date() + timedelta(days=1),
                datetime.min.time(),
                tzinfo=timezone.utc
            ),
            "is_rate_limited": self._rate_limited,
            "is_authenticated": self._is_authenticated
        }
    
    def _reset_credits_if_new_day(self) -> None:
        """Reset credit counter if it's a new UTC day."""
        current_date = dt_util.utcnow().date()
        if current_date > self._last_reset_date:
            _LOGGER.info(
                "OpenSky credit counter reset: %d credits used yesterday",
                self._credits_used_today
            )
            self._credits_used_today = 0
            self._last_reset_date = current_date
            self._rate_limited = False
            self._rate_limit_reset_time = None
    
    def _increment_credits(self, cost: int = 1) -> None:
        """Increment credit usage counter.
        
        Args:
            cost: Number of credits consumed (default: 1)
        """
        self._reset_credits_if_new_day()
        self._credits_used_today += cost
        
        # Warn when approaching limit
        if self._credits_used_today >= self._daily_limit * 0.9:
            _LOGGER.warning(
                "OpenSky approaching daily limit: %d/%d credits used",
                self._credits_used_today,
                self._daily_limit
            )
        elif self._credits_used_today >= self._daily_limit * 0.7:
            _LOGGER.info(
                "OpenSky credit usage: %d/%d credits used",
                self._credits_used_today,
                self._daily_limit
            )
    
    def _check_rate_limit(self) -> bool:
        """Check if currently rate limited.
        
        Returns:
            True if rate limited, False otherwise
        """
        self._reset_credits_if_new_day()
        
        # Check if we've hit the daily limit
        if self._credits_used_today >= self._daily_limit:
            _LOGGER.warning("OpenSky daily credit limit reached (%d/%d)", 
                          self._credits_used_today, self._daily_limit)
            self._rate_limited = True
            return True
        
        # Check if temporarily rate limited (429 response)
        if self._rate_limited and self._rate_limit_reset_time:
            if dt_util.utcnow() < self._rate_limit_reset_time:
                return True
            else:
                # Rate limit expired
                self._rate_limited = False
                self._rate_limit_reset_time = None
        
        return False
    
    async def test_connection(self) -> Tuple[bool, Optional[str]]:
        """Test connection to OpenSky Network API.
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            # Test with a small bounding box around London
            params = {
                "lamin": 51.0,
                "lomin": -1.0,
                "lamax": 52.0,
                "lomax": 0.0
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{OPENSKY_API_BASE_URL}{OPENSKY_STATES_ENDPOINT}",
                    params=params,
                    auth=self._auth,
                    timeout=aiohttp.ClientTimeout(total=self._timeout)
                ) as response:
                    if response.status == 401:
                        return False, "Authentication failed: invalid username or password"
                    
                    if response.status == 429:
                        return False, "Rate limit exceeded: try again later or create free account"
                    
                    if response.status != 200:
                        return False, f"HTTP {response.status}: {response.reason}"
                    
                    try:
                        data = await response.json()
                    except (asyncio.TimeoutError, TimeoutError):
                        return False, f"Connection timeout after {self._timeout}s"
                    
                    # Validate response structure
                    if "time" not in data or "states" not in data:
                        return False, "Invalid OpenSky response: missing required keys"
                    
                    if data["states"] is None:
                        # No aircraft in bbox (valid response, but no data)
                        _LOGGER.info("OpenSky connection successful: no aircraft in test area")
                        return True, None
                    
                    if not isinstance(data["states"], list):
                        return False, "Invalid OpenSky response: 'states' must be array"
                    
                    aircraft_count = len(data["states"])
                    _LOGGER.info(
                        "OpenSky connection successful: %d aircraft visible (%s)",
                        aircraft_count,
                        "authenticated" if self._is_authenticated else "anonymous"
                    )
                    return True, None
        
        except aiohttp.ClientError as e:
            error_msg = f"Connection failed: {str(e)}"
            _LOGGER.warning("OpenSky connection test failed: %s", error_msg)
            return False, error_msg
        
        except (asyncio.TimeoutError, TimeoutError):
            error_msg = f"Connection timeout after {self._timeout}s"
            _LOGGER.warning("OpenSky connection test failed: %s", error_msg)
            return False, error_msg
        
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            _LOGGER.error("OpenSky connection test failed: %s", error_msg)
            return False, error_msg
    
    async def get_aircraft_by_registration(
        self, registration: str
    ) -> List[AircraftData]:
        """Get aircraft data by registration.
        
        Note: OpenSky does not support registration-based queries directly.
        This method fetches all aircraft and filters by registration.
        
        Args:
            registration: Aircraft registration (e.g., "G-ABCD")
        
        Returns:
            Empty list (registration queries not supported by OpenSky)
        """
        # OpenSky doesn't support registration queries
        # Would need to fetch all aircraft globally (too expensive)
        _LOGGER.warning(
            "OpenSky does not support registration-based queries. "
            "Use get_aircraft_near_location() instead."
        )
        return []
    
    async def get_aircraft_by_icao24(self, icao24: str) -> Optional[AircraftData]:
        """Get aircraft data by ICAO24 hex code.
        
        Args:
            icao24: ICAO24 hex code (e.g., "4CA1E3")
        
        Returns:
            AircraftData if found, None otherwise
        """
        # Check cache first
        cache_key = f"icao24:{icao24.upper()}"
        cached = self._get_cached_aircraft(cache_key)
        if cached:
            return cached
        
        # Check rate limit
        if self._check_rate_limit():
            _LOGGER.debug("OpenSky rate limited, using cache only")
            return None
        
        try:
            params = {"icao24": icao24.lower()}  # OpenSky uses lowercase
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{OPENSKY_API_BASE_URL}{OPENSKY_STATES_ENDPOINT}",
                    params=params,
                    auth=self._auth,
                    timeout=aiohttp.ClientTimeout(total=self._timeout)
                ) as response:
                    self._increment_credits(1)  # Track credit usage
                    
                    if response.status == 429:
                        self._handle_rate_limit_response(response)
                        return None
                    
                    if response.status != 200:
                        _LOGGER.warning("OpenSky returned HTTP %d", response.status)
                        return None
                    
                    data = await response.json()
                    
                    if not data.get("states"):
                        return None  # Aircraft not found
                    
                    # Parse first (and only) aircraft
                    state = data["states"][0]
                    aircraft = self._parse_state_vector(state, data["time"])
                    
                    if aircraft:
                        self._cache_aircraft(aircraft)
                    
                    return aircraft
        
        except Exception as e:
            _LOGGER.debug("OpenSky query failed for %s: %s", icao24, str(e))
            return None
    
    async def get_aircraft_near_location(
        self, latitude: float, longitude: float, radius_nm: float = 10
    ) -> List[AircraftData]:
        """Get all aircraft within radius of location.
        
        Args:
            latitude: Centre latitude
            longitude: Centre longitude
            radius_nm: Search radius in nautical miles
        
        Returns:
            List of AircraftData within radius
        """
        # Check rate limit
        if self._check_rate_limit():
            _LOGGER.warning("OpenSky rate limited, using cached data only")
            return []
        
        # Calculate bounding box from centre point and radius
        lamin, lomin, lamax, lomax = self.calculate_bounding_box(
            latitude, longitude, radius_nm
        )
        
        try:
            params = {
                "lamin": lamin,
                "lomin": lomin,
                "lamax": lamax,
                "lomax": lomax
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{OPENSKY_API_BASE_URL}{OPENSKY_STATES_ENDPOINT}",
                    params=params,
                    auth=self._auth,
                    timeout=aiohttp.ClientTimeout(total=self._timeout)
                ) as response:
                    self._increment_credits(1)  # Track credit usage
                    
                    if response.status == 429:
                        self._handle_rate_limit_response(response)
                        return []
                    
                    if response.status != 200:
                        _LOGGER.warning(
                            "OpenSky returned HTTP %d: %s",
                            response.status,
                            response.reason
                        )
                        return []
                    
                    data = await response.json()
                    
                    if not data.get("states"):
                        _LOGGER.debug("OpenSky: no aircraft in area")
                        return []
                    
                    aircraft_list = []
                    fetch_time = datetime.fromtimestamp(data["time"], tz=timezone.utc)
                    
                    for state in data["states"]:
                        try:
                            aircraft = self._parse_state_vector(state, data["time"])
                            if aircraft:
                                aircraft_list.append(aircraft)
                                self._cache_aircraft(aircraft)
                        except Exception as e:
                            _LOGGER.debug(
                                "Failed to parse OpenSky state: %s",
                                str(e)
                            )
                            continue
                    
                    _LOGGER.debug(
                        "Fetched %d aircraft from OpenSky (%.2f, %.2f, %dnm) - %d credits used",
                        len(aircraft_list),
                        latitude,
                        longitude,
                        radius_nm,
                        self._credits_used_today
                    )
                    
                    # Filter by exact distance (bbox is approximate)
                    return self.filter_aircraft_by_distance(
                        aircraft_list, latitude, longitude, radius_nm
                    )
        
        except (asyncio.TimeoutError, TimeoutError):
            _LOGGER.warning("OpenSky request timeout after %ds", self._timeout)
            return []
        
        except Exception as e:
            _LOGGER.error("OpenSky query failed: %s", str(e))
            return []
    
    def _handle_rate_limit_response(self, response: aiohttp.ClientResponse) -> None:
        """Handle 429 rate limit response.
        
        Args:
            response: HTTP response with status 429
        """
        self._rate_limited = True
        
        # Check for Retry-After header
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                # Retry-After can be seconds or HTTP date
                retry_seconds = int(retry_after)
                self._rate_limit_reset_time = dt_util.utcnow() + timedelta(seconds=retry_seconds)
            except ValueError:
                # Default to 1 hour if we can't parse
                self._rate_limit_reset_time = dt_util.utcnow() + timedelta(hours=1)
        else:
            # No Retry-After header, default to 1 hour
            self._rate_limit_reset_time = dt_util.utcnow() + timedelta(hours=1)
        
        _LOGGER.warning(
            "OpenSky rate limit (429) reached. Will retry after %s",
            self._rate_limit_reset_time.isoformat()
        )
    
    def _parse_state_vector(
        self, state: List, fetch_time: int
    ) -> Optional[AircraftData]:
        """Parse OpenSky state vector to AircraftData.
        
        Args:
            state: State vector array from OpenSky API
            fetch_time: Unix timestamp when data was fetched
        
        Returns:
            AircraftData if valid, None otherwise
        """
        # State vector format:
        # [0] ICAO24, [1] callsign, [2] origin_country, [3] time_position,
        # [4] last_contact, [5] longitude, [6] latitude, [7] baro_altitude,
        # [8] on_ground, [9] velocity, [10] true_track, [11] vertical_rate,
        # [12] sensors, [13] geo_altitude, [14] squawk, [15] spi, [16] position_source
        
        try:
            icao24 = state[0]
            if not icao24:
                return None
            
            # Position required for tracking
            longitude = state[5]
            latitude = state[6]
            if longitude is None or latitude is None:
                return None
            
            # Parse optional fields
            callsign = state[1].strip() if state[1] else None
            origin_country = state[2]
            
            # Altitude (meters) - prefer barometric, fall back to geometric
            altitude_m = state[7] if state[7] is not None else state[13]
            altitude_ft = int(altitude_m * 3.28084) if altitude_m is not None else None
            
            # On ground flag
            on_ground = state[8] if state[8] is not None else None
            
            # Velocity (m/s) → knots
            velocity_ms = state[9]
            ground_speed_kt = int(velocity_ms * 1.94384) if velocity_ms is not None else None
            
            # True track (degrees)
            track_deg = int(state[10]) if state[10] is not None else None
            
            # Vertical rate (m/s) → ft/min
            vertical_rate_ms = state[11]
            vertical_rate_fpm = int(vertical_rate_ms * 196.85) if vertical_rate_ms is not None else None
            
            # Squawk code
            squawk = state[14] if len(state) > 14 else None
            
            # Position source: 0=ADS-B, 1=ASTERIX, 2=MLAT, 3=FLARM
            position_source = state[16] if len(state) > 16 else 0
            is_flarm = (position_source == 3)
            
            # Time
            last_contact_timestamp = state[4]
            last_contact = datetime.fromtimestamp(last_contact_timestamp, tz=timezone.utc)
            
            aircraft = AircraftData(
                registration=None,  # OpenSky doesn't provide registration
                icao24=icao24.upper(),  # Normalize to uppercase
                latitude=latitude,
                longitude=longitude,
                altitude_ft=altitude_ft,
                ground_speed_kt=ground_speed_kt,
                track_deg=track_deg,
                vertical_rate_fpm=vertical_rate_fpm,
                callsign=callsign,
                squawk=squawk,
                is_on_ground=on_ground,
                is_flarm=is_flarm,
                source="opensky",
                priority=self.priority,
                last_seen=last_contact,
                last_contact=last_contact,
                metadata={
                    "origin_country": origin_country,
                    "position_source": position_source,
                    "position_source_name": ["ADS-B", "ASTERIX", "MLAT", "FLARM"][position_source],
                }
            )
            
            return aircraft
        
        except (IndexError, ValueError, TypeError) as e:
            _LOGGER.debug("Invalid OpenSky state vector: %s", str(e))
            return None
