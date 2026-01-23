"""dump1090 client for local ADS-B receiver integration.

This module provides a client for dump1090/readsb JSON output, enabling local
ADS-B receiver integration for real-time aircraft tracking.

dump1090 is a popular open-source ADS-B decoder for RTL-SDR USB receivers.
It provides a JSON API at http://localhost:8080/data/aircraft.json by default.

Architecture:
    - Connects to local dump1090/readsb instance via HTTP
    - Parses JSON aircraft array into AircraftData objects
    - Highest priority data source (priority=1, local, lowest latency)
    - No rate limits (local data)
    - Supports both dump1090 and readsb formats

Data Source Priority: 1 (highest - local receiver)

JSON Format (dump1090/readsb):
    {
        "now": 1234567890.0,
        "messages": 12345,
        "aircraft": [
            {
                "hex": "4CA1E3",           # ICAO24 hex code
                "flight": "BAW123  ",      # Callsign (8 chars, space-padded)
                "r": "G-ABCD",             # Registration
                "t": "B738",               # Aircraft type
                "alt_baro": 15000,         # Barometric altitude (feet)
                "alt_geom": 15200,         # Geometric altitude (feet)
                "gs": 450.5,               # Ground speed (knots)
                "track": 270.0,            # Track angle (degrees)
                "baro_rate": 1024,         # Vertical rate (ft/min)
                "lat": 51.4775,            # Latitude
                "lon": -0.4614,            # Longitude
                "seen": 0.5,               # Seconds since last message
                "seen_pos": 1.2,           # Seconds since last position
                "category": "A3",          # Aircraft category
                "squawk": "7000"           # Transponder code
            }
        ]
    }

Used By:
    - ADSBManager (multi-source manager)
    - Device tracker entities
    - Traffic sensors

Configuration:
    The dump1090 URL is configured through global settings (entry.data["settings"]):
    - CONF_DUMP1090_URL: Full URL to dump1090 JSON endpoint
    - CONF_DUMP1090_TIMEOUT: Request timeout in seconds
    
    Default: http://localhost:8080/data/aircraft.json

Example:
    >>> # Configuration typically loaded from settings
    >>> config = {
    ...     "url": "http://192.168.1.100:8080/data/aircraft.json",
    ...     "timeout": 5
    ... }
    >>> client = Dump1090Client(hass, config)
    >>> success, error = await client.test_connection()
    >>> if success:
    ...     aircraft = await client.get_aircraft_near_location(51.4775, -0.4614, 10)
    ...     for a in aircraft:
    ...         print(f"{a.registration} at {a.altitude_ft}ft")
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .http_proxy import HttpClientProxy, HttpRequestOptions, NullCache
from ..const import (
    ADSB_PRIORITY_DUMP1090,
    DEFAULT_DUMP1090_URL,
    DEFAULT_DUMP1090_TIMEOUT,
)
from .adsb_client_base import ADSBClientBase
from .adsb_models import AircraftData

_LOGGER = logging.getLogger(__name__)


class Dump1090Client(ADSBClientBase):
    """Client for dump1090/readsb local ADS-B receiver.
    
    Connects to local dump1090 instance via HTTP to retrieve real-time aircraft data.
    
    Inputs:
        hass: Home Assistant instance
        config: Configuration dict with host, port, endpoint, timeout
    
    Outputs:
        - AircraftData objects from local receiver
        - Highest priority (1) for deduplication
    
    Configuration:
        url: Full URL to dump1090 JSON endpoint (default: http://localhost:8080/data/aircraft.json)
        timeout: Request timeout in seconds (default: 5)
    
    Rate Limits:
        None - local data source
    
    Example:
        >>> client = Dump1090Client(hass, {"url": "http://192.168.1.100:8080/data/aircraft.json"})
        >>> aircraft_list = await client.get_aircraft_near_location(51.5, -0.5, 25)
    """
    
    def __init__(self, hass: HomeAssistant, config: Dict):
        """Initialise dump1090 client.
        
        Args:
            hass: Home Assistant instance
            config: Configuration dictionary with 'url' and optional 'timeout'
        """
        super().__init__(
            hass=hass,
            config=config,
            priority=ADSB_PRIORITY_DUMP1090,  # Highest priority (local data)
            cache_enabled=True,
            cache_ttl=30,  # 30-second cache (positions update frequently)
            max_cache_entries=500  # Local receiver typically tracks < 500 aircraft
        )
        
        self._url = config.get("url", DEFAULT_DUMP1090_URL)
        self._timeout = config.get("timeout", DEFAULT_DUMP1090_TIMEOUT)
        
        # Initialize HTTP proxy for API requests
        self.http_proxy = HttpClientProxy(
            hass=hass,
            cache=NullCache()  # Dump1090 caching handled in get_aircraft_* methods
        )
        
        _LOGGER.debug(
            "Initialised dump1090 client: %s (priority=%d)",
            self._url,
            self.priority
        )
    
    async def test_connection(self) -> Tuple[bool, Optional[str]]:
        """Test connection to dump1090 instance.
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            options = HttpRequestOptions(
                service="dump1090",
                method="GET",
                url=self._url,
                timeout=self._timeout,
                expected_status=(200, 404, 500)
            )
            
            response = await self.http_proxy.request(options)
            
            if response.status_code != 200:
                return False, f"HTTP {response.status_code}: {response.reason}"
            
            try:
                data = json.loads(response.text)
            except (asyncio.TimeoutError, TimeoutError):
                error_msg = f"Connection timeout after {self._timeout}s"
                _LOGGER.warning("dump1090 connection test failed: %s", error_msg)
                return False, error_msg
            
            # Validate response structure
            if "aircraft" not in data:
                return False, "Invalid dump1090 response: missing 'aircraft' key"
            
            if not isinstance(data["aircraft"], list):
                return False, "Invalid dump1090 response: 'aircraft' must be array"
            
            aircraft_count = len(data["aircraft"])
            _LOGGER.info(
                "dump1090 connection successful: %d aircraft visible",
                aircraft_count
            )
            return True, None
        
        except Exception as e:
            error_msg = f"Connection failed: {str(e)}"
            _LOGGER.warning("dump1090 connection test failed: %s", error_msg)
            return False, error_msg
        
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            _LOGGER.error("dump1090 connection test failed: %s", error_msg)
            return False, error_msg
    
    async def get_aircraft_by_registration(
        self, registration: str
    ) -> Optional[AircraftData]:
        """Get aircraft data by registration.
        
        Args:
            registration: Aircraft registration (e.g., "G-ABCD")
        
        Returns:
            AircraftData if found, None otherwise
        """
        # Check cache first
        cache_key = f"reg:{registration.upper()}"
        cached = self._get_cached_aircraft(cache_key)
        if cached:
            return cached
        
        # Fetch all aircraft and filter
        all_aircraft = await self._fetch_all_aircraft()
        
        reg_upper = registration.upper().strip()
        for aircraft in all_aircraft:
            if aircraft.registration and aircraft.registration.upper() == reg_upper:
                self._cache_aircraft(aircraft)
                return aircraft
        
        return None
    
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
        
        # Fetch all aircraft and filter
        all_aircraft = await self._fetch_all_aircraft()
        
        icao_upper = icao24.upper().strip()
        for aircraft in all_aircraft:
            if aircraft.icao24 and aircraft.icao24.upper() == icao_upper:
                self._cache_aircraft(aircraft)
                return aircraft
        
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
        all_aircraft = await self._fetch_all_aircraft()
        
        # Filter by distance
        return self.filter_aircraft_by_distance(
            all_aircraft, latitude, longitude, radius_nm
        )
    
    async def _fetch_all_aircraft(self) -> List[AircraftData]:
        """Fetch all aircraft from dump1090 JSON endpoint.
        
        Returns:
            List of AircraftData from local receiver
        
        Raises:
            aiohttp.ClientError: If HTTP request fails
            ValueError: If JSON parsing fails
        """
        try:
            options = HttpRequestOptions(
                service="dump1090",
                method="GET",
                url=self._url,
                timeout=self._timeout,
                expected_status=(200, 404, 500)
            )
            
            response = await self.http_proxy.request(options)
            
            if response.status_code != 200:
                _LOGGER.warning(
                    "dump1090 returned HTTP %d: %s",
                    response.status_code,
                    response.reason
                )
                return []
            
            data = json.loads(response.text)
            
            if "aircraft" not in data:
                _LOGGER.warning("dump1090 response missing 'aircraft' key")
                return []
            
            aircraft_list = []
            now = dt_util.utcnow()
            
            for ac_json in data["aircraft"]:
                try:
                    aircraft = self._parse_aircraft_json(ac_json, now)
                    if aircraft:
                        aircraft_list.append(aircraft)
                        self._cache_aircraft(aircraft)
                except Exception as e:
                    _LOGGER.debug(
                        "Failed to parse aircraft JSON: %s - %s",
                        ac_json.get("hex", "unknown"),
                        str(e)
                    )
                    continue
            
            _LOGGER.debug(
                "Fetched %d aircraft from dump1090 at %s",
                len(aircraft_list),
                self._url
            )
            
            return aircraft_list
        
        except Exception as e:
            _LOGGER.error("dump1090 fetch failed: %s", str(e))
            return []
    
    def _parse_aircraft_json(
        self, ac_json: Dict, fetch_time: datetime
    ) -> Optional[AircraftData]:
        """Parse dump1090 JSON aircraft object to AircraftData.
        
        Args:
            ac_json: Aircraft JSON object from dump1090
            fetch_time: Time aircraft list was fetched
        
        Returns:
            AircraftData if valid position available, None otherwise
        """
        # ICAO24 hex code is required (unique identifier)
        icao24 = ac_json.get("hex")
        if not icao24:
            return None
        
        # Position is required for tracking
        latitude = ac_json.get("lat")
        longitude = ac_json.get("lon")
        if latitude is None or longitude is None:
            return None
        
        # Parse optional fields
        registration = ac_json.get("r")  # Registration (may not be in dump1090 DB)
        callsign = ac_json.get("flight", "").strip()  # Flight callsign (space-padded)
        aircraft_type = ac_json.get("t")  # ICAO aircraft type code
        
        # Altitude (prefer barometric, fall back to geometric)
        altitude_ft = ac_json.get("alt_baro") or ac_json.get("alt_geom")
        
        # Ground speed and track
        ground_speed_kt = ac_json.get("gs")
        track_deg = ac_json.get("track")
        
        # Vertical rate (feet per minute)
        vertical_rate_fpm = ac_json.get("baro_rate") or ac_json.get("geom_rate")
        
        # Squawk code
        squawk = ac_json.get("squawk")
        
        # Calculate last_seen (seconds since last message)
        seen_seconds = ac_json.get("seen", 0)
        last_seen = fetch_time - timedelta(seconds=seen_seconds)
        
        # Create AircraftData
        try:
            aircraft = AircraftData(
                registration=registration,
                icao24=icao24,
                latitude=latitude,
                longitude=longitude,
                altitude_ft=int(altitude_ft) if altitude_ft is not None else None,
                ground_speed_kt=int(ground_speed_kt) if ground_speed_kt is not None else None,
                track_deg=int(track_deg) if track_deg is not None else None,
                vertical_rate_fpm=int(vertical_rate_fpm) if vertical_rate_fpm is not None else None,
                aircraft_type=aircraft_type,
                callsign=callsign if callsign else None,
                squawk=squawk,
                is_on_ground=None,  # dump1090 doesn't provide reliable ground status
                is_flarm=False,  # dump1090 is ADS-B only
                source="dump1090",
                priority=self.priority,
                last_seen=last_seen,
                last_contact=fetch_time,
                metadata={
                    "seen_seconds": seen_seconds,
                    "category": ac_json.get("category"),
                    "messages": ac_json.get("messages"),
                    "rssi": ac_json.get("rssi"),  # Signal strength
                }
            )
            
            return aircraft
        
        except ValueError as e:
            _LOGGER.debug(
                "Invalid aircraft data for %s: %s",
                icao24,
                str(e)
            )
            return None
