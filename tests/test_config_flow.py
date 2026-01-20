"""Tests for Hangar Assistant config flow."""
from unittest.mock import patch
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
from custom_components.hangar_assistant.const import DOMAIN

async def test_flow_user_init(hass: HomeAssistant):
    """Test the user step of the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "custom_components.hangar_assistant.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Hangar Assistant"
    assert result["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

async def test_flow_user_already_configured(hass: HomeAssistant):
    """Test the user step when already configured."""
    # Create an existing entry
    entry = patch("homeassistant.config_entries.ConfigEntry")
    entry.domain = DOMAIN
    
    with patch(
        "homeassistant.config_entries.ConfigFlow._async_current_entries",
        return_value=[entry],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "already_configured"
