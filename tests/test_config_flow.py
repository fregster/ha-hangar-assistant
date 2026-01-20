from unittest.mock import patch
from homeassistant import config_entries, data_entry_flow
import pytest
from custom_components.hangar_assistant.const import DOMAIN

@pytest.mark.asyncio
async def test_config_flow(hass):
    """Test the config flow."""
    # Start the config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Check that the flow is of the correct type
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # Simulate user input
    with patch("custom_components.hangar_assistant.async_setup_entry", return_value=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    # Check that the flow creates an entry
    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Hangar Assistant"
    assert result2["data"] == {}

@pytest.mark.asyncio
async def test_options_flow(hass):
    """Test the options flow."""
    # Create a mock config entry
    config_entry = config_entries.ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Hangar Assistant",
        data={},
        source="user",
        options={},
    )
    config_entry.add_to_hass(hass)

    # Initialize the options flow
    with patch("custom_components.hangar_assistant.async_setup_entry", return_value=True):
        await hass.config_entries.async_setup(config_entry.entry_id)
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

    # Check that the flow is of the correct type
    assert result["type"] == data_entry_flow.RESULT_TYPE_MENU
    assert result["step_id"] == "init"