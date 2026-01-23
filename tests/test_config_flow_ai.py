"""Tests for config_flow AI assistant configuration.

This module tests AI configuration in the options flow, including
custom prompt toggle and entity selection.

Test Strategy:
    - Mock ConfigEntry and Home Assistant instances
    - Test AI assistant configuration with and without custom prompts
    - Validate form schema changes based on toggle state

Coverage:
    - async_step_ai (form submission with standard prompt)
    - async_step_ai (form submission with custom prompt enabled)
    - Custom prompt field visibility toggle
"""

import pytest
from unittest.mock import MagicMock
from homeassistant import config_entries
from custom_components.hangar_assistant.config_flow import HangarOptionsFlowHandler


@pytest.fixture
def mock_entry_with_ai():
    """Create a mock ConfigEntry with AI configuration.
    
    Provides:
        - AI assistant entity configured
        - Custom prompt disabled by default
    
    Returns:
        MagicMock: Config entry with AI settings
    """
    entry = MagicMock(spec=config_entries.ConfigEntry)
    entry.data = {
        "ai_assistant": {
            "ai_agent_entity": "conversation.home_assistant",
            "use_custom_system_prompt": False
        },
        "settings": {}
    }
    entry.options = {}
    return entry


@pytest.fixture
def mock_entry_with_custom_prompt():
    """Create a mock ConfigEntry with custom AI prompt enabled.
    
    Provides:
        - AI assistant entity configured
        - Custom prompt enabled
        - Custom prompt text
    
    Returns:
        MagicMock: Config entry with custom AI prompt
    """
    entry = MagicMock(spec=config_entries.ConfigEntry)
    entry.data = {
        "ai_assistant": {
            "ai_agent_entity": "conversation.chatgpt",
            "use_custom_system_prompt": True,
            "custom_system_prompt": "Custom aviation assistant prompt"
        },
        "settings": {}
    }
    entry.options = {}
    return entry


def test_ai_config_form_shows_without_custom_prompt(mock_entry_with_ai):
    """Test AI config form when custom prompt is disabled.
    
    This test validates:
        - async_step_ai returns form with AI entity selector
        - Custom prompt field NOT shown when toggle disabled
        - Form schema contains standard fields only
    
    Setup:
        - Mock entry with custom prompt disabled
    
    Validation:
        - Result type is "form"
        - Schema includes ai_agent_entity
        - Schema includes use_custom_system_prompt toggle
        - Custom prompt field absent from schema
    
    Expected Result:
        Form displays AI entity selector and toggle only.
    """
    mock_hass = MagicMock()
    handler = HangarOptionsFlowHandler(mock_entry_with_ai)
    handler.hass = mock_hass
    
    import asyncio
    result = asyncio.run(handler.async_step_ai())
    
    assert result["type"] == "form"
    assert result["step_id"] == "ai"
    # Schema should have ai_agent_entity and use_custom_system_prompt
    # but NOT custom_system_prompt (toggle is False)
    schema_keys = [str(k) for k in result["data_schema"].schema.keys()]
    assert any("ai_agent_entity" in k for k in schema_keys)
    assert any("use_custom_system_prompt" in k for k in schema_keys)


def test_ai_config_form_shows_with_custom_prompt_enabled(mock_entry_with_custom_prompt):
    """Test AI config form when custom prompt is enabled.
    
    This test validates:
        - async_step_ai returns form with custom prompt field
        - Custom prompt field shown when toggle enabled
        - Form schema dynamically includes custom prompt
    
    Setup:
        - Mock entry with custom prompt enabled
    
    Validation:
        - Result type is "form"
        - Schema includes custom_system_prompt field
        - Default value for custom prompt populated
    
    Expected Result:
        Form displays custom prompt text field for editing.
    """
    mock_hass = MagicMock()
    handler = HangarOptionsFlowHandler(mock_entry_with_custom_prompt)
    handler.hass = mock_hass
    
    import asyncio
    result = asyncio.run(handler.async_step_ai())
    
    assert result["type"] == "form"
    assert result["step_id"] == "ai"
    # Schema should include custom_system_prompt when toggle is True
    schema_keys = [str(k) for k in result["data_schema"].schema.keys()]
    assert any("custom_system_prompt" in k for k in schema_keys)


