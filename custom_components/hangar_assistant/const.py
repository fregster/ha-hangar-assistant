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

# ADS-B Tracking Configuration Keys
CONF_ADSB = "adsb"
CONF_ADSB_ENABLED = "adsb_enabled"
CONF_ADSB_SOURCES = "adsb_sources"
CONF_ADSB_TRACKED_AIRCRAFT = "tracked_aircraft"
CONF_ADSB_AIRFIELD_TRAFFIC = "airfield_traffic"

# dump1090 Configuration (local ADS-B receiver)
CONF_DUMP1090_ENABLED = "dump1090_enabled"
CONF_DUMP1090_URL = "dump1090_url"  # Full URL to dump1090 JSON endpoint
CONF_DUMP1090_TIMEOUT = "dump1090_timeout"

# OpenSky Network Configuration (free API, ADS-B + FLARM)
CONF_OPENSKY_ENABLED = "opensky_enabled"
CONF_OPENSKY_USERNAME = "opensky_username"
CONF_OPENSKY_PASSWORD = "opensky_password"
CONF_OPENSKY_RATE_LIMIT_ANONYMOUS = "opensky_rate_limit_anonymous"
CONF_OPENSKY_RATE_LIMIT_AUTH = "opensky_rate_limit_auth"

# Open Gliding Network Configuration (free APRS, FLARM only)
CONF_OGN_ENABLED = "ogn_enabled"
CONF_OGN_CALLSIGN = "ogn_callsign"
CONF_OGN_APRS_SERVER = "ogn_aprs_server"
CONF_OGN_APRS_PORT = "ogn_aprs_port"
CONF_OGN_APRS_FILTER = "ogn_aprs_filter"
CONF_OGN_DDB_CACHE_HOURS = "ogn_ddb_cache_hours"

# ADS-B Exchange Configuration (RapidAPI, paid tiers)
CONF_ADSBEXCHANGE_ENABLED = "adsbexchange_enabled"
CONF_ADSBEXCHANGE_API_KEY = "adsbexchange_api_key"
CONF_ADSBEXCHANGE_RAPIDAPI_HOST = "adsbexchange_rapidapi_host"

# FlightRadar24 Configuration (paid API)
CONF_FR24_ENABLED = "fr24_enabled"
CONF_FR24_API_KEY = "fr24_api_key"

# FlightAware Configuration (paid API)
CONF_FLIGHTAWARE_ENABLED = "flightaware_enabled"
CONF_FLIGHTAWARE_API_KEY = "flightaware_api_key"

# ADS-B Defaults
DEFAULT_ADSB_ENABLED = False  # Opt-in feature
DEFAULT_ADSB_CACHE_TTL = 30  # seconds (aircraft positions update frequently)
DEFAULT_ADSB_UPDATE_INTERVAL = 10  # seconds between updates
DEFAULT_ADSB_MONITORING_RADIUS = 10  # nautical miles around airfield
DEFAULT_DUMP1090_URL = "http://localhost:8080/data/aircraft.json"  # Full URL to dump1090
DEFAULT_DUMP1090_TIMEOUT = 5  # seconds
DEFAULT_OPENSKY_ANONYMOUS_CREDITS_PER_DAY = 400  # OpenSky anonymous rate limit
DEFAULT_OPENSKY_AUTH_CREDITS_PER_DAY = 4000  # OpenSky authenticated rate limit
DEFAULT_OGN_APRS_SERVER = "aprs.glidernet.org"
DEFAULT_OGN_APRS_PORT = 14580
DEFAULT_OGN_CALLSIGN = "HA-HANGAR"  # Default APRS callsign
DEFAULT_OGN_DDB_CACHE_HOURS = 24  # Cache Device Database lookups for 24 hours
DEFAULT_ADSBEXCHANGE_RAPIDAPI_HOST = "adsbexchange-com1.p.rapidapi.com"

# ADS-B Data Source Priority (lower number = higher priority)
ADSB_PRIORITY_DUMP1090 = 1  # Local receiver (best accuracy, lowest latency)
ADSB_PRIORITY_OPENSKY = 2  # Free API, ADS-B + FLARM, 4000 credits with account
ADSB_PRIORITY_OGN = 3  # Free APRS, FLARM only, unlimited
ADSB_PRIORITY_ADSBEXCHANGE = 4  # Paid API, 500-1M requests
ADSB_PRIORITY_FR24 = 5  # Paid API
ADSB_PRIORITY_FLIGHTAWARE = 6  # Paid API

# Default enabled sources (free APIs enabled by default)
DEFAULT_ADSB_ENABLED_SOURCES = [
    "opensky",  # Free, enabled by default (400-4000 credits/day)
    "ogn",  # Free APRS, enabled by default (unlimited, FLARM only)
]

# ADS-B device tracker configuration
CONF_ADSB_TRACK_AIRCRAFT_BY_REG = "track_aircraft_by_registration"
CONF_ADSB_TRACK_AIRCRAFT_BY_ICAO = "track_aircraft_by_icao24"
CONF_ADSB_DEVICE_TRACKER_PREFIX = "adsb_aircraft"

# ADS-B sensor configuration
CONF_ADSB_TRAFFIC_SENSORS = "adsb_traffic_sensors"
CONF_ADSB_NEAREST_AIRCRAFT_SENSOR = "adsb_nearest_aircraft_sensor"
