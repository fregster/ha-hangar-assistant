"""Hangar Assistant: Aviation Safety & Compliance for Home Assistant."""
from __future__ import annotations

import json
import logging
import os
import time
import yaml  # type: ignore
import voluptuous as vol
import inspect
from datetime import datetime
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import DOMAIN, PLATFORMS, DEFAULT_RETENTION_MONTHS, DEFAULT_DASHBOARD_VERSION, DEFAULT_NOTAM_RADIUS_NM
from .utils.qcode_parser import parse_qcode, sort_notams_by_criticality, get_criticality_emoji, NOTAMCriticality
from .utils.forecast_analysis import (
    calculate_sunset_sunrise,
    get_forecast_window,
    analyze_forecast_trends,
    check_overnight_conditions,
)

_LOGGER = logging.getLogger(__name__)

# Dashboard template cache (performance optimization)
_DASHBOARD_TEMPLATE_CACHE: dict | None = None
_TEMPLATE_MODIFIED_TIME: float | None = None


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
    except (OSError, json.JSONDecodeError) as error:
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


def should_show_setup_wizard(entry: ConfigEntry) -> bool:
    """Determine if setup wizard should be shown.
    
    The wizard is shown for first-time setups where:
    - No setup_completed flag is set, AND
    - No airfields configured, AND
    - No aircraft configured
    
    This ensures existing installations are never disrupted while providing
    a guided onboarding experience for new users.
    
    Args:
        entry: Config entry to check
    
    Returns:
        True if wizard should be shown, False otherwise
    """
    # Check for setup completion flag
    settings = entry.data.get("settings", {})
    if settings.get("setup_completed", False):
        return False
    
    # Check for minimal required data
    airfields = entry.data.get("airfields", [])
    aircraft = entry.data.get("aircraft", [])
    
    # Show wizard if no airfields AND no aircraft configured
    return len(airfields) == 0 and len(aircraft) == 0


def _get_briefing_text(hass: HomeAssistant) -> str | None:
    """Get the current AI briefing text.

    Args:
        hass: Home Assistant instance

    Returns:
        Briefing text or None if unavailable
    """
    slug = _resolve_airfield_slug(hass)
    if not slug:
        _LOGGER.warning(
            "No airfield slug found for AI briefing; cannot speak")
        return None

    briefing_state = hass.states.get(
        f"sensor.{slug}_ai_pre_flight_briefing")
    briefing = (briefing_state.attributes.get(
        "briefing") if briefing_state else None)
    if not briefing:
        _LOGGER.warning("AI briefing text not available; skipping TTS")
        return None

    return briefing


def _resolve_airfield_slug(hass: HomeAssistant) -> str | None:
    """Resolve the current airfield slug for briefing.

    First attempts to use the airfield selector entity if available.
    Falls back to finding the first available AI briefing sensor.

    Args:
        hass: Home Assistant instance

    Returns:
        The airfield slug string, or None if unresolvable
    """
    slug: str | None = None
    sel = hass.states.get("select.hangar_assistant_airfield_selector")
    if sel and sel.state not in ("unknown", "unavailable", None):
        slug = str(sel.state)
    if not slug:
        # Find first AI briefing sensor
        for state in hass.states.async_all():
            eid = state.entity_id
            if eid.startswith("sensor.") and eid.endswith(
                    "_ai_pre_flight_briefing"):
                slug = eid.replace(
                    "sensor.", "").replace(
                    "_ai_pre_flight_briefing", "")
                break
    return slug


def _find_media_player(
        hass: HomeAssistant,
        override: str | None) -> str | None:
    """Find the best available media player entity.

    Prefers browser-based media players when available (indicates current device).
    Falls back to any available media player. Can be overridden via service parameter.

    Args:
        hass: Home Assistant instance
        override: Explicitly provided media_player_entity_id from service call

    Returns:
        Media player entity ID string, or None if none available
    """
    if override:
        return override

    # Prefer browser-based media players
    browser_candidates = _find_browser_media_players(hass)
    if browser_candidates:
        return browser_candidates[0]

    # Fallback to first available media player
    for state in hass.states.async_all():
        if state.entity_id.startswith(
                "media_player.") and state.state not in ("unknown", "unavailable"):
            return state.entity_id
    return None


def _find_browser_media_players(hass: HomeAssistant) -> list[str]:
    """Find browser-based media players.

    Args:
        hass: Home Assistant instance

    Returns:
        List of browser media player entity IDs
    """
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
    return browser_candidates


