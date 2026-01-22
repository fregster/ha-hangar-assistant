"""Tests for fuel management sensors.

This module tests fuel-related sensors that are conditionally created
based on aircraft fuel configuration.

Test Strategy:
    - Mock ConfigEntry with aircraft fuel configurations
    - Test sensor creation when fuel burn rate configured
    - Verify sensors NOT created when fuel not configured
    - Test fuel calculation sensors

Coverage:
    - FuelBurnRateSensor creation
    - FuelEnduranceSensor creation
    - FuelWeightSensor creation
    - Conditional sensor creation based on burn_rate
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from homeassistant.config_entries import ConfigEntry
from custom_components.hangar_assistant.sensor import async_setup_entry


@pytest.fixture
def mock_hass():
    """Create mock Home Assistant instance.
    
    Returns:
        MagicMock: Configured hass instance
    """
    mock_hass = MagicMock()
    mock_hass.states = MagicMock()
    mock_hass.states.get.return_value = None
    return mock_hass


@pytest.fixture
def mock_entry_with_fuel():
    """Create mock ConfigEntry with aircraft fuel configuration.
    
    Provides:
        - Aircraft with fuel burn rate configured
        - Fuel type and tank capacity
    
    Returns:
        MagicMock: Config entry with fuel configured
    """
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        "airfields": [],
        "aircraft": [
            {
                "reg": "G-ABCD",
                "model": "Cessna 172",
                "fuel": {
                    "type": "AVGAS",
                    "burn_rate": 35.0,
                    "burn_rate_unit": "liters",
                    "tank_capacity": 160.0,
                    "tank_capacity_unit": "liters"
                }
            }
        ],
        "pilots": [],
        "integrations": {
            "notams": {"enabled": False}
        },
        "settings": {}
    }
    return entry


@pytest.fixture
def mock_entry_without_fuel():
    """Create mock ConfigEntry with aircraft but no fuel config.
    
    Provides:
        - Aircraft without fuel configuration
        - No burn rate specified (glider or electric)
    
    Returns:
        MagicMock: Config entry without fuel
    """
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        "airfields": [],
        "aircraft": [
            {
                "reg": "G-GLDR",
                "model": "ASK-21 Glider"
                # No fuel configuration
            }
        ],
        "pilots": [],
        "integrations": {
            "notams": {"enabled": False}
        },
        "settings": {}
    }
    return entry


@pytest.fixture
def mock_entry_zero_burn_rate():
    """Create mock ConfigEntry with zero fuel burn rate.
    
    Provides:
        - Aircraft with fuel config but zero burn rate
        - Represents electric or non-fuel aircraft
    
    Returns:
        MagicMock: Config entry with zero burn rate
    """
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        "airfields": [],
        "aircraft": [
            {
                "reg": "G-ELEC",
                "model": "Pipistrel Velis Electro",
                "fuel": {
                    "type": "NONE",
                    "burn_rate": 0.0,
                    "burn_rate_unit": "liters",
                    "tank_capacity": 0.0,
                    "tank_capacity_unit": "liters"
                }
            }
        ],
        "pilots": [],
        "integrations": {
            "notams": {"enabled": False}
        },
        "settings": {}
    }
    return entry


@pytest.mark.asyncio
async def test_fuel_sensors_created_when_configured(mock_hass, mock_entry_with_fuel):
    """Test fuel sensors created when fuel burn rate configured.
    
    This test validates:
        - async_setup_entry creates fuel sensors when burn_rate > 0
        - FuelBurnRateSensor, FuelEnduranceSensor, FuelWeightSensor all created
        - Sensors added to entity list
    
    Setup:
        - Mock entry with aircraft fuel configured
        - Burn rate = 35 L/h
    
    Validation:
        - Entity count includes fuel sensors
        - All 3 fuel sensor types created
    
    Expected Result:
        Fuel sensors created and registered for aircraft.
    """
    mock_add_entities = MagicMock()
    
    await async_setup_entry(mock_hass, mock_entry_with_fuel, mock_add_entities)
    
    # Verify entities were added
    assert mock_add_entities.called
    entities = mock_add_entities.call_args[0][0]
    
    # Count fuel sensor types
    burn_rate_sensors = [e for e in entities if e.__class__.__name__ == "FuelBurnRateSensor"]
    endurance_sensors = [e for e in entities if e.__class__.__name__ == "FuelEnduranceSensor"]
    weight_sensors = [e for e in entities if e.__class__.__name__ == "FuelWeightSensor"]
    
    # Should have 1 of each fuel sensor type for the aircraft
    assert len(burn_rate_sensors) == 1
    assert len(endurance_sensors) == 1
    assert len(weight_sensors) == 1


@pytest.mark.asyncio
async def test_fuel_sensors_not_created_without_config(mock_hass, mock_entry_without_fuel):
    """Test fuel sensors NOT created when fuel not configured.
    
    This test validates:
        - async_setup_entry skips fuel sensors when no fuel config
        - Only ground roll and performance sensors created
        - No fuel sensor instances in entity list
    
    Setup:
        - Mock entry with aircraft but no fuel config
        - Represents glider or non-fuel aircraft
    
    Validation:
        - Entity count excludes fuel sensors
        - No fuel sensor types created
    
    Expected Result:
        Fuel sensors not created when fuel not configured.
    """
    mock_add_entities = MagicMock()
    
    await async_setup_entry(mock_hass, mock_entry_without_fuel, mock_add_entities)
    
    # Verify entities were added
    assert mock_add_entities.called
    entities = mock_add_entities.call_args[0][0]
    
    # Count fuel sensor types
    burn_rate_sensors = [e for e in entities if e.__class__.__name__ == "FuelBurnRateSensor"]
    endurance_sensors = [e for e in entities if e.__class__.__name__ == "FuelEnduranceSensor"]
    weight_sensors = [e for e in entities if e.__class__.__name__ == "FuelWeightSensor"]
    
    # Should have 0 fuel sensors without fuel config
    assert len(burn_rate_sensors) == 0
    assert len(endurance_sensors) == 0
    assert len(weight_sensors) == 0


@pytest.mark.asyncio
async def test_fuel_sensors_not_created_with_zero_burn_rate(mock_hass, mock_entry_zero_burn_rate):
    """Test fuel sensors NOT created when burn rate is zero.
    
    This test validates:
        - async_setup_entry skips fuel sensors when burn_rate = 0
        - Zero burn rate represents electric/non-fuel aircraft
        - No fuel sensor instances in entity list
    
    Setup:
        - Mock entry with fuel config but burn_rate = 0
        - Represents electric aircraft
    
    Validation:
        - No fuel sensor types created
        - Standard aircraft sensors still created
    
    Expected Result:
        Fuel sensors not created for zero burn rate aircraft.
    """
    mock_add_entities = MagicMock()
    
    await async_setup_entry(mock_hass, mock_entry_zero_burn_rate, mock_add_entities)
    
    # Verify entities were added
    assert mock_add_entities.called
    entities = mock_add_entities.call_args[0][0]
    
    # Count fuel sensor types
    burn_rate_sensors = [e for e in entities if e.__class__.__name__ == "FuelBurnRateSensor"]
    endurance_sensors = [e for e in entities if e.__class__.__name__ == "FuelEnduranceSensor"]
    weight_sensors = [e for e in entities if e.__class__.__name__ == "FuelWeightSensor"]
    
    # Should have 0 fuel sensors with zero burn rate
    assert len(burn_rate_sensors) == 0
    assert len(endurance_sensors) == 0
    assert len(weight_sensors) == 0


@pytest.mark.asyncio
async def test_multiple_aircraft_fuel_sensors(mock_hass):
    """Test fuel sensors created for multiple aircraft.
    
    This test validates:
        - Each aircraft with fuel config gets its own sensors
        - Sensor count scales with aircraft count
    
    Setup:
        - 2 aircraft with fuel configured
        - Different fuel types and burn rates
    
    Validation:
        - 2 sets of fuel sensors created (6 total)
        - Each aircraft has 3 fuel sensors
    
    Expected Result:
        Fuel sensors created per-aircraft correctly.
    """
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        "airfields": [],
        "aircraft": [
            {
                "reg": "G-ABCD",
                "model": "Cessna 172",
                "fuel": {
                    "type": "AVGAS",
                    "burn_rate": 35.0,
                    "burn_rate_unit": "liters",
                    "tank_capacity": 160.0,
                    "tank_capacity_unit": "liters"
                }
            },
            {
                "reg": "G-EFGH",
                "model": "PA-28",
                "fuel": {
                    "type": "MOGAS",
                    "burn_rate": 28.0,
                    "burn_rate_unit": "liters",
                    "tank_capacity": 140.0,
                    "tank_capacity_unit": "liters"
                }
            }
        ],
        "pilots": [],
        "integrations": {
            "notams": {"enabled": False}
        },
        "settings": {}
    }
    
    mock_add_entities = MagicMock()
    await async_setup_entry(mock_hass, entry, mock_add_entities)
    
    entities = mock_add_entities.call_args[0][0]
    
    # Count fuel sensor types
    burn_rate_sensors = [e for e in entities if e.__class__.__name__ == "FuelBurnRateSensor"]
    endurance_sensors = [e for e in entities if e.__class__.__name__ == "FuelEnduranceSensor"]
    weight_sensors = [e for e in entities if e.__class__.__name__ == "FuelWeightSensor"]
    
    # Should have 2 of each fuel sensor type (one per aircraft)
    assert len(burn_rate_sensors) == 2
    assert len(endurance_sensors) == 2
    assert len(weight_sensors) == 2
