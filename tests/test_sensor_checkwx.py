"""Tests for CheckWX sensor creation and conditional enablement.

This module tests CheckWX-based sensors (METAR, TAF, Station) that are
conditionally created based on integration configuration.

Test Strategy:
    - Mock ConfigEntry with CheckWX integration settings
    - Test sensor creation when CheckWX enabled
    - Verify sensors NOT created when CheckWX disabled
    - Test ICAO code requirement for CheckWX sensors

Coverage:
    - MetarSensor creation when metar_enabled
    - TafSensor creation when taf_enabled
    - StationInfoSensor creation when station_enabled
    - CheckWX sensors require ICAO code
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
def mock_entry_checkwx_enabled():
    """Create mock ConfigEntry with CheckWX enabled.
    
    Provides:
        - CheckWX integration enabled
        - METAR, TAF, Station all enabled
        - Airfield with ICAO code
    
    Returns:
        MagicMock: Config entry with CheckWX enabled
    """
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        "airfields": [
            {
                "name": "Popham",
                "icao": "EGHP",
                "latitude": 51.2,
                "longitude": -1.2,
                "elevation": 100
            }
        ],
        "aircraft": [],
        "pilots": [],
        "integrations": {
            "checkwx": {
                "enabled": True,
                "metar_enabled": True,
                "taf_enabled": True,
                "station_enabled": True
            },
            "notams": {
                "enabled": False
            }
        },
        "settings": {}
    }
    return entry


@pytest.fixture
def mock_entry_checkwx_disabled():
    """Create mock ConfigEntry with CheckWX disabled.
    
    Provides:
        - CheckWX integration disabled
        - Airfield with ICAO code
    
    Returns:
        MagicMock: Config entry with CheckWX disabled
    """
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        "airfields": [
            {
                "name": "Popham",
                "icao": "EGHP",
                "latitude": 51.2,
                "longitude": -1.2,
                "elevation": 100
            }
        ],
        "aircraft": [],
        "pilots": [],
        "integrations": {
            "checkwx": {
                "enabled": False
            },
            "notams": {
                "enabled": False
            }
        },
        "settings": {}
    }
    return entry


@pytest.fixture
def mock_entry_no_icao():
    """Create mock ConfigEntry with CheckWX enabled but no ICAO.
    
    Provides:
        - CheckWX integration enabled
        - Airfield WITHOUT ICAO code
    
    Returns:
        MagicMock: Config entry with missing ICAO
    """
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        "airfields": [
            {
                "name": "Private Strip",
                # No ICAO code
                "latitude": 51.2,
                "longitude": -1.2,
                "elevation": 100
            }
        ],
        "aircraft": [],
        "pilots": [],
        "integrations": {
            "checkwx": {
                "enabled": True,
                "metar_enabled": True,
                "taf_enabled": True,
                "station_enabled": True
            },
            "notams": {
                "enabled": False
            }
        },
        "settings": {}
    }
    return entry


@pytest.mark.asyncio
async def test_checkwx_sensors_created_when_enabled(mock_hass, mock_entry_checkwx_enabled):
    """Test CheckWX sensors created when integration enabled.
    
    This test validates:
        - async_setup_entry creates CheckWX sensors when enabled
        - METAR, TAF, and Station sensors all created
        - Sensors added to entity list
    
    Setup:
        - Mock entry with CheckWX enabled
        - Airfield with ICAO code
    
    Validation:
        - Entity count includes CheckWX sensors
        - async_add_entities called with sensor instances
    
    Expected Result:
        CheckWX sensors created and registered.
    """
    mock_add_entities = MagicMock()
    
    await async_setup_entry(mock_hass, mock_entry_checkwx_enabled, mock_add_entities)
    
    # Verify entities were added
    assert mock_add_entities.called
    entities = mock_add_entities.call_args[0][0]
    
    # Count CheckWX sensor types
    metar_sensors = [e for e in entities if e.__class__.__name__ == "MetarSensor"]
    taf_sensors = [e for e in entities if e.__class__.__name__ == "TafSensor"]
    station_sensors = [e for e in entities if e.__class__.__name__ == "StationInfoSensor"]
    
    # Should have 1 of each CheckWX sensor type for the airfield
    assert len(metar_sensors) == 1
    assert len(taf_sensors) == 1
    assert len(station_sensors) == 1


@pytest.mark.asyncio
async def test_checkwx_sensors_not_created_when_disabled(mock_hass, mock_entry_checkwx_disabled):
    """Test CheckWX sensors NOT created when integration disabled.
    
    This test validates:
        - async_setup_entry skips CheckWX sensors when disabled
        - Only standard sensors created
        - No CheckWX sensor instances in entity list
    
    Setup:
        - Mock entry with CheckWX disabled
        - Airfield with ICAO code
    
    Validation:
        - Entity count excludes CheckWX sensors
        - No METAR/TAF/Station sensors created
    
    Expected Result:
        CheckWX sensors not created when integration disabled.
    """
    mock_add_entities = MagicMock()
    
    await async_setup_entry(mock_hass, mock_entry_checkwx_disabled, mock_add_entities)
    
    # Verify entities were added
    assert mock_add_entities.called
    entities = mock_add_entities.call_args[0][0]
    
    # Count CheckWX sensor types
    metar_sensors = [e for e in entities if e.__class__.__name__ == "MetarSensor"]
    taf_sensors = [e for e in entities if e.__class__.__name__ == "TafSensor"]
    station_sensors = [e for e in entities if e.__class__.__name__ == "StationInfoSensor"]
    
    # Should have 0 CheckWX sensors when disabled
    assert len(metar_sensors) == 0
    assert len(taf_sensors) == 0
    assert len(station_sensors) == 0


@pytest.mark.asyncio
async def test_checkwx_sensors_not_created_without_icao(mock_hass, mock_entry_no_icao):
    """Test CheckWX sensors NOT created when ICAO missing.
    
    This test validates:
        - async_setup_entry skips CheckWX sensors when ICAO absent
        - CheckWX requires ICAO code to function
        - No CheckWX sensor instances in entity list
    
    Setup:
        - Mock entry with CheckWX enabled
        - Airfield WITHOUT ICAO code
    
    Validation:
        - No METAR/TAF/Station sensors created
        - Standard sensors still created
    
    Expected Result:
        CheckWX sensors not created without ICAO code.
    """
    mock_add_entities = MagicMock()
    
    await async_setup_entry(mock_hass, mock_entry_no_icao, mock_add_entities)
    
    # Verify entities were added
    assert mock_add_entities.called
    entities = mock_add_entities.call_args[0][0]
    
    # Count CheckWX sensor types
    metar_sensors = [e for e in entities if e.__class__.__name__ == "MetarSensor"]
    taf_sensors = [e for e in entities if e.__class__.__name__ == "TafSensor"]
    station_sensors = [e for e in entities if e.__class__.__name__ == "StationInfoSensor"]
    
    # Should have 0 CheckWX sensors without ICAO
    assert len(metar_sensors) == 0
    assert len(taf_sensors) == 0
    assert len(station_sensors) == 0


@pytest.mark.asyncio
async def test_metar_sensor_individually_disabled(mock_hass):
    """Test METAR sensor not created when individually disabled.
    
    This test validates:
        - CheckWX can disable individual sensor types
        - METAR disabled while TAF/Station enabled
    
    Setup:
        - CheckWX enabled, METAR disabled
        - TAF and Station enabled
    
    Validation:
        - No METAR sensor created
        - TAF and Station sensors created
    
    Expected Result:
        Individual sensor type control works correctly.
    """
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        "airfields": [{"name": "Popham", "icao": "EGHP", "latitude": 51.2, "longitude": -1.2, "elevation": 100}],
        "aircraft": [],
        "pilots": [],
        "integrations": {
            "checkwx": {
                "enabled": True,
                "metar_enabled": False,  # METAR disabled
                "taf_enabled": True,
                "station_enabled": True
            },
            "notams": {"enabled": False}
        },
        "settings": {}
    }
    
    mock_add_entities = MagicMock()
    await async_setup_entry(mock_hass, entry, mock_add_entities)
    
    entities = mock_add_entities.call_args[0][0]
    metar_sensors = [e for e in entities if e.__class__.__name__ == "MetarSensor"]
    taf_sensors = [e for e in entities if e.__class__.__name__ == "TafSensor"]
    station_sensors = [e for e in entities if e.__class__.__name__ == "StationInfoSensor"]
    
    assert len(metar_sensors) == 0  # METAR disabled
    assert len(taf_sensors) == 1  # TAF enabled
    assert len(station_sensors) == 1  # Station enabled