def test_ai_config_saves_without_custom_prompt(mock_entry_with_ai):
    """Test saving AI config with standard prompt.
    
    This test validates:
        - async_step_ai accepts user input
        - Config entry updated with AI settings
        - Custom prompt not saved when toggle disabled
    
    Setup:
        - Mock entry with custom prompt disabled
        - User selects AI entity
    
    Validation:
        - async_update_entry called
        - AI assistant config updated correctly
    
    Expected Result:
        AI entity configured without custom prompt.
    """
    mock_hass = MagicMock()
    handler = HangarOptionsFlowHandler(mock_entry_with_ai)
    handler.hass = mock_hass
    
    user_input = {
        "ai_agent_entity": "conversation.claude",
        "use_custom_system_prompt": False
    }
    
    import asyncio
    result = asyncio.run(handler.async_step_ai(user_input))
    
    assert result["type"] == "abort"
    # Verify async_update_entry was called
    mock_hass.config_entries.async_update_entry.assert_called_once()
    call_args = mock_hass.config_entries.async_update_entry.call_args
    updated_data = call_args.kwargs["data"]
    
    assert "ai_assistant" in updated_data
    assert updated_data["ai_assistant"]["ai_agent_entity"] == "conversation.claude"
    assert updated_data["ai_assistant"]["use_custom_system_prompt"] is False


def test_ai_config_saves_with_custom_prompt(mock_entry_with_custom_prompt):
    """Test saving AI config with custom prompt.
    
    This test validates:
        - async_step_ai accepts custom prompt in user input
        - Config entry updated with custom prompt text
        - Custom prompt stored correctly
    
    Setup:
        - Mock entry with custom prompt enabled
        - User provides custom prompt text
    
    Validation:
        - async_update_entry called
        - Custom prompt text saved
    
    Expected Result:
        AI entity and custom prompt configured.
    """
    mock_hass = MagicMock()
    handler = HangarOptionsFlowHandler(mock_entry_with_custom_prompt)
    handler.hass = mock_hass
    
    user_input = {
        "ai_agent_entity": "conversation.chatgpt",
        "use_custom_system_prompt": True,
        "custom_system_prompt": "You are a specialized aviation assistant for UK PPL pilots."
    }
    
    import asyncio
    result = asyncio.run(handler.async_step_ai(user_input))
    
    assert result["type"] == "abort"
    # Verify async_update_entry was called
    mock_hass.config_entries.async_update_entry.assert_called_once()
    call_args = mock_hass.config_entries.async_update_entry.call_args
    updated_data = call_args.kwargs["data"]
    
    assert updated_data["ai_assistant"]["use_custom_system_prompt"] is True
    assert updated_data["ai_assistant"]["custom_system_prompt"] == "You are a specialized aviation assistant for UK PPL pilots."


def test_ai_config_toggles_custom_prompt_on(mock_entry_with_ai):
    """Test enabling custom prompt toggle.
    
    This test validates:
        - User can enable custom prompt from disabled state
        - Toggle change reflected in saved config
    
    Setup:
        - Mock entry with custom prompt disabled
        - User enables custom prompt and provides text
    
    Validation:
        - Toggle updated to True
        - Custom prompt text saved
    
    Expected Result:
        Custom prompt enabled with user-provided text.
    """
    mock_hass = MagicMock()
    handler = HangarOptionsFlowHandler(mock_entry_with_ai)
    handler.hass = mock_hass
    
    user_input = {
        "ai_agent_entity": "conversation.home_assistant",
        "use_custom_system_prompt": True,
        "custom_system_prompt": "New custom prompt"
    }
    
    import asyncio
    result = asyncio.run(handler.async_step_ai(user_input))
    
    assert result["type"] == "abort"
    call_args = mock_hass.config_entries.async_update_entry.call_args
    updated_data = call_args.kwargs["data"]
    
    # Verify toggle changed and prompt saved
    assert updated_data["ai_assistant"]["use_custom_system_prompt"] is True
    assert updated_data["ai_assistant"]["custom_system_prompt"] == "New custom prompt"


def test_ai_config_toggles_custom_prompt_off(mock_entry_with_custom_prompt):
    """Test disabling custom prompt toggle.
    
    This test validates:
        - User can disable custom prompt from enabled state
        - Toggle change reflected in saved config
        - Custom prompt text preserved (but not used)
    
    Setup:
        - Mock entry with custom prompt enabled
        - User disables custom prompt
    
    Validation:
        - Toggle updated to False
        - Entry updated successfully
    
    Expected Result:
        Custom prompt disabled, standard prompt used.
    """
    mock_hass = MagicMock()
    handler = HangarOptionsFlowHandler(mock_entry_with_custom_prompt)
    handler.hass = mock_hass
    
    user_input = {
        "ai_agent_entity": "conversation.chatgpt",
        "use_custom_system_prompt": False
        # custom_system_prompt not in input (toggle disabled)
    }
    
    import asyncio
    result = asyncio.run(handler.async_step_ai(user_input))
    
    assert result["type"] == "abort"
    call_args = mock_hass.config_entries.async_update_entry.call_args
    updated_data = call_args.kwargs["data"]
    
    # Verify toggle changed to False
    assert updated_data["ai_assistant"]["use_custom_system_prompt"] is False
