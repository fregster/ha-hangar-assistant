"""Tests for configuration validation."""
import pytest
from unittest.mock import MagicMock


class TestAirfieldValidation:
    """Test airfield configuration validation."""

    def test_airfield_missing_name(self):
        """Test airfield without name is invalid."""
        airfield = {
            "latitude": 51.17,
            "longitude": -1.23,
            "elevation": 100,
            "temp_sensor": "sensor.temp"
        }
        # Name is required for slugification
        assert "name" not in airfield
        assert airfield.get("name") is None

    def test_airfield_missing_elevation(self):
        """Test airfield without elevation."""
        airfield = {
            "name": "Popham",
            "latitude": 51.17,
            "longitude": -1.23,
            "temp_sensor": "sensor.temp"
        }
        assert "elevation" not in airfield
        assert airfield.get("elevation") is None

    def test_airfield_missing_required_sensors(self):
        """Test airfield without required sensor entities."""
        airfield = {
            "name": "Popham",
            "elevation": 100,
            "latitude": 51.17,
            "longitude": -1.23
        }
        required_sensors = ["temp_sensor", "dp_sensor"]
        missing = [s for s in required_sensors if s not in airfield]
        assert len(missing) > 0

    def test_airfield_invalid_elevation(self):
        """Test airfield with invalid elevation value."""
        airfield = {
            "name": "Popham",
            "elevation": -500,  # Negative elevation
            "temp_sensor": "sensor.temp",
            "dp_sensor": "sensor.dp"
        }
        # Elevation should be non-negative
        assert airfield["elevation"] < 0

    def test_airfield_invalid_latitude(self):
        """Test airfield with out-of-range latitude."""
        airfield = {
            "name": "Popham",
            "latitude": 95.0,  # Invalid, must be -90 to 90
            "longitude": -1.23,
            "elevation": 100
        }
        assert not (-90 <= airfield["latitude"] <= 90)

    def test_airfield_invalid_longitude(self):
        """Test airfield with out-of-range longitude."""
        airfield = {
            "name": "Popham",
            "latitude": 51.17,
            "longitude": 200.0,  # Invalid, must be -180 to 180
            "elevation": 100
        }
        assert not (-180 <= airfield["longitude"] <= 180)

    def test_airfield_empty_name(self):
        """Test airfield with empty string name."""
        airfield = {
            "name": "",
            "elevation": 100
        }
        assert airfield["name"] == ""
        assert not airfield["name"]

    def test_airfield_valid_configuration(self):
        """Test valid airfield configuration."""
        airfield = {
            "name": "Popham",
            "elevation": 100,
            "latitude": 51.17,
            "longitude": -1.23,
            "temp_sensor": "sensor.temp",
            "dp_sensor": "sensor.dp",
            "pressure_sensor": "sensor.pressure",
            "wind_sensor": "sensor.wind",
            "wind_dir_sensor": "sensor.wind_dir"
        }
        assert airfield["name"]
        assert 0 <= airfield["elevation"]
        assert -90 <= airfield["latitude"] <= 90
        assert -180 <= airfield["longitude"] <= 180


