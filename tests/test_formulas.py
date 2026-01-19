"""Tests for aviation formulas."""
import pytest

def calculate_da(temp):
    """Simplified DA formula from sensor.py."""
    return round(4000 + (120 * (temp - 15)))

def calculate_cloud_base(t, dp):
    """Cloud base formula from sensor.py."""
    return round(((t - dp) / 2.5) * 1000)

def calculate_carb_risk(t, dp):
    """Carb risk logic from sensor.py."""
    spread = t - dp
    if t < 25 and spread < 5:
        return "Serious Risk"
    if t < 30 and spread < 10:
        return "Moderate Risk"
    return "Low Risk"

def test_density_altitude():
    assert calculate_da(15) == 4000
    assert calculate_da(25) == 5200
    assert calculate_da(5) == 2800

def test_cloud_base():
    assert calculate_cloud_base(20, 10) == 4000
    assert calculate_cloud_base(15, 15) == 0
    assert calculate_cloud_base(25, 10) == 6000

def test_carb_risk():
    assert calculate_carb_risk(20, 18) == "Serious Risk"
    assert calculate_carb_risk(28, 20) == "Moderate Risk"
    assert calculate_carb_risk(35, 30) == "Low Risk"
