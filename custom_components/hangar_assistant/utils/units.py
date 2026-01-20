"""Unit conversion utilities for Hangar Assistant.

Provides conversion functions between aviation units (feet, knots, pounds) and SI units
(meters, kph, kilograms). Supports a configurable global unit preference system.
"""
from typing import Optional


class UnitPreference:
    """Manages unit preference settings for the integration.
    
    Supports two unit systems:
    - AVIATION: feet, knots, pounds (typical aviation units)
    - SI: meters, kph, kilograms (metric/SI units)
    
    This class validates and stores user preferences, providing conversion
    factors and unit strings for sensor display.
    """
    
    AVIATION = "aviation"
    SI = "si"
    VALID_PREFERENCES = {AVIATION, SI}
    
    def __init__(self, preference: str = AVIATION):
        """Initialize with a unit preference.
        
        Args:
            preference: Either 'aviation' or 'si'. Defaults to 'aviation'.
            
        Raises:
            ValueError: If preference is not a valid option.
        """
        if preference not in self.VALID_PREFERENCES:
            raise ValueError(f"Invalid preference: {preference}. Must be one of {self.VALID_PREFERENCES}")
        self.preference = preference
    
    def is_aviation(self) -> bool:
        """Return True if using aviation units."""
        return self.preference == self.AVIATION
    
    def is_si(self) -> bool:
        """Return True if using SI units."""
        return self.preference == self.SI


# Conversion factors
FEET_TO_METERS = 0.3048
METERS_TO_FEET = 1 / FEET_TO_METERS
KNOTS_TO_KPH = 1.852
KPH_TO_KNOTS = 1 / KNOTS_TO_KPH
POUNDS_TO_KG = 0.453592
KG_TO_POUNDS = 1 / POUNDS_TO_KG


def convert_altitude(value: Optional[float], from_feet: bool = True, to_preference: str = "aviation") -> Optional[float]:
    """Convert altitude between feet and meters.
    
    Args:
        value: Altitude value to convert
        from_feet: If True, convert from feet to target unit. If False, from meters to target.
        to_preference: Target unit preference ('aviation' for feet, 'si' for meters)
    
    Returns:
        Converted value, or None if input is None
    """
    if value is None:
        return None
    
    if to_preference == "aviation":
        # Target is feet
        if from_feet:
            return value  # Already in feet
        else:
            return value * METERS_TO_FEET  # Convert from meters to feet
    else:
        # Target is SI (meters)
        if from_feet:
            return value * FEET_TO_METERS  # Convert from feet to meters
        else:
            return value  # Already in meters


def convert_speed(value: Optional[float], from_knots: bool = True, to_preference: str = "aviation") -> Optional[float]:
    """Convert speed between knots and kph.
    
    Args:
        value: Speed value to convert
        from_knots: If True, convert from knots to target unit. If False, from kph to target.
        to_preference: Target unit preference ('aviation' for knots, 'si' for kph)
    
    Returns:
        Converted value, or None if input is None
    """
    if value is None:
        return None
    
    if to_preference == "aviation":
        # Target is knots
        if from_knots:
            return value  # Already in knots
        else:
            return value * KPH_TO_KNOTS  # Convert from kph to knots
    else:
        # Target is SI (kph)
        if from_knots:
            return value * KNOTS_TO_KPH  # Convert from knots to kph
        else:
            return value  # Already in kph


def convert_weight(value: Optional[float], from_pounds: bool = True, to_preference: str = "aviation") -> Optional[float]:
    """Convert weight between pounds and kilograms.
    
    Args:
        value: Weight value to convert
        from_pounds: If True, convert from pounds to target unit. If False, from kg to target.
        to_preference: Target unit preference ('aviation' for pounds, 'si' for kg)
    
    Returns:
        Converted value, or None if input is None
    """
    if value is None:
        return None
    
    if to_preference == "aviation":
        # Target is pounds
        if from_pounds:
            return value  # Already in pounds
        else:
            return value * KG_TO_POUNDS  # Convert from kg to pounds
    else:
        # Target is SI (kg)
        if from_pounds:
            return value * POUNDS_TO_KG  # Convert from pounds to kg
        else:
            return value  # Already in kg


def get_altitude_unit(preference: str = "aviation") -> str:
    """Get the unit string for altitude display.
    
    Args:
        preference: Unit preference ('aviation' or 'si')
    
    Returns:
        Unit string: 'ft' for aviation, 'm' for SI
    """
    return "ft" if preference == "aviation" else "m"


def get_speed_unit(preference: str = "aviation") -> str:
    """Get the unit string for speed display.
    
    Args:
        preference: Unit preference ('aviation' or 'si')
    
    Returns:
        Unit string: 'kt' for aviation, 'kph' for SI
    """
    return "kt" if preference == "aviation" else "kph"


def get_weight_unit(preference: str = "aviation") -> str:
    """Get the unit string for weight display.
    
    Args:
        preference: Unit preference ('aviation' or 'si')
    
    Returns:
        Unit string: 'lbs' for aviation, 'kg' for SI
    """
    return "lbs" if preference == "aviation" else "kg"
