"""Config flow tests for External Integrations (Weather, NOTAMs, ADS-B).

Validates the consolidated menu for enabling weather integrations
(CheckWX, OpenWeatherMap, NOTAMs) and ADS-B data sources (dump1090,
OpenSky, ADSBExchange, OGN, FlightAware, FlightRadar24) with safe
defaults and backward compatibility.
"""
import pytest
from unittest.mock import MagicMock
from custom_components.hangar_assistant.config_flow import HangarOptionsFlowHandler


@pytest.mark.asyncio
async def test_external_integrations_form_defaults_new_install():
    """Form renders with sensible defaults for a new install."""
    handler = HangarOptionsFlowHandler(MagicMock())
    handler._config_entry = MagicMock()
    handler._config_entry.data = {}
    handler.hass = MagicMock()

    result = await handler.async_step_external_integrations(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "external_integrations"

    schema = result["data_schema"].schema

    def _default_for(field: str):
        for marker in schema:
            if getattr(marker, "schema", None) == field:
                default_value = getattr(marker, "default", None)
                return default_value() if callable(default_value) else default_value
        return None

    # Weather integrations
    assert _default_for("checkwx_enabled") is False
    assert _default_for("checkwx_api_key") == ""
    assert _default_for("checkwx_metar_enabled") is True
    assert _default_for("checkwx_taf_enabled") is True
    assert _default_for("checkwx_station_enabled") is True
    assert _default_for("owm_enabled") is False
    assert _default_for("owm_api_key") == ""
    assert _default_for("notam_enabled") is True
    assert _default_for("notam_url") == "https://pibs.nats.co.uk/operational/pibs/PIB.xml"

    # ADS-B integrations
    assert _default_for("dump1090_enabled") is False
    assert _default_for("dump1090_url") == "http://localhost:8080"
    assert _default_for("opensky_enabled") is False
    assert _default_for("opensky_username") == ""
    assert _default_for("opensky_password") == ""
    assert _default_for("opensky_credentials_json") == ""
    assert _default_for("adsb_enabled") is False
    assert _default_for("adsb_api_key") == ""
    assert _default_for("ogn_enabled") is False
    assert _default_for("ogn_api_key") == ""
    assert _default_for("flightaware_enabled") is False
    assert _default_for("flightaware_api_key") == ""
    assert _default_for("flightradar_enabled") is False
    assert _default_for("flightradar_api_key") == ""


@pytest.mark.asyncio
async def test_external_integrations_save_updates_entry():
    """Saving form updates integrations block and preserves failure fields."""
    handler = HangarOptionsFlowHandler(MagicMock())
    handler._config_entry = MagicMock()
    handler._config_entry.data = {
        "integrations": {
            "checkwx": {
                "consecutive_failures": 1,
                "last_error": "rate limit",
            },
            "openweathermap": {
                "consecutive_failures": 2,
                "last_error": "boom",
                "last_success": "2026-01-21T00:00:00",
            },
            "notams": {
                "consecutive_failures": 1,
                "last_error": "timeout",
                "last_update": "2026-01-20T12:00:00",
                "stale_cache_allowed": False,
            },
            "dump1090": {
                "consecutive_failures": 3,
                "last_error": "connection refused",
            },
            "opensky": {
                "consecutive_failures": 2,
                "last_error": "auth failed",
            },
        }
    }
    handler.hass = MagicMock()
    handler.hass.config_entries = MagicMock()
    handler.hass.config_entries.async_update_entry = MagicMock()

    user_input = {
        "checkwx_enabled": True,
        "checkwx_api_key": "checkwx123",
        "checkwx_metar_enabled": True,
        "checkwx_taf_enabled": False,
        "checkwx_station_enabled": True,
        "owm_enabled": True,
        "owm_api_key": "apikey123",
        "notam_enabled": False,
        "notam_url": "https://example.test/notam.xml",
        "dump1090_enabled": True,
        "dump1090_url": "http://192.168.1.10:8080",
        "opensky_enabled": True,
        "opensky_username": "pilot@example.com",
        "opensky_password": "secret",
        "adsb_enabled": True,
        "adsb_api_key": "adsb_key",
        "ogn_enabled": False,
        "ogn_api_key": "",
        "flightaware_enabled": True,
        "flightaware_api_key": "fa_key",
        "flightradar_enabled": False,
        "flightradar_api_key": "",
    }

    result = await handler.async_step_external_integrations(user_input=user_input)

    assert result["type"] == "abort"
    assert result["reason"] == "configuration_updated"

    handler.hass.config_entries.async_update_entry.assert_called_once()
    updated_data = handler.hass.config_entries.async_update_entry.call_args.kwargs["data"]
    integrations = updated_data["integrations"]

    # Weather integrations
    assert integrations["checkwx"]["enabled"] is True
    assert integrations["checkwx"]["api_key"] == "checkwx123"
    assert integrations["checkwx"]["metar_enabled"] is True
    assert integrations["checkwx"]["taf_enabled"] is False
    assert integrations["checkwx"]["station_enabled"] is True
    assert integrations["checkwx"]["consecutive_failures"] == 1
    assert integrations["checkwx"]["last_error"] == "rate limit"

    assert integrations["openweathermap"]["enabled"] is True
    assert integrations["openweathermap"]["api_key"] == "apikey123"
    assert integrations["openweathermap"]["consecutive_failures"] == 2
    assert integrations["openweathermap"]["last_error"] == "boom"
    assert integrations["openweathermap"]["last_success"] == "2026-01-21T00:00:00"

    assert integrations["notams"]["enabled"] is False
    assert integrations["notams"]["url"] == "https://example.test/notam.xml"
    assert integrations["notams"]["consecutive_failures"] == 1
    assert integrations["notams"]["last_error"] == "timeout"
    assert integrations["notams"]["last_update"] == "2026-01-20T12:00:00"
    assert integrations["notams"]["stale_cache_allowed"] is False

    # ADS-B integrations
    assert integrations["dump1090"]["enabled"] is True
    assert integrations["dump1090"]["url"] == "http://192.168.1.10:8080"
    assert integrations["dump1090"]["consecutive_failures"] == 3
    assert integrations["dump1090"]["last_error"] == "connection refused"

    assert integrations["opensky"]["enabled"] is True
    assert integrations["opensky"]["username"] == "pilot@example.com"
    assert integrations["opensky"]["password"] == "secret"
    assert integrations["opensky"].get("credentials") == {}
    assert integrations["opensky"]["consecutive_failures"] == 2
    assert integrations["opensky"]["last_error"] == "auth failed"

    assert integrations["adsbexchange"]["enabled"] is True
    assert integrations["adsbexchange"]["api_key"] == "adsb_key"
    assert integrations["adsbexchange"]["consecutive_failures"] == 0

    assert integrations["ogn"]["enabled"] is False
    assert integrations["ogn"]["api_key"] == ""

    assert integrations["flightaware"]["enabled"] is True
    assert integrations["flightaware"]["api_key"] == "fa_key"

    assert integrations["flightradar24"]["enabled"] is False
    assert integrations["flightradar24"]["api_key"] == ""


@pytest.mark.asyncio
async def test_external_integrations_backward_compat_missing_adsb():
    """Form handles existing installs without CheckWX/OpenSky/ADS-B config gracefully."""
    handler = HangarOptionsFlowHandler(MagicMock())
    handler._config_entry = MagicMock()
    handler._config_entry.data = {
        "integrations": {
            "openweathermap": {
                "enabled": True,
                "api_key": "existing_key",
            },
            "notams": {
                "enabled": True,
                "url": "https://pibs.nats.co.uk/operational/pibs/PIB.xml",
            },
            # CheckWX, OpenSky, and other ADS-B integrations missing (old install)
        }
    }
    handler.hass = MagicMock()

    result = await handler.async_step_external_integrations(user_input=None)

    assert result["type"] == "form"
    schema = result["data_schema"].schema

    def _default_for(field: str):
        for marker in schema:
            if getattr(marker, "schema", None) == field:
                default_value = getattr(marker, "default", None)
                return default_value() if callable(default_value) else default_value
        return None

    # Existing OWM/NOTAM configs preserved
    assert _default_for("owm_enabled") is True
    assert _default_for("owm_api_key") == "existing_key"
    assert _default_for("notam_enabled") is True

    # CheckWX fields default to disabled
    assert _default_for("checkwx_enabled") is False
    assert _default_for("checkwx_api_key") == ""
    assert _default_for("checkwx_metar_enabled") is True
    assert _default_for("checkwx_taf_enabled") is True

    # ADS-B fields default to disabled
    assert _default_for("dump1090_enabled") is False
    assert _default_for("dump1090_url") == "http://localhost:8080"
    assert _default_for("opensky_enabled") is False
    assert _default_for("opensky_username") == ""
    assert _default_for("opensky_password") == ""
    assert _default_for("opensky_credentials_json") == ""
    assert _default_for("adsb_enabled") is False
    assert _default_for("ogn_enabled") is False
    assert _default_for("flightaware_enabled") is False
    assert _default_for("flightradar_enabled") is False


@pytest.mark.asyncio
async def test_external_integrations_save_opensky_credentials_json():
    """OpenSky credentials JSON is parsed and stored securely."""
    handler = HangarOptionsFlowHandler(MagicMock())
    handler._config_entry = MagicMock()
    handler._config_entry.data = {"integrations": {"opensky": {}}}
    handler.hass = MagicMock()
    handler.hass.config_entries = MagicMock()
    handler.hass.config_entries.async_update_entry = MagicMock()

    credentials_json = (
        '{"clientId":"fregster-api-client","clientSecret":"K0EFSnHi9Z7kwgOgUEqqEbvmfMqqsz5g"}'
    )

    user_input = {
        "opensky_enabled": True,
        "opensky_username": "",
        "opensky_password": "",
        "opensky_credentials_json": credentials_json,
    }

    result = await handler.async_step_external_integrations(user_input=user_input)

    assert result["type"] == "abort"
    assert result["reason"] == "configuration_updated"

    handler.hass.config_entries.async_update_entry.assert_called_once()
    updated_data = handler.hass.config_entries.async_update_entry.call_args.kwargs["data"]
    integrations = updated_data["integrations"]

    assert integrations["opensky"]["enabled"] is True
    assert integrations["opensky"]["username"] == ""
    assert integrations["opensky"]["password"] == ""
    assert integrations["opensky"]["credentials"] == {
        "client_id": "fregster-api-client",
        "client_secret": "K0EFSnHi9Z7kwgOgUEqqEbvmfMqqsz5g",
    }

