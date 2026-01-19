"""Hangar Assistant: Aviation Safety & Compliance for Home Assistant."""
import logging
import os
import time
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Hangar Assistant integration."""
    async def handle_manual_cleanup(call: ServiceCall):
        """Service to manually purge legal records."""
        # Get the value from the service call, fall back to entry data, then default to 7
        retention_months = call.data.get("retention_months")
        
        if not retention_months:
            entries = hass.config_entries.async_entries(DOMAIN)
            for entry in entries:
                if "retention_months" in entry.data:
                    retention_months = entry.data["retention_months"]
                    break
        
        retention_months = retention_months or 7
        await async_cleanup_records(hass, retention_months)
    
    hass.services.async_register(DOMAIN, "manual_cleanup", handle_manual_cleanup)
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hangar Assistant from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Store the entry data for reference by other platforms
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Forward the setup to sensor.py and binary_sensor.py
    # These platforms will now loop through entry.data['airfields'] etc.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register a listener for track updates (when user adds/edits via Options Flow)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True

async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update by reloading the integration."""
    # This ensures that when a user adds a new aircraft, the sensors refresh immediately
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

async def async_cleanup_records(hass: HomeAssistant, months: int):
    """Logic to delete old PDF declarations from local storage."""
    path = hass.config.path("www/hangar/")
    # Average seconds in a month
    cutoff_seconds = months * 30.44 * 24 * 60 * 60
    now = time.time()

    if os.path.exists(path):
        for filename in os.listdir(path):
            file_path = os.path.join(path, filename)
            if os.path.isfile(file_path):
                if (now - os.path.getmtime(file_path)) > cutoff_seconds:
                    try:
                        os.remove(file_path)
                        _LOGGER.info(f"Deleted expired aviation record: {filename}")
                    except OSError as e:
                        _LOGGER.error(f"Error deleting record {filename}: {e}")