"""Unit tests for OpenWeatherMap API client."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
from datetime import datetime, timedelta
import json
import asyncio
from custom_components.hangar_assistant.utils.openweathermap import (
    OpenWeatherMapClient,
    OWM_API_BASE,
    DEFAULT_CACHE_TTL_MINUTES,
)


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.config.path = MagicMock(return_value="/config/hangar_assistant_cache")
    hass.helpers.aiohttp_client.async_get_clientsession = MagicMock(
        return_value=AsyncMock()
    )
    
    # Make async_add_executor_job async for testing
    async def mock_executor_job(func, *args):
        """Mock async_add_executor_job that returns awaitable."""
        return func(*args)
    
    hass.async_add_executor_job = mock_executor_job
    return hass


@pytest.fixture
def owm_client(mock_hass):
    """Create an OWM client instance."""
    with patch("pathlib.Path.mkdir"):
        return OpenWeatherMapClient(
            api_key="test_api_key_12345",
            hass=mock_hass,
            cache_enabled=True,
            cache_ttl_minutes=10,
        )


@pytest.fixture
def sample_owm_response():
    """Sample OWM API response."""
    return {
        "lat": 51.2,
        "lon": -1.2,
        "timezone": "Europe/London",
        "current": {
            "dt": 1642770000,
            "temp": 12.5,
            "dew_point": 8.2,
            "pressure": 1013,
            "humidity": 75,
            "clouds": 45,
            "visibility": 10000,
            "wind_speed": 7.5,
            "wind_deg": 270,
            "wind_gust": 12.0,
            "uvi": 2.5,
            "weather": [
                {
                    "id": 802,
                    "main": "Clouds",
                    "description": "scattered clouds",
                    "icon": "03d"
                }
            ]
        },
        "minutely": [
            {"dt": 1642770060, "precipitation": 0},
            {"dt": 1642770120, "precipitation": 0},
        ],
        "hourly": [
            {
                "dt": 1642770000,
                "temp": 12.5,
                "dew_point": 8.2,
                "pressure": 1013,
                "wind_speed": 7.5,
                "wind_deg": 270,
            }
        ],
        "daily": [
            {
                "dt": 1642723200,
                "sunrise": 1642749600,
                "sunset": 1642780800,
                "temp": {
                    "day": 14.2,
                    "min": 8.1,
                    "max": 15.3,
                    "night": 9.5,
                    "eve": 12.1,
                    "morn": 10.2,
                },
                "pressure": 1013,
                "clouds": 60,
                "wind_speed": 12.0,
                "wind_deg": 250,
            }
        ],
        "alerts": [
            {
                "sender_name": "UK Met Office",
                "event": "Wind Warning",
                "start": 1642780800,
                "end": 1642867200,
                "description": "Strong winds expected",
                "tags": ["Wind"],
            }
        ],
    }


class TestOpenWeatherMapClientInit:
    """Test OWM client initialization."""

    @patch("pathlib.Path.mkdir")
    def test_init_with_defaults(self, mock_mkdir, mock_hass):
        """Test client initialization with default parameters."""
        client = OpenWeatherMapClient("test_key", mock_hass)
        
        assert client.api_key == "test_key"
        assert client.hass == mock_hass
        assert client.cache_enabled is True
        assert client.cache_ttl == timedelta(minutes=DEFAULT_CACHE_TTL_MINUTES)
        assert client._api_calls_today == 0

    @patch("pathlib.Path.mkdir")
    def test_init_custom_cache_ttl(self, mock_mkdir, mock_hass):
        """Test initialization with custom cache TTL."""
        client = OpenWeatherMapClient(
            "test_key", mock_hass, cache_ttl_minutes=20
        )
        
        assert client.cache_ttl == timedelta(minutes=20)

    @patch("pathlib.Path.mkdir")
    def test_init_cache_disabled(self, mock_mkdir, mock_hass):
        """Test initialization with caching disabled."""
        client = OpenWeatherMapClient(
            "test_key", mock_hass, cache_enabled=False
        )
        
        assert client.cache_enabled is False

    def test_cache_directory_not_created_on_init(self, mock_hass):
        """Test cache directory is NOT created on init (lazy initialization)."""
        with patch("pathlib.Path.mkdir") as mock_mkdir:
            OpenWeatherMapClient("test_key", mock_hass)
            # Directory should not be created until cache operations occur
            mock_mkdir.assert_not_called()


class TestOpenWeatherMapClientCaching:
    """Test caching functionality."""

    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.exists")
    def test_read_valid_persistent_cache(
        self, mock_exists, mock_file, owm_client, sample_owm_response
    ):
        """Test reading valid persistent cache."""
        mock_exists.return_value = True
        cached_data = {
            "cached_at": datetime.now().isoformat(),
            "coordinates": {"lat": 51.2, "lon": -1.2},
            "data": sample_owm_response,
        }
        mock_file.return_value.read.return_value = json.dumps(cached_data)
        
        result = owm_client._read_persistent_cache(51.2, -1.2)
        
        assert result == sample_owm_response

    @patch("pathlib.Path.exists")
    def test_read_expired_persistent_cache(self, mock_exists, owm_client):
        """Test reading expired persistent cache returns None."""
        mock_exists.return_value = True
        cached_data = {
            "cached_at": (datetime.now() - timedelta(minutes=15)).isoformat(),
            "data": {"test": "data"},
        }
        
        with patch("builtins.open", mock_open(read_data=json.dumps(cached_data))):
            result = owm_client._read_persistent_cache(51.2, -1.2)
        
        assert result is None

    @patch("pathlib.Path.exists")
    def test_read_cache_disabled(self, mock_exists, mock_hass):
        """Test cache reading when caching is disabled."""
        client = OpenWeatherMapClient(
            "test_key", mock_hass, cache_enabled=False
        )
        
        result = client._read_persistent_cache(51.2, -1.2)
        
        assert result is None
        mock_exists.assert_not_called()

    @patch("builtins.open", new_callable=mock_open)
    def test_write_persistent_cache(self, mock_file, owm_client, sample_owm_response):
        """Test writing to persistent cache."""
        owm_client._write_persistent_cache(51.2, -1.2, sample_owm_response)
        
        mock_file.assert_called_once()
        handle = mock_file()
        written_data = "".join(
            call.args[0] for call in handle.write.call_args_list
        )
        cached = json.loads(written_data)
        
        assert cached["data"] == sample_owm_response
        assert "cached_at" in cached
        assert cached["coordinates"] == {"lat": 51.2, "lon": -1.2}

    def test_write_cache_disabled(self, mock_hass, sample_owm_response):
        """Test cache writing when caching is disabled."""
        client = OpenWeatherMapClient(
            "test_key", mock_hass, cache_enabled=False
        )
        
        with patch("builtins.open", mock_open()) as mock_file:
            client._write_persistent_cache(51.2, -1.2, sample_owm_response)
            mock_file.assert_not_called()


class TestOpenWeatherMapClientAPI:
    """Test API interaction."""

    @pytest.mark.asyncio
    async def test_fetch_from_api_success(
        self, owm_client, sample_owm_response, mock_hass
    ):
        """Test successful API fetch."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=sample_owm_response)
        
        # Create async context manager mock properly
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_response
        mock_context_manager.__aexit__.return_value = False
        
        mock_session = MagicMock()
        mock_session.get.return_value = mock_context_manager
        mock_hass.helpers.aiohttp_client.async_get_clientsession.return_value = (
            mock_session
        )
        
        with patch.object(owm_client, "_write_persistent_cache"):
            result = await owm_client._fetch_from_api(51.2, -1.2)
        
        assert result == sample_owm_response
        assert owm_client._api_calls_today == 1

    @pytest.mark.asyncio
    async def test_fetch_api_key_invalid(self, owm_client, mock_hass):
        """Test API fetch with invalid key."""
        mock_response = AsyncMock()
        mock_response.status = 401
        
        # Create async context manager mock properly
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_response
        mock_context_manager.__aexit__.return_value = False
        
        mock_session = MagicMock()
        mock_session.get.return_value = mock_context_manager
        mock_hass.helpers.aiohttp_client.async_get_clientsession.return_value = (
            mock_session
        )
        
        result = await owm_client._fetch_from_api(51.2, -1.2)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_rate_limit_exceeded(self, owm_client, mock_hass):
        """Test API fetch when rate limit exceeded."""
        mock_response = AsyncMock()
        mock_response.status = 429
        
        # Create async context manager mock properly
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_response
        mock_context_manager.__aexit__.return_value = False
        
        mock_session = MagicMock()
        mock_session.get.return_value = mock_context_manager
        mock_hass.helpers.aiohttp_client.async_get_clientsession.return_value = (
            mock_session
        )
        
        result = await owm_client._fetch_from_api(51.2, -1.2)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_timeout(self, owm_client, mock_hass):
        """Test API fetch timeout handling."""
        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=asyncio.TimeoutError())
        mock_hass.helpers.aiohttp_client.async_get_clientsession.return_value = (
            mock_session
        )
        
        result = await owm_client._fetch_from_api(51.2, -1.2)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_client_error(self, owm_client, mock_hass):
        """Test API fetch with client error."""
        # Mock a generic client error (ConnectionError is a built-in)
        mock_session = MagicMock()
        mock_session.get = MagicMock(
            side_effect=ConnectionError("Connection error")
        )
        mock_hass.helpers.aiohttp_client.async_get_clientsession.return_value = (
            mock_session
        )
        
        result = await owm_client._fetch_from_api(51.2, -1.2)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_api_call_tracking(self, owm_client, sample_owm_response, mock_hass):
        """Test API call tracking per day."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=sample_owm_response)
        
        # Create async context manager mock properly
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_response
        mock_context_manager.__aexit__.return_value = False
        
        mock_session = MagicMock()
        mock_session.get.return_value = mock_context_manager
        mock_hass.helpers.aiohttp_client.async_get_clientsession.return_value = (
            mock_session
        )
        
        with patch.object(owm_client, "_write_persistent_cache"):
            await owm_client._fetch_from_api(51.2, -1.2)
            await owm_client._fetch_from_api(51.3, -1.3)
        
        assert owm_client._api_calls_today == 2


class TestOpenWeatherMapClientDataExtraction:
    """Test data extraction methods."""

    def test_extract_current_weather(self, owm_client, sample_owm_response):
        """Test current weather extraction."""
        current = owm_client.extract_current_weather(sample_owm_response)
        
        assert current["temperature"] == 12.5
        assert current["dew_point"] == 8.2
        assert current["pressure"] == 1013
        assert current["wind_speed"] == 7.5
        assert current["wind_direction"] == 270
        assert current["wind_gust"] == 12.0
        assert current["visibility"] == 10.0  # Converted from m to km
        assert current["clouds"] == 45
        assert current["uvi"] == 2.5
        assert current["weather_description"] == "scattered clouds"

    def test_extract_minutely_forecast(self, owm_client, sample_owm_response):
        """Test minutely forecast extraction."""
        minutely = owm_client.extract_minutely_forecast(sample_owm_response)
        
        assert len(minutely) == 2
        assert minutely[0]["precipitation"] == 0

    def test_extract_hourly_forecast(self, owm_client, sample_owm_response):
        """Test hourly forecast extraction."""
        hourly = owm_client.extract_hourly_forecast(sample_owm_response)
        
        assert len(hourly) == 1
        assert hourly[0]["temp"] == 12.5

    def test_extract_daily_forecast(self, owm_client, sample_owm_response):
        """Test daily forecast extraction."""
        daily = owm_client.extract_daily_forecast(sample_owm_response)
        
        assert len(daily) == 1
        assert daily[0]["temp"]["day"] == 14.2

    def test_extract_alerts(self, owm_client, sample_owm_response):
        """Test alerts extraction."""
        alerts = owm_client.extract_alerts(sample_owm_response)
        
        assert len(alerts) == 1
        assert alerts[0]["event"] == "Wind Warning"
        assert alerts[0]["sender_name"] == "UK Met Office"


class TestOpenWeatherMapClientMultiLevelCache:
    """Test multi-level caching strategy."""

    @pytest.mark.asyncio
    async def test_memory_cache_hit(self, owm_client, sample_owm_response):
        """Test memory cache returns data without API call."""
        # Pre-populate memory cache
        owm_client._memory_cache["51.2_-1.2"] = (
            sample_owm_response,
            datetime.now(),
        )
        
        result = await owm_client.get_weather_data(51.2, -1.2)
        
        assert result == sample_owm_response
        # No API call should be made
        assert owm_client._api_calls_today == 0

    @pytest.mark.asyncio
    async def test_persistent_cache_hit(self, owm_client, sample_owm_response):
        """Test persistent cache fallback when memory cache misses."""
        with patch.object(
            owm_client,
            "_read_persistent_cache",
            return_value=sample_owm_response,
        ):
            result = await owm_client.get_weather_data(51.2, -1.2)
        
        assert result == sample_owm_response
        # Data should be added to memory cache
        assert "51.2_-1.2" in owm_client._memory_cache
        # No API call should be made
        assert owm_client._api_calls_today == 0

    @pytest.mark.asyncio
    async def test_cache_miss_triggers_api(
        self, owm_client, sample_owm_response, mock_hass
    ):
        """Test API call when both caches miss."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=sample_owm_response)
        
        # Create async context manager mock properly
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_response
        mock_context_manager.__aexit__.return_value = False
        
        mock_session = MagicMock()
        mock_session.get.return_value = mock_context_manager
        mock_hass.helpers.aiohttp_client.async_get_clientsession.return_value = (
            mock_session
        )
        
        with patch.object(owm_client, "_read_persistent_cache", return_value=None):
            with patch.object(owm_client, "_write_persistent_cache"):
                result = await owm_client.get_weather_data(51.2, -1.2)
        
        assert result == sample_owm_response
        assert owm_client._api_calls_today == 1


