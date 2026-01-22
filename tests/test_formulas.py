"""Tests for aviation formula calculations.

This module tests the core aviation safety formulas used throughout the
Hangar Assistant integration, including:
- Density Altitude (DA) calculation
- Cloud Base estimation
- Carburetor icing risk assessment

Test Strategy:
    - Pure Python function testing (no Home Assistant dependencies)
    - Formula implementations copied from sensor.py for isolated validation
    - Test standard day conditions, edge cases, and boundary values
    - Verify mathematical accuracy against aviation standards

Coverage:
    - Density altitude: Standard day, high temperature, elevation effects, pressure fallback
    - Cloud base: Various temperature/dew point spreads including zero spread
    - Carb risk: All three risk categories (Serious, Moderate, Low)
    - Edge cases: Missing pressure data, zero values, extreme conditions

Aviation Context:
    - These formulas directly impact pilot GO/NO-GO decisions
    - Density altitude affects aircraft performance (takeoff distance, climb rate)
    - Cloud base determines VFR minima compliance
    - Carburetor icing risk is critical for safety in moisture-laden air
"""


def calculate_da(temp, pressure=None, elevation_m=0):
    """Calculate density altitude using standard aviation formula.
    
    This is a copy of the formula from sensor.py for isolated testing.
    DA = PA + (120 * (T - ISA_T)) where ISA_T = 15 - (2 * elevation/1000)
    
    Args:
        temp: Temperature in Celsius
        pressure: Pressure in hPa or inHg (auto-detected, >500 = hPa)
        elevation_m: Field elevation in meters
    
    Returns:
        int: Density altitude in feet
    """
    elevation_ft = elevation_m * 3.28084
    pa = elevation_ft
    if pressure:
        if pressure > 500:  # hPa
            pa += (1013.25 - pressure) * 30
        else:  # inHg
            pa += (29.92 - pressure) * 1000

    isa_temp = 15 - (2 * (elevation_ft / 1000))
    return round(pa + (120 * (temp - isa_temp)))


def calculate_cloud_base(temp, dp):
    """Calculate estimated cloud base using temperature-dew point spread.
    
    This is a copy of the formula from sensor.py for isolated testing.
    Cloud Base (ft) = ((T - DP) / 2.5) * 1000
    
    Args:
        temp: Temperature in Celsius
        dp: Dew point in Celsius
    
    Returns:
        int: Estimated cloud base in feet AGL
    """
    spread = temp - dp
    if spread <= 0:
        return 0
    return round((spread / 2.5) * 1000)


def calculate_carb_risk(temp, dp):
    """Assess carburetor icing risk based on temperature and dew point.
    
    This is a copy of the logic from sensor.py for isolated testing.
    
    Risk Categories:
        - Serious Risk: T < 25°C and spread < 5°C
        - Moderate Risk: T < 30°C and spread < 10°C
        - Low Risk: All other conditions
    
    Args:
        temp: Temperature in Celsius
        dp: Dew point in Celsius
    
    Returns:
        str: Risk level ("Serious Risk", "Moderate Risk", or "Low Risk")
    """
    spread = temp - dp
    if temp < 25 and spread < 5:
        return "Serious Risk"
    if temp < 30 and spread < 10:
        return "Moderate Risk"
    return "Low Risk"


def test_density_altitude():
    """Test density altitude calculations with various atmospheric conditions.
    
    This test validates the aviation density altitude formula used to assess
    aircraft performance degradation in non-standard conditions.
    
    Scenarios Tested:
        1. Standard ISA day (15°C, 1013.25 hPa at sea level) → DA = 0 ft
        2. Hot day (25°C at sea level) → DA = 1200 ft (reduced performance)
        3. Elevated airfield (100m, 15°C) → DA = 407 ft (accounting for elevation)
        4. Missing pressure data → Fallback to pressure altitude only
    
    Validation:
        - Standard day produces DA = 0 (baseline performance)
        - High temperature increases DA, reducing aircraft performance
        - Elevation effects properly incorporated into ISA temperature correction
        - Graceful handling when pressure data unavailable
    
    Aviation Impact:
        - DA > 2000 ft typically requires performance adjustments
        - High DA increases takeoff distance and reduces climb rate
        - Critical for safety planning at hot, high-elevation airfields
    
    Expected Result:
        Density altitude calculations match aviation standards for all scenarios
    """
    # Standard day at SL (15C, 1013.25 hPa, 0m)
    assert calculate_da(15, 1013.25, 0) == 0
    # 25C at SL
    assert calculate_da(25, 1013.25, 0) == 1200
    # 15C at 100m elevation (328ft PA, ISA = 14.34C)
    # -> 328 + 120*(15-14.34) = 407
    assert calculate_da(15, 1013.25, 100) == 407
    # Fallback (no pressure)
    assert calculate_da(15, None, 0) == 0


def test_cloud_base():
    """Test cloud base estimation using temperature-dew point spread.
    
    This test validates the cloud base estimation formula used to assess
    VFR (Visual Flight Rules) minima compliance.
    
    Scenarios Tested:
        1. 10°C spread (20°C temp, 10°C dew point) → 4000 ft cloud base
        2. Zero spread (15°C temp, 15°C dew point) → 0 ft (fog/stratus conditions)
        3. 15°C spread (25°C temp, 10°C dew point) → 6000 ft cloud base
    
    Validation:
        - Larger spreads produce higher cloud bases (drier air = higher clouds)
        - Zero spread correctly returns 0 ft (saturation at ground level)
        - Formula accuracy for typical VFR flight planning
    
    Aviation Impact:
        - Cloud base < 3000 ft may require MVFR procedures
        - Cloud base < 1000 ft typically IFR conditions
        - Critical for VFR flight planning and GO/NO-GO decisions
    
    Expected Result:
        Cloud base estimates match the 2.5°C/1000ft rule of thumb
    """
    assert calculate_cloud_base(20, 10) == 4000
    assert calculate_cloud_base(15, 15) == 0
    assert calculate_cloud_base(25, 10) == 6000


def test_carb_risk():
    """Test carburetor icing risk assessment across all risk categories.
    
    This test validates the carburetor icing risk logic used to warn pilots
    of dangerous ice formation conditions in float-type carburetors.
    
    Scenarios Tested:
        1. Serious Risk: 20°C temp, 18°C dew point (2°C spread, T < 25°C)
        2. Moderate Risk: 28°C temp, 20°C dew point (8°C spread, T < 30°C)
        3. Low Risk: 35°C temp, 30°C dew point (5°C spread, T ≥ 30°C)
    
    Validation:
        - Serious Risk correctly triggered for high moisture + moderate temps
        - Moderate Risk for borderline conditions
        - Low Risk for hot/dry conditions
    
    Aviation Impact:
        - Serious Risk: Apply carburetor heat immediately or avoid flight
        - Moderate Risk: Monitor closely, have carb heat ready
        - Low Risk: Standard operations, minimal icing threat
        - Most dangerous in descent/low power settings with high moisture
    
    Expected Result:
        Risk levels correctly categorized per aviation safety standards
    """
    assert calculate_carb_risk(20, 18) == "Serious Risk"
    assert calculate_carb_risk(28, 20) == "Moderate Risk"
    assert calculate_carb_risk(35, 30) == "Low Risk"
