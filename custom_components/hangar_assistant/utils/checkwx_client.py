"""CheckWX API Client for aviation weather data.

This module provides a client for the CheckWX Aviation Weather API, which offers
METAR, TAF, and station information with a generous free tier (3,000 requests/day).

Features:
    - METAR/TAF decoded JSON data retrieval
    - Station information lookup with auto-population
    - Multi-level caching (memory + persistent file-based)
    - Rate limit tracking and protection
    - Graceful degradation (uses stale cache on API failure)
    - Survives Home Assistant restarts

Rate Limits:
    - Free tier: 3,000 requests/day (resets 00:00 UTC)
    - Warning threshold: 2,700 requests (90%)
    - Recommended cache TTL: 15 min for METAR, 6 hours for TAF

API Documentation:
    https://www.checkwxapi.com/documentation
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False

_LOGGER = logging.getLogger(__name__)

# API Constants
BASE_URL = "https://api.checkwx.com"
DEFAULT_TIMEOUT = 30  # seconds
DEFAULT_METAR_CACHE_MINUTES = 15
DEFAULT_TAF_CACHE_MINUTES = 360  # 6 hours
DEFAULT_STATION_CACHE_MINUTES = 10080  # 7 days
MAX_MEMORY_CACHE_ENTRIES = 100
RATE_LIMIT_FREE_TIER = 3000
RATE_LIMIT_WARNING_THRESHOLD = 2700


class CheckWXClient:
    """Client for CheckWX Aviation Weather API.
    
    This client provides access to official aviation weather data including METAR
    observations, TAF forecasts, and station information. It implements aggressive
    caching to protect against rate limits and ensure reliable operation.
    
    Features:
        - Multi-level caching (memory + persistent)
        - Rate limit tracking and warnings
        - Graceful degradation to stale cache on errors
        - Async file operations for non-blocking I/O
    
    Example:
        ```python
        client = CheckWXClient(api_key, hass, cache_enabled=True)
        metar = await client.get_metar("KJFK", decoded=True)
        taf = await client.get_taf("KJFK", decoded=True)
        station = await client.get_station_info("KJFK")
        ```
    
    Args:
        api_key: CheckWX API key (32+ characters)
        hass: Home Assistant instance for file operations
        cache_enabled: Enable persistent file-based caching
        metar_cache_minutes: Cache TTL for METAR data
        taf_cache_minutes: Cache TTL for TAF data
        station_cache_minutes: Cache TTL for station data
    """
    
    def __init__(
        self,
        api_key: str,
        hass: HomeAssistant,
        cache_enabled: bool = True,
        metar_cache_minutes: int = DEFAULT_METAR_CACHE_MINUTES,
        taf_cache_minutes: int = DEFAULT_TAF_CACHE_MINUTES,
        station_cache_minutes: int = DEFAULT_STATION_CACHE_MINUTES,
    ):
        """Initialize CheckWX API client."""
        self._api_key = api_key
        self._hass = hass
        self._cache_enabled = cache_enabled
        self._metar_cache_ttl = timedelta(minutes=metar_cache_minutes)
        self._taf_cache_ttl = timedelta(minutes=taf_cache_minutes)
        self._station_cache_ttl = timedelta(minutes=station_cache_minutes)
        
        # Memory cache (session-level, LRU eviction)
        self._memory_cache: OrderedDict[str, Tuple[Any, datetime]] = OrderedDict()
        self._max_memory_entries = MAX_MEMORY_CACHE_ENTRIES
        
        # Rate limit tracking
        self._daily_requests = 0
        self._last_reset = dt_util.utcnow().date()
        self._rate_limit_warned = False
        
        # Persistent cache directory
        self._cache_dir = Path(hass.config.path("hangar_assistant_cache", "checkwx"))
        
        # Failure tracking for graceful degradation
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3
        
        _LOGGER.debug("CheckWX client initialized (cache: %s)", cache_enabled)
    
    async def get_metar(
        self,
        icao: str,
        decoded: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Fetch METAR observation for ICAO airport code.
        
        METAR (Meteorological Aerodrome Report) provides current weather observations
        at airports, updated hourly or more frequently when conditions change.
        
        Args:
            icao: 4-letter ICAO airport code (e.g., "KJFK", "EGHP")
            decoded: Return decoded JSON data (True) or raw text (False)
        
        Returns:
            Decoded METAR dictionary with current weather data:
                {
                    "icao": "KJFK",
                    "temperature": {"celsius": 0, "fahrenheit": 32},
                    "dewpoint": {"celsius": -7, "fahrenheit": 19},
                    "wind": {"degrees": 190, "speed_kts": 18, "gust_kts": 31},
                    "barometer": {"hpa": 1028.0, "hg": 30.35},
                    "visibility": {"miles": 10.0, "meters": 16093},
                    "clouds": [{"code": "FEW", "base_feet_agl": 3600, "text": "Few"}],
                    "flight_category": "VFR",
                    "humidity": {"percent": 60},
                    "observed": "2026-01-21T19:51:00Z",
                    "raw_text": "METAR KJFK 211951Z ...",
                }
            Returns None if API fails and no cache available
        
        Raises:
            ValueError: If ICAO code is invalid (not 4 letters)
        """
        if not icao or len(icao) != 4:
            raise ValueError(f"Invalid ICAO code: {icao} (must be 4 letters)")
        
        icao = icao.upper()
        endpoint = f"/metar/{icao}/decoded" if decoded else f"/metar/{icao}"
        cache_key = f"metar_{icao}_{'decoded' if decoded else 'raw'}"
        
        return await self._make_request(endpoint, cache_key, self._metar_cache_ttl)
    
    async def get_taf(
        self,
        icao: str,
        decoded: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Fetch TAF (Terminal Aerodrome Forecast) for ICAO airport code.
        
        TAF provides aviation weather forecasts for airports, typically covering
        9-30 hours with change indicators (FM, BECMG, TEMPO, PROB).
        
        Args:
            icao: 4-letter ICAO airport code
            decoded: Return decoded JSON data (True) or raw text (False)
        
        Returns:
            Decoded TAF dictionary with forecast periods:
                {
                    "icao": "KJFK",
                    "timestamp": {
                        "issued": "2026-01-21T17:22:00Z",
                        "from": "2026-01-21T18:00:00Z",
                        "to": "2026-01-23T00:00:00Z"
                    },
                    "forecast": [
                        {
                            "timestamp": {"from": "...", "to": "..."},
                            "wind": {"degrees": 210, "speed_kts": 11},
                            "visibility": {"miles": 10.0},
                            "clouds": [...]
                        },
                        ...
                    ],
                    "raw_text": "TAF KJFK 211722Z ...",
                }
            Returns None if API fails and no cache available
        
        Raises:
            ValueError: If ICAO code is invalid
        """
        if not icao or len(icao) != 4:
            raise ValueError(f"Invalid ICAO code: {icao} (must be 4 letters)")
        
        icao = icao.upper()
        endpoint = f"/taf/{icao}/decoded" if decoded else f"/taf/{icao}"
        cache_key = f"taf_{icao}_{'decoded' if decoded else 'raw'}"
        
        return await self._make_request(endpoint, cache_key, self._taf_cache_ttl)
    
    async def get_station_info(self, icao: str) -> Optional[Dict[str, Any]]:
        """Fetch station/airport information for ICAO code.
        
        Station info includes location, elevation, coordinates, and airport type.
        This data changes rarely, so it's cached for 7 days by default.
        
        Args:
            icao: 4-letter ICAO airport code
        
        Returns:
            Station information dictionary:
                {
                    "icao": "KJFK",
                    "iata": "JFK",
                    "name": "John F Kennedy International Airport",
                    "city": "New York",
                    "country": {"code": "US", "name": "United States"},
                    "elevation": {"feet": 13.0, "meters": 4.0},
                    "latitude": {"decimal": 40.639},
                    "longitude": {"decimal": -73.779},
                    "type": "Airport",
                    "geometry": {"type": "Point", "coordinates": [-73.779, 40.639]}
                }
            Returns None if API fails and no cache available
        
        Raises:
            ValueError: If ICAO code is invalid
        """
        if not icao or len(icao) != 4:
            raise ValueError(f"Invalid ICAO code: {icao} (must be 4 letters)")
        
        icao = icao.upper()
        endpoint = f"/station/{icao}"
        cache_key = f"station_{icao}"
        
        return await self._make_request(endpoint, cache_key, self._station_cache_ttl)
    
    async def get_sunrise_sunset(self, icao: str) -> Optional[Dict[str, Any]]:
        """Fetch sunrise/sunset times for ICAO airport code.
        
        Provides dawn, sunrise, sunset, dusk times in local and UTC timezones.
        
        Args:
            icao: 4-letter ICAO airport code
        
        Returns:
            Sunrise/sunset dictionary:
                {
                    "local": {
                        "sunrise": "07:15:00",
                        "sunset": "16:45:00",
                        "dawn": "06:42:00",
                        "dusk": "17:18:00"
                    },
                    "utc": {...},
                    "timezone": {"tzid": "America/New_York", ...}
                }
            Returns None if API fails and no cache available
        
        Raises:
            ValueError: If ICAO code is invalid
        """
        if not icao or len(icao) != 4:
            raise ValueError(f"Invalid ICAO code: {icao} (must be 4 letters)")
        
        icao = icao.upper()
        endpoint = f"/station/{icao}/suntimes"
        cache_key = f"suntimes_{icao}"
        
        # Sun times change daily, cache for 12 hours
        cache_ttl = timedelta(hours=12)
        return await self._make_request(endpoint, cache_key, cache_ttl)
    
    async def _make_request(
        self,
        endpoint: str,
        cache_key: str,
        cache_ttl: timedelta
    ) -> Optional[Dict[str, Any]]:
        """Make API request with caching and rate limit protection.
        
        Implements the complete caching hierarchy:
        1. Check memory cache (fast, session-level)
        2. Check persistent cache (survives restarts)
        3. Make API call (if not rate limited)
        4. Update both caches
        5. On failure, use stale cache if available
        
        Args:
            endpoint: API endpoint path (e.g., "/metar/KJFK/decoded")
            cache_key: Unique cache identifier
            cache_ttl: How long cache remains valid
        
        Returns:
            API response data or cached data, None if all sources fail
        """
        # 1. Check memory cache
        cached = self._get_memory_cache(cache_key, cache_ttl)
        if cached is not None:
            _LOGGER.debug("CheckWX: Memory cache hit for %s", cache_key)
            return cached
        
        # 2. Check persistent cache
        if self._cache_enabled:
            cached = await self._get_persistent_cache(cache_key, cache_ttl)
            if cached is not None:
                _LOGGER.debug("CheckWX: Persistent cache hit for %s", cache_key)
                # Populate memory cache
                self._set_memory_cache(cache_key, cached)
                return cached
        
        # 3. Check rate limit before API call
        if not self._check_rate_limit():
            _LOGGER.warning("CheckWX: Rate limit reached, using stale cache if available")
            return await self._get_stale_cache(cache_key)
        
        # 4. Make API call
        try:
            data = await self._api_call(endpoint)
            
            if data is not None:
                # Success - reset failure counter
                self._consecutive_failures = 0
                
                # Update both caches
                self._set_memory_cache(cache_key, data)
                if self._cache_enabled:
                    await self._set_persistent_cache(cache_key, data)
                
                return data
            else:
                # API returned no data
                self._consecutive_failures += 1
                return await self._get_stale_cache(cache_key)
        
        except Exception as e:
            self._consecutive_failures += 1
            _LOGGER.error(
                "CheckWX API error (%d consecutive failures): %s",
                self._consecutive_failures,
                e
            )
            return await self._get_stale_cache(cache_key)
    
    async def _api_call(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """Execute HTTP request to CheckWX API.
        
        Args:
            endpoint: API endpoint path
        
        Returns:
            Parsed JSON response data or None on failure
        """
        url = f"{BASE_URL}{endpoint}"
        headers = {"X-API-Key": self._api_key}
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)) as session:
                async with session.get(url, headers=headers) as response:
                    # Track request count
                    self._daily_requests += 1
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        # CheckWX wraps data in {"results": n, "data": [...]}
                        if data.get("results", 0) > 0 and "data" in data:
                            # Return first result (single ICAO queries return 1 result)
                            return data["data"][0] if data["data"] else None
                        else:
                            _LOGGER.warning("CheckWX: No results for %s", endpoint)
                            return None
                    
                    elif response.status == 401:
                        _LOGGER.error("CheckWX: Invalid API key (401 Unauthorized)")
                        return None
                    
                    elif response.status == 404:
                        _LOGGER.warning("CheckWX: Resource not found (404) - %s", endpoint)
                        return None
                    
                    elif response.status == 429:
                        _LOGGER.error("CheckWX: Rate limit exceeded (429)")
                        return None
                    
                    else:
                        _LOGGER.error(
                            "CheckWX: API error %d for %s",
                            response.status,
                            endpoint
                        )
                        return None
        
        except asyncio.TimeoutError:
            _LOGGER.error("CheckWX: Request timeout for %s", endpoint)
            return None
        
        except aiohttp.ClientError as e:
            _LOGGER.error("CheckWX: Network error for %s: %s", endpoint, e)
            return None
    
    def _check_rate_limit(self) -> bool:
        """Check if rate limit allows more requests.
        
        Resets counter at 00:00 UTC daily. Warns at 90% of free tier limit.
        
        Returns:
            True if request can proceed, False if rate limit reached
        """
        # Reset counter at 00:00 UTC
        today = dt_util.utcnow().date()
        if today > self._last_reset:
            _LOGGER.info(
                "CheckWX: Daily rate limit reset (%d requests used yesterday)",
                self._daily_requests
            )
            self._daily_requests = 0
            self._last_reset = today
            self._rate_limit_warned = False
        
        # Warn at 90% of free tier limit (2,700/3,000)
        if self._daily_requests >= RATE_LIMIT_WARNING_THRESHOLD and not self._rate_limit_warned:
            _LOGGER.warning(
                "CheckWX: Approaching rate limit (%d/%d requests today). "
                "Consider upgrading or increasing cache TTL.",
                self._daily_requests,
                RATE_LIMIT_FREE_TIER
            )
            self._rate_limit_warned = True
        
        # Block at limit
        if self._daily_requests >= RATE_LIMIT_FREE_TIER:
            _LOGGER.error(
                "CheckWX: Daily rate limit reached (%d/%d). "
                "Using cached data until 00:00 UTC reset.",
                self._daily_requests,
                RATE_LIMIT_FREE_TIER
            )
            return False
        
        return True
    
    def _get_memory_cache(
        self,
        cache_key: str,
        cache_ttl: timedelta
    ) -> Optional[Dict[str, Any]]:
        """Retrieve data from memory cache if valid.
        
        Args:
            cache_key: Cache identifier
            cache_ttl: Maximum age for valid cache
        
        Returns:
            Cached data if valid, None otherwise
        """
        if cache_key in self._memory_cache:
            data, timestamp = self._memory_cache[cache_key]
            age = dt_util.utcnow() - timestamp
            
            if age < cache_ttl:
                # Valid cache - move to end for LRU
                self._memory_cache.move_to_end(cache_key)
                return data
        
        return None
    
    def _set_memory_cache(self, cache_key: str, data: Dict[str, Any]) -> None:
        """Store data in memory cache with LRU eviction.
        
        Args:
            cache_key: Cache identifier
            data: Data to cache
        """
        timestamp = dt_util.utcnow()
        self._memory_cache[cache_key] = (data, timestamp)
        self._memory_cache.move_to_end(cache_key)
        
        # Evict oldest entries if over limit
        while len(self._memory_cache) > self._max_memory_entries:
            evicted_key, _ = self._memory_cache.popitem(last=False)
            _LOGGER.debug("CheckWX: Evicted memory cache entry: %s", evicted_key)
    
    async def _get_persistent_cache(
        self,
        cache_key: str,
        cache_ttl: timedelta
    ) -> Optional[Dict[str, Any]]:
        """Retrieve data from persistent file cache if valid.
        
        Args:
            cache_key: Cache identifier
            cache_ttl: Maximum age for valid cache
        
        Returns:
            Cached data if valid, None otherwise
        """
        cache_file = self._cache_dir / f"{cache_key}.json"
        
        def _read_cache():
            """Read cache file (blocking I/O)."""
            try:
                if not cache_file.exists():
                    return None
                
                with open(cache_file, 'rb') as f:
                    if HAS_ORJSON:
                        cached = orjson.loads(f.read())
                    else:
                        cached = json.load(f)
                
                timestamp_str = cached.get("_cache_timestamp")
                if not timestamp_str:
                    return None
                
                timestamp = datetime.fromisoformat(timestamp_str)
                age = dt_util.utcnow() - timestamp
                
                if age < cache_ttl:
                    return cached.get("data")
                
                return None
            
            except (OSError, json.JSONDecodeError, ValueError) as e:
                _LOGGER.debug("CheckWX: Cache read error for %s: %s", cache_key, e)
                return None
        
        # Run blocking I/O in executor
        return await self._hass.async_add_executor_job(_read_cache)
    
    async def _set_persistent_cache(
        self,
        cache_key: str,
        data: Dict[str, Any]
    ) -> None:
        """Store data in persistent file cache.
        
        Args:
            cache_key: Cache identifier
            data: Data to cache
        """
        def _write_cache():
            """Write cache file (blocking I/O)."""
            try:
                # Create cache directory if needed
                self._cache_dir.mkdir(parents=True, exist_ok=True)
                
                cache_file = self._cache_dir / f"{cache_key}.json"
                
                cached = {
                    "_cache_timestamp": dt_util.utcnow().isoformat(),
                    "data": data
                }
                
                with open(cache_file, 'wb') as f:
                    if HAS_ORJSON:
                        f.write(orjson.dumps(cached))
                    else:
                        json_str = json.dumps(cached)
                        f.write(json_str.encode('utf-8'))
            
            except OSError as e:
                _LOGGER.error("CheckWX: Cache write error for %s: %s", cache_key, e)
        
        # Run blocking I/O in executor
        await self._hass.async_add_executor_job(_write_cache)
    
    async def _get_stale_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve stale cache as fallback (ignores TTL).
        
        Used when API fails or rate limit reached. Stale data is better than no data.
        
        Args:
            cache_key: Cache identifier
        
        Returns:
            Cached data regardless of age, None if no cache exists
        """
        # Check memory cache (any age)
        if cache_key in self._memory_cache:
            data, _ = self._memory_cache[cache_key]
            _LOGGER.info("CheckWX: Using stale memory cache for %s", cache_key)
            return data
        
        # Check persistent cache (any age)
        if self._cache_enabled:
            cache_file = self._cache_dir / f"{cache_key}.json"
            
            def _read_stale():
                try:
                    if not cache_file.exists():
                        return None
                    
                    with open(cache_file, 'rb') as f:
                        if HAS_ORJSON:
                            cached = orjson.loads(f.read())
                        else:
                            cached = json.load(f)
                    
                    return cached.get("data")
                
                except (OSError, json.JSONDecodeError) as e:
                    _LOGGER.debug("CheckWX: Stale cache read error: %s", e)
                    return None
            
            data = await self._hass.async_add_executor_job(_read_stale)
            if data:
                _LOGGER.info("CheckWX: Using stale persistent cache for %s", cache_key)
                return data
        
        _LOGGER.warning("CheckWX: No cache available for %s", cache_key)
        return None
    
    async def clear_cache(self, icao: Optional[str] = None) -> None:
        """Clear cache for specific ICAO or all cached data.
        
        Args:
            icao: Clear only this ICAO code, or None to clear all
        """
        if icao:
            icao = icao.upper()
            # Clear memory cache
            keys_to_remove = [k for k in self._memory_cache.keys() if icao in k]
            for key in keys_to_remove:
                del self._memory_cache[key]
            
            # Clear persistent cache
            if self._cache_enabled:
                def _remove_files():
                    if self._cache_dir.exists():
                        for file in self._cache_dir.glob(f"*{icao}*.json"):
                            try:
                                file.unlink()
                            except OSError as e:
                                _LOGGER.error("Error deleting cache file: %s", e)
                
                await self._hass.async_add_executor_job(_remove_files)
            
            _LOGGER.info("CheckWX: Cleared cache for %s", icao)
        else:
            # Clear all memory cache
            self._memory_cache.clear()
            
            # Clear all persistent cache
            if self._cache_enabled:
                def _remove_all():
                    if self._cache_dir.exists():
                        for file in self._cache_dir.glob("*.json"):
                            try:
                                file.unlink()
                            except OSError as e:
                                _LOGGER.error("Error deleting cache file: %s", e)
                
                await self._hass.async_add_executor_job(_remove_all)
            
            _LOGGER.info("CheckWX: Cleared all cache")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics and rate limit information.
        
        Returns:
            Dictionary with cache and rate limit stats:
                {
                    "memory_cache_entries": 15,
                    "persistent_cache_enabled": True,
                    "daily_requests": 142,
                    "rate_limit": 3000,
                    "remaining_requests": 2858,
                    "consecutive_failures": 0
                }
        """
        return {
            "memory_cache_entries": len(self._memory_cache),
            "memory_cache_max": self._max_memory_entries,
            "persistent_cache_enabled": self._cache_enabled,
            "cache_directory": str(self._cache_dir),
            "daily_requests": self._daily_requests,
            "rate_limit": RATE_LIMIT_FREE_TIER,
            "remaining_requests": max(0, RATE_LIMIT_FREE_TIER - self._daily_requests),
            "last_reset": self._last_reset.isoformat(),
            "consecutive_failures": self._consecutive_failures,
            "rate_limit_warning_issued": self._rate_limit_warned,
        }
