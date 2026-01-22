"""Tests for ADS-B Configuration Flow.

Tests user setup wizards, validation, and configuration persistence.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from custom_components.hangar_assistant.adsb_config_flow import (
    ADSBConfigFlow,
    ADSBOptionsFlow,
    DEFAULT_DUMP1090_HOST,
    DEFAULT_DUMP1090_PORT,
    DEFAULT_OPENSKY_ENABLED,
    DEFAULT_OGN_ENABLED,
    DEFAULT_OGN_PORT,
)


@pytest.fixture
def mock_hass():
    """Create mock Home Assistant instance."""
    mock = MagicMock(spec=HomeAssistant)
    return mock


@pytest.fixture
def config_flow(mock_hass):
    """Create config flow instance."""
    flow = ADSBConfigFlow()
    flow.hass = mock_hass
    return flow


class TestADSBConfigFlowInit:
    """Test config flow initialization."""

    @pytest.mark.asyncio
    async def test_init_step_shown(self, config_flow):
        """Test initial step is shown."""
        result = await config_flow.async_step_init()

        assert result["type"] == "form"
        assert result["step_id"] == "init"

    @pytest.mark.asyncio
    async def test_init_step_advance_to_dump1090(self, config_flow):
        """Test advancing from init to dump1090 configuration."""
        result = await config_flow.async_step_init(user_input={})

        assert result["type"] == "form"
        assert result["step_id"] == "dump1090"


class TestDump1090Configuration:
    """Test dump1090 TCP configuration."""

    @pytest.mark.asyncio
    async def test_dump1090_disabled(self, config_flow):
        """Test dump1090 disabled configuration."""
        user_input = {
            "enabled": False,
            "host": DEFAULT_DUMP1090_HOST,
            "port": DEFAULT_DUMP1090_PORT,
        }

        result = await config_flow.async_step_dump1090(user_input=user_input)

        assert result["type"] == "form"
        assert result["step_id"] == "opensky"
        assert config_flow.adsb_config["dump1090"]["enabled"] is False

    @pytest.mark.asyncio
    async def test_dump1090_enabled_valid_connection(self, config_flow):
        """Test dump1090 enabled with valid connection."""
        user_input = {
            "enabled": True,
            "host": DEFAULT_DUMP1090_HOST,
            "port": DEFAULT_DUMP1090_PORT,
        }

        with patch("socket.socket") as mock_socket:
            mock_sock_instance = MagicMock()
            mock_sock_instance.connect_ex.return_value = 0  # Connection success
            mock_socket.return_value = mock_sock_instance

            result = await config_flow.async_step_dump1090(user_input=user_input)

            assert result["type"] == "form"
            assert result["step_id"] == "opensky"
            assert config_flow.adsb_config["dump1090"]["enabled"] is True

    @pytest.mark.asyncio
    async def test_dump1090_enabled_connection_failed(self, config_flow):
        """Test dump1090 enabled with failed connection."""
        user_input = {
            "enabled": True,
            "host": "invalid.host",
            "port": 99999,
        }

        with patch("socket.socket") as mock_socket:
            mock_sock_instance = MagicMock()
            mock_sock_instance.connect_ex.return_value = 1  # Connection failed
            mock_socket.return_value = mock_sock_instance

            result = await config_flow.async_step_dump1090(user_input=user_input)

            assert result["type"] == "form"
            assert result["step_id"] == "dump1090"
            assert "base" in result["errors"]

    @pytest.mark.asyncio
    async def test_dump1090_custom_host_port(self, config_flow):
        """Test dump1090 with custom host and port."""
        user_input = {
            "enabled": True,
            "host": "192.168.1.100",
            "port": 30003,
        }

        with patch("socket.socket") as mock_socket:
            mock_sock_instance = MagicMock()
            mock_sock_instance.connect_ex.return_value = 0
            mock_socket.return_value = mock_sock_instance

            result = await config_flow.async_step_dump1090(user_input=user_input)

            assert config_flow.adsb_config["dump1090"]["host"] == "192.168.1.100"
            assert config_flow.adsb_config["dump1090"]["port"] == 30003


class TestOpenSkyConfiguration:
    """Test OpenSky Network API configuration."""

    @pytest.mark.asyncio
    async def test_opensky_disabled(self, config_flow):
        """Test OpenSky disabled."""
        config_flow.adsb_config = {"dump1090": {}}

        user_input = {
            "enabled": False,
            "api_key": "",
            "update_interval": 30,
        }

        result = await config_flow.async_step_opensky(user_input=user_input)

        assert result["type"] == "form"
        assert result["step_id"] == "ogn"
        assert config_flow.adsb_config["opensky"]["enabled"] is False

    @pytest.mark.asyncio
    async def test_opensky_enabled_no_api_key(self, config_flow):
        """Test OpenSky enabled but no API key provided."""
        config_flow.adsb_config = {"dump1090": {}}

        user_input = {
            "enabled": True,
            "api_key": "",
            "update_interval": 30,
        }

        result = await config_flow.async_step_opensky(user_input=user_input)

        assert result["type"] == "form"
        assert result["step_id"] == "opensky"
        assert "api_key" in result["errors"]

    @pytest.mark.asyncio
    async def test_opensky_enabled_valid_api_key(self, config_flow):
        """Test OpenSky enabled with valid API key."""
        config_flow.adsb_config = {"dump1090": {}}

        user_input = {
            "enabled": True,
            "api_key": "test_api_key_12345",
            "update_interval": 60,
        }

        result = await config_flow.async_step_opensky(user_input=user_input)

        assert result["type"] == "form"
        assert result["step_id"] == "ogn"
        assert config_flow.adsb_config["opensky"]["api_key"] == "test_api_key_12345"
        assert config_flow.adsb_config["opensky"]["update_interval"] == 60

    @pytest.mark.asyncio
    async def test_opensky_api_key_sanitization(self, config_flow):
        """Test API key whitespace is trimmed."""
        config_flow.adsb_config = {"dump1090": {}}

        user_input = {
            "enabled": True,
            "api_key": "  api_key_value  ",
            "update_interval": 30,
        }

        result = await config_flow.async_step_opensky(user_input=user_input)

        assert result["type"] == "form"
        assert result["step_id"] == "ogn"
        assert config_flow.adsb_config["opensky"]["api_key"] == "api_key_value"


class TestOGNConfiguration:
    """Test OGN APRS configuration."""

    @pytest.mark.asyncio
    async def test_ogn_enabled_default(self, config_flow):
        """Test OGN enabled by default."""
        config_flow.adsb_config = {"dump1090": {}, "opensky": {}}

        # No user input - use defaults
        result = await config_flow.async_step_ogn()

        assert result["type"] == "form"
        assert result["step_id"] == "ogn"

    @pytest.mark.asyncio
    async def test_ogn_disabled(self, config_flow):
        """Test OGN disabled."""
        config_flow.adsb_config = {"dump1090": {}, "opensky": {}}

        user_input = {
            "enabled": False,
            "host": "aprs.glidernet.org",
            "port": 14580,
            "cache_enabled": True,
            "cache_ttl": 3600,
        }

        result = await config_flow.async_step_ogn(user_input=user_input)

        assert result["type"] == "form"
        assert result["step_id"] == "manager"
        assert config_flow.adsb_config["ogn"]["enabled"] is False

    @pytest.mark.asyncio
    async def test_ogn_custom_settings(self, config_flow):
        """Test OGN with custom settings."""
        config_flow.adsb_config = {"dump1090": {}, "opensky": {}}

        user_input = {
            "enabled": True,
            "host": "custom.glidernet.host",
            "port": 14581,
            "cache_enabled": False,
            "cache_ttl": 7200,
        }

        result = await config_flow.async_step_ogn(user_input=user_input)

        assert result["type"] == "form"
        assert result["step_id"] == "manager"
        assert config_flow.adsb_config["ogn"]["host"] == "custom.glidernet.host"
        assert config_flow.adsb_config["ogn"]["port"] == 14581
        assert config_flow.adsb_config["ogn"]["cache_ttl"] == 7200


class TestManagerConfiguration:
    """Test ADSBManager coordination settings."""

    @pytest.mark.asyncio
    async def test_manager_defaults(self, config_flow):
        """Test manager uses sensible defaults."""
        config_flow.adsb_config = {
            "dump1090": {"enabled": False},
            "opensky": {"enabled": False},
            "ogn": {"enabled": True},
        }

        user_input = {
            "max_cache_entries": 5000,
            "cache_ttl_seconds": 30,
            "query_timeout_seconds": 5,
        }

        result = await config_flow.async_step_manager(user_input=user_input)

        assert result["type"] == "create_entry"
        assert result["title"] == "ADS-B Tracking"
        assert result["data"]["manager"]["max_cache_entries"] == 5000
        assert result["data"]["manager"]["cache_ttl_seconds"] == 30

    @pytest.mark.asyncio
    async def test_manager_custom_settings(self, config_flow):
        """Test manager with custom settings."""
        config_flow.adsb_config = {
            "dump1090": {"enabled": True},
            "opensky": {"enabled": True},
            "ogn": {"enabled": True},
        }

        user_input = {
            "max_cache_entries": 10000,
            "cache_ttl_seconds": 60,
            "query_timeout_seconds": 10,
        }

        result = await config_flow.async_step_manager(user_input=user_input)

        assert result["type"] == "create_entry"
        assert result["data"]["manager"]["max_cache_entries"] == 10000
        assert result["data"]["manager"]["cache_ttl_seconds"] == 60
        assert result["data"]["manager"]["query_timeout_seconds"] == 10


class TestCompleteConfigFlow:
    """Test complete configuration flow from start to finish."""

    @pytest.mark.asyncio
    async def test_full_setup_ogn_only(self, config_flow):
        """Test complete setup with only OGN enabled."""
        # Step 1: Init
        result = await config_flow.async_step_init(user_input={})
        assert result["step_id"] == "dump1090"

        # Step 2: dump1090 disabled
        result = await config_flow.async_step_dump1090(
            user_input={
                "enabled": False,
                "host": DEFAULT_DUMP1090_HOST,
                "port": DEFAULT_DUMP1090_PORT,
            }
        )
        assert result["step_id"] == "opensky"

        # Step 3: OpenSky disabled
        result = await config_flow.async_step_opensky(
            user_input={
                "enabled": False,
                "api_key": "",
                "update_interval": 30,
            }
        )
        assert result["step_id"] == "ogn"

        # Step 4: OGN enabled
        result = await config_flow.async_step_ogn(
            user_input={
                "enabled": True,
                "host": "aprs.glidernet.org",
                "port": 14580,
                "cache_enabled": True,
                "cache_ttl": 3600,
            }
        )
        assert result["step_id"] == "manager"

        # Step 5: Manager settings
        result = await config_flow.async_step_manager(
            user_input={
                "max_cache_entries": 5000,
                "cache_ttl_seconds": 30,
                "query_timeout_seconds": 5,
            }
        )

        assert result["type"] == "create_entry"
        assert result["data"]["dump1090"]["enabled"] is False
        assert result["data"]["opensky"]["enabled"] is False
        assert result["data"]["ogn"]["enabled"] is True

    @pytest.mark.asyncio
    async def test_full_setup_all_sources(self, config_flow):
        """Test complete setup with all sources enabled."""
        # Step 1: Init
        result = await config_flow.async_step_init(user_input={})
        assert result["step_id"] == "dump1090"

        # Step 2: dump1090 enabled
        with patch("socket.socket") as mock_socket:
            mock_sock_instance = MagicMock()
            mock_sock_instance.connect_ex.return_value = 0
            mock_socket.return_value = mock_sock_instance

            result = await config_flow.async_step_dump1090(
                user_input={
                    "enabled": True,
                    "host": "192.168.1.50",
                    "port": 30002,
                }
            )
        assert result["step_id"] == "opensky"

        # Step 3: OpenSky enabled
        result = await config_flow.async_step_opensky(
            user_input={
                "enabled": True,
                "api_key": "my_api_key",
                "update_interval": 30,
            }
        )
        assert result["step_id"] == "ogn"

        # Step 4: OGN enabled
        result = await config_flow.async_step_ogn(
            user_input={
                "enabled": True,
                "host": "aprs.glidernet.org",
                "port": 14580,
                "cache_enabled": True,
                "cache_ttl": 3600,
            }
        )
        assert result["step_id"] == "manager"

        # Step 5: Manager settings
        result = await config_flow.async_step_manager(
            user_input={
                "max_cache_entries": 5000,
                "cache_ttl_seconds": 30,
                "query_timeout_seconds": 5,
            }
        )

        assert result["type"] == "create_entry"
        assert result["data"]["dump1090"]["enabled"] is True
        assert result["data"]["opensky"]["enabled"] is True
        assert result["data"]["ogn"]["enabled"] is True


class TestADSBOptionsFlow:
    """Test options flow for editing existing configuration."""

    def test_options_flow_creation(self):
        """Test options flow can be created."""
        mock_entry = MagicMock(spec=config_entries.ConfigEntry)
        mock_entry.data = {
            "dump1090": {"enabled": False},
            "opensky": {"enabled": False},
            "ogn": {"enabled": True},
        }

        options_flow = ADSBOptionsFlow(mock_entry)

        assert options_flow.config_entry is mock_entry

    @pytest.mark.asyncio
    async def test_options_flow_init_uses_current_config(self):
        """Test options flow shows current configuration."""
        mock_entry = MagicMock(spec=config_entries.ConfigEntry)
        mock_entry.data = {
            "dump1090": {"enabled": True},
            "opensky": {"enabled": False},
            "ogn": {"enabled": True},
        }

        options_flow = ADSBOptionsFlow(mock_entry)
        result = await options_flow.async_step_init()

        assert result["type"] == "form"
        assert result["step_id"] == "init"

    @pytest.mark.asyncio
    async def test_options_flow_update(self):
        """Test options flow update."""
        mock_entry = MagicMock(spec=config_entries.ConfigEntry)
        mock_entry.data = {
            "dump1090": {"enabled": False},
            "opensky": {"enabled": False},
            "ogn": {"enabled": True},
        }

        options_flow = ADSBOptionsFlow(mock_entry)

        user_input = {
            "dump1090_enabled": True,
            "opensky_enabled": True,
            "ogn_enabled": False,
        }

        result = await options_flow.async_step_init(user_input=user_input)

        assert result["type"] == "create_entry"
        assert result["data"]["dump1090_enabled"] is True


class TestConfigFlowGetOptionsFlow:
    """Test getting options flow from config flow."""

    def test_get_options_flow(self):
        """Test options flow can be retrieved."""
        mock_entry = MagicMock(spec=config_entries.ConfigEntry)

        flow = ADSBConfigFlow.async_get_options_flow(mock_entry)

        assert isinstance(flow, ADSBOptionsFlow)
        assert flow.config_entry is mock_entry
