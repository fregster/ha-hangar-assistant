"""OGN (Open Gliding Network) client for FLARM aircraft tracking.

This module provides a client for the Open Gliding Network APRS feed, enabling
real-time tracking of gliders and other FLARM-equipped aircraft.

OGN is a community network of ground receivers tracking FLARM and other
low-power trackers used primarily by gliders, paramotors, and drones.

Architecture:
    - Connects to OGN APRS feed via aprslib
    - Parses APRS packets to extract position, altitude, speed, track
    - Queries OGN Device Database (DDB) for aircraft type/registration
    - Priority 3 data source (free unlimited, FLARM only)
    - Automatic reconnection on connection loss

Data Source Priority: 3 (free unlimited, FLARM-only coverage)

APRS Packet Format (OGN):
    FLRDD1234>APRS,qAS,RECEIVER:/093045h5123.45N/00123.45W'123/045/A=002500 !W12! id06DD1234 +020fpm +0.5rot 5.5dB 0e -0.3kHz gps2x3

Parsed Fields:
    - Time: 09:30:45 UTC
    - Position: 51°23.45'N, 001°23.45'W
    - Track: 123°
    - Speed: 45 knots
    - Altitude: 2500 feet
    - FLARM ID: DD1234
    - Vertical rate: +20 fpm
    - Turn rate: +0.5°/s
    - Signal quality: 5.5dB

OGN Device Database (DDB):
    Provides aircraft registration and type information for FLARM IDs.
    API: http://ddb.glidernet.org/download/?j=1&t=1&id={flarm_id}
    
    Response:
    {
        "devices": [{
            "device_id": "DD1234",
            "registration": "G-ABCD",
            "cn": "AB",
            "aircraft_type": "ASW 20"
        }]
    }

Connection Management:
    - APRS connection can drop unexpectedly
    - Automatic reconnection with exponential backoff
    - Geographic radius filter to reduce bandwidth
    - Connection health monitoring (uptime, packet rate)

Rate Limits:
    - OGN APRS feed is free and unlimited
    - Respect community guidelines: don't connect/disconnect rapidly
    - DDB queries should be cached (24 hours, aircraft types rarely change)

Used By:
    - ADSBManager (multi-source manager)
    - Device tracker entities
    - Gliding club fleet tracking
    - Soaring site traffic monitoring

Configuration:
    The OGN client is enabled by default (free, no API key required):
    - CONF_OGN_ENABLED: Enable/disable OGN data source (default: True)
    - CONF_OGN_CALLSIGN: APRS callsign (default: "HA-HANGAR")
    - CONF_OGN_DDB_CACHE_HOURS: DDB cache duration (default: 24)

Example:
    >>> # Basic configuration (default callsign)
    >>> config = {"callsign": "HA-HANGAR"}
    >>> client = OGNClient(hass, config)
    >>> 
    >>> # Connect and fetch aircraft near location
    >>> success, error = await client.test_connection()
    >>> if success:
    ...     aircraft = await client.get_aircraft_near_location(51.4775, -0.4614, 25)
    ...     print(f"Found {len(aircraft)} gliders")
"""

import asyncio
import logging
import re
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..const import (
    ADSB_PRIORITY_OGN,
)
from .adsb_client_base import ADSBClientBase
from .adsb_models import AircraftData

_LOGGER = logging.getLogger(__name__)

# Optional dependency - try import, gracefully degrade if missing
try:
    import aprslib
    HAS_APRSLIB = True
except ImportError:
    HAS_APRSLIB = False
    aprslib = None  # Allow patching in tests

# OGN APRS configuration
OGN_APRS_HOST = "aprs.glidernet.org"
OGN_APRS_PORT = 14580
OGN_APRS_READONLY_PASSCODE = "-1"  # Read-only access
OGN_DDB_URL = "http://ddb.glidernet.org/download/"

# APRS packet parsing patterns
# Example: FLRDD1234>APRS,qAS,RECEIVER:/093045h5123.45N/00123.45W'123/045/A=002500
APRS_POSITION_PATTERN = re.compile(
    r'/(?P<time>\d{6})h'
    r'(?P<lat>\d{4}\.\d{2})(?P<lat_dir>[NS])/'
    r'(?P<lon>\d{5}\.\d{2})(?P<lon_dir>[EW])'
    r"'(?P<track>\d{3})/(?P<speed>\d{3})/"
    r'A=(?P<altitude>\d{6})'
)

# Extension data: id06DD1234 +020fpm +0.5rot
APRS_EXTENSION_PATTERN = re.compile(
    r'id(?P<addr_type>\d{2})(?P<id>\w+)\s+'
    r'(?P<climb>[+-]\d+)fpm\s+'
    r'(?P<turn>[+-]\d+\.\d+)rot'
)

