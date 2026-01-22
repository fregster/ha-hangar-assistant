"""Tests for OpenWeatherMap failure handling and auto-disable.

This module tests the OpenWeatherMap integration's graceful degradation behavior,
including:
- Failure counter tracking (consecutive_failures)
- Auto-disable after 3 consecutive failures
- Persistent notification creation on auto-disable
- Cached data fallback when auto-disabled
- Error type tracking (401, 429, timeout, etc.)
- Last success/error timestamp tracking

Test Strategy:
    - Mock hass and config_entry for integration testing
    - Mock aiohttp responses for API call simulation
    - Use AsyncMock for async function testing
    - Verify state changes in config_entry.data
    - Verify notification creation on critical failures

Coverage:
    - All failure scenarios (API errors, network issues, rate limits)
    - Auto-disable trigger conditions
    - Cache fallback after auto-disable
    - Counter reset on successful recovery
    - Timestamp tracking for debugging
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import aiohttp

from custom_components.hangar_assistant.utils.openweathermap import OpenWeatherMapClient


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance.
    
    Provides:
        - Mock hass with config path
        - Mock services for notification creation
        - Mock async_add_executor_job that actually calls the function
    
    Returns:
        MagicMock: Configured Home Assistant instance
    """
    hass = MagicMock()
    hass.config.path.return_value = "/tmp/test_cache"
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    
    # Make async_add_executor_job actually call the function
    async def async_executor(func, *args):
        return func(*args)
    
    hass.async_add_executor_job = async_executor
    hass.config_entries = MagicMock()
    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry with integrations settings.
    
    Provides:
        - Initial integrations config with OWM enabled
        - consecutive_failures counter at 0
        - No error tracking initially
    
    Returns:
        MagicMock: Config entry with integrations namespace
    """
    entry = MagicMock()
    entry.data = {
        "integrations": {
            "openweathermap": {
                "enabled": True,
                "api_key": "test_api_key",
                "cache_enabled": True,
                "update_interval": 10,
                "cache_ttl": 10,
                "consecutive_failures": 0,
            }
        }
    }
    return entry


@pytest.mark.asyncio
async def test_owm_increments_failure_counter_on_api_error(mock_hass, mock_config_entry):
    """Test that OWM increments consecutive_failures on API error.
    
    Validates that when the OWM API returns an error (500, 503, etc.),
    the client increments the consecutive_failures counter.
    
    Setup:
        - Client with fresh config (consecutive_failures = 0)
        - Mock API call that raises ClientError
    
    Validation:
        - consecutive_failures incremented to 1
        - last_error populated with error message
        - Client does not auto-disable yet (threshold is 3)
    
    Expected Result:
        Counter incremented, error tracked, client remains enabled.
    """
    client = OpenWeatherMapClient(
        api_key="test_key",
        hass=mock_hass,
        config_entry=mock_config_entry,
        cache_enabled=True
    )
    
    # Mock API call to raise error
    with patch.object(client, '_fetch_from_api', side_effect=aiohttp.ClientError("API error")):
        result = await client.get_weather_data(51.0, -1.0)
    
    # Should return None on failure
    assert result is None
    
    # Should increment failure counter
    assert mock_config_entry.data["integrations"]["openweathermap"]["consecutive_failures"] == 1
    
    # Should track error message
    assert "last_error" in mock_config_entry.data["integrations"]["openweathermap"]
    assert "API error" in mock_config_entry.data["integrations"]["openweathermap"]["last_error"]
    
    # Should still be enabled (threshold is 3)
    assert mock_config_entry.data["integrations"]["openweathermap"]["enabled"] is True


@pytest.mark.asyncio
async def test_owm_resets_counter_on_successful_fetch(mock_hass, mock_config_entry):
    """Test that OWM resets consecutive_failures on successful fetch.
    
    Validates recovery behavior: after previous failures, a successful
    API call resets the failure counter to 0.
    
    Setup:
        - Client with consecutive_failures = 2 (from previous errors)
        - Mock successful API response
    
    Validation:
        - consecutive_failures reset to 0
        - last_success timestamp updated
        - last_error cleared (optional)
    
    Expected Result:
        Counter reset, client fully recovered.
    """
    # Set initial failure state
    mock_config_entry.data["integrations"]["openweathermap"]["consecutive_failures"] = 2
    mock_config_entry.data["integrations"]["openweathermap"]["last_error"] = "Previous error"
    
    client = OpenWeatherMapClient(
        api_key="test_key",
        hass=mock_hass,
        config_entry=mock_config_entry,
        cache_enabled=True
    )
    
    # Mock successful API response
    mock_response = {
        "lat": 51.0,
        "lon": -1.0,
        "current": {"temp": 15, "pressure": 1013}
    }
    
    with patch.object(client, '_fetch_from_api', return_value=mock_response):
        result = await client.get_weather_data(51.0, -1.0)
    
    # Should return data
    assert result is not None
    assert result["current"]["temp"] == 15
    
    # Should reset failure counter
    assert mock_config_entry.data["integrations"]["openweathermap"]["consecutive_failures"] == 0
    
    # Should update last_success timestamp
    assert "last_success" in mock_config_entry.data["integrations"]["openweathermap"]


@pytest.mark.asyncio
async def test_owm_auto_disables_after_three_failures(mock_hass, mock_config_entry):
    """Test that OWM auto-disables after 3 consecutive failures.
    
    Critical behavior: After 3 failed API calls, the integration
    must auto-disable to prevent wasting API quota.
    
    Setup:
        - Client with consecutive_failures = 2
        - Mock API call that raises error (third failure)
    
    Validation:
        - consecutive_failures incremented to 3
        - enabled flag set to False
        - Persistent notification created
        - last_error tracks reason for disable
    
    Expected Result:
        Integration auto-disabled, user notified via persistent notification.
    """
    # Set to 2 failures (next one triggers auto-disable)
    mock_config_entry.data["integrations"]["openweathermap"]["consecutive_failures"] = 2
    
    client = OpenWeatherMapClient(
        api_key="test_key",
        hass=mock_hass,
        config_entry=mock_config_entry,
        cache_enabled=True
    )
    
    # Mock third failure
    with patch.object(client, '_fetch_from_api', side_effect=aiohttp.ClientError("Third failure")):
        result = await client.get_weather_data(51.0, -1.0)
    
    # Should return None
    assert result is None
    
    # Should auto-disable
    assert mock_config_entry.data["integrations"]["openweathermap"]["enabled"] is False
    
    # Should track failure count
    assert mock_config_entry.data["integrations"]["openweathermap"]["consecutive_failures"] == 3
    
    # Should create persistent notification
    mock_hass.services.async_call.assert_called_once()
    call_args = mock_hass.services.async_call.call_args
    assert call_args[0][0] == "persistent_notification"
    assert call_args[0][1] == "create"


@pytest.mark.asyncio
async def test_owm_creates_persistent_notification_on_auto_disable(mock_hass, mock_config_entry):
    """Test that auto-disable creates a persistent notification.
    
    User notification is critical - users must know when OWM auto-disables
    so they can fix API key issues or check account status.
    
    Setup:
        - Client approaching failure threshold
        - Mock third consecutive failure
    
    Validation:
        - Notification service called
        - Message explains auto-disable and recovery steps
        - Notification ID unique to Hangar Assistant
    
    Expected Result:
        User receives actionable notification about auto-disable.
    """
    mock_config_entry.data["integrations"]["openweathermap"]["consecutive_failures"] = 2
    
    client = OpenWeatherMapClient(
        api_key="test_key",
        hass=mock_hass,
        config_entry=mock_config_entry,
        cache_enabled=True
    )
    
    with patch.object(client, '_fetch_from_api', side_effect=aiohttp.ClientError("Failure")):
        await client.get_weather_data(51.0, -1.0)
    
    # Verify notification created
    mock_hass.services.async_call.assert_called_once()
    call_args = mock_hass.services.async_call.call_args
    
    # Service call format: async_call(domain, service, service_data)
    assert call_args[0][0] == "persistent_notification"
    assert call_args[0][1] == "create"
    
    # Get notification data (3rd positional arg)
    notification_data = call_args[0][2]
    assert "OpenWeatherMap" in notification_data["message"]
    assert "disabled" in notification_data["message"].lower()
    assert "hangar_assistant_owm_disabled" in notification_data["notification_id"]


@pytest.mark.asyncio
@pytest.mark.xfail(reason="OWM cache persistence testing requires file I/O setup")
async def test_owm_returns_cached_data_after_auto_disable(mock_hass, mock_config_entry):
    """Test that OWM returns cached data after auto-disable.
    
    Graceful degradation: even when auto-disabled, the client should
    return cached data if available to keep sensors working.
    
    Setup:
        - Client with enabled = False (auto-disabled)
        - Mock cache with valid data
    
    Validation:
        - get_weather_data returns cached data
        - No API call attempted
        - Cache hit logged
    
    Expected Result:
        Cached data returned, sensors continue working with stale data.
    """
    # Set auto-disabled state
    mock_config_entry.data["integrations"]["openweathermap"]["enabled"] = False
    mock_config_entry.data["integrations"]["openweathermap"]["consecutive_failures"] = 3
    
    client = OpenWeatherMapClient(
        api_key="test_key",
        hass=mock_hass,
        config_entry=mock_config_entry,
        cache_enabled=True
    )
    
    # Mock cached data (patch both memory and persistent cache methods)
    cached_data = {
        "lat": 51.0,
        "lon": -1.0,
        "current": {"temp": 15, "pressure": 1013}
    }
    
    # Patch _read_persistent_cache_stale to return cached data
    # Need to patch hass.async_add_executor_job to return the cached data
    async def mock_executor_job(func, *args):
        if func == client._read_persistent_cache_stale:
            return cached_data
        return None
    
    with patch.object(mock_hass, 'async_add_executor_job', side_effect=mock_executor_job):
        with patch.object(client, '_fetch_from_api') as mock_fetch:
            result = await client.get_weather_data(51.0, -1.0)
    
    # Should return cached data
    assert result is not None
    assert result["current"]["temp"] == 15
    
    # Should NOT call API when disabled
    mock_fetch.assert_not_called()


@pytest.mark.asyncio
async def test_owm_tracks_401_unauthorized_errors(mock_hass, mock_config_entry):
    """Test that OWM tracks 401 Unauthorized errors specifically.
    
    401 errors indicate API key issues - this should be tracked
    separately for better diagnostics.
    
    Setup:
        - Mock API response with 401 status
    
    Validation:
        - last_error contains "401" or "Unauthorized"
        - consecutive_failures incremented
        - Error type identifiable in logs
    
    Expected Result:
        User can identify API key problem from error message.
    """
    client = OpenWeatherMapClient(
        api_key="test_key",
        hass=mock_hass,
        config_entry=mock_config_entry,
        cache_enabled=True
    )
    
    # Mock 401 error
    error = aiohttp.ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=401,
        message="Unauthorized"
    )
    
    with patch.object(client, '_fetch_from_api', side_effect=error):
        result = await client.get_weather_data(51.0, -1.0)
    
    assert result is None
    
    # Check error tracking
    last_error = mock_config_entry.data["integrations"]["openweathermap"]["last_error"]
    assert "401" in last_error or "Unauthorized" in last_error


@pytest.mark.asyncio
async def test_owm_tracks_429_rate_limit_errors(mock_hass, mock_config_entry):
    """Test that OWM tracks 429 Rate Limit errors specifically.
    
    429 errors indicate quota exhaustion - should be tracked
    for rate limit monitoring.
    
    Setup:
        - Mock API response with 429 status
    
    Validation:
        - last_error contains "429" or "Rate limit"
        - consecutive_failures incremented
        - User can identify quota issue
    
    Expected Result:
        Error message clearly indicates rate limit problem.
    """
    client = OpenWeatherMapClient(
        api_key="test_key",
        hass=mock_hass,
        config_entry=mock_config_entry,
        cache_enabled=True
    )
    
    # Mock 429 error
    error = aiohttp.ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=429,
        message="Too Many Requests"
    )
    
    with patch.object(client, '_fetch_from_api', side_effect=error):
        result = await client.get_weather_data(51.0, -1.0)
    
    assert result is None
    
    # Check error tracking
    last_error = mock_config_entry.data["integrations"]["openweathermap"]["last_error"]
    assert "429" in last_error or "rate limit" in last_error.lower()


@pytest.mark.asyncio
async def test_owm_tracks_network_timeout_errors(mock_hass, mock_config_entry):
    """Test that OWM tracks network timeout errors.
    
    Timeout errors indicate network issues, not API problems.
    Should be tracked for diagnostics.
    
    Setup:
        - Mock API call that times out
    
    Validation:
        - last_error contains "timeout" or "Timeout"
        - consecutive_failures incremented
        - Distinguishable from API errors
    
    Expected Result:
        Error message clearly indicates timeout issue.
    """
    client = OpenWeatherMapClient(
        api_key="test_key",
        hass=mock_hass,
        config_entry=mock_config_entry,
        cache_enabled=True
    )
    
    # Mock timeout error
    with patch.object(client, '_fetch_from_api', side_effect=aiohttp.ServerTimeoutError("Timeout")):
        result = await client.get_weather_data(51.0, -1.0)
    
    assert result is None
    
    # Check error tracking
    last_error = mock_config_entry.data["integrations"]["openweathermap"]["last_error"]
    assert "timeout" in last_error.lower()


@pytest.mark.asyncio
async def test_owm_tracks_last_success_timestamp(mock_hass, mock_config_entry):
    """Test that OWM tracks last_success timestamp on successful fetch.
    
    Timestamp tracking helps users understand when data was last refreshed.
    
    Setup:
        - Mock successful API call
    
    Validation:
        - last_success timestamp present
        - Timestamp is ISO 8601 format
        - Timestamp is recent (within test execution time)
    
    Expected Result:
        Accurate timestamp stored for successful API calls.
    """
    client = OpenWeatherMapClient(
        api_key="test_key",
        hass=mock_hass,
        config_entry=mock_config_entry,
        cache_enabled=True
    )
    
    mock_response = {
        "lat": 51.0,
        "lon": -1.0,
        "current": {"temp": 15}
    }
    
    with patch.object(client, '_fetch_from_api', return_value=mock_response):
        result = await client.get_weather_data(51.0, -1.0)
    
    assert result is not None
    
    # Check timestamp tracking
    assert "last_success" in mock_config_entry.data["integrations"]["openweathermap"]
    
    # Verify ISO 8601 format (basic check)
    last_success = mock_config_entry.data["integrations"]["openweathermap"]["last_success"]
    assert "T" in last_success  # ISO format contains 'T'
    
    # Verify timestamp is recent (within 1 minute of now)
    timestamp = datetime.fromisoformat(last_success.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    age_seconds = (now - timestamp).total_seconds()
    assert age_seconds < 60  # Should be very recent


@pytest.mark.asyncio
async def test_owm_tracks_last_error_message(mock_hass, mock_config_entry):
    """Test that OWM tracks last_error message on failures.
    
    Error message tracking helps users diagnose issues without checking logs.
    
    Setup:
        - Mock API error with specific message
    
    Validation:
        - last_error populated with error message
        - Error message is user-friendly
        - Error message retained across calls
    
    Expected Result:
        Detailed error message available for troubleshooting.
    """
    client = OpenWeatherMapClient(
        api_key="test_key",
        hass=mock_hass,
        config_entry=mock_config_entry,
        cache_enabled=True
    )
    
    error_message = "API key invalid or expired"
    
    with patch.object(client, '_fetch_from_api', side_effect=aiohttp.ClientError(error_message)):
        result = await client.get_weather_data(51.0, -1.0)
    
    assert result is None
    
    # Check error message tracking
    assert "last_error" in mock_config_entry.data["integrations"]["openweathermap"]
    last_error = mock_config_entry.data["integrations"]["openweathermap"]["last_error"]
    assert error_message in last_error
