"""OpenWeatherMap API integration for Hangar Assistant.

Provides professional weather data including:
- Current conditions
- 48-hour hourly forecast
- 8-day daily forecast
- Minutely precipitation forecast
- Government weather alerts

Features robust caching to protect against API rate limits,
especially during system restarts.
"""
from typing import Optional, Dict, Any
import asyncio
import json
import logging
import re
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .http_proxy import HttpClientProxy, HttpRequestOptions, PersistentFileCache

# Try to import orjson for 2-5x faster JSON operations
try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False

# Optional import for notifications (may not be available in test env)
try:
    from homeassistant.components.persistent_notification import async_create as _async_create_notification
    HAS_NOTIFICATIONS = True
except (ImportError, ModuleNotFoundError):
    HAS_NOTIFICATIONS = False
    _async_create_notification = None

_LOGGER = logging.getLogger(__name__)

OWM_API_BASE = "https://api.openweathermap.org/data/3.0/onecall"
DEFAULT_CACHE_TTL_MINUTES = 10  # OWM updates every 10 minutes
DEFAULT_TIMEOUT_SECONDS = 10


class OpenWeatherMapClient:
    """Client for OpenWeatherMap One Call API 3.0.

    Implements persistent caching to protect against API rate limit breaches,
    especially important during system restarts or configuration changes.

    Inputs:
        - api_key: OWM API key
        - hass: Home Assistant instance (for config path)
        - cache_enabled: Enable/disable persistent caching (default: True)
        - cache_ttl_minutes: Cache time-to-live (default: 10 minutes)

    Outputs:
        - Weather data dict with current conditions, forecasts, alerts

    Used by:
        - Sensor entities for weather data
        - Binary sensors for alerts
        - AI briefing service

    Example:
        client = OpenWeatherMapClient(api_key, hass, cache_enabled=True)
        data = await client.get_weather_data(51.2, -1.2)
    """

    def __init__(
        self,
        api_key: str,
        hass,
        cache_enabled: bool = True,
        cache_ttl_minutes: int = DEFAULT_CACHE_TTL_MINUTES,
        config_entry: Any = None,
    ):
        """Initialize OWM client with caching configuration.

        Args:
            api_key: OpenWeatherMap API key
            hass: Home Assistant instance
            cache_enabled: Enable persistent file-based caching
            cache_ttl_minutes: Cache lifetime in minutes
            config_entry: Config entry for failure tracking (optional)
        """
        self.api_key = api_key
        self.hass = hass
        self.cache_enabled = cache_enabled
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self.entry = config_entry

        # Persistent cache directory (survives restarts)
        # Note: Directory creation is lazy - only created when needed
        config_path = getattr(getattr(hass, "config", None), "path", None)
        if callable(config_path):
            self.cache_dir = Path(config_path("hangar_assistant_cache"))
        else:
            self.cache_dir = Path("/tmp/hangar_assistant_cache")
        self._cache_dir_initialized = False

        # In-memory cache for current session (LRU eviction for memory safety)
        self._memory_cache: OrderedDict[str, tuple[Dict[str, Any], datetime]] = OrderedDict()
        self._max_memory_entries = 1000  # Prevent unbounded growth

        # API call tracking (resets daily)
        self._api_calls_today = 0
        self._api_calls_date = datetime.now().date()

        # Initialize HTTP proxy with persistent caching for OWM data
        # OWM updates every 10 minutes, so cache is valid for 10 minutes
        persistent_cache = PersistentFileCache(
            cache_file=self.cache_dir / "openweathermap.json"
        )
        self.http_proxy = HttpClientProxy(
            hass=hass,
            cache=persistent_cache
        )

        _LOGGER.info(
            "OWM client initialized (cache: %s, TTL: %d min)",
            "enabled" if cache_enabled else "disabled",
            cache_ttl_minutes,
        )

    async def _increment_failure_counter(self, error_message: str) -> None:
        """Increment consecutive failure counter and update last_error.

        Args:
            error_message: Error message to store
        """
        if not self.entry:
            return

        new_data = dict(self.entry.data)
        integrations = new_data.get("integrations", {})
        owm_config = integrations.get("openweathermap", {})

        consecutive_failures = owm_config.get("consecutive_failures", 0) + 1
        owm_config["consecutive_failures"] = consecutive_failures
        owm_config["last_error"] = error_message

        integrations["openweathermap"] = owm_config
        new_data["integrations"] = integrations

        self.hass.config_entries.async_update_entry(self.entry, data=new_data)

        _LOGGER.warning(
            "OWM failure #%d: %s",
            consecutive_failures,
            error_message
        )

        # Auto-disable after 3 consecutive failures
        if consecutive_failures >= 3:
            await self._auto_disable_integration()

    async def _reset_failure_counter(self) -> None:
        """Reset consecutive failure counter on successful fetch."""
        if not self.entry:
            return

        new_data = dict(self.entry.data)
        integrations = new_data.get("integrations", {})
        owm_config = integrations.get("openweathermap", {})

        # Update failure counter and last_success timestamp
        had_failures = owm_config.get("consecutive_failures", 0) > 0
        owm_config["consecutive_failures"] = 0
        owm_config["last_success"] = datetime.now(timezone.utc).isoformat()

        integrations["openweathermap"] = owm_config
        new_data["integrations"] = integrations

        self.hass.config_entries.async_update_entry(self.entry, data=new_data)

        if had_failures:
            _LOGGER.info("OWM connection restored, failure counter reset")

    async def _auto_disable_integration(self) -> None:
        """Auto-disable OWM integration after 3 consecutive failures."""
        if not self.entry:
            return

        new_data = dict(self.entry.data)
        integrations = new_data.get("integrations", {})
        owm_config = integrations.get("openweathermap", {})

        # Check if already disabled
        if not owm_config.get("enabled", False):
            return

        owm_config["enabled"] = False
        integrations["openweathermap"] = owm_config
        new_data["integrations"] = integrations

        self.hass.config_entries.async_update_entry(self.entry, data=new_data)

        _LOGGER.error(
            "OpenWeatherMap integration auto-disabled after 3 consecutive failures. "
            "Check your API key and re-enable in Settings → Integrations."
        )

        # Create persistent notification via service call
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "Hangar Assistant: OpenWeatherMap Disabled",
                "message": (
                    "OpenWeatherMap has been disabled after 3 consecutive failures. "
                    "Please check your API key and re-enable in Settings → Devices & Services → "
                    "Hangar Assistant → Configure."
                ),
                "notification_id": "hangar_assistant_owm_disabled"
            }
        )

    def _ensure_cache_dir(self) -> None:
        """Ensure cache directory exists (lazy initialization)."""
        if not self._cache_dir_initialized and self.cache_enabled:
            try:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                self._cache_dir_initialized = True
            except (OSError, PermissionError) as e:
                _LOGGER.error(
                    "Failed to create OWM cache directory: %s. "
                    "Caching will be disabled. Check permissions for: %s",
                    e, self.cache_dir
                )
                # Disable caching if we can't create directory
                self.cache_enabled = False
                
                # Notify user about permission issue (if available)
                if HAS_NOTIFICATIONS and _async_create_notification:
                    self.hass.async_create_task(
                        _async_create_notification(
                            self.hass,
                            message=(
                                f"Hangar Assistant cannot create weather cache directory. "
                                f"Caching will be disabled. Please check permissions for: {self.cache_dir}"
                            ),
                            title="Hangar Assistant: Cache Permission Error",
                            notification_id="hangar_owm_cache_permission_error"
                        )
                    )

    def _get_cache_file_path(self, latitude: float, longitude: float) -> Path:
        """Get cache file path for coordinates.

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate

        Returns:
            Path to cache file
        """
        # Sanitize coordinates for filename (remove any non-numeric characters except decimal and minus)
        lat_str = re.sub(r'[^0-9.-]', '', f"{latitude:.4f}")
        lon_str = re.sub(r'[^0-9.-]', '', f"{longitude:.4f}")
        
        cache_key = f"owm_{lat_str}_{lon_str}.json"
        return self.cache_dir / cache_key

    def _read_persistent_cache(
        self, latitude: float, longitude: float
    ) -> Optional[Dict[str, Any]]:
        """Read cached data from disk if valid.

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate

        Returns:
            Cached data dict if valid, None otherwise
        """
        if not self.cache_enabled:
            return None

        self._ensure_cache_dir()

        cache_file = self._get_cache_file_path(latitude, longitude)

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r") as f:
                cached = orjson.loads(f.read()) if HAS_ORJSON else json.load(f)

            # Check if cache is still valid
            cached_time = datetime.fromisoformat(cached["cached_at"])
            cache_age = datetime.now() - cached_time

            if cache_age < self.cache_ttl:
                _LOGGER.debug(
                    "Using persistent cache (age: %d seconds)",
                    cache_age.total_seconds()
                )
                return cached["data"]
            else:
                _LOGGER.debug(
                    "Persistent cache expired (age: %d seconds)",
                    cache_age.total_seconds()
                )
                return None

        except (json.JSONDecodeError, KeyError, ValueError, OSError) as e:
            _LOGGER.warning("Failed to read cache file: %s", e)
            return None

    def _read_persistent_cache_stale(
        self, latitude: float, longitude: float
    ) -> Optional[Dict[str, Any]]:
        """Read cached data from disk even if expired (graceful degradation).

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate

        Returns:
            Cached data dict if exists, None otherwise (ignoring TTL)
        """
        if not self.cache_enabled:
            return None

        self._ensure_cache_dir()

        cache_file = self._get_cache_file_path(latitude, longitude)

        if not cache_file.exists():
            return None

        try:
            # Use orjson if available (2-5x faster)
            if HAS_ORJSON:
                cache_bytes = cache_file.read_bytes()
                cached = orjson.loads(cache_bytes)
            else:
                with open(cache_file, "r") as f:
                    cached = json.load(f)

            # Return data regardless of age (stale cache for graceful degradation)
            _LOGGER.debug("Using stale persistent cache for graceful degradation")
            return cached["data"]

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            _LOGGER.warning("Failed to read stale cache file: %s", e)
            return None

    def _write_persistent_cache(
        self, latitude: float, longitude: float, data: Dict[str, Any]
    ) -> None:
        """Write data to persistent cache.

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            data: Weather data to cache
        """
        if not self.cache_enabled:
            return

        self._ensure_cache_dir()

        cache_file = self._get_cache_file_path(latitude, longitude)

        try:
            cached = {
                "cached_at": datetime.now().isoformat(),
                "coordinates": {"lat": latitude, "lon": longitude},
                "data": data,
            }

            with open(cache_file, "w") as f:
                if HAS_ORJSON:
                    f.write(orjson.dumps(cached, option=orjson.OPT_INDENT_2).decode("utf-8"))
                else:
                    json.dump(cached, f, indent=2)

            _LOGGER.debug("Wrote persistent cache to %s", cache_file.name)

        except (OSError, TypeError) as e:
            _LOGGER.error("Failed to write cache file: %s", e)

    async def get_weather_data(
        self,
        latitude: float,
        longitude: float,
        units: str = "metric",
    ) -> Optional[Dict[str, Any]]:
        """Fetch current weather and forecast data with multi-level caching.

        Caching strategy (in order of priority):
        1. In-memory cache (fastest, session only)
        2. Persistent file cache (survives restarts)
        3. API call (only if cache invalid)

        This protects against rate limit breaches during:
        - Multiple system restarts
        - Configuration changes
        - Integration reloads

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            units: Unit system (metric, imperial, standard)

        Returns:
            Weather data dict or None if error
        """
        cache_key = f"{latitude}_{longitude}"

        # 1. Check in-memory cache first (fastest)
        if cache_key in self._memory_cache:
            cached_data, cached_time = self._memory_cache[cache_key]
            cache_age = datetime.now() - cached_time

            if cache_age < self.cache_ttl:
                # Move to end to mark as recently used (LRU)
                self._memory_cache.move_to_end(cache_key)
                _LOGGER.debug(
                    "Using memory cache for %s (age: %d seconds)",
                    cache_key,
                    cache_age.total_seconds(),
                )
                return cached_data

        # 2. Check persistent cache (survives restarts)
        persistent_data = await self.hass.async_add_executor_job(
            self._read_persistent_cache, latitude, longitude
        )
        if persistent_data:
            # Update memory cache with persistent data
            self._memory_cache[cache_key] = (persistent_data, datetime.now())
            return persistent_data

        # 3. Fetch from API (cache miss)
        try:
            data = await self._fetch_from_api(latitude, longitude, units)
            if data:
                # Reset failure counter on successful fetch
                await self._reset_failure_counter()
                return data
        except Exception as e:
            _LOGGER.error("OWM API fetch failed: %s", e)
            await self._increment_failure_counter(str(e))
        
        # 4. Return stale cache as last resort if API fails
        stale_data = await self.hass.async_add_executor_job(
            self._read_persistent_cache_stale, latitude, longitude
        )
        if stale_data:
            _LOGGER.warning("Using stale OWM cache due to API failure")
            return stale_data
        
        return None

    async def _fetch_from_api(
        self,
        latitude: float,
        longitude: float,
        units: str = "metric",
    ) -> Optional[Dict[str, Any]]:
        """Fetch data from OWM API.

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            units: Unit system

        Returns:
            Weather data dict or None if error
        """
        # Track API calls per day
        today = datetime.now().date()
        if today != self._api_calls_date:
            self._api_calls_today = 0
            self._api_calls_date = today

        self._api_calls_today += 1

        # Warn if approaching free tier limit
        if self._api_calls_today >= 950:
            _LOGGER.warning(
                "OWM API calls approaching limit: %d/1000 today",
                self._api_calls_today,
            )

        url = (
            f"{OWM_API_BASE}"
            f"?lat={latitude}"
            f"&lon={longitude}"
            f"&appid={self.api_key}"
            f"&units={units}"
        )

        try:
            # Use HTTP proxy which handles caching, retries, and logging
            options = HttpRequestOptions(
                service="openweathermap",
                method="GET",
                url=url,
                timeout=DEFAULT_TIMEOUT_SECONDS
            )
            
            response = await self.http_proxy.request(options)

            if response.status_code == 200:
                data = json.loads(response.text) if isinstance(response.text, str) else response.text

                # Update both caches (with LRU eviction)
                cache_key = f"{latitude}_{longitude}"
                self._memory_cache[cache_key] = (data, datetime.now())
                self._memory_cache.move_to_end(cache_key)  # Mark as most recently used
                
                # Evict oldest entries if cache exceeds limit
                while len(self._memory_cache) > self._max_memory_entries:
                    evicted_key, _ = self._memory_cache.popitem(last=False)
                    _LOGGER.debug("Evicted oldest cache entry: %s", evicted_key)
                
                await self.hass.async_add_executor_job(
                    self._write_persistent_cache, latitude, longitude, data
                )

                _LOGGER.info(
                    "Fetched OWM data for %s,%s (call %d today)",
                    latitude,
                    longitude,
                    self._api_calls_today,
                )
                
                # Reset failure counter on success
                await self._reset_failure_counter()
                
                return data

            elif response.status_code == 401:
                error_msg = "OWM API key invalid or expired"
                _LOGGER.error(error_msg)
                await self._increment_failure_counter(error_msg)
                return None

            elif response.status_code == 429:
                error_msg = f"OWM API rate limit exceeded ({self._api_calls_today} calls today)"
                _LOGGER.error(error_msg)
                await self._increment_failure_counter(error_msg)
                return None

            else:
                error_msg = f"OWM API error: HTTP {response.status_code}"
                _LOGGER.error(error_msg)
                await self._increment_failure_counter(error_msg)
                return None

        except asyncio.TimeoutError:
            error_msg = "OWM API request timed out"
            _LOGGER.error(error_msg)
            await self._increment_failure_counter(error_msg)
            return None

        except Exception as e:
            error_msg = f"OWM API request failed: {e}"
            _LOGGER.error(error_msg)
            await self._increment_failure_counter(error_msg)
            return None

    def extract_current_weather(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract current weather from OWM response.

        Args:
            data: Raw OWM API response

        Returns:
            Dict with current weather fields
        """
        current = data.get("current", {})
        weather_list = current.get("weather", [{}])

        return {
            "temperature": current.get("temp"),
            "dew_point": current.get("dew_point"),
            "pressure": current.get("pressure"),
            "wind_speed": current.get("wind_speed"),
            "wind_direction": current.get("wind_deg"),
            "wind_gust": current.get("wind_gust"),
            "visibility": current.get("visibility", 10000) / 1000,  # m to km
            "clouds": current.get("clouds"),
            "humidity": current.get("humidity"),
            "uvi": current.get("uvi"),
            "weather_main": weather_list[0].get("main", "Unknown"),
            "weather_description": weather_list[0].get("description", "Unknown"),
            "weather_icon": weather_list[0].get("icon", "01d"),
        }

    def extract_minutely_forecast(self, data: Dict[str, Any]) -> list:
        """Extract minutely precipitation forecast (60 minutes).

        Args:
            data: Raw OWM API response

        Returns:
            List of minutely forecast dicts
        """
        return data.get("minutely", [])

    def extract_hourly_forecast(self, data: Dict[str, Any]) -> list:
        """Extract hourly forecast (48 hours).

        Args:
            data: Raw OWM API response

        Returns:
            List of hourly forecast dicts
        """
        return data.get("hourly", [])

    def extract_daily_forecast(self, data: Dict[str, Any]) -> list:
        """Extract daily forecast (8 days).

        Args:
            data: Raw OWM API response

        Returns:
            List of daily forecast dicts
        """
        return data.get("daily", [])

    def extract_alerts(self, data: Dict[str, Any]) -> list:
        """Extract government weather alerts.

        Args:
            data: Raw OWM API response

        Returns:
            List of alert dicts with sender, event, description, etc.
        """
        return data.get("alerts", [])

    def clear_cache(
            self,
            latitude: Optional[float] = None,
            longitude: Optional[float] = None) -> None:
        """Clear cached data for specific coordinates or all data.

        Args:
            latitude: Latitude coordinate (None = clear all)
            longitude: Longitude coordinate (None = clear all)
        """
        if latitude is not None and longitude is not None:
            # Clear specific coordinate cache
            cache_key = f"{latitude}_{longitude}"
            self._memory_cache.pop(cache_key, None)

            cache_file = self._get_cache_file_path(latitude, longitude)
            if cache_file.exists():
                cache_file.unlink()
                _LOGGER.info("Cleared cache for %s,%s", latitude, longitude)
        else:
            # Clear all caches
            self._memory_cache.clear()

            for cache_file in self.cache_dir.glob("owm_*.json"):
                cache_file.unlink()

            _LOGGER.info("Cleared all OWM caches")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring.

        Returns:
            Dict with cache stats (entries, API calls, etc.)
        """
        persistent_files = list(self.cache_dir.glob("owm_*.json"))

        return {
            "cache_enabled": self.cache_enabled,
            "cache_ttl_minutes": self.cache_ttl.total_seconds() / 60,
            "memory_cache_entries": len(self._memory_cache),
            "persistent_cache_files": len(persistent_files),
            "api_calls_today": self._api_calls_today,
            "api_calls_date": self._api_calls_date.isoformat(),
        }
