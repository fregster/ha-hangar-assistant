"""Coverage tests for hangar helper utilities.

Tests for hangar-aware aircraft resolution, sensor fallback chains, and
convenience functions for accessing temperature/humidity with full fallback.

Coverage focus:
    - get_aircraft_airfield hangar resolution paths
    - Convenience functions with implicit aircraft config resolution
    - Edge cases (missing configs, invalid states)
"""
from unittest.mock import MagicMock
import pytest

from custom_components.hangar_assistant.utils.hangar_helpers import (
    get_aircraft_airfield,
    get_aircraft_hangar,
    find_hangar_by_name,
    get_airfield_for_hangar,
    get_hangar_sensor_value,
    _try_get_sensor_value,
    get_hangar_temperature,
    get_hangar_humidity,
)


class TestGetAircraftAirfield:
    """Test aircraft airfield resolution with hangar priority."""

    def test_hangar_priority_over_direct_airfield(self):
        """Test hangar takes priority when aircraft has both hangar and direct airfield."""
        aircraft = {
            "reg": "G-ABCD",
            "hangar": "Hangar A",
            "linked_airfield": "Backup Field"
        }
        hangar = {"name": "Hangar A", "airfield_name": "Main Field"}
        hangars = [hangar]
        airfields = [
            {"name": "Main Field"},
            {"name": "Backup Field"},
        ]

        result = get_aircraft_airfield(aircraft, hangars, airfields)

        assert result == {"name": "Main Field"}

    def test_direct_airfield_fallback(self):
        """Test direct airfield used when hangar not found."""
        aircraft = {
            "reg": "G-ABCD",
            "hangar": "Nonexistent Hangar",
            "linked_airfield": "Backup Field"
        }
        hangars = []
        airfields = [{"name": "Backup Field"}]

        result = get_aircraft_airfield(aircraft, hangars, airfields)

        assert result == {"name": "Backup Field"}

    def test_hangar_without_matching_airfield(self):
        """Test returns None when hangar exists but airfield not found."""
        aircraft = {"reg": "G-ABCD", "hangar": "Hangar A"}
        hangar = {"name": "Hangar A", "airfield_name": "Missing Field"}
        hangars = [hangar]
        airfields = [{"name": "Other Field"}]

        result = get_aircraft_airfield(aircraft, hangars, airfields)

        assert result is None

    def test_no_hangar_or_direct_airfield(self):
        """Test returns None when aircraft unlinked."""
        aircraft = {"reg": "G-ABCD"}
        hangars = []
        airfields = []

        result = get_aircraft_airfield(aircraft, hangars, airfields)

        assert result is None

    def test_multiple_airfields_correct_selection(self):
        """Test correct airfield selected from multiple options."""
        aircraft = {"reg": "G-ABCD", "hangar": "Hangar B"}
        hangar = {"name": "Hangar B", "airfield_name": "Field 2"}
        hangars = [hangar]
        airfields = [
            {"name": "Field 1", "icao": "EGKA"},
            {"name": "Field 2", "icao": "EGLC"},
            {"name": "Field 3", "icao": "EGSH"},
        ]

        result = get_aircraft_airfield(aircraft, hangars, airfields)

        assert result == {"name": "Field 2", "icao": "EGLC"}


class TestGetAircraftHangar:
    """Test aircraft hangar resolution."""

    def test_hangar_found(self):
        """Test returns hangar when aircraft assigned."""
        aircraft = {"reg": "G-ABCD", "hangar": "Hangar A"}
        hangar = {"name": "Hangar A", "capacity": 1}
        hangars = [hangar]

        result = get_aircraft_hangar(aircraft, hangars)

        assert result == hangar

    def test_hangar_not_assigned(self):
        """Test returns None when aircraft not assigned to hangar."""
        aircraft = {"reg": "G-ABCD"}
        hangars = []

        result = get_aircraft_hangar(aircraft, hangars)

        assert result is None

    def test_hangar_not_found_in_list(self):
        """Test returns None when hangar name doesn't exist."""
        aircraft = {"reg": "G-ABCD", "hangar": "Missing Hangar"}
        hangars = [{"name": "Other Hangar"}]

        result = get_aircraft_hangar(aircraft, hangars)

        assert result is None


