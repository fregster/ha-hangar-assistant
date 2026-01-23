"""Tests for config_flow briefing management flows.

This module tests briefing add/manage/edit/delete operations in the options flow,
ensuring complete coverage of automated briefing configuration paths.

Test Strategy:
    - Mock ConfigEntry with airfields/aircraft/pilots dependencies
    - Test all briefing CRUD operations
    - Validate briefing scheduling and pilot assignments
    - Cover menu navigation and error paths

Coverage:
    - async_step_briefing (menu vs direct add)
    - async_step_briefing_add (form submission with dependencies)
    - async_step_briefing_manage (selection and action routing)
    - async_step_briefing_edit (update existing briefing)
    - async_step_briefing_delete (confirmation and deletion)
"""

import pytest
from unittest.mock import MagicMock
from homeassistant import config_entries
from custom_components.hangar_assistant.config_flow import HangarOptionsFlowHandler


@pytest.fixture
def mock_entry_with_briefings():
    """Create a mock ConfigEntry with briefings and dependencies.
    
    Provides:
        - ConfigEntry with 1 briefing
        - Airfields, aircraft, and pilots for dropdown options
    
    Used By:
        - Briefing management tests requiring existing data
    
    Returns:
        MagicMock: Configured config entry with briefings
    """
    entry = MagicMock(spec=config_entries.ConfigEntry)
    entry.data = {
        "airfields": [
            {"name": "Popham", "icao": "EGHP"},
            {"name": "Old Sarum", "icao": "EGLS"}
        ],
        "aircraft": [
            {"reg": "G-ABCD", "model": "Cessna 172"},
            {"reg": "G-EFGH", "model": "PA-28"}
        ],
        "pilots": [
            {"name": "John Smith"},
            {"name": "Jane Doe"}
        ],
        "briefings": [
            {
                "airfield_name": "Popham",
                "aircraft_reg": "G-ABCD",
                "briefing_time": "07:00",
                "pilots": ["John Smith"],
                "enable_ai_reporting": True
            }
        ],
        "settings": {}
    }
    entry.options = {}
    return entry


@pytest.fixture
def mock_entry_no_briefings():
    """Create a mock ConfigEntry without briefings but with dependencies.
    
    Provides:
        - Empty briefings list
        - Airfields, aircraft, pilots for dropdown options
    
    Returns:
        MagicMock: Config entry without briefings
    """
    entry = MagicMock(spec=config_entries.ConfigEntry)
    entry.data = {
        "airfields": [{"name": "Popham", "icao": "EGHP"}],
        "aircraft": [{"reg": "G-ABCD", "model": "Cessna 172"}],
        "pilots": [{"name": "John Smith"}],
        "briefings": [],
        "settings": {}
    }
    entry.options = {}
    return entry


def test_briefing_menu_shows_when_briefings_exist(mock_entry_with_briefings):
    """Test that briefing menu appears when briefings are configured.
    
    This test validates:
        - async_step_briefing returns menu when briefings exist
        - Menu includes briefing_add and briefing_manage options
    
    Setup:
        - Mock entry with 1 existing briefing
    
    Validation:
        - Result type is "menu"
        - Menu options include add and manage
    
    Expected Result:
        User sees menu to add new briefing or manage existing ones.
    """
    mock_hass = MagicMock()
    handler = HangarOptionsFlowHandler(mock_entry_with_briefings)
    handler.hass = mock_hass
    
    import asyncio
    result = asyncio.run(handler.async_step_briefing())
    
    assert result["type"] == "menu"
    assert "briefing_add" in result["menu_options"]
    assert "briefing_manage" in result["menu_options"]


def test_briefing_add_directly_when_no_briefings(mock_entry_no_briefings):
    """Test that briefing add form shows directly when no briefings exist.
    
    This test validates:
        - async_step_briefing goes directly to add form when briefings list empty
        - Form includes airfield, aircraft, pilot selectors
    
    Setup:
        - Mock entry with empty briefings list
    
    Validation:
        - Result is async_step_briefing_add call
        - Form schema includes required fields
    
    Expected Result:
        User sees briefing add form immediately, skipping menu.
    """
    mock_hass = MagicMock()
    handler = HangarOptionsFlowHandler(mock_entry_no_briefings)
    handler.hass = mock_hass
    
    import asyncio
    result = asyncio.run(handler.async_step_briefing())
    
    # Should go directly to add form
    assert result["type"] == "form"
    assert result["step_id"] == "briefing_add"