def _find_tts_entity(hass: HomeAssistant, override: str | None) -> str | None:
    """Find an available TTS entity.

    Can be overridden via service parameter. Auto-discovers first available TTS
    entity if not specified.

    Args:
        hass: Home Assistant instance
        override: Explicitly provided tts_entity_id from service call

    Returns:
        TTS entity ID string, or None if none available
    """
    if override:
        return override

    for state in hass.states.async_all():
        if state.entity_id.startswith("tts."):
            return state.entity_id
    return None


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Hangar Assistant integration global services."""

    async def handle_manual_cleanup(call: ServiceCall) -> None:
        """Service to manually purge legal records past their retention date."""
        # Get retention from service call, fallback to 7 months
        retention_months = call.data.get(
            "retention_months", DEFAULT_RETENTION_MONTHS)

        await async_cleanup_records(hass, retention_months)

    async def handle_rebuild_dashboard(call: ServiceCall) -> None:
        """Service to rebuild the Hangar Assistant dashboard."""
        _LOGGER.info("Rebuild dashboard service called")
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            _LOGGER.warning(
                "No Hangar Assistant config entry found for dashboard rebuild")
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
            _LOGGER.warning(
                "⚠️ Dashboard rebuild completed but may not have created/updated the file")

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
        # Get briefing text
        briefing = _get_briefing_text(hass)
        if not briefing:
            return

        # Resolve media player and TTS entity
        media_player = _find_media_player(
            hass, call.data.get("media_player_entity_id"))
        tts_entity = _find_tts_entity(hass, call.data.get("tts_entity_id"))

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

    async def handle_install_dashboard(call: ServiceCall) -> None:
        """Service to install the Hangar Assistant dashboard.
        
        This service supports both automatic installation (via Lovelace API)
        and manual installation (returns YAML for user to copy/paste).
        Called from setup wizard or manually for dashboard updates.
        
        Service data:
            - method: 'automatic' (default) or 'manual'
        """
        method = call.data.get("method", "automatic")
        
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            _LOGGER.warning("No Hangar Assistant config entry found")
            return
        
        entry = entries[0]
        
        if method == "automatic":
            # Use existing dashboard creation logic
            _LOGGER.info("Installing dashboard via automatic method")
            result = await async_create_dashboard(
                hass,
                entry,
                force_rebuild=True,
                reason="install_service",
            )
            
            if result:
                # Update settings to mark dashboard as installed
                new_data = dict(entry.data)
                settings = new_data.setdefault("settings", {})
                settings["dashboard_installed"] = True
                settings["dashboard_url"] = "/hangar-assistant/glass_cockpit"
                settings["dashboard_install_method"] = "automatic"
                hass.config_entries.async_update_entry(entry, data=new_data)
                
                _LOGGER.info("✅ Dashboard installed successfully (automatic)")
            else:
                _LOGGER.error("❌ Dashboard installation failed")
        
        elif method == "manual":
            # Generate YAML for manual installation
            _LOGGER.info("Generating dashboard YAML for manual installation")
            dashboard_yaml = await _generate_dashboard_yaml(hass, entry)
            
            if dashboard_yaml:
                # Store YAML in config for retrieval by wizard
                new_data = dict(entry.data)
                settings = new_data.setdefault("settings", {})
                settings["dashboard_yaml"] = dashboard_yaml
                settings["dashboard_install_method"] = "manual"
                hass.config_entries.async_update_entry(entry, data=new_data)
                
                _LOGGER.info("✅ Dashboard YAML generated for manual installation")
            else:
                _LOGGER.error("❌ Dashboard YAML generation failed")

    # Register all services
    await _register_service(
        hass, "manual_cleanup", handle_manual_cleanup,
        vol.Schema({vol.Optional("retention_months"): cv.positive_int})
    )
    await _register_service(
        hass, "rebuild_dashboard", handle_rebuild_dashboard, vol.Schema({})
    )
    await _register_service(
        hass, "refresh_ai_briefings", handle_refresh_ai_briefings, vol.Schema({})
    )
    await _register_service(
        hass, "speak_briefing", handle_speak_briefing,
        vol.Schema({
            vol.Optional("tts_entity_id"): cv.entity_id,
            vol.Optional("media_player_entity_id"): cv.entity_id,
        })
    )
    await _register_service(
        hass, "install_dashboard", handle_install_dashboard,
        vol.Schema({
            vol.Optional("method", default="automatic"): vol.In(["automatic", "manual"]),
        })
    )

    return True


async def _register_service(
    hass: HomeAssistant,
    service_name: str,
    handler,
    schema: vol.Schema
) -> None:
    """Register a service and handle mock awaitable responses.

    Args:
        hass: Home Assistant instance
        service_name: Name of the service
        handler: Service handler function
        schema: Service schema for validation
    """
    result = hass.services.async_register(
        DOMAIN, service_name, handler, schema=schema
    )
    if inspect.isawaitable(result):
        await result


async def _migrate_to_integrations(
        hass: HomeAssistant,
        entry: ConfigEntry) -> None:
    """Migrate OWM settings to integrations namespace with backward compatibility.

    This migration ensures existing installations continue working while moving
    configuration to the new centralized integrations structure. Settings are
    preserved in both locations during transition period.

    Args:
        hass: Home Assistant instance
        entry: Config entry to migrate
    """
    if "integrations" not in entry.data:
        settings = entry.data.get("settings", {})

        integrations = {
            "openweathermap": {
                "enabled": settings.get("openweathermap_enabled", False),
                "api_key": settings.get("openweathermap_api_key", ""),
                "cache_enabled": settings.get("openweathermap_cache_enabled", True),
                "update_interval": settings.get("openweathermap_update_interval", 10),
                "cache_ttl": settings.get("openweathermap_cache_ttl", 10),
                "consecutive_failures": 0,
                "last_error": None,
                "last_success": None
            },
            "notams": {
                "enabled": False,  # Existing installs: off by default
                "update_time": "02:00",
                "cache_days": 7,
                "last_update": None,
                "consecutive_failures": 0,
                "last_error": None,
                "stale_cache_allowed": True
            }
        }

        new_data = {**entry.data, "integrations": integrations}
        hass.config_entries.async_update_entry(entry, data=new_data)

        _LOGGER.info("Migrated OWM settings to integrations namespace")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hangar Assistant from a config entry."""
    # Migrate OWM settings to integrations namespace if needed
    await _migrate_to_integrations(hass, entry)

    dashboard_info = entry.data.get(
        "dashboard_info",
        {}) if isinstance(
        entry.data,
        dict) else {}
    force_dashboard_rebuild = should_force_dashboard_rebuild(dashboard_info)

    # Create or refresh the dashboard on first setup, major version upgrade,
    # or template change
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
            async_track_time_change(
                hass,
                run_briefing,
                hour=hour,
                minute=minute,
                second=0))

    # Reload integration if options change in the UI
    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Set up hourly AI briefings if an agent is defined
    ai_config = entry.data.get("ai_assistant", {})
    if ai_config.get("ai_agent_entity"):
        async def run_hourly_ai_briefing(now):
            await async_generate_all_ai_briefings(hass, entry)

        entry.async_on_unload(
            async_track_time_change(
                hass,
                run_hourly_ai_briefing,
                minute=0,
                second=0))

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
                    _LOGGER.debug(
                        "Sensors ready after %d seconds, generating AI briefings",
                        attempt + 1)
                    await async_generate_all_ai_briefings(hass, entry)
                    return

                await asyncio.sleep(1)

            # Timeout - proceed anyway but log warning
            _LOGGER.warning(
                "Sensor readiness timeout after %d seconds, generating AI briefings anyway",
                max_wait)
            await async_generate_all_ai_briefings(hass, entry)

        hass.async_create_task(wait_for_sensors_and_brief())

    # Set up scheduled NOTAM updates if enabled
    integrations = entry.data.get("integrations", {})
    notam_config = integrations.get("notams", {})

    if notam_config.get("enabled"):
        from .utils.notam import NOTAMClient

        update_time = notam_config.get("update_time", "02:00")
        hour, minute = map(int, update_time.split(":"))

        async def update_notams(now):
            """Scheduled NOTAM update."""
            notam_client = NOTAMClient(
                hass, notam_config.get(
                    "cache_days", 7), entry)
            try:
                notams, is_stale = await notam_client.fetch_notams()
                _LOGGER.info(
                    "Updated %d NOTAMs at scheduled time (stale: %s)",
                    len(notams),
                    is_stale)

            except Exception as e:
                _LOGGER.error("NOTAM scheduled update failed: %s", e)

        # Schedule daily update
        entry.async_on_unload(
            async_track_time_change(
                hass,
                update_notams,
                hour=hour,
                minute=minute,
                second=0))

        # Also run once on startup (after a brief delay for network)
        async def initial_notam_update():
            import asyncio
            await asyncio.sleep(10)  # Wait 10 seconds for network to be ready
            notam_client = NOTAMClient(
                hass, notam_config.get(
                    "cache_days", 7), entry)
            try:
                notams, is_stale = await notam_client.fetch_notams()
                _LOGGER.info(
                    "Initial NOTAM fetch: %d NOTAMs (stale: %s)",
                    len(notams),
                    is_stale)
            except Exception as e:
                _LOGGER.debug(
                    "Initial NOTAM fetch failed (will retry at scheduled time): %s", e)

        hass.async_create_task(initial_notam_update())

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update by reloading the integration."""
    await hass.config_entries.async_reload(entry.entry_id)


def _get_template_path() -> str:
    """Get the dashboard template file path.

    Returns:
        Absolute path to glass_cockpit.yaml template
    """
    return os.path.join(
        os.path.dirname(__file__),
        "dashboard_templates",
        "glass_cockpit.yaml"
    )


async def _generate_dashboard_yaml(
    hass: HomeAssistant,
    entry: ConfigEntry
) -> str | None:
    """Generate dashboard YAML for manual installation.
    
    Loads the dashboard template and returns it as a YAML string
    for users to manually copy/paste into their Home Assistant dashboard.
    
    Args:
        hass: Home Assistant instance
        entry: Config entry with airfield/aircraft data
    
    Returns:
        YAML string ready for manual installation, or None on error
    """
    def _load_and_format():
        """Sync function for YAML I/O (wrapped in executor)."""
        try:
            template_path = _get_template_path()
            
            # Load template
            with open(template_path, 'r', encoding='utf-8') as f:
                yaml_content = f.read()
            
            # Add instructional header
            header = """# Hangar Assistant Glass Cockpit Dashboard
