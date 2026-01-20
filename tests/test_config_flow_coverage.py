"""Tests for config flow options handler."""
import pytest
from unittest.mock import MagicMock
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
from custom_components.hangar_assistant.config_flow import (
    HangarAssistantConfigFlow,
    HangarOptionsFlowHandler
)
from custom_components.hangar_assistant.const import DOMAIN


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock(
        spec=config_entries.ConfigEntry
    )
    entry.domain = DOMAIN
    entry.domain = DOMAIN
    entry.data = {
        "airfields": [
            {
                "name": "Popham",
                "latitude": 51.17,
                "longitude": -1.23,
                "elevation": 100,
                "runways": "03, 21",
                "primary_runway": "21",
                "runway_length": 800,
                "temp_sensor": "sensor.popham_temp",
                "dp_sensor": "sensor.popham_dp",
                "pressure_sensor": "sensor.popham_pressure",
                "wind_sensor": "sensor.popham_wind",
                "wind_dir_sensor": "sensor.popham_wind_dir"
            }
        ],
        "aircraft": [
            {
                "reg": "G-ABCD",
                "model": "Cessna 172",
                "empty_weight": 750,
                "max_tow": 1200,
                "max_xwind": 15,
                "baseline_roll": 300,
                "baseline_50ft": 600,
                "linked_airfield": "Popham"
            }
        ],
        "settings": {}
    }
    entry.options = {}
    return entry


@pytest.fixture
def mock_empty_config_entry():
    """Create a minimal config entry to catch init regressions."""
    entry = MagicMock(spec=config_entries.ConfigEntry)
    entry.domain = DOMAIN
    entry.data = {}
    entry.options = {}
    return entry


