"""Tests for airfield and hangar option flows.

This module covers airfield validation/conversion logic and hangar/dash
board behaviours in the options flow.

Test Strategy:
    - Exercise add airfield validation (ICAO format)
    - Verify airfield edit converts feet to metres
    - Validate duplicate hangar name handling per airfield
    - Ensure dashboard recreate triggers async_create_dashboard

Coverage:
    - async_step_add_airfield (validation path)
    - async_step_airfield_edit (distance unit conversion)
    - async_step_hangar_add (duplicate detection)
    - async_step_dashboard (recreate dashboard call)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry

from custom_components.hangar_assistant.config_flow import (
    HangarAssistantConfigFlow,
    HangarOptionsFlowHandler,
)


@pytest.mark.asyncio
async def test_add_airfield_validates_icao_format():
    """Test ICAO validation fails for short code.

    Validates that async_step_add_airfield returns an error when the ICAO
    code is not four characters. Ensures validation guard rails catch
    malformed codes before proceeding.
    """
    flow = HangarAssistantConfigFlow()

    result = await flow.async_step_add_airfield({"icao": "eg", "name": "Test"})

    assert result["type"] == "form"
    assert result["errors"]["icao"] == "invalid_icao"


@pytest.mark.asyncio
async def test_airfield_edit_converts_feet_to_metres():
    """Test airfield edit converts elevation and runway length from feet.

    Provides imperial inputs and verifies they are stored as metres when
    distance_unit is set to feet. Ensures legacy/imperial data is migrated
    safely without user-visible breakage.
    """
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        "airfields": [
            {
                "name": "Popham",
                "icao_code": "EGHP",
                "latitude": 51.2,
                "longitude": -1.3,
                "elevation": 90,
                "runway_length": 300,
            }
        ],
        "hangars": [],
        "aircraft": [],
        "pilots": [],
        "integrations": {"notams": {"enabled": False}},
        "settings": {},
    }
    entry.options = {}

    handler = HangarOptionsFlowHandler(entry)
    handler.hass = MagicMock()
    handler.hass.config_entries = MagicMock()
    handler.hass.config_entries.async_update_entry = MagicMock()
    handler._index = 0

    user_input = {
        "name": "Popham",
        "icao_code": "EGHP",
        "latitude": 51.2,
        "longitude": -1.3,
        "elevation": 300,  # feet
        "distance_unit": "ft",
        "runway_length": 1000,  # feet
        "runways": [],
        "primary_runway": "",
        "temp_sensor": "",
        "dp_sensor": "",
        "pressure_sensor": "",
        "wind_sensor": "",
        "wind_dir_sensor": "",
        "radio_frequency": "",
        "ppl_required": False,
        "weather_data_source": "sensors",
        "use_owm_forecast": True,
        "use_owm_alerts": True,
    }

    result = await handler.async_step_airfield_edit(user_input)

    handler.hass.config_entries.async_update_entry.assert_called_once()
    updated = handler.hass.config_entries.async_update_entry.call_args.kwargs["data"]
    updated_airfield = updated["airfields"][0]

    assert result["type"] == "abort"
    assert pytest.approx(updated_airfield["runway_length"], rel=0.001) == 304.8
    assert pytest.approx(updated_airfield["elevation"], rel=0.001) == 91.44


@pytest.mark.asyncio
async def test_hangar_add_blocks_duplicate_names_per_airfield():
    """Test hangar add returns an error for duplicate names on same airfield."""
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        "airfields": [{"name": "Popham"}],
        "hangars": [
            {
                "name": "Main",
                "airfield_name": "Popham",
                "temp_sensor": "sensor.temp1",
                "humidity_sensor": "sensor.humid1",
            }
        ],
        "aircraft": [],
        "pilots": [],
        "integrations": {"notams": {"enabled": False}},
        "settings": {},
    }
    entry.options = {}

    handler = HangarOptionsFlowHandler(entry)
    handler.hass = MagicMock()

    user_input = {
        "name": "Main",
        "airfield_name": "Popham",
        "temp_sensor": "sensor.temp2",
        "humidity_sensor": "sensor.humid2",
    }

    result = await handler.async_step_hangar_add(user_input)

    assert result["type"] == "form"
    assert "already exists" in result["errors"]["name"]


@pytest.mark.asyncio
async def test_dashboard_recreate_calls_builder():
    """Test dashboard recreate triggers async_create_dashboard with force flag."""
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        "airfields": [],
        "hangars": [],
        "aircraft": [],
        "pilots": [],
        "integrations": {"notams": {"enabled": False}},
        "settings": {},
        "dashboard_info": {},
    }
    entry.options = {}

    handler = HangarOptionsFlowHandler(entry)
    handler.hass = MagicMock()
    handler.hass.bus = MagicMock()
    handler.hass.bus.async_fire = MagicMock()
    handler.hass.async_add_executor_job = AsyncMock(return_value=True)
    handler.hass.services = MagicMock()
    handler.hass.services.has_service = MagicMock(return_value=False)

    mock_create = AsyncMock()
    with patch(
        "custom_components.hangar_assistant.async_create_dashboard",
        mock_create,
        create=True,
    ), patch(
        "custom_components.hangar_assistant.config_flow.async_create_dashboard",
        mock_create,
        create=True,
    ):
        result = await handler.async_step_dashboard({
            "recreate_dashboard": True,
            "send_setup_help": False,
            "fire_setup_event": False,
        })

    mock_create.assert_awaited_once()
    args, kwargs = mock_create.call_args
    assert kwargs["force_rebuild"] is True
    assert kwargs["reason"] == "options_flow"
    assert result["type"] == "abort"
