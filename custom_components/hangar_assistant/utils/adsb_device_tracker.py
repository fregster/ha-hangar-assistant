"""ADS-B Device Tracker Implementation.

Provides device tracker entities for individual aircraft tracked via ADS-B.
Each aircraft is represented as a device with location tracking and attributes.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Set
from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import (
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_ALTITUDE,
)

from custom_components.hangar_assistant.utils.adsb_models import AircraftData

_LOGGER = logging.getLogger(__name__)

# Integration domain
DOMAIN = "hangar_assistant"

# Device tracker source name
DEVICE_TRACKER_SOURCE = f"{DOMAIN}_adsb"

# GPS accuracy for ADS-B data (varies by source)
GPS_ACCURACY_DUMP1090 = 50  # meters
GPS_ACCURACY_OPENSKY = 100  # meters
GPS_ACCURACY_OGN = 200  # meters (more coarse)
GPS_ACCURACY_FR24 = 150  # meters
GPS_ACCURACY_FLIGHTAWARE = 200  # meters


@dataclass
class ADSBAircraftLocation:
    """Location data for an ADS-B tracked aircraft."""

    latitude: float
    longitude: float
    altitude: Optional[int] = None
    accuracy: int = 100  # meters
    gps_accuracy: int = 100  # deprecated but included for compatibility
    track: Optional[float] = None  # heading in degrees
    ground_speed: Optional[float] = None  # knots
    vertical_speed: Optional[float] = None  # feet per minute
    callsign: Optional[str] = None
    source: Optional[str] = None


class ADSBDeviceTrackerManager:
    """Manages device tracker entities for ADS-B aircraft.
    
    Converts AircraftData objects from ADSBManager into Home Assistant
    device tracker entities with location updates and attributes.
    """

    def __init__(self, hass: HomeAssistant):
        """Initialize device tracker manager.
        
        Args:
            hass: Home Assistant instance
        """
        self.hass = hass
        self._tracked_aircraft: Dict[str, Dict] = {}  # Maps ICAO24 to aircraft data
        self._entity_registry: Dict[str, str] = {}  # Maps ICAO24 → entity_id
        self._ident_map: Dict[str, str] = {}  # Maps aircraft ID → ICAO24 for tracking
        self._update_callbacks: List = []

    def register_update_callback(self, callback_fn) -> None:
        """Register a callback for device updates.
        
        Args:
            callback_fn: Async function to call on updates
        """
        if callback_fn not in self._update_callbacks:
            self._update_callbacks.append(callback_fn)

    async def _notify_updates(self, updates: Dict[str, ADSBAircraftLocation]) -> None:
        """Notify all callbacks of device updates.
        
        Args:
            updates: Dict mapping entity_id to location data
        """
        for callback_fn in self._update_callbacks:
            try:
                if callable(callback_fn) and hasattr(callback_fn, '__self__'):
                    # Method bound to instance
                    await callback_fn(updates)
                elif callable(callback_fn):
                    # Regular function - wrap in coroutine if needed
                    result = callback_fn(updates)
                    if hasattr(result, '__await__'):
                        await result
            except Exception as e:
                _LOGGER.error("Error calling update callback: %s", e)

    def get_device_info(self, aircraft: AircraftData) -> DeviceInfo:
        """Generate Home Assistant DeviceInfo for aircraft.
        
        Args:
            aircraft: Aircraft data
        
        Returns:
            DeviceInfo with aircraft identifier and metadata
        """
        # Determine identifier (prefer registration, fallback to ICAO24 or FLARM ID)
        identifier = (
            aircraft.registration
            or aircraft.icao24
            or aircraft.flarm_id
            or "unknown"
        ).lower().replace(" ", "_")

        # Generate display name
        name_parts = []
        if aircraft.registration:
            name_parts.append(aircraft.registration)
        if aircraft.callsign:
            name_parts.append(f"({aircraft.callsign})")
        if not name_parts:
            name_parts.append(aircraft.icao24 or aircraft.flarm_id or "Unknown Aircraft")

        display_name = " ".join(name_parts)

        return DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            name=display_name,
            manufacturer="ADS-B Network",
            model=aircraft.aircraft_type or "Unknown",
            hw_version=aircraft.icao24,
            suggested_area="Airspace",
        )

    def _get_gps_accuracy(self, aircraft: AircraftData) -> int:
        """Determine GPS accuracy based on source.
        
        Args:
            aircraft: Aircraft data with source information
        
        Returns:
            GPS accuracy in meters
        """
        source = aircraft.source or "unknown"
        
        if "dump1090" in source.lower():
            return GPS_ACCURACY_DUMP1090
        elif "opensky" in source.lower():
            return GPS_ACCURACY_OPENSKY
        elif "ogn" in source.lower():
            return GPS_ACCURACY_OGN
        elif "fr24" in source.lower():
            return GPS_ACCURACY_FR24
        elif "flightaware" in source.lower():
            return GPS_ACCURACY_FLIGHTAWARE
        else:
            return 100

    def _aircraft_to_location(self, aircraft: AircraftData) -> Optional[ADSBAircraftLocation]:
        """Convert AircraftData to location for device tracker.
        
        Args:
            aircraft: Aircraft data
        
        Returns:
            Location data or None if insufficient data
        """
        if aircraft.latitude is None or aircraft.longitude is None:
            return None

        # Convert altitude if present (AircraftData stores in feet)
        altitude = aircraft.altitude_ft  # Already in feet

        return ADSBAircraftLocation(
            latitude=aircraft.latitude,
            longitude=aircraft.longitude,
            altitude=altitude,
            accuracy=self._get_gps_accuracy(aircraft),
            gps_accuracy=self._get_gps_accuracy(aircraft),
            track=aircraft.track_deg,
            ground_speed=aircraft.ground_speed_kt,
            callsign=aircraft.callsign,
            source=aircraft.source,
        )

    async def update_aircraft(self, aircraft_list: List[AircraftData]) -> None:
        """Update device tracker with current aircraft data.
        
        Updates existing tracked aircraft and registers new ones.
        
        Args:
            aircraft_list: List of aircraft from ADS-B sources
        """
        # Track which aircraft we see in this update
        seen_icao24: Set[str] = set()
        location_updates: Dict[str, ADSBAircraftLocation] = {}

        for aircraft in aircraft_list:
            if not aircraft.icao24:
                continue

            seen_icao24.add(aircraft.icao24)

            # Convert to location
            location = self._aircraft_to_location(aircraft)
            if not location:
                continue

            # Generate entity ID
            entity_id = self._generate_entity_id(aircraft)
            location_updates[entity_id] = location

            # Register or update aircraft tracking
            self._entity_registry[aircraft.icao24] = entity_id

            # Store device info for later entity creation
            if aircraft.icao24 not in self._tracked_aircraft:
                # New aircraft - would need entity creation in platform
                _LOGGER.debug(
                    "New ADS-B aircraft: %s (%s)",
                    aircraft.registration or aircraft.icao24,
                    aircraft.source,
                )

        # Notify via callback for entity platform to update
        if location_updates:
            await self._notify_updates(location_updates)

    def _generate_entity_id(self, aircraft: AircraftData) -> str:
        """Generate entity ID for aircraft.
        
        Args:
            aircraft: Aircraft data
        
        Returns:
            Entity ID in format: device_tracker.aircraft_{identifier}
        """
        # Use registration if available, fallback to ICAO24 or FLARM ID
        identifier = (
            aircraft.registration
            or aircraft.icao24
            or aircraft.flarm_id
        )

        if not identifier:
            identifier = "unknown"

        # Sanitize for entity ID (lowercase, replace spaces/special chars)
        identifier = (
            identifier.lower()
            .replace(" ", "_")
            .replace("-", "_")
            .replace("/", "_")
        )

        return f"device_tracker.aircraft_{identifier}"

    def get_tracked_aircraft(self) -> Dict[str, str]:
        """Get mapping of ICAO24 to entity IDs.
        
        Returns:
            Dictionary mapping ICAO24 codes to entity IDs
        """
        return dict(self._entity_registry)

    def get_aircraft_count(self) -> int:
        """Get number of currently tracked aircraft.
        
        Returns:
            Count of unique aircraft
        """
        return len(self._entity_registry)

    def clear_stale_tracking(self, current_icao24: Set[str], max_age_minutes: int = 60) -> None:
        """Remove aircraft not seen recently (aging out).
        
        Args:
            current_icao24: Set of ICAO24 codes currently visible
            max_age_minutes: Minutes before considering aircraft gone
        """
        # Could track last_seen timestamps and remove old entries
        # For now, just log what we have
        stale_count = len(self._entity_registry) - len(current_icao24)
        if stale_count > 0:
            _LOGGER.debug(
                "ADS-B tracking: %d aircraft active, %d stale",
                len(current_icao24),
                stale_count,
            )

    def get_manager_stats(self) -> Dict[str, any]:
        """Get statistics about tracked aircraft.
        
        Returns:
            Dictionary with tracking statistics
        """
        return {
            "tracked_aircraft_count": len(self._entity_registry),
            "registered_entities": len(self._entity_registry),
            "callbacks_registered": len(self._update_callbacks),
        }
