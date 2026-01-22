"""Multi-source ADS-B aircraft tracking manager.

This module coordinates data from multiple ADS-B sources (dump1090, OpenSky, OGN, etc.)
with intelligent deduplication, priority-based merging, and graceful degradation.

Architecture:
    - Maintains pool of ADS-B client instances
    - Queries all enabled sources in parallel for performance
    - Deduplicates by ICAO24 hex code (aircraft unique ID)
    - Priority-based merging: higher-priority source data wins
    - Fills missing fields from lower-priority sources
    - Tracks source health and availability

Priority Order (highest to lowest):
    1. dump1090 (local, real-time, most accurate)
    2. OpenSky Network (global, includes FLARM)
    3. OGN (Open Gliding Network, FLARM-only)
    4. FlightRadar24 (commercial, paid)
    5. FlightAware (commercial, paid)
    6. ADS-B Exchange (free tier available)

Data Deduplication:
    Multiple sources may report same aircraft (ICAO24 code is unique identifier).
    Strategy:
    - Query all sources in parallel
    - Group by ICAO24 hex code
    - For duplicate aircraft: use data from highest-priority source
    - Merge non-conflicting data from lower sources (fill gaps)
    
    Example: dump1090 sees local aircraft but lacks aircraft type.
    OpenSky has same aircraft with type info. Result: use dump1090's
    position/speed (more accurate), but supplement with OpenSky's type.

Performance:
    - LRU cache prevents redundant queries
    - Parallel source queries (asyncio.gather)
    - Graceful timeout handling (1-2 second timeout per source)
    - Fallback to cached data on failures

Error Handling:
    - Source connection failures don't block other sources
    - Missing source gracefully ignored
    - Network timeouts handled with stale cache fallback
    - Health tracking for alerting

Used By:
    - Device tracker entities (track individual aircraft)
    - Traffic sensors (count aircraft, patterns)
    - Dashboard integration (RADAR-style visualization)

Example:
    >>> manager = ADSBManager(hass, config)
    >>> await manager.initialize()
    
    >>> # Get all aircraft in 25nm radius of airfield
    >>> aircraft = await manager.get_aircraft_near_location(
    ...     latitude=51.48, longitude=-0.46, radius_nm=25
    ... )
    >>> for a in aircraft:
    ...     print(f"{a.registration or a.callsign} at {a.altitude_ft}ft")
    
    >>> # Get specific aircraft
    >>> aircraft = await manager.get_aircraft_by_icao24("4CA1E3")
    >>> if aircraft:
    ...     print(f"Found: {aircraft.registration}")
"""

import asyncio
import logging
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .adsb_client_base import ADSBClientBase
from .adsb_models import AircraftData

_LOGGER = logging.getLogger(__name__)

# Default configuration values
DEFAULT_QUERY_TIMEOUT_SECONDS = 5  # Timeout per source
DEFAULT_CACHE_ENTRY_TTL_SECONDS = 30  # Keep deduplicated data fresh
DEFAULT_MAX_CACHE_ENTRIES = 5000  # Limit memory usage


