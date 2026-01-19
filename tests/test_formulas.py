"""Tests for aviation formulas."""
import pytest

def calculate_da(temp, pressure=None, elevation_m=0):
    """DA formula from sensor.py."""
    elevation_ft = elevation_m * 3.28084
    pa = elevation_ft
    if pressure:
        if pressure > 500: # hPa
            pa += (1013.25 - pressure) * 30 
        else: # inHg
            pa += (29.92 - pressure) * 1000
    
    isa_temp = 15 - (2 * (elevation_ft / 1000))
    return round(pa + (120 * (temp - isa_temp)))

def test_density_altitude():
    # Standard day at SL (15C, 1013.25 hPa, 0m)
    assert calculate_da(15, 1013.25, 0) == 0
    # 25C at SL
    assert calculate_da(25, 1013.25, 0) == 1200
    # 15C at 100m elevation (328ft PA, ISA = 14.34C) -> 328 + 120*(15-14.34) = 407
    assert calculate_da(15, 1013.25, 100) == 407
    # Fallback (no pressure)
    assert calculate_da(15, None, 0) == 0

def test_cloud_base():
    assert calculate_cloud_base(20, 10) == 4000
    assert calculate_cloud_base(15, 15) == 0
    assert calculate_cloud_base(25, 10) == 6000

def test_carb_risk():
    assert calculate_carb_risk(20, 18) == "Serious Risk"
    assert calculate_carb_risk(28, 20) == "Moderate Risk"
    assert calculate_carb_risk(35, 30) == "Low Risk"
