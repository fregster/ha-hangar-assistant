"""Data models for ADS-B aircraft tracking.

This module defines the core data structures used throughout the ADS-B tracking system,
supporting both ADS-B (1090MHz) and FLARM (868/915MHz) data sources.

Key Components:
    - AircraftData: Primary data class representing an aircraft's state
    - Validation functions for registration and ICAO24 hex codes
    - Utility methods for distance, bearing, and airborne status calculations

Used By:
    - All ADS-B data source clients (dump1090, OpenSky, OGN, etc.)
    - Device tracker entities
    - Traffic sensors
    - Dashboard integrations
"""

from dataclasses import dataclass, field
from datetime import datetime
from math import atan2, cos, radians, sin, sqrt
from typing import Optional


@dataclass
class AircraftData:
    """Represents real-time aircraft position and state data.
    
    This class supports both ADS-B (commercial/general aviation) and FLARM (gliders)
    data sources. Fields are intentionally flexible to accommodate different data
    source capabilities.
    
    ADS-B vs FLARM Differences:
        - ADS-B: Provides ICAO24 hex code, registration (if available), precise altitude
        - FLARM: Provides FLARM ID, often includes glider-specific data (turn rate)
        - Both: Latitude, longitude, ground speed, track
    
    Inputs:
        registration: Aircraft registration/tail number (e.g., "G-ABCD", "N12345")
        icao24: ICAO 24-bit hex code (e.g., "4CA1E3") - ADS-B unique identifier
        flarm_id: FLARM hex ID (e.g., "DDA123") - FLARM unique identifier
        latitude: Decimal degrees (-90 to 90)
        longitude: Decimal degrees (-180 to 180)
        altitude_ft: Altitude in feet above sea level (None if unavailable)
        ground_speed_kt: Ground speed in knots (None if stationary/unavailable)
        track_deg: Track angle in degrees (0-359, None if stationary)
        vertical_rate_fpm: Climb/descent rate in feet per minute (+ climb, - descent)
        turn_rate_deg_s: Turn rate in degrees per second (FLARM-specific, gliders)
        aircraft_type: ICAO aircraft type code (e.g., "C172", "GLID")
        callsign: Flight callsign (e.g., "BAW123", None for VFR)
        squawk: Transponder squawk code (e.g., "7000" for VFR)
        is_on_ground: True if aircraft on ground (ADS-B specific)
        is_flarm: True if data source is FLARM (not ADS-B)
        source: Data source name ("dump1090", "opensky", "ogn", "adsbexchange", etc.)
        priority: Source priority (1=highest, lower number = higher priority)
        last_seen: UTC timestamp of last position update
        last_contact: UTC timestamp of last contact with data source
    
    Outputs:
        - Validated aircraft state data
        - Distance/bearing calculations via utility methods
        - Airborne status determination
    
    Example:
        >>> aircraft = AircraftData(
        ...     registration="G-ABCD",
        ...     icao24="4CA1E3",
        ...     latitude=51.2789,
        ...     longitude=-0.7792,
        ...     altitude_ft=1500,
        ...     ground_speed_kt=95,
        ...     track_deg=270,
        ...     source="dump1090",
        ...     priority=1,
        ...     last_seen=datetime.utcnow()
        ... )
        >>> aircraft.is_airborne()
        True
        >>> aircraft.distance_to(51.3, -0.8)
        5.2  # nautical miles
    """
    
    # Identification (at least one required)
    registration: Optional[str] = None
    icao24: Optional[str] = None
    flarm_id: Optional[str] = None
    
    # Position (required for tracking)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude_ft: Optional[int] = None
    
    # Velocity
    ground_speed_kt: Optional[int] = None
    track_deg: Optional[int] = None  # 0-359
    vertical_rate_fpm: Optional[int] = None
    turn_rate_deg_s: Optional[float] = None  # FLARM-specific
    
    # Aircraft Details
    aircraft_type: Optional[str] = None
    callsign: Optional[str] = None
    squawk: Optional[str] = None
    
    # Status
    is_on_ground: Optional[bool] = None
    is_flarm: bool = False  # True if FLARM data source
    
    # Metadata
    source: str = "unknown"
    priority: int = 999  # Lower number = higher priority
    last_seen: Optional[datetime] = None
    last_contact: Optional[datetime] = None
    
    # Additional metadata from source
    metadata: dict = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate and normalise data after initialisation.
        
        Raises:
            ValueError: If no valid identifier (registration, ICAO24, or FLARM ID) provided
            ValueError: If position data is invalid
        """
        # Require at least one identifier
        if not any([self.registration, self.icao24, self.flarm_id]):
            raise ValueError(
                "At least one identifier required: registration, icao24, or flarm_id"
            )
        
        # Normalise ICAO24 to uppercase hex
        if self.icao24:
            self.icao24 = self.icao24.upper().strip()
        
        # Normalise FLARM ID to uppercase hex
        if self.flarm_id:
            self.flarm_id = self.flarm_id.upper().strip()
        
        # Normalise registration to uppercase
        if self.registration:
            self.registration = self.registration.upper().strip()
        
        # Validate position if provided
        if self.latitude is not None or self.longitude is not None:
            if not self._validate_position():
                raise ValueError(
                    f"Invalid position: lat={self.latitude}, lon={self.longitude}"
                )
        
        # Normalise track to 0-359 range
        if self.track_deg is not None:
            self.track_deg = self.track_deg % 360
    
    def _validate_position(self) -> bool:
        """Validate latitude and longitude are within valid ranges.
        
        Returns:
            bool: True if position is valid, False otherwise
        """
        if self.latitude is None or self.longitude is None:
            return False
        
        return (-90 <= self.latitude <= 90) and (-180 <= self.longitude <= 180)
    
    def get_unique_id(self) -> str:
        """Get unique identifier for this aircraft (for deduplication).
        
        Priority: ICAO24 > FLARM ID > Registration
        
        Returns:
            str: Unique identifier string
        """
        if self.icao24:
            return f"icao24:{self.icao24}"
        elif self.flarm_id:
            return f"flarm:{self.flarm_id}"
        elif self.registration:
            return f"reg:{self.registration}"
        else:
            return f"unknown:{id(self)}"
    
    def is_airborne(self) -> bool | None:
        """Determine if aircraft is airborne.
        
        Uses is_on_ground flag if available (ADS-B), otherwise infers from altitude.
        Gliders with altitude > 100ft are considered airborne.
        
        Returns:
            bool | None: True if aircraft is airborne, False if on ground, None if unknown
        """
        # Use explicit on-ground flag if available (ADS-B)
        if self.is_on_ground is not None:
            return not self.is_on_ground
        
        # Infer from altitude (> 100ft considered airborne)
        if self.altitude_ft is not None:
            return self.altitude_ft > 100
        
        # Unknown
        return None
    
    def distance_to(self, lat: float, lon: float) -> Optional[float]:
        """Calculate distance to a given position using Haversine formula.
        
        Args:
            lat: Target latitude in decimal degrees
            lon: Target longitude in decimal degrees
        
        Returns:
            float: Distance in nautical miles, or None if position unavailable
        """
        if self.latitude is None or self.longitude is None:
            return None
        
        # Haversine formula
        R = 3440.065  # Earth radius in nautical miles
        
        lat1 = radians(self.latitude)
        lon1 = radians(self.longitude)
        lat2 = radians(lat)
        lon2 = radians(lon)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        
        distance = R * c
        return round(distance, 2)
    
    def bearing_to(self, lat: float, lon: float) -> Optional[int]:
        """Calculate bearing to a given position.
        
        Args:
            lat: Target latitude in decimal degrees
            lon: Target longitude in decimal degrees
        
        Returns:
            int: Bearing in degrees (0-359), or None if position unavailable
        """
        if self.latitude is None or self.longitude is None:
            return None
        
        lat1 = radians(self.latitude)
        lon1 = radians(self.longitude)
        lat2 = radians(lat)
        lon2 = radians(lon)
        
        dlon = lon2 - lon1
        
        y = sin(dlon) * cos(lat2)
        x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
        
        bearing = atan2(y, x)
        bearing_deg = (bearing * 180 / 3.14159 + 360) % 360
        
        return int(bearing_deg)
    
    def time_since_last_seen(self) -> Optional[float]:
        """Calculate seconds since last position update.
        
        Returns:
            float: Seconds since last_seen, or None if timestamp unavailable
        """
        if self.last_seen is None:
            return None
        
        delta = datetime.utcnow() - self.last_seen
        return delta.total_seconds()
    
    def is_stale(self, max_age_seconds: int = 60) -> bool:
        """Check if aircraft data is stale (old).
        
        Args:
            max_age_seconds: Maximum age in seconds before considered stale (default: 60)
        
        Returns:
            bool: True if data is stale, False if fresh, None if no timestamp
        """
        age = self.time_since_last_seen()
        if age is None:
            return None
        
        return age > max_age_seconds
    
    def merge_with(self, other: "AircraftData") -> "AircraftData":
        """Merge this aircraft data with another (for deduplication).
        
        Uses priority system: lower number = higher priority wins for conflicting fields.
        Non-conflicting fields are merged (e.g., one source has registration, other has type).
        
        Args:
            other: Another AircraftData instance for the same aircraft
        
        Returns:
            AircraftData: New merged instance with best data from both sources
        """
        # Determine which source has priority
        if self.priority <= other.priority:
            primary = self
            secondary = other
        else:
            primary = other
            secondary = self
        
        # Start with primary source data
        merged = AircraftData(
            registration=primary.registration or secondary.registration,
            icao24=primary.icao24 or secondary.icao24,
            flarm_id=primary.flarm_id or secondary.flarm_id,
            latitude=primary.latitude if primary.latitude is not None else secondary.latitude,
            longitude=primary.longitude if primary.longitude is not None else secondary.longitude,
            altitude_ft=primary.altitude_ft if primary.altitude_ft is not None else secondary.altitude_ft,
            ground_speed_kt=primary.ground_speed_kt if primary.ground_speed_kt is not None else secondary.ground_speed_kt,
            track_deg=primary.track_deg if primary.track_deg is not None else secondary.track_deg,
            vertical_rate_fpm=primary.vertical_rate_fpm if primary.vertical_rate_fpm is not None else secondary.vertical_rate_fpm,
            turn_rate_deg_s=primary.turn_rate_deg_s if primary.turn_rate_deg_s is not None else secondary.turn_rate_deg_s,
            aircraft_type=primary.aircraft_type or secondary.aircraft_type,
            callsign=primary.callsign or secondary.callsign,
            squawk=primary.squawk or secondary.squawk,
            is_on_ground=primary.is_on_ground if primary.is_on_ground is not None else secondary.is_on_ground,
            is_flarm=primary.is_flarm or secondary.is_flarm,
            source=f"{primary.source},{secondary.source}",  # Track both sources
            priority=primary.priority,  # Use higher priority
            last_seen=primary.last_seen if primary.last_seen else secondary.last_seen,
            last_contact=primary.last_contact if primary.last_contact else secondary.last_contact,
            metadata={**secondary.metadata, **primary.metadata}  # Merge metadata, primary wins
        )
        
        return merged


def validate_registration(registration: str) -> bool:
    """Validate aircraft registration format.
    
    Supports common formats:
    - UK: G-XXXX (4 letters/digits after G-)
    - US: N12345 or N123AB (alphanumeric after N)
    - Germany: D-XXXX
    - France: F-XXXX
    - And others following {letter}-{alphanumeric} pattern
    
    Args:
        registration: Aircraft registration string
    
    Returns:
        bool: True if format appears valid, False otherwise
    """
    if not registration or len(registration) < 3:
        return False
    
    # Normalise to uppercase
    reg = registration.upper().strip()
    
    # Basic pattern: starts with 1-2 letters, optional hyphen, alphanumeric
    # Examples: G-ABCD, N12345, D-EFGH, F-WXYZ
    if len(reg) < 3 or len(reg) > 10:
        return False
    
    # First character must be letter (country code)
    if not reg[0].isalpha():
        return False
    
    # Allow hyphen as second or third character
    if '-' in reg:
        parts = reg.split('-')
        if len(parts) != 2:
            return False
        # Part after hyphen must be alphanumeric
        if not parts[1].isalnum():
            return False
    
    return True


def validate_icao24(icao24: str) -> bool:
    """Validate ICAO 24-bit address hex code.
    
    ICAO24 addresses are 6-character hexadecimal strings (24 bits).
    Examples: 4CA1E3, ABC123, 000001
    
    Args:
        icao24: ICAO24 hex string
    
    Returns:
        bool: True if format is valid 6-digit hex, False otherwise
    """
    if not icao24 or len(icao24) != 6:
        return False
    
    # Check if valid hexadecimal
    try:
        int(icao24, 16)
        return True
    except ValueError:
        return False


def validate_flarm_id(flarm_id: str) -> bool:
    """Validate FLARM ID hex code.
    
    FLARM IDs are typically 6-character hexadecimal strings.
    Examples: DDA123, ABC456
    
    Args:
        flarm_id: FLARM hex ID string
    
    Returns:
        bool: True if format is valid 6-digit hex, False otherwise
    """
    # FLARM IDs use same format as ICAO24
    return validate_icao24(flarm_id)
