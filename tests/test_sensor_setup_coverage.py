"""Tests for sensor setup and base functionality."""
import pytest
from unittest.mock import MagicMock
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from custom_components.hangar_assistant.sensor import (
    async_setup_entry,
    HangarSensorBase,
    DensityAltSensor,
    CloudBaseSensor,
    PerformanceMarginSensor,
)


@pytest.fixture
def mock_hass():
    """Create mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        "airfields": [
            {
                "name": "Test Airfield",
                "latitude": 51.5,
                "longitude": -0.1,
                "elevation": 100,
                "runways": "09, 27",
                "primary_runway": "09",
                "runway_length": 1000,
                "temp_sensor": "sensor.temp",
                "dp_sensor": "sensor.dp",
                "pressure_sensor": "sensor.pressure",
                "wind_sensor": "sensor.wind",
                "wind_dir_sensor": "sensor.wind_dir"
            }
        ],
        "aircraft": [
            {
                "reg": "G-TEST",
                "model": "Cessna 172",
                "baseline_roll": 300,
                "linked_airfield": "Test Airfield"
            }
        ],
        "pilots": [],
        "settings": {}
    }
    return entry


@pytest.mark.asyncio
async def test_async_setup_entry_creates_airfield_sensors(
    mock_hass, mock_config_entry
):
    """Test that async_setup_entry creates sensors for airfields."""
    async_add_entities = MagicMock()

    await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

    # Verify entities were added
    async_add_entities.assert_called_once()
    entities = async_add_entities.call_args[0][0]

    # Should have multiple airfield sensors
    assert len(entities) > 0
    # Check for specific sensor types
    sensor_types = [type(e).__name__ for e in entities]
    assert "DensityAltSensor" in sensor_types


@pytest.mark.asyncio
async def test_async_setup_entry_creates_aircraft_sensors(
    mock_hass, mock_config_entry
):
    """Test that async_setup_entry creates sensors for aircraft."""
    async_add_entities = MagicMock()

    await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

    entities = async_add_entities.call_args[0][0]
    sensor_types = [type(e).__name__ for e in entities]

    # Check for aircraft sensor
    assert "GroundRollSensor" in sensor_types
    assert "PerformanceMarginSensor" in sensor_types


@pytest.mark.asyncio
async def test_async_setup_entry_with_empty_config(mock_hass):
    """Test setup with empty configuration."""
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        "airfields": [],
        "aircraft": [],
        "pilots": []
    }

    async_add_entities = MagicMock()

    await async_setup_entry(mock_hass, entry, async_add_entities)

    # Should still be called even with empty lists
    async_add_entities.assert_called_once()


@pytest.mark.asyncio
async def test_async_setup_entry_multiple_airfields(mock_hass):
    """Test setup with multiple airfields."""
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        "airfields": [
            {
                "name": "Airfield 1",
                "temp_sensor": "sensor.t1",
                "dp_sensor": "sensor.dp1",
                "pressure_sensor": "sensor.p1",
                "wind_sensor": "sensor.w1",
                "wind_dir_sensor": "sensor.wd1"
            },
            {
                "name": "Airfield 2",
                "temp_sensor": "sensor.t2",
                "dp_sensor": "sensor.dp2",
                "pressure_sensor": "sensor.p2",
                "wind_sensor": "sensor.w2",
                "wind_dir_sensor": "sensor.wd2"
            }
        ],
        "aircraft": [],
        "pilots": [],
        "settings": {}
    }

    async_add_entities = MagicMock()

    await async_setup_entry(mock_hass, entry, async_add_entities)

    entities = async_add_entities.call_args[0][0]

    # Each airfield gets multiple sensors
    assert len(entities) >= 14  # Minimum sensors per airfield


class TestHangarSensorBase:
    """Tests for HangarSensorBase helper methods."""

    def test_get_sensor_value_valid_float(self, mock_hass):
        """Test retrieving valid float sensor value."""
        config = {"name": "Test"}
        sensor = HangarSensorBase(mock_hass, config)

        mock_hass.states.get.return_value = MagicMock(state="20.5")
        result = sensor._get_sensor_value("sensor.test")

        assert result == 20.5

    def test_get_sensor_value_integer_converted_to_float(self, mock_hass):
        """Test integer state is converted to float."""
        config = {"name": "Test"}
        sensor = HangarSensorBase(mock_hass, config)

        mock_hass.states.get.return_value = MagicMock(state="100")
        result = sensor._get_sensor_value("sensor.test")

        assert result == 100.0
        assert isinstance(result, float)

    def test_get_sensor_value_unknown_state(self, mock_hass):
        """Test returns None for 'unknown' state."""
        config = {"name": "Test"}
        sensor = HangarSensorBase(mock_hass, config)

        mock_hass.states.get.return_value = MagicMock(state="unknown")
        result = sensor._get_sensor_value("sensor.test")

        assert result is None

    def test_get_sensor_value_unavailable_state(self, mock_hass):
        """Test returns None for 'unavailable' state."""
        config = {"name": "Test"}
        sensor = HangarSensorBase(mock_hass, config)

        mock_hass.states.get.return_value = MagicMock(state="unavailable")
        result = sensor._get_sensor_value("sensor.test")

        assert result is None

    def test_get_sensor_value_nonexistent_entity(self, mock_hass):
        """Test returns None when entity doesn't exist."""
        config = {"name": "Test"}
        sensor = HangarSensorBase(mock_hass, config)

        mock_hass.states.get.return_value = None
        result = sensor._get_sensor_value("sensor.nonexistent")

        assert result is None

    def test_get_sensor_value_invalid_format(self, mock_hass):
        """Test returns None for non-numeric state."""
        config = {"name": "Test"}
        sensor = HangarSensorBase(mock_hass, config)

        mock_hass.states.get.return_value = MagicMock(state="not_a_number")
        result = sensor._get_sensor_value("sensor.test")

        assert result is None

    def test_unique_id_from_name(self, mock_hass):
        """Test unique_id is generated from name."""
        config = {"name": "Test Airfield"}
        sensor = HangarSensorBase(mock_hass, config)

        assert "test_airfield" in sensor._attr_unique_id

    def test_unique_id_from_reg_if_no_name(self, mock_hass):
        """Test unique_id uses registration if name not provided."""
        config = {"reg": "G-ABCD"}
        sensor = HangarSensorBase(mock_hass, config)

        # Registration is lowercased, hyphens preserved (only spaces replaced)
        assert "g-abcd" in sensor._attr_unique_id.lower()

    def test_unique_id_includes_class_name(self, mock_hass):
        """Test unique_id includes class name."""
        config = {"name": "Test"}
        sensor = DensityAltSensor(mock_hass, config, {})

        assert "densityaltsensor" in sensor._attr_unique_id.lower()

    def test_device_info_created(self, mock_hass):
        """Test device info is created for grouping."""
        config = {"name": "My Airfield"}
        sensor = HangarSensorBase(mock_hass, config)

        assert sensor._attr_device_info is not None
        assert sensor._attr_device_info["identifiers"] is not None

    def test_device_info_includes_name(self, mock_hass):
        """Test device info includes configuration name."""
        config = {"name": "My Airfield"}
        sensor = HangarSensorBase(mock_hass, config)

        assert sensor._attr_device_info["name"] == "My Airfield"

    def test_extra_state_attributes_includes_airfield_data(self, mock_hass):
        """Test extra attributes include airfield configuration."""
        config = {
            "name": "Test Airfield",
            "latitude": 51.5,
            "longitude": -0.1,
            "elevation": 100,
            "runways": "09, 27"
        }
        sensor = HangarSensorBase(mock_hass, config)
        attrs = sensor.extra_state_attributes

        # Check attributes that are always included
        assert "latitude" in attrs
        assert attrs.get("latitude") == 51.5
        assert attrs.get("longitude") == -0.1

    def test_extra_state_attributes_includes_aircraft_data(self, mock_hass):
        """Test extra attributes include aircraft configuration."""
        config = {
            "reg": "G-ABCD",
            "model": "Cessna 172",
            "max_tow": 1200
        }
        sensor = HangarSensorBase(mock_hass, config)
        attrs = sensor.extra_state_attributes

        assert attrs["registration"] == "G-ABCD"
        assert attrs["model"] == "Cessna 172"
        assert attrs["mtow_kg"] == 1200

    def test_source_entities_tracked(self, mock_hass):
        """Test source entities are tracked for updates."""
        config = {
            "name": "Test",
            "temp_sensor": "sensor.temp",
            "dp_sensor": "sensor.dp"
        }
        sensor = CloudBaseSensor(mock_hass, config)

        assert "sensor.temp" in sensor._source_entities
        assert "sensor.dp" in sensor._source_entities

    def test_slugification_removes_spaces(self, mock_hass):
        """Test slugification replaces spaces with underscores."""
        config = {"name": "My Test Airfield"}
        sensor = HangarSensorBase(mock_hass, config)

        assert "my_test_airfield" in sensor._id_slug

    def test_slugification_lowercases_names(self, mock_hass):
        """Test slugification converts to lowercase."""
        config = {"name": "UPPER CASE"}
        sensor = HangarSensorBase(mock_hass, config)

        assert sensor._id_slug == "upper_case"
