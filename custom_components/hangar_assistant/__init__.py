import os
import time
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from .const import DOMAIN, PLATFORMS

async def async_setup(hass, config):
    async def handle_manual_cleanup(call: ServiceCall):
        entries = hass.config_entries.async_entries(DOMAIN)
        briefing = next((e for e in entries if e.data.get("type") == "briefing"), None)
        months = briefing.data.get("retention_months", 7) if briefing else 7
        await async_cleanup_records(hass, months)
    
    hass.services.async_register(DOMAIN, "manual_cleanup", handle_manual_cleanup)
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_cleanup_records(hass, months):
    path = "/config/www/hangar/"
    cutoff = months * 30.44 * 24 * 60 * 60
    if os.path.exists(path):
        for f in os.listdir(path):
            f_path = os.path.join(path, f)
            if os.path.isfile(f_path) and (time.time() - os.path.getmtime(f_path)) > cutoff:
                os.remove(f_path)