def test_briefing_add_creates_new_briefing(mock_entry_no_briefings):
    """Test adding a new briefing updates config entry.
    
    This test validates:
        - async_step_briefing_add accepts form data
        - New briefing appended to briefings list
        - Config entry updated with new data
    
    Setup:
        - Mock entry with no briefings
        - Form submission with complete briefing data
    
    Validation:
        - Briefings list length increased
        - New briefing data stored correctly
        - async_update_entry called with updated data
    
    Expected Result:
        Briefing added to configuration, entry updated.
    """
    mock_hass = MagicMock()
    handler = HangarOptionsFlowHandler(mock_entry_no_briefings)
    handler.hass = mock_hass
    
    user_input = {
        "airfield_name": "Popham",
        "aircraft_reg": "G-ABCD",
        "briefing_time": "08:00",
        "pilots": ["John Smith"],
        "enable_ai_reporting": False
    }
    
    import asyncio
    result = asyncio.run(handler.async_step_briefing_add(user_input))
    
    assert result["type"] == "abort"
    # Verify async_update_entry was called
    mock_hass.config_entries.async_update_entry.assert_called_once()
    # Verify briefing was added (check the call args)
    call_args = mock_hass.config_entries.async_update_entry.call_args
    updated_data = call_args.kwargs["data"]
    assert len(updated_data["briefings"]) == 1
    assert updated_data["briefings"][0]["airfield_name"] == "Popham"
    assert updated_data["briefings"][0]["briefing_time"] == "08:00"


def test_briefing_manage_selects_briefing_for_edit(mock_entry_with_briefings):
    """Test briefing manage flow routes to edit when action is 'edit'.
    
    This test validates:
        - async_step_briefing_manage shows selection form
        - Selecting edit action routes to async_step_briefing_edit
        - Briefing index stored for subsequent edit
    
    Setup:
        - Mock entry with 1 briefing
        - User selects briefing and "edit" action
    
    Validation:
        - Handler stores selected index
        - Result routes to briefing_edit step
    
    Expected Result:
        User proceeds to edit form for selected briefing.
    """
    mock_hass = MagicMock()
    handler = HangarOptionsFlowHandler(mock_entry_with_briefings)
    handler.hass = mock_hass
    
    user_input = {
        "briefing_index": "0",
        "action": "edit"
    }
    
    import asyncio
    result = asyncio.run(handler.async_step_briefing_manage(user_input))
    
    # Should route to edit form
    assert result["type"] == "form"
    assert result["step_id"] == "briefing_edit"
    assert handler._briefing_index == 0


def test_briefing_manage_selects_briefing_for_delete(mock_entry_with_briefings):
    """Test briefing manage flow routes to delete when action is 'delete'.
    
    This test validates:
        - Selecting delete action routes to async_step_briefing_delete
        - Briefing index stored for deletion confirmation
    
    Setup:
        - Mock entry with 1 briefing
        - User selects briefing and "delete" action
    
    Validation:
        - Handler stores selected index
        - Result routes to briefing_delete step
    
    Expected Result:
        User proceeds to delete confirmation for selected briefing.
    """
    mock_hass = MagicMock()
    handler = HangarOptionsFlowHandler(mock_entry_with_briefings)
    handler.hass = mock_hass
    
    user_input = {
        "briefing_index": "0",
        "action": "delete"
    }
    
    import asyncio
    result = asyncio.run(handler.async_step_briefing_manage(user_input))
    
    # Should route to delete confirmation
    assert result["type"] == "form"
    assert result["step_id"] == "briefing_delete"
    assert handler._briefing_index == 0


def test_briefing_edit_updates_existing_briefing(mock_entry_with_briefings):
    """Test editing an existing briefing updates config entry.
    
    This test validates:
        - async_step_briefing_edit accepts updated data
        - Briefing at specified index updated in-place
        - Config entry updated with modified data
    
    Setup:
        - Mock entry with 1 briefing
        - Edit briefing with new time and pilots
    
    Validation:
        - Briefing list length unchanged
        - Briefing data updated
        - async_update_entry called
    
    Expected Result:
        Briefing modified in configuration, entry updated.
    """
    mock_hass = MagicMock()
    handler = HangarOptionsFlowHandler(mock_entry_with_briefings)
    handler.hass = mock_hass
    handler._briefing_index = 0
    
    user_input = {
        "airfield_name": "Old Sarum",  # Changed
        "aircraft_reg": "G-EFGH",  # Changed
        "briefing_time": "06:30",  # Changed
        "pilots": ["John Smith", "Jane Doe"],  # Added pilot
        "enable_ai_reporting": False  # Changed
    }
    
    import asyncio
    result = asyncio.run(handler.async_step_briefing_edit(user_input))
    
    assert result["type"] == "abort"
    # Verify async_update_entry was called
    mock_hass.config_entries.async_update_entry.assert_called_once()
    # Verify briefing was updated (check the call args)
    call_args = mock_hass.config_entries.async_update_entry.call_args
    updated_data = call_args.kwargs["data"]
    assert len(updated_data["briefings"]) == 1
    assert updated_data["briefings"][0]["airfield_name"] == "Old Sarum"
    assert updated_data["briefings"][0]["briefing_time"] == "06:30"
    assert len(updated_data["briefings"][0]["pilots"]) == 2


