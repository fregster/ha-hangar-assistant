"""Hangar Assistant: Aviation Safety & Compliance for Home Assistant."""
from __future__ import annotations

import json
import logging
import os
import yaml  # type: ignore
import voluptuous as vol
import inspect
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import DOMAIN, PLATFORMS, DEFAULT_RETENTION_MONTHS, DEFAULT_DASHBOARD_VERSION

_LOGGER = logging.getLogger(__name__)

def _load_integration_version() -> str:
    """Load the integration version from manifest.json.
    
    Returns the version string defined in the integration manifest. If the
    manifest cannot be read or the version is missing, a safe fallback of
    "0.0.0" is returned so callers can continue with conservative defaults.
    """
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
    try:
        with open(manifest_path, "r", encoding="utf-8") as manifest_file:
            manifest = json.load(manifest_file)
        version = manifest.get("version", "0.0.0")
        return str(version)
    except (OSError, IOError, json.JSONDecodeError) as error:
        _LOGGER.debug("Unable to read manifest version: %s", error)
    except Exception as error:  # pragma: no cover - unexpected errors
        _LOGGER.error("Unexpected error reading manifest version: %s", error)
    return "0.0.0"


def _extract_major_version(version_value) -> int:
    """Extract the major version component from a Hangar Assistant version string.
    
    Args:
        version_value: A version string in YYYYNN.V.H format or an int.

    Returns:
        The major portion as an integer. Defaults to 0 when parsing fails so
        that upgrade checks degrade gracefully.
    """
    if isinstance(version_value, int):
        return version_value
    try:
        major_segment = str(version_value).split(".")[0]
        return int(major_segment)
    except (ValueError, AttributeError, IndexError):
        return 0


def should_force_dashboard_rebuild(dashboard_info: dict) -> bool:
    """Determine whether the dashboard must be rebuilt.
    
    A rebuild is required when we cannot determine the stored integration
    version (first install) or when the stored major version differs from the
    currently installed integration. This ensures users automatically receive
    dashboard updates on major releases without manual intervention.

    Args:
        dashboard_info: The persisted dashboard metadata from the config entry.

    Returns:
        True when a rebuild is needed, False when the existing dashboard can be
        reused safely.
    """
    stored_major = _extract_major_version(
        dashboard_info.get("integration_version")
        or dashboard_info.get("integration_major")
    )
    if stored_major == 0:
        return True
    return stored_major != INTEGRATION_MAJOR_VERSION


