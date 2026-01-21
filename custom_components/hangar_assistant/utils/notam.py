"""NOTAM client for UK NATS Aeronautical Information Service.

This module provides functionality to fetch, parse, and cache Notice to Airmen
(NOTAM) data from the UK NATS PIB (Pre-flight Information Bulletin) XML feed.

Data Source:
    UK NATS AIS: https://pibs.nats.co.uk/operational/pibs/PIB.xml

Caching Strategy:
    - Persistent file-based caching with configurable retention (default: 7 days)
    - Stale cache allowed on fetch failure (graceful degradation)
    - Cache survives Home Assistant restarts

Error Handling:
    - Network failures: Use stale cache indefinitely
    - Parse errors: Log error, return empty list
    - Failure tracking: Increment counter for monitoring
    - Warning sensors created for stale data

Usage:
    client = NOTAMClient(hass, cache_days=7)
    notams, is_stale = await client.fetch_notams()
    filtered = client.filter_by_location(notams, icao="EGLL")
"""

from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# UK NATS PIB XML feed URL
NATS_PIB_URL = "https://pibs.nats.co.uk/operational/pibs/PIB.xml"

# Default timeout for HTTP requests (seconds)
DEFAULT_TIMEOUT_SECONDS = 30


class NOTAMClient:
    """Client for UK NATS NOTAM XML feed with persistent caching."""

    def __init__(
        self,
        hass: HomeAssistant,
        cache_days: int = 7,
        entry: Any = None
    ) -> None:
        """Initialize NOTAM client.

        Args:
            hass: Home Assistant instance
            cache_days: Days to retain cached NOTAMs (default: 7)
            entry: Config entry for failure tracking (optional)
        """
        self.hass = hass
        self.cache_days = cache_days
        self.entry = entry
        self.cache_dir = Path(hass.config.path("hangar_assistant_cache"))
        self.cache_file = self.cache_dir / "notams.json"

    async def fetch_notams(self) -> Tuple[List[Dict[str, Any]], bool]:
        """Fetch NOTAMs from NATS or cache with stale fallback.

        Returns:
            Tuple of (notams_list, is_stale_data)
                - notams_list: List of NOTAM dictionaries
                - is_stale_data: True if using expired cache due to failure

        Raises:
            None - All errors are caught and logged internally
        """
        # Check fresh cache first
        cached = self._read_cache()
        if cached:
            return cached, False

        # Try fetching fresh data
        try:
            notams = await self._fetch_from_nats()

            if notams:
                # Success - reset failure counter
                await self._reset_failure_counter()
                return notams, False

        except Exception as e:
            _LOGGER.error("NOTAM fetch failed: %s", e)
            await self._increment_failure_counter(str(e))

            # Try stale cache if allowed
            stale_notams = self._read_stale_cache()
            if stale_notams:
                cache_age = self._get_cache_age_hours()
                _LOGGER.warning(
                    "Using stale NOTAM cache (%d hours old) due to fetch failure",
                    cache_age
                )
                return stale_notams, True

            # No cache available
            _LOGGER.error("No NOTAM data available (fresh or cached)")
            return [], False

        return [], False

    async def _fetch_from_nats(self) -> List[Dict[str, Any]]:
        """Download and parse NATS PIB XML.

        Returns:
            List of NOTAM dictionaries with parsed data

        Raises:
            Exception: On network or parsing errors
        """
        session = self.hass.helpers.aiohttp_client.async_get_clientsession()

        async with session.get(NATS_PIB_URL, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            if response.status == 200:
                xml_content = await response.text()
                notams = self._parse_pib_xml(xml_content)
                self._write_cache(notams)
                _LOGGER.info("Fetched %d NOTAMs from NATS PIB feed", len(notams))
                return notams
            else:
                _LOGGER.error("NATS PIB fetch failed: HTTP %d", response.status)
                raise Exception(f"HTTP {response.status}")

    def _parse_pib_xml(self, xml_content: str) -> List[Dict[str, Any]]:
        """Parse PIB XML into structured NOTAM data.

        Args:
            xml_content: Raw XML string from NATS PIB feed

        Returns:
            List of NOTAM dictionaries with extracted fields

        NOTAM Structure:
            - id: NOTAM identifier (e.g., "C0123/21")
            - location: ICAO code or area identifier
            - category: Type of NOTAM (AERODROME, AIRSPACE, etc.)
            - start_time: ISO timestamp when NOTAM becomes effective
            - end_time: ISO timestamp when NOTAM expires
            - text: Full NOTAM text content
            - latitude: Latitude if location-specific (optional)
            - longitude: Longitude if location-specific (optional)
        """
        try:
            root = ET.fromstring(xml_content)
            notams = []

            # Parse each NOTAM element
            for notam_elem in root.findall(".//NOTAM"):
                try:
                    notam = {
                        "id": self._get_text(notam_elem, "ID"),
                        "location": self._get_text(notam_elem, "LOCATION") or self._get_text(notam_elem, "ICAO"),
                        "category": self._get_text(notam_elem, "CATEGORY") or "UNKNOWN",
                        "start_time": self._parse_datetime(self._get_text(notam_elem, "START") or self._get_text(notam_elem, "StartDate")),
                        "end_time": self._parse_datetime(self._get_text(notam_elem, "END") or self._get_text(notam_elem, "EndDate")),
                        "text": self._get_text(notam_elem, "TEXT") or self._get_text(notam_elem, "Text") or "",
                        "q_code": self._get_text(notam_elem, "Q"),
                        "latitude": self._get_float(notam_elem, "LAT") or self._get_float(notam_elem, "Latitude"),
                        "longitude": self._get_float(notam_elem, "LON") or self._get_float(notam_elem, "Longitude"),
                    }

                    # Only add NOTAMs with valid ID
                    if notam["id"]:
                        notams.append(notam)

                except Exception as e:
                    _LOGGER.debug("Failed to parse NOTAM element: %s", e)
                    continue

            return notams

        except ET.ParseError as e:
            _LOGGER.error("Failed to parse PIB XML: %s", e)
            return []

    def _get_text(self, element: ET.Element, tag: str) -> Optional[str]:
        """Safely extract text from XML element.

        Args:
            element: XML element to search
            tag: Tag name to find

        Returns:
            Text content or None if not found
        """
        child = element.find(tag)
        if child is not None and child.text:
            return child.text.strip()
        return None

    def _get_float(self, element: ET.Element, tag: str) -> Optional[float]:
        """Safely extract float from XML element.

        Args:
            element: XML element to search
            tag: Tag name to find

        Returns:
            Float value or None if not found/invalid
        """
        text = self._get_text(element, tag)
        if text:
            try:
                return float(text)
            except ValueError:
                pass
        return None

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[str]:
        """Parse and normalize datetime strings to ISO format.

        Args:
            dt_str: Date/time string in various formats

        Returns:
            ISO 8601 formatted string or None if invalid
        """
        if not dt_str:
            return None

        try:
            # Try parsing common NOTAM date formats
            for fmt in [
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S",
                "%Y%m%d%H%M",
                "%Y-%m-%d",
            ]:
                try:
                    dt = datetime.strptime(dt_str, fmt)
                    return dt.isoformat()
                except ValueError:
                    continue

            # If no format matches, return original
            return dt_str

        except Exception:
            return None

    def _read_cache(self) -> Optional[List[Dict[str, Any]]]:
        """Read cached NOTAMs if within retention period.

        Returns:
            List of NOTAMs or None if cache expired/missing
        """
        if not self.cache_file.exists():
            return None

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)

            cache_time = datetime.fromisoformat(cached["cached_at"])
            if datetime.now() - cache_time < timedelta(days=self.cache_days):
                _LOGGER.debug("NOTAM cache hit (age: %d hours)", self._get_cache_age_hours())
                return cached["notams"]

            _LOGGER.debug("NOTAM cache expired (age: %d hours)", self._get_cache_age_hours())

        except (OSError, json.JSONDecodeError, KeyError) as e:
            _LOGGER.debug("Failed to read NOTAM cache: %s", e)

        return None

    def _read_stale_cache(self) -> Optional[List[Dict[str, Any]]]:
        """Read cached NOTAMs even if expired (graceful degradation).

        Returns:
            List of NOTAMs or None if cache missing/corrupt
        """
        if not self.cache_file.exists():
            return None

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)
            return cached.get("notams", [])

        except (OSError, json.JSONDecodeError):
            return None

    def _write_cache(self, notams: List[Dict[str, Any]]) -> None:
        """Write NOTAMs to persistent cache.

        Args:
            notams: List of NOTAM dictionaries to cache
        """
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

            cached = {
                "cached_at": datetime.now().isoformat(),
                "notams": notams
            }

            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cached, f, indent=2)

            _LOGGER.debug("Wrote %d NOTAMs to cache", len(notams))

        except (OSError, TypeError) as e:
            _LOGGER.error("Failed to write NOTAM cache: %s", e)

    def _get_cache_age_hours(self) -> int:
        """Get age of cached data in hours.

        Returns:
            Hours since cache was written, or 0 if no cache exists
        """
        if not self.cache_file.exists():
            return 0

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)
            cache_time = datetime.fromisoformat(cached["cached_at"])
            return int((datetime.now() - cache_time).total_seconds() / 3600)
        except Exception:
            return 0

    def filter_by_location(
        self,
        notams: List[Dict[str, Any]],
        icao: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        radius_nm: float = 50
    ) -> List[Dict[str, Any]]:
        """Filter NOTAMs by ICAO code or proximity to coordinates.

        Args:
            notams: List of NOTAM dictionaries to filter
            icao: ICAO airport code to match (e.g., "EGLL")
            lat: Latitude for proximity filtering
            lon: Longitude for proximity filtering
            radius_nm: Radius in nautical miles for proximity (default: 50)

        Returns:
            Filtered list of NOTAMs relevant to the location
        """
        if not notams:
            return []

        filtered = []

        for notam in notams:
            # Filter by ICAO code
            if icao and notam.get("location") == icao:
                filtered.append(notam)
                continue

            # Filter by proximity to coordinates
            if lat is not None and lon is not None:
                notam_lat = notam.get("latitude")
                notam_lon = notam.get("longitude")

                if notam_lat is not None and notam_lon is not None:
                    distance_nm = self._calculate_distance_nm(
                        lat, lon, notam_lat, notam_lon
                    )
                    if distance_nm <= radius_nm:
                        filtered.append(notam)

        return filtered

    def _calculate_distance_nm(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """Calculate great-circle distance between two points.

        Uses the Haversine formula to compute distance between two
        latitude/longitude points on Earth.

        Args:
            lat1: Latitude of first point (degrees)
            lon1: Longitude of first point (degrees)
            lat2: Latitude of second point (degrees)
            lon2: Longitude of second point (degrees)

        Returns:
            Distance in nautical miles
        """
        from math import radians, sin, cos, sqrt, atan2

        # Earth radius in nautical miles
        R = 3440.065

        # Convert to radians
        lat1_rad = radians(lat1)
        lon1_rad = radians(lon1)
        lat2_rad = radians(lat2)
        lon2_rad = radians(lon2)

        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        return R * c

    def clear_cache(self) -> None:
        """Remove cached NOTAM data."""
        if self.cache_file.exists():
            try:
                self.cache_file.unlink()
                _LOGGER.info("Cleared NOTAM cache")
            except OSError as e:
                _LOGGER.error("Failed to clear NOTAM cache: %s", e)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache metadata:
                - exists: Whether cache file exists
                - age_hours: Age of cache in hours
                - count: Number of cached NOTAMs
                - size_bytes: Cache file size in bytes
        """
        if not self.cache_file.exists():
            return {
                "exists": False,
                "age_hours": 0,
                "count": 0,
                "size_bytes": 0
            }

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)

            return {
                "exists": True,
                "age_hours": self._get_cache_age_hours(),
                "count": len(cached.get("notams", [])),
                "size_bytes": self.cache_file.stat().st_size
            }
        except Exception:
            return {
                "exists": True,
                "age_hours": 0,
                "count": 0,
                "size_bytes": 0
            }

    async def _increment_failure_counter(self, error_msg: str) -> None:
        """Track consecutive failures for monitoring.

        Args:
            error_msg: Error message to store
        """
        if not self.entry:
            return

        try:
            integrations = self.entry.data.get("integrations", {})
            notam_config = integrations.get("notams", {})

            failures = notam_config.get("consecutive_failures", 0) + 1
            notam_config["consecutive_failures"] = failures
            notam_config["last_error"] = error_msg

            new_data = {**self.entry.data, "integrations": integrations}
            self.hass.config_entries.async_update_entry(self.entry, data=new_data)

            _LOGGER.debug("NOTAM failure counter: %d", failures)

        except Exception as e:
            _LOGGER.debug("Failed to update NOTAM failure counter: %s", e)

    async def _reset_failure_counter(self) -> None:
        """Reset failure counter on successful fetch."""
        if not self.entry:
            return

        try:
            integrations = self.entry.data.get("integrations", {})
            notam_config = integrations.get("notams", {})

            notam_config["consecutive_failures"] = 0
            notam_config["last_error"] = None
            notam_config["last_update"] = datetime.now().isoformat()

            new_data = {**self.entry.data, "integrations": integrations}
            self.hass.config_entries.async_update_entry(self.entry, data=new_data)

            _LOGGER.debug("NOTAM failure counter reset")

        except Exception as e:
            _LOGGER.debug("Failed to reset NOTAM failure counter: %s", e)
