"""Validation helpers for setup wizard and user input.

This module provides real-time validation for user inputs to prevent
configuration errors and provide helpful feedback.
"""
import re
from typing import Tuple, Optional

# Validation patterns
ICAO_PATTERN = r"^[A-Z]{4}$"
UK_REG_PATTERN = r"^[A-Z]-[A-Z]{4}$"
US_REG_PATTERN = r"^[A-Z]\d{4,5}[A-Z]?$"
EU_REG_PATTERN = r"^[A-Z]{2}-[A-Z]{3}$"


def validate_icao(icao: str) -> Tuple[bool, Optional[str]]:
    """Validate ICAO airport code.
    
    ICAO codes are 4-letter airport identifiers used worldwide for aviation.
    Examples: EGHP (Popham, UK), KJFK (New York JFK, USA), LFPG (Paris CDG, France)
    
    Args:
        icao: ICAO code to validate (will be uppercased)
    
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if validation passes
        - error_message: None if valid, helpful error message if invalid
    """
    if not icao:
        return False, "ICAO code is required"
    
    icao = icao.strip().upper()
    
    if len(icao) != 4:
        return False, "ICAO codes are exactly 4 characters (e.g., EGHP, KJFK)"
    
    if not icao.isalpha():
        return False, "ICAO codes contain only letters (no numbers)"
    
    if not icao.isupper():
        return False, "ICAO codes must be uppercase"
    
    return True, None


def validate_registration(reg: str) -> Tuple[bool, Optional[str]]:
    """Validate aircraft registration (tail number).
    
    Supports common registration formats:
    - UK: G-ABCD (letter-hyphen-4 letters)
    - US: N12345 or N1234A (letter-4/5 digits with optional letter)
    - EU: D-EFGH (2 letters-hyphen-3 letters)
    
    Args:
        reg: Aircraft registration to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not reg:
        return False, "Aircraft registration is required"
    
    reg = reg.strip().upper()
    
    if len(reg) < 3:
        return False, "Registration too short (e.g., G-ABCD, N12345)"
    
    # Check against known patterns
    patterns = {
        UK_REG_PATTERN: "UK format: G-ABCD",
        US_REG_PATTERN: "US format: N12345",
        EU_REG_PATTERN: "EU format: D-EFGH",
    }
    
    for pattern, example in patterns.items():
        if re.match(pattern, reg):
            return True, None
    
    return False, f"Registration format not recognized. Examples: {', '.join(patterns.values())}"


def validate_mtow(value: float, unit: str) -> Tuple[bool, Optional[str]]:
    """Validate Maximum Takeoff Weight is within reasonable range.
    
    Checks that MTOW is within typical ranges for general aviation aircraft.
    This prevents data entry errors (typos, wrong units).
    
    Args:
        value: MTOW value
        unit: "kg" or "lbs"
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if value <= 0:
        return False, "MTOW must be greater than 0"
    
    # Reasonable ranges for GA aircraft
    if unit == "kg":
        if value < 300 or value > 5000:
            return False, f"MTOW {value} kg seems unusual. Typical range: 300-5000 kg"
    elif unit == "lbs":
        if value < 660 or value > 11000:
            return False, f"MTOW {value} lbs seems unusual. Typical range: 660-11000 lbs"
    else:
        return False, f"Unknown unit: {unit}"
    
    return True, None


def validate_runway_length(value: float, unit: str) -> Tuple[bool, Optional[str]]:
    """Validate runway length is within reasonable range.
    
    Args:
        value: Runway length value
        unit: "m" or "ft"
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if value <= 0:
        return False, "Runway length must be greater than 0"
    
    if unit == "m":
        if value < 200 or value > 6000:
            return False, f"Runway {value} m seems unusual. Typical range: 200-6000 m"
    elif unit == "ft":
        if value < 660 or value > 20000:
            return False, f"Runway {value} ft seems unusual. Typical range: 660-20000 ft"
    else:
        return False, f"Unknown unit: {unit}"
    
    return True, None


def validate_api_key(api_key: str, service: str) -> Tuple[bool, Optional[str]]:
    """Validate API key format for external services.
    
    Performs basic format validation to catch obvious errors before
    attempting API connection.
    
    Args:
        api_key: API key to validate
        service: Service name ("checkwx", "openweathermap", etc.)
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not api_key or not api_key.strip():
        return False, "API key is required"
    
    api_key = api_key.strip()
    
    # Basic length checks
    if len(api_key) < 16:
        return False, "API key seems too short. Please check and try again."
    
    # Service-specific validation
    if service == "checkwx":
        # CheckWX keys are typically 32+ chars
        if len(api_key) < 32:
            return False, "CheckWX API keys are typically 32+ characters"
    
    elif service == "openweathermap":
        # OWM keys are typically 32 hex chars
        if len(api_key) != 32:
            return False, "OpenWeatherMap API keys are 32 characters"
        if not all(c in "0123456789abcdefABCDEF" for c in api_key):
            return False, "OpenWeatherMap API keys are hexadecimal"
    
    return True, None


def validate_latitude(lat: float) -> Tuple[bool, Optional[str]]:
    """Validate latitude is within valid range.
    
    Args:
        lat: Latitude in decimal degrees
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if lat < -90 or lat > 90:
        return False, f"Latitude must be between -90 and 90 (got {lat})"
    
    return True, None


def validate_longitude(lon: float) -> Tuple[bool, Optional[str]]:
    """Validate longitude is within valid range.
    
    Args:
        lon: Longitude in decimal degrees
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if lon < -180 or lon > 180:
        return False, f"Longitude must be between -180 and 180 (got {lon})"
    
    return True, None


def get_validation_icon(is_valid: bool) -> str:
    """Get validation icon for UI display.
    
    Args:
        is_valid: Whether validation passed
    
    Returns:
        Icon string (✅ for valid, ❌ for invalid)
    """
    return "✅" if is_valid else "❌"


def format_validation_message(is_valid: bool, message: Optional[str] = None) -> str:
    """Format validation message with icon for UI display.
    
    Args:
        is_valid: Whether validation passed
        message: Error or success message
    
    Returns:
        Formatted message with icon
    """
    icon = get_validation_icon(is_valid)
    if message:
        return f"{icon} {message}"
    return f"{icon} {'Valid' if is_valid else 'Invalid'}"
