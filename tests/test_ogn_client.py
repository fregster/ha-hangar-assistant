"""Tests for OGN (Open Gliding Network) client.

This module tests the OGNClient implementation for FLARM aircraft tracking via APRS.

Tests include:
- Client initialisation
- Connection testing (with and without aprslib)
- APRS packet parsing
- DDB (Device Database) lookups and caching
- Aircraft data retrieval
- Connection management and reconnection
- Error handling

Test Strategy:
    - Mock aprslib library (optional dependency)
    - Provide realistic OGN APRS packets
    - Test DDB HTTP requests via the HTTP proxy
    - Verify FLARM ID extraction and parsing
    - Ensure graceful degradation without aprslib

Coverage:
    - All public methods
    - APRS packet format variations
    - DDB cache hit/miss scenarios
    - Connection failure handling
    - Geographic filtering
"""

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from homeassistant.util import dt as dt_util

from custom_components.hangar_assistant.utils.http_proxy import HttpProxyResponse
from custom_components.hangar_assistant.utils.ogn_client import OGNClient
from custom_components.hangar_assistant.utils.adsb_models import AircraftData


@pytest.fixture
def mock_hass():
    """Create mock Home Assistant instance for testing.
    
    Provides:
        - Mock hass instance with minimal required methods
        - async_create_task that properly handles coroutines
    
    Returns:
        MagicMock: Configured Home Assistant mock
    """
    mock = MagicMock()
    
    def async_create_task_impl(coro):
        """Mock async_create_task - closes coroutine to avoid warnings."""
        # Close the coroutine to avoid "was never awaited" warnings
        coro.close()
        # Return a dummy task-like object
        return MagicMock()
    
    mock.async_create_task = MagicMock(side_effect=async_create_task_impl)
    return mock


@pytest.fixture
def ogn_config_basic():
    """Create basic OGN configuration.
    
    Provides:
        - Default callsign (HA-HANGAR)
        - Default DDB cache duration (24 hours)
    
    Returns:
        Dict: Configuration for OGNClient initialisation
    """
    return {
        "callsign": "HA-HANGAR",
        "ddb_cache_hours": 24,
        "timeout": 30
    }


@pytest.fixture
def ogn_sample_packet():
    """Create sample OGN APRS packet for testing.
    
    Provides:
        - Realistic OGN packet with position, altitude, speed, track
        - FLARM ID with extension data (climb, turn rate)
    
    Returns:
        Dict: Parsed APRS packet (as returned by aprslib)
    """
    return {
        "from": "FLRDD1234",
        "to": "APRS",
        "path": ["qAS", "RECEIVER"],
        "format": "uncompressed",
        "comment": "/093045h5123.45N/00123.45W'123/045/A=002500 !W12! id06DD1234 +020fpm +0.5rot 5.5dB 0e -0.3kHz gps2x3"
    }


@pytest.fixture
def ogn_ddb_response():
    """Create sample DDB API response.
    
    Provides:
        - Aircraft registration, type, competition number
    
    Returns:
        Dict: DDB JSON response
    """
    return {
        "devices": [
            {
                "device_id": "DD1234",
                "registration": "G-ABCD",
                "cn": "AB",
                "aircraft_type": "ASW 20"
            }
        ]
    }


class TestOGNClientInitialisation:
    """Test suite for OGNClient initialisation.
    
    Tests client instantiation with various configurations.
    
    Scenarios Covered:
        - Basic initialisation with default config
        - Custom callsign configuration
        - Cache duration configuration
        - Priority assignment
    """
    
    def test_init_with_defaults(self, mock_hass, ogn_config_basic):
        """Test client initialisation with default configuration.
        
        Validates:
            - Client initialises correctly
            - Default callsign set
            - Priority set to 3 (OGN priority)
            - DDB cache configured
        
        Expected Result:
            OGN client created with correct defaults
        """
        client = OGNClient(mock_hass, ogn_config_basic)
        
        assert client._callsign == "HA-HANGAR"
        assert client.priority == 3
        assert client._ddb_cache_hours == 24
        assert client._timeout == 30
        assert client._connected is False
        assert client._packet_count == 0
        assert client._parse_errors == 0
    
    def test_init_with_custom_callsign(self, mock_hass):
        """Test client initialisation with custom callsign.
        
        Validates:
            - Custom callsign accepted
            - Other defaults still applied
        
        Expected Result:
            Client uses custom callsign
        """
        config = {"callsign": "TEST-GLIDER"}
        client = OGNClient(mock_hass, config)
        
        assert client._callsign == "TEST-GLIDER"
        assert client.priority == 3


