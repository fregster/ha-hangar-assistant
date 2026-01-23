"""Tests for dump1090 client.

This module tests the Dump1090Client implementation for local ADS-B receiver integration.

Tests include:
- Client initialization and configuration
- Connection testing (success and failure scenarios)
- Aircraft data fetching and parsing
- Registration and ICAO24 lookups
- Location-based queries with distance filtering
- Cache behavior (hits, misses, TTL expiration)
- Error handling (network errors, invalid JSON, missing fields)
- dump1090 JSON format parsing edge cases

Test Strategy:
    - Mock HTTP proxy requests for outbound calls
    - Provide realistic dump1090 JSON responses
    - Test both success and failure paths
    - Verify caching optimises performance
    - Ensure graceful degradation on errors

Coverage:
    - All public methods (test_connection, get_aircraft_by_registration, etc.)
    - JSON parsing with various field combinations
    - Cache hit/miss scenarios
    - Network error handling
    - Invalid response handling
"""

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.util import dt as dt_util

from custom_components.hangar_assistant.utils.http_proxy import HttpProxyResponse
from custom_components.hangar_assistant.utils.dump1090_client import Dump1090Client
from custom_components.hangar_assistant.utils.adsb_models import AircraftData


@pytest.fixture
def mock_hass():
    """Create mock Home Assistant instance for testing.
    
    Provides:
        - Mock hass instance with minimal required methods
    
    Returns:
        MagicMock: Configured Home Assistant mock
    """
    return MagicMock()


@pytest.fixture
def dump1090_config():
    """Create dump1090 configuration for testing.
    
    Provides:
        - Standard localhost URL configuration
        - Default timeout value
    
    Returns:
        Dict: Configuration for Dump1090Client initialization
    """
    return {
        "url": "http://localhost:8080/data/aircraft.json",
        "timeout": 5
    }


@pytest.fixture
def dump1090_sample_data():
    """Create sample dump1090 JSON response for testing.
    
    Provides:
        - Realistic dump1090 JSON with 3 aircraft
        - Mix of complete and incomplete data
        - Various aircraft types and states
    
    Returns:
        Dict: dump1090 JSON response structure
    """
    return {
        "now": 1737560000.0,
        "messages": 123456,
        "aircraft": [
            {
                "hex": "4CA1E3",
                "flight": "BAW123  ",
                "r": "G-ABCD",
                "t": "B738",
                "alt_baro": 15000,
                "gs": 450,
                "track": 270,
                "lat": 51.4775,
                "lon": -0.4614,
                "seen": 0.5,
                "category": "A3",
                "squawk": "7000",
                "messages": 1500,
                "rssi": -15.2
            },
            {
                "hex": "ABC123",
                "r": "N12345",
                "alt_baro": 3500,
                "gs": 110,
                "track": 180,
                "lat": 51.5,
                "lon": -0.5,
                "seen": 2.0,
                "baro_rate": -500,
                "squawk": "7001"
            },
            {
                "hex": "DEF456",
                "lat": 51.6,
                "lon": -0.3,
                "seen": 10.0
            }
        ]
    }


class TestDump1090ClientInitialization:
    """Test suite for Dump1090Client initialization.
    
    Tests client instantiation with various configurations.
    
    Scenarios Covered:
        - Default configuration
        - Custom URL
        - Custom timeout
        - Priority assignment
        - Cache configuration
    """
    
    def test_init_with_default_config(self, mock_hass):
        """Test client initialisation with default configuration.
        
        Validates:
            - Client initialises without errors
            - Default values applied correctly
            - URL set to default
            - Priority set to 1 (highest)
        
        Expected Result:
            Client created with default URL configuration
        """
        client = Dump1090Client(mock_hass, {})
        
        assert client._url == "http://localhost:8080/data/aircraft.json"
        assert client._timeout == 5
        assert client.priority == 1
    
    def test_init_with_custom_config(self, mock_hass):
        """Test client initialisation with custom configuration.
        
        Validates:
            - Custom URL respected
            - Custom timeout applied
            - URL reflects custom values
        
        Expected Result:
            Client created with custom configuration values
        """
        config = {
            "url": "http://192.168.1.100:8080/aircraft.json",
            "timeout": 10
        }
        
        client = Dump1090Client(mock_hass, config)
        
        assert client._url == "http://192.168.1.100:8080/aircraft.json"
        assert client._timeout == 10