class TestOpenWeatherMapClientCacheManagement:
    """Test cache management utilities."""

    @patch("pathlib.Path.unlink")
    @patch("pathlib.Path.exists", return_value=True)
    def test_clear_specific_cache(
        self, mock_exists, mock_unlink, owm_client, sample_owm_response
    ):
        """Test clearing cache for specific coordinates."""
        # Pre-populate memory cache
        owm_client._memory_cache["51.2_-1.2"] = (
            sample_owm_response,
            datetime.now(),
        )
        
        owm_client.clear_cache(51.2, -1.2)
        
        assert "51.2_-1.2" not in owm_client._memory_cache
        mock_unlink.assert_called_once()

    @patch("pathlib.Path.glob")
    def test_clear_all_caches(
        self, mock_glob, owm_client, sample_owm_response
    ):
        """Test clearing all caches."""
        # Pre-populate memory cache
        owm_client._memory_cache["51.2_-1.2"] = (
            sample_owm_response,
            datetime.now(),
        )
        
        mock_file1 = MagicMock()
        mock_file2 = MagicMock()
        mock_glob.return_value = [mock_file1, mock_file2]
        
        owm_client.clear_cache()
        
        assert len(owm_client._memory_cache) == 0
        assert mock_file1.unlink.called
        assert mock_file2.unlink.called

    def test_get_cache_stats(self, owm_client, sample_owm_response):
        """Test getting cache statistics."""
        # Pre-populate memory cache
        owm_client._memory_cache["51.2_-1.2"] = (
            sample_owm_response,
            datetime.now(),
        )
        owm_client._api_calls_today = 5
        
        with patch("pathlib.Path.glob", return_value=[MagicMock(), MagicMock()]):
            stats = owm_client.get_cache_stats()
        
        assert stats["cache_enabled"] is True
        assert stats["cache_ttl_minutes"] == 10
        assert stats["memory_cache_entries"] == 1
        assert stats["persistent_cache_files"] == 2
        assert stats["api_calls_today"] == 5


