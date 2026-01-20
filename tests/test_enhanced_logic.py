"""Enhanced logic tests for Hangar Assistant."""
import pytest
from unittest.mock import MagicMock
from homeassistant.core import HomeAssistant
from custom_components.hangar_assistant.sensor import (
    BestRunwaySensor,
    GroundRollSensor,
    CarbRiskTransitionSensor,
    PrimaryRunwayCrosswindSensor,
    IdealRunwayCrosswindSensor,
    CarbRiskSensor
)
from custom_components.hangar_assistant.binary_sensor import (
    PilotMedicalAlert,
    HangarMasterSafetyAlert
)
from datetime import datetime, timedelta


@pytest.fixture
def mock_hass():
    """Create mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    return hass


def test_best_runway_selection(mock_hass):
    """Test runway selection based on wind direction."""
    config = {
        "name": "Test Airfield",
        "runways": "03, 21, 09, 27",
        "wind_dir_sensor": "sensor.wind_dir"
    }
    sensor = BestRunwaySensor(mock_hass, config)

    # Wind from 040 should pick 03
    mock_hass.states.get.return_value = MagicMock(state="40")
    assert sensor.native_value == "03"

    # Wind from 200 should pick 21
    mock_hass.states.get.return_value = MagicMock(state="200")
    assert sensor.native_value == "21"

    # Wind from 100 should pick 09
    mock_hass.states.get.return_value = MagicMock(state="100")
    assert sensor.native_value == "09"


def test_crosswind_calculations(mock_hass):
    """Test crosswind component calculations."""
    config = {
        "name": "Test Airfield",
        "primary_runway": "09",
        "runways": "09, 27",
        "wind_sensor": "sensor.wind_speed",
        "wind_dir_sensor": "sensor.wind_dir"
    }

    # Primary Crosswind (090 heading, wind 120 at 20kt)
    # Angle = 30 deg. sin(30) = 0.5. Xwind = 10kt.
    sensor_primary = PrimaryRunwayCrosswindSensor(mock_hass, config)

    def mock_get_state(entity_id):
        if entity_id == "sensor.wind_speed":
            return MagicMock(state="20")
        if entity_id == "sensor.wind_dir":
            return MagicMock(state="120")
        return None

    mock_hass.states.get.side_effect = mock_get_state
    assert sensor_primary.native_value == 10.0

    # Ideal Crosswind (09/27)
    sensor_ideal = IdealRunwayCrosswindSensor(mock_hass, config)
    assert sensor_ideal.native_value == 10.0


def test_ground_roll_adjustment(mock_hass):
    """Test ground roll adjustment based on Density Altitude."""
    config = {
        "reg": "G-TEST",
        "baseline_roll": 300,
        "linked_airfield": "Popham"
    }
    sensor = GroundRollSensor(mock_hass, config)

    # Mock DA sensor state
    mock_hass.states.get.return_value = MagicMock(state="2000")
    assert sensor.native_value == 360


def test_carb_risk_transition(mock_hass):
    """Test the altitude at which carb risk becomes moderate."""
    config = {
        "name": "Test Airfield",
        "temp_sensor": "sensor.temp",
        "dp_sensor": "sensor.dp"
    }
    sensor = CarbRiskTransitionSensor(mock_hass, config)

    def mock_get_state(entity_id):
        if entity_id == "sensor.temp":
            return MagicMock(state="35")
        if entity_id == "sensor.dp":
            return MagicMock(state="15")
        return None

    mock_hass.states.get.side_effect = mock_get_state
    assert sensor.native_value == 2500


def test_carb_risk_levels(mock_hass):
    """Test carb risk classification."""
    config = {
        "name": "Test Airfield",
        "temp_sensor": "sensor.temp",
        "dp_sensor": "sensor.dp"
    }
    sensor = CarbRiskSensor(mock_hass, config)

    def set_mock(t, dp):
        mock_hass.states.get.side_effect = lambda eid: {
            "sensor.temp": MagicMock(state=t),
            "sensor.dp": MagicMock(state=dp)
        }.get(eid)

    set_mock("20", "18")
    assert sensor.native_value == "Serious Risk"

    set_mock("28", "20")
    assert sensor.native_value == "Moderate Risk"

    set_mock("35", "30")
    assert sensor.native_value == "Low Risk"


def test_pilot_medical_alert(mock_hass):
    """Test medical expiry alert."""
    # Past date
    config_expired = {"medical_expiry": "2020-01-01"}
    sensor_expired = PilotMedicalAlert(mock_hass, config_expired)
    assert sensor_expired.is_on is True

    # Future date
    future_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
    config_valid = {"medical_expiry": future_date}
    sensor_valid = PilotMedicalAlert(mock_hass, config_valid)
    assert sensor_valid.is_on is False


def test_master_safety_alert(mock_hass):
    """Test the master safety alert combined logic."""
    config = {"name": "Test Airfield"}
    alert = HangarMasterSafetyAlert(mock_hass, config)

    # Mock sibling sensors
    alert._freshness_id = "sensor.test_airfield_weather_data_age"
    alert._carb_id = "sensor.test_airfield_carb_risk"

    def set_mock(fresh, risk):
        mock_hass.states.get.side_effect = lambda eid: {
            alert._freshness_id: MagicMock(state=fresh),
            alert._carb_id: MagicMock(state=risk)
        }.get(eid)

    # Case: Stale data
    set_mock("35", "Low Risk")
    assert alert.is_on is True

    # Case: Serious carb risk
    set_mock("5", "Serious Risk")
    assert alert.is_on is True

    # Case: All good
    set_mock("10", "Moderate Risk")
    assert alert.is_on is False
    future_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
    config_valid = {"medical_expiry": future_date}
    sensor_valid = PilotMedicalAlert(mock_hass, config_valid)
    assert sensor_valid.is_on is False
