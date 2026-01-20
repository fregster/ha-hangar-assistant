"""Tests for uncovered sensor implementations."""
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
    """Create mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    hass.bus = MagicMock()
    hass.config = MagicMock()
    hass.config.time_zone = "UTC"
    return hass


class TestDataFreshnessSensor:
    """Tests for DataFreshnessSensor."""

    def test_weather_data_age_calculation(self, mock_hass):
        """Test calculation of weather data age in minutes."""
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
        """Test age calculation for 30 minutes (threshold for stale)."""
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
        """Test when temp_sensor is not configured."""
        config = {"name": "Test Airfield"}
        sensor = DataFreshnessSensor(mock_hass, config)

        assert sensor.native_value is None

    def test_weather_data_age_sensor_unavailable(self, mock_hass):
        """Test when sensor state is unavailable."""
        config = {
            "name": "Test Airfield",
            "temp_sensor": "sensor.temp"
        }
        sensor = DataFreshnessSensor(mock_hass, config)
        mock_hass.states.get.return_value = None

        assert sensor.native_value is None

    def test_sensor_name(self, mock_hass):
        """Test sensor name property."""
        config = {"name": "Test Airfield", "temp_sensor": "sensor.temp"}
        sensor = DataFreshnessSensor(mock_hass, config)

        assert sensor.name == "Weather Data Age"

    def test_sensor_unit(self, mock_hass):
        """Test sensor unit of measurement."""
        config = {"name": "Test Airfield", "temp_sensor": "sensor.temp"}
        sensor = DataFreshnessSensor(mock_hass, config)

        assert sensor._attr_native_unit_of_measurement == "min"

    def test_freshness_status_and_threshold_defaults(self, mock_hass):
        """Ensure freshness status and threshold attributes use defaults."""
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
        """Ensure custom stale threshold is reflected in status calculation."""
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
    """Tests for AIBriefingSensor."""

    def test_initial_state_waiting(self, mock_hass):
        """Test initial state is 'Waiting'."""
        config = {"name": "Test Airfield"}
        sensor = AIBriefingSensor(mock_hass, config)

        assert sensor.native_value == "Waiting"

    def test_briefing_initial_message(self, mock_hass):
        """Test default briefing message."""
        config = {"name": "Test Airfield"}
        sensor = AIBriefingSensor(mock_hass, config)

        # Check internal state
        assert sensor._briefing_text == "Waiting for first briefing..."

    def test_sensor_name(self, mock_hass):
        """Test sensor name."""
        config = {"name": "Test Airfield"}
        sensor = AIBriefingSensor(mock_hass, config)

        assert sensor.name == "AI Pre-flight Briefing"

    def test_sensor_icon(self, mock_hass):
        """Test sensor icon."""
        config = {"name": "Test Airfield"}
        sensor = AIBriefingSensor(mock_hass, config)

        assert sensor._attr_icon == "mdi:robot"


class TestDensityAltitudeBanner:
    """Tests for density altitude banner attributes."""

    def test_da_banner_caution_level(self, mock_hass):
        """DA banner flags elevated level when above caution threshold."""
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
        """DA banner flags high level when above warning threshold."""
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
    """Tests for icing advisory strip."""

    def test_frost_risk_advisory(self, mock_hass):
        """Flags frost risk when temp near freezing and saturated."""
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
        """Flags airframe icing potential in visible moisture band."""
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
        """Falls back to carb icing state when no frost/airframe triggers."""
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
    """Tests for daylight countdown sensor."""

    def test_daylight_remaining(self, mock_hass):
        """Counts down to legal daylight end when above horizon."""
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
        """Counts down to legal daylight start when below horizon."""
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
    """Tests for AirfieldWeatherPassThrough."""

    def test_temperature_pass_through(self, mock_hass):
        """Test passing through temperature value."""
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
        """Test passing through dew point value."""
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
        """Test passing through wind speed value."""
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
        """Each pass-through sensor should have a distinct unique_id."""
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
        """Test returns None when sensor_key not in config."""
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
        """Test sensor name includes provided label."""
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
        """Test unit of measurement is set correctly."""
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
        """Test source entity is registered for updates."""
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
    """Tests for PilotInfoSensor."""

    def test_licence_type_as_native_value(self, mock_hass):
        """Test licence type is returned as native value."""
        config = {
            "name": "John Doe",
            "licence_type": "Commercial"
        }
        sensor = PilotInfoSensor(mock_hass, config)

        assert sensor.native_value == "Commercial"

    def test_pilot_attributes(self, mock_hass):
        """Test pilot information in attributes."""
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
        """Test sensor name."""
        config = {"name": "John Doe", "licence_type": "Private"}
        sensor = PilotInfoSensor(mock_hass, config)

        assert sensor.name == "Pilot Qualifications"

    def test_private_licence(self, mock_hass):
        """Test private licence type."""
        config = {
            "name": "Jane Smith",
            "licence_type": "Private"
        }
        sensor = PilotInfoSensor(mock_hass, config)

        assert sensor.native_value == "Private"

    def test_missing_licence_type(self, mock_hass):
        """Test when licence_type is missing."""
        config = {
            "name": "John Doe"
        }
        sensor = PilotInfoSensor(
            mock_hass, config
        )

        assert sensor.native_value is None

    def test_missing_email_in_attributes(self, mock_hass):
        """Test when email is not configured."""
        config = {
            "name": "John Doe",
            "licence_type": "Commercial"
        }
        sensor = PilotInfoSensor(mock_hass, config)
        attrs = sensor.extra_state_attributes

        assert attrs["email"] is None

    def test_missing_licence_number_in_attributes(self, mock_hass):
        """Test when licence number is not configured."""
        config = {
            "name": "John Doe",
            "licence_type": "Commercial"
        }
        sensor = PilotInfoSensor(mock_hass, config)
        attrs = sensor.extra_state_attributes

        assert attrs["licence_number"] is None

    def test_missing_medical_expiry_in_attributes(self, mock_hass):
        """Test when medical expiry is not configured."""
        config = {
            "name": "John Doe",
            "licence_type": "Commercial"
        }
        sensor = PilotInfoSensor(mock_hass, config)
        attrs = sensor.extra_state_attributes

        assert attrs["medical_expiry"] is None


class TestAirfieldTimezoneSensor:
    """Tests for AirfieldTimezoneSensor."""

    def test_timezone_from_coordinates(self, mocker, mock_hass):
        """Return timezone from coordinate lookup when available."""
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
        """Fall back to Home Assistant timezone when lookup fails or no coords."""
        config = {"name": "Test Airfield"}
        mock_hass.config.time_zone = "Europe/Paris"
        mocker.patch("custom_components.hangar_assistant.sensor._TZ_FINDER", None)

        sensor = AirfieldTimezoneSensor(mock_hass, config)
        assert sensor.native_value == "Europe/Paris"
        assert sensor.extra_state_attributes.get("source") == "home_assistant"

    def test_timezone_final_fallback_utc(self, mocker, mock_hass):
        """Fallback to UTC when no HA timezone is configured."""
        config = {"name": "Test Airfield"}
        mock_hass.config.time_zone = None
        mocker.patch("custom_components.hangar_assistant.sensor._TZ_FINDER", None)

        sensor = AirfieldTimezoneSensor(mock_hass, config)
        assert sensor.native_value == "UTC"
        assert sensor.extra_state_attributes.get("source") == "utc_fallback"

    def test_ratings_defaults_false(self, mock_hass):
        """Ratings should default to False when not provided."""
        config = {
            "name": "John Doe",
            "licence_type": "Commercial"
        }
        sensor = PilotInfoSensor(mock_hass, config)
        ratings = sensor.extra_state_attributes["ratings"]

        assert all(value is False for value in ratings.values())

    def test_ratings_respect_config(self, mock_hass):
        """Ratings should reflect provided configuration flags."""
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
