"""Tests for sensor unit preference system (aviation vs SI units).

This module tests the unit preference system that allows users to choose
between aviation-standard units (ft, kt, etc.) and SI units (m, kph, etc.).

Test Strategy:
    - Test each sensor type's unit output with both preferences
    - Validate _attr_native_unit_of_measurement property
    - Test that unit preference cascades from global settings
    - Verify backward compatibility (default to aviation if not set)

Coverage:
    - DensityAltSensor: ft vs m
    - CloudBaseSensor: ft vs m
    - Crosswind sensors: kt vs kph
    - CarbRiskTransitionSensor: ft vs m
    - GroundRollSensor: m (always meters)

User Experience:
    - Aviation preference (default): Traditional units familiar to pilots
    - SI preference: Metric units for international users
    - Home Assistant displays units in entity cards automatically
    - Unit conversion happens transparently in sensor code
"""
import pytest
from unittest.mock import MagicMock
from custom_components.hangar_assistant.sensor import (
    DensityAltSensor,
    CloudBaseSensor,
    PrimaryRunwayCrosswindSensor,
    IdealRunwayCrosswindSensor,
    CarbRiskTransitionSensor,
    GroundRollSensor,
)
from custom_components.hangar_assistant.const import (
    UNIT_PREFERENCE_AVIATION,
    UNIT_PREFERENCE_SI,
    DOMAIN,
)


class TestDensityAltSensorUnits:
    """Test suite for density altitude sensor unit handling.
    
    Tests that DensityAltSensor correctly outputs feet (aviation) or
    meters (SI) based on global unit preference setting.
    
    Test Approach:
        - Create sensor with different unit_preference settings
        - Validate _attr_native_unit_of_measurement
        - Mock required sensor states (temp, pressure)
    
    Scenarios Covered:
        - Aviation preference → "ft"
        - SI preference → "m"
    """
    
    def test_da_aviation_units(self):
        """Test density altitude sensor uses feet with aviation preference.
        
        This test validates the default/traditional behavior where density
        altitude is displayed in feet, the aviation standard unit.
        
        Setup:
            - Mock temp sensor: 15°C (ISA standard)
            - settings: {"unit_preference": "aviation"}
        
        Validation:
            - native_unit_of_measurement is "ft"
        
        Expected Result:
            Sensor displays density altitude in feet, matching aviation
            charts, pilot operating handbooks, and ATIS broadcasts.
        """
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = MagicMock(state="15")
        
        config = {
            "name": "Popham",
            "elevation": 100,
            "temp_sensor": "sensor.temp"
        }
        
        settings = {"unit_preference": UNIT_PREFERENCE_AVIATION}
        sensor = DensityAltSensor(mock_hass, config, settings)
        
        assert sensor._attr_native_unit_of_measurement == "ft"
    
    def test_da_si_units(self):
        """Test density altitude sensor uses meters with SI preference.
        
        This test validates the SI/metric option for international users
        who prefer meters over feet.
        
        Setup:
            - Mock temp sensor: 15°C
            - settings: {"unit_preference": "si"}
        
        Validation:
            - native_unit_of_measurement is "m"
        
        Expected Result:
            Sensor displays density altitude in meters. User sees metric
            values in dashboard, though aviation formulas still calculate
            internally in feet then convert.
        """
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = MagicMock(state="15")
        
        config = {
            "name": "Popham",
            "elevation": 100,
            "temp_sensor": "sensor.temp"
        }
        
        settings = {"unit_preference": UNIT_PREFERENCE_SI}
        sensor = DensityAltSensor(mock_hass, config, settings)
        
        assert sensor._attr_native_unit_of_measurement == "m"


class TestCloudBaseSensorUnits:
    """Test CloudBaseSensor respects unit preference."""
    
    def test_cb_aviation_units(self):
        """Test CB sensor outputs feet when preference is aviation."""
        mock_hass = MagicMock()
        mock_hass.states.get.side_effect = lambda x: MagicMock(state="15" if "temp" in x else "5")
        
        config = {
            "name": "Popham",
            "temp_sensor": "sensor.temp",
            "dp_sensor": "sensor.dp"
        }
        
        settings = {"unit_preference": UNIT_PREFERENCE_AVIATION}
        sensor = CloudBaseSensor(mock_hass, config, settings)
        
        assert sensor._attr_native_unit_of_measurement == "ft"
    
    def test_cb_si_units(self):
        """Test CB sensor outputs meters when preference is SI."""
        mock_hass = MagicMock()
        mock_hass.states.get.side_effect = lambda x: MagicMock(state="15" if "temp" in x else "5")
        
        config = {
            "name": "Popham",
            "temp_sensor": "sensor.temp",
            "dp_sensor": "sensor.dp"
        }
        
        settings = {"unit_preference": UNIT_PREFERENCE_SI}
        sensor = CloudBaseSensor(mock_hass, config, settings)
        
        assert sensor._attr_native_unit_of_measurement == "m"