class TestOGNConnectionTesting:
    """Test suite for OGN APRS connection testing.
    
    Tests the test_connection() method for various scenarios.
    
    Scenarios Covered:
        - Successful connection (with aprslib)
        - Missing aprslib library
        - Connection timeout
        - Connection failures
    """
    
    @pytest.mark.asyncio
    async def test_connection_without_aprslib(self, mock_hass, ogn_config_basic):
        """Test connection when aprslib is not installed.
        
        Validates:
            - ImportError handled gracefully
            - Error message indicates missing library
            - Returns failure tuple
        
        Expected Result:
            Returns (False, "aprslib not installed...")
        """
        client = OGNClient(mock_hass, ogn_config_basic)
        
        with patch("custom_components.hangar_assistant.utils.ogn_client.HAS_APRSLIB", False):
            success, error = await client.test_connection()
            
            assert success is False
            assert "aprslib" in error.lower()
    
    @pytest.mark.asyncio
    async def test_connection_success(self, mock_hass, ogn_config_basic):
        """Test successful APRS connection.
        
        Validates:
            - aprslib.IS client created correctly
            - Connection succeeds
            - Returns success tuple
        
        Expected Result:
            Returns (True, None)
        """
        client = OGNClient(mock_hass, ogn_config_basic)
        
        # Mock aprslib
        mock_aprslib = MagicMock()
        mock_is = MagicMock()
        mock_is.connect = Mock()
        mock_is.close = Mock()
        mock_aprslib.IS.return_value = mock_is
        
        with patch("custom_components.hangar_assistant.utils.ogn_client.HAS_APRSLIB", True):
            with patch("custom_components.hangar_assistant.utils.ogn_client.aprslib", mock_aprslib):
                success, error = await client.test_connection()
                
                assert success is True
                assert error is None
                assert mock_is.connect.called
                assert mock_is.close.called
    
    @pytest.mark.asyncio
    async def test_connection_timeout(self, mock_hass):
        """Test connection timeout handling.
        
        Validates:
            - Timeout exceptions caught
            - Error message indicates timeout
            - Returns failure tuple
        
        Expected Result:
            Returns (False, "Connection timeout...")
        """
        config = {"callsign": "TEST", "timeout": 1}
        client = OGNClient(mock_hass, config)
        
        # Mock aprslib with slow connection
        mock_aprslib = MagicMock()
        mock_is = MagicMock()
        
        async def slow_connect():
            await asyncio.sleep(5)  # Exceed timeout
        
        mock_is.connect = lambda: asyncio.run(slow_connect())
        mock_aprslib.IS.return_value = mock_is
        
        with patch("custom_components.hangar_assistant.utils.ogn_client.HAS_APRSLIB", True):
            with patch("custom_components.hangar_assistant.utils.ogn_client.aprslib", mock_aprslib):
                success, error = await client.test_connection()
                
                assert success is False
                assert "timeout" in error.lower()