INTEGRATION_VERSION = _load_integration_version()
INTEGRATION_MAJOR_VERSION = _extract_major_version(INTEGRATION_VERSION)

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
        result = await async_create_dashboard(
            hass,
            entry,
            force_rebuild=True,
            reason="service_call",
        )
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

    async def handle_speak_briefing(call: ServiceCall) -> None:
        """Service to speak the current AI pre-flight briefing via TTS.

        Attempts to determine the active airfield slug from the built-in select
        entity (select.hangar_assistant_airfield_selector). If not available,
        auto-detects the first configured briefing sensor. Then uses the TTS
        engine and media player provided in service data, or auto-picks sane
        defaults.

        Service data options (all optional):
            - tts_entity_id: TTS engine entity (e.g., tts.cloud)
            - media_player_entity_id: Target media player (e.g., media_player.living_room)
        """
        # Resolve airfield slug
        slug: str | None = None
        sel = hass.states.get("select.hangar_assistant_airfield_selector")
        if sel and sel.state not in ("unknown", "unavailable", None):
            slug = str(sel.state)
        if not slug:
            # Find first AI briefing sensor
            for state in hass.states.async_all():
                eid = state.entity_id
                if eid.startswith("sensor.") and eid.endswith("_ai_pre_flight_briefing"):
                    slug = eid.replace("sensor.", "").replace("_ai_pre_flight_briefing", "")
                    break

        if not slug:
            _LOGGER.warning("No airfield slug found for AI briefing; cannot speak")
            return

        briefing_state = hass.states.get(f"sensor.{slug}_ai_pre_flight_briefing")
        briefing = (
            briefing_state.attributes.get("briefing") if briefing_state else None
        )
        if not briefing:
            _LOGGER.warning("AI briefing text not available; skipping TTS")
            return

        # Resolve media player target
        media_player = call.data.get("media_player_entity_id")
        if not media_player:
            # Prefer browser-based media players (current device) when available
            browser_candidates: list[str] = []
            for state in hass.states.async_all():
                try:
                    ent_id = state.entity_id
                    if not ent_id.startswith("media_player."):
                        continue
                    attrs = getattr(state, "attributes", {}) or {}
                    name = str(attrs.get("friendly_name", "")).lower()
                    app_name = str(attrs.get("app_name", "")).lower()
                    if (
                        "browser" in ent_id
                        or "browser" in name
                        or app_name == "home assistant"
                    ) and state.state not in ("unknown", "unavailable"):
                        browser_candidates.append(ent_id)
                except Exception:  # pragma: no cover - defensive per-entity
                    continue

            if browser_candidates:
                media_player = browser_candidates[0]
            else:
                # Fallback to first available media player
                for state in hass.states.async_all():
                    if state.entity_id.startswith("media_player.") and state.state not in ("unknown", "unavailable"):
                        media_player = state.entity_id
                        break

        # Resolve TTS engine
        tts_entity = call.data.get("tts_entity_id")
        if not tts_entity:
            for state in hass.states.async_all():
                if state.entity_id.startswith("tts."):
                    tts_entity = state.entity_id
                    break

        if not media_player or not tts_entity:
            _LOGGER.warning(
                "Cannot speak briefing: media_player=%s, tts_entity=%s",
                media_player,
                tts_entity,
            )
            return

        await hass.services.async_call(
            "tts",
            "speak",
            {
                "entity_id": tts_entity,
                "media_player_entity_id": media_player,
                "message": briefing,
            },
            blocking=False,
        )

    # Register the manual cleanup service (await if mocked as coroutine)
    _schema_cleanup = vol.Schema({vol.Optional("retention_months"): cv.positive_int})
    _res_cleanup = hass.services.async_register(DOMAIN, "manual_cleanup", handle_manual_cleanup, schema=_schema_cleanup)
    if inspect.isawaitable(_res_cleanup):
        await _res_cleanup
    
    # Register the dashboard rebuild service
    _schema_rebuild = vol.Schema({})
    _res_rebuild = hass.services.async_register(DOMAIN, "rebuild_dashboard", handle_rebuild_dashboard, schema=_schema_rebuild)
    if inspect.isawaitable(_res_rebuild):
        await _res_rebuild

    # Register the AI briefing refresh service
    _schema_refresh = vol.Schema({})
    _res_refresh = hass.services.async_register(DOMAIN, "refresh_ai_briefings", handle_refresh_ai_briefings, schema=_schema_refresh)
    if inspect.isawaitable(_res_refresh):
        await _res_refresh

    # Register TTS speak briefing service
    _schema_speak = vol.Schema({
        vol.Optional("tts_entity_id"): cv.entity_id,
        vol.Optional("media_player_entity_id"): cv.entity_id,
    })
    _res_speak = hass.services.async_register(DOMAIN, "speak_briefing", handle_speak_briefing, schema=_schema_speak)
    if inspect.isawaitable(_res_speak):
        await _res_speak
    
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hangar Assistant from a config entry."""
    dashboard_info = entry.data.get("dashboard_info", {}) if isinstance(entry.data, dict) else {}
    force_dashboard_rebuild = should_force_dashboard_rebuild(dashboard_info)

    # Create or refresh the dashboard on first setup, major version upgrade, or template change
    await async_create_dashboard(
        hass,
        entry,
        force_rebuild=force_dashboard_rebuild,
        reason="major_version_upgrade" if force_dashboard_rebuild else "startup",
    )

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
        
        # Also run once on startup after sensors are ready
        async def wait_for_sensors_and_brief():
            """Wait for airfield sensors to be available before generating briefings.
            
            Polls for sensor readiness up to 30 seconds with 1-second intervals.
            Proceeds once all airfield density altitude sensors are available or
            timeout expires.
            """
            import asyncio
            airfield_slugs = [
                (af.get("name") or "").lower().replace(" ", "_")
                for af in entry.data.get("airfields", [])
                if isinstance(af, dict) and af.get("name")
            ]
            
            # Wait up to 30 seconds for sensors to become available
            max_wait = 30
            for attempt in range(max_wait):
                # Check if all required sensors are available
                all_ready = True
                for slug in airfield_slugs:
                    sensor_id = f"sensor.{slug}_density_altitude"
                    state = hass.states.get(sensor_id)
                    if not state or state.state in ("unknown", "unavailable"):
                        all_ready = False
                        break
                
                if all_ready:
                    _LOGGER.debug("Sensors ready after %d seconds, generating AI briefings", attempt + 1)
                    await async_generate_all_ai_briefings(hass, entry)
                    return
                
                await asyncio.sleep(1)
            
            # Timeout - proceed anyway but log warning
            _LOGGER.warning(
                "Sensor readiness timeout after %d seconds, generating AI briefings anyway",
                max_wait
            )
            await async_generate_all_ai_briefings(hass, entry)
        
        hass.async_create_task(wait_for_sensors_and_brief())

    return True

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update by reloading the integration."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_create_dashboard(
    hass: HomeAssistant,
    entry: ConfigEntry = None,
    force_rebuild: bool = False,
    reason: str | None = None,
) -> bool:
    """Create or rebuild the Hangar Assistant dashboard from the template.
    
    Args:
        hass: Home Assistant instance.
        entry: Config entry for this integration (optional for service-triggered rebuilds).
        force_rebuild: When True, always regenerate the dashboard from the template.
        reason: Text context for logs (startup, major_version_upgrade, options_flow, service, etc.).

    Returns:
        True when the dashboard was created or refreshed successfully, False on failure.
    """
    
    def _generate_dashboard():
        """Sync function to perform blocking I/O."""
        # Maximum dashboard template size (5MB) to prevent memory exhaustion
        MAX_DASHBOARD_SIZE = 5 * 1024 * 1024
        
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
            
            # Validate template size before loading
            template_size = os.path.getsize(template_path)
            if template_size > MAX_DASHBOARD_SIZE:
                _LOGGER.error(
                    "Dashboard template exceeds maximum size limit: %d bytes (max: %d bytes)",
                    template_size,
                    MAX_DASHBOARD_SIZE
                )
                return False
            
            # Check if dashboard file exists
            dashboards_path = hass.config.path("dashboards")
            dashboard_yaml_path = os.path.join(dashboards_path, "hangar_assistant.yaml")
            
            # Get current dashboard version from config entry
            stored_version = 0
            if entry:
                dashboard_info = entry.data.get("dashboard_info", {})
                try:
                    stored_version = int(dashboard_info.get("version", 0))
                except (TypeError, ValueError):
                    stored_version = 0
            
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
        except (OSError, IOError) as e:
            _LOGGER.error("File system error during dashboard creation: %s", e)
            return False
        except yaml.YAMLError as e:
            _LOGGER.error("YAML parsing error in dashboard template: %s", e)
            return False
        except Exception as e:
            _LOGGER.error("Unexpected error in dashboard file operations: %s", e)
            return False

    # Run the blocking I/O in the executor
    _LOGGER.info(
        "Creating Hangar Assistant dashboard (reason=%s, force=%s)",
        reason or "auto",
        force_rebuild,
    )
    result = await hass.async_add_executor_job(_generate_dashboard)
    
    if not result:
        return False

    try:
        # Update config entry with new dashboard version ONLY if changed
        if entry:
            dashboard_info = entry.data.get("dashboard_info", {})
            try:
                current_stored_version = int(dashboard_info.get("version", 0))
            except (TypeError, ValueError):
                current_stored_version = 0
            stored_major = _extract_major_version(
                dashboard_info.get("integration_version")
                or dashboard_info.get("integration_major")
            )

            if (
                force_rebuild
                or current_stored_version < DEFAULT_DASHBOARD_VERSION
                or stored_major != INTEGRATION_MAJOR_VERSION
            ):
                _LOGGER.debug(
                    "Updating dashboard metadata (reason=%s, stored_version=%s, stored_major=%s)",
                    reason or "auto",
                    current_stored_version,
                    stored_major,
                )
                new_data = dict(entry.data)
                updated_dashboard_info = dict(dashboard_info)
                updated_dashboard_info.update(
                    {
                        "version": DEFAULT_DASHBOARD_VERSION,
                        "last_updated": dt_util.now().isoformat(),
                        "integration_version": INTEGRATION_VERSION,
                        "integration_major": INTEGRATION_MAJOR_VERSION,
                    }
                )
                new_data["dashboard_info"] = updated_dashboard_info
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
    """Logic to delete old PDF declarations from local storage.
    
    Uses os.scandir() for efficient directory traversal with lower memory footprint
    compared to os.listdir(). This is particularly beneficial for large archives
    with hundreds or thousands of PDF files.
    
    Args:
        hass: Home Assistant instance
        months: Retention period in months (files older than this are deleted)
    """
    # Use hass.config.path to ensure cross-platform compatibility
    path = hass.config.path("www/hangar/")
    cutoff_seconds = months * 30.44 * 24 * 60 * 60
    now = dt_util.as_timestamp(dt_util.utcnow())

    def _cleanup():
        if os.path.exists(path):
            # Use scandir() for iterator-based processing (lower memory footprint)
            with os.scandir(path) as entries:
                for entry in entries:
                    if entry.is_file():
                        try:
                            file_mtime = entry.stat().st_mtime
                            if (now - file_mtime) > cutoff_seconds:
                                os.remove(entry.path)
                                _LOGGER.info("Deleted expired aviation record: %s", entry.name)
                        except (OSError, FileNotFoundError) as e:
                            _LOGGER.error("Error managing record %s: %s", entry.name, e)

    await hass.async_add_executor_job(_cleanup)

async def async_generate_all_ai_briefings(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Trigger AI briefing generation for all airfields."""
    ai_config = entry.data.get("ai_assistant", {})
    agent_id = ai_config.get("ai_agent_entity")
    if not agent_id:
        return

    # Load system prompt from file without blocking the event loop
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "preflight_brief.txt")

    def _read_prompt_file() -> str:
        if not os.path.exists(prompt_path):
            return ""
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except (OSError, IOError, UnicodeDecodeError) as e:
            _LOGGER.error("Error reading preflight_brief.txt: %s", e)
            return ""
        except Exception as e:
            _LOGGER.error("Unexpected error reading preflight_brief.txt: %s", e)
            return ""

    system_instructions = await hass.async_add_executor_job(_read_prompt_file)
    
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
        tz = hass.states.get(f"sensor.{slug}_airfield_timezone")
        
        # Get sunset/sunrise
        sun = hass.states.get("sun.sun")
        next_event = "unknown"
        if sun:
            next_rising = sun.attributes.get("next_rising")
            next_setting = sun.attributes.get("next_setting")
            next_event = f"Next Sunrise: {next_rising}, Next Sunset: {next_setting}"

        tz_value = None
        if tz:
            tz_value = tz.state
        if not tz_value:
            tz_value = getattr(hass.config, "time_zone", None) or "unknown"

        user_prompt = (
            f"{system_instructions}\n\n"
            f"### LIVE DATA FOR {airfield_name} ({icao}):\n"
            f"- Wind: {wind_speed.state if wind_speed else 'unknown'}kt at {wind_dir.state if wind_dir else 'unknown'}°\n"
            f"- Recommended Runway: {best_rwy.state if best_rwy else 'unknown'}\n"
            f"- Density Altitude: {da.state if da else 'unknown'} ft\n"
            f"- Est. Cloud Base: {cloud_base.state if cloud_base else 'unknown'} ft\n"
            f"- Carburettor Icing Risk: {carb.state if carb else 'unknown'}\n"
            f"- Local Timezone: {tz_value}\n"
            f"- Solar: {next_event}\n\n"
            f"Please provide the briefing based on this data and your general aviation knowledge."
        )

        # Retry with exponential backoff for AI service failures
        MAX_RETRIES = 3
        BACKOFF_SECONDS = 60
        
        for retry in range(MAX_RETRIES):
            try:
                _LOGGER.debug("Requesting AI briefing for %s from %s (attempt %d/%d)", 
                            airfield_name, agent_id, retry + 1, MAX_RETRIES)
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
                        break  # Success - exit retry loop
                    except (KeyError, TypeError) as e:
                        _LOGGER.error("AI Agent returned an unexpected response format for %s: %s", airfield_name, result)
                        break  # Don't retry format errors
                else:
                    _LOGGER.warning("AI Agent %s returned no response for %s", agent_id, airfield_name)
                    if retry < MAX_RETRIES - 1:
                        # Wait before retry (exponential backoff)
                        import asyncio
                        wait_time = BACKOFF_SECONDS * (2 ** retry)
                        _LOGGER.info("Retrying AI briefing for %s in %d seconds", airfield_name, wait_time)
                        await asyncio.sleep(wait_time)
                    else:
                        _LOGGER.error("AI briefing failed for %s after %d attempts", airfield_name, MAX_RETRIES)
            except Exception as e:
                _LOGGER.error("Error generating AI briefing for %s (attempt %d/%d): %s", 
                            airfield_name, retry + 1, MAX_RETRIES, e)
                if retry < MAX_RETRIES - 1:
                    # Wait before retry (exponential backoff)
                    import asyncio
                    wait_time = BACKOFF_SECONDS * (2 ** retry)
                    _LOGGER.info("Retrying AI briefing for %s in %d seconds", airfield_name, wait_time)
                    await asyncio.sleep(wait_time)
                else:
                    _LOGGER.error("AI briefing failed for %s after %d attempts", airfield_name, MAX_RETRIES)

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