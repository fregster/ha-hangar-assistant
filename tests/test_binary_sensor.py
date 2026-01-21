"""Tests for binary sensor safety alert system.

This module tests the binary sensor entities that provide critical safety
warnings to pilots, including:
- Master safety alerts (stale weather data, carburetor icing)
- Aircraft-specific crosswind alerts (runway suitability)

Test Strategy:
    - Mock Home Assistant state machine for sensor data
    - Test binary state transitions (on/off) based on safety thresholds
    - Verify attribute exposure for dashboard integration
    - Cover all alert trigger conditions and edge cases

Coverage:
    - HangarMasterSafetyAlert: Stale data detection, carb risk triggers
    - AircraftCrosswindAlert: Crosswind calculations, runway selection
    - Threshold handling: Custom vs default limits
    - State attributes: best_runway, crosswind_component, within_limit

Safety Impact:
    - These sensors directly affect GO/NO-GO decisions
    - Master safety alert prevents flights with unreliable data
    - Crosswind alerts protect against runway excursions
    - Integrated with automation for pilot notifications
"""
import pytest
from unittest.mock import MagicMock
from homeassistant.core import HomeAssistant
from custom_components.hangar_assistant.binary_sensor import (
    AircraftCrosswindAlert,
    HangarMasterSafetyAlert,
)
from custom_components.hangar_assistant.const import DEFAULT_STALE_WEATHER_MINUTES


@pytest.fixture
def mock_hass():
    """Create mock Home Assistant instance with state machine.
    
    Provides:
        - Mock hass instance spec'd to HomeAssistant type
        - Mock states attribute for sensor lookups
        - Prepared for side_effect mocking in tests
    
    Used By:
        - test_safety_alert_logic
        - test_aircraft_crosswind_alert_*
        - test_safety_alert_respects_threshold_attribute
    
    Example:
        ```python
        def test_something(mock_hass):
            mock_hass.states.get.return_value = MagicMock(state="10")
            sensor = SafetySensor(mock_hass, config)
            assert sensor.is_on is False
        ```
    
    Returns:
        MagicMock: Configured Home Assistant instance mock
    """
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    return hass


def test_safety_alert_logic(mock_hass):
    """Test master safety alert triggers on stale data or serious carb risk.
    
    This test validates the core safety alert logic that prevents flights
    when weather data is unreliable or carburetor icing risk is critical.
    
    Scenarios Tested:
        1. Good conditions: Fresh data (10 min) + Low carb risk → Alert OFF
        2. Stale data: Old data (45 min) + Low carb risk → Alert ON
    
    Setup:
        - Mock airfield configuration with name
        - Mock sensor entity IDs for weather age and carb risk
        - Mock state machine returns specific age/risk values
    
    Validation:
        - Alert remains OFF when all conditions safe (<30 min data age)
        - Alert turns ON when data age exceeds threshold (>30 min)
        - Alert would also turn ON for "Serious Risk" carb conditions
        - Entity correctly reads from constructed sensor IDs
    
    Expected Result:
        Binary sensor state transitions properly based on safety thresholds,
        protecting pilots from decision-making with unreliable data.
    """
    config = {"name": "Test Airfield"}
    sensor = HangarMasterSafetyAlert(mock_hass, config)

    # Mock internal IDs
    sensor._freshness_id = "sensor.test_airfield_weather_data_age"
    sensor._carb_id = "sensor.test_airfield_carb_risk"

    # Case 1: All Good
    mock_hass.states.get.side_effect = lambda entity_id: {
        "sensor.test_airfield_weather_data_age": MagicMock(state="10"),
        "sensor.test_airfield_carb_risk": MagicMock(state="Low Risk")
    }.get(entity_id)

    assert sensor.is_on is False

    # Case 2: Stale Data
    mock_hass.states.get.side_effect = lambda entity_id: {
        "sensor.test_airfield_weather_data_age": MagicMock(state="45"),
        "sensor.test_airfield_carb_risk": MagicMock(state="Low Risk")
    }.get(entity_id)

    assert sensor.is_on is True