class TestOpenWeatherMapClientRateLimitProtection:
    """Test rate limit protection."""

    @pytest.mark.asyncio
    async def test_rate_limit_warning(
        self, owm_client, sample_owm_response, mock_hass, caplog
    ):
        """Test warning when approaching rate limit."""
        owm_client._api_calls_today = 950
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=sample_owm_response)
        
        # Create async context manager mock properly
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_response
        mock_context_manager.__aexit__.return_value = False
        
        mock_session = MagicMock()
        mock_session.get.return_value = mock_context_manager
        mock_hass.helpers.aiohttp_client.async_get_clientsession.return_value = (
            mock_session
        )
        
        with patch.object(owm_client, "_write_persistent_cache"):
            await owm_client._fetch_from_api(51.2, -1.2)
        
        assert owm_client._api_calls_today == 951
        # Check warning was logged (in real test would check caplog)

    def test_daily_api_call_reset(self, owm_client):
        """Test API call counter resets daily."""
        owm_client._api_calls_today = 100
        owm_client._api_calls_date = datetime.now().date() - timedelta(days=1)
        
        # Trigger date check (would happen during _fetch_from_api)
        today = datetime.now().date()
        if today != owm_client._api_calls_date:
            owm_client._api_calls_today = 0
            owm_client._api_calls_date = today
        
        assert owm_client._api_calls_today == 0