class TestCrosswindSensorUnits:
    """Test crosswind sensors respect unit preference."""
    
    def test_crosswind_aviation_units(self):
        """Test crosswind sensor outputs knots when preference is aviation."""
        mock_hass = MagicMock()
        
        config = {
            "name": "Popham",
            "primary_runway": "21",
            "wind_sensor": "sensor.wind",
            "wind_dir_sensor": "sensor.wind_dir"
        }
        
        settings = {"unit_preference": UNIT_PREFERENCE_AVIATION}
        sensor = PrimaryRunwayCrosswindSensor(mock_hass, config, settings)
        
        assert sensor._attr_native_unit_of_measurement == "kt"
    
    def test_crosswind_si_units(self):
        """Test crosswind sensor outputs kph when preference is SI."""
        mock_hass = MagicMock()
        
        config = {
            "name": "Popham",
            "primary_runway": "21",
            "wind_sensor": "sensor.wind",
            "wind_dir_sensor": "sensor.wind_dir"
        }
        
        settings = {"unit_preference": UNIT_PREFERENCE_SI}
        sensor = PrimaryRunwayCrosswindSensor(mock_hass, config, settings)
        
        assert sensor._attr_native_unit_of_measurement == "kph"


class TestCarTransitionSensorUnits:
    """Test carb risk transition sensor respects unit preference."""
    
    def test_carb_transition_aviation_units(self):
        """Test carb transition sensor outputs feet when preference is aviation."""
        mock_hass = MagicMock()
        mock_hass.states.get.side_effect = lambda x: MagicMock(state="20" if "temp" in x else "15")
        
        config = {
            "name": "Popham",
            "temp_sensor": "sensor.temp",
            "dp_sensor": "sensor.dp"
        }
        
        settings = {"unit_preference": UNIT_PREFERENCE_AVIATION}
        sensor = CarbRiskTransitionSensor(mock_hass, config, settings)
        
        assert sensor._attr_native_unit_of_measurement == "ft"
    
    def test_carb_transition_si_units(self):
        """Test carb transition sensor outputs meters when preference is SI."""
        mock_hass = MagicMock()
        mock_hass.states.get.side_effect = lambda x: MagicMock(state="20" if "temp" in x else "15")
        
        config = {
            "name": "Popham",
            "temp_sensor": "sensor.temp",
            "dp_sensor": "sensor.dp"
        }
        
        settings = {"unit_preference": UNIT_PREFERENCE_SI}
        sensor = CarbRiskTransitionSensor(mock_hass, config, settings)
        
        assert sensor._attr_native_unit_of_measurement == "m"


class TestGroundRollSensorUnits:
    """Test GroundRollSensor respects unit preference."""
    
    def test_ground_roll_aviation_units(self):
        """Test ground roll sensor outputs feet when preference is aviation."""
        mock_hass = MagicMock()
        
        config = {
            "reg": "G-TEST",
            "baseline_roll": 300
        }
        
        settings = {"unit_preference": UNIT_PREFERENCE_AVIATION}
        sensor = GroundRollSensor(mock_hass, config, settings)
        
        assert sensor._attr_native_unit_of_measurement == "ft"
    
    def test_ground_roll_si_units(self):
        """Test ground roll sensor outputs meters when preference is SI."""
        mock_hass = MagicMock()
        
        config = {
            "reg": "G-TEST",
            "baseline_roll": 300
        }
        
        settings = {"unit_preference": UNIT_PREFERENCE_SI}
        sensor = GroundRollSensor(mock_hass, config, settings)
        
        assert sensor._attr_native_unit_of_measurement == "m"


class TestBestRunwayAttributes:
    """Test BestRunway attributes include wind unit."""
    
    def test_best_runway_attributes_aviation(self):
        """Test best runway attributes include aviation wind unit."""
        mock_hass = MagicMock()
        mock_hass.states.get.side_effect = lambda x: MagicMock(state="180" if "dir" in x else "20")
        
        config = {
            "name": "Popham",
            "runways": "03, 21",
            "wind_sensor": "sensor.wind",
            "wind_dir_sensor": "sensor.wind_dir"
        }
        
        settings = {"unit_preference": UNIT_PREFERENCE_AVIATION}
        from custom_components.hangar_assistant.sensor import BestRunwaySensor
        
        sensor = BestRunwaySensor(mock_hass, config, settings)
        attrs = sensor.extra_state_attributes
        
        assert attrs.get("wind_unit") == "kt"
    
    def test_best_runway_attributes_si(self):
        """Test best runway attributes include SI wind unit."""
        mock_hass = MagicMock()
        mock_hass.states.get.side_effect = lambda x: MagicMock(state="180" if "dir" in x else "20")
        
        config = {
            "name": "Popham",
            "runways": "03, 21",
            "wind_sensor": "sensor.wind",
            "wind_dir_sensor": "sensor.wind_dir"
        }
        
        settings = {"unit_preference": UNIT_PREFERENCE_SI}
        from custom_components.hangar_assistant.sensor import BestRunwaySensor
        
        sensor = BestRunwaySensor(mock_hass, config, settings)
        attrs = sensor.extra_state_attributes
        
        assert attrs.get("wind_unit") == "kph"


class TestDefaultPreference:
    """Test sensors use default preference when not provided."""
    
    def test_sensor_default_preference_aviation(self):
        """Test sensors default to aviation units."""
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = MagicMock(state="15")
        
        config = {
            "name": "Popham",
            "elevation": 100,
            "temp_sensor": "sensor.temp"
        }
        
        # No settings provided
        sensor = DensityAltSensor(mock_hass, config, {})
        
        # Should default to aviation (feet)
        assert sensor._attr_native_unit_of_measurement == "ft"