# Address types (first 2 digits of ID)
OGN_ADDR_TYPE_RANDOM = 0
OGN_ADDR_TYPE_ICAO = 1
OGN_ADDR_TYPE_FLARM = 2
OGN_ADDR_TYPE_OGN = 3


class OGNClient(ADSBClientBase):
    """Client for Open Gliding Network APRS feed.
    
    Connects to OGN APRS network to track FLARM-equipped aircraft.
    
    Attributes:
        _callsign: APRS callsign for connection identification
        _aprs_connection: Active APRS connection (if connected)
        _connected: Connection status flag
        _reconnect_task: Background reconnection task
        _packet_count: Total packets received since connection
        _parse_errors: Packet parsing error count
        _last_packet_time: Timestamp of last received packet
        _ddb_cache: OGN Device Database lookup cache (FLARM ID → aircraft details)
        _ddb_cache_hours: How long to cache DDB lookups (default: 24 hours)
    """
    
    def __init__(
        self,
        hass: HomeAssistant,
        config: Dict[str, any]
    ):
        """Initialise OGN APRS client.
        
        Args:
            hass: Home Assistant instance
            config: Configuration dictionary with:
                - callsign: APRS callsign (default: "HA-HANGAR")
                - ddb_cache_hours: DDB cache duration (default: 24)
                - timeout: Connection timeout in seconds (default: 30)
        """
        super().__init__(
            hass=hass,
            config=config,
            priority=ADSB_PRIORITY_OGN,
            cache_ttl=30,  # Fresh data every 30 seconds
            max_cache_entries=500
        )
        
        # APRS configuration
        self._callsign = config.get("callsign", "HA-HANGAR")
        self._timeout = config.get("timeout", 30)
        
        # Connection state
        self._aprs_connection = None
        self._connected = False
        self._reconnect_task = None
        self._reconnect_delay = 30  # Start with 30 seconds
        self._max_reconnect_delay = 300  # Max 5 minutes
        
        # Statistics
        self._packet_count = 0
        self._parse_errors = 0
        self._last_packet_time: Optional[datetime] = None
        self._connection_uptime_start: Optional[datetime] = None
        
        # OGN Device Database cache
        self._ddb_cache: OrderedDict[str, Tuple[Dict, datetime]] = OrderedDict()
        self._ddb_cache_hours = config.get("ddb_cache_hours", 24)
        self._max_ddb_cache_entries = 1000
        
        # Geographic filter (set by get_aircraft_near_location)
        self._filter_latitude: Optional[float] = None
        self._filter_longitude: Optional[float] = None
        self._filter_radius_km: Optional[float] = None
        
        _LOGGER.debug(
            "Initialised OGN client: callsign=%s, priority=%d, DDB cache=%dh",
            self._callsign, self.priority, self._ddb_cache_hours
        )
    
    async def test_connection(self) -> Tuple[bool, Optional[str]]:
        """Test OGN APRS connection.
        
        Attempts to connect to OGN APRS feed and verify connection.
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            # Check if aprslib is available
            if not HAS_APRSLIB:
                return False, "aprslib not installed. Install with: pip install aprslib"
            
            # Attempt connection
            test_client = aprslib.IS(
                self._callsign,
                passwd=OGN_APRS_READONLY_PASSCODE,
                host=OGN_APRS_HOST,
                port=OGN_APRS_PORT
            )
            
            # Connect with timeout
            await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    test_client.connect
                ),
                timeout=self._timeout
            )
            
            # Connection successful
            test_client.close()
            
            _LOGGER.info("OGN APRS connection test successful")
            return True, None
        
        except ImportError:
            error = "aprslib library not installed"
            _LOGGER.error("OGN: %s", error)
            return False, error
        
        except asyncio.TimeoutError:
            error = f"Connection timeout after {self._timeout}s"
            _LOGGER.error("OGN: %s", error)
            return False, error
        
        except Exception as e:
            error = f"Connection failed: {str(e)}"
            _LOGGER.error("OGN: %s", error)
            return False, error
    
    async def get_aircraft_by_registration(
        self, registration: str
    ) -> List[AircraftData]:
        """Get aircraft data by registration.
        
        Searches DDB for FLARM ID matching registration, then searches
        received packets for that ID.
        
        Args:
            registration: Aircraft registration (e.g., "G-ABCD")
        
        Returns:
            List of matching aircraft (typically 0 or 1)
        """
        # Query DDB for FLARM ID matching registration
        flarm_id = await self._lookup_flarm_id_by_registration(registration)
        if not flarm_id:
            return []
        
        # Search cache for aircraft with that FLARM ID
        cache_key = f"flarm:{flarm_id.upper()}"
        cached = self._get_cached_aircraft(cache_key)
        if cached:
            return [cached]
        
        return []
    
    async def get_aircraft_by_icao24(self, icao24: str) -> Optional[AircraftData]:
        """Get aircraft data by ICAO24 hex code.
        
        OGN tracks FLARM IDs, not ICAO24 addresses. This method searches
        for aircraft with matching ICAO24 in the cache.
        
        Args:
            icao24: ICAO24 hex code (e.g., "4CA1E3")
        
        Returns:
            AircraftData if found in cache, None otherwise
        """
        # Check cache
        cache_key = f"icao24:{icao24.upper()}"
        return self._get_cached_aircraft(cache_key)
    
    async def get_aircraft_near_location(
        self, latitude: float, longitude: float, radius_nm: float = 10
    ) -> List[AircraftData]:
        """Get all aircraft within radius of location.
        
        Connects to OGN APRS feed with geographic filter, receives packets
        for a short period, then returns parsed aircraft.
        
        Args:
            latitude: Centre latitude
            longitude: Centre longitude
            radius_nm: Search radius in nautical miles
        
        Returns:
            List of AircraftData within radius
        """
        # Update filter parameters
        self._filter_latitude = latitude
        self._filter_longitude = longitude
        self._filter_radius_km = radius_nm * 1.852  # NM → km
        
        # Ensure connection with updated filter
        await self._ensure_connected()
        
        if not self._connected:
            _LOGGER.warning("OGN: Not connected, cannot fetch aircraft")
            return []
        
        # Collect packets for 10 seconds (enough to get recent traffic)
        await asyncio.sleep(10)
        
        # Return all cached aircraft within radius
        aircraft_list = []
        for cached_aircraft, _ in self._cache.values():
            if isinstance(cached_aircraft, AircraftData):
                distance_nm = cached_aircraft.distance_to(latitude, longitude)
                if distance_nm <= radius_nm:
                    aircraft_list.append(cached_aircraft)
        
        return aircraft_list
    
    async def _ensure_connected(self) -> None:
        """Ensure APRS connection is active, reconnect if needed."""
        if self._connected and self._aprs_connection:
            return  # Already connected
        
        if self._reconnect_task and not self._reconnect_task.done():
            return  # Reconnection already in progress
        
        # Start reconnection task
        self._reconnect_task = asyncio.create_task(self._connect_aprs())
    
    async def _connect_aprs(self) -> None:
        """Connect to OGN APRS feed with geographic filter."""
        if not HAS_APRSLIB:
            _LOGGER.error("OGN: aprslib not installed, cannot connect")
            return
        
        try:
            # Create APRS client
            self._aprs_connection = aprslib.IS(
                self._callsign,
                passwd=OGN_APRS_READONLY_PASSCODE,
                host=OGN_APRS_HOST,
                port=OGN_APRS_PORT
            )
            
            # Set geographic filter (reduce bandwidth)
            if (self._filter_latitude is not None and 
                self._filter_longitude is not None and 
                self._filter_radius_km is not None):
                
                filter_str = (
                    f"r/{self._filter_latitude:.4f}/"
                    f"{self._filter_longitude:.4f}/"
                    f"{int(self._filter_radius_km)}"
                )
                self._aprs_connection.set_filter(filter_str)
                _LOGGER.debug("OGN: Set filter: %s", filter_str)
            
            # Connect with timeout
            await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    self._aprs_connection.connect
                ),
                timeout=self._timeout
            )
            
            self._connected = True
            self._connection_uptime_start = dt_util.utcnow()
            self._reconnect_delay = 30  # Reset backoff
            
            _LOGGER.info("OGN: Connected to APRS feed at %s:%d", OGN_APRS_HOST, OGN_APRS_PORT)
            
            # Start receiving packets
            asyncio.create_task(self._receive_packets())
        
        except Exception as e:
            self._connected = False
            _LOGGER.error("OGN: Connection failed: %s", e)
            
            # Schedule reconnection with exponential backoff
            await asyncio.sleep(self._reconnect_delay)
            self._reconnect_delay = min(
                self._reconnect_delay * 2,
                self._max_reconnect_delay
            )
            asyncio.create_task(self._connect_aprs())
    
    async def _receive_packets(self) -> None:
        """Receive and process APRS packets in background."""
        if not self._aprs_connection:
            return
        
        try:
            # Process packets in executor (aprslib.consumer blocks)
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._aprs_connection.consumer(
                    callback=self._handle_packet,
                    raw=False  # Parse packets automatically
                )
            )
        
        except Exception as e:
            _LOGGER.error("OGN: Packet receiver error: %s", e)
            self._connected = False
            
            # Reconnect
            asyncio.create_task(self._connect_aprs())
    
    def _handle_packet(self, packet: Dict) -> None:
        """Handle received APRS packet.
        
        Called by aprslib for each received packet.
        
        Args:
            packet: Parsed APRS packet dictionary
        """
        try:
            self._packet_count += 1
            self._last_packet_time = dt_util.utcnow()
            
            # Parse OGN-specific data
            aircraft = self._parse_ogn_packet(packet)
            if aircraft:
                # Cache aircraft
                self._cache_aircraft(aircraft)
                
                _LOGGER.debug(
                    "OGN: Parsed %s (%s) at %.4f,%.4f %dft",
                    aircraft.icao24 or aircraft.registration or "Unknown",
                    aircraft.callsign or "",
                    aircraft.latitude,
                    aircraft.longitude,
                    aircraft.altitude_ft or 0
                )
        
        except Exception as e:
            self._parse_errors += 1
            _LOGGER.debug("OGN: Packet parse error: %s", e)
    
    def _parse_ogn_packet(self, packet: Dict) -> Optional[AircraftData]:
        """Parse OGN APRS packet to AircraftData.
        
        Args:
            packet: Parsed APRS packet from aprslib
        
        Returns:
            AircraftData if valid OGN packet, None otherwise
        """
        try:
            # Extract comment (contains position and extension data)
            comment = packet.get("comment", "")
            if not comment:
                return None
            
            # Match position data
            pos_match = APRS_POSITION_PATTERN.search(comment)
            if not pos_match:
                return None
            
            # Parse position
            lat_deg = int(pos_match.group("lat")[:2])
            lat_min = float(pos_match.group("lat")[2:])
            latitude = lat_deg + (lat_min / 60.0)
            if pos_match.group("lat_dir") == "S":
                latitude = -latitude
            
            lon_deg = int(pos_match.group("lon")[:3])
            lon_min = float(pos_match.group("lon")[3:])
            longitude = lon_deg + (lon_min / 60.0)
            if pos_match.group("lon_dir") == "W":
                longitude = -longitude
            
            # Parse altitude (feet)
            altitude_ft = int(pos_match.group("altitude"))
            
            # Parse speed (knots) and track (degrees)
            ground_speed_kt = int(pos_match.group("speed"))
            track_deg = int(pos_match.group("track"))
            
            # Match extension data (FLARM ID, climb, turn rate)
            ext_match = APRS_EXTENSION_PATTERN.search(comment)
            flarm_id = None
            vertical_rate_fpm = None
            turn_rate = None
            addr_type = OGN_ADDR_TYPE_FLARM  # Default to FLARM if no extension
            
            if ext_match:
                addr_type = int(ext_match.group("addr_type"))
                flarm_id = ext_match.group("id").upper()
                vertical_rate_fpm = int(ext_match.group("climb"))
                turn_rate = float(ext_match.group("turn"))
            
            # Get sender callsign (often the receiver station)
            sender = packet.get("from", "")
            
            # If no FLARM ID from extension, use sender as identifier
            # This ensures AircraftData validation passes (requires at least one ID)
            if not flarm_id and sender:
                flarm_id = sender.upper()
            
            # Determine ICAO24 vs FLARM ID
            icao24 = None
            is_flarm = True
            
            if ext_match and addr_type == OGN_ADDR_TYPE_ICAO:
                icao24 = flarm_id
                is_flarm = False
            
            # Time from packet (HH:MM:SS format)
            time_str = pos_match.group("time")
            now = dt_util.utcnow()
            packet_time = now.replace(
                hour=int(time_str[0:2]),
                minute=int(time_str[2:4]),
                second=int(time_str[4:6]),
                microsecond=0
            )
            
            # If packet time is in future, it's from yesterday
            if packet_time > now:
                packet_time -= timedelta(days=1)
            
            # Query DDB for registration/type (async task)
            # Note: This is done in background to avoid blocking packet processing
            if flarm_id:
                # Use hass.async_create_task to ensure proper event loop handling
                self.hass.async_create_task(self._enrich_with_ddb(flarm_id))
            
            # Get cached DDB info if available
            ddb_info = self._get_ddb_cache(flarm_id) if flarm_id else None
            registration = ddb_info.get("registration") if ddb_info else None
            aircraft_type = ddb_info.get("aircraft_type") if ddb_info else None
            
            # Create AircraftData
            aircraft = AircraftData(
                registration=registration,
                icao24=icao24,
                flarm_id=flarm_id,  # Pass FLARM ID directly (required identifier)
                latitude=latitude,
                longitude=longitude,
                altitude_ft=altitude_ft,
                ground_speed_kt=ground_speed_kt,
                track_deg=track_deg,
                vertical_rate_fpm=vertical_rate_fpm,
                callsign=None,  # OGN doesn't provide callsigns
                squawk=None,
                is_on_ground=altitude_ft < 100,  # Rough estimate
                is_flarm=is_flarm,
                source="ogn",
                priority=self.priority,
                last_seen=packet_time,
                last_contact=packet_time,
                metadata={
                    "turn_rate": turn_rate,
                    "receiver": sender,
                    "aircraft_type": aircraft_type,
                    "addr_type": addr_type,
                    "addr_type_name": ["Random", "ICAO", "FLARM", "OGN"][addr_type] if addr_type < 4 else "Unknown"
                }
            )
            
            return aircraft
        
        except (KeyError, ValueError, IndexError) as e:
            _LOGGER.debug("OGN: Invalid packet format: %s", e)
            return None
    
    async def _enrich_with_ddb(self, flarm_id: str) -> None:
        """Query OGN Device Database for aircraft details.
        
        Runs in background to avoid blocking packet processing.
        
        Args:
            flarm_id: FLARM ID (6-character hex)
        """
        # Check cache first
        if self._get_ddb_cache(flarm_id):
            return  # Already cached
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    OGN_DDB_URL,
                    params={"j": "1", "t": "1", "id": flarm_id},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        devices = data.get("devices", [])
                        if devices:
                            device = devices[0]
                            ddb_info = {
                                "registration": device.get("registration"),
                                "aircraft_type": device.get("aircraft_type"),
                                "cn": device.get("cn")  # Competition number
                            }
                            self._set_ddb_cache(flarm_id, ddb_info)
        
        except Exception as e:
            _LOGGER.debug("OGN: DDB query failed for %s: %s", flarm_id, e)
    
    def _get_ddb_cache(self, flarm_id: str) -> Optional[Dict]:
        """Get cached DDB info for FLARM ID.
        
        Args:
            flarm_id: FLARM ID
        
        Returns:
            DDB info dict or None if not cached or expired
        """
        if flarm_id in self._ddb_cache:
            info, cached_time = self._ddb_cache[flarm_id]
            age = (dt_util.utcnow() - cached_time).total_seconds() / 3600
            
            if age < self._ddb_cache_hours:
                # Move to end (LRU)
                self._ddb_cache.move_to_end(flarm_id)
                return info
            else:
                # Expired
                del self._ddb_cache[flarm_id]
        
        return None
    
    def _set_ddb_cache(self, flarm_id: str, info: Dict) -> None:
        """Cache DDB info for FLARM ID.
        
        Args:
            flarm_id: FLARM ID
            info: DDB information dictionary
        """
        self._ddb_cache[flarm_id] = (info, dt_util.utcnow())
        self._ddb_cache.move_to_end(flarm_id)
        
        # Evict oldest if over limit
        while len(self._ddb_cache) > self._max_ddb_cache_entries:
            self._ddb_cache.popitem(last=False)
    
    async def _lookup_flarm_id_by_registration(self, registration: str) -> Optional[str]:
        """Query DDB for FLARM ID by registration.
        
        Args:
            registration: Aircraft registration
        
        Returns:
            FLARM ID if found, None otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    OGN_DDB_URL,
                    params={"j": "1", "r": registration.upper()},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        devices = data.get("devices", [])
                        if devices:
                            return devices[0].get("device_id")
        
        except Exception as e:
            _LOGGER.debug("OGN: DDB registration query failed for %s: %s", registration, e)
        
        return None
    
    def get_connection_stats(self) -> Dict[str, any]:
        """Get connection statistics.
        
        Returns:
            Dictionary with connection health metrics
        """
        uptime_seconds = 0
        if self._connection_uptime_start:
            uptime_seconds = (dt_util.utcnow() - self._connection_uptime_start).total_seconds()
        
        return {
            "connected": self._connected,
            "uptime_seconds": int(uptime_seconds),
            "packets_received": self._packet_count,
            "parse_errors": self._parse_errors,
            "last_packet_time": self._last_packet_time.isoformat() if self._last_packet_time else None,
            "ddb_cache_size": len(self._ddb_cache),
            "aircraft_cache_size": len(self._cache)
        }
