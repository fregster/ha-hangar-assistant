"""ADS-B Configuration Flow for Home Assistant.

Handles user setup and configuration of ADS-B data sources including:
- dump1090 TCP connection settings
- OpenSky Network API credentials
- OGN APRS connection settings
- Multi-source coordination options
"""

import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from custom_components.hangar_assistant.const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Configuration constants
DEFAULT_DUMP1090_HOST = "localhost"
DEFAULT_DUMP1090_PORT = 30002
DEFAULT_DUMP1090_ENABLED = False

DEFAULT_OPENSKY_ENABLED = False
DEFAULT_OPENSKY_UPDATE_INTERVAL = 30  # seconds

DEFAULT_OGN_ENABLED = True
DEFAULT_OGN_HOSTS = ["aprs.glidernet.org", "glidern1.glidernet.org"]
DEFAULT_OGN_PORT = 14580

DEFAULT_MANAGER_CACHE_TTL = 30  # seconds
DEFAULT_MANAGER_MAX_CACHE = 5000  # aircraft


class ADSBConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle ADS-B configuration flow.
    
    Guides users through setup of ADS-B data sources with validation
    and intelligent defaults for different source types.
    """

    VERSION = 1

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle initial step - ADS-B feature selection."""
        if user_input is not None:
            # User confirmed ADS-B tracking setup
            return await self.async_step_dump1090()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
            description_placeholders={
                "learn_more": "https://github.com/hangar-assistant/hangar-assistant/wiki/ADS-B-Tracking"
            },
        )

    async def async_step_dump1090(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle dump1090 TCP server configuration."""
        errors = {}

        if user_input is not None:
            enabled = user_input.get("enabled", False)

            if enabled:
                # Validate connection settings
                host = user_input.get("host", DEFAULT_DUMP1090_HOST)
                port = user_input.get("port", DEFAULT_DUMP1090_PORT)

                # Try to connect and validate
                try:
                    import socket

                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    result = sock.connect_ex((host, port))
                    sock.close()

                    if result != 0:
                        _LOGGER.warning(
                            "Cannot connect to dump1090 at %s:%d", host, port
                        )
                        errors["base"] = "connection_failed"
                except Exception as e:
                    _LOGGER.error("Error validating dump1090 connection: %s", e)
                    errors["base"] = "connection_error"

            if not errors:
                # Store configuration and continue
                self.adsb_config = {
                    "dump1090": {
                        "enabled": enabled,
                        "host": user_input.get("host", DEFAULT_DUMP1090_HOST),
                        "port": user_input.get("port", DEFAULT_DUMP1090_PORT),
                    }
                }
                return await self.async_step_opensky()

        return self.async_show_form(
            step_id="dump1090",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "enabled", default=DEFAULT_DUMP1090_ENABLED
                    ): bool,
                    vol.Optional(
                        "host",
                        default=DEFAULT_DUMP1090_HOST,
                        description={"suggested_value": DEFAULT_DUMP1090_HOST},
                    ): str,
                    vol.Optional(
                        "port",
                        default=DEFAULT_DUMP1090_PORT,
                        description={"suggested_value": DEFAULT_DUMP1090_PORT},
                    ): int,
                }
            ),
            errors=errors,
            description_placeholders={
                "example_host": DEFAULT_DUMP1090_HOST,
                "example_port": DEFAULT_DUMP1090_PORT,
            },
        )

    async def async_step_opensky(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle OpenSky Network API configuration."""
        errors = {}

        if user_input is not None:
            enabled = user_input.get("enabled", False)

            if enabled:
                # API key is required if enabled
                api_key = user_input.get("api_key", "").strip()

                if not api_key:
                    errors["api_key"] = "invalid_api_key"
                else:
                    # Validate API key with simple check (real validation in client)
                    if len(api_key) < 5:
                        errors["api_key"] = "invalid_api_key"

            if not errors:
                if not hasattr(self, "adsb_config"):
                    self.adsb_config = {}

                self.adsb_config["opensky"] = {
                    "enabled": enabled,
                    "api_key": user_input.get("api_key", "").strip(),
                    "update_interval": user_input.get(
                        "update_interval", DEFAULT_OPENSKY_UPDATE_INTERVAL
                    ),
                }
                return await self.async_step_ogn()

        return self.async_show_form(
            step_id="opensky",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "enabled", default=DEFAULT_OPENSKY_ENABLED
                    ): bool,
                    vol.Optional("api_key", default=""): selector.TextSelector(
                        selector.TextSelectorConfig(type="password")
                    ),
                    vol.Optional(
                        "update_interval", default=DEFAULT_OPENSKY_UPDATE_INTERVAL
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=10, max=300, unit_of_measurement="s")
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "signup": "https://opensky-network.org/account/profile",
                "learn_more": "https://opensky-network.org/apidoc/rest.html",
            },
        )

    async def async_step_ogn(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle OGN APRS connection configuration."""
        errors = {}

        if user_input is not None:
            enabled = user_input.get("enabled", DEFAULT_OGN_ENABLED)

            if not errors:
                if not hasattr(self, "adsb_config"):
                    self.adsb_config = {}

                self.adsb_config["ogn"] = {
                    "enabled": enabled,
                    "host": user_input.get("host", DEFAULT_OGN_HOSTS[0]),
                    "port": user_input.get("port", DEFAULT_OGN_PORT),
                    "cache_enabled": user_input.get("cache_enabled", True),
                    "cache_ttl": user_input.get("cache_ttl", 3600),
                }
                return await self.async_step_manager()

        return self.async_show_form(
            step_id="ogn",
            data_schema=vol.Schema(
                {
                    vol.Optional("enabled", default=DEFAULT_OGN_ENABLED): bool,
                    vol.Optional(
                        "host",
                        default=DEFAULT_OGN_HOSTS[0],
                        description={"suggested_value": DEFAULT_OGN_HOSTS[0]},
                    ): str,
                    vol.Optional(
                        "port",
                        default=DEFAULT_OGN_PORT,
                        description={"suggested_value": DEFAULT_OGN_PORT},
                    ): int,
                    vol.Optional("cache_enabled", default=True): bool,
                    vol.Optional(
                        "cache_ttl",
                        default=3600,
                        description={"suggested_value": 3600},
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=300, max=86400, unit_of_measurement="s")
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "example_host": DEFAULT_OGN_HOSTS[0],
                "example_port": DEFAULT_OGN_PORT,
                "learn_more": "https://www.glidernet.org/",
            },
        )

    async def async_step_manager(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle ADSBManager coordination settings."""
        errors = {}

        if user_input is not None:
            if not hasattr(self, "adsb_config"):
                self.adsb_config = {}

            self.adsb_config["manager"] = {
                "max_cache_entries": user_input.get(
                    "max_cache_entries", DEFAULT_MANAGER_MAX_CACHE
                ),
                "cache_ttl_seconds": user_input.get(
                    "cache_ttl_seconds", DEFAULT_MANAGER_CACHE_TTL
                ),
                "query_timeout_seconds": user_input.get(
                    "query_timeout_seconds", 5
                ),
            }

            # Create config entry with all settings
            return self.async_create_entry(
                title="ADS-B Tracking",
                data=self.adsb_config,
            )

        return self.async_show_form(
            step_id="manager",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "max_cache_entries",
                        default=DEFAULT_MANAGER_MAX_CACHE,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=100, max=50000)
                    ),
                    vol.Optional(
                        "cache_ttl_seconds",
                        default=DEFAULT_MANAGER_CACHE_TTL,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=5, max=300, unit_of_measurement="s")
                    ),
                    vol.Optional(
                        "query_timeout_seconds",
                        default=5,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=1, max=30, unit_of_measurement="s")
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "learn_more": "https://github.com/hangar-assistant/hangar-assistant/wiki/ADS-B-Performance"
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get options flow for editing settings."""
        return ADSBOptionsFlow(config_entry)


class ADSBOptionsFlow(config_entries.OptionsFlow):
    """Handle ADS-B options (editing existing configuration)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle options update."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "dump1090_enabled",
                        default=self.config_entry.data.get("dump1090", {}).get(
                            "enabled", DEFAULT_DUMP1090_ENABLED
                        ),
                    ): bool,
                    vol.Optional(
                        "opensky_enabled",
                        default=self.config_entry.data.get("opensky", {}).get(
                            "enabled", DEFAULT_OPENSKY_ENABLED
                        ),
                    ): bool,
                    vol.Optional(
                        "ogn_enabled",
                        default=self.config_entry.data.get("ogn", {}).get(
                            "enabled", DEFAULT_OGN_ENABLED
                        ),
                    ): bool,
                }
            ),
        )
