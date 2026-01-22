"""Abstract base class for ADS-B data source clients.

This module provides the foundation for all ADS-B data source integrations, defining
a consistent interface and common utility functions for aircraft tracking.

Architecture:
    - ADSBClientBase: Abstract class defining required methods for all clients
    - Common utilities: Distance, bearing, bounding box calculations
    - Cache management: Memory + persistent caching patterns (following OWM approach)
    - Deduplication: Merge aircraft data from multiple sources by unique ID

Data Source Priority System:
    1. dump1090 (local receiver, lowest latency, highest accuracy)
    2. OpenSky Network (free API, ADS-B + FLARM, 4000 credits/day with account)
    3. Open Gliding Network (free APRS, FLARM only, unlimited)
    4. ADS-B Exchange (RapidAPI, paid tiers, 500-1M requests/day)
    5. FlightRadar24 (paid API)
    6. FlightAware (paid API)

Clients must implement:
    - get_aircraft_by_registration()
    - get_aircraft_by_icao24()
    - get_aircraft_near_location()
    - test_connection()

Used By:
    - dump1090Client
    - OpenSkyClient
    - OGNClient
    - ADSBExchangeClient
    - FlightRadar24Client
    - FlightAwareClient
"""

from abc import ABC, abstractmethod
from collections import OrderedDict
from datetime import datetime
from math import atan2, cos, radians, sin, sqrt
from typing import Dict, List, Optional, Tuple

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .adsb_models import AircraftData


