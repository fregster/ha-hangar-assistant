"""Constants for the Hangar Assistant integration."""
from homeassistant.const import Platform

# The unique domain for the integration
DOMAIN = "hangar_assistant"

# The list of platforms supported by this integration
# In this version, we use 'sensor' for weather/performance and
# 'binary_sensor' for alerts.
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
]

# Attribute constants used for legal and data tracking
ATTR_OLD_SOURCE = "oldest_source"
ATTR_LAST_CHECK = "last_check_utc"
ATTR_PILOT_NAME = "pilot_in_command"

# Default retention setting (months) as required by the CAA 6-month rule
DEFAULT_RETENTION_MONTHS = 7

# Dashboard version for tracking template updates
DEFAULT_DASHBOARD_VERSION = 2

# Weather freshness defaults
DEFAULT_STALE_WEATHER_MINUTES = 30
DEFAULT_DA_CAUTION_FT = 3000
DEFAULT_DA_WARNING_FT = 6000
DEFAULT_FROST_TEMP_C = 3
DEFAULT_SURFACE_ICE_SPREAD_C = 2
DEFAULT_AIRFRAME_ICING_MIN_C = -10
DEFAULT_AIRFRAME_ICING_MAX_C = 5
DEFAULT_SATURATION_SPREAD_C = 3

# Sensor value caching (performance optimization)
DEFAULT_SENSOR_CACHE_TTL_SECONDS = 60  # 1 minute default cache TTL

# NOTAM filtering defaults
DEFAULT_NOTAM_RADIUS_NM = 50  # Default radius for NOTAM filtering

# Unit preferences
UNIT_PREFERENCE_AVIATION = "aviation"  # Feet, knots, pounds
UNIT_PREFERENCE_SI = "si"  # Meters, kph, kilograms
DEFAULT_UNIT_PREFERENCE = UNIT_PREFERENCE_AVIATION

# Fuel types
FUEL_TYPE_AVGAS = "AVGAS"
FUEL_TYPE_MOGAS = "MOGAS"
FUEL_TYPE_JET_A = "JET_A"
FUEL_TYPE_JET_B = "JET_B"
FUEL_TYPE_DIESEL = "DIESEL"
FUEL_TYPE_NONE = "NONE"

FUEL_TYPES = [
    FUEL_TYPE_AVGAS,
    FUEL_TYPE_MOGAS,
    FUEL_TYPE_JET_A,
    FUEL_TYPE_JET_B,
    FUEL_TYPE_DIESEL,
    FUEL_TYPE_NONE,
]

# Fuel density constants at 15°C (59°F)
FUEL_DENSITY = {
    FUEL_TYPE_AVGAS: {
        "kg_per_liter": 0.72,
        "lbs_per_gallon_us": 6.0,
        "lbs_per_gallon_imperial": 7.2,
    },
    FUEL_TYPE_MOGAS: {
        "kg_per_liter": 0.75,
        "lbs_per_gallon_us": 6.25,
        "lbs_per_gallon_imperial": 7.5,
    },
    FUEL_TYPE_JET_A: {
        "kg_per_liter": 0.80,
        "lbs_per_gallon_us": 6.7,
        "lbs_per_gallon_imperial": 8.0,
    },
    FUEL_TYPE_JET_B: {
        "kg_per_liter": 0.77,
        "lbs_per_gallon_us": 6.4,
        "lbs_per_gallon_imperial": 7.7,
    },
    FUEL_TYPE_DIESEL: {
        "kg_per_liter": 0.84,
        "lbs_per_gallon_us": 7.0,
        "lbs_per_gallon_imperial": 8.4,
    },
    FUEL_TYPE_NONE: {
        "kg_per_liter": 0.0,
        "lbs_per_gallon_us": 0.0,
        "lbs_per_gallon_imperial": 0.0,
    },
}

# Fuel volume units
FUEL_UNIT_LITERS = "liters"
FUEL_UNIT_GALLONS_US = "gallons"
FUEL_UNIT_GALLONS_IMPERIAL = "gallons_imperial"

# Fuel defaults
DEFAULT_FUEL_RESERVE_MINUTES = 30  # Standard 30-minute reserve
DEFAULT_FUEL_PRICE_STALENESS_DAYS = 30  # Warn if price older than 30 days

# Setup Wizard Constants
SETUP_WIZARD_VERSION = "1.0"
SETUP_WIZARD_ENABLED = True  # Feature flag for setup wizard

# Welcome screen text
WELCOME_TITLE = "Welcome to Hangar Assistant!"
WELCOME_DESCRIPTION = """The complete aviation safety and operations integration for Home Assistant.

What You Can Do:
• Monitor airfield conditions (weather, density altitude)
• Track aircraft performance limits & safety margins
• Get AI-generated pre-flight safety briefings
• Receive alerts for unsafe flying conditions
• Calculate fuel costs & trip planning
• Manage weight & balance
• Log flights & maintenance

Setup Time: 10-15 minutes
"""

SETUP_STEPS = [
    "General Settings",
    "External Integrations",
    "Add First Airfield",
    "Add Hangar (Optional)",
    "Add First Aircraft",
    "Connect Weather Sensors",
    "Install Dashboard",
]

# Validation patterns for user input
ICAO_PATTERN = r"^[A-Z]{4}$"
UK_REG_PATTERN = r"^[A-Z]-[A-Z]{4}$"
US_REG_PATTERN = r"^[A-Z]\d{4,5}[A-Z]?$"
EU_REG_PATTERN = r"^[A-Z]{2}-[A-Z]{3}$"

# Default AI system prompt for aviation briefings
DEFAULT_AI_SYSTEM_PROMPT = """You are an aviation safety assistant specializing in pre-flight briefings and CAP 1590B compliance.

Your role:
- Provide clear, concise briefings for pilot decision-making this should include the current weather, aircraft performance considerations, legal compliance checks, and safety recommendations.
- Use up-to-date weather and performance data to inform your briefings.
- Highlight safety concerns and crosswind/performance limitations
- Reference configuration data (aircraft type, airfield, pilot qualifications)
- Suggest go/no-go decisions based on available data
- Always prioritize safety over operational convenience

Format:
- Use aviation units (height in feet, wind in knots, temperature in Celsius, distance in miles but weight and take of distance will be in SI units)
- Structure briefs as: WXBRIEF → PERFORMANCE → LEGAL → RECOMMENDATION
- Be direct and avoid aviation jargon when possible
- Flag any missing or outdated data"""
