"""Tests for sensor entity implementations and attributes.

This module validates sensor creation, state calculation, and attribute
handling across all sensor types in the Hangar Assistant integration.

Test Strategy:
    - Mock Home Assistant core components (hass, states, config)
    - Test each sensor class individually with focused scenarios
    - Validate state computation, attributes, and device info
    - Test edge cases (missing sensors, unavailable data, fallbacks)

Coverage:
    - DataFreshnessSensor: Weather data age tracking
    - AIBriefingSensor: Pre-flight briefing state
    - DensityAltSensor: Density altitude banners and thresholds
    - IcingAdvisorySensor: Frost, airframe, carb icing detection
    - DaylightCountdownSensor: Legal daylight calculations
    - AirfieldWeatherPassThrough: Sensor value forwarding
    - PilotInfoSensor: Pilot qualification tracking
    - AirfieldTimezoneSensor: Timezone detection with fallbacks

Aviation Safety Context:
    - Data freshness critical for safe decision-making (30-min threshold)
    - Density altitude affects aircraft performance (caution/warning levels)
    - Icing conditions pose significant hazard (frost/airframe/carb)
    - Legal daylight restrictions for VFR flight
"""
import pytest
from unittest.mock import MagicMock
from datetime import timedelta
from homeassistant.util import dt as dt_util
from homeassistant.core import HomeAssistant
from custom_components.hangar_assistant.sensor import (
    DataFreshnessSensor,
    AIBriefingSensor,
    AirfieldWeatherPassThrough,
    PilotInfoSensor,
    AirfieldTimezoneSensor,
    DensityAltSensor,
    IcingAdvisorySensor,
    DaylightCountdownSensor,
)
from custom_components.hangar_assistant.const import (
    DEFAULT_STALE_WEATHER_MINUTES,
    DEFAULT_DA_CAUTION_FT,
    DEFAULT_DA_WARNING_FT,
    DEFAULT_FROST_TEMP_C,
    DEFAULT_AIRFRAME_ICING_MAX_C,
    DEFAULT_AIRFRAME_ICING_MIN_C,
    DEFAULT_SATURATION_SPREAD_C,
)