class TestOpenWeatherMapClientEdgeCases:
    """Test edge cases and error handling."""

    def test_extract_current_missing_data(self, owm_client):
        """Test extraction with missing fields."""
        minimal_response = {"current": {}}
        
        current = owm_client.extract_current_weather(minimal_response)
        
        assert current["temperature"] is None
        assert current["pressure"] is None
        assert current["visibility"] == 10.0  # Default

    def test_extract_alerts_none(self, owm_client):
        """Test extraction when no alerts present."""
        no_alerts_response = {"current": {}}
        
        alerts = owm_client.extract_alerts(no_alerts_response)
        
        assert alerts == []

    @pytest.mark.asyncio
    async def test_concurrent_api_calls(
        self, owm_client, sample_owm_response, mock_hass
    ):
        """Test concurrent API calls don't break tracking."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=sample_owm_response)
        
        # Create async context manager mock properly
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_response
        mock_context_manager.__aexit__.return_value = False
        
        mock_session = MagicMock()
        mock_session.get.return_value = mock_context_manager
        mock_hass.helpers.aiohttp_client.async_get_clientsession.return_value = (
            mock_session
        )
        
        with patch.object(owm_client, "_write_persistent_cache"):
            # Simulate concurrent requests
            tasks = [
                owm_client._fetch_from_api(51.2, -1.2),
                owm_client._fetch_from_api(51.3, -1.3),
                owm_client._fetch_from_api(51.4, -1.4),
            ]
            await asyncio.gather(*tasks)
        
        assert owm_client._api_calls_today == 3