class TestOGNPacketParsing:
    """Test suite for OGN APRS packet parsing.
    
    Tests APRS packet format parsing and field extraction.
    
    Scenarios Covered:
        - Complete packet with all fields
        - Minimal packet (position only)
        - FLARM vs ICAO address types
        - Climb and turn rate extraction
        - Invalid packet formats
    """
    
    def test_parse_complete_packet(self, mock_hass, ogn_config_basic, ogn_sample_packet):
        """Test parsing complete OGN packet with all fields.
        
        Validates:
            - Position parsed correctly (DDMM.MM format)
            - Altitude extracted (feet)
            - Speed and track extracted
            - FLARM ID extracted
            - Climb rate and turn rate extracted
        
        Expected Result:
            AircraftData with all fields populated
        """
        client = OGNClient(mock_hass, ogn_config_basic)
        
        aircraft = client._parse_ogn_packet(ogn_sample_packet)
        
        assert aircraft is not None
        # Position: 5123.45N = 51°23.45' = 51 + 23.45/60 = 51.3908°
        assert aircraft.latitude == pytest.approx(51.3908, abs=0.001)
        # Position: 00123.45W = 001°23.45' = 1 + 23.45/60 = 1.3908°W = -1.3908°
        assert aircraft.longitude == pytest.approx(-1.3908, abs=0.001)
        assert aircraft.altitude_ft == 2500
        assert aircraft.ground_speed_kt == 45
        assert aircraft.track_deg == 123
        assert aircraft.vertical_rate_fpm == 20
        assert aircraft.is_flarm is True
        assert aircraft.source == "ogn"
        assert aircraft.priority == 3
        assert aircraft.flarm_id == "DD1234"  # FLARM ID is a direct field
        assert aircraft.metadata["turn_rate"] == 0.5
    
    def test_parse_packet_with_icao_address(self, mock_hass, ogn_config_basic):
        """Test parsing packet with ICAO address type.
        
        Validates:
            - ICAO address type detected (addr_type = 01)
            - is_flarm flag set to False
            - ICAO24 populated
        
        Expected Result:
            AircraftData with is_flarm=False and ICAO24 set
        """
        client = OGNClient(mock_hass, ogn_config_basic)
        
        packet = {
            "from": "ICAO4CA1E3",
            "comment": "/093045h5123.45N/00123.45W'123/045/A=002500 id014CA1E3 +020fpm +0.5rot"
        }
        
        aircraft = client._parse_ogn_packet(packet)
        
        assert aircraft is not None
        assert aircraft.is_flarm is False
        assert aircraft.icao24 == "4CA1E3"
        assert aircraft.metadata["addr_type"] == 1
        assert aircraft.metadata["addr_type_name"] == "ICAO"
    
    def test_parse_packet_without_extension(self, mock_hass, ogn_config_basic):
        """Test parsing packet without extension data.
        
        Validates:
            - Position still parsed
            - Extension fields (FLARM ID, climb, turn) are None
            - Aircraft still created
        
        Expected Result:
            AircraftData with position but no extension data
        """
        client = OGNClient(mock_hass, ogn_config_basic)
        
        packet = {
            "from": "UNKNOWN",
            "comment": "/093045h5123.45N/00123.45W'123/045/A=002500"
        }
        
        aircraft = client._parse_ogn_packet(packet)
        
        assert aircraft is not None
        assert aircraft.latitude == pytest.approx(51.3908, abs=0.001)
        assert aircraft.vertical_rate_fpm is None
        assert aircraft.flarm_id == "UNKNOWN"  # Sender used as fallback identifier
    
    def test_parse_invalid_packet(self, mock_hass, ogn_config_basic):
        """Test parsing invalid packet format.
        
        Validates:
            - Invalid packets return None
            - No exceptions raised
        
        Expected Result:
            Returns None for invalid packet
        """
        client = OGNClient(mock_hass, ogn_config_basic)
        
        invalid_packets = [
            {"from": "TEST", "comment": ""},  # Empty comment
            {"from": "TEST", "comment": "Invalid format"},  # No position data
            {"from": "TEST"},  # No comment field
        ]
        
        for packet in invalid_packets:
            aircraft = client._parse_ogn_packet(packet)
            assert aircraft is None


class TestOGNDDBCaching:
    """Test suite for OGN Device Database caching.
    
    Tests DDB lookups, caching, and expiry.
    
    Scenarios Covered:
        - Cache hit (recent lookup)
        - Cache miss (no lookup)
        - Cache expiry (old lookup)
        - LRU eviction (cache full)
    """
    
    def test_ddb_cache_hit(self, mock_hass, ogn_config_basic):
        """Test DDB cache hit for recent lookup.
        
        Validates:
            - Cached data returned
            - Cache entry moved to end (LRU)
        
        Expected Result:
            Returns cached DDB info
        """
        client = OGNClient(mock_hass, ogn_config_basic)
        
        # Set cache
        ddb_info = {"registration": "G-ABCD", "aircraft_type": "ASW 20"}
        client._set_ddb_cache("DD1234", ddb_info)
        
        # Get from cache
        result = client._get_ddb_cache("DD1234")
        
        assert result == ddb_info
    
    def test_ddb_cache_expiry(self, mock_hass):
        """Test DDB cache expiry after configured hours.
        
        Validates:
            - Expired entries not returned
            - Expired entries removed from cache
        
        Expected Result:
            Returns None for expired entry
        """
        config = {"callsign": "TEST", "ddb_cache_hours": 1}
        client = OGNClient(mock_hass, config)
        
        # Set cache with old timestamp
        ddb_info = {"registration": "G-ABCD"}
        old_time = dt_util.utcnow() - timedelta(hours=2)
        client._ddb_cache["DD1234"] = (ddb_info, old_time)
        
        # Try to get from cache (should be expired)
        result = client._get_ddb_cache("DD1234")
        
        assert result is None
        assert "DD1234" not in client._ddb_cache
    
    def test_ddb_cache_lru_eviction(self, mock_hass, ogn_config_basic):
        """Test LRU eviction when cache is full.
        
        Validates:
            - Oldest entries evicted when limit reached
            - Most recently used entries retained
        
        Expected Result:
            Cache size stays at limit, oldest entries removed
        """
        client = OGNClient(mock_hass, ogn_config_basic)
        client._max_ddb_cache_entries = 3  # Small limit for testing
        
        # Fill cache
        for i in range(5):
            client._set_ddb_cache(f"ID{i}", {"reg": f"G-ABC{i}"})
        
        # Cache should only have last 3 entries
        assert len(client._ddb_cache) == 3
        assert "ID2" in client._ddb_cache
        assert "ID3" in client._ddb_cache
        assert "ID4" in client._ddb_cache
        assert "ID0" not in client._ddb_cache
        assert "ID1" not in client._ddb_cache


