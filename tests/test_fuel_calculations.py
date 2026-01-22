"""Tests for fuel calculation utilities.

This module tests the fuel management calculation functions including volume
conversions, weight calculations, and endurance computations.

Test Strategy:
    - Unit tests for pure calculation functions
    - Validation of conversion between liters and gallons (US/Imperial)
    - Fuel weight calculations for all fuel types
    - Endurance calculations with reserve fuel

Coverage:
    - Volume unit conversions (liters ↔ gallons ↔ imperial gallons)
    - Fuel weight calculations (all fuel types: AVGAS, MOGAS, JET_A, etc.)
    - Endurance calculations with and without reserve
    - Edge cases: zero values, negative values, unknown fuel types
"""
import pytest
from custom_components.hangar_assistant.utils.units import (
    convert_fuel_volume,
    calculate_fuel_weight,
    calculate_fuel_endurance,
)
from custom_components.hangar_assistant.const import (
    FUEL_TYPE_AVGAS,
    FUEL_TYPE_MOGAS,
    FUEL_TYPE_JET_A,
    FUEL_TYPE_DIESEL,
    FUEL_TYPE_NONE,
)


class TestFuelVolumeConversions:
    """Test fuel volume conversions between different units."""
    
    def test_liters_to_us_gallons(self):
        """Test conversion from liters to US gallons."""
        # 100 liters = ~26.417 US gallons
        result = convert_fuel_volume(100, from_unit="liters", to_unit="gallons")
        assert result is not None
        assert pytest.approx(result, abs=0.01) == 26.417
    
    def test_us_gallons_to_liters(self):
        """Test conversion from US gallons to liters."""
        # 10 US gallons = 37.8541 liters
        result = convert_fuel_volume(10, from_unit="gallons", to_unit="liters")
        assert result is not None
        assert pytest.approx(result, abs=0.01) == 37.854
    
    def test_liters_to_imperial_gallons(self):
        """Test conversion from liters to Imperial gallons."""
        # 100 liters = ~21.997 Imperial gallons
        result = convert_fuel_volume(100, from_unit="liters", to_unit="gallons_imperial")
        assert result is not None
        assert pytest.approx(result, abs=0.01) == 21.997
    
    def test_imperial_gallons_to_liters(self):
        """Test conversion from Imperial gallons to liters."""
        # 10 Imperial gallons = 45.4609 liters
        result = convert_fuel_volume(10, from_unit="gallons_imperial", to_unit="liters")
        assert result is not None
        assert pytest.approx(result, abs=0.01) == 45.461
    
    def test_same_unit_conversion(self):
        """Test conversion when source and target units are the same."""
        result = convert_fuel_volume(100, from_unit="liters", to_unit="liters")
        assert result == 100
    
    def test_none_value_handling(self):
        """Test that None input returns None output."""
        result = convert_fuel_volume(None, from_unit="liters", to_unit="gallons")
        assert result is None
    
    def test_zero_volume(self):
        """Test conversion of zero volume."""
        result = convert_fuel_volume(0, from_unit="liters", to_unit="gallons")
        assert result == 0