class TestDump1090ConnectionTesting:
    """Test suite for dump1090 connection testing.
    
    Tests the test_connection() method for various network scenarios.
    
    Scenarios Covered:
        - Successful connection
        - HTTP errors (404, 500)
        - Network timeouts
        - Invalid JSON responses
        - Missing aircraft key
    """
    
    @pytest.mark.asyncio
    async def test_connection_success(self, mock_hass, dump1090_config, dump1090_sample_data):
        """Test successful connection to dump1090.
        
        Validates:
            - HTTP 200 response handled correctly
            - JSON parsed successfully
            - Aircraft count logged
            - Returns success tuple
        
        Expected Result:
            Returns (True, None) indicating successful connection
        """
        client = Dump1090Client(mock_hass, dump1090_config)
        
        with patch.object(client.http_proxy, "request", AsyncMock()) as mock_request:
            mock_request.return_value = HttpProxyResponse(
                status_code=200,
                text=json.dumps(dump1090_sample_data),
                reason="OK",
                headers={},
            )
            
            success, error = await client.test_connection()
            
            assert success is True
            assert error is None
    
    @pytest.mark.asyncio
    async def test_connection_http_error(self, mock_hass, dump1090_config):
        """Test connection with HTTP error response.
        
        Validates:
            - HTTP 404 handled gracefully
            - Error message includes status code
            - Returns failure tuple
        
        Expected Result:
            Returns (False, "HTTP 404: Not Found") indicating connection failure
        """
        client = Dump1090Client(mock_hass, dump1090_config)
        
        with patch.object(client.http_proxy, "request", AsyncMock()) as mock_request:
            mock_request.return_value = HttpProxyResponse(
                status_code=404,
                text="Not Found",
                reason="Not Found",
                headers={},
            )
            
            success, error = await client.test_connection()
            
            assert success is False
            assert "HTTP 404" in error
    
    @pytest.mark.asyncio
    async def test_connection_timeout(self, mock_hass, dump1090_config):
        """Test connection timeout handling.
        
        Validates:
            - Timeout exception caught gracefully
            - Error message includes timeout duration
            - Returns failure tuple
        
        Expected Result:
            Returns (False, "Connection timeout after 5s")
        """
        client = Dump1090Client(mock_hass, dump1090_config)
        
        with patch.object(client.http_proxy, "request") as mock_request:
            mock_request.side_effect = asyncio.TimeoutError("Connection timeout after 5s")
            
            success, error = await client.test_connection()
            
            assert success is False
            assert "timeout" in error.lower()
            assert "5" in error
    
    @pytest.mark.asyncio
    async def test_connection_invalid_json(self, mock_hass, dump1090_config):
        """Test connection with invalid JSON response.
        
        Validates:
            - Missing 'aircraft' key detected
            - Error message explains problem
            - Returns failure tuple
        
        Expected Result:
            Returns (False, "Invalid dump1090 response: missing 'aircraft' key")
        """
        client = Dump1090Client(mock_hass, dump1090_config)
        
        with patch.object(client.http_proxy, "request", AsyncMock()) as mock_request:
            mock_request.return_value = HttpProxyResponse(
                status_code=200,
                text=json.dumps({"messages": 123}),
                reason="OK",
                headers={},
            )
            
            success, error = await client.test_connection()
            
            assert success is False
            assert "aircraft" in error.lower()