@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance for sensor testing.
    
    Provides:
        - Mock hass instance with state machine configured
        - Mock bus for event handling
        - Mock config with UTC timezone
        - No actual sensors or integrations loaded
    
    Used By:
        - All sensor test classes in this module
        - Tests requiring sensor state lookups
    
    The UTC timezone default ensures predictable datetime calculations
    for daylight countdown and timestamp-based sensors.
    
    Returns:
        MagicMock: Configured Home Assistant instance mock
    """
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    hass.bus = MagicMock()
    hass.config = MagicMock()
    hass.config.time_zone = "UTC"
    return hass


class TestDataFreshnessSensor:
    """Test suite for weather data age tracking sensor.
    
    Tests the DataFreshnessSensor which monitors how long weather data
    has been stale. Critical for aviation safety - decisions based on
    old weather can be dangerous (wind shifts, visibility changes).
    
    Test Approach:
        - Mock sensor states with specific last_updated timestamps
        - Calculate age in minutes from mocked timestamps
        - Validate status transitions (fresh → stale at 30-minute threshold)
    
    Scenarios Covered:
        - Recent data (< 30 minutes): status="fresh"
        - Stale data (≥ 30 minutes): status="stale"
        - Missing sensor configuration
        - Unavailable sensor states
        - Custom stale thresholds
    
    Aviation Context:
        Weather can change rapidly. Default 30-minute threshold aligns
        with METAR update frequency and safety best practices.
    """

    def test_weather_data_age_calculation(self, mock_hass):
        """Test accurate calculation of weather data age in minutes.
        
        This test validates the core functionality of the DataFreshnessSensor:
        measuring how many minutes have elapsed since weather data was updated.
        
        Scenario:
            - Temperature sensor updated 10 minutes ago
            - Current time is "now"
            - Expected age: 10 minutes
        
        Setup:
            - Mock temp_sensor with last_updated = now - 10 minutes
            - Sensor configured to monitor temp_sensor
        
        Validation:
            - Asserts sensor.native_value == 10
            - Confirms accurate timedelta calculation
        
        Expected Result:
            Sensor reports 10 minutes age, allowing pilots to assess
            whether weather data is current enough for safe decisions.
        """
        config = {
            "name": "Test Airfield",
            "temp_sensor": "sensor.temp"
        }
        sensor = DataFreshnessSensor(mock_hass, config)

        # Mock state with last_updated 10 minutes ago
        now = dt_util.utcnow()
        ten_mins_ago = now - timedelta(minutes=10)
        mock_state = MagicMock()
        mock_state.last_updated = ten_mins_ago
        mock_hass.states.get.return_value = mock_state

        assert sensor.native_value == 10

    def test_weather_data_age_30_minutes(self, mock_hass):
        """Test age calculation at 30-minute threshold (stale boundary).
        
        This test validates behavior at the critical threshold where
        weather data transitions from "fresh" to "stale" status.
        
        Scenario:
            - Temperature sensor updated exactly 30 minutes ago
            - Default stale threshold: 30 minutes (DEFAULT_STALE_WEATHER_MINUTES)
            - Expected: Data is now considered stale
        
        Setup:
            - Mock temp_sensor with last_updated = now - 30 minutes
            - Sensor uses default stale threshold
        
        Validation:
            - Asserts sensor.native_value == 30
            - Confirms accurate calculation at boundary condition
        
        Expected Result:
            Sensor reports 30 minutes age. At this threshold, status
            attribute transitions to "stale" and safety alerts may trigger.
        """
        config = {
            "name": "Test Airfield",
            "temp_sensor": "sensor.temp"
        }
        sensor = DataFreshnessSensor(mock_hass, config)

        now = dt_util.utcnow()
        thirty_mins_ago = now - timedelta(minutes=30)
        mock_state = MagicMock()
        mock_state.last_updated = thirty_mins_ago
        mock_hass.states.get.return_value = mock_state

        assert sensor.native_value == 30

    def test_weather_data_age_no_sensor(self, mock_hass):
        """Test graceful handling when temp_sensor not configured.
        
        This test validates backward compatibility and partial configuration
        handling - sensor should not crash if monitoring is disabled.
        
        Scenario:
            - Airfield configured without temp_sensor
            - DataFreshnessSensor instantiated
            - No sensor to monitor
        
        Setup:
            - Config contains only airfield name
            - No temp_sensor key in config
        
        Validation:
            - Asserts sensor.native_value is None
            - Confirms no AttributeError or KeyError raised
        
        Expected Result:
            Sensor returns None gracefully, allowing rest of system
            to function. Freshness monitoring simply disabled for this airfield.
        """
        config = {"name": "Test Airfield"}
        sensor = DataFreshnessSensor(mock_hass, config)

        assert sensor.native_value is None

    def test_weather_data_age_sensor_unavailable(self, mock_hass):
        """Test handling when referenced sensor state is unavailable.
        
        This test validates resilience against common sensor failures:
        offline sensors, integration errors, or temporary unavailability.
        
        Scenario:
            - temp_sensor configured but state lookup returns None
            - Sensor state machine has no entry for entity_id
            - Expected: Graceful None return
        
        Setup:
            - Config has temp_sensor = "sensor.temp"
            - mock_hass.states.get returns None (unavailable)
        
        Validation:
            - Asserts sensor.native_value is None
            - Confirms no exception raised on missing state
        
        Expected Result:
            Sensor returns None when data unavailable. This prevents
            false "data is fresh" signals when sensor is actually offline.
        """
        config = {
            "name": "Test Airfield",
            "temp_sensor": "sensor.temp"
        }
        sensor = DataFreshnessSensor(mock_hass, config)
        mock_hass.states.get.return_value = None

        assert sensor.native_value is None

    def test_sensor_name(self, mock_hass):
        """Test sensor name property is correctly set.
        
        Validates sensor entity naming convention for UI display.
        
        Setup:
            - Airfield named "Test Airfield"
            - DataFreshnessSensor instantiated
        
        Validation:
            - Asserts sensor.name == "Weather Data Age"
            - Confirms consistent naming across all instances
        
        Expected Result:
            Sensor appears as "Weather Data Age" in Home Assistant UI,
            making it clear what the sensor monitors.
        """
        config = {"name": "Test Airfield", "temp_sensor": "sensor.temp"}
        sensor = DataFreshnessSensor(mock_hass, config)

        assert sensor.name == "Weather Data Age"

    def test_sensor_unit(self, mock_hass):
        """Test sensor unit of measurement is minutes.
        
        Validates proper unit assignment for time-based sensor.
        
        Setup:
            - DataFreshnessSensor configured
        
        Validation:
            - Asserts unit == "min"
            - Confirms UI will display values as minutes
        
        Expected Result:
            Sensor state displays with "min" suffix (e.g., "10 min"),
            providing clear indication of time elapsed.
        """
        config = {"name": "Test Airfield", "temp_sensor": "sensor.temp"}
        sensor = DataFreshnessSensor(mock_hass, config)

        assert sensor._attr_native_unit_of_measurement == "min"

    def test_freshness_status_and_threshold_defaults(self, mock_hass):
        """Test freshness status uses default threshold (30 minutes).
        
        This test validates the status attribute which provides a
        human-readable "fresh" or "stale" designation based on age.
        
        Scenario:
            - Weather data 2 minutes old (well within threshold)
            - Default stale threshold: 30 minutes
            - Expected status: "fresh"
        
        Setup:
            - Mock temp_sensor updated 2 minutes ago
            - No custom stale_weather_minutes setting (use default)
        
        Validation:
            - Asserts attrs["status"] == "fresh"
            - Asserts attrs["threshold_minutes"] == DEFAULT_STALE_WEATHER_MINUTES
            - Confirms default value used correctly
        
        Expected Result:
            Status is "fresh" for recent data, threshold attribute shows
            30 minutes so users understand the boundary.
        """
        config = {"name": "Test Airfield", "temp_sensor": "sensor.temp"}
        sensor = DataFreshnessSensor(mock_hass, config)

        now = dt_util.utcnow()
        two_mins_ago = now - timedelta(minutes=2)
        mock_state = MagicMock()
        mock_state.last_updated = two_mins_ago
        mock_hass.states.get.return_value = mock_state

        attrs = sensor.extra_state_attributes
        assert attrs["status"] == "fresh"
        assert attrs["threshold_minutes"] == DEFAULT_STALE_WEATHER_MINUTES

    def test_freshness_status_respects_custom_threshold(self, mock_hass):
        """Test custom stale threshold is honored in status calculation.
        
        This test validates user-configurable stale thresholds,
        allowing pilots to set stricter or more lenient freshness criteria.
        
        Scenario:
            - Custom threshold: 20 minutes (stricter than default 30)
            - Weather data 25 minutes old
            - Expected status: "stale" (exceeds custom threshold)
        
        Setup:
            - Mock temp_sensor updated 25 minutes ago
            - Settings: stale_weather_minutes = 20
        
        Validation:
            - Asserts attrs["status"] == "stale"
            - Asserts attrs["threshold_minutes"] == 20
            - Confirms custom threshold applied to status logic
        
        Expected Result:
            Data that would be "fresh" with default threshold (25 < 30)
            is correctly flagged as "stale" with custom 20-minute threshold.
        """
        config = {"name": "Test Airfield", "temp_sensor": "sensor.temp"}
        sensor = DataFreshnessSensor(mock_hass, config, {"stale_weather_minutes": 20})

        now = dt_util.utcnow()
        twenty_five_mins_ago = now - timedelta(minutes=25)
        mock_state = MagicMock()
        mock_state.last_updated = twenty_five_mins_ago
        mock_hass.states.get.return_value = mock_state

        attrs = sensor.extra_state_attributes
        assert attrs["status"] == "stale"
        assert attrs["threshold_minutes"] == 20


class TestAIBriefingSensor:
    """Test suite for AI-generated pre-flight briefing sensor.
    
    Tests the AIBriefingSensor which holds AI-generated briefings
    summarizing weather, NOTAMs, and safety considerations.
    
    Test Approach:
        - Validate initial state (before first briefing generated)
        - Check sensor properties (name, icon, state)
        - Verify default message content
    
    Scenarios Covered:
        - Initial "Waiting" state
        - Default briefing text
        - Sensor naming and iconography
    """

    def test_initial_state_waiting(self, mock_hass):
        """Test initial state is 'Waiting' before first briefing generated.
        
        Validates sensor initialization state before AI generates first briefing.
        
        Setup:
            - AIBriefingSensor instantiated with airfield config
            - No briefing generated yet
        
        Validation:
            - Asserts sensor.native_value == "Waiting"
        
        Expected Result:
            Sensor displays "Waiting" state in UI until first scheduled
            briefing is generated by AI service.
        """
        config = {"name": "Test Airfield"}
        sensor = AIBriefingSensor(mock_hass, config)

        assert sensor.native_value == "Waiting"

    def test_briefing_initial_message(self, mock_hass):
        """Test default briefing message before first generation.
        
        Validates internal briefing text storage initialization.
        
        Setup:
            - AIBriefingSensor instantiated
            - No briefing generated
        
        Validation:
            - Asserts _briefing_text == "Waiting for first briefing..."
        
        Expected Result:
            Internal state holds placeholder message that will be
            replaced when AI generates actual briefing content.
        """
        config = {"name": "Test Airfield"}
        sensor = AIBriefingSensor(mock_hass, config)

        # Check internal state
        assert sensor._briefing_text == "Waiting for first briefing..."

    def test_sensor_name(self, mock_hass):
        """Test sensor name is properly formatted for UI.
        
        Validates entity naming convention.
        
        Validation:
            - Asserts sensor.name == "AI Pre-flight Briefing"
        
        Expected Result:
            Sensor appears with clear, descriptive name in UI.
        """
        config = {"name": "Test Airfield"}
        sensor = AIBriefingSensor(mock_hass, config)

        assert sensor.name == "AI Pre-flight Briefing"

    def test_sensor_icon(self, mock_hass):
        """Test sensor uses robot icon to indicate AI generation.
        
        Validates icon assignment for visual identification.
        
        Validation:
            - Asserts icon == "mdi:robot"
        
        Expected Result:
            Sensor displays robot icon in UI, clearly indicating
            this is an AI-generated content sensor.
        """
        config = {"name": "Test Airfield"}
        sensor = AIBriefingSensor(mock_hass, config)

        assert sensor._attr_icon == "mdi:robot"


class TestDensityAltitudeBanner:
    """Test suite for density altitude warning banners.
    
    Tests the DensityAltSensor's banner attributes which provide
    visual warnings about elevated density altitude conditions.
    
    Test Approach:
        - Mock temperature and pressure sensors with extreme values
        - Calculate density altitude internally
        - Validate banner severity levels (normal/caution/warning)
    
    Scenarios Covered:
        - Elevated DA (above caution threshold): severity="caution"
        - High DA (above warning threshold): severity="warning"
        - Threshold attributes present in sensor
    
    Aviation Context:
        High density altitude = reduced aircraft performance.
        - Caution threshold: 1000 ft above field elevation
        - Warning threshold: 2000 ft above field elevation
        Critical for takeoff/landing safety calculations.
    """

    def test_da_banner_caution_level(self, mock_hass):
        """Test DA banner shows caution severity for elevated density altitude.
        
        This test validates the warning system for moderately high density
        altitude conditions that affect aircraft performance.
        
        Scenario:
            - Temperature: 40°C (extremely hot)
            - Pressure: 1013.25 hPa (standard)
            - Elevation: Sea level
            - Calculated DA: ~7000 ft (well above caution threshold)
        
        Setup:
            - Mock temp=40°C, pressure=1013.25 hPa
            - DensityAltSensor at sea level elevation
        
        Validation:
            - Asserts da_status == "Elevated DA"
            - Asserts da_severity == "caution"
            - Confirms thresholds present in attributes
        
        Expected Result:
            Banner displays caution-level warning. Pilot alerted that
            aircraft performance is degraded (longer takeoff roll,
            reduced climb rate) but within manageable limits.
        """
        config = {
            "name": "Test Airfield",
            "temp_sensor": "sensor.temp",
            "pressure_sensor": "sensor.pressure",
            "elevation": 0,
        }
        sensor = DensityAltSensor(mock_hass, config, {})

        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.temp": MagicMock(state="40"),
            "sensor.pressure": MagicMock(state="1013.25"),
        }.get(entity_id)

        attrs = sensor.extra_state_attributes
        assert attrs["da_status"] == "Elevated DA"
        assert attrs["da_severity"] == "caution"
        assert attrs["da_caution_threshold_ft"] == DEFAULT_DA_CAUTION_FT
        assert attrs["da_warning_threshold_ft"] == DEFAULT_DA_WARNING_FT

    def test_da_banner_warning_level(self, mock_hass):
        """Test DA banner shows warning severity for dangerously high density altitude.
        
        This test validates critical warnings for extreme density altitude
        conditions that pose significant safety risks.
        
        Scenario:
            - Temperature: 60°C (extremely hot - edge case)
            - Pressure: 1013.25 hPa (standard)
            - Elevation: 150m (495 ft)
            - Calculated DA: ~11,400 ft (well above warning threshold)
        
        Setup:
            - Mock temp=60°C, pressure=1013.25 hPa
            - DensityAltSensor at 150m elevation
        
        Validation:
            - Asserts da_status == "High DA"
            - Asserts da_severity == "warning"
        
        Expected Result:
            Banner displays warning-level alert. Pilot strongly cautioned
            that aircraft performance is severely degraded - consider
            delaying flight or reducing weight.
        """
        config = {
            "name": "Test Airfield",
            "temp_sensor": "sensor.temp",
            "pressure_sensor": "sensor.pressure",
            "elevation": 150,
        }
        sensor = DensityAltSensor(mock_hass, config, {})

        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.temp": MagicMock(state="60"),
            "sensor.pressure": MagicMock(state="1013.25"),
        }.get(entity_id)

        attrs = sensor.extra_state_attributes
        assert attrs["da_status"] == "High DA"
        assert attrs["da_severity"] == "warning"


class TestIcingAdvisorySensor:
    """Test suite for icing hazard detection sensor.
    
    Tests the IcingAdvisorySensor which detects three types of icing
    hazards: frost risk, airframe icing, and carburetor icing.
    
    Test Approach:
        - Mock temperature and dew point sensors
        - Calculate temperature-dewpoint spread
        - Reference carb risk sensor for fallback
        - Validate severity levels and advisory messages
    
    Scenarios Covered:
        - Frost risk: temp ≤ 2°C and spread ≤ 1°C → severity="caution"
        - Airframe icing: -10°C ≤ temp ≤ 10°C and visible moisture → severity="warning"
        - Carburetor icing: fallback to carb risk sensor state
    
    Aviation Context:
        Icing is one of the most dangerous weather hazards:
        - Frost prevents smooth airflow over wings
        - Airframe ice increases weight, disrupts lift
        - Carb ice causes engine power loss
        All three can be fatal if not detected early.
    """

    def test_frost_risk_advisory(self, mock_hass):
        """Test frost risk detection when temperature near freezing and saturated.
        
        This test validates frost risk detection, critical for aircraft safety
        as frost on wings prevents takeoff.
        
        Scenario:
            - Temperature: 2°C (just above freezing)
            - Dew point: 1°C (spread = 1°C, nearly saturated)
            - Carb risk: Low (not a factor)
            - Expected: Frost Risk advisory
        
        Setup:
            - Mock temp_sensor = 2.0°C
            - Mock dp_sensor = 1.0°C
            - Mock carb_risk_sensor = "Low Risk"
        
        Validation:
            - Asserts native_value == "Frost Risk"
            - Asserts severity == "caution"
            - Confirms threshold attributes present
        
        Expected Result:
            Advisory warns of frost formation risk. Pilot must inspect
            aircraft for frost before departure - takeoff with frost is illegal
            and dangerous (disrupts lift, can cause stall on takeoff).
        """
        config = {
            "name": "Test Airfield",
            "temp_sensor": "sensor.temp",
            "dp_sensor": "sensor.dp",
        }
        sensor = IcingAdvisorySensor(mock_hass, config, {})

        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.temp": MagicMock(state="2.0"),
            "sensor.dp": MagicMock(state="1.0"),
            "sensor.test_airfield_carb_risk": MagicMock(state="Low Risk"),
        }.get(entity_id)

        assert sensor.native_value == "Frost Risk"
        attrs = sensor.extra_state_attributes
        assert attrs["severity"] == "caution"
        assert attrs["frost_temp_threshold_c"] == DEFAULT_FROST_TEMP_C
        assert attrs["saturation_spread_threshold_c"] == DEFAULT_SATURATION_SPREAD_C

    def test_airframe_icing_potential(self, mock_hass):
        """Test airframe icing detection in visible moisture temperature band.
        
        This test validates detection of conditions conducive to in-flight
        airframe icing, one of aviation's most serious hazards.
        
        Scenario:
            - Temperature: 4.5°C (within airframe icing band)
            - Dew point: 2.0°C (spread = 2.5°C, visible moisture likely)
            - Carb risk: Low
            - Expected: Airframe Icing Potential warning
        
        Setup:
            - Mock temp_sensor = 4.5°C
            - Mock dp_sensor = 2.0°C
            - Temperature within -10°C to 10°C range (DEFAULT_AIRFRAME_ICING)
        
        Validation:
            - Asserts native_value == "Airframe Icing Potential"
            - Asserts severity == "warning" (more serious than frost)
            - Confirms icing temperature range in attributes
        
        Expected Result:
            Warning level advisory issued. Pilot alerted that visible moisture
            (clouds, rain, fog) at this temperature will cause ice accumulation
            on airframe. VFR flight should avoid clouds; IFR requires ice protection.
        """
        config = {
            "name": "Test Airfield",
            "temp_sensor": "sensor.temp",
            "dp_sensor": "sensor.dp",
        }
        sensor = IcingAdvisorySensor(mock_hass, config, {})

        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.temp": MagicMock(state="4.5"),
            "sensor.dp": MagicMock(state="2.0"),
            "sensor.test_airfield_carb_risk": MagicMock(state="Low Risk"),
        }.get(entity_id)

        assert sensor.native_value == "Airframe Icing Potential"
        attrs = sensor.extra_state_attributes
        assert attrs["severity"] == "warning"
        assert attrs["airframe_icing_max_c"] == DEFAULT_AIRFRAME_ICING_MAX_C
        assert attrs["airframe_icing_min_c"] == DEFAULT_AIRFRAME_ICING_MIN_C

    def test_carb_icing_advisory(self, mock_hass):
        """Test fallback to carb icing when no frost/airframe conditions present.
        
        This test validates the sensor's priority logic: frost/airframe checks
        first, then fall back to carb icing advisory if neither triggered.
        
        Scenario:
            - Temperature: 15°C (too warm for frost/airframe icing)
            - Dew point: 8°C (spread = 7°C)
            - Carb risk: "Serious Risk" (from separate sensor)
            - Expected: Display carb icing state
        
        Setup:
            - Mock temp_sensor = 15°C (above icing thresholds)
            - Mock dp_sensor = 8°C
            - Mock carb_risk_sensor = "Serious Risk"
        
        Validation:
            - Asserts native_value == "Serious Carb Icing"
            - Asserts carb_risk_level attribute matches sensor state
        
        Expected Result:
            Sensor displays carburetor icing risk when other icing types
            not applicable. Provides unified icing advisory display with
            appropriate priority hierarchy.
        """
        config = {
            "name": "Test Airfield",
            "temp_sensor": "sensor.temp",
            "dp_sensor": "sensor.dp",
        }
        sensor = IcingAdvisorySensor(mock_hass, config, {})

        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.temp": MagicMock(state="15"),
            "sensor.dp": MagicMock(state="8"),
            "sensor.test_airfield_carb_risk": MagicMock(state="Serious Risk"),
        }.get(entity_id)

        assert sensor.native_value == "Serious Carb Icing"
        attrs = sensor.extra_state_attributes
        assert attrs["carb_risk_level"] == "Serious Risk"


class TestDaylightCountdownSensor:
    """Test suite for legal daylight countdown calculations.
    
    Tests the DaylightCountdownSensor which tracks minutes until
    legal daylight start/end for VFR flight planning.
    
    Test Approach:
        - Mock sun.sun entity with next_rising/next_setting times
        - Calculate countdown from current time to daylight boundary
        - Add 30-minute civil twilight buffer per aviation regulations
    
    Scenarios Covered:
        - Daytime (sun above horizon): countdown to daylight end
        - Nighttime (sun below horizon): countdown to daylight start
        - Phase attribute ("day" vs "night")
        - Legal daylight start/end timestamps
    
    Aviation Context:
        VFR flight restrictions: flight must end 30 minutes after sunset
        or begin 30 minutes before sunrise (civil twilight buffer).
        Critical for flight planning compliance.
    """

    def test_daylight_remaining(self, mock_hass):
        """Test countdown to legal daylight end during daytime hours.
        
        This test validates the sensor's core functionality during daylight:
        calculating minutes until VFR flight must end (30 min after sunset).
        
        Scenario:
            - Sun currently above horizon (daytime)
            - Sunset in 1 hour (60 minutes)
            - Legal daylight end: sunset + 30 minutes = 90 minutes
            - Expected countdown: ~90 minutes
        
        Setup:
            - Mock sun.sun state = "above_horizon"
            - next_setting = now + 1 hour
            - next_rising = now + 10 hours (tomorrow)
        
        Validation:
            - Asserts phase == "day"
            - Asserts legal_daylight_end timestamp present
            - Asserts countdown value between 80-95 minutes (allows timing variance)
        
        Expected Result:
            Sensor shows 90 minutes until legal daylight end. Pilot knows
            they have ~1.5 hours before VFR flight must conclude per regulations.
        """
        now = dt_util.utcnow()
        next_setting = (now + timedelta(hours=1)).isoformat()
        next_rising = (now + timedelta(hours=10)).isoformat()

        sun_state = MagicMock(state="above_horizon", attributes={"next_rising": next_rising, "next_setting": next_setting})

        config = {"name": "Test Airfield"}
        sensor = DaylightCountdownSensor(mock_hass, config, {})

        mock_hass.states.get.side_effect = lambda entity_id: sun_state if entity_id == "sun.sun" else None

        value = sensor.native_value
        attrs = sensor.extra_state_attributes

        assert attrs["phase"] == "day"
        assert attrs["legal_daylight_end"] is not None
        assert value is not None and value > 0
        assert 80 <= value <= 95  # ~90 minutes with small timing margin

    def test_night_until_daylight(self, mock_hass):
        """Test countdown to legal daylight start during nighttime hours.
        
        This test validates sensor behavior during night: calculating minutes
        until VFR flight may legally begin (30 min before sunrise).
        
        Scenario:
            - Sun currently below horizon (nighttime)
            - Sunrise in 2 hours (120 minutes)
            - Legal daylight start: sunrise - 30 minutes = 90 minutes from now
            - Expected countdown: ~90 minutes
        
        Setup:
            - Mock sun.sun state = "below_horizon"
            - next_rising = now + 2 hours
            - next_setting = now + 12 hours (this afternoon)
        
        Validation:
            - Asserts phase == "night"
            - Asserts legal_daylight_start timestamp present
            - Asserts countdown value between 80-125 minutes (allows variance)
        
        Expected Result:
            Sensor shows 90 minutes until legal daylight start. Pilot knows
            they have ~1.5 hours before VFR flight may commence per regulations.
        """
        now = dt_util.utcnow()
        next_rising = (now + timedelta(hours=2)).isoformat()
        next_setting = (now + timedelta(hours=12)).isoformat()

        sun_state = MagicMock(state="below_horizon", attributes={"next_rising": next_rising, "next_setting": next_setting})

        config = {"name": "Test Airfield"}
        sensor = DaylightCountdownSensor(mock_hass, config, {})

        mock_hass.states.get.side_effect = lambda entity_id: sun_state if entity_id == "sun.sun" else None

        value = sensor.native_value
        attrs = sensor.extra_state_attributes

        assert attrs["phase"] == "night"
        assert attrs["legal_daylight_start"] is not None
        assert value is not None and value > 0
        assert 80 <= value <= 125  # ~90 minutes with buffer


class TestAirfieldWeatherPassThrough:
    """Test suite for weather sensor pass-through entities.
    
    Tests the AirfieldWeatherPassThrough sensor which forwards values
    from external weather sensors to airfield-specific entities.
    
    Test Approach:
        - Mock external sensor states (temp, dew point, wind, pressure)
        - Instantiate pass-through sensor with sensor_key reference
        - Validate value forwarding and attribute handling
    
    Scenarios Covered:
        - Temperature pass-through
        - Dew point pass-through
        - Wind speed pass-through
        - Unique ID generation for each sensor type
        - Missing sensor configuration (returns None)
        - Unit of measurement preservation
        - Source entity registration for updates
    
    Design Pattern:
        This sensor pattern allows external weather sensors (from other
        integrations) to be referenced by airfield-specific calculations
        while maintaining proper device grouping.
    """

    def test_temperature_pass_through(self, mock_hass):
        """Test accurate forwarding of temperature sensor values.
        
        This test validates the basic pass-through mechanism: reading an
        external sensor state and exposing it as an airfield-specific entity.
        
        Scenario:
            - External temperature sensor reports 20.5°C
            - Pass-through sensor configured to monitor it
            - Expected: Value forwarded without modification
        
        Setup:
            - Mock external sensor.temp with state="20.5"
            - AirfieldWeatherPassThrough configured for temp_sensor
        
        Validation:
            - Asserts native_value == 20.5 (float)
            - Confirms value type conversion from string
        
        Expected Result:
            Temperature value accurately forwarded to airfield entity,
            allowing calculations (DA, carb risk) to reference local sensor.
        """
        config = {
            "name": "Test Airfield",
            "temp_sensor": "sensor.temp"
        }
        sensor = AirfieldWeatherPassThrough(
            mock_hass,
            config,
            "temp_sensor",
            "Temperature",
            device_class=None,
            unit="°C"
        )

        mock_hass.states.get.return_value = MagicMock(state="20.5")
        assert sensor.native_value == 20.5

    def test_dew_point_pass_through(self, mock_hass):
        """Test accurate forwarding of dew point sensor values.
        
        Validates pass-through for dew point, critical for icing risk
        and cloud base calculations.
        
        Scenario:
            - External dew point sensor reports 15.0°C
            - Expected: Value forwarded as float
        
        Setup:
            - Mock external sensor.dp with state="15.0"
            - AirfieldWeatherPassThrough configured for dp_sensor
        
        Validation:
            - Asserts native_value == 15.0
        
        Expected Result:
            Dew point forwarded for use in temperature-dewpoint spread
            calculations (carb icing, cloud base, frost risk).
        """
        config = {
            "name": "Test Airfield",
            "dp_sensor": "sensor.dp"
        }
        sensor = AirfieldWeatherPassThrough(
            mock_hass,
            config,
            "dp_sensor",
            "Dew Point",
            device_class=None,
            unit="°C"
        )

        mock_hass.states.get.return_value = MagicMock(state="15.0")
        assert sensor.native_value == 15.0

    def test_wind_speed_pass_through(self, mock_hass):
        """Test accurate forwarding of wind speed sensor values.
        
        Validates pass-through for wind speed, essential for runway
        selection and crosswind component calculations.
        
        Scenario:
            - External wind sensor reports 12 knots
            - Expected: Value forwarded as float
        
        Setup:
            - Mock external sensor.wind with state="12"
            - AirfieldWeatherPassThrough configured for wind_sensor
        
        Validation:
            - Asserts native_value == 12.0
        
        Expected Result:
            Wind speed forwarded for use in best runway calculations
            and crosswind component determinations.
        """
        config = {
            "name": "Test Airfield",
            "wind_sensor": "sensor.wind"
        }
        sensor = AirfieldWeatherPassThrough(
            mock_hass,
            config,
            "wind_sensor",
            "Wind Speed",
            device_class=None,
            unit="kt"
        )

        mock_hass.states.get.return_value = MagicMock(state="12")
        assert sensor.native_value == 12.0

    def test_weather_pass_through_unique_ids(self, mock_hass):
        """Test that each pass-through sensor has distinct unique_id.
        
        This test validates proper entity registration: each sensor type
        must have a unique identifier to prevent conflicts in HA registry.
        
        Scenario:
            - Two pass-through sensors for same airfield
            - Wind speed and wind direction
            - Expected: Different unique_ids
        
        Setup:
            - Create two AirfieldWeatherPassThrough instances
            - Same airfield, different sensor_keys and labels
        
        Validation:
            - Asserts speed.unique_id != direction.unique_id
            - Confirms unique_id generation incorporates label
        
        Expected Result:
            Each pass-through sensor has distinct unique_id, allowing
            proper entity registration without conflicts.
        """
        config = {
            "name": "Test Airfield",
            "wind_sensor": "sensor.wind",
            "wind_dir_sensor": "sensor.wind_dir"
        }

        speed = AirfieldWeatherPassThrough(
            mock_hass,
            config,
            "wind_sensor",
            "Wind Speed",
            device_class=None,
            unit="kt"
        )

        direction = AirfieldWeatherPassThrough(
            mock_hass,
            config,
            "wind_dir_sensor",
            "Wind Direction",
            device_class=None,
            unit="°"
        )

        assert speed._attr_unique_id != direction._attr_unique_id

    def test_missing_sensor_returns_none(self, mock_hass):
        """Test graceful handling when sensor_key not in configuration.
        
        This test validates backward compatibility: sensor should not crash
        if optional weather parameter is not configured.
        
        Scenario:
            - Airfield configured without temp_sensor
            - Pass-through sensor instantiated
            - Expected: Returns None gracefully
        
        Setup:
            - Config contains only airfield name
            - No temp_sensor key present
        
        Validation:
            - Asserts native_value is None
            - Confirms no KeyError raised
        
        Expected Result:
            Sensor returns None when source not configured. Dependent
            calculations handle None appropriately (skip or use fallback).
        """
        config = {"name": "Test Airfield"}
        sensor = AirfieldWeatherPassThrough(
            mock_hass,
            config,
            "temp_sensor",
            "Temperature",
            unit="°C"
        )

        assert sensor.native_value is None

    def test_sensor_name_includes_label(self, mock_hass):
        """Test sensor name incorporates the provided label for identification.
        
        Validates that sensor entities are clearly identifiable in UI
        by incorporating the weather parameter name.
        
        Setup:
            - Pass-through sensor configured with label="Temperature"
        
        Validation:
            - Asserts "Temperature" appears in sensor.name
        
        Expected Result:
            Sensor name includes parameter type (e.g., "Test Airfield Temperature"),
            making it clear what weather data is being monitored.
        """
        config = {"name": "Test Airfield", "temp_sensor": "sensor.temp"}
        sensor = AirfieldWeatherPassThrough(
            mock_hass,
            config,
            "temp_sensor",
            "Temperature",
            unit="°C"
        )

        assert "Temperature" in sensor.name

    def test_unit_of_measurement_set(self, mock_hass):
        """Test unit of measurement is correctly assigned from configuration.
        
        Validates that pass-through sensors preserve the unit of measurement
        from the source sensor for proper display and calculations.
        
        Setup:
            - Pass-through sensor configured with unit="°C"
        
        Validation:
            - Asserts native_unit_of_measurement == "°C"
        
        Expected Result:
            Sensor displays values with correct unit suffix in UI,
            and HA can perform proper unit conversions if configured.
        """
        config = {"name": "Test Airfield", "temp_sensor": "sensor.temp"}
        sensor = AirfieldWeatherPassThrough(
            mock_hass,
            config,
            "temp_sensor",
            "Temperature",
            unit="°C"
        )

        assert sensor._attr_native_unit_of_measurement == "°C"

    def test_sensor_registers_source_entity(self, mock_hass):
        """Test source entity is registered for state change updates.
        
        This test validates the update mechanism: pass-through sensor
        should listen to source sensor changes and update accordingly.
        
        Scenario:
            - Pass-through sensor configured to monitor sensor.pressure
            - Expected: sensor.pressure registered in _source_entities
        
        Setup:
            - AirfieldWeatherPassThrough configured with pressure_sensor
        
        Validation:
            - Asserts "sensor.pressure" in _source_entities list
            - Confirms update listener will be registered
        
        Expected Result:
            When source sensor updates, pass-through sensor automatically
            updates, ensuring real-time weather data reflection.
        """
        config = {
            "name": "Test Airfield",
            "pressure_sensor": "sensor.pressure"
        }
        sensor = AirfieldWeatherPassThrough(
            mock_hass,
            config,
            "pressure_sensor",
            "Pressure",
            unit="hPa"
        )

        assert "sensor.pressure" in sensor._source_entities


class TestPilotInfoSensor:
    """Test suite for pilot qualification tracking sensor.
    
    Tests the PilotInfoSensor which stores and displays pilot
    credentials, licence details, and ratings.
    
    Test Approach:
        - Mock pilot configuration with various credential combinations
        - Validate state (licence type) and attributes
        - Test handling of missing/optional fields
    
    Scenarios Covered:
        - Complete pilot profile (all fields present)
        - Missing optional fields (email, licence_number, medical_expiry)
        - Licence types (Private, Commercial)
        - Ratings flags (IFR, night, tailwheel, complex, multi-engine)
        - Default rating values (all False if not configured)
    
    Compliance Context:
        Pilot credentials determine legal flight operations:
        - Licence type: Private vs Commercial privileges
        - Ratings: Required for certain aircraft/conditions
        - Medical expiry: Mandatory for legal flight
    """

    def test_licence_type_as_native_value(self, mock_hass):
        """Test that pilot licence type is displayed as sensor state.
        
        This test validates the primary sensor value: licence type,
        which determines pilot privileges and legal operations.
        
        Setup:
            - Pilot configured with licence_type="Commercial"
        
        Validation:
            - Asserts sensor.native_value == "Commercial"
        
        Expected Result:
            Sensor state shows "Commercial" in UI, clearly indicating
            pilot's certification level at a glance.
        """
        config = {
            "name": "John Doe",
            "licence_type": "Commercial"
        }
        sensor = PilotInfoSensor(mock_hass, config)

        assert sensor.native_value == "Commercial"

    def test_pilot_attributes(self, mock_hass):
        """Test complete pilot profile is stored in sensor attributes.
        
        This test validates that all pilot credential fields are properly
        stored and accessible via sensor attributes.
        
        Scenario:
            - Complete pilot configuration with all optional fields
            - Name, email, licence number, medical expiry, licence type
        
        Setup:
            - Full pilot config with all credentials
        
        Validation:
            - Asserts pilot_name == "John Doe"
            - Asserts email == "john@example.com"
            - Asserts licence_number == "PL1234567"
            - Asserts medical_expiry == "2026-06-15"
        
        Expected Result:
            All pilot credentials accessible via attributes for use in
            automations, briefings, and CAP1590B PDF generation.
        """
        config = {
            "name": "John Doe",
            "email": "john@example.com",
            "licence_number": "PL1234567",
            "medical_expiry": "2026-06-15",
            "licence_type": "Commercial"
        }
        sensor = PilotInfoSensor(mock_hass, config)
        attrs = sensor.extra_state_attributes

        assert attrs["pilot_name"] == "John Doe"
        assert attrs["email"] == "john@example.com"
        assert attrs["licence_number"] == "PL1234567"
        assert attrs["medical_expiry"] == "2026-06-15"

    def test_sensor_name(self, mock_hass):
        """Test sensor name is consistently labeled.
        
        Validates UI display name for pilot sensor.
        
        Validation:
            - Asserts sensor.name == "Pilot Qualifications"
        
        Expected Result:
            Sensor appears as "Pilot Qualifications" in UI,
            clearly identifying its purpose.
        """
        sensor = PilotInfoSensor(mock_hass, config)

        assert sensor.name == "Pilot Qualifications"

    def test_private_licence(self, mock_hass):
        """Test Private Pilot Licence (PPL) display.
        
        Validates sensor handles PPL certification level.
        
        Setup:
            - Pilot configured with licence_type="Private"
        
        Validation:
            - Asserts native_value == "Private"
        
        Expected Result:
            Sensor displays "Private" indicating Private Pilot Licence,
            which permits non-commercial operations.
        """
        config = {
            "name": "Jane Smith",
            "licence_type": "Private"
        }
        sensor = PilotInfoSensor(mock_hass, config)

        assert sensor.native_value == "Private"

    def test_missing_licence_type(self, mock_hass):
        """Test graceful handling when licence type not configured.
        
        Validates backward compatibility for partial pilot profiles.
        
        Scenario:
            - Pilot configured with only name
            - No licence_type provided
        
        Setup:
            - Config with only "name" field
        
        Validation:
            - Asserts native_value is None
        
        Expected Result:
            Sensor returns None gracefully without crashing.
            Allows pilot entry creation before all details finalized.
        """
        config = {
            "name": "John Doe"
        }
        sensor = PilotInfoSensor(
            mock_hass, config
        )

        assert sensor.native_value is None

    def test_missing_email_in_attributes(self, mock_hass):
        """Test email attribute is None when not configured.
        
        Validates optional field handling for email address.
        
        Setup:
            - Pilot config without email field
        
        Validation:
            - Asserts attrs["email"] is None
        
        Expected Result:
            Missing optional fields default to None, allowing
            automations to check for presence before use.
        """
        config = {
            "name": "John Doe",
            "licence_type": "Commercial"
        }
        sensor = PilotInfoSensor(mock_hass, config)
        attrs = sensor.extra_state_attributes

        assert attrs["email"] is None

    def test_missing_licence_number_in_attributes(self, mock_hass):
        """Test licence_number attribute is None when not configured.
        
        Validates optional field handling for licence number.
        
        Setup:
            - Pilot config without licence_number field
        
        Validation:
            - Asserts attrs["licence_number"] is None
        
        Expected Result:
            Missing licence number returns None, allowing flexible
            pilot profile creation.
        """
        config = {
            "name": "John Doe",
            "licence_type": "Commercial"
        }
        sensor = PilotInfoSensor(mock_hass, config)
        attrs = sensor.extra_state_attributes

        assert attrs["licence_number"] is None

    def test_missing_medical_expiry_in_attributes(self, mock_hass):
        """Test medical_expiry attribute is None when not configured.
        
        Validates optional field handling for medical expiry date.
        
        Setup:
            - Pilot config without medical_expiry field
        
        Validation:
            - Asserts attrs["medical_expiry"] is None
        
        Expected Result:
            Missing medical expiry returns None. While medical certificates
            are mandatory for legal flight, this allows pilots to be configured
            before obtaining medical certification.
        """
        config = {
            "name": "John Doe",
            "licence_type": "Commercial"
        }
        sensor = PilotInfoSensor(mock_hass, config)
        attrs = sensor.extra_state_attributes

        assert attrs["medical_expiry"] is None


class TestAirfieldTimezoneSensor:
    """Test suite for airfield timezone detection sensor.
    
    Tests the AirfieldTimezoneSensor which determines local timezone
    for airfield coordinates with multiple fallback levels.
    
    Test Approach:
        - Mock timezonefinder library lookup
        - Test coordinate-based timezone detection
        - Validate fallback chain to HA timezone then UTC
    
    Scenarios Covered:
        - Successful coordinate lookup (e.g., 51.47°N, 0.45°W → Europe/London)
        - Fallback to Home Assistant timezone when lookup fails
        - Final fallback to UTC when no HA timezone configured
        - Source attribute tracking (airfield_coords, home_assistant, utc_fallback)
    
    Aviation Context:
        Accurate timezone critical for:
        - NOTAM validity periods
        - Daylight calculation (sunrise/sunset times)
        - Flight planning time conversions
        - Briefing timestamp interpretation
    """

    def test_timezone_from_coordinates(self, mocker, mock_hass):
        """Test timezone lookup from airfield coordinates succeeds.
        
        This test validates the primary timezone detection method:
        using lat/lon coordinates to determine local timezone.
        
        Scenario:
            - Airfield at 51.47°N, 0.45°W (near London)
            - timezonefinder library available
            - Expected: "Europe/London" timezone
        
        Setup:
            - Mock timezonefinder with fake lookup function
            - Airfield config with latitude/longitude
        
        Validation:
            - Asserts native_value == "Europe/London"
            - Asserts source attribute == "airfield_coords"
        
        Expected Result:
            Sensor accurately determines local timezone from coordinates,
            critical for NOTAM validity times and sunrise/sunset calculations.
        """
        config = {
            "name": "Test Airfield",
            "latitude": 51.47,
            "longitude": -0.45,
        }

        from types import SimpleNamespace
        fake_finder = SimpleNamespace(timezone_at=lambda lat, lng: "Europe/London")
        mocker.patch("custom_components.hangar_assistant.sensor._TZ_FINDER", fake_finder)

        sensor = AirfieldTimezoneSensor(mock_hass, config)
        assert sensor.native_value == "Europe/London"
        assert sensor.extra_state_attributes.get("source") == "airfield_coords"

    def test_timezone_falls_back_to_ha(self, mocker, mock_hass):
        """Test fallback to Home Assistant timezone when coordinate lookup fails.
        
        This test validates the first fallback level: using HA system timezone
        when timezonefinder is unavailable or coordinates not configured.
        
        Scenario:
            - Airfield configured without coordinates
            - timezonefinder not available (_TZ_FINDER = None)
            - HA system timezone: "Europe/Paris"
            - Expected: Use HA timezone
        
        Setup:
            - Mock _TZ_FINDER as None
            - mock_hass.config.time_zone = "Europe/Paris"
        
        Validation:
            - Asserts native_value == "Europe/Paris"
            - Asserts source == "home_assistant"
        
        Expected Result:
            Sensor falls back to HA timezone when coordinates unavailable.
            Reasonable default for local operations.
        """
        config = {"name": "Test Airfield"}
        mock_hass.config.time_zone = "Europe/Paris"
        mocker.patch("custom_components.hangar_assistant.sensor._TZ_FINDER", None)

        sensor = AirfieldTimezoneSensor(mock_hass, config)
        assert sensor.native_value == "Europe/Paris"
        assert sensor.extra_state_attributes.get("source") == "home_assistant"

    def test_timezone_final_fallback_utc(self, mocker, mock_hass):
        """Test final fallback to UTC when all other methods fail.
        
        This test validates the last-resort fallback: UTC when neither
        coordinate lookup nor HA timezone is available.
        
        Scenario:
            - No coordinates configured
            - timezonefinder unavailable
            - HA timezone not configured (None)
            - Expected: UTC fallback
        
        Setup:
            - Mock _TZ_FINDER as None
            - mock_hass.config.time_zone = None
        
        Validation:
            - Asserts native_value == "UTC"
            - Asserts source == "utc_fallback"
        
        Expected Result:
            Sensor defaults to UTC, ensuring system never crashes due to
            missing timezone. UTC is universal aviation standard.
        """
        config = {"name": "Test Airfield"}
        mock_hass.config.time_zone = None
        mocker.patch("custom_components.hangar_assistant.sensor._TZ_FINDER", None)

        sensor = AirfieldTimezoneSensor(mock_hass, config)
        assert sensor.native_value == "UTC"
        assert sensor.extra_state_attributes.get("source") == "utc_fallback"

    def test_ratings_defaults_false(self, mock_hass):
        """Test pilot ratings default to False when not configured.
        
        This test validates conservative defaults for pilot ratings:
        assume no additional certifications unless explicitly stated.
        
        Scenario:
            - Pilot configured with only name and licence_type
            - No rating flags provided
            - Expected: All ratings False
        
        Setup:
            - Pilot config without rating flags
        
        Validation:
            - Asserts all ratings dict values are False
        
        Expected Result:
            Ratings default to False, requiring explicit configuration.
            Conservative approach ensures pilots don't accidentally claim
            certifications they don't possess.
        """
        config = {
            "name": "John Doe",
            "licence_type": "Commercial"
        }
        sensor = PilotInfoSensor(mock_hass, config)
        ratings = sensor.extra_state_attributes["ratings"]

        assert all(value is False for value in ratings.values())

    def test_ratings_respect_config(self, mock_hass):
        """Test pilot ratings accurately reflect configuration flags.
        
        This test validates that configured ratings are correctly stored
        and retrievable via sensor attributes.
        
        Scenario:
            - Pilot with multiple ratings configured
            - Mix of True and False values
            - Expected: Each rating matches configuration
        
        Setup:
            - Full rating config:
              - IFR: True (Instrument Flight Rules)
              - Night: True (Night flying)
              - Tailwheel: True (Conventional gear)
              - Complex: False (Not certified)
              - Multi-engine: True (Multi-engine aircraft)
        
        Validation:
            - Asserts each rating matches configured value
        
        Expected Result:
            Ratings accurately stored for use in aircraft suitability
            checks and legal flight determination. Automations can verify
            pilot is qualified for specific aircraft/conditions.
        """
        config = {
            "name": "John Doe",
            "licence_type": "Commercial",
            "ifr_rating": True,
            "night_rating": True,
            "tailwheel_rating": True,
            "complex_rating": False,
            "multi_engine_rating": True,
        }
        sensor = PilotInfoSensor(mock_hass, config)
        ratings = sensor.extra_state_attributes["ratings"]

        assert ratings["ifr_rating"] is True
        assert ratings["night_rating"] is True
        assert ratings["tailwheel_rating"] is True
        assert ratings["complex_rating"] is False
        assert ratings["multi_engine_rating"] is True
