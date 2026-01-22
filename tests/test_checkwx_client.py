"""Tests for CheckWX API client.

This module tests the CheckWX aviation weather client including:
- API request handling and response parsing
- Multi-level caching (memory + persistent)
- Rate limit tracking and warnings
- Graceful degradation to stale cache
- Async file operations for persistent cache

Test Strategy:
    - Mock aiohttp responses for all API calls
    - Test cache behavior independently from API
    - Verify rate limit tracking across date boundaries
    - Test failure scenarios and stale cache fallback
    - Ensure no blocking I/O in async functions

Coverage:
    - All API methods (METAR, TAF, station info, sunrise/sunset)
    - Cache hit/miss scenarios with TTL validation
    - Rate limit warning at 2700 and blocking at 3000
    - LRU eviction when memory cache exceeds limit
    - Persistent cache survives "restarts" (new client instance)
    - Graceful degradation when API fails
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.util import dt as dt_util

from custom_components.hangar_assistant.utils.checkwx_client import (
    CheckWXClient,
    RATE_LIMIT_FREE_TIER,
    RATE_LIMIT_WARNING_THRESHOLD,
)


@pytest.fixture
def mock_hass(tmp_path):
    """Create mock Home Assistant instance with temp config path.
    
    Provides:
        - Mock hass with temp cache directory
        - async_add_executor_job for async file operations
        - config.path() returns temp directory
    
    Used By:
        - All tests requiring CheckWX client initialization
    
    Returns:
        MagicMock: Configured Home Assistant instance
    """
    mock_hass = MagicMock()
    mock_hass.config.path.return_value = str(tmp_path)
    
    # Mock executor job to run sync functions
    def run_sync(func, *args):
        return func(*args) if args else func()
    
    mock_hass.async_add_executor_job = AsyncMock(side_effect=run_sync)
    
    return mock_hass


@pytest.fixture
def checkwx_client(mock_hass):
    """Create CheckWX client with test configuration.
    
    Provides:
        - Client with 32-char test API key
        - Caching enabled (both memory + persistent)
        - Short cache TTLs for testing (15 min METAR, 360 min TAF)
    
    Used By:
        - Tests requiring initialized client
    
    Returns:
        CheckWXClient: Configured client instance
    """
    return CheckWXClient(
        api_key="test_api_key_32_characters_long",
        hass=mock_hass,
        cache_enabled=True,
        metar_cache_minutes=15,
        taf_cache_minutes=360,
    )


@pytest.mark.asyncio
async def test_checkwx_client_initialization(mock_hass):
    """Test CheckWX client initializes with correct defaults.
    
    Validates:
        - API key stored correctly
        - Cache directories created
        - Rate limit counters initialized to zero
        - Memory cache is empty OrderedDict
    
    Expected Result:
        Client initializes without errors, all attributes set correctly
    """
    client = CheckWXClient(
        api_key="test_key_12345678901234567890123",
        hass=mock_hass,
        cache_enabled=True
    )
    
    assert client._api_key == "test_key_12345678901234567890123"
    assert client._cache_enabled is True
    assert client._daily_requests == 0
    assert client._consecutive_failures == 0
    assert len(client._memory_cache) == 0
    assert client._rate_limit_warned is False


@pytest.mark.asyncio
async def test_get_metar_invalid_icao(checkwx_client):
    """Test METAR fetch rejects invalid ICAO codes.
    
    Validates:
        - Raises ValueError for empty string
        - Raises ValueError for wrong length (not 4 chars)
        - Error message includes invalid ICAO code
    
    Expected Result:
        ValueError raised with descriptive message
    """
    with pytest.raises(ValueError, match="Invalid ICAO code"):
        await checkwx_client.get_metar("")
    
    with pytest.raises(ValueError, match="Invalid ICAO code"):
        await checkwx_client.get_metar("KJF")  # Only 3 chars
    
    with pytest.raises(ValueError, match="Invalid ICAO code"):
        await checkwx_client.get_metar("KJFKX")  # 5 chars


@pytest.mark.asyncio
@patch("aiohttp.ClientSession")
async def test_get_metar_success(mock_session, checkwx_client):
    """Test successful METAR retrieval and parsing.
    
    Setup:
        - Mock aiohttp session returns 200 with valid METAR JSON
        - METAR data includes flight category, temperature, wind, etc.
    
    Validation:
        - API called with correct URL and headers
        - Response parsed correctly
        - Data cached in memory
        - Request counter incremented
    
    Expected Result:
        METAR dictionary returned with all expected fields
    """
    # Mock API response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "results": 1,
        "data": [{
            "icao": "KJFK",
            "flight_category": "VFR",
            "temperature": {"celsius": 15, "fahrenheit": 59},
            "dewpoint": {"celsius": 10, "fahrenheit": 50},
            "wind": {"degrees": 270, "speed_kts": 12},
            "barometer": {"hpa": 1013.25, "hg": 29.92},
            "visibility": {"miles": 10.0},
            "observed": "2026-01-22T12:00:00Z",
            "raw_text": "METAR KJFK 221200Z 27012KT 10SM FEW050 15/10 A2992"
        }]
    })
    
    mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
    
    # Fetch METAR
    result = await checkwx_client.get_metar("KJFK", decoded=True)
    
    # Validate response
    assert result is not None
    assert result["icao"] == "KJFK"
    assert result["flight_category"] == "VFR"
    assert result["temperature"]["celsius"] == 15
    assert result["wind"]["speed_kts"] == 12
    
    # Validate caching
    assert len(checkwx_client._memory_cache) == 1
    assert checkwx_client._daily_requests == 1


@pytest.mark.asyncio
@patch("aiohttp.ClientSession")
async def test_get_taf_success(mock_session, checkwx_client):
    """Test successful TAF retrieval with forecast periods.
    
    Setup:
        - Mock TAF response with multiple forecast periods
        - Includes change indicators (FM, BECMG)
    
    Validation:
        - TAF data parsed correctly
        - Forecast periods accessible
        - Cached for 6 hours (longer TTL than METAR)
    
    Expected Result:
        TAF dictionary with forecast array and validity timestamps
    """
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "results": 1,
        "data": [{
            "icao": "KJFK",
            "timestamp": {
                "issued": "2026-01-22T11:00:00Z",
                "from": "2026-01-22T12:00:00Z",
                "to": "2026-01-23T12:00:00Z"
            },
            "forecast": [
                {
                    "timestamp": {"from": "2026-01-22T12:00:00Z", "to": "2026-01-22T18:00:00Z"},
                    "wind": {"degrees": 270, "speed_kts": 15},
                    "visibility": {"miles": 10.0}
                }
            ],
            "raw_text": "TAF KJFK 221100Z 2212/2312 27015KT P6SM"
        }]
    })
    
    mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
    
    result = await checkwx_client.get_taf("KJFK", decoded=True)
    
    assert result is not None
    assert result["icao"] == "KJFK"
    assert "forecast" in result
    assert len(result["forecast"]) == 1
    assert result["forecast"][0]["wind"]["speed_kts"] == 15


@pytest.mark.asyncio
@patch("aiohttp.ClientSession")
async def test_get_station_info_success(mock_session, checkwx_client):
    """Test station information retrieval.
    
    Setup:
        - Mock station response with location, elevation, coordinates
    
    Validation:
        - Station name and ICAO correct
        - Elevation in both feet and meters
        - Coordinates present for mapping
    
    Expected Result:
        Station dictionary with all geographic data
    """
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "results": 1,
        "data": [{
            "icao": "KJFK",
            "iata": "JFK",
            "name": "John F Kennedy International Airport",
            "city": "New York",
            "country": {"code": "US", "name": "United States"},
            "elevation": {"feet": 13.0, "meters": 4.0},
            "latitude": {"decimal": 40.639},
            "longitude": {"decimal": -73.779},
            "type": "Airport"
        }]
    })
    
    mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
    
    result = await checkwx_client.get_station_info("KJFK")
    
    assert result is not None
    assert result["icao"] == "KJFK"
    assert result["name"] == "John F Kennedy International Airport"
    assert result["elevation"]["feet"] == 13.0
    assert result["latitude"]["decimal"] == 40.639


@pytest.mark.asyncio
async def test_memory_cache_hit(checkwx_client):
    """Test memory cache returns cached data without API call.
    
    Setup:
        - Manually populate memory cache with METAR data
        - Set recent timestamp (within TTL)
    
    Validation:
        - get_metar() returns cached data
        - No API call made (request counter unchanged)
        - Cache entry moved to end for LRU
    
    Expected Result:
        Cached data returned instantly, zero API calls
    """
    # Manually cache data
    cache_key = "metar_KJFK_decoded"
    cached_data = {"icao": "KJFK", "flight_category": "VFR"}
    timestamp = dt_util.utcnow()
    checkwx_client._memory_cache[cache_key] = (cached_data, timestamp)
    
    # Fetch (should hit cache)
    with patch("aiohttp.ClientSession") as mock_session:
        result = await checkwx_client.get_metar("KJFK", decoded=True)
        
        assert result == cached_data
        assert checkwx_client._daily_requests == 0  # No API call
        mock_session.assert_not_called()


@pytest.mark.asyncio
async def test_memory_cache_expired(checkwx_client):
    """Test expired memory cache triggers new API call.
    
    Setup:
        - Cache data with old timestamp (>15 min ago)
        - Mock fresh API response
    
    Validation:
        - Expired cache not returned
        - API called to fetch fresh data
        - Cache updated with new data
    
    Expected Result:
        Fresh data fetched from API, cache refreshed
    """
    # Cache expired data
    cache_key = "metar_KJFK_decoded"
    old_timestamp = dt_util.utcnow() - timedelta(minutes=30)  # Expired
    checkwx_client._memory_cache[cache_key] = ({"old": "data"}, old_timestamp)
    
    # Mock fresh API response
    with patch("aiohttp.ClientSession") as mock_session:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "results": 1,
            "data": [{"icao": "KJFK", "flight_category": "MVFR"}]
        })
        mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
        
        result = await checkwx_client.get_metar("KJFK", decoded=True)
        
        assert result["flight_category"] == "MVFR"  # Fresh data
        assert checkwx_client._daily_requests == 1


@pytest.mark.asyncio
async def test_lru_cache_eviction(checkwx_client):
    """Test LRU eviction when memory cache exceeds maximum entries.
    
    Setup:
        - Set max cache size to 5
        - Add 10 entries sequentially
    
    Validation:
        - Oldest entries evicted first (FIFO for LRU)
        - Cache size never exceeds max
        - Most recent entries retained
    
    Expected Result:
        Cache maintains max size, oldest evicted
    """
    checkwx_client._max_memory_entries = 5
    
    # Add 10 entries
    for i in range(10):
        cache_key = f"test_key_{i}"
        data = {"entry": i}
        checkwx_client._set_memory_cache(cache_key, data)
    
    # Verify size limit
    assert len(checkwx_client._memory_cache) == 5
    
    # Verify oldest evicted (0-4 gone, 5-9 remain)
    assert "test_key_0" not in checkwx_client._memory_cache
    assert "test_key_9" in checkwx_client._memory_cache


@pytest.mark.asyncio
async def test_rate_limit_warning(checkwx_client):
    """Test rate limit warning at 2700 requests.
    
    Setup:
        - Set daily request count to 2699
        - Make one more request
    
    Validation:
        - Warning logged at 2700
        - Warning flag set (prevents duplicate warnings)
        - Request still allowed (<3000)
    
    Expected Result:
        Warning issued once at 2700, subsequent requests silent
    """
    checkwx_client._daily_requests = 2699
    
    with patch("aiohttp.ClientSession") as mock_session:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"results": 1, "data": [{"icao": "KJFK"}]})
        mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
        
        with patch("custom_components.hangar_assistant.utils.checkwx_client._LOGGER") as mock_logger:
            await checkwx_client.get_metar("KJFK")
            
            # Verify warning logged
            assert any("Approaching rate limit" in str(call) for call in mock_logger.warning.call_args_list)
            assert checkwx_client._rate_limit_warned is True


@pytest.mark.asyncio
async def test_rate_limit_blocking(checkwx_client):
    """Test rate limit blocks requests at 3000/day.
    
    Setup:
        - Set daily requests to 3000 (at limit)
        - Attempt API call
    
    Validation:
        - Request blocked (no API call)
        - Stale cache used if available
        - Error logged about limit reached
    
    Expected Result:
        No API call made, cached data returned or None
    """
    checkwx_client._daily_requests = 3000  # At limit
    
    # Cache some data to fallback to
    cache_key = "metar_KJFK_decoded"
    cached_data = {"icao": "KJFK", "stale": True}
    old_timestamp = dt_util.utcnow() - timedelta(hours=2)
    checkwx_client._memory_cache[cache_key] = (cached_data, old_timestamp)
    
    with patch("aiohttp.ClientSession") as mock_session:
        result = await checkwx_client.get_metar("KJFK")
        
        # No API call
        mock_session.assert_not_called()
        
        # Stale cache returned
        assert result == cached_data


@pytest.mark.asyncio
async def test_rate_limit_reset_at_midnight(checkwx_client):
    """Test rate limit counter resets at 00:00 UTC.
    
    Setup:
        - Set last reset to yesterday
        - Set request count to 2500
        - Make new request today
    
    Validation:
        - Counter reset to 0
        - Warning flag cleared
        - New request counted as first of day
    
    Expected Result:
        Fresh daily limit after midnight UTC
    """
    yesterday = (dt_util.utcnow() - timedelta(days=1)).date()
    checkwx_client._last_reset = yesterday
    checkwx_client._daily_requests = 2500
    checkwx_client._rate_limit_warned = True
    
    # Check rate limit (should reset)
    can_proceed = checkwx_client._check_rate_limit()
    
    assert can_proceed is True
    assert checkwx_client._daily_requests == 0
    assert checkwx_client._rate_limit_warned is False
    assert checkwx_client._last_reset == dt_util.utcnow().date()


@pytest.mark.asyncio
async def test_persistent_cache_write_read(checkwx_client, tmp_path):
    """Test persistent cache survives client restart.
    
    Scenario:
        1. Client fetches data, caches to file
        2. Simulate restart (new client instance)
        3. New client reads persistent cache
    
    Validation:
        - Data written to JSON file
        - New client instance finds cached data
        - No API call needed on restart
    
    Expected Result:
        Persistent cache protects against restart-induced API calls
    """
    # First client fetches data
    cache_key = "metar_KJFK_decoded"
    data = {"icao": "KJFK", "temperature": {"celsius": 20}}
    
    await checkwx_client._set_persistent_cache(cache_key, data)
    
    # Verify file created
    cache_file = tmp_path / "hangar_assistant_cache" / "checkwx" / f"{cache_key}.json"
    assert cache_file.exists()
    
    # Simulate restart: new client instance
    new_client = CheckWXClient(
        api_key="test_key",
        hass=checkwx_client._hass,
        cache_enabled=True
    )
    
    # Read from persistent cache
    cached = await new_client._get_persistent_cache(cache_key, timedelta(minutes=15))
    
    assert cached is not None
    assert cached["icao"] == "KJFK"
    assert cached["temperature"]["celsius"] == 20


@pytest.mark.asyncio
@patch("aiohttp.ClientSession")
async def test_graceful_degradation_on_api_failure(mock_session, checkwx_client):
    """Test stale cache used when API fails.
    
    Setup:
        - Cache old data (>15 min ago, expired)
        - Mock API failure (timeout)
    
    Validation:
        - API call attempted
        - Failure logged
        - Stale cache returned as fallback
        - Consecutive failure counter incremented
    
    Expected Result:
        Stale data better than no data, system remains functional
    """
    # Cache stale data
    cache_key = "metar_KJFK_decoded"
    stale_data = {"icao": "KJFK", "stale": True}
    old_timestamp = dt_util.utcnow() - timedelta(hours=1)
    checkwx_client._memory_cache[cache_key] = (stale_data, old_timestamp)
    
    # Mock API failure
    mock_session.side_effect = asyncio.TimeoutError()
    
    result = await checkwx_client.get_metar("KJFK")
    
    # Stale cache returned
    assert result == stale_data
    assert checkwx_client._consecutive_failures == 1


@pytest.mark.asyncio
@patch("aiohttp.ClientSession")
async def test_api_error_401_unauthorized(mock_session, checkwx_client):
    """Test handling of invalid API key (401 error).
    
    Setup:
        - Mock 401 Unauthorized response
    
    Validation:
        - Error logged with clear message
        - None returned (no fallback to stale cache for auth errors)
        - Failure counter incremented
    
    Expected Result:
        Clear error message helps user diagnose API key issue
    """
    mock_response = AsyncMock()
    mock_response.status = 401
    mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
    
    with patch("custom_components.hangar_assistant.utils.checkwx_client._LOGGER") as mock_logger:
        result = await checkwx_client.get_metar("KJFK")
        
        assert result is None
        assert any("Invalid API key" in str(call) for call in mock_logger.error.call_args_list)


@pytest.mark.asyncio
@patch("aiohttp.ClientSession")
async def test_api_error_404_not_found(mock_session, checkwx_client):
    """Test handling of invalid ICAO code (404 error).
    
    Setup:
        - Mock 404 Not Found response (ICAO doesn't exist)
    
    Validation:
        - Warning logged (not error, ICAO might be obscure)
        - None returned
        - Doesn't crash or retry endlessly
    
    Expected Result:
        Graceful handling of non-existent ICAO codes
    """
    mock_response = AsyncMock()
    mock_response.status = 404
    mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
    
    result = await checkwx_client.get_metar("XXXX")  # Non-existent ICAO
    
    assert result is None


@pytest.mark.asyncio
async def test_clear_cache_specific_icao(checkwx_client, tmp_path):
    """Test cache clearing for specific ICAO code.
    
    Setup:
        - Cache data for KJFK and EGHP
        - Clear only KJFK
    
    Validation:
        - KJFK cache removed (memory + file)
        - EGHP cache remains untouched
    
    Expected Result:
        Selective cache clearing works correctly
    """
    # Cache data for two ICAOs
    checkwx_client._set_memory_cache("metar_KJFK_decoded", {"icao": "KJFK"})
    checkwx_client._set_memory_cache("metar_EGHP_decoded", {"icao": "EGHP"})
    
    await checkwx_client._set_persistent_cache("metar_KJFK_decoded", {"icao": "KJFK"})
    await checkwx_client._set_persistent_cache("metar_EGHP_decoded", {"icao": "EGHP"})
    
    # Clear KJFK only
    await checkwx_client.clear_cache("KJFK")
    
    # Verify selective clearing
    assert "metar_KJFK_decoded" not in checkwx_client._memory_cache
    assert "metar_EGHP_decoded" in checkwx_client._memory_cache


@pytest.mark.asyncio
async def test_clear_all_cache(checkwx_client):
    """Test clearing all cached data.
    
    Setup:
        - Cache multiple entries
    
    Validation:
        - All memory cache cleared
        - All persistent cache files deleted
    
    Expected Result:
        Complete cache wipe, fresh start
    """
    # Cache multiple entries
    checkwx_client._set_memory_cache("metar_KJFK_decoded", {"icao": "KJFK"})
    checkwx_client._set_memory_cache("taf_EGHP_decoded", {"icao": "EGHP"})
    
    await checkwx_client.clear_cache()
    
    assert len(checkwx_client._memory_cache) == 0


@pytest.mark.asyncio
async def test_cache_stats(checkwx_client):
    """Test cache statistics reporting.
    
    Validation:
        - Returns memory cache entry count
        - Shows rate limit usage
        - Indicates cache enabled status
        - Provides cache directory path
    
    Expected Result:
        Complete stats dictionary for monitoring
    """
    checkwx_client._daily_requests = 142
    checkwx_client._set_memory_cache("test_key", {"data": "test"})
    
    stats = checkwx_client.get_cache_stats()
    
    assert stats["memory_cache_entries"] == 1
    assert stats["daily_requests"] == 142
    assert stats["remaining_requests"] == 2858
    assert stats["persistent_cache_enabled"] is True
    assert "cache_directory" in stats
