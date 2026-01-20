"""Constants for the Hangar Assistant integration."""
from homeassistant.const import Platform

# The unique domain for the integration
DOMAIN = "hangar_assistant"

# The list of platforms supported by this integration
# In this version, we use 'sensor' for weather/performance and 'binary_sensor' for alerts.
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]

# Attribute constants used for legal and data tracking
ATTR_OLD_SOURCE = "oldest_source"
ATTR_LAST_CHECK = "last_check_utc"
ATTR_PILOT_NAME = "pilot_in_command"

# Default retention setting (months) as required by the CAA 6-month rule
DEFAULT_RETENTION_MONTHS = 7

# Dashboard version for tracking template updates
DEFAULT_DASHBOARD_VERSION = 2

# Unit preferences
UNIT_PREFERENCE_AVIATION = "aviation"  # Feet, knots, pounds
UNIT_PREFERENCE_SI = "si"  # Meters, kph, kilograms
DEFAULT_UNIT_PREFERENCE = UNIT_PREFERENCE_AVIATION

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