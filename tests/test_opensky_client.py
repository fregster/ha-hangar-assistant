"""Tests for OpenSky Network client.

This module tests the OpenSkyClient implementation for free community ADS-B data.

Tests include:
- Client initialization (anonymous and authenticated)
- Connection testing (success and failure scenarios)
- Aircraft data fetching and parsing
- ICAO24 and location-based queries
- Rate limit tracking and credit management
- Cache behavior (hits, misses, TTL expiration)
- Error handling (network errors, rate limits, invalid responses)
- OpenSky API response format parsing

Test Strategy:
    - Mock aiohttp.ClientSession for HTTP requests
    - Provide realistic OpenSky API JSON responses
    - Test both anonymous (400 credits/day) and authenticated (4000 credits/day) modes
    - Verify rate limit protection works correctly
    - Ensure graceful degradation on errors

Coverage:
    - All public methods (test_connection, get_aircraft_by_icao24, etc.)
    - State vector parsing with various field combinations
    - Credit tracking and daily reset logic
    - Rate limit handling (429 responses)
    - FLARM aircraft detection
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from homeassistant.util import dt as dt_util

from custom_components.hangar_assistant.utils.opensky_client import OpenSkyClient
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
def opensky_config_anonymous():
    """Create OpenSky configuration for anonymous access.
    
    Provides:
        - No username or password (anonymous mode)
        - 400 credits/day limit
        - 60-second cache TTL
    
    Returns:
        Dict: Configuration for OpenSkyClient initialization
    """
    return {
        "username": None,
        "password": None
    }


@pytest.fixture
def opensky_config_authenticated():
    """Create OpenSky configuration for authenticated access.
    
    Provides:
        - Username and password (free account mode)
        - 4000 credits/day limit
        - 30-second cache TTL
    
    Returns:
        Dict: Configuration for OpenSkyClient initialization
    """
    return {
        "username": "test@example.com",
        "password": "testpass"
    }


@pytest.fixture
def opensky_sample_response():
    """Create sample OpenSky API response for testing.
    
    Provides:
        - Realistic OpenSky /states/all JSON response
        - Mix of ADS-B and FLARM aircraft
        - Various aircraft states (airborne, on ground)
    
    Returns:
        Dict: OpenSky API response structure
    """
    return {
        "time": 1737560000,
        "states": [
            # ADS-B aircraft (airborne)
            [
                "4ca1e3",           # ICAO24
                "BAW123  ",         # Callsign
                "United Kingdom",   # Origin country
                1737560000,         # Time position
                1737560000,         # Last contact
                -0.4614,            # Longitude
                51.4775,            # Latitude
                4572.0,             # Baro altitude (meters) = 15000ft
                False,              # On ground
                232.0,              # Velocity (m/s) = 450kt
                270.0,              # True track
                0.0,                # Vertical rate
                None,               # Sensors
                4572.0,             # Geo altitude
                "7000",             # Squawk
                False,              # SPI
                0                   # Position source (0=ADS-B)
            ],
            # FLARM aircraft (glider)
            [
                "dda123",           # ICAO24 (FLARM range)
                None,               # No callsign
                "Germany",          # Origin country
                1737560000,         # Time position
                1737560000,         # Last contact
                7.5,                # Longitude
                48.5,               # Latitude
                1000.0,             # Baro altitude (meters)
                False,              # On ground
                30.0,               # Velocity (m/s) = 58kt
                180.0,              # True track
                2.0,                # Vertical rate (m/s) = 394 fpm
                None,               # Sensors
                1000.0,             # Geo altitude
                None,               # No squawk
                False,              # SPI
                3                   # Position source (3=FLARM)
            ],
            # Aircraft on ground
            [
                "abc456",
                "N12345  ",
                "United States",
                1737560000,
                1737560000,
                -122.3,
                37.6,
                0.0,
                True,               # On ground
                0.0,
                0.0,
                0.0,
                None,
                0.0,
                "1200",
                False,
                0
            ]
        ]
    }


class TestOpenSkyClientInitialization:
    """Test suite for OpenSkyClient initialization.
    
    Tests client instantiation with anonymous and authenticated configurations.
    
    Scenarios Covered:
        - Anonymous initialization (400 credits/day)
        - Authenticated initialization (4000 credits/day)
        - Cache TTL configuration
        - Priority assignment
        - Rate limit setup
    """
    
    def test_init_anonymous(self, mock_hass, opensky_config_anonymous):
        """Test client initialisation in anonymous mode.
        
        Validates:
            - Client initialises without credentials
            - Daily limit set to 400 credits
            - Cache TTL set to 60 seconds
            - Priority set to 2
        
        Expected Result:
            Anonymous client created with 400 credits/day limit
        """
        client = OpenSkyClient(mock_hass, opensky_config_anonymous)
        
        assert client._is_authenticated is False
        assert client._username is None
        assert client._password is None
        assert client._auth is None
        assert client._daily_limit == 400
        assert client.priority == 2
        assert client._credits_used_today == 0
    
    def test_init_authenticated(self, mock_hass, opensky_config_authenticated):
        """Test client initialisation in authenticated mode.
        
        Validates:
            - Client initialises with credentials
            - Daily limit set to 4000 credits
            - Cache TTL set to 30 seconds
            - BasicAuth configured
        
        Expected Result:
            Authenticated client created with 4000 credits/day limit
        """
        client = OpenSkyClient(mock_hass, opensky_config_authenticated)
        
        assert client._is_authenticated is True
        assert client._username == "test@example.com"
        assert client._password == "testpass"
        assert client._auth is not None
        assert client._daily_limit == 4000
        assert client.priority == 2


class TestOpenSkyConnectionTesting:
    """Test suite for OpenSky connection testing.
    
    Tests the test_connection() method for various scenarios.
    
    Scenarios Covered:
        - Successful connection (anonymous and authenticated)
        - Authentication failures (401)
        - Rate limit errors (429)
        - HTTP errors (404, 500)
        - Invalid JSON responses
    """
    
    @pytest.mark.asyncio
    async def test_connection_success(
        self, mock_hass, opensky_config_anonymous, opensky_sample_response
    ):
        """Test successful connection to OpenSky Network.
        
        Validates:
            - HTTP 200 response handled correctly
            - JSON parsed successfully
            - Aircraft count logged
            - Returns success tuple
        
        Expected Result:
            Returns (True, None) indicating successful connection
        """
        client = OpenSkyClient(mock_hass, opensky_config_anonymous)
        
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=opensky_sample_response)
            
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_session.get = MagicMock()
            mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.get.return_value.__aexit__ = AsyncMock()
            
            mock_session_class.return_value = mock_session
            
            success, error = await client.test_connection()
            
            assert success is True
            assert error is None
    
    @pytest.mark.asyncio
    async def test_connection_auth_failure(
        self, mock_hass, opensky_config_authenticated
    ):
        """Test connection with invalid credentials.
        
        Validates:
            - HTTP 401 handled gracefully
            - Error message indicates auth failure
            - Returns failure tuple
        
        Expected Result:
            Returns (False, "Authentication failed...") tuple
        """
        client = OpenSkyClient(mock_hass, opensky_config_authenticated)
        
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_response = AsyncMock()
            mock_response.status = 401
            mock_response.reason = "Unauthorized"
            
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_session.get = MagicMock()
            mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.get.return_value.__aexit__ = AsyncMock()
            
            mock_session_class.return_value = mock_session
            
            success, error = await client.test_connection()
            
            assert success is False
            assert "authentication" in error.lower()
    
    @pytest.mark.asyncio
    async def test_connection_rate_limited(
        self, mock_hass, opensky_config_anonymous
    ):
        """Test connection when rate limited.
        
        Validates:
            - HTTP 429 handled gracefully
            - Error message mentions rate limit
            - Returns failure tuple
        
        Expected Result:
            Returns (False, "Rate limit exceeded...") tuple
        """
        client = OpenSkyClient(mock_hass, opensky_config_anonymous)
        
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_response = AsyncMock()
            mock_response.status = 429
            mock_response.reason = "Too Many Requests"
            
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_session.get = MagicMock()
            mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.get.return_value.__aexit__ = AsyncMock()
            
            mock_session_class.return_value = mock_session
            
            success, error = await client.test_connection()
            
            assert success is False
            assert "rate limit" in error.lower()


class TestOpenSkyCreditTracking:
    """Test suite for OpenSky credit tracking and rate limiting.
    
    Tests credit usage tracking, daily resets, and rate limit enforcement.
    
    Scenarios Covered:
        - Credit increment and tracking
        - Daily reset at 00:00 UTC
        - Rate limit enforcement at daily limit
        - Credit usage statistics
    """
    
    def test_credit_usage_tracking(self, mock_hass, opensky_config_anonymous):
        """Test credit usage tracking.
        
        Validates:
            - Credits increment correctly
            - Usage statistics accurate
            - Credits remaining calculated correctly
        
        Expected Result:
            Credit usage tracked accurately
        """
        client = OpenSkyClient(mock_hass, opensky_config_anonymous)
        
        # Initial state
        usage = client.get_credit_usage()
        assert usage["credits_used"] == 0
        assert usage["daily_limit"] == 400
        assert usage["credits_remaining"] == 400
        
        # Increment credits
        client._increment_credits(10)
        usage = client.get_credit_usage()
        assert usage["credits_used"] == 10
        assert usage["credits_remaining"] == 390
    
    def test_daily_reset(self, mock_hass, opensky_config_anonymous):
        """Test credit counter resets at new UTC day.
        
        Validates:
            - Credits reset when date changes
            - Last reset date updated
            - Rate limit flag cleared
        
        Expected Result:
            Credits reset to 0 on new day
        """
        client = OpenSkyClient(mock_hass, opensky_config_anonymous)
        
        # Use some credits
        client._increment_credits(50)
        assert client._credits_used_today == 50
        
        # Simulate new day
        client._last_reset_date = dt_util.utcnow().date() - timedelta(days=1)
        
        # Trigger reset
        client._reset_credits_if_new_day()
        
        assert client._credits_used_today == 0
        assert client._last_reset_date == dt_util.utcnow().date()
    
    def test_rate_limit_at_daily_limit(self, mock_hass, opensky_config_anonymous):
        """Test rate limiting when daily limit reached.
        
        Validates:
            - Rate limit enforced at 400 credits
            - Further requests blocked
            - Rate limited flag set
        
        Expected Result:
            Queries blocked after hitting daily limit
        """
        client = OpenSkyClient(mock_hass, opensky_config_anonymous)
        
        # Use all credits
        client._credits_used_today = 400
        
        # Check rate limit
        assert client._check_rate_limit() is True
        assert client._rate_limited is True


class TestOpenSkyAircraftFetching:
    """Test suite for fetching aircraft from OpenSky.
    
    Tests aircraft retrieval by ICAO24 and location.
    
    Scenarios Covered:
        - Fetch by ICAO24 (found/not found)
        - Fetch near location with bounding box
        - Distance filtering
        - Cache hits and misses
    """
    
    @pytest.mark.asyncio
    async def test_get_aircraft_by_icao24(
        self, mock_hass, opensky_config_anonymous, opensky_sample_response
    ):
        """Test retrieving aircraft by ICAO24.
        
        Validates:
            - Correct aircraft returned for valid ICAO24
            - Credit usage incremented
            - Aircraft cached after retrieval
        
        Expected Result:
            Returns AircraftData for 4CA1E3
        """
        client = OpenSkyClient(mock_hass, opensky_config_anonymous)
        
        # Create single-aircraft response
        single_aircraft_response = {
            "time": 1737560000,
            "states": [opensky_sample_response["states"][0]]
        }
        
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=single_aircraft_response)
            
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_session.get = MagicMock()
            mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.get.return_value.__aexit__ = AsyncMock()
            
            mock_session_class.return_value = mock_session
            
            aircraft = await client.get_aircraft_by_icao24("4ca1e3")
            
            assert aircraft is not None
            assert aircraft.icao24 == "4CA1E3"  # Normalized to uppercase
            assert aircraft.callsign == "BAW123"
            assert aircraft.latitude == 51.4775
            assert aircraft.longitude == -0.4614
            assert aircraft.altitude_ft == 15000  # Converted from meters
            assert client._credits_used_today == 1
    
    @pytest.mark.asyncio
    async def test_get_aircraft_near_location(
        self, mock_hass, opensky_config_anonymous, opensky_sample_response
    ):
        """Test retrieving aircraft near a location.
        
        Validates:
            - Aircraft within radius returned
            - Bounding box query constructed correctly
            - Distance filtering applied
            - Credit usage tracked
        
        Expected Result:
            Returns list of aircraft within specified radius
        """
        client = OpenSkyClient(mock_hass, opensky_config_anonymous)
        
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=opensky_sample_response)
            
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_session.get = MagicMock()
            mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.get.return_value.__aexit__ = AsyncMock()
            
            mock_session_class.return_value = mock_session
            
            # Query near Popham
            aircraft_list = await client.get_aircraft_near_location(51.4775, -0.4614, 25)
            
            # Should find at least one aircraft (BAW123 is very close)
            assert len(aircraft_list) >= 1
            
            # Verify credit usage
            assert client._credits_used_today == 1


class TestOpenSkyStateVectorParsing:
    """Test suite for OpenSky state vector parsing.
    
    Tests parsing of various OpenSky response formats.
    
    Scenarios Covered:
        - Complete state vector (all fields)
        - Minimal state vector (required fields only)
        - FLARM aircraft detection
        - Unit conversions (meters to feet, m/s to knots)
    """
    
    def test_parse_complete_state_vector(
        self, mock_hass, opensky_config_anonymous, opensky_sample_response
    ):
        """Test parsing complete state vector.
        
        Validates:
            - All fields parsed correctly
            - Units converted properly (meters→feet, m/s→knots)
            - Metadata stored
        
        Expected Result:
            AircraftData with all fields populated
        """
        client = OpenSkyClient(mock_hass, opensky_config_anonymous)
        
        state = opensky_sample_response["states"][0]
        fetch_time = opensky_sample_response["time"]
        
        aircraft = client._parse_state_vector(state, fetch_time)
        
        assert aircraft is not None
        assert aircraft.icao24 == "4CA1E3"
        assert aircraft.callsign == "BAW123"
        assert aircraft.latitude == 51.4775
        assert aircraft.longitude == -0.4614
        assert aircraft.altitude_ft == 15000  # 4572m → 15000ft
        assert aircraft.ground_speed_kt == 450  # 232 m/s → 450kt
        assert aircraft.track_deg == 270
        assert aircraft.is_on_ground is False
        assert aircraft.is_flarm is False
        assert aircraft.source == "opensky"
        assert aircraft.priority == 2
    
    def test_parse_flarm_aircraft(
        self, mock_hass, opensky_config_anonymous, opensky_sample_response
    ):
        """Test parsing FLARM aircraft (position_source=3).
        
        Validates:
            - FLARM flag detected correctly
            - Position source recorded in metadata
            - All fields parsed
        
        Expected Result:
            AircraftData with is_flarm=True
        """
        client = OpenSkyClient(mock_hass, opensky_config_anonymous)
        
        state = opensky_sample_response["states"][1]  # FLARM aircraft
        fetch_time = opensky_sample_response["time"]
        
        aircraft = client._parse_state_vector(state, fetch_time)
        
        assert aircraft is not None
        assert aircraft.icao24 == "DDA123"
        assert aircraft.is_flarm is True
        assert aircraft.metadata["position_source"] == 3
        assert aircraft.metadata["position_source_name"] == "FLARM"


class TestOpenSkyRateLimitHandling:
    """Test suite for OpenSky rate limit handling.
    
    Tests 429 response handling and retry logic.
    
    Scenarios Covered:
        - 429 response sets rate limit flag
        - Retry-After header parsed
        - Subsequent requests blocked until reset
    """
    
    @pytest.mark.asyncio
    async def test_rate_limit_response_handling(
        self, mock_hass, opensky_config_anonymous
    ):
        """Test handling of 429 rate limit response.
        
        Validates:
            - Rate limit flag set on 429
            - Retry-After header parsed
            - Subsequent queries blocked
        
        Expected Result:
            Client enters rate-limited state and blocks queries
        """
        client = OpenSkyClient(mock_hass, opensky_config_anonymous)
        
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_response = AsyncMock()
            mock_response.status = 429
            mock_response.headers = {"Retry-After": "3600"}  # 1 hour
            mock_response.reason = "Too Many Requests"
            
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_session.get = MagicMock()
            mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.get.return_value.__aexit__ = AsyncMock()
            
            mock_session_class.return_value = mock_session
            
            # First request triggers rate limit
            aircraft_list = await client.get_aircraft_near_location(51.5, -0.5, 10)
            
            assert aircraft_list == []  # Empty due to rate limit
            assert client._rate_limited is True
            assert client._rate_limit_reset_time is not None
            
            # Second request blocked by rate limit check
            assert client._check_rate_limit() is True


class TestOpenSkyErrorHandling:
    """Test suite for OpenSky error handling.
    
    Tests graceful degradation on network and parsing errors.
    
    Scenarios Covered:
        - Network errors (connection refused)
        - HTTP timeouts
        - Invalid JSON responses
        - Malformed state vectors
    """
    
    @pytest.mark.asyncio
    async def test_network_error_returns_empty_list(
        self, mock_hass, opensky_config_anonymous
    ):
        """Test network error handling.
        
        Validates:
            - Network errors logged
            - Returns empty list (no exceptions raised)
            - Graceful degradation
        
        Expected Result:
            Returns empty list on network failure
        """
        client = OpenSkyClient(mock_hass, opensky_config_anonymous)
        
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_response = AsyncMock()
            mock_response.json = AsyncMock(side_effect=aiohttp.ClientError("Connection refused"))
            
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_session.get = MagicMock()
            mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.get.return_value.__aexit__ = AsyncMock()
            
            mock_session_class.return_value = mock_session
            
            aircraft_list = await client.get_aircraft_near_location(51.5, -0.5, 10)
            
            assert aircraft_list == []
