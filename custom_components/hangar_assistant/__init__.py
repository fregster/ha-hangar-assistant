"""Hangar Assistant: Aviation Safety & Compliance for Home Assistant."""
from __future__ import annotations

import logging
import os
import yaml
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import DOMAIN, PLATFORMS, DEFAULT_RETENTION_MONTHS, DEFAULT_DASHBOARD_VERSION

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

    async def handle_rebuild_dashboard(call: ServiceCall) -> None:
        """Service to rebuild the Hangar Assistant dashboard."""
        _LOGGER.info("Rebuild dashboard service called")
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            _LOGGER.warning("No Hangar Assistant config entry found for dashboard rebuild")
            return
        
        entry = entries[0]  # Use the first (and typically only) entry
        _LOGGER.info("Starting dashboard rebuild with force_rebuild=True")
        result = await async_create_dashboard(hass, entry, force_rebuild=True)
        if result:
            _LOGGER.info("✅ Hangar Assistant dashboard rebuilt successfully")
        else:
            _LOGGER.warning("⚠️ Dashboard rebuild completed but may not have created/updated the file")

    async def handle_refresh_ai_briefings(call: ServiceCall) -> None:
        """Service to manually refresh AI pre-flight briefings."""
        _LOGGER.info("Manual AI briefing refresh requested")
        entries = hass.config_entries.async_entries(DOMAIN)
        for entry in entries:
            await async_generate_all_ai_briefings(hass, entry)

    # Register the manual cleanup service
    hass.services.async_register(
        DOMAIN, 
        "manual_cleanup", 
        handle_manual_cleanup,
        schema=vol.Schema({
            vol.Optional("retention_months"): cv.positive_int
        })
    )
    
    # Register the dashboard rebuild service
    hass.services.async_register(
        DOMAIN,
        "rebuild_dashboard",
        handle_rebuild_dashboard,
        schema=vol.Schema({})
    )

    # Register the AI briefing refresh service
    hass.services.async_register(
        DOMAIN,
        "refresh_ai_briefings",
        handle_refresh_ai_briefings,
        schema=vol.Schema({})
    )
    
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hangar Assistant from a config entry."""
    # Create the dashboard on first setup or if template version changed
    await async_create_dashboard(hass, entry)
    
    # Forward setup to sensor and binary_sensor platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up briefing schedules
    for briefing in entry.data.get("briefings", []):
        async def run_briefing(now, b=briefing, e=entry):
            await async_send_briefing(hass, b, e)
        
        # Parse HH:MM:SS or HH:MM
        time_parts = briefing["briefing_time"].split(":")
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        
        entry.async_on_unload(
            async_track_time_change(hass, run_briefing, hour=hour, minute=minute, second=0)
        )

    # Reload integration if options change in the UI
    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Set up hourly AI briefings if an agent is defined
    ai_config = entry.data.get("ai_assistant", {})
    if ai_config.get("ai_agent_entity"):
        async def run_hourly_ai_briefing(now):
            await async_generate_all_ai_briefings(hass, entry)
        
        entry.async_on_unload(
            async_track_time_change(hass, run_hourly_ai_briefing, minute=0, second=0)
        )
        # Also run once on startup (after a short delay to ensure sensors are ready)
        async def delayed_startup_briefing():
            import asyncio
            await asyncio.sleep(10)
            await async_generate_all_ai_briefings(hass, entry)
        
        hass.async_create_task(delayed_startup_briefing())

    return True

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update by reloading the integration."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_create_dashboard(hass: HomeAssistant, entry: ConfigEntry = None, force_rebuild: bool = False) -> bool:
    """Create the Hangar Assistant dashboard from template."""
    
    def _generate_dashboard():
        """Sync function to perform blocking I/O."""
        try:
            # Get the template file path
            template_path = os.path.join(
                os.path.dirname(__file__),
                "dashboard_templates",
                "glass_cockpit.yaml"
            )
            
            # Verify template exists
            if not os.path.exists(template_path):
                _LOGGER.error("Dashboard template not found at: %s", template_path)
                return False
            
            # Check if dashboard file exists
            dashboards_path = hass.config.path("dashboards")
            dashboard_yaml_path = os.path.join(dashboards_path, "hangar_assistant.yaml")
            
            # Get current dashboard version from config entry
            stored_version = 0
            if entry:
                dashboard_info = entry.data.get("dashboard_info", {})
                stored_version = dashboard_info.get("version", 0)
            
            # Check if we need to rebuild
            dashboard_exists = os.path.exists(dashboard_yaml_path)
            version_mismatch = stored_version < DEFAULT_DASHBOARD_VERSION
            
            if dashboard_exists and not force_rebuild and not version_mismatch:
                return False
            
            # Read the template file
            with open(template_path, "r", encoding="utf-8") as f:
                dashboard_config = yaml.safe_load(f)
            
            # Create dashboards directory if it doesn't exist
            os.makedirs(dashboards_path, exist_ok=True)
            
            # Write the dashboard to the dashboards directory
            with open(dashboard_yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(dashboard_config, f, default_flow_style=False, allow_unicode=True)
            
            return True
        except Exception as e:
            _LOGGER.error("Error in dashboard file operations: %s", e)
            return False

    # Run the blocking I/O in the executor
    result = await hass.async_add_executor_job(_generate_dashboard)
    
    if not result:
        return False

    try:
        # Update config entry with new dashboard version ONLY if changed
        if entry:
            dashboard_info = entry.data.get("dashboard_info", {})
            current_stored_version = dashboard_info.get("version", 0)
            
            if current_stored_version < DEFAULT_DASHBOARD_VERSION:
                _LOGGER.debug("Updating dashboard version in config entry from %s to %s", 
                             current_stored_version, DEFAULT_DASHBOARD_VERSION)
                new_data = dict(entry.data)
                new_data["dashboard_info"] = {
                    "version": DEFAULT_DASHBOARD_VERSION,
                    "last_updated": dt_util.now().isoformat()
                }
                hass.config_entries.async_update_entry(entry, data=new_data)
        
        # Trigger dashboard reload via service if available
        if hass.services.has_service("frontend", "reload_themes"):
            await hass.services.async_call("frontend", "reload_themes")
        
        if hass.services.has_service("lovelace", "reload_dashboards"):
            try:
                await hass.services.async_call("lovelace", "reload_dashboards")
            except Exception as e:
                _LOGGER.debug("Could not reload dashboards via lovelace service: %s", e)
        
        _LOGGER.info("Dashboard creation completed for Hangar Assistant")
        return True
        
    except Exception as e:
        _LOGGER.error("Error updating Hangar Assistant dashboard state: %s", e)
        return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

async def async_cleanup_records(hass: HomeAssistant, months: int) -> None:
    """Logic to delete old PDF declarations from local storage."""
    # Use hass.config.path to ensure cross-platform compatibility
    path = hass.config.path("www/hangar/")
    cutoff_seconds = months * 30.44 * 24 * 60 * 60
    now = dt_util.as_timestamp(dt_util.utcnow())

    def _cleanup():
        if os.path.exists(path):
            for filename in os.listdir(path):
                file_path = os.path.join(path, filename)
                if os.path.isfile(file_path):
                    try:
                        file_mtime = os.path.getmtime(file_path)
                        if (now - file_mtime) > cutoff_seconds:
                            os.remove(file_path)
                            _LOGGER.info("Deleted expired aviation record: %s", filename)
                    except (OSError, FileNotFoundError) as e:
                        _LOGGER.error("Error managing record %s: %s", filename, e)

    await hass.async_add_executor_job(_cleanup)

async def async_generate_all_ai_briefings(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Trigger AI briefing generation for all airfields."""
    ai_config = entry.data.get("ai_assistant", {})
    agent_id = ai_config.get("ai_agent_entity")
    if not agent_id:
        return

    # Load system prompt from file
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "preflight_brief.txt")
    system_instructions = ""
    if os.path.exists(prompt_path):
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                system_instructions = f.read()
        except Exception as e:
            _LOGGER.error("Error reading preflight_brief.txt: %s", e)
    
    # Generate briefings for each airfield
    for airfield in entry.data.get("airfields", []):
        airfield_name = airfield["name"]
        slug = airfield_name.lower().replace(" ", "_")
        icao = airfield.get("icao_code", "unknown")
        
        # Get current data from our sensors
        da = hass.states.get(f"sensor.{slug}_density_altitude")
        carb = hass.states.get(f"sensor.{slug}_carb_risk")
        wind_speed = hass.states.get(f"sensor.{slug}_weather_wind_speed")
        wind_dir = hass.states.get(f"sensor.{slug}_weather_wind_direction")
        cloud_base = hass.states.get(f"sensor.{slug}_est_cloud_base")
        best_rwy = hass.states.get(f"sensor.{slug}_best_runway")
        
        # Get sunset/sunrise
        sun = hass.states.get("sun.sun")
        next_event = "unknown"
        if sun:
            next_rising = sun.attributes.get("next_rising")
            next_setting = sun.attributes.get("next_setting")
            next_event = f"Next Sunrise: {next_rising}, Next Sunset: {next_setting}"

        user_prompt = (
            f"{system_instructions}\n\n"
            f"### LIVE DATA FOR {airfield_name} ({icao}):\n"
            f"- Wind: {wind_speed.state if wind_speed else 'unknown'}kt at {wind_dir.state if wind_dir else 'unknown'}°\n"
            f"- Recommended Runway: {best_rwy.state if best_rwy else 'unknown'}\n"
            f"- Density Altitude: {da.state if da else 'unknown'} ft\n"
            f"- Est. Cloud Base: {cloud_base.state if cloud_base else 'unknown'} ft\n"
            f"- Carburettor Icing Risk: {carb.state if carb else 'unknown'}\n"
            f"- Solar: {next_event}\n\n"
            f"Please provide the briefing based on this data and your general aviation knowledge."
        )

        try:
            _LOGGER.debug("Requesting AI briefing for %s from %s", airfield_name, agent_id)
            result = await hass.services.async_call(
                "conversation",
                "process",
                {
                    "agent_id": agent_id,
                    "text": user_prompt,
                },
                blocking=True,
                return_response=True
            )
            
            if result and "response" in result:
                try:
                    response_text = result["response"]["speech"]["plain"]["speech"]
                    # Fire event that the sensors are listening for
                    hass.bus.async_fire("hangar_assistant_ai_briefing", {
                        "airfield_name": airfield_name,
                        "text": response_text
                    })
                    _LOGGER.info("Successfully generated AI briefing for %s", airfield_name)
                except (KeyError, TypeError) as e:
                    _LOGGER.error("AI Agent returned an unexpected response format for %s: %s", airfield_name, result)
            else:
                _LOGGER.warning("AI Agent %s returned no response for %s", agent_id, airfield_name)
        except Exception as e:
            _LOGGER.error("Error generating AI briefing for %s: %s", airfield_name, e)

async def async_send_briefing(hass: HomeAssistant, briefing: dict, entry: ConfigEntry) -> None:
    """Compose and send the briefing email."""
    airfield_slug = briefing["airfield_name"].lower().replace(" ", "_")
    aircraft_slug = briefing["aircraft_reg"].lower().replace(" ", "_")
    
    # Fetch current states
    da = hass.states.get(f"sensor.{airfield_slug}_density_altitude")
    carb = hass.states.get(f"sensor.{airfield_slug}_carb_risk")
    roll = hass.states.get(f"sensor.{aircraft_slug}_calculated_ground_roll")
    
    # Get recipient emails from pilot names
    pilot_names = briefing.get("pilots", [])
    all_pilots = entry.data.get("pilots", [])
    recipient_emails = [p["email"] for p in all_pilots if p["name"] in pilot_names]
    
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
        _LOGGER.info("Briefing for %s sent to %s pilots: %s", 
                    briefing["airfield_name"], 
                    len(recipient_emails), 
                    ", ".join(recipient_emails))
    except Exception as e:
        _LOGGER.error("Failed to send briefing: %s", e)