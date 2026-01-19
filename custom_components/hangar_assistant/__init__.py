"""Hangar Assistant: Aviation Safety & Compliance for Home Assistant."""
from __future__ import annotations

import logging
import os
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import DOMAIN, PLATFORMS, DEFAULT_RETENTION_MONTHS

_LOGGER = logging.getLogger(__name__)

# This line resolves the [CONFIG_SCHEMA] error for Hassfest
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Hangar Assistant integration global services."""
    
    async def handle_manual_cleanup(call: ServiceCall) -> None:
        """Service to manually purge legal records past their retention date."""
        # Get retention from service call, fallback to 7 months
        retention_months = call.data.get("retention_months", DEFAULT_RETENTION_MONTHS)
        
        await async_cleanup_records(hass, retention_months)

    # Register the service globally
    hass.services.async_register(
        DOMAIN, 
        "manual_cleanup", 
        handle_manual_cleanup,
        schema=vol.Schema({
            vol.Optional("retention_months"): cv.positive_int
        })
    )
    
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hangar Assistant from a config entry."""
    # Forward setup to sensor and binary_sensor platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up briefing schedules
    for briefing in entry.data.get("briefings", []):
        async def run_briefing(now, b=briefing):
            await async_send_briefing(hass, b)
        
        # Parse HH:MM:SS or HH:MM
        time_parts = briefing["briefing_time"].split(":")
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        
        entry.async_on_unload(
            async_track_time_change(hass, run_briefing, hour=hour, minute=minute, second=0)
        )

    # Reload integration if options change in the UI
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update by reloading the integration."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

async def async_cleanup_records(hass: HomeAssistant, months: int) -> None:
    """Logic to delete old PDF declarations from local storage."""
    # Use hass.config.path to ensure cross-platform compatibility
    path = hass.config.path("www/hangar/")
    cutoff_seconds = months * 30.44 * 24 * 60 * 60
    now = dt_util.as_timestamp(dt_util.utcnow())

    if os.path.exists(path):
        for filename in os.listdir(path):
            file_path = os.path.join(path, filename)
            if os.path.isfile(file_path):
                file_mtime = os.path.getmtime(file_path)
                if (now - file_mtime) > cutoff_seconds:
                    try:
                        os.remove(file_path)
                        _LOGGER.info("Deleted expired aviation record: %s", filename)
                    except OSError as e:
                        _LOGGER.error("Error deleting record %s: %s", filename, e)

async def async_send_briefing(hass: HomeAssistant, briefing: dict) -> None:
    """Compose and send the briefing email."""
    airfield_slug = briefing["airfield_name"].lower().replace(" ", "_")
    aircraft_slug = briefing["aircraft_reg"].lower().replace(" ", "_")
    
    # Fetch current states
    da = hass.states.get(f"sensor.{airfield_slug}_density_altitude")
    carb = hass.states.get(f"sensor.{airfield_slug}_carb_risk")
    roll = hass.states.get(f"sensor.{aircraft_slug}_calculated_ground_roll")
    
    subject = f"✈️ Hangar Briefing: {briefing['airfield_name']} / {briefing['aircraft_reg']}"
    body = (
        f"Good morning Captain.\n\n"
        f"Here is your automated safety briefing for {briefing['airfield_name']}:\n"
        f"- Density Altitude: {da.state if da else 'N/A'} ft\n"
        f"- Carb Icing Risk: {carb.state if carb else 'N/A'}\n"
        f"- Predicted Ground Roll ({briefing['aircraft_reg']}): {roll.state if roll else 'N/A'} m\n\n"
        f"Fly safe!"
    )

    try:
        await hass.services.async_call(
            "notify", 
            "persistent_notification", # Fallback for demo, usually 'email' or 'mobile_app'
            {
                "title": subject,
                "message": body
            }
        )
        _LOGGER.info("Briefing sent to %s", briefing["email_recipient"])
    except Exception as e:
        _LOGGER.error("Failed to send briefing: %s", e)