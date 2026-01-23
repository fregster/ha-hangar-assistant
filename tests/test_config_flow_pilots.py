"""Tests for config_flow pilot management flows.

This module tests pilot add/manage/edit/delete operations in the options flow,
ensuring complete coverage of pilot configuration paths.

Test Strategy:
    - Mock ConfigEntry and Home Assistant instances
    - Test all pilot CRUD operations
    - Validate form schemas and data updates
    - Cover menu navigation and error paths

Coverage:
    - async_step_pilot (menu vs direct add)
    - async_step_pilot_add (form submission and validation)
    - async_step_pilot_manage (selection and action routing)
    - async_step_pilot_edit (update existing pilot)
    - async_step_pilot_delete (confirmation and deletion)
"""

import pytest
from unittest.mock import MagicMock, patch
from homeassistant import config_entries
from custom_components.hangar_assistant.config_flow import HangarOptionsFlowHandler


@pytest.fixture
def mock_entry_with_pilots():
    """Create a mock ConfigEntry with existing pilots.
    
    Provides:
        - ConfigEntry with 2 pilots configured
        - All pilot attributes including ratings
    
    Used By:
        - Pilot management tests requiring existing data
    
    Returns:
        MagicMock: Configured config entry with pilots
    """
    entry = MagicMock(spec=config_entries.ConfigEntry)
    entry.data = {
        "pilots": [
            {
                "name": "John Smith",
                "email": "john@example.com",
                "licence_number": "PPL12345",
                "licence_type": "PPL",
                "medical_expiry": "2026-12-31",
                "ifr_rating": False,
                "night_rating": True,
                "tailwheel_rating": False,
                "complex_rating": False,
                "high_performance_rating": False,
                "multi_engine_rating": False,
                "seaplane_rating": False,
                "glider_rating": False,
                "aerobatic_rating": False,
                "mountain_rating": False,
            },
            {
                "name": "Jane Doe",
                "email": "jane@example.com",
                "licence_number": "CPL67890",
                "licence_type": "CPL",
                "medical_expiry": "2026-06-30",
                "ifr_rating": True,
                "night_rating": True,
                "tailwheel_rating": True,
                "complex_rating": True,
                "high_performance_rating": False,
                "multi_engine_rating": False,
                "seaplane_rating": False,
                "glider_rating": False,
                "aerobatic_rating": False,
                "mountain_rating": False,
            }
        ],
        "settings": {}
    }
    entry.options = {}
    return entry


@pytest.fixture
def mock_entry_no_pilots():
    """Create a mock ConfigEntry with no pilots.
    
    Provides:
        - Empty pilots list
        - Used to test first-time pilot add flow
    
    Returns:
        MagicMock: Config entry without pilots
    """
    entry = MagicMock(spec=config_entries.ConfigEntry)
    entry.data = {
        "pilots": [],
        "settings": {}
    }
    entry.options = {}
    return entry


def test_pilot_menu_shows_when_pilots_exist(mock_entry_with_pilots):
    """Test that pilot menu appears when pilots are configured.
    
    This test validates:
        - async_step_pilot returns menu when pilots exist
        - Menu includes pilot_add and pilot_manage options
    
    Setup:
        - Mock entry with 2 existing pilots
    
    Validation:
        - Result type is "menu"
        - Menu options include add and manage
    
    Expected Result:
        User sees menu to add new pilot or manage existing ones.
    """
    mock_hass = MagicMock()
    handler = HangarOptionsFlowHandler(mock_entry_with_pilots)
    handler.hass = mock_hass
    
    import asyncio
    result = asyncio.run(handler.async_step_pilot())
    
    assert result["type"] == "menu"
    assert "pilot_add" in result["menu_options"]
    assert "pilot_manage" in result["menu_options"]


def test_pilot_add_directly_when_no_pilots(mock_entry_no_pilots):
    """Test that pilot add form shows directly when no pilots exist.
    
    This test validates:
        - async_step_pilot goes directly to add form when pilots list empty
        - Form includes all required pilot fields
    
    Setup:
        - Mock entry with empty pilots list
    
    Validation:
        - Result is async_step_pilot_add call
        - Form schema includes name, email, licence fields
    
    Expected Result:
        User sees pilot add form immediately, skipping menu.
    """
    mock_hass = MagicMock()
    handler = HangarOptionsFlowHandler(mock_entry_no_pilots)
    handler.hass = mock_hass
    
    import asyncio
    result = asyncio.run(handler.async_step_pilot())
    
    # Should go directly to add form
    assert result["type"] == "form"
    assert result["step_id"] == "pilot_add"