class TestFuelWeightCalculations:
    """Test fuel weight calculations for different fuel types."""
    
    def test_avgas_weight_from_liters(self):
        """Test AVGAS weight calculation from liters.
        
        AVGAS density: 0.72 kg/L
        100 liters = 72 kg
        """
        result = calculate_fuel_weight(100, FUEL_TYPE_AVGAS, volume_unit="liters")
        assert pytest.approx(result, abs=0.1) == 72.0
    
    def test_mogas_weight_from_liters(self):
        """Test MOGAS weight calculation from liters.
        
        MOGAS density: 0.75 kg/L
        100 liters = 75 kg
        """
        result = calculate_fuel_weight(100, FUEL_TYPE_MOGAS, volume_unit="liters")
        assert pytest.approx(result, abs=0.1) == 75.0
    
    def test_jet_a_weight_from_liters(self):
        """Test JET-A weight calculation from liters.
        
        JET-A density: 0.80 kg/L
        100 liters = 80 kg
        """
        result = calculate_fuel_weight(100, FUEL_TYPE_JET_A, volume_unit="liters")
        assert pytest.approx(result, abs=0.1) == 80.0
    
    def test_diesel_weight_from_liters(self):
        """Test diesel weight calculation from liters.
        
        Diesel density: 0.84 kg/L
        100 liters = 84 kg
        """
        result = calculate_fuel_weight(100, FUEL_TYPE_DIESEL, volume_unit="liters")
        assert pytest.approx(result, abs=0.1) == 84.0
    
    def test_none_fuel_type_weight(self):
        """Test glider (no fuel) weight calculation.
        
        NONE fuel type has zero density.
        """
        result = calculate_fuel_weight(100, FUEL_TYPE_NONE, volume_unit="liters")
        assert result == 0.0
    
    def test_weight_from_us_gallons(self):
        """Test weight calculation with US gallons input.
        
        10 US gallons = 37.854 liters of AVGAS
        37.854 L * 0.72 kg/L = 27.25 kg
        """
        result = calculate_fuel_weight(10, FUEL_TYPE_AVGAS, volume_unit="gallons")
        assert pytest.approx(result, abs=0.1) == 27.25
    
    def test_zero_volume_weight(self):
        """Test weight calculation with zero volume."""
        result = calculate_fuel_weight(0, FUEL_TYPE_AVGAS, volume_unit="liters")
        assert result == 0.0
    
    def test_unknown_fuel_type_defaults_to_avgas(self):
        """Test that unknown fuel type defaults to AVGAS density."""
        result = calculate_fuel_weight(100, "UNKNOWN_FUEL", volume_unit="liters")
        # Should default to AVGAS (0.72 kg/L)
        assert pytest.approx(result, abs=0.1) == 72.0


class TestFuelEnduranceCalculations:
    """Test fuel endurance calculations with reserve fuel."""
    
    def test_endurance_no_reserve(self):
        """Test endurance calculation without reserve fuel.
        
        Tank: 100 liters
        Burn rate: 25 liters/hour
        Reserve: 0 minutes
        Expected: 4.0 hours
        """
        result = calculate_fuel_endurance(
            tank_capacity=100,
            burn_rate=25,
            volume_unit="liters",
            reserve_minutes=0
        )
        assert pytest.approx(result, abs=0.01) == 4.0
    
    def test_endurance_with_30_min_reserve(self):
        """Test endurance calculation with 30-minute reserve.
        
        Tank: 100 liters
        Burn rate: 25 liters/hour
        Reserve: 30 minutes (12.5 liters)
        Usable: 87.5 liters
        Expected: 3.5 hours
        """
        result = calculate_fuel_endurance(
            tank_capacity=100,
            burn_rate=25,
            volume_unit="liters",
            reserve_minutes=30
        )
        assert pytest.approx(result, abs=0.01) == 3.5
    
    def test_endurance_with_45_min_reserve(self):
        """Test endurance calculation with 45-minute reserve.
        
        Tank: 100 liters
        Burn rate: 20 liters/hour
        Reserve: 45 minutes (15 liters)
        Usable: 85 liters
        Expected: 4.25 hours
        """
        result = calculate_fuel_endurance(
            tank_capacity=100,
            burn_rate=20,
            volume_unit="liters",
            reserve_minutes=45
        )
        assert pytest.approx(result, abs=0.01) == 4.25
    
    def test_endurance_from_us_gallons(self):
        """Test endurance calculation with US gallons.
        
        Tank: 41 US gallons (~155 liters)
        Burn rate: 9.2 US gallons/hour (~35 liters/hour)
        Reserve: 30 minutes
        Expected: ~3.95 hours
        """
        result = calculate_fuel_endurance(
            tank_capacity=41,
            burn_rate=9.2,
            volume_unit="gallons",
            reserve_minutes=30
        )
        assert pytest.approx(result, abs=0.1) == 3.95
    
    def test_endurance_zero_burn_rate(self):
        """Test endurance calculation with zero burn rate (glider).
        
        Should return 0 to avoid division by zero.
        """
        result = calculate_fuel_endurance(
            tank_capacity=100,
            burn_rate=0,
            volume_unit="liters",
            reserve_minutes=30
        )
        assert result == 0.0
    
    def test_endurance_reserve_exceeds_capacity(self):
        """Test endurance when reserve exceeds tank capacity.
        
        Tank: 50 liters
        Burn rate: 10 liters/hour
        Reserve: 60 minutes (10 liters)
        Total endurance: 5 hours
        Reserve: 1 hour
        Usable: max(0, 5 - 1) = 4 hours
        """
        result = calculate_fuel_endurance(
            tank_capacity=50,
            burn_rate=10,
            volume_unit="liters",
            reserve_minutes=60
        )
        assert pytest.approx(result, abs=0.01) == 4.0
    
    def test_endurance_reserve_nearly_equals_capacity(self):
        """Test endurance when reserve nearly equals capacity.
        
        Should return close to 0 but not negative.
        """
        result = calculate_fuel_endurance(
            tank_capacity=50,
            burn_rate=10,
            volume_unit="liters",
            reserve_minutes=295  # 4.92 hours reserve, 5 hour total
        )
        # Usable = max(0, 5 - 4.92) = 0.08 hours
        assert result >= 0
        assert result < 0.1


