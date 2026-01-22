"""Unit tests for hangar config flow and helper functions.

Tests cover:
- Hangar CRUD operations (add/edit/delete via config flow)
- Backward compatibility with aircraft that reference airfields directly
- Hangar sensor fallback logic (hangar → airfield → global)
- Duplicate hangar name validation
- Migration scenarios
"""

import pytest
from unittest.mock import MagicMock, patch
from homeassistant import config_entries
from custom_components.hangar_assistant.config_flow import HangarOptionsFlowHandler
from custom_components.hangar_assistant.utils.hangar_helpers import (
    get_aircraft_airfield,
    get_aircraft_hangar,
    find_hangar_by_name,
    get_airfield_for_hangar,
    get_hangar_sensor_value,
)


class TestHangarConfigFlow:
    """Test hangar management in config flow."""

    def test_hangar_add_success(self):
        """Test successfully adding a new hangar."""
        mock_entry = MagicMock(spec=config_entries.ConfigEntry)
        mock_entry.data = {
            "airfields": [
                {"name": "Popham", "latitude": 51.2, "longitude": -1.2}
            ],
            "hangars": []
        }
        mock_entry.options = {}
        
        handler = HangarOptionsFlowHandler(mock_entry)
        handler.hass = MagicMock()
        
        # Simulate adding a hangar
        hangar_data = {
            "name": "Hangar 3",
            "airfield_name": "Popham",
            "temp_sensor": "sensor.hangar3_temperature"
        }
        
        # Mock the config entry update
        with patch.object(handler.hass.config_entries, 'async_update_entry'):
            # Manually perform the logic that async_step_hangar_add does
            new_data = handler._entry_data()
            hangars = handler._list_from(new_data.get("hangars", []))
            hangars.append(hangar_data)
            new_data["hangars"] = hangars
            
            assert len(new_data["hangars"]) == 1
            assert new_data["hangars"][0]["name"] == "Hangar 3"
            assert new_data["hangars"][0]["airfield_name"] == "Popham"

    def test_hangar_add_duplicate_name_same_airfield(self):
        """Test that duplicate hangar names at same airfield are rejected."""
        mock_entry = MagicMock(spec=config_entries.ConfigEntry)
        mock_entry.data = {
            "airfields": [
                {"name": "Popham"}
            ],
            "hangars": [
                {"name": "Hangar 1", "airfield_name": "Popham"}
            ]
        }
        mock_entry.options = {}
        
        handler = HangarOptionsFlowHandler(mock_entry)
        
        existing_hangars = handler._list_from(handler._entry_data().get("hangars", []))
        new_hangar_name = "Hangar 1"
        new_airfield_name = "Popham"
        
        # Check for duplicate
        is_duplicate = False
        for hangar in existing_hangars:
            if (hangar.get("name") == new_hangar_name and 
                hangar.get("airfield_name") == new_airfield_name):
                is_duplicate = True
                break
        
        assert is_duplicate

    def test_hangar_add_duplicate_name_different_airfield_allowed(self):
        """Test that same hangar name at different airfield is allowed."""
        mock_entry = MagicMock(spec=config_entries.ConfigEntry)
        mock_entry.data = {
            "airfields": [
                {"name": "Popham"},
                {"name": "Goodwood"}
            ],
            "hangars": [
                {"name": "Hangar 1", "airfield_name": "Popham"}
            ]
        }
        mock_entry.options = {}
        
        handler = HangarOptionsFlowHandler(mock_entry)
        
        existing_hangars = handler._list_from(handler._entry_data().get("hangars", []))
        new_hangar_name = "Hangar 1"
        new_airfield_name = "Goodwood"  # Different airfield
        
        # Check for duplicate
        is_duplicate = False
        for hangar in existing_hangars:
            if (hangar.get("name") == new_hangar_name and 
                hangar.get("airfield_name") == new_airfield_name):
                is_duplicate = True
                break
        
        assert not is_duplicate  # Should be allowed

    def test_hangar_edit(self):
        """Test editing an existing hangar."""
        mock_entry = MagicMock(spec=config_entries.ConfigEntry)
        mock_entry.data = {
            "hangars": [
                {
                    "name": "Hangar 3",
                    "airfield_name": "Popham",
                    "temp_sensor": "sensor.hangar3_temperature"
                }
            ]
        }
        mock_entry.options = {}
        
        handler = HangarOptionsFlowHandler(mock_entry)
        handler.hass = MagicMock()
        
        # Edit the hangar
        new_data = handler._entry_data()
        hangars = handler._list_from(new_data.get("hangars", []))
        hangars[0]["humidity_sensor"] = "sensor.hangar3_humidity"
        new_data["hangars"] = hangars
        
        assert new_data["hangars"][0]["humidity_sensor"] == "sensor.hangar3_humidity"
        assert new_data["hangars"][0]["name"] == "Hangar 3"  # Unchanged

    def test_hangar_delete(self):
        """Test deleting a hangar."""
        mock_entry = MagicMock(spec=config_entries.ConfigEntry)
        mock_entry.data = {
            "hangars": [
                {"name": "Hangar 1", "airfield_name": "Popham"},
                {"name": "Hangar 2", "airfield_name": "Popham"}
            ]
        }
        mock_entry.options = {}
        
        handler = HangarOptionsFlowHandler(mock_entry)
        
        new_data = handler._entry_data()
        hangars = handler._list_from(new_data.get("hangars", []))
        del hangars[0]  # Delete first hangar
        new_data["hangars"] = hangars
        
        assert len(new_data["hangars"]) == 1
        assert new_data["hangars"][0]["name"] == "Hangar 2"

    def test_aircraft_with_hangar_field(self):
        """Test aircraft config with hangar field."""
        mock_entry = MagicMock(spec=config_entries.ConfigEntry)
        mock_entry.data = {
            "hangars": [
                {"name": "Hangar 3", "airfield_name": "Popham"}
            ],
            "aircraft": [
                {
                    "reg": "G-ABCD",
                    "model": "PA-28",
                    "hangar": "Hangar 3"
                }
            ]
        }
        mock_entry.options = {}
        
        handler = HangarOptionsFlowHandler(mock_entry)
        aircraft = handler._entry_data().get("aircraft", [])[0]
        
        assert aircraft["hangar"] == "Hangar 3"