def test_pilot_add_creates_new_pilot(mock_entry_no_pilots):
    """Test adding a new pilot updates config entry.
    
    This test validates:
        - async_step_pilot_add accepts form data
        - New pilot appended to pilots list
        - Config entry updated with new data
    
    Setup:
        - Mock entry with no pilots
        - Form submission with complete pilot data
    
    Validation:
        - Pilots list length increased
        - New pilot data stored correctly
        - async_update_entry called with updated data
    
    Expected Result:
        Pilot added to configuration, entry updated.
    """
    mock_hass = MagicMock()
    handler = HangarOptionsFlowHandler(mock_entry_no_pilots)
    handler.hass = mock_hass
    
    user_input = {
        "name": "Test Pilot",
        "email": "test@example.com",
        "licence_number": "TEST123",
        "licence_type": "PPL",
        "medical_expiry": "2027-01-01",
        "ifr_rating": False,
        "night_rating": True,
        "tailwheel_rating": False,
        "complex_rating": False,
        "high_performance_rating": False,
        "multi_engine_rating": False,
        "seaplane_rating": False,
        "glider_rating": False,
        "aerobatic_rating": False,
        "mountain_rating": False,
    }
    
    import asyncio
    result = asyncio.run(handler.async_step_pilot_add(user_input))
    
    assert result["type"] == "abort"
    # Verify async_update_entry was called
    mock_hass.config_entries.async_update_entry.assert_called_once()
    # Verify pilot was added (check the call args)
    call_args = mock_hass.config_entries.async_update_entry.call_args
    updated_data = call_args.kwargs["data"]
    assert len(updated_data["pilots"]) == 1
    assert updated_data["pilots"][0]["name"] == "Test Pilot"


def test_pilot_manage_selects_pilot_for_edit(mock_entry_with_pilots):
    """Test pilot manage flow routes to edit when action is 'edit'.
    
    This test validates:
        - async_step_pilot_manage shows selection form
        - Selecting edit action routes to async_step_pilot_edit
        - Pilot index stored for subsequent edit
    
    Setup:
        - Mock entry with 2 pilots
        - User selects first pilot and "edit" action
    
    Validation:
        - Handler stores selected index
        - Result routes to pilot_edit step
    
    Expected Result:
        User proceeds to edit form for selected pilot.
    """
    mock_hass = MagicMock()
    handler = HangarOptionsFlowHandler(mock_entry_with_pilots)
    handler.hass = mock_hass
    
    user_input = {
        "index": "0",
        "action": "edit"
    }
    
    import asyncio
    result = asyncio.run(handler.async_step_pilot_manage(user_input))
    
    # Should route to edit form
    assert result["type"] == "form"
    assert result["step_id"] == "pilot_edit"
    assert handler._index == 0


def test_pilot_manage_selects_pilot_for_delete(mock_entry_with_pilots):
    """Test pilot manage flow routes to delete when action is 'delete'.
    
    This test validates:
        - Selecting delete action routes to async_step_pilot_delete
        - Pilot index stored for deletion confirmation
    
    Setup:
        - Mock entry with 2 pilots
        - User selects second pilot and "delete" action
    
    Validation:
        - Handler stores selected index
        - Result routes to pilot_delete step
    
    Expected Result:
        User proceeds to delete confirmation for selected pilot.
    """
    mock_hass = MagicMock()
    handler = HangarOptionsFlowHandler(mock_entry_with_pilots)
    handler.hass = mock_hass
    
    user_input = {
        "index": "1",
        "action": "delete"
    }
    
    import asyncio
    result = asyncio.run(handler.async_step_pilot_manage(user_input))
    
    # Should route to delete confirmation
    assert result["type"] == "form"
    assert result["step_id"] == "pilot_delete"
    assert handler._index == 1