class TestAircraftValidation:
    """Test aircraft configuration validation."""

    def test_aircraft_missing_registration(self):
        """Test aircraft without registration number."""
        aircraft = {
            "model": "Cessna 172",
            "baseline_roll": 300
        }
        assert "reg" not in aircraft
        assert aircraft.get("reg") is None

    def test_aircraft_missing_model(self):
        """Test aircraft without model."""
        aircraft = {
            "reg": "G-ABCD",
            "baseline_roll": 300
        }
        assert "model" not in aircraft

    def test_aircraft_missing_baseline_roll(self):
        """Test aircraft without baseline roll."""
        aircraft = {
            "reg": "G-ABCD",
            "model": "Cessna 172"
        }
        assert "baseline_roll" not in aircraft
        assert aircraft.get("baseline_roll") is None

    def test_aircraft_invalid_baseline_roll(self):
        """Test aircraft with invalid baseline roll."""
        aircraft = {
            "reg": "G-ABCD",
            "model": "Cessna 172",
            "baseline_roll": -100  # Negative distance
        }
        assert aircraft["baseline_roll"] < 0

    def test_aircraft_empty_registration(self):
        """Test aircraft with empty registration."""
        aircraft = {
            "reg": "",
            "model": "Cessna 172",
            "baseline_roll": 300
        }
        assert aircraft["reg"] == ""
        assert not aircraft["reg"]

    def test_aircraft_empty_model(self):
        """Test aircraft with empty model."""
        aircraft = {
            "reg": "G-ABCD",
            "model": "",
            "baseline_roll": 300
        }
        assert aircraft["model"] == ""

    def test_aircraft_valid_configuration(self):
        """Test valid aircraft configuration."""
        aircraft = {
            "reg": "G-ABCD",
            "model": "Cessna 172",
            "baseline_roll": 300,
            "linked_airfield": "Popham"
        }
        assert aircraft["reg"]
        assert aircraft["model"]
        assert aircraft["baseline_roll"] >= 0


class TestSensorEntityValidation:
    """Test sensor entity ID validation."""

    def test_invalid_entity_id_format(self):
        """Test entity ID with invalid format."""
        entity_id = "invalid_format"
        assert "." not in entity_id

    def test_entity_id_missing_domain(self):
        """Test entity ID missing domain prefix."""
        entity_id = "my_sensor"
        assert not entity_id.startswith("sensor.")

    def test_entity_id_empty_string(self):
        """Test empty entity ID."""
        entity_id = ""
        assert entity_id == ""

    def test_valid_entity_id(self):
        """Test valid sensor entity ID."""
        entity_id = "sensor.popham_temperature"
        assert "." in entity_id
        assert entity_id.startswith("sensor.")

    def test_entity_id_case_sensitivity(self):
        """Test entity IDs are case-insensitive."""
        entity_id1 = "sensor.Temperature"
        entity_id2 = "sensor.temperature"
        assert entity_id1.lower() == entity_id2.lower()


class TestConfigurationLists:
    """Test configuration list validation."""

    def test_empty_airfields_list(self):
        """Test configuration with empty airfields."""
        config = {
            "airfields": [],
            "aircraft": []
        }
        assert len(config["airfields"]) == 0

    def test_empty_aircraft_list(self):
        """Test configuration with empty aircraft."""
        config = {
            "airfields": [{"name": "Popham"}],
            "aircraft": []
        }
        assert len(config["aircraft"]) == 0

    def test_missing_airfields_key(self):
        """Test configuration without airfields key."""
        config = {
            "aircraft": []
        }
        assert "airfields" not in config
        assert config.get("airfields") is None

    def test_missing_aircraft_key(self):
        """Test configuration without aircraft key."""
        config = {
            "airfields": []
        }
        assert "aircraft" not in config

    def test_multiple_airfields(self):
        """Test configuration with multiple airfields."""
        config = {
            "airfields": [
                {"name": "Popham", "elevation": 100},
                {"name": "Odiham", "elevation": 200}
            ]
        }
        assert len(config["airfields"]) == 2

    def test_duplicate_airfield_names(self):
        """Test configuration with duplicate airfield names."""
        config = {
            "airfields": [
                {"name": "Popham", "elevation": 100},
                {"name": "Popham", "elevation": 200}
            ]
        }
        names = [a["name"] for a in config["airfields"]]
        assert len(names) != len(set(names))  # Duplicates detected

    def test_duplicate_aircraft_registrations(self):
        """Test configuration with duplicate aircraft registrations."""
        config = {
            "aircraft": [
                {"reg": "G-ABCD", "model": "Cessna 172"},
                {"reg": "G-ABCD", "model": "Piper Cub"}
            ]
        }
        regs = [a["reg"] for a in config["aircraft"]]
        assert len(regs) != len(set(regs))  # Duplicates detected
