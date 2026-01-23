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
            raise ValueError(
                f"Invalid preference: {preference}. Must be one of {self.VALID_PREFERENCES}")
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


def convert_altitude(
        value: Optional[float],
        from_feet: bool = True,
        to_preference: str = "aviation") -> Optional[float]:
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


def convert_speed(
        value: Optional[float],
        from_knots: bool = True,
        to_preference: str = "aviation") -> Optional[float]:
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


def convert_weight(
        value: Optional[float],
        from_pounds: bool = True,
        to_preference: str = "aviation") -> Optional[float]:
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
        Unit string: 'lb' for aviation, 'kg' for SI
    """
    return "lb" if preference == "aviation" else "kg"


# Fuel volume conversion factors
LITERS_TO_US_GALLONS = 0.264172
LITERS_TO_IMPERIAL_GALLONS = 0.219969
US_GALLONS_TO_LITERS = 3.78541
IMPERIAL_GALLONS_TO_LITERS = 4.54609


def convert_fuel_volume(
        value: Optional[float],
        from_unit: str = "liters",
        to_unit: str = "liters") -> Optional[float]:
    """Convert fuel volume between liters and gallons.

    Args:
        value: Volume value to convert
        from_unit: Source unit ('liters', 'gallons', 'gallons_imperial')
        to_unit: Target unit ('liters', 'gallons', 'gallons_imperial')

    Returns:
        Converted value, or None if input is None
    """
    if value is None:
        return None

    # Normalize from_unit
    if from_unit == "gallons":
        from_unit = "gallons_us"

    # Normalize to_unit
    if to_unit == "gallons":
        to_unit = "gallons_us"

    # If same unit, return as-is
    if from_unit == to_unit:
        return value

    # Convert to liters first (common base)
    if from_unit == "liters":
        value_liters = value
    elif from_unit == "gallons_us":
        value_liters = value * US_GALLONS_TO_LITERS
    elif from_unit == "gallons_imperial":
        value_liters = value * IMPERIAL_GALLONS_TO_LITERS
    else:
        # Unknown unit, return as-is
        return value

    # Convert from liters to target unit
    if to_unit == "liters":
        return value_liters
    elif to_unit == "gallons_us":
        return value_liters * LITERS_TO_US_GALLONS
    elif to_unit == "gallons_imperial":
        return value_liters * LITERS_TO_IMPERIAL_GALLONS
    else:
        # Unknown unit, return liters
        return value_liters


def get_fuel_volume_unit(preference: str = "aviation") -> str:
    """Get the unit string for fuel volume display.

    Args:
        preference: Unit preference ('aviation' or 'si')

    Returns:
        Unit string: 'gal' for aviation (US gallons), 'L' for SI (liters)
    """
    return "gal" if preference == "aviation" else "L"


def get_fuel_burn_rate_unit(preference: str = "aviation") -> str:
    """Get the unit string for fuel burn rate display.

    Args:
        preference: Unit preference ('aviation' or 'si')

    Returns:
        Unit string: 'gal/h' for aviation, 'L/h' for SI
    """
    return "gal/h" if preference == "aviation" else "L/h"


def calculate_fuel_weight(
        volume: float,
        fuel_type: str,
        volume_unit: str = "liters") -> float:
    """Calculate fuel weight from volume.

    Args:
        volume: Fuel volume
        fuel_type: Type of fuel (AVGAS, MOGAS, JET_A, etc.)
        volume_unit: Unit of volume ('liters', 'gallons', 'gallons_imperial')

    Returns:
        Fuel weight in kilograms
    """
    from ..const import FUEL_DENSITY, FUEL_TYPE_AVGAS

    # Convert to liters first
    volume_liters = convert_fuel_volume(volume, from_unit=volume_unit, to_unit="liters")
    if volume_liters is None:
        return 0.0

    # Get density (default to AVGAS if unknown type)
    density_data = FUEL_DENSITY.get(fuel_type, FUEL_DENSITY[FUEL_TYPE_AVGAS])
    kg_per_liter = density_data["kg_per_liter"]

    return volume_liters * kg_per_liter


def calculate_fuel_endurance(
        tank_capacity: float,
        burn_rate: float,
        volume_unit: str = "liters",
        reserve_minutes: int = 30) -> float:
    """Calculate fuel endurance in hours.

    Args:
        tank_capacity: Total usable fuel capacity
        burn_rate: Fuel burn rate per hour
        volume_unit: Unit of volume ('liters', 'gallons', 'gallons_imperial')
        reserve_minutes: Reserve fuel time in minutes (default: 30)

    Returns:
        Endurance in hours (excluding reserve)
    """
    if burn_rate <= 0:
        return 0.0

    # Ensure both in same units (convert to liters)
    capacity_liters = convert_fuel_volume(tank_capacity, from_unit=volume_unit, to_unit="liters")
    burn_rate_liters = convert_fuel_volume(burn_rate, from_unit=volume_unit, to_unit="liters")

    if capacity_liters is None or burn_rate_liters is None:
        return 0.0

    # Total endurance
    total_hours = capacity_liters / burn_rate_liters

    # Subtract reserve
    reserve_hours = reserve_minutes / 60.0
    usable_hours = max(0.0, total_hours - reserve_hours)

    return usable_hours
