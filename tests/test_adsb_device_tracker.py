"""Tests for ADS-B Device Tracker Manager.

Tests device tracker entity management, location tracking, and attribute handling.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from custom_components.hangar_assistant.utils.adsb_device_tracker import (
    ADSBDeviceTrackerManager,
    ADSBAircraftLocation,
    GPS_ACCURACY_DUMP1090,
    GPS_ACCURACY_OPENSKY,
    GPS_ACCURACY_OGN,
)
from custom_components.hangar_assistant.utils.adsb_models import AircraftData


@pytest.fixture
def mock_hass():
    """Create mock Home Assistant instance."""
    mock = MagicMock(spec=HomeAssistant)
    mock.async_create_task = AsyncMock()
    return mock


@pytest.fixture
def device_tracker_manager(mock_hass):
    """Create device tracker manager instance."""
    return ADSBDeviceTrackerManager(mock_hass)


@pytest.fixture
def sample_aircraft():
    """Create sample aircraft data for testing."""
    return {
        "g_abcd": AircraftData(
            registration="G-ABCD",
            icao24="407F11",
            flarm_id=None,
            latitude=51.5074,
            longitude=-0.1278,
            altitude_ft=5000,
            ground_speed_kt=120,
            track_deg=45,
            aircraft_type="Cessna 172",
            callsign="GABCD",
            is_flarm=False,
            source="dump1090",
            priority=1,
            last_seen=datetime.now(timezone.utc),
        ),
        "n987fx": AircraftData(
            registration="N987FX",
            icao24="A0A0A0",
            flarm_id=None,
            latitude=51.4700,
            longitude=-0.4000,
            altitude_ft=3500,
            ground_speed_kt=90,
            track_deg=180,
            aircraft_type="Piper PA-28",
            callsign=None,
            is_flarm=False,
            source="opensky",
            priority=2,
            last_seen=datetime.now(timezone.utc),
        ),
        "flarm_dd1234": AircraftData(
            registration=None,
            icao24="4CA1E4",
            flarm_id="DD1234",
            latitude=51.6000,
            longitude=-0.5000,
            altitude_ft=2000,
            ground_speed_kt=60,
            track_deg=270,
            aircraft_type="Glider",
            callsign=None,
            is_flarm=True,
            source="ogn",
            priority=3,
            last_seen=datetime.now(timezone.utc),
        ),
        "no_location": AircraftData(
            registration="D-EFGH",
            icao24="802123",
            flarm_id=None,
            latitude=None,
            longitude=None,
            altitude_ft=None,
            ground_speed_kt=None,
            track_deg=None,
            aircraft_type="Unknown",
            callsign=None,
            is_flarm=False,
            source="fr24",
            priority=5,
            last_seen=datetime.now(timezone.utc),
        ),
    }


class TestADSBDeviceTrackerInitialisation:
    """Test device tracker manager initialization."""

    def test_manager_creation(self, mock_hass):
        """Test manager initializes correctly."""
        manager = ADSBDeviceTrackerManager(mock_hass)

        assert manager.hass is mock_hass
        assert manager._tracked_aircraft == {}
        assert manager._entity_registry == {}
        assert manager._ident_map == {}
        assert manager._update_callbacks == []

    def test_register_callback(self, device_tracker_manager):
        """Test callback registration."""
        mock_callback = MagicMock()

        device_tracker_manager.register_update_callback(mock_callback)

        assert mock_callback in device_tracker_manager._update_callbacks

    def test_duplicate_callback_not_registered(self, device_tracker_manager):
        """Test duplicate callbacks not registered twice."""
        mock_callback = MagicMock()

        device_tracker_manager.register_update_callback(mock_callback)
        device_tracker_manager.register_update_callback(mock_callback)

        assert device_tracker_manager._update_callbacks.count(mock_callback) == 1


class TestADSBDeviceInfo:
    """Test device info generation."""

    def test_device_info_with_registration(self, device_tracker_manager, sample_aircraft):
        """Test device info uses registration as identifier."""
        aircraft = sample_aircraft["g_abcd"]

        info = device_tracker_manager.get_device_info(aircraft)

        # Identifier should contain registration (as lower case, may use - or _)
        assert ("hangar_assistant", "g-abcd") in info["identifiers"] or ("hangar_assistant", "g_abcd") in info["identifiers"]
        assert "G-ABCD" in info["name"]
        assert info["model"] == "Cessna 172"
        assert info["hw_version"] == "407F11"
        assert info["manufacturer"] == "ADS-B Network"

    def test_device_info_with_callsign(self, device_tracker_manager, sample_aircraft):
        """Test device info includes callsign."""
        aircraft = sample_aircraft["g_abcd"]

        info = device_tracker_manager.get_device_info(aircraft)

        assert "GABCD" in info["name"]

    def test_device_info_icao24_fallback(self, device_tracker_manager, sample_aircraft):
        """Test device info falls back to ICAO24."""
        aircraft = sample_aircraft["flarm_dd1234"]

        info = device_tracker_manager.get_device_info(aircraft)

        # Check that identifiers contain the ICAO24 code
        identifiers = list(info["identifiers"])
        assert any("4ca1e4" in str(ident).lower() for ident in identifiers)

    def test_device_info_flarm_fallback(self, device_tracker_manager):
        """Test device info falls back to FLARM ID."""
        aircraft = AircraftData(
            registration=None,
            icao24=None,
            flarm_id="ABC123",
            latitude=51.0,
            longitude=-0.1,
            altitude_ft=1000,
            ground_speed_kt=0,
            track_deg=0,
            aircraft_type=None,
            callsign=None,
            is_flarm=True,
            source="ogn",
            priority=3,
            last_seen=datetime.now(timezone.utc),
        )

        info = device_tracker_manager.get_device_info(aircraft)

        # Check that identifiers contain the FLARM ID
        identifiers = list(info["identifiers"])
        assert any("abc123" in str(ident).lower() for ident in identifiers)


class TestADSBLocationConversion:
    """Test aircraft to location conversion."""

    def test_aircraft_to_location_complete_data(self, device_tracker_manager, sample_aircraft):
        """Test conversion with complete aircraft data."""
        aircraft = sample_aircraft["g_abcd"]

        location = device_tracker_manager._aircraft_to_location(aircraft)

        assert location is not None
        assert location.latitude == 51.5074
        assert location.longitude == -0.1278
        assert location.altitude == 5000
        assert location.track == 45
        assert location.ground_speed == 120
        assert location.callsign == "GABCD"
        assert location.source == "dump1090"

    def test_aircraft_to_location_no_position(self, device_tracker_manager, sample_aircraft):
        """Test conversion returns None without position."""
        aircraft = sample_aircraft["no_location"]

        location = device_tracker_manager._aircraft_to_location(aircraft)

        assert location is None

    def test_gps_accuracy_by_source_dump1090(self, device_tracker_manager, sample_aircraft):
        """Test GPS accuracy for dump1090 source."""
        aircraft = sample_aircraft["g_abcd"]
        assert aircraft.source == "dump1090"

        accuracy = device_tracker_manager._get_gps_accuracy(aircraft)

        assert accuracy == GPS_ACCURACY_DUMP1090

    def test_gps_accuracy_by_source_opensky(self, device_tracker_manager, sample_aircraft):
        """Test GPS accuracy for OpenSky source."""
        aircraft = sample_aircraft["n987fx"]
        assert aircraft.source == "opensky"

        accuracy = device_tracker_manager._get_gps_accuracy(aircraft)

        assert accuracy == GPS_ACCURACY_OPENSKY

    def test_gps_accuracy_by_source_ogn(self, device_tracker_manager, sample_aircraft):
        """Test GPS accuracy for OGN source."""
        aircraft = sample_aircraft["flarm_dd1234"]
        assert aircraft.source == "ogn"

        accuracy = device_tracker_manager._get_gps_accuracy(aircraft)

        assert accuracy == GPS_ACCURACY_OGN

    def test_gps_accuracy_default_unknown_source(self, device_tracker_manager):
        """Test GPS accuracy defaults for unknown source."""
        aircraft = AircraftData(
            registration="TEST",
            icao24="ABCDEF",
            flarm_id=None,
            latitude=51.0,
            longitude=-0.1,
            altitude_ft=1000,
            ground_speed_kt=0,
            track_deg=0,
            aircraft_type=None,
            callsign=None,
            is_flarm=False,
            source="unknown_source",
            priority=10,
            last_seen=datetime.now(timezone.utc),
        )

        accuracy = device_tracker_manager._get_gps_accuracy(aircraft)

        assert accuracy == 100


class TestEntityIDGeneration:
    """Test entity ID generation."""

    def test_entity_id_from_registration(self, device_tracker_manager, sample_aircraft):
        """Test entity ID generated from registration."""
        aircraft = sample_aircraft["g_abcd"]

        entity_id = device_tracker_manager._generate_entity_id(aircraft)

        assert entity_id == "device_tracker.aircraft_g_abcd"

    def test_entity_id_from_icao24(self, device_tracker_manager):
        """Test entity ID generated from ICAO24."""
        aircraft = AircraftData(
            registration=None,
            icao24="407F11",
            flarm_id=None,
            latitude=51.0,
            longitude=-0.1,
            altitude_ft=1000,
            ground_speed_kt=0,
            track_deg=0,
            aircraft_type=None,
            callsign=None,
            is_flarm=False,
            source="dump1090",
            priority=1,
            last_seen=datetime.now(timezone.utc),
        )

        entity_id = device_tracker_manager._generate_entity_id(aircraft)

        assert entity_id == "device_tracker.aircraft_407f11"

    def test_entity_id_sanitisation(self, device_tracker_manager):
        """Test entity ID sanitisation of special characters."""
        aircraft = AircraftData(
            registration="G-ABC/D",
            icao24=None,
            flarm_id=None,
            latitude=51.0,
            longitude=-0.1,
            altitude_ft=1000,
            ground_speed_kt=0,
            track_deg=0,
            aircraft_type=None,
            callsign=None,
            is_flarm=False,
            source="dump1090",
            priority=1,
            last_seen=datetime.now(timezone.utc),
        )

        entity_id = device_tracker_manager._generate_entity_id(aircraft)

        # Special chars should be replaced
        assert "/" not in entity_id
        assert "-" in entity_id or "_" in entity_id


class TestAircraftUpdate:
    """Test aircraft tracking updates."""

    @pytest.mark.asyncio
    async def test_update_aircraft_new_tracked(self, device_tracker_manager, sample_aircraft):
        """Test updating with new aircraft."""
        aircraft_list = [sample_aircraft["g_abcd"], sample_aircraft["n987fx"]]

        await device_tracker_manager.update_aircraft(aircraft_list)

        # Entity registry should be populated
        assert len(device_tracker_manager._entity_registry) == 2
        assert "407F11" in device_tracker_manager._entity_registry
        assert "A0A0A0" in device_tracker_manager._entity_registry

    @pytest.mark.asyncio
    async def test_update_aircraft_skips_no_location(self, device_tracker_manager, sample_aircraft):
        """Test update skips aircraft without location."""
        aircraft_list = [sample_aircraft["g_abcd"], sample_aircraft["no_location"]]

        await device_tracker_manager.update_aircraft(aircraft_list)

        # Should only register aircraft with location
        assert len(device_tracker_manager._entity_registry) == 1
        assert "407F11" in device_tracker_manager._entity_registry
        assert "802123" not in device_tracker_manager._entity_registry

    @pytest.mark.asyncio
    async def test_update_aircraft_skips_no_icao24(self, device_tracker_manager):
        """Test update skips aircraft without ICAO24."""
        aircraft = AircraftData(
            registration="TEST",
            icao24=None,
            flarm_id=None,
            latitude=51.0,
            longitude=-0.1,
            altitude_ft=1000,
            ground_speed_kt=0,
            track_deg=0,
            aircraft_type=None,
            callsign=None,
            is_flarm=False,
            source="dump1090",
            priority=1,
            last_seen=datetime.now(timezone.utc),
        )

        await device_tracker_manager.update_aircraft([aircraft])

        assert len(device_tracker_manager._entity_registry) == 0

    @pytest.mark.asyncio
    async def test_update_aircraft_calls_callbacks(self, device_tracker_manager, sample_aircraft):
        """Test update calls registered callbacks."""
        mock_callback = AsyncMock()
        device_tracker_manager.register_update_callback(mock_callback)

        aircraft_list = [sample_aircraft["g_abcd"]]
        await device_tracker_manager.update_aircraft(aircraft_list)

        # Callback should be called with location updates
        mock_callback.assert_called_once()


class TestTrackerStatistics:
    """Test tracking statistics."""

    def test_get_tracked_aircraft(self, device_tracker_manager):
        """Test getting tracked aircraft mapping."""
        # Manually populate for testing
        device_tracker_manager._entity_registry = {
            "407F11": "device_tracker.aircraft_g_abcd",
            "A0A0A0": "device_tracker.aircraft_n987fx",
        }

        result = device_tracker_manager.get_tracked_aircraft()

        assert len(result) == 2
        assert result["407F11"] == "device_tracker.aircraft_g_abcd"

    def test_get_aircraft_count(self, device_tracker_manager):
        """Test getting aircraft count."""
        device_tracker_manager._entity_registry = {
            "407F11": "device_tracker.aircraft_g_abcd",
            "A0A0A0": "device_tracker.aircraft_n987fx",
            "4CA1E4": "device_tracker.aircraft_dd1234",
        }

        count = device_tracker_manager.get_aircraft_count()

        assert count == 3

    def test_get_manager_stats(self, device_tracker_manager):
        """Test getting manager statistics."""
        device_tracker_manager._entity_registry = {
            "407F11": "device_tracker.aircraft_g_abcd",
            "A0A0A0": "device_tracker.aircraft_n987fx",
        }
        mock_callback = MagicMock()
        device_tracker_manager.register_update_callback(mock_callback)

        stats = device_tracker_manager.get_manager_stats()

        assert stats["tracked_aircraft_count"] == 2
        assert stats["registered_entities"] == 2
        assert stats["callbacks_registered"] == 1

    def test_clear_stale_tracking(self, device_tracker_manager):
        """Test clearing stale aircraft tracking."""
        device_tracker_manager._entity_registry = {
            "407F11": "device_tracker.aircraft_g_abcd",
            "A0A0A0": "device_tracker.aircraft_n987fx",
            "4CA1E4": "device_tracker.aircraft_dd1234",
        }

        # Simulate only seeing 2 aircraft currently
        current = {"407F11", "A0A0A0"}
        device_tracker_manager.clear_stale_tracking(current)

        # Method should log but not remove (configurable via max_age_minutes)
        assert device_tracker_manager.get_aircraft_count() == 3


class TestLocationData:
    """Test ADSBAircraftLocation dataclass."""

    def test_location_creation(self):
        """Test location data creation."""
        location = ADSBAircraftLocation(
            latitude=51.5,
            longitude=-0.1,
            altitude=5000,
            accuracy=50,
            track=45,
            ground_speed=120,
            callsign="TEST",
            source="dump1090",
        )

        assert location.latitude == 51.5
        assert location.longitude == -0.1
        assert location.altitude == 5000
        assert location.accuracy == 50
        assert location.track == 45
        assert location.ground_speed == 120
        assert location.callsign == "TEST"
        assert location.source == "dump1090"

    def test_location_defaults(self):
        """Test location defaults."""
        location = ADSBAircraftLocation(
            latitude=51.5,
            longitude=-0.1,
        )

        assert location.altitude is None
        assert location.accuracy == 100
        assert location.gps_accuracy == 100
        assert location.track is None
        assert location.ground_speed is None
        assert location.vertical_speed is None
        assert location.callsign is None
        assert location.source is None