class ADSBClientBase(ABC):
    """Abstract base class for ADS-B data source clients.
    
    Provides common functionality for all ADS-B/FLARM data sources including
    caching, distance calculations, and deduplication logic.
    
    Inputs:
        hass: Home Assistant instance for async operations
        config: Client-specific configuration dictionary
        cache_enabled: Enable memory + persistent caching (default: True)
        cache_ttl: Cache time-to-live in seconds (default: 30)
        max_cache_entries: Maximum LRU cache size (default: 1000)
    
    Outputs:
        - AircraftData objects via abstract methods
        - Cache statistics via get_cache_stats()
        - Connection test results via test_connection()
    
    Subclass Implementation:
        Clients must implement all @abstractmethod functions and set self.priority
        to their data source priority (1=highest, 6=lowest typically).
    
    Example:
        class Dump1090Client(ADSBClientBase):
            def __init__(self, hass, config):
                super().__init__(hass, config, priority=1)
            
            async def get_aircraft_near_location(self, lat, lon, radius_nm):
                # Fetch from dump1090 JSON endpoint
                aircraft_list = await self._fetch_from_dump1090()
                return [a for a in aircraft_list if a.distance_to(lat, lon) <= radius_nm]
    """
    
    def __init__(
        self,
        hass: HomeAssistant,
        config: Dict,
        priority: int = 999,
        cache_enabled: bool = True,
        cache_ttl: int = 30,
        max_cache_entries: int = 1000
    ):
        """Initialise ADS-B client base.
        
        Args:
            hass: Home Assistant instance
            config: Client-specific configuration
            priority: Data source priority (1=highest, lower is better)
            cache_enabled: Enable caching
            cache_ttl: Cache TTL in seconds
            max_cache_entries: Max LRU cache size
        """
        self.hass = hass
        self.config = config
        self.priority = priority
        self._cache_enabled = cache_enabled
        self._cache_ttl = cache_ttl
        self._max_cache_entries = max_cache_entries
        
        # Memory cache (LRU eviction)
        self._cache: OrderedDict[str, Tuple[AircraftData, datetime]] = OrderedDict()
    
    @abstractmethod
    async def get_aircraft_by_registration(
        self, registration: str
    ) -> Optional[AircraftData]:
        """Get aircraft data by registration/tail number.
        
        Args:
            registration: Aircraft registration (e.g., "G-ABCD", "N12345")
        
        Returns:
            AircraftData if found, None otherwise
        
        Raises:
            NotImplementedError: If subclass doesn't implement
        """
        raise NotImplementedError("Subclass must implement get_aircraft_by_registration")
    
    @abstractmethod
    async def get_aircraft_by_icao24(self, icao24: str) -> Optional[AircraftData]:
        """Get aircraft data by ICAO 24-bit hex code.
        
        Args:
            icao24: ICAO24 hex code (e.g., "4CA1E3")
        
        Returns:
            AircraftData if found, None otherwise
        
        Raises:
            NotImplementedError: If subclass doesn't implement
        """
        raise NotImplementedError("Subclass must implement get_aircraft_by_icao24")
    
    @abstractmethod
    async def get_aircraft_near_location(
        self, latitude: float, longitude: float, radius_nm: float = 10
    ) -> List[AircraftData]:
        """Get all aircraft within radius of a location.
        
        Args:
            latitude: Centre latitude in decimal degrees
            longitude: Centre longitude in decimal degrees
            radius_nm: Search radius in nautical miles (default: 10)
        
        Returns:
            List of AircraftData within radius, empty list if none
        
        Raises:
            NotImplementedError: If subclass doesn't implement
        """
        raise NotImplementedError("Subclass must implement get_aircraft_near_location")
    
    @abstractmethod
    async def test_connection(self) -> Tuple[bool, Optional[str]]:
        """Test connection to data source.
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
            - (True, None) if connection successful
            - (False, "error message") if connection failed
        
        Raises:
            NotImplementedError: If subclass doesn't implement
        """
        raise NotImplementedError("Subclass must implement test_connection")
    
    # Cache Management Methods
    
    def _get_cached_aircraft(self, cache_key: str) -> Optional[AircraftData]:
        """Get aircraft from cache if still valid.
        
        Args:
            cache_key: Unique cache key (e.g., "icao24:4CA1E3")
        
        Returns:
            AircraftData if cached and fresh, None otherwise
        """
        if not self._cache_enabled or cache_key not in self._cache:
            return None
        
        aircraft, cached_time = self._cache[cache_key]
        age = (dt_util.utcnow() - cached_time).total_seconds()
        
        if age < self._cache_ttl:
            # Move to end (mark as recently used)
            self._cache.move_to_end(cache_key)
            return aircraft
        else:
            # Expired - remove from cache
            del self._cache[cache_key]
            return None
    
    def _cache_aircraft(self, aircraft: AircraftData) -> None:
        """Cache aircraft data with LRU eviction.
        
        Args:
            aircraft: AircraftData to cache
        """
        if not self._cache_enabled:
            return
        
        cache_key = aircraft.get_unique_id()
        self._cache[cache_key] = (aircraft, dt_util.utcnow())
        self._cache.move_to_end(cache_key)
        
        # LRU eviction if over limit
        while len(self._cache) > self._max_cache_entries:
            evicted_key, _ = self._cache.popitem(last=False)
            # Optional: log eviction for debugging
    
    def clear_cache(self) -> None:
        """Clear all cached aircraft data."""
        self._cache.clear()
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics.
        
        Returns:
            Dict with cache size, hit rate, etc.
        """
        return {
            "size": len(self._cache),
            "max_size": self._max_cache_entries,
            "ttl_seconds": self._cache_ttl,
            "enabled": self._cache_enabled,
        }
    
    # Utility Methods
    
    @staticmethod
    def calculate_distance(
        lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Calculate distance between two positions using Haversine formula.
        
        Args:
            lat1: Starting latitude in decimal degrees
            lon1: Starting longitude in decimal degrees
            lat2: Ending latitude in decimal degrees
            lon2: Ending longitude in decimal degrees
        
        Returns:
            float: Distance in nautical miles
        """
        R = 3440.065  # Earth radius in nautical miles
        
        lat1_rad = radians(lat1)
        lon1_rad = radians(lon1)
        lat2_rad = radians(lat2)
        lon2_rad = radians(lon2)
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        
        return R * c
    
    @staticmethod
    def calculate_bearing(
        lat1: float, lon1: float, lat2: float, lon2: float
    ) -> int:
        """Calculate bearing from one position to another.
        
        Args:
            lat1: Starting latitude in decimal degrees
            lon1: Starting longitude in decimal degrees
            lat2: Ending latitude in decimal degrees
            lon2: Ending longitude in decimal degrees
        
        Returns:
            int: Bearing in degrees (0-359)
        """
        lat1_rad = radians(lat1)
        lon1_rad = radians(lon1)
        lat2_rad = radians(lat2)
        lon2_rad = radians(lon2)
        
        dlon = lon2_rad - lon1_rad
        
        y = sin(dlon) * cos(lat2_rad)
        x = cos(lat1_rad) * sin(lat2_rad) - sin(lat1_rad) * cos(lat2_rad) * cos(dlon)
        
        bearing = atan2(y, x)
        bearing_deg = (bearing * 180 / 3.14159 + 360) % 360
        
        return int(bearing_deg)
    
    @staticmethod
    def calculate_bounding_box(
        latitude: float, longitude: float, radius_nm: float
    ) -> Tuple[float, float, float, float]:
        """Calculate bounding box for a radius around a point.
        
        Used to filter aircraft by approximate location before precise distance calc.
        
        Args:
            latitude: Centre latitude in decimal degrees
            longitude: Centre longitude in decimal degrees
            radius_nm: Radius in nautical miles
        
        Returns:
            Tuple of (min_lat, max_lat, min_lon, max_lon)
        """
        # Approximate: 1 nautical mile ≈ 1 minute of latitude ≈ 1/60 degree
        lat_delta = radius_nm / 60.0
        
        # Longitude degrees per nautical mile varies with latitude
        # At equator: 1nm ≈ 1/60 deg, at poles: much larger
        lon_delta = radius_nm / (60.0 * cos(radians(latitude)))
        
        min_lat = latitude - lat_delta
        max_lat = latitude + lat_delta
        min_lon = longitude - lon_delta
        max_lon = longitude + lon_delta
        
        return (min_lat, max_lat, min_lon, max_lon)
    
    @staticmethod
    def deduplicate_aircraft(
        aircraft_list: List[AircraftData]
    ) -> List[AircraftData]:
        """Deduplicate aircraft list by unique ID, keeping highest priority.
        
        When multiple data sources report the same aircraft, keep the data from
        the highest-priority source (lowest priority number). Merge non-conflicting
        fields from lower-priority sources.
        
        Args:
            aircraft_list: List of AircraftData from multiple sources
        
        Returns:
            List of deduplicated AircraftData with merged fields
        """
        # Group by unique ID
        aircraft_by_id: Dict[str, List[AircraftData]] = {}
        for aircraft in aircraft_list:
            unique_id = aircraft.get_unique_id()
            if unique_id not in aircraft_by_id:
                aircraft_by_id[unique_id] = []
            aircraft_by_id[unique_id].append(aircraft)
        
        # For each unique aircraft, merge data from all sources
        deduplicated = []
        for unique_id, aircraft_variants in aircraft_by_id.items():
            if len(aircraft_variants) == 1:
                # Only one source - use as-is
                deduplicated.append(aircraft_variants[0])
            else:
                # Multiple sources - merge by priority
                # Sort by priority (ascending - lower number = higher priority)
                sorted_variants = sorted(aircraft_variants, key=lambda a: a.priority)
                
                # Start with highest priority source
                merged = sorted_variants[0]
                
                # Merge in lower-priority sources
                for variant in sorted_variants[1:]:
                    merged = merged.merge_with(variant)
                
                deduplicated.append(merged)
        
        return deduplicated
    
    @staticmethod
    def filter_aircraft_by_distance(
        aircraft_list: List[AircraftData],
        latitude: float,
        longitude: float,
        max_distance_nm: float
    ) -> List[AircraftData]:
        """Filter aircraft list to only those within max distance.
        
        Args:
            aircraft_list: List of AircraftData to filter
            latitude: Centre latitude
            longitude: Centre longitude
            max_distance_nm: Maximum distance in nautical miles
        
        Returns:
            List of AircraftData within distance, sorted by distance (nearest first)
        """
        filtered = []
        for aircraft in aircraft_list:
            if aircraft.latitude is None or aircraft.longitude is None:
                continue
            
            distance = aircraft.distance_to(latitude, longitude)
            if distance is not None and distance <= max_distance_nm:
                filtered.append((distance, aircraft))
        
        # Sort by distance (nearest first)
        filtered.sort(key=lambda x: x[0])
        
        return [aircraft for _, aircraft in filtered]