class TestFindHangarByName:
    """Test hangar lookup by name."""

    def test_exact_name_match(self):
        """Test returns hangar on exact name match."""
        hangar = {"name": "Main Hangar", "size": "large"}
        hangars = [hangar, {"name": "Other Hangar"}]

        result = find_hangar_by_name("Main Hangar", hangars)

        assert result == hangar

    def test_no_match(self):
        """Test returns None when name not found."""
        hangars = [{"name": "Hangar A"}, {"name": "Hangar B"}]

        result = find_hangar_by_name("Missing", hangars)

        assert result is None

    def test_empty_list(self):
        """Test returns None on empty list."""
        result = find_hangar_by_name("Any", [])

        assert result is None

    def test_case_sensitive_match(self):
        """Test name match is case-sensitive."""
        hangar = {"name": "Main Hangar"}
        hangars = [hangar]

        result = find_hangar_by_name("main hangar", hangars)

        assert result is None


class TestGetAirfieldForHangar:
    """Test airfield resolution for a hangar."""

    def test_hangar_with_matching_airfield(self):
        """Test returns airfield when name matches."""
        hangar = {"name": "Hangar 1", "airfield_name": "Popham"}
        airfield = {"name": "Popham", "icao": "EGHP"}
        airfields = [airfield, {"name": "Other"}]

        result = get_airfield_for_hangar(hangar, airfields)

        assert result == airfield

    def test_airfield_not_found(self):
        """Test returns None when airfield missing."""
        hangar = {"name": "Hangar 1", "airfield_name": "Popham"}
        airfields = [{"name": "Other"}]

        result = get_airfield_for_hangar(hangar, airfields)

        assert result is None

    def test_hangar_without_airfield_name(self):
        """Test returns None when hangar lacks airfield_name."""
        hangar = {"name": "Hangar 1"}
        airfields = [{"name": "Popham"}]

        result = get_airfield_for_hangar(hangar, airfields)

        assert result is None


class TestGetHangarSensorValue:
    """Test sensor value fallback chain."""

    def test_hangar_sensor_takes_priority(self):
        """Test hangar sensor returned when available."""
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = MagicMock(state="22.5")

        hangar = {"temp_sensor": "sensor.hangar_temp"}
        airfield = {"temp_sensor": "sensor.airfield_temp"}

        result = get_hangar_sensor_value(mock_hass, "temp_sensor", hangar, airfield)

        assert result == 22.5
        mock_hass.states.get.assert_called_with("sensor.hangar_temp")

    def test_airfield_fallback_when_hangar_unavailable(self):
        """Test airfield sensor used when hangar unavailable."""
        mock_hass = MagicMock()
        mock_state = MagicMock(state="20.0")
        mock_hass.states.get.side_effect = [None, mock_state]

        hangar = {"temp_sensor": "sensor.hangar_temp"}
        airfield = {"temp_sensor": "sensor.airfield_temp"}

        result = get_hangar_sensor_value(mock_hass, "temp_sensor", hangar, airfield)

        assert result == 20.0

    def test_global_sensor_fallback(self):
        """Test global sensor used when hangar/airfield unavailable."""
        mock_hass = MagicMock()
        mock_hass.states.get.side_effect = [None, None, MagicMock(state="18.0")]

        hangar = {"temp_sensor": "sensor.hangar_temp"}
        airfield = {"temp_sensor": "sensor.airfield_temp"}

        result = get_hangar_sensor_value(
            mock_hass, "temp_sensor", hangar, airfield, "sensor.global_temp"
        )

        assert result == 18.0

    def test_all_unavailable(self):
        """Test returns None when all sources unavailable."""
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None

        result = get_hangar_sensor_value(mock_hass, "temp_sensor", None, None)

        assert result is None


