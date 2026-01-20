"""Tests for Hangar Assistant config flow."""
import pytest
from unittest.mock import patch, MagicMock
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
from custom_components.hangar_assistant.const import DOMAIN
from custom_components.hangar_assistant.config_flow import (
    HangarAssistantConfigFlow
)


@pytest.mark.asyncio
async def test_flow_user_init():
    """Test the user step of the config flow."""
    flow = HangarAssistantConfigFlow()
    flow.hass = MagicMock()
    flow._async_current_entries = MagicMock(return_value=[])

    result = await flow.async_step_user()

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_flow_user_already_configured():
    """Test the user step when already configured."""
    flow = HangarAssistantConfigFlow()
    flow.hass = MagicMock()
    # Mock existing entry
    existing_entry = MagicMock()
    existing_entry.domain = DOMAIN
    flow._async_current_entries = MagicMock(
        return_value=[existing_entry]
    )

    result = await flow.async_step_user()

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