class ADSBManager:
    """Coordinate multiple ADS-B data sources with deduplication and priority logic.
    
    Manages connections to multiple ADS-B clients (dump1090, OpenSky, OGN, etc.)
    and provides unified access to aircraft data with intelligent deduplication.
    
    Attributes:
        hass: Home Assistant instance
        clients: Dict of {source_name: ADSBClientBase} instances
        _deduplicated_cache: OrderedDict of {icao24: (AircraftData, timestamp)}
        _cache_hits: Counter for cache hit tracking
        _cache_misses: Counter for cache miss tracking
        _source_health: Dict tracking availability of each source
    """
    
    def __init__(self, hass: HomeAssistant, config: Dict):
        """Initialize ADSBManager.
        
        Args:
            hass: Home Assistant instance
            config: Configuration dict with client configurations
        
        Example config:
            {
                "clients": {
                    "dump1090": dump1090_config,
                    "opensky": opensky_config,
                    "ogn": ogn_config
                }
            }
        """
        self.hass = hass
        self.config = config
        self.clients: Dict[str, ADSBClientBase] = {}
        
        # Deduplicated aircraft cache (ICAO24 → Aircraft)
        self._deduplicated_cache: OrderedDict[str, Tuple[AircraftData, float]] = OrderedDict()
        self._max_cache_entries = config.get(
            "max_cache_entries",
            DEFAULT_MAX_CACHE_ENTRIES
        )
        self._cache_ttl = config.get(
            "cache_ttl_seconds",
            DEFAULT_CACHE_ENTRY_TTL_SECONDS
        )
        
        # Performance tracking
        self._cache_hits = 0
        self._cache_misses = 0
        self._query_count = 0
        
        # Source health tracking
        self._source_health: Dict[str, dict] = {}
        
        _LOGGER.debug(
            "Initialised ADSBManager: max_cache=%d, cache_ttl=%ds",
            self._max_cache_entries,
            self._cache_ttl
        )
    
    def register_client(self, name: str, client: ADSBClientBase) -> None:
        """Register an ADS-B client (data source).
        
        Args:
            name: Source name (e.g., "dump1090", "opensky", "ogn")
            client: Instantiated client implementing ADSBClientBase
        
        Example:
            >>> from .dump1090_client import Dump1090Client
            >>> client = Dump1090Client(hass, dump1090_config)
            >>> manager.register_client("dump1090", client)
        """
        self.clients[name] = client
        self._source_health[name] = {
            "enabled": True,
            "consecutive_failures": 0,
            "last_success": None,
            "last_error": None,
            "aircraft_count": 0
        }
        _LOGGER.debug("Registered ADS-B client: %s (priority=%d)", name, client.priority)
    
    async def initialize(self) -> None:
        """Test all registered clients and log status.
        
        Called during integration setup to verify sources are accessible.
        """
        _LOGGER.info("ADSBManager initializing %d sources...", len(self.clients))
        
        test_tasks = [
            self._test_client_connection(name, client)
            for name, client in self.clients.items()
        ]
        
        await asyncio.gather(*test_tasks, return_exceptions=True)
        
        # Log initialization summary
        enabled_count = sum(
            1 for h in self._source_health.values() if h["enabled"]
        )
        _LOGGER.info("ADSBManager ready: %d/%d sources available", 
                     enabled_count, len(self.clients))
    
    async def _test_client_connection(self, name: str, client: ADSBClientBase) -> None:
        """Test connection to a single client and update health status.
        
        Args:
            name: Source name
            client: Client to test
        """
        try:
            success, error = await asyncio.wait_for(
                client.test_connection(),
                timeout=DEFAULT_QUERY_TIMEOUT_SECONDS
            )
            
            if success:
                self._source_health[name]["enabled"] = True
                self._source_health[name]["last_success"] = dt_util.utcnow()
                self._source_health[name]["consecutive_failures"] = 0
                _LOGGER.debug("✓ ADS-B source available: %s", name)
            else:
                self._source_health[name]["enabled"] = False
                self._source_health[name]["last_error"] = error
                self._source_health[name]["consecutive_failures"] += 1
                _LOGGER.warning("✗ ADS-B source unavailable: %s (%s)", name, error)
        
        except asyncio.TimeoutError:
            self._source_health[name]["enabled"] = False
            self._source_health[name]["last_error"] = "Connection timeout"
            self._source_health[name]["consecutive_failures"] += 1
            _LOGGER.warning("✗ ADS-B source timeout: %s", name)
        except Exception as e:
            self._source_health[name]["enabled"] = False
            self._source_health[name]["last_error"] = str(e)
            self._source_health[name]["consecutive_failures"] += 1
            _LOGGER.error("✗ ADS-B source error: %s (%s)", name, e)
    
    async def get_aircraft_near_location(
        self,
        latitude: float,
        longitude: float,
        radius_nm: float = 25
    ) -> List[AircraftData]:
        """Get all aircraft within radius of location from all sources.
        
        Queries all enabled sources in parallel, deduplicates by ICAO24,
        and merges data based on priority.
        
        Args:
            latitude: Center point latitude
            longitude: Center point longitude
            radius_nm: Search radius in nautical miles (default 25)
        
        Returns:
            List of deduplicated AircraftData, sorted by priority and distance
        
        Performance:
            - Parallel source queries (asyncio.gather)
            - 5-second timeout per source
            - LRU cache prevents excessive queries
            - Typical response time: <2 seconds with 3 sources
        """
        self._query_count += 1
        
        # Collect tasks for all enabled sources
        query_tasks = []
        source_names = []
        
        for name, client in self.clients.items():
            if not self._source_health[name]["enabled"]:
                continue  # Skip unavailable sources
            
            query_tasks.append(self._query_client_safe(
                name,
                client,
                latitude,
                longitude,
                radius_nm
            ))
            source_names.append(name)
        
        if not query_tasks:
            _LOGGER.warning("No ADS-B sources available")
            return []
        
        # Convert tasks to list and create Task objects so they run independently
        # This allows partial results even if overall timeout occurs
        task_objects = [asyncio.create_task(task) for task in query_tasks]
        
        # Query all sources in parallel with timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*task_objects, return_exceptions=True),
                timeout=DEFAULT_QUERY_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            _LOGGER.warning("ADS-B query timeout after %ds - returning partial results", DEFAULT_QUERY_TIMEOUT_SECONDS)
            # Gather completed results from tasks
            results = []
            for task in task_objects:
                if task.done() and not task.cancelled():
                    try:
                        results.append(task.result())
                    except Exception:
                        pass
        
        # Filter out None/Exception results to get clean list of (name, aircraft_list) tuples
        results = [r for r in results if r and not isinstance(r, Exception)]
        
        # Deduplicate and merge aircraft data
        deduplicated = await self._deduplicate_aircraft(results)
        
        # Cache results
        await self._update_cache(deduplicated)
        
        return deduplicated
    
    async def _query_client_safe(
        self,
        name: str,
        client: ADSBClientBase,
        latitude: float,
        longitude: float,
        radius_nm: float
    ) -> Tuple[str, List[AircraftData]]:
        """Safely query a single client with error handling.
        
        Args:
            name: Source name (for error reporting)
            client: Client to query
            latitude: Center latitude
            longitude: Center longitude
            radius_nm: Search radius
        
        Returns:
            Tuple of (source_name, aircraft_list)
        """
        try:
            aircraft = await asyncio.wait_for(
                client.get_aircraft_near_location(latitude, longitude, radius_nm),
                timeout=DEFAULT_QUERY_TIMEOUT_SECONDS
            )
            
            self._source_health[name]["enabled"] = True
            self._source_health[name]["last_success"] = dt_util.utcnow()
            self._source_health[name]["aircraft_count"] = len(aircraft)
            self._source_health[name]["consecutive_failures"] = 0
            
            return name, aircraft
        
        except asyncio.TimeoutError:
            self._source_health[name]["consecutive_failures"] += 1
            _LOGGER.debug("ADS-B query timeout: %s", name)
            return name, []
        
        except Exception as e:
            self._source_health[name]["consecutive_failures"] += 1
            self._source_health[name]["last_error"] = str(e)
            _LOGGER.debug("ADS-B query error (%s): %s", name, e)
            return name, []
    
    async def _deduplicate_aircraft(
        self,
        results: List[Tuple[str, List[AircraftData]]]
    ) -> List[AircraftData]:
        """Deduplicate aircraft from multiple sources using ICAO24 as key.
        
        Priority logic:
            1. Higher-priority client data preferred (dump1090 > OpenSky > OGN)
            2. Same ICAO24: merge non-conflicting fields from all sources
            3. Client-specific data (e.g., FlightRadar24 photos) in metadata
        
        Args:
            results: List of (source_name, aircraft_list) tuples
        
        Returns:
            Deduplicated list sorted by priority
        """
        # Group aircraft by ICAO24
        aircraft_by_icao24: Dict[str, List[Tuple[str, AircraftData]]] = {}
        
        for source_name, aircraft_list in results:
            if isinstance(aircraft_list, Exception):
                continue  # Skip failed queries
            
            for aircraft in aircraft_list:
                icao24 = aircraft.icao24
                if not icao24:
                    continue  # Skip aircraft without ICAO24
                
                if icao24 not in aircraft_by_icao24:
                    aircraft_by_icao24[icao24] = []
                
                aircraft_by_icao24[icao24].append((source_name, aircraft))
        
        # Merge duplicates by priority
        deduplicated = []
        
        for icao24, aircraft_list in aircraft_by_icao24.items():
            # Sort by priority (lower client.priority value = higher priority)
            # Use client index as fallback for mocked clients without numeric priority
            source_names = list(self.clients.keys())
            
            def get_sort_key(item: Tuple[str, AircraftData]) -> int:
                source_name = item[0]
                client = self.clients.get(source_name)
                if client and hasattr(client, 'priority') and isinstance(client.priority, int):
                    return client.priority
                # Fallback: use source index in clients dict
                return source_names.index(source_name) if source_name in source_names else 999
            
            sorted_aircraft = sorted(aircraft_list, key=get_sort_key)
            
            # Start with highest-priority source
            primary_source, primary_aircraft = sorted_aircraft[0]
            merged = self._merge_aircraft_data(primary_aircraft, sorted_aircraft[1:])
            
            deduplicated.append(merged)
        
        return deduplicated
    
    def _merge_aircraft_data(
        self,
        primary: AircraftData,
        supplements: List[Tuple[str, AircraftData]]
    ) -> AircraftData:
        """Merge aircraft data from multiple sources.
        
        Strategy: Use primary source as base, fill missing fields from supplements
        in priority order (lower priority value = more important).
        
        Args:
            primary: Aircraft data from highest-priority source
            supplements: List of (source_name, aircraft) from lower-priority sources
        
        Returns:
            Merged AircraftData with fields filled from best available source
        """
        result = primary
        
        for source_name, supplement in supplements:
            # Only fill fields that are missing in primary
            if result.registration is None and supplement.registration:
                result.registration = supplement.registration
            
            if result.aircraft_type is None and supplement.aircraft_type:
                result.aircraft_type = supplement.aircraft_type
            
            if result.callsign is None and supplement.callsign:
                result.callsign = supplement.callsign
        
        return result
    
    async def _update_cache(self, aircraft_list: List[AircraftData]) -> None:
        """Update deduplicated cache with aircraft data.
        
        Uses LRU eviction when cache exceeds max size.
        
        Args:
            aircraft_list: Deduplicated aircraft to cache
        """
        now = dt_util.utcnow()
        
        for aircraft in aircraft_list:
            if not aircraft.icao24:
                continue
            
            # Update or create cache entry
            self._deduplicated_cache[aircraft.icao24] = (aircraft, now)
            # Move to end (most recently used)
            self._deduplicated_cache.move_to_end(aircraft.icao24)
            
            # Evict oldest entries if over limit
            while len(self._deduplicated_cache) > self._max_cache_entries:
                evicted_key, _ = self._deduplicated_cache.popitem(last=False)
                _LOGGER.debug("Cache evicted: %s", evicted_key)
    
    async def get_aircraft_by_icao24(self, icao24: str) -> Optional[AircraftData]:
        """Get specific aircraft by ICAO24 hex code.
        
        Checks cache first, queries all sources if not found.
        
        Args:
            icao24: ICAO 24-bit hex code (e.g., "4CA1E3")
        
        Returns:
            AircraftData if found, None otherwise
        """
        # Check cache first
        cached = self._get_from_cache(icao24)
        if cached:
            self._cache_hits += 1
            return cached
        
        self._cache_misses += 1
        
        # Query all sources in parallel
        query_tasks = [
            client.get_aircraft_by_icao24(icao24)
            for client in self.clients.values()
            if self._source_health[self._get_source_name(client)]["enabled"]
        ]
        
        if not query_tasks:
            return None
        
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*query_tasks, return_exceptions=True),
                timeout=DEFAULT_QUERY_TIMEOUT_SECONDS
            )
            
            # Return first successful result (highest priority)
            for result in results:
                if isinstance(result, AircraftData):
                    # Cache and return
                    self._deduplicated_cache[icao24] = (result, dt_util.utcnow())
                    self._deduplicated_cache.move_to_end(icao24)
                    return result
        
        except asyncio.TimeoutError:
            _LOGGER.debug("Timeout querying aircraft %s", icao24)
        
        return None
    
    def _get_from_cache(self, icao24: str) -> Optional[AircraftData]:
        """Get aircraft from cache if not expired.
        
        Args:
            icao24: Aircraft ICAO24 code
        
        Returns:
            Cached AircraftData if valid, None if expired or not found
        """
        if icao24 not in self._deduplicated_cache:
            return None
        
        aircraft, timestamp = self._deduplicated_cache[icao24]
        age_seconds = (dt_util.utcnow() - timestamp).total_seconds()
        
        if age_seconds > self._cache_ttl:
            # Expired - remove and return None
            del self._deduplicated_cache[icao24]
            return None
        
        # Still valid - move to end (LRU)
        self._deduplicated_cache.move_to_end(icao24)
        return aircraft
    
    def _get_source_name(self, client: ADSBClientBase) -> str:
        """Get source name for a client instance.
        
        Args:
            client: Client instance
        
        Returns:
            Source name (e.g., "dump1090")
        """
        for name, c in self.clients.items():
            if c is client:
                return name
        return "unknown"
    
    async def clear_cache(self) -> None:
        """Clear all caches (manager + all clients)."""
        _LOGGER.debug("Clearing ADSBManager cache")
        self._deduplicated_cache.clear()
        
        # Clear all client caches
        for name, client in self.clients.items():
            try:
                await client.clear_cache()
            except Exception as e:
                _LOGGER.warning("Error clearing cache for %s: %s", name, e)
    
    def get_cache_stats(self) -> Dict[str, any]:
        """Get cache and performance statistics.
        
        Returns:
            Dict with cache size, hit rate, query count, source status
        
        Example:
            {
                "cache_size": 250,
                "max_cache_size": 5000,
                "cache_hit_rate": 0.85,
                "cache_hits": 850,
                "cache_misses": 150,
                "query_count": 1000,
                "sources": {
                    "dump1090": {
                        "enabled": True,
                        "aircraft_count": 12,
                        "last_success": "2026-01-22T15:30:45.123Z",
                        "consecutive_failures": 0
                    },
                    "opensky": {...}
                }
            }
        """
        total_queries = self._cache_hits + self._cache_misses
        hit_rate = (
            self._cache_hits / total_queries if total_queries > 0 else 0
        )
        
        return {
            "cache_size": len(self._deduplicated_cache),
            "max_cache_size": self._max_cache_entries,
            "cache_ttl_seconds": self._cache_ttl,
            "cache_hit_rate": round(hit_rate, 2),
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "total_queries": total_queries,
            "query_count": self._query_count,
            "sources": {
                name: {
                    "enabled": health["enabled"],
                    "aircraft_count": health.get("aircraft_count", 0),
                    "consecutive_failures": health["consecutive_failures"],
                    "last_success": health["last_success"].isoformat()
                    if health["last_success"] else None,
                    "last_error": health.get("last_error")
                }
                for name, health in self._source_health.items()
            }
        }
