"""Tests for config flow initialization and property handling."""
import pytest
from unittest.mock import MagicMock, patch
from homeassistant import config_entries
from custom_components.hangar_assistant.config_flow import (
    HangarAssistantConfigFlow,
    HangarOptionsFlowHandler,
)
from custom_components.hangar_assistant.const import DOMAIN


class TestHangarConfigFlow:
    """Test initial config flow."""
    
    def test_config_flow_init(self):
        """Test ConfigFlow initializes without errors."""
        flow = HangarAssistantConfigFlow()
        assert flow is not None
        assert flow.VERSION == 1


class TestHangarOptionsFlowInit:
    """Test OptionsFlowHandler initialization with proper property handling."""
    
    def test_options_flow_init_with_entry(self):
        """Test OptionsFlowHandler initializes without AttributeError on config_entry.
        
        This test ensures the fix for:
        AttributeError: property 'config_entry' of 'HangarOptionsFlowHandler' 
        object has no setter
        """
        # Create a mock ConfigEntry
        mock_entry = MagicMock(spec=config_entries.ConfigEntry)
        mock_entry.data = {
            "airfields": [{"name": "Popham", "elevation": 100}],
            "aircraft": [],
            "pilots": [],
            "settings": {},
        }
        mock_entry.options = {}
        
        # Should initialize without raising AttributeError
        handler = HangarOptionsFlowHandler(mock_entry)
        assert handler is not None
        
        # Verify private attribute is set correctly
        assert handler._config_entry is mock_entry
    
    def test_options_flow_entry_data_access(self):
        """Test that _entry_data() method works correctly."""
        mock_entry = MagicMock(spec=config_entries.ConfigEntry)
        test_data = {"airfields": [{"name": "Test"}]}
        mock_entry.data = test_data
        mock_entry.options = {}
        
        handler = HangarOptionsFlowHandler(mock_entry)
        
        # Should retrieve data without errors
        entry_data = handler._entry_data()
        assert entry_data == test_data
    
    def test_options_flow_entry_options_access(self):
        """Test that _entry_options() method works correctly."""
        mock_entry = MagicMock(spec=config_entries.ConfigEntry)
        mock_entry.data = {}
        test_options = {"some_key": "some_value"}
        mock_entry.options = test_options
        
        handler = HangarOptionsFlowHandler(mock_entry)
        
        # Should retrieve options without errors
        entry_options = handler._entry_options()
        assert entry_options == test_options
    
    def test_options_flow_with_none_data(self):
        """Test graceful handling when data is None."""
        mock_entry = MagicMock(spec=config_entries.ConfigEntry)
        mock_entry.data = None
        mock_entry.options = None
        
        handler = HangarOptionsFlowHandler(mock_entry)
        
        # Should return empty dicts, not raise errors
        entry_data = handler._entry_data()
        assert entry_data == {}
        
        entry_options = handler._entry_options()
        assert entry_options == {}
    
    
    def test_options_flow_uses_private_attribute(self):
        """Verify that OptionsFlowHandler uses private _config_entry attribute.
        
        The original error was:
        AttributeError: property 'config_entry' of 'HangarOptionsFlowHandler' 
        object has no setter
        
        This was fixed by using self._config_entry instead of self.config_entry.
        """
        mock_entry = MagicMock(spec=config_entries.ConfigEntry)
        mock_entry.data = {}
        mock_entry.options = {}
        
        handler = HangarOptionsFlowHandler(mock_entry)
        
        # Verify private attribute is used (not public config_entry)
        assert hasattr(handler, '_config_entry')
        assert handler._config_entry is mock_entry
        
        # Verify the handler can still access entry methods through private attribute
        assert handler._entry_data() == {}
        assert handler._entry_options() == {}



class TestOptionsFlowDataManagement:
    """Test data manipulation methods in OptionsFlowHandler."""
    
    def test_list_from_with_list(self):
        """Test _list_from with valid list."""
        result = HangarOptionsFlowHandler._list_from([1, 2, 3])
        assert result == [1, 2, 3]
        assert isinstance(result, list)
    
    def test_list_from_with_non_list(self):
        """Test _list_from with non-list value."""
        result = HangarOptionsFlowHandler._list_from("not_a_list")
        assert result == []
    
    def test_list_from_with_none(self):
        """Test _list_from with None."""
        result = HangarOptionsFlowHandler._list_from(None)
        assert result == []
    
    def test_list_from_returns_copy(self):
        """Test that _list_from returns a copy, not the original."""
        original = [1, 2, 3]
        result = HangarOptionsFlowHandler._list_from(original)
        
        # Modify result should not affect original
        result.append(4)
        assert original == [1, 2, 3]
        assert result == [1, 2, 3, 4]