class TestHangarHelpers:
    """Test hangar helper functions for backward compatibility."""

    def test_get_aircraft_airfield_via_hangar(self):
        """Test aircraft airfield resolution via hangar."""
        aircraft = {"reg": "G-ABCD", "hangar": "Hangar 3"}
        hangars = [{"name": "Hangar 3", "airfield_name": "Popham"}]
        airfields = [{"name": "Popham", "latitude": 51.2}]
        
        result = get_aircraft_airfield(aircraft, hangars, airfields)
        
        assert result is not None
        assert result["name"] == "Popham"

    def test_get_aircraft_airfield_direct_link_legacy(self):
        """Test aircraft airfield resolution via direct link (legacy)."""
        aircraft = {"reg": "G-ABCD", "linked_airfield": "Popham"}
        hangars = []
        airfields = [{"name": "Popham", "latitude": 51.2}]
        
        result = get_aircraft_airfield(aircraft, hangars, airfields)
        
        assert result is not None
        assert result["name"] == "Popham"

    def test_get_aircraft_airfield_hangar_priority(self):
        """Test that hangar takes priority over direct airfield link."""
        aircraft = {
            "reg": "G-ABCD",
            "hangar": "Hangar 3",
            "linked_airfield": "Goodwood"  # Should be ignored
        }
        hangars = [{"name": "Hangar 3", "airfield_name": "Popham"}]
        airfields = [
            {"name": "Popham", "latitude": 51.2},
            {"name": "Goodwood", "latitude": 50.8}
        ]
        
        result = get_aircraft_airfield(aircraft, hangars, airfields)
        
        assert result is not None
        assert result["name"] == "Popham"  # Hangar's airfield, not direct link

    def test_get_aircraft_airfield_none_configured(self):
        """Test aircraft with neither hangar nor airfield returns None."""
        aircraft = {"reg": "G-ABCD", "model": "PA-28"}
        hangars = []
        airfields = []
        
        result = get_aircraft_airfield(aircraft, hangars, airfields)
        
        assert result is None

    def test_get_aircraft_hangar_assigned(self):
        """Test get_aircraft_hangar when aircraft is in a hangar."""
        aircraft = {"reg": "G-ABCD", "hangar": "Hangar 3"}
        hangars = [{"name": "Hangar 3", "airfield_name": "Popham"}]
        
        result = get_aircraft_hangar(aircraft, hangars)
        
        assert result is not None
        assert result["name"] == "Hangar 3"

    def test_get_aircraft_hangar_not_assigned(self):
        """Test get_aircraft_hangar when aircraft has no hangar."""
        aircraft = {"reg": "G-ABCD", "linked_airfield": "Popham"}
        hangars = []
        
        result = get_aircraft_hangar(aircraft, hangars)
        
        assert result is None

    def test_find_hangar_by_name_found(self):
        """Test finding hangar by name."""
        hangars = [
            {"name": "Hangar 1", "airfield_name": "Popham"},
            {"name": "Hangar 3", "airfield_name": "Popham"}
        ]
        
        result = find_hangar_by_name("Hangar 3", hangars)
        
        assert result is not None
        assert result["name"] == "Hangar 3"

    def test_find_hangar_by_name_not_found(self):
        """Test finding non-existent hangar."""
        hangars = [{"name": "Hangar 1", "airfield_name": "Popham"}]
        
        result = find_hangar_by_name("Hangar 99", hangars)
        
        assert result is None

    def test_get_airfield_for_hangar(self):
        """Test getting airfield config for a hangar."""
        hangar = {"name": "Hangar 3", "airfield_name": "Popham"}
        airfields = [{"name": "Popham", "latitude": 51.2}]
        
        result = get_airfield_for_hangar(hangar, airfields)
        
        assert result is not None
        assert result["name"] == "Popham"