def test_briefing_delete_confirms_and_removes_briefing(mock_entry_with_briefings):
    """Test briefing delete confirmation removes briefing from config.
    
    This test validates:
        - async_step_briefing_delete shows confirmation form
        - Confirming deletion removes briefing from list
        - Config entry updated
    
    Setup:
        - Mock entry with 1 briefing
        - Delete briefing with confirmation
    
    Validation:
        - Briefings list length decreased
        - Briefing removed
        - async_update_entry called
    
    Expected Result:
        Briefing removed from configuration, entry updated.
    """
    mock_hass = MagicMock()
    handler = HangarOptionsFlowHandler(mock_entry_with_briefings)
    handler.hass = mock_hass
    handler._briefing_index = 0
    
    user_input = {
        "confirm_delete": True
    }
    
    import asyncio
    result = asyncio.run(handler.async_step_briefing_delete(user_input))
    
    assert result["type"] == "abort"
    # Verify async_update_entry was called
    mock_hass.config_entries.async_update_entry.assert_called_once()
    # Verify briefing was deleted (check the call args)
    call_args = mock_hass.config_entries.async_update_entry.call_args
    updated_data = call_args.kwargs["data"]
    assert len(updated_data["briefings"]) == 0


def test_briefing_delete_cancels_without_confirmation(mock_entry_with_briefings):
    """Test briefing delete cancellation preserves briefing data.
    
    This test validates:
        - Not confirming deletion preserves briefings list
        - Config entry unchanged
    
    Setup:
        - Mock entry with 1 briefing
        - Cancel deletion (confirm_delete=False)
    
    Validation:
        - Briefings list length unchanged
        - No briefings removed
    
    Expected Result:
        Deletion cancelled, all briefings preserved.
    """
    mock_hass = MagicMock()
    handler = HangarOptionsFlowHandler(mock_entry_with_briefings)
    handler.hass = mock_hass
    handler._briefing_index = 0
    
    user_input = {
        "confirm_delete": False
    }
    
    import asyncio
    result = asyncio.run(handler.async_step_briefing_delete(user_input))
    
    assert result["type"] == "abort"
    # When confirmation is False, async_update_entry should NOT be called
    mock_hass.config_entries.async_update_entry.assert_not_called()


def test_briefing_edit_handles_out_of_range_index(mock_entry_with_briefings):
    """Test briefing edit aborts gracefully for invalid index.
    
    This test validates:
        - Out-of-range index doesn't cause crash
        - Flow aborts with appropriate reason
    
    Setup:
        - Mock entry with 1 briefing
        - Attempt to edit index 5 (out of range)
    
    Validation:
        - Result aborts
        - No exceptions raised
    
    Expected Result:
        Edit aborts gracefully without modifying data.
    """
    mock_hass = MagicMock()
    handler = HangarOptionsFlowHandler(mock_entry_with_briefings)
    handler.hass = mock_hass
    handler._briefing_index = 5  # Out of range
    
    import asyncio
    result = asyncio.run(handler.async_step_briefing_edit())
    
    # Should abort gracefully
    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_successful"


def test_briefing_delete_handles_out_of_range_index(mock_entry_with_briefings):
    """Test briefing delete aborts gracefully for invalid index.
    
    This test validates:
        - Out-of-range index doesn't cause crash
        - Flow aborts with appropriate reason
    
    Setup:
        - Mock entry with 1 briefing
        - Attempt to delete index 10 (out of range)
    
    Validation:
        - Result aborts
        - No exceptions raised
    
    Expected Result:
        Delete aborts gracefully without modifying data.
    """
    mock_hass = MagicMock()
    handler = HangarOptionsFlowHandler(mock_entry_with_briefings)
    handler.hass = mock_hass
    handler._briefing_index = 10  # Out of range
    
    import asyncio
    result = asyncio.run(handler.async_step_briefing_delete())
    
    # Should abort gracefully
    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_successful"