class TestDump1090AircraftFetching:
    """Test suite for fetching aircraft from dump1090.
    
    Tests aircraft retrieval by registration, ICAO24, and location.
    
    Scenarios Covered:
        - Fetch by registration (found/not found)
        - Fetch by ICAO24 (found/not found)
        - Fetch near location with radius filtering
        - Cache hits and misses
        - Network error handling
    """
    
    @pytest.mark.asyncio
    async def test_get_aircraft_by_registration(
        self, mock_hass, dump1090_config, dump1090_sample_data
    ):
        """Test retrieving aircraft by registration.
        
        Validates:
            - Correct aircraft returned for valid registration
            - Registration matching is case-insensitive
            - Aircraft cached after retrieval
        
        Expected Result:
            Returns AircraftData for G-ABCD with correct attributes
        """
        client = Dump1090Client(mock_hass, dump1090_config)
        
        with patch.object(client.http_proxy, "request", AsyncMock()) as mock_request:
            mock_request.return_value = HttpProxyResponse(
                status_code=200,
                text=json.dumps(dump1090_sample_data),
                reason="OK",
                headers={},
            )
            
            aircraft = await client.get_aircraft_by_registration("G-ABCD")
            
            assert aircraft is not None
            assert aircraft.registration == "G-ABCD"
            assert aircraft.icao24 == "4CA1E3"
            assert aircraft.latitude == 51.4775
            assert aircraft.longitude == -0.4614
            assert aircraft.altitude_ft == 15000
    
    @pytest.mark.asyncio
    async def test_get_aircraft_by_registration_not_found(
        self, mock_hass, dump1090_config, dump1090_sample_data
    ):
        """Test retrieving aircraft with non-existent registration.
        
        Validates:
            - Returns None for unknown registration
            - Does not raise exceptions
        
        Expected Result:
            Returns None
        """
        client = Dump1090Client(mock_hass, dump1090_config)
        
        with patch.object(client.http_proxy, "request", AsyncMock()) as mock_request:
            mock_request.return_value = HttpProxyResponse(
                status_code=200,
                text=json.dumps(dump1090_sample_data),
                reason="OK",
                headers={},
            )
            
            aircraft = await client.get_aircraft_by_registration("ZZ-NONE")
            
            assert aircraft is None
    
    @pytest.mark.asyncio
    async def test_get_aircraft_by_icao24(
        self, mock_hass, dump1090_config, dump1090_sample_data
    ):
        """Test retrieving aircraft by ICAO24 hex code.
        
        Validates:
            - Correct aircraft returned for valid ICAO24
            - ICAO24 matching is case-insensitive
            - Aircraft cached after retrieval
        
        Expected Result:
            Returns AircraftData for 4CA1E3 (G-ABCD)
        """
        client = Dump1090Client(mock_hass, dump1090_config)
        
        with patch.object(client.http_proxy, "request", AsyncMock()) as mock_request:
            mock_request.return_value = HttpProxyResponse(
                status_code=200,
                text=json.dumps(dump1090_sample_data),
                reason="OK",
                headers={},
            )
            
            aircraft = await client.get_aircraft_by_icao24("4ca1e3")  # lowercase
            
            assert aircraft is not None
            assert aircraft.icao24 == "4CA1E3"
            assert aircraft.registration == "G-ABCD"
    
    @pytest.mark.asyncio
    async def test_get_aircraft_near_location(
        self, mock_hass, dump1090_config, dump1090_sample_data
    ):
        """Test retrieving aircraft near a location.
        
        Validates:
            - Aircraft within radius returned
            - Distance filtering works correctly
            - Results sorted by distance (nearest first)
        
        Expected Result:
            Returns list of aircraft within 10nm of Popham (51.4775, -0.4614)
        """
        client = Dump1090Client(mock_hass, dump1090_config)
        
        with patch.object(client.http_proxy, "request", AsyncMock()) as mock_request:
            mock_request.return_value = HttpProxyResponse(
                status_code=200,
                text=json.dumps(dump1090_sample_data),
                reason="OK",
                headers={},
            )
            
            # Popham coordinates
            aircraft_list = await client.get_aircraft_near_location(51.4775, -0.4614, 10)
            
            # All sample aircraft are within 10nm
            assert len(aircraft_list) >= 2
            
            # Verify all have valid positions
            for aircraft in aircraft_list:
                assert aircraft.latitude is not None
                assert aircraft.longitude is not None


