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
)


@pytest.fixture
def mock_hass():
    """Create mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    hass.bus = MagicMock()
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