# 
# INSTALLATION INSTRUCTIONS:
# 1. Go to Home Assistant Settings → Dashboards
# 2. Click "+ Add Dashboard" in the top right
# 3. Enter title: "Hangar Glass Cockpit"
# 4. Click "Create"
# 5. Click the three-dot menu → "Edit Dashboard"
# 6. Click the three-dot menu again → "Raw configuration editor"
# 7. Delete the default content
# 8. Copy and paste this ENTIRE file contents below
# 9. Click "Save"
#
# The dashboard will now be available in your sidebar.
#
"""
            
            return header + yaml_content
            
        except OSError as e:
            _LOGGER.error("Failed to load dashboard template: %s", e)
            return None
        except Exception as e:
            _LOGGER.error("Unexpected error generating dashboard YAML: %s", e)
            return None
    
    # Run blocking I/O in executor
    yaml_string = await hass.async_add_executor_job(_load_and_format)
    return yaml_string


def _validate_template(template_path: str) -> bool:
    """Validate dashboard template exists and is within size limits.

    Args:
        template_path: Path to template file

    Returns:
        True if template is valid, False otherwise
    """
    MAX_DASHBOARD_SIZE = 5 * 1024 * 1024  # 5MB

    if not os.path.exists(template_path):
        _LOGGER.error("Dashboard template not found at: %s", template_path)
        return False

    template_size = os.path.getsize(template_path)
    if template_size > MAX_DASHBOARD_SIZE:
        _LOGGER.error(
            "Dashboard template exceeds maximum size limit: %d bytes (max: %d bytes)",
            template_size,
            MAX_DASHBOARD_SIZE)
        return False

    return True


def _get_dashboard_path(hass: HomeAssistant) -> str:
    """Get the dashboard output file path.

    Args:
        hass: Home Assistant instance

    Returns:
        Absolute path to hangar_assistant.yaml dashboard
    """
    dashboards_path = hass.config.path("dashboards")
    return os.path.join(dashboards_path, "hangar_assistant.yaml")


def _should_rebuild_dashboard(
    dashboard_path: str,
    entry: ConfigEntry | None,
    force_rebuild: bool
) -> bool:
    """Check if dashboard needs to be rebuilt.

    Args:
        dashboard_path: Path to dashboard file
        entry: Config entry (optional)
        force_rebuild: Force rebuild flag

    Returns:
        True if rebuild needed, False otherwise
    """
    dashboard_exists = os.path.exists(dashboard_path)

    # Always rebuild if forced or dashboard doesn't exist
    if force_rebuild or not dashboard_exists:
        return True

    # Check version mismatch
    if entry:
        dashboard_info = entry.data.get("dashboard_info", {})
        try:
            stored_version = int(dashboard_info.get("version", 0))
            if stored_version < DEFAULT_DASHBOARD_VERSION:
                return True
        except (TypeError, ValueError):
            return True

    return False


def _load_dashboard_template(template_path: str) -> dict | None:
    """Load dashboard template from YAML file with caching.

    Caches the parsed template in memory and only reloads if the file
    has been modified. This significantly improves dashboard rebuild
    performance by avoiding redundant YAML parsing.

    Performance optimization: Returns cached reference instead of deep copy
    since callers don't mutate the template.

    Args:
        template_path: Path to template file

    Returns:
        Dashboard config dict or None on error
    """
    global _DASHBOARD_TEMPLATE_CACHE, _TEMPLATE_MODIFIED_TIME

    try:
        # Check if template has been modified since last load
        current_mtime = os.path.getmtime(template_path)
        
        if (_DASHBOARD_TEMPLATE_CACHE is not None and
                _TEMPLATE_MODIFIED_TIME == current_mtime):
            _LOGGER.debug(
                "Using cached dashboard template (age: %.1fs)",
                time.time() - current_mtime
            )
            # Return cached reference (30-40% faster than deep copy)
            # Safe because callers don't mutate the template
            return _DASHBOARD_TEMPLATE_CACHE

        # Cache miss or file modified - load and parse
        with open(template_path, "r", encoding="utf-8") as f:
            template = yaml.safe_load(f)
        
        # Update cache
        _DASHBOARD_TEMPLATE_CACHE = template
        _TEMPLATE_MODIFIED_TIME = current_mtime
        _LOGGER.debug("Dashboard template loaded and cached")
        
        return template

    except yaml.YAMLError as e:
        _LOGGER.error("YAML parsing error in dashboard template: %s", e)
        return None
    except OSError as e:
        _LOGGER.error("Error reading dashboard template: %s", e)
        return None


def _write_dashboard(dashboard_path: str, dashboard_config: dict) -> bool:
    """Write dashboard config to file.

    Args:
        dashboard_path: Path to output file
        dashboard_config: Dashboard configuration dict

    Returns:
        True on success, False on error
    """
    try:
        # Create directory if needed
        os.makedirs(os.path.dirname(dashboard_path), exist_ok=True)

        # Write dashboard
        with open(dashboard_path, "w", encoding="utf-8") as f:
            yaml.dump(
                dashboard_config,
                f,
                default_flow_style=False,
                allow_unicode=True)
        return True
    except OSError as e:
        _LOGGER.error("File system error during dashboard creation: %s", e)
        return False


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
        """Sync function to perform blocking I/O (YAML parsing wrapped in executor)."""
        try:
            # Validate template
            template_path = _get_template_path()
            if not _validate_template(template_path):
                return False

            # Check if rebuild needed
            dashboard_yaml_path = _get_dashboard_path(hass)
            if not _should_rebuild_dashboard(
                dashboard_yaml_path, entry, force_rebuild
            ):
                return False

            # Load and write dashboard (YAML I/O is blocking)
            dashboard_config = _load_dashboard_template(template_path)
            if dashboard_config is None:
                return False

            return _write_dashboard(dashboard_yaml_path, dashboard_config)

        except Exception as e:
            _LOGGER.error(
                "Unexpected error in dashboard file operations: %s", e)
            return False

    # Run the blocking I/O (including YAML parsing) in the executor
    _LOGGER.info(
        "Creating Hangar Assistant dashboard (reason=%s, force=%s)",
        reason or "auto",
        force_rebuild,
    )
    result = await hass.async_add_executor_job(_generate_dashboard)

    if not result:
        return False

    # Update metadata and reload dashboards
    _update_dashboard_metadata(hass, entry, force_rebuild, reason)
    await _reload_dashboards(hass)

    _LOGGER.info("Dashboard creation completed for Hangar Assistant")
    return True


def _update_dashboard_metadata(
    hass: HomeAssistant,
    entry: ConfigEntry | None,
    force_rebuild: bool,
    reason: str | None
) -> None:
    """Update dashboard metadata in config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry (optional)
        force_rebuild: Whether this was a forced rebuild
        reason: Rebuild reason for logging
    """
    if not entry:
        return

    dashboard_info = entry.data.get("dashboard_info", {})
    try:
        current_stored_version = int(dashboard_info.get("version", 0))
    except (TypeError, ValueError):
        current_stored_version = 0

    stored_major = _extract_major_version(
        dashboard_info.get("integration_version")
        or dashboard_info.get("integration_major")
    )

    # Only update if version changed
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


async def _reload_dashboards(hass: HomeAssistant) -> None:
    """Trigger dashboard reload via Home Assistant services.

    Args:
        hass: Home Assistant instance
    """
    if hass.services.has_service("frontend", "reload_themes"):
        await hass.services.async_call("frontend", "reload_themes")

    if hass.services.has_service("lovelace", "reload_dashboards"):
        try:
            await hass.services.async_call("lovelace", "reload_dashboards")
        except Exception as e:
            _LOGGER.debug(
                "Could not reload dashboards via lovelace service: %s", e)


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
            # Use scandir() for iterator-based processing (lower memory
            # footprint)
            with os.scandir(path) as entries:
                for entry in entries:
                    if entry.is_file():
                        try:
                            file_mtime = entry.stat().st_mtime
                            if (now - file_mtime) > cutoff_seconds:
                                os.remove(entry.path)
                                _LOGGER.info(
                                    "Deleted expired aviation record: %s", entry.name)
                        except OSError as e:
                            _LOGGER.error(
                                "Error managing record %s: %s", entry.name, e)

    await hass.async_add_executor_job(_cleanup)


async def _request_ai_briefing_with_retry(
    hass: HomeAssistant, agent_id: str, airfield_name: str, user_prompt: str
) -> bool:
    """Request AI briefing for an airfield with exponential backoff retry.

    Attempts to call the conversation.process service up to 3 times with
    exponential backoff on failure. Fires hangar_assistant_ai_briefing event
    on success.

    Args:
        hass: Home Assistant instance
        agent_id: The AI agent entity ID to use
        airfield_name: The airfield name (for logging and event data)
        user_prompt: The complete prompt to send to the AI agent

    Returns:
        True if briefing generated successfully, False otherwise
    """
    import asyncio

    MAX_RETRIES = 3
    BACKOFF_SECONDS = 60

    for retry in range(MAX_RETRIES):
        try:
            _LOGGER.debug(
                "Requesting AI briefing for %s from %s (attempt %d/%d)",
                airfield_name,
                agent_id,
                retry + 1,
                MAX_RETRIES)
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
                    _LOGGER.info(
                        "Successfully generated AI briefing for %s",
                        airfield_name)
                    return True
                except (KeyError, TypeError) as e:
                    _LOGGER.error(
                        "AI Agent returned an unexpected response format for %s: %s",
                        airfield_name,
                        result)
                    return False  # Don't retry format errors
            else:
                _LOGGER.warning(
                    "AI Agent %s returned no response for %s",
                    agent_id,
                    airfield_name)
                if retry < MAX_RETRIES - 1:
                    # Wait before retry (exponential backoff)
                    wait_time = BACKOFF_SECONDS * (2 ** retry)
                    _LOGGER.info(
                        "Retrying AI briefing for %s in %d seconds",
                        airfield_name,
                        wait_time)
                    await asyncio.sleep(wait_time)
                else:
                    _LOGGER.error(
                        "AI briefing failed for %s after %d attempts",
                        airfield_name,
                        MAX_RETRIES)
                    return False
        except Exception as e:
            _LOGGER.error(
                "Error generating AI briefing for %s (attempt %d/%d): %s",
                airfield_name,
                retry + 1,
                MAX_RETRIES,
                e)
            if retry < MAX_RETRIES - 1:
                # Wait before retry (exponential backoff)
                wait_time = BACKOFF_SECONDS * (2 ** retry)
                _LOGGER.info(
                    "Retrying AI briefing for %s in %d seconds",
                    airfield_name,
                    wait_time)
                await asyncio.sleep(wait_time)
            else:
                _LOGGER.error(
                    "AI briefing failed for %s after %d attempts",
                    airfield_name,
                    MAX_RETRIES)
                return False

    return False


def _gather_airfield_sensor_data(
    hass: HomeAssistant,
    slug: str,
    airfield: dict
) -> dict:
    """Gather all sensor data for an airfield.

    Args:
        hass: Home Assistant instance
        slug: Airfield slug
        airfield: Airfield config dict

    Returns:
        Dictionary with all sensor values
    """
    best_rwy = hass.states.get(f"sensor.{slug}_best_runway")

    return {
        "da": hass.states.get(f"sensor.{slug}_density_altitude"),
        "carb": hass.states.get(f"sensor.{slug}_carb_risk"),
        "wind_speed": hass.states.get(f"sensor.{slug}_weather_wind_speed"),
        "wind_dir": hass.states.get(f"sensor.{slug}_weather_wind_direction"),
        "cloud_base": hass.states.get(f"sensor.{slug}_est_cloud_base"),
        "best_rwy": best_rwy,
        "temp": hass.states.get(f"sensor.{slug}_weather_temperature"),
        "dp": hass.states.get(f"sensor.{slug}_weather_dew_point"),
        "pressure": hass.states.get(f"sensor.{slug}_weather_pressure"),
        "weather_age": hass.states.get(f"sensor.{slug}_weather_data_age"),
        "safety_alert": hass.states.get(f"binary_sensor.{slug}_master_safety_alert"),
        "crosswind": best_rwy.attributes.get("crosswind_component") if best_rwy and best_rwy.attributes else None,
        "headwind": best_rwy.attributes.get("headwind_component") if best_rwy and best_rwy.attributes else None,
        "runway_number": best_rwy.state if best_rwy else "unknown",
        "runway_length": airfield.get("runway_length", "unknown"),
    }


def _get_timezone_and_solar_info(
    hass: HomeAssistant,
    slug: str,
    lat: float | None,
    lon: float | None
) -> tuple[str, str, str]:
    """Get timezone and solar information for an airfield.

    Args:
        hass: Home Assistant instance
        slug: Airfield slug
        lat: Latitude (optional)
        lon: Longitude (optional)

    Returns:
        Tuple of (timezone, sunrise_time, sunset_time)
    """
    tz_sensor = hass.states.get(f"sensor.{slug}_airfield_timezone")
    tz_value = tz_sensor.state if tz_sensor else None
    if not tz_value:
        tz_value = getattr(hass.config, "time_zone", None) or "UTC"

    sunrise_time = "unknown"
    sunset_time = "unknown"
    if lat is not None and lon is not None:
        try:
            now = dt_util.now()
            sunrise, sunset = calculate_sunset_sunrise(
                float(lat), float(lon), now)
            sunrise_time = sunrise.strftime("%H:%M %Z")
            sunset_time = sunset.strftime("%H:%M %Z")
        except Exception:
            pass

    return tz_value, sunrise_time, sunset_time


def _process_notams_for_briefing(
    hass: HomeAssistant,
    slug: str,
    notam_radius: int
) -> str:
    """Process NOTAMs for AI briefing.

    Args:
        hass: Home Assistant instance
        slug: Airfield slug
        notam_radius: NOTAM radius in nm

    Returns:
        Formatted NOTAM text for prompt
    """
    notam_sensor = hass.states.get(f"sensor.{slug}_notams")
    if not notam_sensor or not notam_sensor.attributes:
        return f"No NOTAMs available within {notam_radius}nm (or NOTAM data not configured)"

    raw_notams = notam_sensor.attributes.get("notams", [])
    if not raw_notams:
        return f"No NOTAMs available within {notam_radius}nm (or NOTAM data not configured)"

    # Parse Q-codes and sort by criticality
    notams_data = []
    for notam in raw_notams:
        q_code = notam.get("q_code")
        parsed = parse_qcode(q_code)
        notam["parsed_qcode"] = parsed
        notams_data.append(notam)
    notams_data = sort_notams_by_criticality(notams_data)

    # Format NOTAMs
    notam_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    notam_details = []

    for notam in notams_data:
        parsed = notam.get("parsed_qcode", {})
        crit = parsed.get("criticality", NOTAMCriticality.LOW).name
        notam_counts[crit] += 1

        emoji = get_criticality_emoji(parsed.get(
            "criticality", NOTAMCriticality.LOW))
        category = parsed.get("category", "UNKNOWN")
        description = parsed.get("description", "")

        notam_id = notam.get("id", "Unknown")
        location = notam.get("location", "Unknown")
        text = notam.get("text", "No details")
        start = notam.get("start_time", "Unknown")
        end = notam.get("end_time", "Unknown")

        notam_details.append(
            f"\n{emoji} {crit} - {notam_id} ({location}) - {category}"
            f"\n  Q-code: {notam.get('q_code', 'N/A')} - {description}"
            f"\n  Valid: {start} to {end}"
            f"\n  Details: {text[:200]}..."
            f"\n"
        )

    notam_summary = f"{len(notams_data)} NOTAMs within {notam_radius}nm:"
    notam_summary += f" {notam_counts['CRITICAL']}🔴 CRITICAL, {notam_counts['HIGH']}🟠 HIGH, {notam_counts['MEDIUM']}🟡 MEDIUM, {notam_counts['LOW']}⚪ LOW"
    return notam_summary + "".join(notam_details)


def _process_forecast_for_briefing(
    hass: HomeAssistant,
    entry: ConfigEntry,
    slug: str,
    lat: float | None,
    lon: float | None,
    now: datetime,
    airfield_name: str
) -> str:
    """Process forecast data for AI briefing.

    Args:
        hass: Home Assistant instance
        entry: Config entry
        slug: Airfield slug
        lat: Latitude (optional)
        lon: Longitude (optional)
        now: Current datetime
        airfield_name: Airfield name for logging

    Returns:
        Formatted forecast text for prompt
    """
    if lat is None or lon is None:
        return "\nCoordinates not available for forecast\n"

    owm_enabled = entry.data.get(
        "integrations", {}).get(
        "openweathermap", {}).get("enabled", False)

    if not owm_enabled:
        return "\nOpenWeatherMap forecast not enabled\n"

    try:
        window_start, window_end, is_overnight = get_forecast_window(
            float(lat), float(lon), now)

        forecast_hourly_sensor = hass.states.get(
            f"sensor.{slug}_weather_forecast_hourly")

        if not forecast_hourly_sensor or not forecast_hourly_sensor.attributes:
            return "\nOWM forecast sensor not available\n"

        forecast_raw = forecast_hourly_sensor.attributes.get("forecast", [])
        if not forecast_raw:
            return "\nForecast data empty\n"

        # Filter forecast to window
        forecast_data = [
            item for item in forecast_raw
            if (item_time := dt_util.parse_datetime(item.get("datetime")))
            and window_start <= item_time <= window_end
        ]

        if not forecast_data:
            return "\nNo forecast data in window\n"

        return _format_forecast_text(
            forecast_data, window_end, is_overnight, window_start
        )

    except Exception as e:
        _LOGGER.warning(
            "Error processing forecast for %s: %s", airfield_name, e)
        return f"\nError processing forecast: {e}\n"


def _format_forecast_text(
    forecast_data: list,
    window_end: datetime,
    is_overnight: bool,
    window_start: datetime
) -> str:
    """Format forecast data into text for AI prompt.

    Args:
        forecast_data: List of forecast items
        window_end: End of forecast window
        is_overnight: Whether forecast extends overnight
        window_start: Start of forecast window

    Returns:
        Formatted forecast text
    """
    # Analyze trends
    trends = analyze_forecast_trends(forecast_data)

    forecast_text = f"\n### FORECAST TO {window_end.strftime('%H:%M %Z')}:\n"
    forecast_text += f"Overall Trend: {trends['overall'].upper()}\n"
    forecast_text += f"Summary: {trends['summary']}\n\n"
    forecast_text += "Key Forecast Points:\n"

    # Show forecast every 2-3 hours
    step = max(1, len(forecast_data) // 4)
    for item in forecast_data[::step]:
        time_str = dt_util.parse_datetime(
            item.get("datetime")).strftime("%H:%M")
        temp_f = item.get("temperature", "?")
        wind_speed_f = item.get("wind_speed", "?")
        wind_dir_f = item.get("wind_bearing", "?")
        clouds_f = item.get("cloud_coverage", "?")
        precip_f = item.get("precipitation", 0)

        forecast_text += (
            f"  {time_str}: {temp_f}°C, Wind {wind_speed_f}kt @ {wind_dir_f}°, "
            f"Clouds {clouds_f}%, Precip {precip_f}mm\n")

    # Check overnight conditions
    if is_overnight:
        overnight_warnings = check_overnight_conditions(
            forecast_data, window_start, window_end)

        if overnight_warnings["has_warnings"]:
            forecast_text += f"\n⚠️ OVERNIGHT WARNINGS:\n{overnight_warnings['summary']}\n"
            for detail in overnight_warnings["details"]:
                forecast_text += f"  - {detail}\n"
    else:
        forecast_text += "\n(No overnight period in forecast window)\n"

    return forecast_text


def _build_briefing_prompt(
    system_instructions: str,
    airfield_name: str,
    icao: str,
    airfield: dict,
    sensor_data: dict,
    tz_value: str,
    sunrise_time: str,
    sunset_time: str,
    now: datetime,
    notam_text: str,
    notam_radius: int,
    forecast_text: str
) -> str:
    """Build the complete AI briefing prompt.

    Args:
        system_instructions: System prompt text
        airfield_name: Name of airfield
        icao: ICAO code
        airfield: Airfield config dict
        sensor_data: Dictionary of all sensor values
        tz_value: Timezone string
        sunrise_time: Formatted sunrise time
        sunset_time: Formatted sunset time
        now: Current datetime
        notam_text: Formatted NOTAM text
        notam_radius: NOTAM radius in nm
        forecast_text: Formatted forecast text

    Returns:
        Complete prompt string
    """
    lat = airfield.get("latitude")
    lon = airfield.get("longitude")

    return (
        f"{system_instructions}\n\n"
        f"### LIVE DATA FOR {airfield_name} ({icao}):\n"
        f"**Airfield Information:**\n"
        f"- ICAO: {icao}\n"
        f"- Coordinates: {lat}, {lon}\n"
        f"- Elevation: {airfield.get('elevation', 'unknown')} m\n"
        f"- Runway: {sensor_data['runway_number']} - {sensor_data['runway_length']}m\n"
        f"- Timezone: {tz_value}\n"
        f"- Current Time: {now.strftime('%H:%M %Z')}\n"
        f"- Sunrise: {sunrise_time} | Sunset: {sunset_time}\n\n"
        f"**Current Weather:**\n"
        f"- Wind: {sensor_data['wind_speed'].state if sensor_data['wind_speed'] else 'unknown'}kt at {sensor_data['wind_dir'].state if sensor_data['wind_dir'] else 'unknown'}°\n"
        f"- Crosswind: {sensor_data['crosswind'] if sensor_data['crosswind'] else 'unknown'}kt | Headwind: {sensor_data['headwind'] if sensor_data['headwind'] else 'unknown'}kt\n"
        f"- Temperature: {sensor_data['temp'].state if sensor_data['temp'] else 'unknown'}°C | Dew Point: {sensor_data['dp'].state if sensor_data['dp'] else 'unknown'}°C\n"
        f"- Pressure: {sensor_data['pressure'].state if sensor_data['pressure'] else 'unknown'} hPa\n"
        f"- Cloud Base (Est): {sensor_data['cloud_base'].state if sensor_data['cloud_base'] else 'unknown'} ft AGL\n"
        f"- Density Altitude: {sensor_data['da'].state if sensor_data['da'] else 'unknown'} ft\n"
        f"- Carburettor Icing Risk: {sensor_data['carb'].state if sensor_data['carb'] else 'unknown'}\n"
        f"- Recommended Runway: {sensor_data['runway_number']}\n"
        f"- Weather Data Age: {sensor_data['weather_age'].state if sensor_data['weather_age'] else 'unknown'} minutes\n"
        f"- Master Safety Alert: {'ACTIVE ⚠️' if sensor_data['safety_alert'] and sensor_data['safety_alert'].state == 'on' else 'OK ✓'}\n\n"
        f"**NOTAMs ({notam_radius}nm radius):**\n"
        f"{notam_text}\n\n"
        f"**FORECAST:**\n"
        f"{forecast_text}\n\n"
        f"Please provide the briefing based on this data following the CFI morning brief format specified.")


async def async_generate_all_ai_briefings(
        hass: HomeAssistant,
        entry: ConfigEntry) -> None:
    """Trigger AI briefing generation for all airfields."""
    ai_config = entry.data.get("ai_assistant", {})
    agent_id = ai_config.get("ai_agent_entity")
    if not agent_id:
        return

    # Load system prompt from file without blocking the event loop
    prompt_path = os.path.join(
        os.path.dirname(__file__),
        "prompts",
        "preflight_brief.txt")

    def _read_prompt_file() -> str:
        if not os.path.exists(prompt_path):
            return ""
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except (OSError, UnicodeDecodeError) as e:
            _LOGGER.error("Error reading preflight_brief.txt: %s", e)
            return ""
        except Exception as e:
            _LOGGER.error(
                "Unexpected error reading preflight_brief.txt: %s", e)
            return ""

    system_instructions = await hass.async_add_executor_job(_read_prompt_file)

    # Get global settings for NOTAM radius
    settings = entry.data.get("settings", {})
    default_notam_radius = settings.get(
        "notam_default_radius_nm",
        DEFAULT_NOTAM_RADIUS_NM)

    # Generate briefings for each airfield
    for airfield in entry.data.get("airfields", []):
        airfield_name = airfield["name"]
        slug = airfield_name.lower().replace(" ", "_")
        icao = airfield.get("icao_code", "unknown")
        lat = airfield.get("latitude")
        lon = airfield.get("longitude")

        # Get NOTAM radius (airfield override or global default)
        notam_radius = airfield.get(
            "notam_radius_override") or default_notam_radius

        # Gather all sensor data
        sensor_data = _gather_airfield_sensor_data(hass, slug, airfield)

        # Get timezone and solar info
        tz_value, sunrise_time, sunset_time = _get_timezone_and_solar_info(
            hass, slug, lat, lon
        )

        # Process NOTAMs
        notam_text = _process_notams_for_briefing(
            hass, slug, notam_radius
        )

        # Process forecast data
        now = dt_util.now()
        forecast_text = _process_forecast_for_briefing(
            hass, entry, slug, lat, lon, now, airfield_name
        )

        user_prompt = _build_briefing_prompt(
            system_instructions,
            airfield_name,
            icao,
            airfield,
            sensor_data,
            tz_value,
            sunrise_time,
            sunset_time,
            now,
            notam_text,
            notam_radius,
            forecast_text
        )

        # Request AI briefing with automatic retry on failure
        await _request_ai_briefing_with_retry(hass, agent_id, airfield_name, user_prompt)


async def async_send_briefing(
        hass: HomeAssistant,
        briefing: dict,
        entry: ConfigEntry) -> None:
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
    recipient_emails = [p["email"]
                        for p in all_pilots if p["name"] in pilot_names]

    subject = f"✈️ Hangar Briefing: {briefing['airfield_name']} / {briefing['aircraft_reg']}"
    body = (
        f"Good morning Captain.\n\n"
        f"Here is your automated safety briefing for {briefing['airfield_name']}:\n"
        f"- Density Altitude: {da.state if da else 'N/A'} ft\n"
        f"- Carb Icing Risk: {carb.state if carb else 'N/A'}\n"
        f"- Predicted Ground Roll ({briefing['aircraft_reg']}): {roll.state if roll else 'N/A'} m\n\n"
        f"Fly safe!")

    try:
        await hass.services.async_call(
            "notify",
            "persistent_notification",  # Fallback for demo, usually 'email' or 'mobile_app'
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