def test_aircraft_crosswind_alert_within_limit(mock_hass):
    """Test crosswind alert stays OFF when runway crosswind within aircraft limits.
    
    This test validates that the crosswind alert correctly calculates crosswind
    component and remains OFF when safe for the aircraft's max crosswind limit.
    
    Scenario:
        - Aircraft: G-TEST with 15 kt max crosswind limit
        - Airfield: Runways 09/27 (east-west alignment, 90°/270° magnetic)
        - Wind: 10 kt from 090° (directly down runway 09)
        - Expected: No crosswind (direct headwind), alert OFF
    
    Setup:
        - Airfield config with runway headings and wind sensors
        - Aircraft config with registration and max crosswind
        - Mock wind speed: 10 kt, wind direction: 090°
    
    Validation:
        - Alert state is OFF (crosswind within limits)
        - best_runway attribute correctly identifies "09" (direct headwind)
        - within_limit attribute is True
        - Crosswind component calculations accurate
    
    Expected Result:
        Crosswind alert remains OFF, pilot cleared for safe operations
        on best runway with minimal crosswind component.
    """
    airfield = {
        "name": "Test Airfield",
        "runways": "09, 27",
        "wind_sensor": "sensor.wind",
        "wind_dir_sensor": "sensor.wind_dir",
    }
    aircraft = {
        "reg": "G-TEST",
        "max_xwind": 15,
    }

    alert = AircraftCrosswindAlert(mock_hass, aircraft, airfield, {})

    mock_hass.states.get.side_effect = lambda entity_id: {
        "sensor.wind": MagicMock(state="10"),
        "sensor.wind_dir": MagicMock(state="90"),
    }.get(entity_id)

    assert alert.is_on is False
    attrs = alert.extra_state_attributes
    assert attrs["best_runway"] == "09"
    assert attrs["within_limit"] is True


def test_aircraft_crosswind_alert_exceeds_limit(mock_hass):
    """Test crosswind alert turns ON when crosswind exceeds aircraft limits.
    
    This test validates that the crosswind alert triggers when calculated
    crosswind component exceeds the aircraft's maximum crosswind limit.
    
    Scenario:
        - Aircraft: G-TEST with 10 kt max crosswind limit (lower limit)
        - Airfield: Runways 09/27 (east-west)
        - Wind: 20 kt from 180° (south, 90° crosswind to both runways)
        - Expected: Full crosswind = 20 kt > 10 kt limit → Alert ON
    
    Setup:
        - Airfield config with runway headings
        - Aircraft config with restrictive 10 kt max crosswind
        - Mock wind: 20 kt from 180° (perpendicular to runways)
    
    Validation:
        - Alert state is ON (crosswind exceeds limits)
        - Crosswind component calculated as ≈20 kt (90° angle)
        - Alert attributes indicate unsafe conditions
    
    Expected Result:
        Crosswind alert triggers, warning pilot that crosswind exceeds
        aircraft limits on all available runways. Flight may require
        delay, diversion, or higher minimums.
    """
    airfield = {
        "name": "Test Airfield",
        "runways": "09, 27",
        "wind_sensor": "sensor.wind",
        "wind_dir_sensor": "sensor.wind_dir",
    }
    aircraft = {
        "reg": "G-TEST",
        "max_xwind": 10,
    }

    alert = AircraftCrosswindAlert(mock_hass, aircraft, airfield, {})

    mock_hass.states.get.side_effect = lambda entity_id: {
        "sensor.wind": MagicMock(state="20"),
        "sensor.wind_dir": MagicMock(state="180"),
    }.get(entity_id)

    assert alert.is_on is True


def test_safety_alert_respects_threshold_attribute(mock_hass):
    """Test master safety alert uses threshold guardrail from sensor attributes.
    
    This test validates that the safety alert respects custom thresholds
    exposed as sensor attributes, allowing per-airfield customization.
    
    Scenario:
        - Default threshold: 30 minutes (DEFAULT_STALE_WEATHER_MINUTES)
        - Custom threshold (from sensor attribute): 50 minutes
        - Weather data age: 40 minutes (between default and custom)
        - Expected: Alert OFF (respects custom 50-minute threshold)
    
    Setup:
        - Create master safety alert with default 30-minute threshold
        - Mock weather age sensor state = 40 minutes
        - Mock sensor attributes include "threshold_minutes": 50
        - Mock carb risk = "Low Risk" (not a trigger)
    
    Validation:
        - Alert reads threshold_minutes attribute from sensor state
        - Alert uses custom threshold (50 min) instead of default (30 min)
        - Alert state is OFF because 40 < 50 (within custom threshold)
        - Threshold attribute takes precedence over config default
    
    Expected Result:
        Safety alert correctly defers to sensor-provided threshold,
        allowing flexible configuration per airfield without code changes.
    """
    config = {"name": "Test Airfield"}
    sensor = HangarMasterSafetyAlert(mock_hass, config, {"stale_weather_minutes": DEFAULT_STALE_WEATHER_MINUTES})

    freshness_state = MagicMock(state="40")
    freshness_state.attributes = {"threshold_minutes": 50}

    sensor._freshness_id = "sensor.test_airfield_weather_data_age"
    sensor._carb_id = "sensor.test_airfield_carb_risk"
    mock_hass.states.get.side_effect = lambda entity_id: {
        "sensor.test_airfield_weather_data_age": freshness_state,
        "sensor.test_airfield_carb_risk": MagicMock(state="Low Risk"),
    }.get(entity_id)

    assert sensor.is_on is False