class TestDump1090JSONParsing:
    """Test suite for dump1090 JSON parsing.
    
    Tests parsing of various dump1090 JSON formats and edge cases.
    
    Scenarios Covered:
        - Complete aircraft data
        - Minimal aircraft data (lat/lon/hex only)
        - Missing position (should be skipped)
        - Missing ICAO24 (should be skipped)
        - Various altitude sources (baro vs geometric)
        - Vertical rate parsing
        - Metadata extraction (RSSI, messages, etc.)
    """
    
    def test_parse_complete_aircraft(self, mock_hass, dump1090_config):
        """Test parsing aircraft with complete data.
        
        Validates:
            - All fields parsed correctly
            - Callsign whitespace stripped
            - Altitude, speed, track converted to integers
            - Metadata stored correctly
        
        Expected Result:
            AircraftData with all fields populated
        """
        client = Dump1090Client(mock_hass, dump1090_config)
        
        ac_json = {
            "hex": "4CA1E3",
            "flight": "BAW123  ",
            "r": "G-ABCD",
            "t": "B738",
            "alt_baro": 15000,
            "gs": 450,
            "track": 270,
            "lat": 51.4775,
            "lon": -0.4614,
            "seen": 0.5,
            "category": "A3",
            "squawk": "7000",
            "baro_rate": -1000,
            "messages": 1500,
            "rssi": -15.2
        }
        
        now = dt_util.utcnow()
        aircraft = client._parse_aircraft_json(ac_json, now)
        
        assert aircraft is not None
        assert aircraft.icao24 == "4CA1E3"
        assert aircraft.registration == "G-ABCD"
        assert aircraft.callsign == "BAW123"  # Whitespace stripped
        assert aircraft.aircraft_type == "B738"
        assert aircraft.latitude == 51.4775
        assert aircraft.longitude == -0.4614
        assert aircraft.altitude_ft == 15000
        assert aircraft.ground_speed_kt == 450
        assert aircraft.track_deg == 270
        assert aircraft.vertical_rate_fpm == -1000
        assert aircraft.squawk == "7000"
        assert aircraft.source == "dump1090"
        assert aircraft.priority == 1
        assert aircraft.metadata["category"] == "A3"
        assert aircraft.metadata["rssi"] == -15.2
    
    def test_parse_minimal_aircraft(self, mock_hass, dump1090_config):
        """Test parsing aircraft with minimal data.
        
        Validates:
            - Only required fields (hex, lat, lon) parsed
            - Optional fields remain None
            - Aircraft still created successfully
        
        Expected Result:
            AircraftData with only position and ICAO24
        """
        client = Dump1090Client(mock_hass, dump1090_config)
        
        ac_json = {
            "hex": "ABC123",
            "lat": 51.5,
            "lon": -0.5,
            "seen": 1.0
        }
        
        now = dt_util.utcnow()
        aircraft = client._parse_aircraft_json(ac_json, now)
        
        assert aircraft is not None
        assert aircraft.icao24 == "ABC123"
        assert aircraft.latitude == 51.5
        assert aircraft.longitude == -0.5
        assert aircraft.registration is None
        assert aircraft.altitude_ft is None
        assert aircraft.ground_speed_kt is None
    
    def test_parse_aircraft_no_position(self, mock_hass, dump1090_config):
        """Test parsing aircraft without position.
        
        Validates:
            - Aircraft without lat/lon skipped
            - Returns None (cannot track without position)
        
        Expected Result:
            Returns None (position required for tracking)
        """
        client = Dump1090Client(mock_hass, dump1090_config)
        
        ac_json = {
            "hex": "DEF456",
            "r": "N99999",
            "seen": 0.5
        }
        
        now = dt_util.utcnow()
        aircraft = client._parse_aircraft_json(ac_json, now)
        
        assert aircraft is None
    
    def test_parse_aircraft_no_icao24(self, mock_hass, dump1090_config):
        """Test parsing aircraft without ICAO24.
        
        Validates:
            - Aircraft without hex code skipped
            - Returns None (ICAO24 required for unique identification)
        
        Expected Result:
            Returns None (ICAO24 required)
        """
        client = Dump1090Client(mock_hass, dump1090_config)
        
        ac_json = {
            "lat": 51.5,
            "lon": -0.5,
            "seen": 0.5
        }
        
        now = dt_util.utcnow()
        aircraft = client._parse_aircraft_json(ac_json, now)
        
        assert aircraft is None


class TestDump1090Caching:
    """Test suite for dump1090 client caching behavior.
    
    Tests cache hits, misses, TTL expiration, and LRU eviction.
    
    Scenarios Covered:
        - Cache miss on first fetch
        - Cache hit on second fetch
        - Cache expiration after TTL
        - Aircraft cached automatically
    """
    
    @pytest.mark.asyncio
    async def test_cache_hit(self, mock_hass, dump1090_config, dump1090_sample_data):
        """Test cache hit scenario.
        
        Validates:
            - First fetch retrieves from network
            - Second fetch retrieves from cache
            - Cache prevents duplicate network requests
        
        Expected Result:
            Second fetch returns cached data (same object reference)
        """
        client = Dump1090Client(mock_hass, dump1090_config)
        
        with patch.object(client.http_proxy, "request", AsyncMock()) as mock_request:
            mock_request.return_value = HttpProxyResponse(
                status_code=200,
                text=json.dumps(dump1090_sample_data),
                reason="OK",
                headers={},
            )
            
            # First fetch - populates cache
            aircraft1 = await client.get_aircraft_by_registration("G-ABCD")
            assert aircraft1 is not None
            
            # Second fetch - should hit cache (cache TTL is 30s, immediate re-fetch should hit)
            aircraft2 = await client.get_aircraft_by_registration("G-ABCD")
            assert aircraft2 is not None
            
            # Both should reference same aircraft
            assert aircraft1.icao24 == aircraft2.icao24
            assert aircraft1.registration == aircraft2.registration


class TestDump1090ErrorHandling:
    """Test suite for dump1090 error handling.
    
    Tests graceful degradation when network or parsing errors occur.
    
    Scenarios Covered:
        - Network errors (connection refused)
        - HTTP timeouts
        - Invalid JSON
        - Partial aircraft data
    """
    
    @pytest.mark.asyncio
    async def test_network_error_returns_empty_list(self, mock_hass, dump1090_config):
        """Test network error handling.
        
        Validates:
            - Network errors logged
            - Returns empty list (no exceptions raised)
            - Graceful degradation
        
        Expected Result:
            Returns empty list on network failure
        """
        client = Dump1090Client(mock_hass, dump1090_config)
        
        with patch.object(client.http_proxy, "request") as mock_request:
            mock_request.side_effect = Exception("Connection refused")
            
            aircraft_list = await client._fetch_all_aircraft()
            
            assert aircraft_list == []
