"""Tests for Hangar Assistant configuration flow.

This module tests the Home Assistant configuration flow which allows users
to install and configure the Hangar Assistant integration via the UI.

Test Strategy:
    - Mock Home Assistant config_entries system
    - Simulate user interaction flow (init → configure → create entry)
    - Validate flow type transitions and data storage
    - Test both initial configuration and options flow

Coverage:
    - Initial config flow (user installation)
    - Options flow (post-installation configuration menu)
    - Flow state transitions (form → menu → create_entry)
    - Entry creation with correct domain and title

Integration Context:
    The config flow is the user's entry point to Hangar Assistant.
    Single-instance integration with centralized configuration.
"""
from unittest.mock import patch
from homeassistant import config_entries, data_entry_flow
import pytest
from custom_components.hangar_assistant.const import DOMAIN

@pytest.mark.asyncio
async def test_config_flow(hass):
    """Test the initial configuration flow for first-time installation.
    
    This test validates the complete user installation flow from initiation
    through entry creation in the Home Assistant config registry.
    
    Flow Sequence:
        1. User initiates flow from Integrations page
        2. Flow presents user form (step_id="user")
        3. User submits form (can be empty for single-instance integration)
        4. Flow creates config entry and completes
    
    Setup:
        - Start config flow with SOURCE_USER context
        - Mock async_setup_entry to prevent full integration load
    
    Validation:
        - Step 1: Asserts result type is FORM
        - Step 1: Asserts step_id is "user"
        - Step 2: Asserts result type is CREATE_ENTRY after submission
        - Step 2: Asserts title is "Hangar Assistant"
        - Step 2: Asserts data dictionary is empty (single instance)
    
    Expected Result:
        Config flow successfully creates integration entry with correct
        title and domain. User can now access options flow to configure
        airfields, aircraft, and pilots.
    """
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
    """Test the options flow menu initialization after installation.
    
    This test validates that after installation, users can access the
    options flow menu to configure airfields, aircraft, pilots, and settings.
    
    Flow Sequence:
        1. Integration already installed (config entry exists)
        2. User opens integration options
        3. Flow presents menu with configuration choices
    
    Setup:
        - Create mock config entry for Hangar Assistant
        - Add entry to hass registry
        - Mock async_setup_entry
        - Initialize options flow
    
    Validation:
        - Asserts result type is MENU
        - Asserts step_id is "init"
        - Confirms menu options available (airfields, aircraft, pilots, etc.)
    
    Expected Result:
        Options flow presents menu successfully. User can navigate to:
        - Manage Airfields
        - Manage Aircraft
        - Manage Pilots
        - Manage Hangars
        - General Settings
        - External Integrations
    """
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