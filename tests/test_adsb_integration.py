"""Integration tests for ADS-B multi-source coordination (simplified, stable).

Covers:
- Multi-source deduplication with priority
- Graceful degradation when sources fail
- ICAO24-based caching
- Basic device tracking creation
- Mixed aircraft scenarios and partial data merging
- Handling many aircraft results
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from custom_components.hangar_assistant.utils.adsb_manager import ADSBManager
from custom_components.hangar_assistant.utils.adsb_models import AircraftData


@pytest.fixture
def manager():
    """Create ADSBManager with mock hass and basic cache settings."""
    hass = MagicMock()
    config = {"max_cache_entries": 100, "cache_ttl_seconds": 30}
    return ADSBManager(hass, config)


def _enable(manager: ADSBManager, source: str) -> None:
    """Helper to mark a registered source as enabled."""
    if source not in manager._source_health:
        manager._source_health[source] = {
            "enabled": True,
            "consecutive_failures": 0,
            "last_success": None,
            "last_error": None,
            "aircraft_count": 0,
        }
    manager._source_health[source]["enabled"] = True


class TestMultiSourceCoordination:
    """Test multi-source deduplication and caching."""

    @pytest.mark.asyncio
    async def test_multi_source_deduplication(self, manager: ADSBManager):
        """Highest-priority source data is selected when multiple sources provide the same aircraft."""
        dump1090_client = AsyncMock()
        dump1090_client.priority = 1
        dump1090_client.get_aircraft_near_location = AsyncMock(
            return_value=[
                AircraftData(
                    registration="G-BBBB",
                    icao24="407F11",
                    latitude=51.5000,
                    longitude=-0.1000,
                    altitude_ft=5000,
                    ground_speed_kt=150,
                    track_deg=90,
                    aircraft_type="C172",
                    callsign="GBBBB",
                    is_flarm=False,
                    source="dump1090",
                    priority=1,
                    last_seen=datetime.now(timezone.utc),
                )
            ]
        )

        opensky_client = AsyncMock()
        opensky_client.priority = 2
        opensky_client.get_aircraft_near_location = AsyncMock(
            return_value=[
                AircraftData(
                    registration="G-BBBB",
                    icao24="407F11",
                    latitude=51.5010,
                    longitude=-0.1005,
                    altitude_ft=5050,
                    ground_speed_kt=149,
                    track_deg=91,
                    aircraft_type="C172",
                    callsign="GBBBB",
                    is_flarm=False,
                    source="opensky",
                    priority=2,
                    last_seen=datetime.now(timezone.utc),
                )
            ]
        )

        manager.register_client("dump1090", dump1090_client)
        manager.register_client("opensky", opensky_client)
        _enable(manager, "dump1090")
        _enable(manager, "opensky")

        result = await manager.get_aircraft_near_location(51.5, -0.1, 50)

        assert len(result) == 1
        assert result[0].icao24 == "407F11"
        assert result[0].latitude == 51.5000  # higher-priority source value

    @pytest.mark.asyncio
    async def test_all_sources_fail_gracefully(self, manager: ADSBManager):
        """When all sources fail, we return an empty list without raising."""
        failing = AsyncMock()
        failing.priority = 1
        failing.get_aircraft_near_location = AsyncMock(side_effect=Exception("fail"))

        manager.register_client("failing", failing)
        _enable(manager, "failing")

        result = await manager.get_aircraft_near_location(51.5, -0.1, 50)

        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_cache_by_icao24(self, manager: ADSBManager):
        """ICAO24 cache prevents redundant source calls."""
        client = AsyncMock()
        client.priority = 1
        aircraft = AircraftData(
            registration="G-TEST",
            icao24="TESTAA",
            latitude=51.5,
            longitude=-0.1,
            altitude_ft=5000,
            ground_speed_kt=100,
            track_deg=0,
            aircraft_type="TEST",
            callsign=None,
            is_flarm=False,
            source="test",
            priority=1,
            last_seen=datetime.now(timezone.utc),
        )

        client.get_aircraft_by_icao24 = AsyncMock(return_value=aircraft)
        manager.register_client("test", client)
        _enable(manager, "test")

        first = await manager.get_aircraft_by_icao24("TESTAA")
        second = await manager.get_aircraft_by_icao24("TESTAA")

        assert first is not None and second is not None
        assert client.get_aircraft_by_icao24.call_count == 1
        assert manager.get_cache_stats()["cache_hits"] >= 1


class TestDeviceTrackerIntegration:
    """Test device tracker-style usage (basic presence)."""

    @pytest.mark.asyncio
    async def test_device_tracker_entity_creation(self, manager: ADSBManager):
        client = AsyncMock()
        client.priority = 1
        aircraft = AircraftData(
            registration="G-TEST",
            icao24="TEST01",
            latitude=51.5,
            longitude=-0.1,
            altitude_ft=5000,
            ground_speed_kt=100,
            track_deg=90,
            aircraft_type="TEST",
            callsign="GTEST",
            is_flarm=False,
            source="test",
            priority=1,
            last_seen=datetime.now(timezone.utc),
        )

        client.get_aircraft_near_location = AsyncMock(return_value=[aircraft])
        manager.register_client("test", client)
        _enable(manager, "test")

        result = await manager.get_aircraft_near_location(51.5, -0.1, 50)

        assert len(result) == 1
        assert result[0].icao24 == "TEST01"


class TestRealWorldScenarios:
    """Test mixed and partial data scenarios."""

    @pytest.mark.asyncio
    async def test_mixed_aircraft_types(self, manager: ADSBManager):
        dump_client = AsyncMock()
        dump_client.priority = 1
        dump_client.get_aircraft_near_location = AsyncMock(
            return_value=[
                AircraftData(
                    registration="N12345",
                    icao24="A0A0A0",
                    latitude=51.5,
                    longitude=-0.1,
                    altitude_ft=30000,
                    ground_speed_kt=450,
                    track_deg=270,
                    aircraft_type="B737",
                    callsign="AAL123",
                    is_flarm=False,
                    source="dump1090",
                    priority=1,
                    last_seen=datetime.now(timezone.utc),
                ),
                AircraftData(
                    registration="G-ABCD",
                    icao24="407F11",
                    latitude=51.4,
                    longitude=-0.2,
                    altitude_ft=5000,
                    ground_speed_kt=120,
                    track_deg=90,
                    aircraft_type="C172",
                    callsign="GABCD",
                    is_flarm=False,
                    source="dump1090",
                    priority=1,
                    last_seen=datetime.now(timezone.utc),
                ),
            ]
        )

        manager.register_client("dump1090", dump_client)
        _enable(manager, "dump1090")

        result = await manager.get_aircraft_near_location(51.5, -0.2, 100)

        assert len(result) == 2
        assert any(a.icao24 == "A0A0A0" for a in result)
        assert any(a.icao24 == "407F11" for a in result)

    @pytest.mark.asyncio
    async def test_partial_data_merging(self, manager: ADSBManager):
        client1 = AsyncMock()
        client1.priority = 1
        client1.get_aircraft_near_location = AsyncMock(
            return_value=[
                AircraftData(
                    registration="G-TEST",
                    icao24="TESTAA",
                    latitude=51.5,
                    longitude=-0.1,
                    altitude_ft=5000,
                    ground_speed_kt=100,
                    track_deg=90,
                    aircraft_type="C172",
                    callsign="GTEST",
                    is_flarm=False,
                    source="client1",
                    priority=1,
                    last_seen=datetime.now(timezone.utc),
                )
            ]
        )

        client2 = AsyncMock()
        client2.priority = 2
        client2.get_aircraft_near_location = AsyncMock(
            return_value=[
                AircraftData(
                    registration="G-TEST",
                    icao24="TESTAA",
                    latitude=51.5,
                    longitude=-0.1,
                    altitude_ft=5000,
                    ground_speed_kt=100,
                    track_deg=90,
                    aircraft_type=None,
                    callsign=None,
                    is_flarm=False,
                    source="client2",
                    priority=2,
                    last_seen=datetime.now(timezone.utc),
                )
            ]
        )

        manager.register_client("client1", client1)
        manager.register_client("client2", client2)
        _enable(manager, "client1")
        _enable(manager, "client2")

        result = await manager.get_aircraft_near_location(51.5, -0.1, 50)

        assert len(result) == 1
        assert result[0].aircraft_type == "C172"
        assert result[0].callsign == "GTEST"


class TestPerformance:
    """Test handling of many aircraft results."""

    @pytest.mark.asyncio
    async def test_many_aircraft_handling(self, manager: ADSBManager):
        client = AsyncMock()
        client.priority = 1
        aircraft_list = [
            AircraftData(
                registration=f"G-A{i:04d}",
                icao24=f"40{i:05x}",
                latitude=51.5 + (i * 0.001),
                longitude=-0.1 + (i * 0.001),
                altitude_ft=5000 + (i * 10),
                ground_speed_kt=100 + (i % 50),
                track_deg=i % 360,
                aircraft_type="C172",
                callsign=None,
                is_flarm=False,
                source="test",
                priority=1,
                last_seen=datetime.now(timezone.utc),
            )
            for i in range(100)
        ]

        client.get_aircraft_near_location = AsyncMock(return_value=aircraft_list)
        manager.register_client("test", client)
        _enable(manager, "test")

        result = await manager.get_aircraft_near_location(51.5, -0.1, 100)

        assert len(result) == 100