class TestRealWorldScenarios:
    """Test real-world fuel calculation scenarios."""
    
    def test_cessna_172_fuel_profile(self):
        """Test Cessna 172 fuel calculations.
        
        Typical C172:
        - Tank: 155 liters (41 US gallons)
        - Burn: 35 liters/hour (9.2 gal/hour)
        - Fuel: AVGAS (0.72 kg/L)
        - Reserve: 30 minutes
        """
        tank_capacity = 155  # liters
        burn_rate = 35  # liters/hour
        
        # Endurance
        endurance = calculate_fuel_endurance(
            tank_capacity,
            burn_rate,
            volume_unit="liters",
            reserve_minutes=30
        )
        assert pytest.approx(endurance, abs=0.1) == 3.93
        
        # Weight
        weight_kg = calculate_fuel_weight(tank_capacity, FUEL_TYPE_AVGAS, "liters")
        assert pytest.approx(weight_kg, abs=1) == 112  # 155 * 0.72
    
    def test_piper_pa28_fuel_profile(self):
        """Test Piper PA-28 fuel calculations.
        
        Typical PA-28:
        - Tank: 189 liters (50 US gallons)
        - Burn: 38 liters/hour (10 gal/hour)
        - Fuel: AVGAS
        - Reserve: 30 minutes
        """
        tank_capacity = 189
        burn_rate = 38
        
        endurance = calculate_fuel_endurance(
            tank_capacity,
            burn_rate,
            volume_unit="liters",
            reserve_minutes=30
        )
        assert pytest.approx(endurance, abs=0.1) == 4.47
        
        weight_kg = calculate_fuel_weight(tank_capacity, FUEL_TYPE_AVGAS, "liters")
        assert pytest.approx(weight_kg, abs=1) == 136
    
    def test_diamond_da42_diesel_profile(self):
        """Test Diamond DA42 diesel fuel calculations.
        
        DA42 (diesel engines):
        - Tank: 227 liters (60 US gallons)
        - Burn: 32 liters/hour (8.5 gal/hour, both engines)
        - Fuel: JET-A/Diesel (0.84 kg/L)
        - Reserve: 45 minutes
        """
        tank_capacity = 227
        burn_rate = 32
        
        endurance = calculate_fuel_endurance(
            tank_capacity,
            burn_rate,
            volume_unit="liters",
            reserve_minutes=45
        )
        assert pytest.approx(endurance, abs=0.1) == 6.34
        
        # Diesel is heavier than AVGAS
        weight_kg = calculate_fuel_weight(tank_capacity, FUEL_TYPE_DIESEL, "liters")
        assert pytest.approx(weight_kg, abs=1) == 191  # 227 * 0.84
    
    def test_glider_zero_fuel(self):
        """Test glider (no fuel) calculations."""
        tank_capacity = 0
        burn_rate = 0
        
        endurance = calculate_fuel_endurance(
            tank_capacity,
            burn_rate,
            volume_unit="liters",
            reserve_minutes=0
        )
        assert endurance == 0.0
        
        weight_kg = calculate_fuel_weight(tank_capacity, FUEL_TYPE_NONE, "liters")
        assert weight_kg == 0.0