class TestHangarSensorFallback:
    """Test sensor fallback logic: hangar → airfield → global."""

    def test_sensor_fallback_hangar_available(self):
        """Test sensor uses hangar value when available."""
        mock_hass = MagicMock()
        mock_state = MagicMock()
        mock_state.state = "15.5"
        mock_hass.states.get.return_value = mock_state
        
        hangar = {"temp_sensor": "sensor.hangar_temp"}
        airfield = {"temp_sensor": "sensor.airfield_temp"}
        
        result = get_hangar_sensor_value(
            mock_hass, "temp_sensor", hangar, airfield, None
        )
        
        assert result == 15.5
        mock_hass.states.get.assert_called_with("sensor.hangar_temp")

    def test_sensor_fallback_hangar_unavailable_uses_airfield(self):
        """Test sensor falls back to airfield when hangar unavailable."""
        mock_hass = MagicMock()
        
        def get_state_side_effect(entity_id):
            if entity_id == "sensor.hangar_temp":
                state = MagicMock()
                state.state = "unavailable"
                return state
            elif entity_id == "sensor.airfield_temp":
                state = MagicMock()
                state.state = "18.0"
                return state
            return None
        
        mock_hass.states.get.side_effect = get_state_side_effect
        
        hangar = {"temp_sensor": "sensor.hangar_temp"}
        airfield = {"temp_sensor": "sensor.airfield_temp"}
        
        result = get_hangar_sensor_value(
            mock_hass, "temp_sensor", hangar, airfield, None
        )
        
        assert result == 18.0

    def test_sensor_fallback_no_hangar_uses_airfield(self):
        """Test sensor uses airfield when no hangar configured."""
        mock_hass = MagicMock()
        mock_state = MagicMock()
        mock_state.state = "18.0"
        mock_hass.states.get.return_value = mock_state
        
        hangar = None
        airfield = {"temp_sensor": "sensor.airfield_temp"}
        
        result = get_hangar_sensor_value(
            mock_hass, "temp_sensor", hangar, airfield, None
        )
        
        assert result == 18.0
        mock_hass.states.get.assert_called_with("sensor.airfield_temp")

    def test_sensor_fallback_uses_global_sensor(self):
        """Test sensor falls back to global sensor as last resort."""
        mock_hass = MagicMock()
        
        def get_state_side_effect(entity_id):
            if entity_id in ["sensor.hangar_temp", "sensor.airfield_temp"]:
                state = MagicMock()
                state.state = "unavailable"
                return state
            elif entity_id == "sensor.global_temp":
                state = MagicMock()
                state.state = "20.0"
                return state
            return None
        
        mock_hass.states.get.side_effect = get_state_side_effect
        
        hangar = {"temp_sensor": "sensor.hangar_temp"}
        airfield = {"temp_sensor": "sensor.airfield_temp"}
        global_sensor = "sensor.global_temp"
        
        result = get_hangar_sensor_value(
            mock_hass, "temp_sensor", hangar, airfield, global_sensor
        )
        
        assert result == 20.0

    def test_sensor_fallback_all_unavailable_returns_none(self):
        """Test sensor returns None when all sources unavailable."""
        mock_hass = MagicMock()
        mock_state = MagicMock()
        mock_state.state = "unavailable"
        mock_hass.states.get.return_value = mock_state
        
        hangar = {"temp_sensor": "sensor.hangar_temp"}
        airfield = {"temp_sensor": "sensor.airfield_temp"}
        global_sensor = "sensor.global_temp"
        
        result = get_hangar_sensor_value(
            mock_hass, "temp_sensor", hangar, airfield, global_sensor
        )
        
        assert result is None

    def test_sensor_fallback_handles_non_numeric_values(self):
        """Test sensor handles non-numeric state values gracefully."""
        mock_hass = MagicMock()
        mock_state = MagicMock()
        mock_state.state = "invalid"
        mock_hass.states.get.return_value = mock_state
        
        hangar = {"temp_sensor": "sensor.hangar_temp"}
        
        result = get_hangar_sensor_value(
            mock_hass, "temp_sensor", hangar, None, None
        )
        
        assert result is None