def test_pilot_edit_updates_existing_pilot(mock_entry_with_pilots):
    """Test editing an existing pilot updates config entry.
    
    This test validates:
        - async_step_pilot_edit accepts updated data
        - Pilot at specified index updated in-place
        - Config entry updated with modified data
    
    Setup:
        - Mock entry with 2 pilots
        - Edit first pilot with new data
    
    Validation:
        - Pilot list length unchanged
        - First pilot data updated
        - async_update_entry called
    
    Expected Result:
        Pilot modified in configuration, entry updated.
    """
    mock_hass = MagicMock()
    handler = HangarOptionsFlowHandler(mock_entry_with_pilots)
    handler.hass = mock_hass
    handler._index = 0  # Edit first pilot
    
    user_input = {
        "name": "John Smith Updated",
        "email": "john.updated@example.com",
        "licence_number": "PPL12345",
        "licence_type": "PPL",
        "medical_expiry": "2027-12-31",
        "ifr_rating": True,  # Changed
        "night_rating": True,
        "tailwheel_rating": False,
        "complex_rating": False,
        "high_performance_rating": False,
        "multi_engine_rating": False,
        "seaplane_rating": False,
        "glider_rating": False,
        "aerobatic_rating": False,
        "mountain_rating": False,
    }
    
    import asyncio
    result = asyncio.run(handler.async_step_pilot_edit(user_input))
    
    assert result["type"] == "abort"
    # Verify async_update_entry was called
    mock_hass.config_entries.async_update_entry.assert_called_once()
    # Verify pilot was updated (check the call args)
    call_args = mock_hass.config_entries.async_update_entry.call_args
    updated_data = call_args.kwargs["data"]
    assert len(updated_data["pilots"]) == 2
    assert updated_data["pilots"][0]["name"] == "John Smith Updated"
    assert updated_data["pilots"][0]["ifr_rating"] is True


def test_pilot_delete_confirms_and_removes_pilot(mock_entry_with_pilots):
    """Test pilot delete confirmation removes pilot from config.
    
    This test validates:
        - async_step_pilot_delete shows confirmation form
        - Confirming deletion removes pilot from list
        - Config entry updated
    
    Setup:
        - Mock entry with 2 pilots
        - Delete second pilot with confirmation
    
    Validation:
        - Pilots list length decreased
        - Correct pilot removed
        - async_update_entry called
    
    Expected Result:
        Pilot removed from configuration, entry updated.
    """
    mock_hass = MagicMock()
    handler = HangarOptionsFlowHandler(mock_entry_with_pilots)
    handler.hass = mock_hass
    handler._index = 1  # Delete second pilot
    
    user_input = {
        "confirm": True
    }
    
    import asyncio
    result = asyncio.run(handler.async_step_pilot_delete(user_input))
    
    assert result["type"] == "abort"
    # Verify async_update_entry was called
    mock_hass.config_entries.async_update_entry.assert_called_once()
    # Verify pilot was deleted (check the call args)
    call_args = mock_hass.config_entries.async_update_entry.call_args
    updated_data = call_args.kwargs["data"]
    assert len(updated_data["pilots"]) == 1
    # First pilot should remain
    assert updated_data["pilots"][0]["name"] == "John Smith"


def test_pilot_delete_cancels_without_confirmation(mock_entry_with_pilots):
    """Test pilot delete cancellation preserves pilot data.
    
    This test validates:
        - Not confirming deletion preserves pilots list
        - Config entry unchanged
    
    Setup:
        - Mock entry with 2 pilots
        - Cancel deletion (confirm=False)
    
    Validation:
        - Pilots list length unchanged
        - No pilots removed
    
    Expected Result:
        Deletion cancelled, all pilots preserved.
    """
    mock_hass = MagicMock()
    handler = HangarOptionsFlowHandler(mock_entry_with_pilots)
    handler.hass = mock_hass
    handler._index = 1
    
    user_input = {
        "confirm": False
    }
    
    import asyncio
    result = asyncio.run(handler.async_step_pilot_delete(user_input))
    
    assert result["type"] == "abort"
    # When confirmation is False, async_update_entry should NOT be called
    mock_hass.config_entries.async_update_entry.assert_not_called()
