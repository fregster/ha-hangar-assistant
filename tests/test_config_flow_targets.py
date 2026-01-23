"""Additional config_flow tests targeting uncovered branches.

Covers:
- OWM setup with invalid API key
- CheckWX setup API test failure scenarios
"""
import pytest
from unittest.mock import MagicMock, patch

from custom_components.hangar_assistant.config_flow import HangarAssistantConfigFlow


@pytest.mark.asyncio
async def test_owm_setup_invalid_api_key_shows_error():
    """Submitting an invalid OWM API key should show form errors."""
    flow = HangarAssistantConfigFlow()
    # Too short / non-hex key triggers validation error
    result = await flow.async_step_owm_setup(user_input={"api_key": "123"})
    assert result["type"] == "form"
    assert "errors" in result
    assert result["errors"].get("api_key") == "invalid_api_key"


@pytest.mark.asyncio
async def test_checkwx_setup_api_test_returns_none_sets_invalid_error():
    """If CheckWX test returns None, flow sets invalid_api_key error."""
    flow = HangarAssistantConfigFlow()
    flow.hass = MagicMock()
    # Valid-looking CheckWX key (length >= 32)
    user_input = {"api_key": "A" * 32, "metar_enabled": True, "taf_enabled": True, "station_enabled": True}
    with patch("custom_components.hangar_assistant.utils.checkwx_client.CheckWXClient.get_station_info", return_value=None):
        result = await flow.async_step_checkwx_setup(user_input=user_input)
    assert result["type"] == "form"
    assert result["errors"].get("api_key") == "invalid_api_key"


@pytest.mark.asyncio
async def test_checkwx_setup_api_test_exception_sets_cannot_connect():
    """If CheckWX test raises, flow sets cannot_connect error."""
    flow = HangarAssistantConfigFlow()
    flow.hass = MagicMock()
    user_input = {"api_key": "B" * 32, "metar_enabled": True, "taf_enabled": True, "station_enabled": True}
    with patch("custom_components.hangar_assistant.utils.checkwx_client.CheckWXClient.get_station_info", side_effect=Exception("network")):
        result = await flow.async_step_checkwx_setup(user_input=user_input)
    assert result["type"] == "form"
    assert result["errors"].get("api_key") == "cannot_connect"