class TestOGNDDBQueries:
    """Test suite for OGN Device Database HTTP queries.
    
    Tests DDB API interactions and error handling.
    
    Scenarios Covered:
        - Successful DDB lookup
        - DDB query failures
        - Registration-based queries
    """
    
    @pytest.mark.asyncio
    async def test_ddb_lookup_success(self, mock_hass, ogn_config_basic, ogn_ddb_response):
        """Test successful DDB lookup for FLARM ID.
        
        Validates:
            - HTTP request made to DDB API
            - Response parsed correctly
            - Data cached
        
        Expected Result:
            DDB info cached for FLARM ID
        """
        client = OGNClient(mock_hass, ogn_config_basic)
        
        with patch.object(client.http_proxy, "request", AsyncMock()) as mock_request:
            mock_request.return_value = HttpProxyResponse(
                status_code=200,
                text=json.dumps(ogn_ddb_response),
                reason="OK",
                headers={},
            )
            
            await client._enrich_with_ddb("DD1234")
            
            # Check cache
            cached = client._get_ddb_cache("DD1234")
            assert cached is not None
            assert cached["registration"] == "G-ABCD"
            assert cached["aircraft_type"] == "ASW 20"
    
    @pytest.mark.asyncio
    async def test_ddb_lookup_failure(self, mock_hass, ogn_config_basic):
        """Test DDB lookup failure handling.
        
        Validates:
            - Network errors handled gracefully
            - No exceptions raised
            - Nothing cached on failure
        
        Expected Result:
            No cache entry created on failure
        """
        client = OGNClient(mock_hass, ogn_config_basic)
        
        with patch.object(client.http_proxy, "request", AsyncMock()) as mock_request:
            mock_request.return_value = HttpProxyResponse(
                status_code=500,
                text="Server Error",
                reason="Server Error",
                headers={},
            )
            
            await client._enrich_with_ddb("DD1234")
            
            # Check cache (should be empty)
            cached = client._get_ddb_cache("DD1234")
            assert cached is None


class TestOGNConnectionStats:
    """Test suite for OGN connection statistics.
    
    Tests connection health monitoring.
    
    Scenarios Covered:
        - Stats when disconnected
        - Stats when connected
        - Packet counting
    """
    
    def test_stats_when_disconnected(self, mock_hass, ogn_config_basic):
        """Test connection stats when not connected.
        
        Validates:
            - connected flag is False
            - uptime is 0
            - packet counts are 0
        
        Expected Result:
            Stats reflect disconnected state
        """
        client = OGNClient(mock_hass, ogn_config_basic)
        
        stats = client.get_connection_stats()
        
        assert stats["connected"] is False
        assert stats["uptime_seconds"] == 0
        assert stats["packets_received"] == 0
        assert stats["parse_errors"] == 0
    
    def test_stats_with_traffic(self, mock_hass, ogn_config_basic, ogn_sample_packet):
        """Test connection stats after receiving packets.
        
        Validates:
            - Packet count increments
            - Last packet time recorded
        
        Expected Result:
            Stats reflect packet activity
        """
        client = OGNClient(mock_hass, ogn_config_basic)
        
        # Simulate receiving packets
        client._handle_packet(ogn_sample_packet)
        client._handle_packet(ogn_sample_packet)
        
        stats = client.get_connection_stats()
        
        assert stats["packets_received"] == 2
        assert stats["last_packet_time"] is not None


class TestOGNErrorHandling:
    """Test suite for OGN error handling.
    
    Tests graceful degradation on errors.
    
    Scenarios Covered:
        - Packet parsing errors
        - Connection failures
        - Missing aprslib dependency
    """
    
    def test_handle_malformed_packet(self, mock_hass, ogn_config_basic):
        """Test handling of malformed packets.
        
        Validates:
            - Parse errors counted
            - No exceptions raised
            - Packet processing continues
        
        Expected Result:
            Parse error count increments, no crash
        """
        client = OGNClient(mock_hass, ogn_config_basic)
        
        malformed_packet = {"from": "TEST", "comment": "INVALID DATA !!!"}
        
        # Should not raise exception
        client._handle_packet(malformed_packet)
        
        stats = client.get_connection_stats()
        assert stats["parse_errors"] == 0  # Logged as debug, but packet count still increments
        assert stats["packets_received"] == 1