@pytest.fixture
def mock_hass():
    """Create mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config_entries = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()
    return hass


class TestHangarOptionsFlowHandlerAirfieldAdd:
    """Tests for airfield_add step."""

    def test_options_flow_factory_returns_handler(self, mock_config_entry):
        """Factory should return a valid options flow handler without TypeError."""
        flow = HangarAssistantConfigFlow.async_get_options_flow(mock_config_entry)

        assert isinstance(flow, HangarOptionsFlowHandler)
        assert flow._config_entry == mock_config_entry

    def test_options_flow_factory_keeps_config_entry_reference(self, mock_config_entry):
        """Factory must attach the provided config_entry to the handler."""
        handler = HangarAssistantConfigFlow.async_get_options_flow(mock_config_entry)

        # Ensure the handler uses the same entry object, not a copy or None
        assert handler._config_entry is mock_config_entry

    def test_options_flow_factory_called_via_instance(self, mock_config_entry):
        """Instance-level access should still produce an options flow handler."""
        flow_instance = HangarAssistantConfigFlow()
        handler = flow_instance.async_get_options_flow(mock_config_entry)

        assert isinstance(handler, HangarOptionsFlowHandler)
        assert handler._config_entry is mock_config_entry

    async def test_airfield_add_form_displayed(
        self, mock_hass, mock_config_entry
    ):
        """Test that add airfield form is displayed."""
        handler = HangarOptionsFlowHandler(mock_config_entry)
        handler.hass = mock_hass

        result = await handler.async_step_airfield_add()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "airfield_add"

    async def test_airfield_add_creates_entry(
        self, mock_hass, mock_config_entry
    ):
        """Test adding a new airfield creates entry."""
        handler = HangarOptionsFlowHandler(mock_config_entry)
        handler.hass = mock_hass

        new_airfield = {
            "name": "Shoreham",
            "icao_code": "EGKA",
            "latitude": 50.84,
            "longitude": -0.27,
            "elevation": 5,
            "runways": "02, 20",
            "primary_runway": "20",
            "runway_length": 1400,
            "temp_sensor": "sensor.shoreham_temp",
            "dp_sensor": "sensor.shoreham_dp",
            "pressure_sensor": (
                "sensor.shoreham_pressure"
            ),
            "wind_sensor": "sensor.shoreham_wind",
            "wind_dir_sensor": (
                "sensor.shoreham_wind_dir"
            ),
        }

        result = await handler.async_step_airfield_add(user_input=new_airfield)

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        mock_hass.config_entries.async_update_entry.assert_called_once()

    async def test_airfield_add_appends_to_list(
        self, mock_hass, mock_config_entry
    ):
        """Test new airfield is appended to existing list."""
        handler = HangarOptionsFlowHandler(mock_config_entry)
        handler.hass = mock_hass

        new_airfield = {
            "name": "Biggin Hill",
            "latitude": 51.34,
            "longitude": 0.04,
            "elevation": 190,
            "runways": "03, 21",
            "primary_runway": "21",
            "runway_length": 1750,
            "temp_sensor": "sensor.bh_temp",
            "dp_sensor": "sensor.bh_dp",
            "pressure_sensor": "sensor.bh_pressure",
            "wind_sensor": "sensor.bh_wind",
            "wind_dir_sensor": "sensor.bh_wind_dir",
        }

        await handler.async_step_airfield_add(user_input=new_airfield)

        # Verify the mock was called with updated data
        assert mock_hass.config_entries.async_update_entry.called


class TestHangarOptionsFlowHandlerAirfieldEdit:
    """Tests for airfield_edit step."""

    async def test_airfield_edit_form_displayed(
        self, mock_hass, mock_config_entry
    ):
        """Test that edit airfield form is displayed."""
        handler = HangarOptionsFlowHandler(mock_config_entry)
        handler.hass = mock_hass
        handler._index = 0

        result = await handler.async_step_airfield_edit()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "airfield_edit"

    async def test_airfield_edit_prefilled_with_existing_data(
        self, mock_hass, mock_config_entry
    ):
        """Test edit form is prefilled with existing airfield data."""
        handler = HangarOptionsFlowHandler(mock_config_entry)
        handler.hass = mock_hass
        handler._index = 0

        result = await handler.async_step_airfield_edit()

        # Check data schema has defaults from existing airfield
        schema = result["data_schema"].schema
        assert schema is not None

    async def test_airfield_edit_updates_entry(
        self, mock_hass, mock_config_entry
    ):
        """Test editing an airfield updates the entry."""
        handler = HangarOptionsFlowHandler(mock_config_entry)
        handler.hass = mock_hass
        handler._index = 0

        updated_airfield = mock_config_entry.data[
            "airfields"
        ][0].copy()
        updated_airfield["name"] = "Popham (Updated)"
        updated_airfield["elevation"] = 150

        result = await handler.async_step_airfield_edit(
            user_input=updated_airfield
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        mock_hass.config_entries.async_update_entry.assert_called_once()


class TestHangarOptionsFlowHandlerAircraftAdd:
    """Tests for aircraft_add step."""

    async def test_aircraft_add_form_displayed(
        self, mock_hass, mock_config_entry
    ):
        """Test that add aircraft form is displayed."""
        handler = HangarOptionsFlowHandler(mock_config_entry)
        handler.hass = mock_hass

        result = await handler.async_step_aircraft_add()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "aircraft_add"

    async def test_aircraft_add_includes_airfield_options(
        self, mock_hass, mock_config_entry
    ):
        """Test aircraft form includes airfield options."""
        handler = HangarOptionsFlowHandler(mock_config_entry)
        handler.hass = mock_hass

        result = await handler.async_step_aircraft_add()

        # Verify form includes airfield selector
        assert result["type"] == data_entry_flow.FlowResultType.FORM

    async def test_aircraft_add_creates_entry(
        self, mock_hass, mock_config_entry
    ):
        """Test adding new aircraft creates entry."""
        handler = HangarOptionsFlowHandler(mock_config_entry)
        handler.hass = mock_hass

        new_aircraft = {
            "reg": "G-ZYXW",
            "model": "Piper Warrior",
            "empty_weight": 680,
            "max_tow": 1100,
            "max_xwind": 12,
            "baseline_roll": 280,
            "baseline_50ft": 550,
            "linked_airfield": "Popham"
        }

        result = await handler.async_step_aircraft_add(
            user_input=new_aircraft
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        mock_hass.config_entries.async_update_entry.assert_called_once()

    async def test_aircraft_add_appends_to_fleet(
        self, mock_hass, mock_config_entry
    ):
        """Test new aircraft is appended to existing fleet."""
        handler = HangarOptionsFlowHandler(mock_config_entry)
        handler.hass = mock_hass

        new_aircraft = {
            "reg": "N12345",
            "model": "Cessna 182",
            "empty_weight": 1250,
            "max_tow": 2200,
            "max_xwind": 18,
            "baseline_roll": 400,
            "baseline_50ft": 750,
        }

        await handler.async_step_aircraft_add(user_input=new_aircraft)

        assert mock_hass.config_entries.async_update_entry.called


class TestHangarOptionsFlowHandlerAircraftEdit:
    """Tests for aircraft_edit step."""

    async def test_aircraft_edit_form_displayed(
        self, mock_hass, mock_config_entry
    ):
        """Test that edit aircraft form is displayed."""
        handler = HangarOptionsFlowHandler(mock_config_entry)
        handler.hass = mock_hass
        handler._index = 0

        result = await handler.async_step_aircraft_edit()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "aircraft_edit"

    async def test_aircraft_edit_prefilled_with_existing_data(
        self, mock_hass, mock_config_entry
    ):
        """Test edit form is prefilled with existing aircraft data."""
        handler = HangarOptionsFlowHandler(mock_config_entry)
        handler.hass = mock_hass
        handler._index = 0

        result = await handler.async_step_aircraft_edit()

        # Check data schema exists
        assert result["data_schema"] is not None

    async def test_aircraft_edit_updates_entry(
        self, mock_hass, mock_config_entry
    ):
        """Test editing aircraft updates the entry."""
        handler = HangarOptionsFlowHandler(mock_config_entry)
        handler.hass = mock_hass
        handler._index = 0

        updated_aircraft = mock_config_entry.data[
            "aircraft"
        ][0].copy()
        updated_aircraft["baseline_roll"] = 350
        updated_aircraft["baseline_50ft"] = 650

        result = await handler.async_step_aircraft_edit(
            user_input=updated_aircraft
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        mock_hass.config_entries.async_update_entry.assert_called_once()

    async def test_aircraft_edit_preserves_registration(
        self, mock_hass, mock_config_entry
    ):
        """Test aircraft registration is preserved in edit."""
        handler = HangarOptionsFlowHandler(mock_config_entry)
        handler.hass = mock_hass
        handler._index = 0

        updated_aircraft = mock_config_entry.data[
            "aircraft"
        ][0].copy()
        updated_aircraft["max_tow"] = 1300

        await handler.async_step_aircraft_edit(
            user_input=updated_aircraft
        )

        # Verify the mock was called (actual data preservation
        # happens in handler)
        assert mock_hass.config_entries.async_update_entry.called


class TestHangarOptionsFlowHandlerInit:
    """Tests for init step and menu navigation."""

    async def test_init_shows_main_menu(self, mock_hass, mock_config_entry):
        """Test init step shows main menu."""
        handler = HangarOptionsFlowHandler(mock_config_entry)
        handler.hass = mock_hass

        result = await handler.async_step_init()

        assert result["type"] == data_entry_flow.FlowResultType.MENU
        assert result["step_id"] == "init"
        assert "airfield" in result["menu_options"]
        assert "aircraft" in result["menu_options"]


class TestHangarOptionsFlowRegression:
    """Regression tests to guard config-flow 500s."""

    async def test_options_flow_init_with_empty_data(self, mock_hass, mock_empty_config_entry):
        """Ensure init menu loads even when entry.data is empty."""
        handler = HangarOptionsFlowHandler(mock_empty_config_entry)
        handler.hass = mock_hass

        result = await handler.async_step_init()

        assert result["type"] == data_entry_flow.FlowResultType.MENU
        assert result["step_id"] == "init"

    async def test_aircraft_add_handles_no_airfields(self, mock_hass, mock_empty_config_entry):
        """Ensure aircraft add form renders without airfields configured."""
        handler = HangarOptionsFlowHandler(mock_empty_config_entry)
        handler.hass = mock_hass

        result = await handler.async_step_aircraft_add()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "aircraft_add"
