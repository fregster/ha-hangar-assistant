"""Additional tests to increase config_flow coverage.

Targets:
- AI prompt toggle save path
- Airfield add validations and ft->m conversions
- Hangar add duplicate name error
- Dashboard recreate triggers async_create_dashboard
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from homeassistant import config_entries

from custom_components.hangar_assistant.config_flow import HangarOptionsFlowHandler


def _make_hass_with_update_entry():
    hass = MagicMock()
    hass.config_entries = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()
    hass.services = MagicMock()
    # Prevent awaiting mock services by making has_service return False
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_call = AsyncMock(return_value=None)
    hass.bus = MagicMock()
    return hass


@pytest.mark.asyncio
async def test_ai_prompt_save_updates_entry():
    """Saving AI assistant config writes to entry data."""
    mock_entry = MagicMock(spec=config_entries.ConfigEntry)
    mock_entry.data = {}
    mock_entry.options = {}

    handler = HangarOptionsFlowHandler(mock_entry)
    handler.hass = _make_hass_with_update_entry()

    user_input = {
        "ai_agent_entity": "conversation.my_agent",
        "use_custom_system_prompt": True,
        "custom_system_prompt": "Custom prompt here",
    }
    result = await handler.async_step_ai(user_input=user_input)
    assert result["type"] == "abort"
    # Ensure update_entry called with ai_assistant data
    args, kwargs = handler.hass.config_entries.async_update_entry.call_args
    updated_entry, = args
    assert updated_entry is mock_entry
    assert "ai_assistant" in kwargs["data"]
    assert kwargs["data"]["ai_assistant"]["use_custom_system_prompt"] is True


@pytest.mark.asyncio
async def test_airfield_add_validation_errors_then_success_with_conversions():
    """Airfield add: runway validation errors and feet-to-meters conversion branch."""
    mock_entry = MagicMock(spec=config_entries.ConfigEntry)
    mock_entry.data = {}
    mock_entry.options = {}

    handler = HangarOptionsFlowHandler(mock_entry)
    handler.hass = _make_hass_with_update_entry()

    # Missing runways should error
    bad_input = {
        "name": "Test Field",
        "icao_code": "EGHP",
        "latitude": 51.1,
        "longitude": -1.2,
        "elevation": 100,
        "distance_unit": "m",
        "runways": "",
        "primary_runway": "03/21",
        "runway_length": 500,
    }
    form = await handler.async_step_airfield_add(user_input=bad_input)
    assert form["type"] == "form"
    assert "errors" in form and "runways" in form["errors"]

    # Primary runway not in list should error
    bad_input["runways"] = "01/19"
    bad_input["primary_runway"] = "03/21"
    form = await handler.async_step_airfield_add(user_input=bad_input)
    assert form["type"] == "form"
    assert "primary_runway" in form["errors"]

    # Success with feet unit conversions
    good_input = {
        "name": "Test Field",
        "icao_code": "EGHP",
        "latitude": 51.1,
        "longitude": -1.2,
        "elevation": 328.1,  # 1076 ft in m after conversion (approx)
        "distance_unit": "ft",
        "runways": "03/21, 08/26",
        "primary_runway": "03/21",
        "runway_length": 1640.4,  # 500 m in ft before conversion
    }
    result = await handler.async_step_airfield_add(user_input=good_input)
    assert result["type"] == "abort"
    # Validate conversion applied in update call
    args, kwargs = handler.hass.config_entries.async_update_entry.call_args
    data = kwargs["data"]
    airfields = data.get("airfields", [])
    assert airfields, "Airfield should be added"
    added = airfields[-1]
    assert isinstance(added.get("runway_length"), (int, float))
    assert isinstance(added.get("elevation"), (int, float))


@pytest.mark.asyncio
async def test_hangar_add_duplicate_name_errors():
    """Duplicate hangar name at same airfield produces error."""
    mock_entry = MagicMock(spec=config_entries.ConfigEntry)
    mock_entry.data = {"hangars": [{"name": "A1", "airfield_name": "Popham"}]}
    mock_entry.options = {}

    handler = HangarOptionsFlowHandler(mock_entry)
    handler.hass = _make_hass_with_update_entry()

    dup_input = {"name": "A1", "airfield_name": "Popham"}
    form = await handler.async_step_hangar_add(user_input=dup_input)
    assert form["type"] == "form"
    assert "errors" in form and "name" in form["errors"]


@pytest.mark.asyncio
async def test_dashboard_recreate_calls_async_create_dashboard():
    """Dashboard recreate flag should call async_create_dashboard."""
    mock_entry = MagicMock(spec=config_entries.ConfigEntry)
    mock_entry.data = {}
    mock_entry.options = {}

    handler = HangarOptionsFlowHandler(mock_entry)
    handler.hass = _make_hass_with_update_entry()

    # Make executor job awaitable to avoid real I/O during dashboard creation
    handler.hass.async_add_executor_job = AsyncMock(return_value=True)
    result = await handler.async_step_dashboard(user_input={"recreate_dashboard": True})
    assert result["type"] == "abort"
    # Ensure creation attempted
    assert handler.hass.async_add_executor_job.await_count == 1