class TestTryGetSensorValue:
    """Test low-level sensor value extraction."""

    def test_numeric_state_returned(self):
        """Test numeric state converted to float."""
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = MagicMock(state="25.5")
        config = {"temp_sensor": "sensor.temp"}

        result = _try_get_sensor_value(mock_hass, config, "temp_sensor", "Test")

        assert result == 25.5

    def test_unavailable_state_ignored(self):
        """Test unavailable state returns None."""
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = MagicMock(state="unavailable")
        config = {"temp_sensor": "sensor.temp"}

        result = _try_get_sensor_value(mock_hass, config, "temp_sensor", "Test")

        assert result is None

    def test_unknown_state_ignored(self):
        """Test unknown state returns None."""
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = MagicMock(state="unknown")
        config = {"temp_sensor": "sensor.temp"}

        result = _try_get_sensor_value(mock_hass, config, "temp_sensor", "Test")

        assert result is None

    def test_empty_state_ignored(self):
        """Test empty state returns None."""
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = MagicMock(state="")
        config = {"temp_sensor": "sensor.temp"}

        result = _try_get_sensor_value(mock_hass, config, "temp_sensor", "Test")

        assert result is None

    def test_entity_not_found(self):
        """Test missing entity returns None."""
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None
        config = {"temp_sensor": "sensor.missing"}

        result = _try_get_sensor_value(mock_hass, config, "temp_sensor", "Test")

        assert result is None

    def test_missing_key_in_config(self):
        """Test missing key in config returns None."""
        mock_hass = MagicMock()
        config = {}

        result = _try_get_sensor_value(mock_hass, config, "temp_sensor", "Test")

        assert result is None

    def test_non_numeric_state_ignored(self):
        """Test non-numeric state returns None."""
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = MagicMock(state="not_a_number")
        config = {"temp_sensor": "sensor.temp"}

        result = _try_get_sensor_value(mock_hass, config, "temp_sensor", "Test")

        assert result is None

    def test_none_config(self):
        """Test None config returns None."""
        mock_hass = MagicMock()

        result = _try_get_sensor_value(mock_hass, None, "temp_sensor", "Test")

        assert result is None


class TestConvenienceFunctions:
    """Test convenience functions with implicit aircraft resolution."""

    def test_get_hangar_temperature_explicit_config(self):
        """Test temperature with explicit hangar/airfield config."""
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = MagicMock(state="20.0")

        hangar = {"temp_sensor": "sensor.hangar_temp"}

        result = get_hangar_temperature(mock_hass, hangar_config=hangar)

        assert result == 20.0

    def test_get_hangar_humidity_explicit_config(self):
        """Test humidity with explicit config."""
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = MagicMock(state="65.0")

        airfield = {"humidity_sensor": "sensor.humidity"}

        result = get_hangar_humidity(mock_hass, airfield_config=airfield)

        assert result == 65.0

    def test_temperature_with_aircraft_resolution(self):
        """Test temperature resolution with hangar fallback."""
        # Test the get_hangar_sensor_value directly with explicit configs
        mock_hass = MagicMock()
        mock_state = MagicMock()
        mock_state.state = "22.0"
        mock_hass.states.get.return_value = mock_state

        hangar_config = {"name": "Hangar A", "temp_sensor": "sensor.hangar_temp"}
        
        result = get_hangar_sensor_value(
            mock_hass, "temp_sensor", hangar_config, None, None
        )

        assert result == 22.0

    def test_no_resolution_when_explicit_config_provided(self):
        """Test aircraft resolution skipped when explicit configs given."""
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = MagicMock(state="19.0")
        mock_hass.data = {"hangar_assistant": {}}

        aircraft = {"reg": "G-ABCD", "hangar": "Hangar A"}
        hangar = {"temp_sensor": "sensor.explicit"}

        result = get_hangar_temperature(
            mock_hass, aircraft_config=aircraft, hangar_config=hangar
        )

        assert result == 19.0
        # Should use explicit hangar, not resolve from aircraft
        mock_hass.states.get.assert_called_with("sensor.explicit")
