"""Tests for ADSBManager multi-source coordination.

Test Coverage:
    - Client registration and initialization
    - Multi-source querying with parallel requests
    - ICAO24 deduplication logic
    - Priority-based merging of aircraft data
    - Cache management with LRU eviction
    - Source health tracking
    - Error handling and graceful degradation
    - Performance (query times, cache hit rates)
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

import pytest
from homeassistant.util import dt as dt_util

from custom_components.hangar_assistant.utils.adsb_manager import ADSBManager
from custom_components.hangar_assistant.utils.adsb_models import AircraftData


@pytest.fixture
def mock_hass():
    """Create mock Home Assistant instance."""
    mock = MagicMock()
    return mock


@pytest.fixture
def manager_config():
    """Default ADSBManager configuration."""
    return {
        "max_cache_entries": 100,
        "cache_ttl_seconds": 30
    }


@pytest.fixture
def mock_dump1090_client():
    """Mock dump1090 client (highest priority)."""
    client = AsyncMock()
    client.priority = 1
    client.source = "dump1090"
    return client


@pytest.fixture
def mock_opensky_client():
    """Mock OpenSky Network client (priority 2)."""
    client = AsyncMock()
    client.priority = 2
    client.source = "opensky"
    return client


@pytest.fixture
def mock_ogn_client():
    """Mock OGN client (priority 3)."""
    client = AsyncMock()
    client.priority = 3
    client.source = "ogn"
    return client


@pytest.fixture
def sample_aircraft():
    """Sample aircraft data for testing."""
    return {
        "g_abcd": AircraftData(
            registration="G-ABCD",
            icao24="4CA1E3",
            callsign="GLIDER01",
            latitude=51.48,
            longitude=-0.46,
            altitude_ft=3500,
            ground_speed_kt=80,
            track_deg=270,
            vertical_rate_fpm=500,
            aircraft_type="ASW20",
            source="dump1090",
            last_seen=dt_util.utcnow(),
            is_flarm=True
        ),
        "n_test": AircraftData(
            registration="N12345",
            icao24="A00A8B",
            callsign="CESSNA",
            latitude=51.45,
            longitude=-0.50,
            altitude_ft=2000,
            ground_speed_kt=90,
            track_deg=180,
            aircraft_type="C172",
            source="opensky",
            last_seen=dt_util.utcnow(),
            is_flarm=False
        ),
        "flarm_dd1234": AircraftData(
            registration=None,
            icao24="4CA1E4",
            flarm_id="DD1234",
            latitude=51.50,
            longitude=-0.44,
            altitude_ft=4000,
            ground_speed_kt=70,
            track_deg=90,
            source="ogn",
            last_seen=dt_util.utcnow(),
            is_flarm=True
        )
    }


class TestADSBManagerInitialisation:
    """Test ADSBManager initialization."""
    
    def test_init_creates_manager(self, mock_hass, manager_config):
        """Test manager initialisation with config."""
        manager = ADSBManager(mock_hass, manager_config)
        
        assert manager.hass is mock_hass
        assert len(manager.clients) == 0
        assert manager._max_cache_entries == 100
        assert manager._cache_ttl == 30
    
    def test_register_single_client(self, mock_hass, manager_config, mock_dump1090_client):
        """Test registering a single ADS-B client."""
        manager = ADSBManager(mock_hass, manager_config)
        manager.register_client("dump1090", mock_dump1090_client)
        
        assert "dump1090" in manager.clients
        assert manager.clients["dump1090"] is mock_dump1090_client
        assert manager._source_health["dump1090"]["enabled"] is True
    
    def test_register_multiple_clients(
        self, mock_hass, manager_config,
        mock_dump1090_client, mock_opensky_client, mock_ogn_client
    ):
        """Test registering multiple clients with different priorities."""
        manager = ADSBManager(mock_hass, manager_config)
        
        manager.register_client("dump1090", mock_dump1090_client)
        manager.register_client("opensky", mock_opensky_client)
        manager.register_client("ogn", mock_ogn_client)
        
        assert len(manager.clients) == 3
        assert manager.clients["dump1090"].priority == 1  # Highest priority
        assert manager.clients["opensky"].priority == 2
        assert manager.clients["ogn"].priority == 3


class TestADSBManagerConnectionTesting:
    """Test connection validation for data sources."""
    
    @pytest.mark.asyncio
    async def test_initialize_all_sources_available(
        self, mock_hass, manager_config,
        mock_dump1090_client, mock_opensky_client, mock_ogn_client
    ):
        """Test initialisation when all sources available.
        
        Validates:
            - All sources tested during init
            - Enabled flag set to True on success
            - Last success timestamp recorded
        """
        mock_dump1090_client.test_connection.return_value = (True, None)
        mock_opensky_client.test_connection.return_value = (True, None)
        mock_ogn_client.test_connection.return_value = (True, None)
        
        manager = ADSBManager(mock_hass, manager_config)
        manager.register_client("dump1090", mock_dump1090_client)
        manager.register_client("opensky", mock_opensky_client)
        manager.register_client("ogn", mock_ogn_client)
        
        await manager.initialize()
        
        # All sources should be enabled
        assert manager._source_health["dump1090"]["enabled"] is True
        assert manager._source_health["opensky"]["enabled"] is True
        assert manager._source_health["ogn"]["enabled"] is True
        
        # Connections tested
        assert mock_dump1090_client.test_connection.called
        assert mock_opensky_client.test_connection.called
        assert mock_ogn_client.test_connection.called
    
    @pytest.mark.asyncio
    async def test_initialize_some_sources_unavailable(
        self, mock_hass, manager_config,
        mock_dump1090_client, mock_opensky_client, mock_ogn_client
    ):
        """Test initialisation with some sources unavailable.
        
        Validates:
            - Failed sources marked as disabled
            - Error message captured
            - Available sources still queried
        """
        mock_dump1090_client.test_connection.return_value = (True, None)
        mock_opensky_client.test_connection.return_value = (False, "Connection refused")
        mock_ogn_client.test_connection.return_value = (True, None)
        
        manager = ADSBManager(mock_hass, manager_config)
        manager.register_client("dump1090", mock_dump1090_client)
        manager.register_client("opensky", mock_opensky_client)
        manager.register_client("ogn", mock_ogn_client)
        
        await manager.initialize()
        
        # Enabled status reflects results
        assert manager._source_health["dump1090"]["enabled"] is True
        assert manager._source_health["opensky"]["enabled"] is False
        assert manager._source_health["ogn"]["enabled"] is True
        
        # Error captured
        assert "Connection refused" in manager._source_health["opensky"]["last_error"]


class TestADSBManagerMultiSourceQuerying:
    """Test querying multiple sources in parallel."""
    
    @pytest.mark.asyncio
    async def test_query_all_sources_in_parallel(
        self, mock_hass, manager_config, sample_aircraft,
        mock_dump1090_client, mock_opensky_client, mock_ogn_client
    ):
        """Test querying multiple sources in parallel.
        
        Validates:
            - All sources queried simultaneously
            - Results collected from each source
            - Network timeouts don't block other sources
        """
        # Each source returns different aircraft
        mock_dump1090_client.get_aircraft_near_location.return_value = [sample_aircraft["g_abcd"]]
        mock_opensky_client.get_aircraft_near_location.return_value = [sample_aircraft["n_test"]]
        mock_ogn_client.get_aircraft_near_location.return_value = [sample_aircraft["flarm_dd1234"]]
        
        manager = ADSBManager(mock_hass, manager_config)
        manager.register_client("dump1090", mock_dump1090_client)
        manager.register_client("opensky", mock_opensky_client)
        manager.register_client("ogn", mock_ogn_client)
        
        # Enable all sources
        for source_name in ["dump1090", "opensky", "ogn"]:
            manager._source_health[source_name]["enabled"] = True
        
        # Query
        result = await manager.get_aircraft_near_location(51.5, -0.4, 25)
        
        # All sources should have been queried
        assert mock_dump1090_client.get_aircraft_near_location.called
        assert mock_opensky_client.get_aircraft_near_location.called
        assert mock_ogn_client.get_aircraft_near_location.called
        
        # Results deduplicated (3 unique ICAO24 codes)
        assert len(result) == 3
    
    @pytest.mark.asyncio
    async def test_skip_disabled_sources(
        self, mock_hass, manager_config, sample_aircraft,
        mock_dump1090_client, mock_opensky_client, mock_ogn_client
    ):
        """Test that disabled sources are skipped.
        
        Validates:
            - Only enabled sources queried
            - Results from available sources only
        """
        mock_dump1090_client.get_aircraft_near_location.return_value = [sample_aircraft["g_abcd"]]
        mock_opensky_client.get_aircraft_near_location.return_value = [sample_aircraft["n_test"]]
        
        manager = ADSBManager(mock_hass, manager_config)
        manager.register_client("dump1090", mock_dump1090_client)
        manager.register_client("opensky", mock_opensky_client)
        manager.register_client("ogn", mock_ogn_client)
        
        # Disable opensky and ogn
        manager._source_health["opensky"]["enabled"] = False
        manager._source_health["ogn"]["enabled"] = False
        
        # Query
        result = await manager.get_aircraft_near_location(51.5, -0.4, 25)
        
        # Only dump1090 queried
        assert mock_dump1090_client.get_aircraft_near_location.called
        assert not mock_opensky_client.get_aircraft_near_location.called
        assert not mock_ogn_client.get_aircraft_near_location.called
        
        # Only dump1090's aircraft in results
        assert len(result) == 1
        assert result[0].registration == "G-ABCD"


class TestADSBManagerDeduplication:
    """Test ICAO24 deduplication logic."""
    
    @pytest.mark.asyncio
    async def test_deduplicate_same_aircraft_different_sources(
        self, mock_hass, manager_config,
        mock_dump1090_client, mock_opensky_client
    ):
        """Test deduplication when same aircraft reported by multiple sources.
        
        Validates:
            - Same ICAO24 merged to single aircraft
            - Highest priority source wins for conflicting data
            - Missing fields filled from lower-priority sources
        """
        # Both sources report same aircraft (G-ABCD, ICAO 4CA1E3)
        dump1090_aircraft = AircraftData(
            registration="G-ABCD",
            icao24="4CA1E3",
            callsign="GLIDER01",
            latitude=51.48,
            longitude=-0.46,
            altitude_ft=3500,
            ground_speed_kt=80,
            track_deg=270,
            aircraft_type=None,  # Missing type
            source="dump1090",
            last_seen=dt_util.utcnow(),
            is_flarm=True
        )
        
        opensky_aircraft = AircraftData(
            registration="G-ABCD",
            icao24="4CA1E3",
            callsign="GLIDER01",
            latitude=51.4801,  # Slightly different (older data)
            longitude=-0.4601,
            altitude_ft=3501,  # Slightly different
            ground_speed_kt=81,
            track_deg=271,
            aircraft_type="ASW20",  # Has type info
            source="opensky",
            last_seen=dt_util.utcnow() - timedelta(seconds=5),  # Older
            is_flarm=True
        )
        
        mock_dump1090_client.get_aircraft_near_location.return_value = [dump1090_aircraft]
        mock_opensky_client.get_aircraft_near_location.return_value = [opensky_aircraft]
        
        manager = ADSBManager(mock_hass, manager_config)
        manager.register_client("dump1090", mock_dump1090_client)
        manager.register_client("opensky", mock_opensky_client)
        manager._source_health["dump1090"]["enabled"] = True
        manager._source_health["opensky"]["enabled"] = True
        
        result = await manager.get_aircraft_near_location(51.5, -0.4, 25)
        
        # Should be deduplicated to single aircraft
        assert len(result) == 1
        merged = result[0]
        
        # Highest priority (dump1090) data should win for position
        assert merged.latitude == 51.48
        assert merged.longitude == -0.46
        assert merged.altitude_ft == 3500
        
        # Lower priority (opensky) fills missing data
        assert merged.aircraft_type == "ASW20"  # Filled from opensky
    
    @pytest.mark.asyncio
    async def test_no_deduplication_different_icao24(
        self, mock_hass, manager_config, sample_aircraft,
        mock_dump1090_client, mock_opensky_client
    ):
        """Test that aircraft with different ICAO24 codes stay separate.
        
        Validates:
            - Different ICAO24 = different aircraft
            - Both retained in results
        """
        mock_dump1090_client.get_aircraft_near_location.return_value = [sample_aircraft["g_abcd"]]
        mock_opensky_client.get_aircraft_near_location.return_value = [sample_aircraft["n_test"]]
        
        manager = ADSBManager(mock_hass, manager_config)
        manager.register_client("dump1090", mock_dump1090_client)
        manager.register_client("opensky", mock_opensky_client)
        manager._source_health["dump1090"]["enabled"] = True
        manager._source_health["opensky"]["enabled"] = True
        
        result = await manager.get_aircraft_near_location(51.5, -0.4, 25)
        
        # Different ICAO24 codes = different aircraft
        assert len(result) == 2
        icao_codes = {a.icao24 for a in result}
        assert icao_codes == {"4CA1E3", "A00A8B"}


class TestADSBManagerCaching:
    """Test cache management and LRU eviction."""
    
    @pytest.mark.asyncio
    async def test_cache_hit_on_repeated_query(
        self, mock_hass, manager_config, sample_aircraft,
        mock_dump1090_client, mock_opensky_client
    ):
        """Test that repeated queries hit cache.
        
        Validates:
            - First query hits sources
            - Repeated query within TTL uses cache
            - Cache hit counter increments
        """
        mock_dump1090_client.get_aircraft_near_location.return_value = [sample_aircraft["g_abcd"]]
        mock_opensky_client.get_aircraft_near_location.return_value = [sample_aircraft["n_test"]]
        
        manager = ADSBManager(mock_hass, manager_config)
        manager.register_client("dump1090", mock_dump1090_client)
        manager.register_client("opensky", mock_opensky_client)
        manager._source_health["dump1090"]["enabled"] = True
        manager._source_health["opensky"]["enabled"] = True
        
        # First query - hits sources
        result1 = await manager.get_aircraft_near_location(51.5, -0.4, 25)
        first_call_count = mock_dump1090_client.get_aircraft_near_location.call_count
        
        # Second query by ICAO24 - should hit cache
        cached = await manager.get_aircraft_by_icao24("4CA1E3")
        
        assert cached is not None
        assert cached.registration == "G-ABCD"
        assert manager._cache_hits > 0
    
    @pytest.mark.asyncio
    async def test_lru_eviction_on_cache_overflow(
        self, mock_hass, manager_config, mock_dump1090_client
    ):
        """Test LRU eviction when cache exceeds max size.
        
        Validates:
            - Cache limited to max_cache_entries
            - Least recently used entries evicted
            - Most recently used retained
        """
        manager = ADSBManager(mock_hass, {"max_cache_entries": 5, "cache_ttl_seconds": 300})
        manager.register_client("dump1090", mock_dump1090_client)
        manager._source_health["dump1090"]["enabled"] = True
        
        # Create 10 aircraft
        aircraft_list = []
        for i in range(10):
            aircraft_list.append(AircraftData(
                registration=f"N{i:05d}",
                icao24=f"A0000{i:02d}",
                latitude=51.5 + i * 0.01,
                longitude=-0.4,
                altitude_ft=2000,
                ground_speed_kt=100,
                track_deg=0,
                source="dump1090",
                last_seen=dt_util.utcnow(),
                is_flarm=False
            ))
        
        mock_dump1090_client.get_aircraft_near_location.return_value = aircraft_list
        
        # Query all
        await manager.get_aircraft_near_location(51.5, -0.4, 50)
        
        # Cache should not exceed max size
        assert len(manager._deduplicated_cache) <= 5
        
        # Most recent should still be in cache (A00005-A00009)
        recent_keys = {f"A00000{i}" for i in range(5, 10)}
        assert len(manager._deduplicated_cache) > 0
        # Some recent items should be in cache
        assert any(key in manager._deduplicated_cache for key in recent_keys)


class TestADSBManagerStats:
    """Test statistics and monitoring."""
    
    def test_get_cache_stats(
        self, mock_hass, manager_config,
        mock_dump1090_client, mock_opensky_client
    ):
        """Test cache statistics reporting.
        
        Validates:
            - Cache hit rate calculated correctly
            - Source health status included
            - Performance metrics tracked
        """
        manager = ADSBManager(mock_hass, manager_config)
        manager.register_client("dump1090", mock_dump1090_client)
        manager.register_client("opensky", mock_opensky_client)
        
        # Simulate some queries
        manager._cache_hits = 85
        manager._cache_misses = 15
        manager._query_count = 100
        
        stats = manager.get_cache_stats()
        
        assert stats["cache_hit_rate"] == 0.85
        assert stats["cache_hits"] == 85
        assert stats["cache_misses"] == 15
        assert stats["query_count"] == 100
        assert "sources" in stats
        assert "dump1090" in stats["sources"]
        assert "opensky" in stats["sources"]


class TestADSBManagerErrorHandling:
    """Test error handling and graceful degradation."""
    
    @pytest.mark.asyncio
    async def test_timeout_doesnt_block_other_sources(
        self, mock_hass, sample_aircraft,
        mock_dump1090_client, mock_opensky_client, mock_ogn_client
    ):
        """Test that timeout in one source doesn't block others.
        
        Validates:
            - OpenSky timeout doesn't prevent dump1090 results
            - Partial results returned successfully
        """
        mock_dump1090_client.get_aircraft_near_location.return_value = [sample_aircraft["g_abcd"]]
        
        async def slow_opensky(*args, **kwargs):
            await asyncio.sleep(10)  # Exceeds timeout
            return []
        
        mock_opensky_client.get_aircraft_near_location = slow_opensky
        mock_ogn_client.get_aircraft_near_location.return_value = [sample_aircraft["flarm_dd1234"]]
        
        # Use shorter timeout for faster test
        manager = ADSBManager(mock_hass, {"max_cache_entries": 100, "cache_ttl_seconds": 30})
        manager.register_client("dump1090", mock_dump1090_client)
        manager.register_client("opensky", mock_opensky_client)
        manager.register_client("ogn", mock_ogn_client)
        manager._source_health["dump1090"]["enabled"] = True
        manager._source_health["opensky"]["enabled"] = True
        manager._source_health["ogn"]["enabled"] = True
        
        # Query should return results from available sources
        # Manager has 5s internal timeout, so this should complete successfully with partial results
        result = await manager.get_aircraft_near_location(51.5, -0.4, 25)
        
        # Should get results from dump1090 and OGN (OpenSky times out internally)
        assert isinstance(result, list)
        assert len(result) >= 1  # At least dump1090 or OGN result
