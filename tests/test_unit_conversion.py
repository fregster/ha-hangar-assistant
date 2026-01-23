"""Tests for unit conversion utilities."""
import pytest
from custom_components.hangar_assistant.utils.units import (
    UnitPreference,
    convert_altitude,
    convert_speed,
    convert_weight,
    get_altitude_unit,
    get_speed_unit,
    get_weight_unit,
    FEET_TO_METERS,
    METERS_TO_FEET,
    KNOTS_TO_KPH,
    KPH_TO_KNOTS,
    POUNDS_TO_KG,
    KG_TO_POUNDS,
)


class TestUnitPreference:
    """Test UnitPreference class."""
    
    def test_aviation_preference(self):
        """Test aviation preference initialization."""
        pref = UnitPreference("aviation")
        assert pref.is_aviation()
        assert not pref.is_si()
    
    def test_si_preference(self):
        """Test SI preference initialization."""
        pref = UnitPreference("si")
        assert pref.is_si()
        assert not pref.is_aviation()
    
    def test_default_preference(self):
        """Test default preference is aviation."""
        pref = UnitPreference()
        assert pref.is_aviation()
    
    def test_invalid_preference(self):
        """Test invalid preference raises error."""
        with pytest.raises(ValueError):
            UnitPreference("invalid")


class TestAltitudeConversion:
    """Test altitude conversion functions."""
    
    def test_feet_to_meters(self):
        """Test feet to meters conversion."""
        result = convert_altitude(1000, from_feet=True, to_preference="si")
        expected = 1000 * FEET_TO_METERS
        assert abs(result - expected) < 0.01
    
    def test_meters_to_feet(self):
        """Test meters to feet conversion."""
        result = convert_altitude(300, from_feet=False, to_preference="aviation")
        expected = 300 * METERS_TO_FEET
        assert abs(result - expected) < 0.01
    
    def test_feet_to_feet(self):
        """Test feet to feet (no conversion)."""
        result = convert_altitude(5000, from_feet=True, to_preference="aviation")
        assert result == 5000
    
    def test_meters_to_meters(self):
        """Test meters to meters (no conversion)."""
        result = convert_altitude(1524, from_feet=False, to_preference="si")
        assert result == 1524
    
    def test_none_input(self):
        """Test None input returns None."""
        result = convert_altitude(None, from_feet=True, to_preference="si")
        assert result is None
    
    def test_zero_input(self):
        """Test zero input."""
        result = convert_altitude(0, from_feet=True, to_preference="si")
        assert result == 0


class TestSpeedConversion:
    """Test speed conversion functions."""
    
    def test_knots_to_kph(self):
        """Test knots to kph conversion."""
        result = convert_speed(100, from_knots=True, to_preference="si")
        expected = 100 * KNOTS_TO_KPH
        assert abs(result - expected) < 0.01
    
    def test_kph_to_knots(self):
        """Test kph to knots conversion."""
        result = convert_speed(185.2, from_knots=False, to_preference="aviation")
        expected = 185.2 * KPH_TO_KNOTS
        assert abs(result - expected) < 0.01
    
    def test_knots_to_knots(self):
        """Test knots to knots (no conversion)."""
        result = convert_speed(50, from_knots=True, to_preference="aviation")
        assert result == 50
    
    def test_kph_to_kph(self):
        """Test kph to kph (no conversion)."""
        result = convert_speed(100, from_knots=False, to_preference="si")
        assert result == 100
    
    def test_none_input(self):
        """Test None input returns None."""
        result = convert_speed(None, from_knots=True, to_preference="si")
        assert result is None


class TestWeightConversion:
    """Test weight conversion functions."""
    
    def test_pounds_to_kg(self):
        """Test pounds to kg conversion."""
        result = convert_weight(1000, from_pounds=True, to_preference="si")
        expected = 1000 * POUNDS_TO_KG
        assert abs(result - expected) < 0.01
    
    def test_kg_to_pounds(self):
        """Test kg to pounds conversion."""
        result = convert_weight(453.592, from_pounds=False, to_preference="aviation")
        expected = 453.592 * KG_TO_POUNDS
        assert abs(result - expected) < 0.01
    
    def test_pounds_to_pounds(self):
        """Test pounds to pounds (no conversion)."""
        result = convert_weight(500, from_pounds=True, to_preference="aviation")
        assert result == 500
    
    def test_kg_to_kg(self):
        """Test kg to kg (no conversion)."""
        result = convert_weight(226.8, from_pounds=False, to_preference="si")
        assert result == 226.8
    
    def test_none_input(self):
        """Test None input returns None."""
        result = convert_weight(None, from_pounds=True, to_preference="si")
        assert result is None


class TestUnitStrings:
    """Test unit string getter functions."""
    
    def test_altitude_units(self):
        """Test altitude unit strings."""
        assert get_altitude_unit("aviation") == "ft"
        assert get_altitude_unit("si") == "m"
    
    def test_speed_units(self):
        """Test speed unit strings."""
        assert get_speed_unit("aviation") == "kt"
        assert get_speed_unit("si") == "kph"
    
    def test_weight_units(self):
        """Test weight unit strings."""
        assert get_weight_unit("aviation") == "lb"
        assert get_weight_unit("si") == "kg"


class TestRealWorldScenarios:
    """Test real-world conversion scenarios."""
    
    def test_density_altitude_conversion(self):
        """Test density altitude conversion (5000 ft)."""
        da_ft = 5000
        # Convert to meters
        da_m = convert_altitude(da_ft, from_feet=True, to_preference="si")
        # Should be approximately 1524 m
        assert abs(da_m - 1524) < 2
    
    def test_crosswind_conversion(self):
        """Test crosswind conversion (15 knots)."""
        crosswind_kt = 15
        # Convert to kph
        crosswind_kph = convert_speed(crosswind_kt, from_knots=True, to_preference="si")
        # Should be approximately 27.78 kph
        assert abs(crosswind_kph - 27.78) < 0.1
    
    def test_aircraft_weight_conversion(self):
        """Test aircraft weight conversion (3500 lbs)."""
        mtow_lbs = 3500
        # Convert to kg
        mtow_kg = convert_weight(mtow_lbs, from_pounds=True, to_preference="si")
        # Should be approximately 1588 kg
        assert abs(mtow_kg - 1588) < 5
    
    def test_round_trip_conversion(self):
        """Test round-trip conversion maintains approximate value."""
        original = 1000  # feet
        to_meters = convert_altitude(original, from_feet=True, to_preference="si")
        back_to_feet = convert_altitude(to_meters, from_feet=False, to_preference="aviation")
        assert abs(back_to_feet - original) < 1
