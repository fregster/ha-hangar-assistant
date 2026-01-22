from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional, Set
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from .const import (
    DOMAIN,
    DEFAULT_AI_SYSTEM_PROMPT,
    DEFAULT_DASHBOARD_VERSION,
    UNIT_PREFERENCE_AVIATION,
    UNIT_PREFERENCE_SI,
    DEFAULT_UNIT_PREFERENCE,
    DEFAULT_SENSOR_CACHE_TTL_SECONDS,
    SETUP_WIZARD_VERSION,
    SETUP_WIZARD_ENABLED,
    WELCOME_TITLE,
    WELCOME_DESCRIPTION,
    SETUP_STEPS,
    ICAO_PATTERN,
    UK_REG_PATTERN,
    US_REG_PATTERN,
    EU_REG_PATTERN,
)
from .utils.i18n import get_available_languages, get_distance_unit_options, get_action_options, get_unit_preference_options
from .validation import (
    validate_icao,
    validate_registration,
    validate_mtow,
    validate_runway_length,
    validate_api_key,
    validate_latitude,
    validate_longitude,
    format_validation_message,
)
from .templates import (
    AIRCRAFT_TEMPLATES,
    QUICK_START_TEMPLATES,
    get_aircraft_template,
    apply_aircraft_template,
    list_aircraft_templates,
)

_LOGGER = logging.getLogger(__name__)


class SetupWizardState:
    """State container for setup wizard progress.
    
    This class tracks the user's progress through the 7-step setup wizard,
    storing configuration data for each step and managing step completion status.
    
    Attributes:
        current_step: Current step number (0-6 for 7 steps)
        completed_steps: Set of completed step names
        general_settings: Dict of general settings from step 1
        api_configs: Dict of API configurations (CheckWX, OWM, NOTAMs)
        airfield_data: Dict of first airfield configuration
        hangar_data: Optional dict of hangar configuration
        aircraft_data: Dict of first aircraft configuration
        sensor_links: Dict mapping sensor types to entity IDs
        dashboard_method: "automatic" or "manual" installation
    
    Used by:
        - HangarAssistantConfigFlow for first-time setup wizard
        - Progress tracking and step skipping logic
    """
    
    def __init__(self):
        """Initialize wizard state with empty data structures."""
        self.current_step: int = 0
        self.completed_steps: Set[str] = set()
        self.general_settings: Dict[str, Any] = {}
        self.api_configs: Dict[str, Any] = {}
        self.airfield_data: Optional[Dict] = None
        self.hangar_data: Optional[Dict] = None
        self.aircraft_data: Optional[Dict] = None
        self.sensor_links: Dict[str, str] = {}
        self.dashboard_method: str = "automatic"
        self.use_wizard: bool = True  # Flag to track if wizard was chosen
    
    def mark_step_complete(self, step_name: str) -> None:
        """Mark a step as completed.
        
        Args:
            step_name: Name of step to mark complete (e.g., "general_settings")
        """
        self.completed_steps.add(step_name)
        _LOGGER.debug("Marked step complete: %s", step_name)
    
    def can_skip_step(self, step_name: str) -> bool:
        """Check if a step can be skipped.
        
        Args:
            step_name: Name of step to check
        
        Returns:
            True if step is optional and can be skipped
        """
        skip_rules = {
            "api_integrations": True,  # Always optional (but recommended)
            "add_hangar": True,  # Always optional
            "link_sensors": True,  # Optional if APIs configured
            "install_dashboard": True,  # Optional (can install manually)
        }
        return skip_rules.get(step_name, False)
    
    def get_progress_percentage(self) -> int:
        """Calculate setup progress percentage.
        
        Returns:
            Integer percentage (0-100) of completed steps
        """
        total_steps = len(SETUP_STEPS)
        if total_steps == 0:
            return 0
        return int((len(self.completed_steps) / total_steps) * 100)
    
    def get_progress_text(self) -> str:
        """Get progress text for display.
        
        Returns:
            String like "Step 3 of 7 (42% complete)"
        """
        current = len(self.completed_steps) + 1
        total = len(SETUP_STEPS)
        percentage = self.get_progress_percentage()
        return f"Step {current} of {total} ({percentage}% complete)"

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class HangarAssistantConfigFlow(
        config_entries.ConfigFlow,
        domain=DOMAIN):  # type: ignore[call-arg]
    """Handle initial onboarding for Hangar Assistant.

    This config flow manages first-time setup with an optional guided wizard
    for new users, or direct configuration for advanced users.

    Wizard Mode (First-Time Users):
        - 7-step guided setup process
        - Auto-population from CheckWX API
        - Aircraft templates for common types
        - Dashboard auto-installation
        - Real-time validation and help

    Direct Mode (Advanced Users):
        - Creates blank entry for manual configuration
        - All settings accessible via Options flow

    Inputs:
        - user_input: Optional dict submitted from forms

    Outputs/Behavior:
        - Shows wizard welcome screen for first-time users
        - Creates ConfigEntry with wizard-collected data
        - Aborts with reason "already_configured" if entry exists

    Used by:
        - Devices & Services > Add Integration > Hangar Assistant
        - Configure button routes to HangarOptionsFlowHandler
    """
    VERSION = 1

    def __init__(self):
        """Initialize config flow with wizard state."""
        super().__init__()
        self.wizard_state = SetupWizardState()

    async def async_step_user(self, user_input=None):
        """Initial step when adding the integration for the first time.

        Checks if an entry already exists (integration only supports single instance).
        Shows wizard welcome screen for new installations if wizard is enabled.

        Args:
            user_input: None on first load, dict on form submission

        Returns:
            - async_abort(reason="already_configured") if entry exists
            - async_step_welcome() if wizard enabled for new setup
            - async_create_entry() to create blank entry for manual config
        """
        # Ensure only one instance of the integration is installed
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        # Show wizard welcome screen if enabled
        if SETUP_WIZARD_ENABLED:
            return await self.async_step_welcome()

        # Fallback: Create blank entry for manual configuration
        if user_input is not None:
            return self.async_create_entry(title="Hangar Assistant", data={})

        return self.async_show_form(step_id="user")

    # ========================================================================
    # SETUP WIZARD FLOW STEPS (Phase 2)
    # ========================================================================

    async def async_step_welcome(self, user_input=None):
        """Show welcome screen with wizard overview.
        
        This is the entry point for the guided setup wizard. Users can choose
        to proceed with the wizard or skip to manual configuration.
        
        Args:
            user_input: None on first load, dict with choice on submission
        
        Returns:
            - async_step_general_settings() if user starts wizard
            - async_create_entry() if user skips wizard
        """
        if user_input is not None:
            if user_input.get("start_wizard", True):
                self.wizard_state.use_wizard = True
                return await self.async_step_general_settings()
            else:
                # User chose to skip wizard - create blank entry
                self.wizard_state.use_wizard = False
                return self.async_create_entry(
                    title="Hangar Assistant",
                    data={"settings": {"setup_completed": False}}
                )
        
        # Build steps list for display
        steps_text = "\n".join(
            f"{i+1}. {step}" for i, step in enumerate(SETUP_STEPS)
        )
        
        return self.async_show_form(
            step_id="welcome",
            data_schema=vol.Schema({
                vol.Required("start_wizard", default=True): selector.BooleanSelector(),
            }),
            description_placeholders={
                "welcome_title": WELCOME_TITLE,
                "welcome_description": WELCOME_DESCRIPTION,
                "setup_steps": steps_text,
                "estimated_time": "10-15 minutes",
            },
        )

    async def async_step_general_settings(self, user_input=None):
        """Step 1: General settings (language, units, preferences).
        
        Collects core settings that affect the entire integration:
        - UI language
        - Unit preference (aviation/SI)
        - Cache settings
        
        Args:
            user_input: None on first load, dict with settings on submission
        
        Returns:
            - async_step_api_integrations() on success
        """
        errors = {}
        
        if user_input is not None:
            # Store general settings
            self.wizard_state.general_settings = {
                "language": user_input.get("language", "en"),
                "unit_preference": user_input.get("unit_preference", DEFAULT_UNIT_PREFERENCE),
                "sensor_cache_ttl_seconds": user_input.get("sensor_cache_ttl_seconds", DEFAULT_SENSOR_CACHE_TTL_SECONDS),
                "setup_wizard_version": SETUP_WIZARD_VERSION,
                "setup_completed": False,  # Will be set to True at end of wizard
            }
            self.wizard_state.mark_step_complete("general_settings")
            return await self.async_step_api_integrations()
        
        # Build language options
        language_options = [
            selector.SelectOptionDict(value=code, label=label)
            for code, label in get_available_languages()
        ]
        
        # Build unit preference options
        unit_options = get_unit_preference_options()
        
        return self.async_show_form(
            step_id="general_settings",
            data_schema=vol.Schema({
                vol.Required("language", default="en"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=language_options,
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required("unit_preference", default=DEFAULT_UNIT_PREFERENCE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=unit_options,
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Optional("sensor_cache_ttl_seconds", default=DEFAULT_SENSOR_CACHE_TTL_SECONDS): vol.All(
                    vol.Coerce(int), vol.Range(min=30, max=300)
                ),
            }),
            errors=errors,
            description_placeholders={
                "progress": self.wizard_state.get_progress_text(),
                "step_description": "Configure language and unit preferences for your aviation operations.",
            },
        )

    async def async_step_api_integrations(self, user_input=None):
        """Step 2: API integrations menu (CheckWX, OpenWeatherMap, NOTAMs).
        
        Shows available external integrations and allows configuration.
        All integrations are optional but recommended for best experience.
        
        Args:
            user_input: None on first load, dict with selections on submission
        
        Returns:
            - async_step_checkwx_setup() if CheckWX selected
            - async_step_owm_setup() if OpenWeatherMap selected
            - async_step_add_airfield() if skipped or completed
        """
        errors = {}
        
        if user_input is not None:
            # Check what user wants to configure
            if user_input.get("configure_checkwx", False):
                return await self.async_step_checkwx_setup()
            elif user_input.get("configure_owm", False):
                return await self.async_step_owm_setup()
            elif user_input.get("skip", False):
                # User skipped API configuration
                self.wizard_state.mark_step_complete("api_integrations")
                return await self.async_step_add_airfield()
            else:
                # No selections but submitted - treat as skip
                self.wizard_state.mark_step_complete("api_integrations")
                return await self.async_step_add_airfield()
        
        return self.async_show_form(
            step_id="api_integrations",
            data_schema=vol.Schema({
                vol.Optional("configure_checkwx", default=False): selector.BooleanSelector(),
                vol.Optional("configure_owm", default=False): selector.BooleanSelector(),
                vol.Optional("skip", default=False): selector.BooleanSelector(),
            }),
            errors=errors,
            description_placeholders={
                "progress": self.wizard_state.get_progress_text(),
                "checkwx_info": "CheckWX: Free METAR/TAF data (recommended)",
                "owm_info": "OpenWeatherMap: Professional forecasts (~$10-30/month)",
                "notams_info": "NOTAMs: Free UK NATS data (auto-enabled)",
                "recommendation": "⚡ Recommended: Configure CheckWX for auto-population!",
            },
        )

    # ========================================================================
    # API INTEGRATION SUB-FLOWS (Phase 3)
    # ========================================================================

    async def async_step_checkwx_setup(self, user_input=None):
        """Configure CheckWX API integration (free METAR/TAF data).
        
        CheckWX provides free aviation weather data including:
        - Current METAR observations
        - TAF terminal forecasts
        - Station information for auto-population
        
        Args:
            user_input: None on first load, dict with API key on submission
        
        Returns:
            - async_step_api_integrations() on success
            - Shows form with errors on failure
        """
        errors = {}
        
        if user_input is not None:
            api_key = user_input.get("api_key", "").strip()
            
            # Validate API key format
            is_valid, error_msg = validate_api_key(api_key, "checkwx")
            if not is_valid:
                errors["api_key"] = "invalid_api_key"
                _LOGGER.warning("CheckWX API key validation failed: %s", error_msg)
            else:
                # Test API connection with a simple station query
                from .utils.checkwx_client import CheckWXClient
                
                try:
                    # Use a well-known ICAO (KJFK) to test connection
                    test_client = CheckWXClient(
                        api_key=api_key,
                        hass=self.hass,
                        cache_enabled=False  # Don't cache test request
                    )
                    
                    # Quick station info test (doesn't count heavily against rate limit)
                    test_result = await test_client.get_station_info("KJFK")
                    
                    if test_result is None:
                        errors["api_key"] = "invalid_api_key"
                        _LOGGER.warning("CheckWX API test failed: No data returned")
                    else:
                        # Success - store configuration
                        self.wizard_state.api_configs["checkwx"] = {
                            "enabled": True,
                            "api_key": api_key,
                            "metar_enabled": user_input.get("metar_enabled", True),
                            "taf_enabled": user_input.get("taf_enabled", True),
                            "station_enabled": user_input.get("station_enabled", True),
                            "metar_cache_minutes": user_input.get("metar_cache_minutes", 30),
                            "taf_cache_minutes": user_input.get("taf_cache_minutes", 360),
                        }
                        _LOGGER.info("CheckWX API configured and tested successfully")
                        
                        # Return to integrations menu (user can configure more APIs)
                        return await self.async_step_api_integrations()
                
                except Exception as e:
                    errors["api_key"] = "cannot_connect"
                    _LOGGER.error("CheckWX API test connection failed: %s", e)
        
        # Build cache interval options
        metar_cache_options = [
            selector.SelectOptionDict(value=15, label="15 minutes"),
            selector.SelectOptionDict(value=30, label="30 minutes"),
            selector.SelectOptionDict(value=60, label="60 minutes"),
        ]
        
        taf_cache_options = [
            selector.SelectOptionDict(value=180, label="3 hours"),
            selector.SelectOptionDict(value=360, label="6 hours"),
            selector.SelectOptionDict(value=720, label="12 hours"),
        ]
        
        return self.async_show_form(
            step_id="checkwx_setup",
            data_schema=vol.Schema({
                vol.Required("api_key"): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                vol.Optional("metar_enabled", default=True): selector.BooleanSelector(),
                vol.Optional("taf_enabled", default=True): selector.BooleanSelector(),
                vol.Optional("station_enabled", default=True): selector.BooleanSelector(),
                vol.Optional("metar_cache_minutes", default=30): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=metar_cache_options,
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Optional("taf_cache_minutes", default=360): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=taf_cache_options,
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
            }),
            errors=errors,
            description_placeholders={
                "signup_url": "https://www.checkwxapi.com/signup",
                "instructions": "1. Visit https://www.checkwxapi.com/signup\n2. Create free account\n3. Copy API key from profile\n4. Paste key below",
                "cost": "✅ 100% FREE - No credit card required",
            },
        )

    async def async_step_owm_setup(self, user_input=None):
        """Configure OpenWeatherMap API integration (professional weather data).
        
        OpenWeatherMap provides professional weather forecasts including:
        - Current weather conditions
        - Hourly forecasts (48 hours)
        - Daily forecasts (8 days)
        - Weather alerts
        
        WARNING: This is a PAID service (~$10-30/month typical usage).
        
        Args:
            user_input: None on first load, dict with API key on submission
        
        Returns:
            - async_step_api_integrations() on success
            - Shows form with errors on failure
        """
        errors = {}
        
        if user_input is not None:
            api_key = user_input.get("api_key", "").strip()
            
            # Validate API key format
            is_valid, error_msg = validate_api_key(api_key, "openweathermap")
            if not is_valid:
                errors["api_key"] = "invalid_api_key"
                _LOGGER.warning("OWM API key validation failed: %s", error_msg)
            else:
                # Store configuration (don't test yet - will test when fetching weather)
                self.wizard_state.api_configs["openweathermap"] = {
                    "enabled": True,
                    "api_key": api_key,
                    "cache_enabled": user_input.get("cache_enabled", True),
                    "update_interval": user_input.get("update_interval", 10),
                    "cache_ttl": user_input.get("cache_ttl", 10),
                }
                _LOGGER.info("OpenWeatherMap API configured successfully")
                
                # Return to integrations menu
                return await self.async_step_api_integrations()
        
        # Build interval options
        interval_options = [
            selector.SelectOptionDict(value=5, label="5 minutes"),
            selector.SelectOptionDict(value=10, label="10 minutes"),
            selector.SelectOptionDict(value=15, label="15 minutes"),
            selector.SelectOptionDict(value=30, label="30 minutes"),
            selector.SelectOptionDict(value=60, label="60 minutes"),
        ]
        
        ttl_options = [
            selector.SelectOptionDict(value=5, label="5 minutes"),
            selector.SelectOptionDict(value=10, label="10 minutes"),
            selector.SelectOptionDict(value=15, label="15 minutes"),
            selector.SelectOptionDict(value=30, label="30 minutes"),
        ]
        
        return self.async_show_form(
            step_id="owm_setup",
            data_schema=vol.Schema({
                vol.Required("api_key"): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                vol.Optional("cache_enabled", default=True): selector.BooleanSelector(),
                vol.Optional("update_interval", default=10): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=interval_options,
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Optional("cache_ttl", default=10): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=ttl_options,
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
            }),
            errors=errors,
            description_placeholders={
                "signup_url": "https://openweathermap.org/api",
                "pricing": "~$0.0012 per call (~$10-30/month typical)",
                "warning": "⚠️  This is a PAID service",
                "recommendation": "Use CheckWX (free) for basic weather. OWM adds forecasts and alerts.",
            },
        )

    # ========================================================================
    # AIRFIELD, HANGAR, AIRCRAFT SETUP STEPS
    # ========================================================================

    async def async_step_add_airfield(self, user_input=None):
        """Step 3: Add first airfield.
        
        Collects airfield information with optional auto-population from CheckWX.
        Validates ICAO code format and provides real-time feedback.
        
        Args:
            user_input: None on first load, dict with airfield data on submission
        
        Returns:
            - async_step_add_hangar() on success
        """
        errors = {}
        
        if user_input is not None:
            icao = user_input.get("icao", "").strip().upper()
            name = user_input.get("name", "").strip()
            
            # Validate ICAO code
            is_valid, error_msg = validate_icao(icao)
            if not is_valid:
                errors["icao"] = "invalid_icao"
                _LOGGER.warning("ICAO validation failed: %s", error_msg)
            elif not name:
                errors["name"] = "name_required"
            else:
                # Create airfield data
                self.wizard_state.airfield_data = {
                    "icao": icao,
                    "name": name,
                    "latitude": user_input.get("latitude"),
                    "longitude": user_input.get("longitude"),
                    "elevation_m": user_input.get("elevation_m", 0),
                    "weather_data_source": "sensors",  # Default
                    "use_owm_forecast": False,
                    "use_owm_alerts": False,
                }
                
                _LOGGER.info("Airfield configured: %s (%s)", name, icao)
                self.wizard_state.mark_step_complete("add_airfield")
                return await self.async_step_add_hangar()
        
        # Show form with validation hints
        has_checkwx = "checkwx" in self.wizard_state.api_configs
        
        return self.async_show_form(
            step_id="add_airfield",
            data_schema=vol.Schema({
                vol.Required("icao"): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
                vol.Required("name"): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
                vol.Optional("latitude"): vol.All(vol.Coerce(float), vol.Range(min=-90, max=90)),
                vol.Optional("longitude"): vol.All(vol.Coerce(float), vol.Range(min=-180, max=180)),
                vol.Optional("elevation_m", default=0): vol.All(vol.Coerce(float), vol.Range(min=-100, max=5000)),
            }),
            errors=errors,
            description_placeholders={
                "progress": self.wizard_state.get_progress_text(),
                "icao_help": "4-letter airport code (e.g., EGHP, KJFK, LFPG)",
                "checkwx_available": "✨ CheckWX configured - coordinates will auto-populate" if has_checkwx else "",
                "example": "Example: ICAO=EGHP, Name=Popham Airfield",
            },
        )

    async def async_step_add_hangar(self, user_input=None):
        """Step 4: Add hangar (optional).
        
        Allows user to configure a hangar for environmental sensors.
        This step is always optional and can be skipped.
        
        Args:
            user_input: None on first load, dict with hangar data on submission
        
        Returns:
            - async_step_add_aircraft() on completion or skip
        """
        errors = {}
        
        if user_input is not None:
            if user_input.get("skip", False):
                # User skipped hangar configuration
                self.wizard_state.mark_step_complete("add_hangar")
                return await self.async_step_add_aircraft()
            
            name = user_input.get("name", "").strip()
            if not name:
                errors["name"] = "name_required"
            else:
                # Create hangar data
                self.wizard_state.hangar_data = {
                    "name": name,
                    "airfield": self.wizard_state.airfield_data["name"],
                    "temp_sensor": user_input.get("temp_sensor", ""),
                    "humidity_sensor": user_input.get("humidity_sensor", ""),
                }
                
                _LOGGER.info("Hangar configured: %s", name)
                self.wizard_state.mark_step_complete("add_hangar")
                return await self.async_step_add_aircraft()
        
        return self.async_show_form(
            step_id="add_hangar",
            data_schema=vol.Schema({
                vol.Optional("name"): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
                vol.Optional("temp_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional("humidity_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional("skip", default=False): selector.BooleanSelector(),
            }),
            errors=errors,
            description_placeholders={
                "progress": self.wizard_state.get_progress_text(),
                "optional_notice": "📦 Hangars are optional - skip if you don't use one",
                "hangar_help": "Configure environmental sensors in your hangar for climate monitoring",
            },
        )

    async def async_step_add_aircraft(self, user_input=None):
        """Step 5: Add first aircraft with template support.
        
        Collects aircraft registration and optionally loads performance
        data from templates (Cessna 172, PA-28, etc.).
        
        Args:
            user_input: None on first load, dict with aircraft data on submission
        
        Returns:
            - async_step_aircraft_template() if template selected
            - async_step_link_sensors() if manual entry or template applied
        """
        errors = {}
        
        if user_input is not None:
            registration = user_input.get("registration", "").strip().upper()
            
            # Validate registration format
            is_valid, error_msg = validate_registration(registration)
            if not is_valid:
                errors["registration"] = "invalid_registration"
                _LOGGER.warning("Registration validation failed: %s", error_msg)
            else:
                aircraft_type = user_input.get("aircraft_type", "")
                
                # Check if user selected a template
                if aircraft_type and aircraft_type in AIRCRAFT_TEMPLATES:
                    # Load template data
                    template_data = apply_aircraft_template(aircraft_type, registration)
                    template_data["airfield"] = self.wizard_state.airfield_data["name"]
                    
                    # Add hangar if configured
                    if self.wizard_state.hangar_data:
                        template_data["hangar"] = self.wizard_state.hangar_data["name"]
                    
                    self.wizard_state.aircraft_data = template_data
                    _LOGGER.info("Aircraft configured with template: %s (%s)", registration, aircraft_type)
                else:
                    # Manual entry without template
                    self.wizard_state.aircraft_data = {
                        "reg": registration,
                        "type": user_input.get("type_manual", "Unknown"),
                        "airfield": self.wizard_state.airfield_data["name"],
                    }
                    
                    if self.wizard_state.hangar_data:
                        self.wizard_state.aircraft_data["hangar"] = self.wizard_state.hangar_data["name"]
                    
                    _LOGGER.info("Aircraft configured manually: %s", registration)
                
                self.wizard_state.mark_step_complete("add_aircraft")
                return await self.async_step_link_sensors()
        
        # Build template options
        template_options = [
            selector.SelectOptionDict(value="", label="None (manual entry)")
        ] + [
            selector.SelectOptionDict(value=template_id, label=template_data["name"])
            for template_id, template_data in AIRCRAFT_TEMPLATES.items()
        ]
        
        return self.async_show_form(
            step_id="add_aircraft",
            data_schema=vol.Schema({
                vol.Required("registration"): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
                vol.Optional("aircraft_type"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=template_options,
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Optional("type_manual"): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
            }),
            errors=errors,
            description_placeholders={
                "progress": self.wizard_state.get_progress_text(),
                "reg_help": "Aircraft registration/tail number (e.g., G-ABCD, N12345)",
                "template_hint": "✨ Select aircraft type to load default specs",
                "templates_available": f"{len(AIRCRAFT_TEMPLATES)} templates available",
            },
        )

    async def async_step_link_sensors(self, user_input=None):
        """Step 6: Link weather sensors (optional).
        
        Allows user to connect Home Assistant weather sensors for real-time data.
        This step is optional if APIs are configured.
        
        Args:
            user_input: None on first load, dict with sensor mappings on submission
        
        Returns:
            - async_step_install_dashboard() on completion or skip
        """
        errors = {}
        
        if user_input is not None:
            # Store sensor links (all optional)
            self.wizard_state.sensor_links = {
                "temp_sensor": user_input.get("temp_sensor", ""),
                "humidity_sensor": user_input.get("humidity_sensor", ""),
                "pressure_sensor": user_input.get("pressure_sensor", ""),
                "wind_speed_sensor": user_input.get("wind_speed_sensor", ""),
                "wind_direction_sensor": user_input.get("wind_direction_sensor", ""),
            }
            
            _LOGGER.info("Sensor links configured")
            self.wizard_state.mark_step_complete("link_sensors")
            return await self.async_step_install_dashboard()
        
        # Check if APIs are configured (makes sensors more optional)
        has_apis = bool(self.wizard_state.api_configs)
        
        return self.async_show_form(
            step_id="link_sensors",
            data_schema=vol.Schema({
                vol.Optional("temp_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional("humidity_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional("pressure_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional("wind_speed_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional("wind_direction_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            }),
            errors=errors,
            description_placeholders={
                "progress": self.wizard_state.get_progress_text(),
                "optional_notice": "🌡️ Sensors are optional" + (" - APIs configured!" if has_apis else ""),
                "sensor_help": "Link existing HA weather sensors for real-time data",
            },
        )

    async def async_step_install_dashboard(self, user_input=None):
        """Step 7: Install Glass Cockpit dashboard (optional).
        
        Final step - offers to install the Glass Cockpit dashboard automatically
        or provides YAML for manual installation.
        
        Args:
            user_input: None on first load, dict with installation choice on submission
        
        Returns:
            - async_create_entry() with all collected data
        """
        errors = {}
        
        if user_input is not None:
            method = user_input.get("method", "skip")
            self.wizard_state.dashboard_method = method
            self.wizard_state.mark_step_complete("install_dashboard")
            
            # Wizard complete! Create config entry with all collected data
            config_data = self._build_final_config()
            
            # Create entry first (so we have an entry reference for the service)
            _LOGGER.info("Setup wizard completed successfully")
            result = self.async_create_entry(
                title="Hangar Assistant",
                data=config_data
            )
            
            # Trigger dashboard installation AFTER entry is created
            if method in ["automatic", "manual"]:
                # Schedule dashboard installation as a background task
                # This ensures it runs after entry setup completes
                async def _install_dashboard_after_setup():
                    """Install dashboard after a brief delay to ensure entry is fully set up."""
                    import asyncio
                    await asyncio.sleep(2)  # Allow entry setup to complete
                    
                    try:
                        await self.hass.services.async_call(
                            DOMAIN,
                            "install_dashboard",
                            {"method": method},
                            blocking=True
                        )
                        _LOGGER.info("Dashboard installation triggered: %s", method)
                    except Exception as e:
                        _LOGGER.error("Dashboard installation failed: %s", e)
                
                # Fire and forget - don't block wizard completion
                self.hass.async_create_task(_install_dashboard_after_setup())
            
            return result
        
        return self.async_show_form(
            step_id="install_dashboard",
            data_schema=vol.Schema({
                vol.Optional("method", default="automatic"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value="automatic", label="Automatic (recommended)"),
                            selector.SelectOptionDict(value="manual", label="Manual (provide YAML)"),
                            selector.SelectOptionDict(value="skip", label="Skip (install later)"),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
            }),
            errors=errors,
            description_placeholders={
                "progress": "Step 7 of 7 (100% complete)",
                "dashboard_info": "🎛️ Glass Cockpit: Beautiful aviation-themed dashboard",
                "features": "• Live weather conditions\n• Performance calculations\n• Safety alerts\n• Fuel management",
                "completion": "🎉 Setup wizard almost complete!",
            },
        )

    def _build_final_config(self) -> Dict[str, Any]:
        """Build final configuration from wizard state.
        
        Combines all wizard steps into a single configuration structure
        that will be stored in the config entry.
        
        Returns:
            Dict with complete configuration including settings, integrations,
            airfields, hangars, aircraft, and dashboard preferences
        """
        config = {
            "settings": self.wizard_state.general_settings,
            "integrations": self.wizard_state.api_configs,
            "airfields": [],
            "hangars": [],
            "aircraft": [],
        }
        
        # Mark setup as completed
        config["settings"]["setup_completed"] = True
        
        # Add NOTAM integration (free, enabled by default for new installs)
        if "notams" not in config["integrations"]:
            config["integrations"]["notams"] = {
                "enabled": True,
                "update_time": "02:00",
                "cache_days": 7,
                "stale_cache_allowed": True,
            }
        
        # Add airfield
        if self.wizard_state.airfield_data:
            airfield = self.wizard_state.airfield_data.copy()
            
            # Add sensor links if provided
            for sensor_type, entity_id in self.wizard_state.sensor_links.items():
                if entity_id:
                    airfield[sensor_type] = entity_id
            
            config["airfields"].append(airfield)
        
        # Add hangar if configured
        if self.wizard_state.hangar_data:
            config["hangars"].append(self.wizard_state.hangar_data)
        
        # Add aircraft
        if self.wizard_state.aircraft_data:
            config["aircraft"].append(self.wizard_state.aircraft_data)
        
        # Store dashboard installation preference
        if "dashboard" not in config["settings"]:
            config["settings"]["dashboard"] = {}
        
        config["settings"]["dashboard"]["installation_method"] = self.wizard_state.dashboard_method
        config["settings"]["dashboard"]["version"] = DEFAULT_DASHBOARD_VERSION
        
        return config

    @classmethod
    @callback
    def async_get_options_flow(
        cls, config_entry: config_entries.ConfigEntry,
    ) -> HangarOptionsFlowHandler:
        """Directs 'Configure' button clicks to the Options Flow."""
        return HangarOptionsFlowHandler(config_entry)


class HangarOptionsFlowHandler(config_entries.OptionsFlow):
    """Manages the 'Configure' menu for adding/editing data.

    This handler provides the full configuration interface accessed through the
    \"Configure\" button in Settings > Devices & Services > Hangar Assistant.

    Main Menu Structure:
        - Airfield (add/manage airfields)
        - Aircraft (add/manage aircraft)
        - Pilot (add/manage pilots)
        - Briefing (add/manage scheduled briefings)
        - Global Config (settings, AI prompts, retention, dashboard)

    Data Flow:
        1. User navigates menu: async_step_init
        2. Selects category (airfield/aircraft/pilot/briefing/global_config)
        3. Chooses action (add/edit/delete) if applicable
        4. Completes form and data is saved to entry.data via async_update_entry

    Each submenu has add/edit/delete/manage options for managing the corresponding lists.
    """

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow.

        Args:
            config_entry: The ConfigEntry to manage options for.
        """
        super().__init__()
        # Store config_entry as a private attribute since OptionsFlow manages
        # it as a property
        self._config_entry = config_entry

    def _entry_data(self) -> dict:
        """Return config entry data as a mutable dict, defaulting to empty."""
        return dict(self._config_entry.data or {})

    def _entry_options(self) -> dict:
        """Return config entry options as a mutable dict, defaulting to empty."""
        return dict(self._config_entry.options or {})

    @staticmethod
    def _list_from(value) -> list:
        """Return a safe list copy from stored data."""
        return list(value) if isinstance(value, list) else []

    def _safe_item(self, items: list, index: int) -> dict:
        """Return a dict item at index or an empty dict if out of range/invalid."""
        if 0 <= index < len(items):
            item = items[index]
            return item if isinstance(item, dict) else {}
        return {}

    def _lang(self) -> str:
        """Return the selected UI language (default 'en')."""
        return self._entry_data().get("settings", {}).get("language", "en")

    async def async_step_init(self, _user_input=None):
        """Main configuration menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "airfield",
                "hangar",
                "aircraft",
                "pilot",
                "briefing",
                "integrations",
                "global_config"])

    async def async_step_global_config(self, _user_input=None):
        """Sub-menu for global system settings."""
        return self.async_show_menu(
            step_id="global_config",
            menu_options=["settings", "ai", "retention", "dashboard"]
        )

    async def async_step_settings(self, user_input=None):
        """Configure global system settings."""
        if user_input is not None:
            new_data = self._entry_data()
            new_data["settings"] = user_input
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        settings = self._entry_data().get("settings", {})

        # Dynamically build language options from available translation files
        language_options = [
            selector.SelectOptionDict(value=code, label=label)
            for code, label in get_available_languages()
        ]

        # Build airfield/aircraft options for default dashboard selection
        airfields = self._list_from(self._entry_data().get("airfields", []))
        aircraft = self._list_from(self._entry_data().get("aircraft", []))

        airfield_options = [
            selector.SelectOptionDict(value="", label="None (Auto-detect)")
        ] + [
            selector.SelectOptionDict(
                value=(af.get("name") or "").lower().replace(" ", "_"),
                label=af.get("name", "Unknown")
            ) for af in airfields
        ]

        aircraft_options = [
            selector.SelectOptionDict(value="", label="None (Auto-detect)")
        ] + [
            selector.SelectOptionDict(
                value=(ac.get("reg") or "").lower().replace(" ", "_"),
                label=f"{ac.get('type', 'Unknown')} ({ac.get('reg', 'Unknown')})"
            ) for ac in aircraft
        ]

        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema({
                vol.Required("language", default=settings.get("language", "en")): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=language_options,
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required("unit_preference", default=settings.get("unit_preference", DEFAULT_UNIT_PREFERENCE)): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=UNIT_PREFERENCE_AVIATION, label=get_unit_preference_options(self._lang())[0]["label"]),
                            selector.SelectOptionDict(value=UNIT_PREFERENCE_SI, label=get_unit_preference_options(self._lang())[1]["label"]),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Optional("global_pressure_sensor", default=settings.get("global_pressure_sensor")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="pressure")
                ),
                vol.Optional("default_pressure", default=settings.get("default_pressure", 1013.25)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=800, max=1100, step=0.1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="hPa")
                ),
                vol.Optional("cache_ttl_seconds", default=settings.get("cache_ttl_seconds", DEFAULT_SENSOR_CACHE_TTL_SECONDS)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=300, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="s")
                ),
                vol.Optional("default_dashboard_airfield", default=settings.get("default_dashboard_airfield", "")): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=airfield_options,
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Optional("default_dashboard_aircraft", default=settings.get("default_dashboard_aircraft", "")): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=aircraft_options,
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Optional("openweathermap_api_key", default=settings.get("openweathermap_api_key", "")): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                vol.Optional("openweathermap_enabled", default=settings.get("openweathermap_enabled", False)): selector.BooleanSelector(),
                vol.Optional("openweathermap_cache_enabled", default=settings.get("openweathermap_cache_enabled", True)): selector.BooleanSelector(),
                vol.Optional("openweathermap_update_interval", default=settings.get("openweathermap_update_interval", 10)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=5, max=60, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="min")
                ),
                vol.Optional("openweathermap_cache_ttl", default=settings.get("openweathermap_cache_ttl", 10)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=5, max=60, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="min")
                ),
            })
        )

    async def async_step_airfield(self, user_input=None):
        """Sub-menu for airfield management."""
        airfields = self._list_from(self._entry_data().get("airfields", []))

        if airfields:
            return self.async_show_menu(
                step_id="airfield",
                menu_options=["airfield_add", "airfield_manage"]
            )
        return await self.async_step_airfield_add()

    async def async_step_airfield_add(self, user_input=None):
        """Form to add a new airfield from scratch."""
        if user_input is not None:
            # Validate ICAO code format if provided
            icao_code = user_input.get("icao_code", "").strip().upper()
            if icao_code:
                if not (len(icao_code) == 4 and icao_code.isalpha()):
                    return self.async_show_form(
                        step_id="airfield_add",
                        errors={
                            "icao_code": "ICAO codes must be exactly 4 uppercase letters (e.g., EGLL, KSFO)"},
                        data_schema=self._get_airfield_add_schema())
                user_input["icao_code"] = icao_code

            # Validate runway format (comma-separated identifiers)
            runways = user_input.get("runways", "").strip()
            if not runways:
                return self.async_show_form(
                    step_id="airfield_add",
                    errors={
                        "runways": "At least one runway must be specified"},
                    data_schema=self._get_airfield_add_schema())

            # Validate primary runway is in runway list
            primary = user_input.get("primary_runway", "").strip()
            runway_list = [r.strip() for r in runways.split(",")]
            if primary not in runway_list:
                return self.async_show_form(
                    step_id="airfield_add",
                    errors={
                        "primary_runway": "Primary runway must be one of the available runways"},
                    data_schema=self._get_airfield_add_schema())

            new_data = self._entry_data()
            airfields = self._list_from(new_data.get("airfields", []))

            # Convert runway_length and elevation from feet to meters if needed
            distance_unit = user_input.pop("distance_unit", "m")
            if distance_unit == "ft":
                user_input["runway_length"] = round(
                    user_input["runway_length"] * 0.3048, 2)
                user_input["elevation"] = round(
                    user_input["elevation"] * 0.3048, 2)

            airfields.append(user_input)
            new_data["airfields"] = airfields
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        return self.async_show_form(
            step_id="airfield_add",
            data_schema=self._get_airfield_add_schema()
        )

    def _get_airfield_add_schema(self) -> vol.Schema:
        """Return the schema for airfield add form."""
        return vol.Schema({
            vol.Required("name"): str,
            vol.Optional("icao_code"): str,
            vol.Required("latitude", default=51.47): selector.NumberSelector(
                selector.NumberSelectorConfig(min=-90, max=90, step="any", mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required("longitude", default=-0.45): selector.NumberSelector(
                selector.NumberSelectorConfig(min=-180, max=180, step="any", mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required("elevation", default=25): selector.NumberSelector(
                selector.NumberSelectorConfig(min=-500, max=9000, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="m")
            ),
            vol.Required("distance_unit", default="m"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=o["value"], label=o["label"]) for o in get_distance_unit_options(self._lang())
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required("runways"): str,
            vol.Required("primary_runway"): str,
            vol.Required("runway_length", default=500): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=100,
                    max=2000,
                    step=1,
                    mode=selector.NumberSelectorMode.SLIDER,
                    unit_of_measurement="m"
                )
            ),
            vol.Optional("temp_sensor"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional("dp_sensor"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional("pressure_sensor"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional("wind_sensor"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional("wind_dir_sensor"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional("radio_frequency"): str,
            vol.Optional("ppl_required", default=False): selector.BooleanSelector(),
            vol.Optional("weather_data_source", default="sensors"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value="sensors", label="Home Assistant Sensors"),
                        selector.SelectOptionDict(value="openweathermap", label="OpenWeatherMap (OWM) Only"),
                        selector.SelectOptionDict(value="hybrid", label="OWM Primary, Sensors Fallback"),
                        selector.SelectOptionDict(value="sensors_backup_owm", label="Sensors Primary, OWM Fallback"),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Optional("use_owm_forecast", default=True): selector.BooleanSelector(),
            vol.Optional("use_owm_alerts", default=True): selector.BooleanSelector(),
        })

    async def async_step_airfield_manage(self, user_input=None):
        """Menu to manage existing airfields."""
        airfields = self._list_from(self._entry_data().get("airfields", []))
        options = {str(i): a.get("name", f"Airfield {i}")
                   for i, a in enumerate(airfields)}

        if user_input is not None:
            self._index = int(user_input["index"])
            if user_input["action"] == "edit":
                return await self.async_step_airfield_edit()
            return await self.async_step_airfield_delete()

        return self.async_show_form(
            step_id="airfield_manage",
            data_schema=vol.Schema(
                {
                    vol.Required("index"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=k,
                                    label=v) for k,
                                v in options.items()],
                            mode=selector.SelectSelectorMode.DROPDOWN)),
                    vol.Required("action"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=o["value"],
                                    label=o["label"]) for o in get_action_options(
                                    self._lang())],
                            mode=selector.SelectSelectorMode.DROPDOWN)),
                }))

    async def async_step_airfield_edit(self, user_input=None):
        """Edit an existing airfield."""
        index = self._index
        airfields = self._list_from(self._entry_data().get("airfields", []))
        airfield = self._safe_item(airfields, index)

        if user_input is not None:
            new_data = self._entry_data()
            airfields = self._list_from(new_data.get("airfields", []))

            # Convert runway_length and elevation from feet to meters if needed
            distance_unit = user_input.pop("distance_unit", "m")
            if distance_unit == "ft":
                user_input["runway_length"] = round(
                    user_input["runway_length"] * 0.3048, 2)
                user_input["elevation"] = round(
                    user_input["elevation"] * 0.3048, 2)

            airfields[index] = user_input
            new_data["airfields"] = airfields
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        return self.async_show_form(
            step_id="airfield_edit",
            data_schema=vol.Schema({
                vol.Required("name", default=airfield.get("name")): str,
                vol.Optional("icao_code", default=airfield.get("icao_code", "")): str,
                vol.Required("latitude", default=airfield.get("latitude")): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-90, max=90, step="any", mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Required("longitude", default=airfield.get("longitude")): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-180, max=180, step="any", mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Required("elevation", default=airfield.get("elevation", 0)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-500, max=9000, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="m")
                ),
                vol.Required("distance_unit", default="m"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=o["value"], label=o["label"]) for o in get_distance_unit_options(self._lang())
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required("runways", default=airfield.get("runways")): str,
                vol.Required("primary_runway", default=airfield.get("primary_runway")): str,
                vol.Required("runway_length", default=airfield.get("runway_length", 500)): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=100,
                        max=2000,
                        step=1,
                        mode=selector.NumberSelectorMode.SLIDER,
                        unit_of_measurement="m"
                    )
                ),
                vol.Optional("temp_sensor", default=airfield.get("temp_sensor")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional("dp_sensor", default=airfield.get("dp_sensor")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional("pressure_sensor", default=airfield.get("pressure_sensor")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional("wind_sensor", default=airfield.get("wind_sensor")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional("wind_dir_sensor", default=airfield.get("wind_dir_sensor")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional("radio_frequency", default=airfield.get("radio_frequency", "")): str,
                vol.Optional("ppl_required", default=airfield.get("ppl_required", False)): selector.BooleanSelector(),
                vol.Optional("weather_data_source", default=airfield.get("weather_data_source", "sensors")): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value="sensors", label="Home Assistant Sensors"),
                            selector.SelectOptionDict(value="openweathermap", label="OpenWeatherMap (OWM) Only"),
                            selector.SelectOptionDict(value="hybrid", label="OWM Primary, Sensors Fallback"),
                            selector.SelectOptionDict(value="sensors_backup_owm", label="Sensors Primary, OWM Fallback"),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Optional("use_owm_forecast", default=airfield.get("use_owm_forecast", True)): selector.BooleanSelector(),
                vol.Optional("use_owm_alerts", default=airfield.get("use_owm_alerts", True)): selector.BooleanSelector(),
            })
        )

    async def async_step_airfield_delete(self, user_input=None):
        """Delete an airfield."""
        if user_input is not None:
            if user_input["confirm"]:
                new_data = self._entry_data()
                airfields = self._list_from(new_data.get("airfields", []))
                if 0 <= self._index < len(airfields):
                    airfields.pop(self._index)
                new_data["airfields"] = airfields
                self.hass.config_entries.async_update_entry(
                    self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        return self.async_show_form(
            step_id="airfield_delete",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "confirm",
                        default=False): selector.BooleanSelector()}),
            description_placeholders={
                "name": self._safe_item(
                    self._list_from(
                        self._entry_data().get(
                            "airfields",
                            [])),
                    self._index).get(
                    "name",
                        "Airfield")})

    async def async_step_hangar(self, user_input=None):
        """Sub-menu for hangar management."""
        hangars = self._list_from(self._entry_data().get("hangars", []))

        if hangars:
            return self.async_show_menu(
                step_id="hangar",
                menu_options=["hangar_add", "hangar_manage"]
            )
        return await self.async_step_hangar_add()

    async def async_step_hangar_add(self, user_input=None):
        """Form to add a new hangar."""
        if user_input is not None:
            # Validate hangar name
            name = user_input.get("name", "").strip()
            if not name:
                return self.async_show_form(
                    step_id="hangar_add",
                    errors={"name": "Hangar name is required"},
                    data_schema=self._get_hangar_add_schema()
                )

            # Check for duplicate hangar names within the same airfield
            airfield_name = user_input.get("airfield_name", "")
            existing_hangars = self._list_from(
                self._entry_data().get("hangars", []))
            for hangar in existing_hangars:
                if (hangar.get("name") == name and
                        hangar.get("airfield_name") == airfield_name):
                    return self.async_show_form(
                        step_id="hangar_add",
                        errors={
                            "name": f"A hangar named '{name}' already exists at {airfield_name}"},
                        data_schema=self._get_hangar_add_schema())

            new_data = self._entry_data()
            hangars = self._list_from(new_data.get("hangars", []))
            hangars.append(user_input)
            new_data["hangars"] = hangars
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data)

            # Check if this is the first hangar - offer migration notification
            if len(hangars) == 1:
                _LOGGER.info(
                    "First hangar added. Users can optionally migrate aircraft to hangars.")

            return self.async_create_entry(data=self._entry_options())

        return self.async_show_form(
            step_id="hangar_add",
            data_schema=self._get_hangar_add_schema()
        )

    def _get_hangar_add_schema(self) -> vol.Schema:
        """Return the schema for hangar add form."""
        airfields = [
            a.get(
                "name",
                "") for a in self._list_from(
                self._entry_data().get(
                    "airfields",
                    []))]
        airfield_options = [
            selector.SelectOptionDict(
                value=a,
                label=a) for a in airfields] if airfields else [
            selector.SelectOptionDict(
                value="",
                label="No airfields configured")]

        return vol.Schema({
            vol.Required("name"): str,
            vol.Required("airfield_name"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=airfield_options,
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Optional("temp_sensor"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional("humidity_sensor"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
        })

    async def async_step_hangar_manage(self, user_input=None):
        """Menu to manage existing hangars."""
        hangars = self._list_from(self._entry_data().get("hangars", []))
        options = {
            str(i): f"{h.get('name', 'Hangar')} ({h.get('airfield_name', 'Unknown')})"
            for i, h in enumerate(hangars)
        }

        if user_input is not None:
            self._index = int(user_input["index"])
            if user_input["action"] == "edit":
                return await self.async_step_hangar_edit()
            return await self.async_step_hangar_delete()

        return self.async_show_form(
            step_id="hangar_manage",
            data_schema=vol.Schema({
                vol.Required("index"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[selector.SelectOptionDict(value=k, label=v) for k, v in options.items()],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required("action"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=o["value"], label=o["label"])
                            for o in get_action_options(self._lang())
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
            })
        )

    async def async_step_hangar_edit(self, user_input=None):
        """Edit an existing hangar."""
        index = self._index
        hangars = self._list_from(self._entry_data().get("hangars", []))
        hangar = self._safe_item(hangars, index)

        if user_input is not None:
            new_data = self._entry_data()
            hangars = self._list_from(new_data.get("hangars", []))
            hangars[index] = user_input
            new_data["hangars"] = hangars
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        airfields = [
            a.get(
                "name",
                "") for a in self._list_from(
                self._entry_data().get(
                    "airfields",
                    []))]
        airfield_options = [
            selector.SelectOptionDict(
                value=a, label=a) for a in airfields]

        return self.async_show_form(
            step_id="hangar_edit",
            data_schema=vol.Schema({
                vol.Required("name", default=hangar.get("name")): str,
                vol.Required("airfield_name", default=hangar.get("airfield_name")): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=airfield_options,
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Optional("temp_sensor", default=hangar.get("temp_sensor")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional("humidity_sensor", default=hangar.get("humidity_sensor")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            })
        )

    async def async_step_hangar_delete(self, user_input=None):
        """Delete a hangar."""
        index = self._index
        hangars = self._list_from(self._entry_data().get("hangars", []))
        hangar = self._safe_item(hangars, index)

        if user_input is not None:
            if user_input.get("confirm"):
                new_data = self._entry_data()
                hangars = self._list_from(new_data.get("hangars", []))
                del hangars[index]
                new_data["hangars"] = hangars
                self.hass.config_entries.async_update_entry(
                    self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        return self.async_show_form(
            step_id="hangar_delete",
            data_schema=vol.Schema({
                vol.Required("confirm", default=False): selector.BooleanSelector(),
            }),
            description_placeholders={"name": hangar.get("name", "this hangar")}
        )

    async def async_step_aircraft(self, user_input=None):
        """Sub-menu for aircraft management."""
        fleet = self._list_from(self._entry_data().get("aircraft", []))

        if fleet:
            return self.async_show_menu(
                step_id="aircraft",
                menu_options=["aircraft_add", "aircraft_manage"]
            )
        return await self.async_step_aircraft_add()

    async def async_step_aircraft_add(self, user_input=None):
        """Form to add a new aircraft."""
        if user_input is not None:
            # Validate registration format (basic alphanumeric check)
            reg = user_input.get("reg", "").strip().upper()
            if not reg or not reg.replace("-", "").isalnum():
                return self.async_show_form(
                    step_id="aircraft_add",
                    errors={
                        "reg": "Registration must contain only letters, numbers, and hyphens"},
                    data_schema=self._get_aircraft_add_schema())
            user_input["reg"] = reg

            # Validate weights (empty weight must be less than MTOW)
            empty_weight = float(user_input.get("empty_weight", 0))
            max_tow = float(user_input.get("max_tow", 0))
            weight_unit = user_input.get("weight_unit", "kg")

            if empty_weight >= max_tow:
                return self.async_show_form(
                    step_id="aircraft_add",
                    errors={
                        "empty_weight": "Empty weight must be less than MTOW"},
                    data_schema=self._get_aircraft_add_schema())

            new_data = self._entry_data()
            fleet = self._list_from(new_data.get("aircraft", []))

            # Convert weights from lbs to kg if needed
            weight_unit = user_input.pop("weight_unit", "kg")
            if weight_unit == "lbs":
                user_input["empty_weight"] = round(
                    float(user_input["empty_weight"]) * 0.453592, 2)
                user_input["max_tow"] = round(
                    float(user_input["max_tow"]) * 0.453592, 2)

            # Convert distances from feet to meters if needed
            distance_unit = user_input.pop("distance_unit", "m")
            if distance_unit == "ft":
                user_input["baseline_roll"] = round(
                    float(user_input["baseline_roll"]) * 0.3048, 2)
                user_input["baseline_50ft"] = round(
                    float(user_input["baseline_50ft"]) * 0.3048, 2)
            
            # Process fuel configuration
            fuel_type = user_input.pop("fuel_type", "AVGAS")
            fuel_burn_rate = user_input.pop("fuel_burn_rate", 0.0)
            fuel_tank_capacity = user_input.pop("fuel_tank_capacity", 0.0)
            fuel_volume_unit = user_input.pop("fuel_volume_unit", "liters")
            
            user_input["fuel"] = {
                "type": fuel_type,
                "burn_rate": float(fuel_burn_rate),
                "burn_rate_unit": fuel_volume_unit,
                "tank_capacity": float(fuel_tank_capacity),
                "tank_capacity_unit": fuel_volume_unit,
                "notes": ""
            }

            fleet.append(user_input)
            new_data["aircraft"] = fleet
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        return self.async_show_form(
            step_id="aircraft_add",
            data_schema=self._get_aircraft_add_schema()
        )

    def _get_aircraft_add_schema(self) -> vol.Schema:
        """Return the schema for aircraft add form."""
        airfields = [
            a.get(
                "name",
                "") for a in self._list_from(
                self._entry_data().get(
                    "airfields",
                    []))]
        airfield_options = [
            selector.SelectOptionDict(
                value=a,
                label=a) for a in airfields] if airfields else [
            selector.SelectOptionDict(
                value="",
                label="No airfields configured")]

        # Get hangars for dropdown, grouped by airfield
        hangars = self._list_from(self._entry_data().get("hangars", []))
        hangar_options = [
            selector.SelectOptionDict(
                value="",
                label="None (Use Airfield)")]
        for hangar in hangars:
            hangar_options.append(
                selector.SelectOptionDict(
                    value=hangar.get("name", ""),
                    label=f"{hangar.get('name', 'Hangar')} ({hangar.get('airfield_name', 'Unknown')})"
                )
            )

        return vol.Schema({
            vol.Required("reg"): str,
            vol.Required("model"): str,
            vol.Required("empty_weight", default=750): selector.NumberSelector(
                selector.NumberSelectorConfig(min=500, max=10000, step=50, unit_of_measurement="kg")
            ),
            vol.Required("max_tow", default=1200): selector.NumberSelector(
                selector.NumberSelectorConfig(min=500, max=10000, step=50, unit_of_measurement="kg")
            ),
            vol.Required("weight_unit", default="kg"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value="kg", label="Kilograms"),
                        selector.SelectOptionDict(value="lbs", label="Pounds"),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required("max_xwind", default=15): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=50, step=1, unit_of_measurement="kt")
            ),
            vol.Required("baseline_roll", default=300): selector.NumberSelector(
                selector.NumberSelectorConfig(min=10, max=750, step=5, unit_of_measurement="m")
            ),
            vol.Required("baseline_50ft", default=600): selector.NumberSelector(
                selector.NumberSelectorConfig(min=10, max=1500, step=5, unit_of_measurement="m")
            ),
            vol.Required("distance_unit", default="m"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value="m", label="Meters"),
                        selector.SelectOptionDict(value="ft", label="Feet"),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Optional("hangar"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=hangar_options,
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Optional("linked_airfield"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=airfield_options,
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required("ifr_capable", default=False): selector.BooleanSelector(),
            
            # Fuel configuration section
            vol.Required("fuel_type", default="AVGAS"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value="AVGAS", label="AVGAS (Aviation Gasoline)"),
                        selector.SelectOptionDict(value="MOGAS", label="MOGAS (Motor Gasoline)"),
                        selector.SelectOptionDict(value="JET_A", label="JET-A (Kerosene)"),
                        selector.SelectOptionDict(value="JET_B", label="JET-B (Wide-cut)"),
                        selector.SelectOptionDict(value="DIESEL", label="Diesel"),
                        selector.SelectOptionDict(value="NONE", label="No Fuel (Glider/Electric)"),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required("fuel_burn_rate", default=0.0): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=500, step=0.5, unit_of_measurement="L/h")
            ),
            vol.Required("fuel_tank_capacity", default=0.0): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=2000, step=1, unit_of_measurement="L")
            ),
            vol.Required("fuel_volume_unit", default="liters"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value="liters", label="Liters"),
                        selector.SelectOptionDict(value="gallons", label="US Gallons"),
                        selector.SelectOptionDict(value="gallons_imperial", label="Imperial Gallons"),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
        })

    async def async_step_aircraft_manage(self, user_input=None):
        """Menu to manage existing aircraft."""
        fleet = self._list_from(self._entry_data().get("aircraft", []))
        options = {
            str(i): f"{a.get('reg', 'Aircraft')} ({a.get('model', 'Unknown')})" for i,
            a in enumerate(fleet)}

        if user_input is not None:
            self._index = int(user_input["index"])
            if user_input["action"] == "edit":
                return await self.async_step_aircraft_edit()
            return await self.async_step_aircraft_delete()

        return self.async_show_form(
            step_id="aircraft_manage",
            data_schema=vol.Schema(
                {
                    vol.Required("index"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=k,
                                    label=v) for k,
                                v in options.items()],
                            mode=selector.SelectSelectorMode.DROPDOWN)),
                    vol.Required("action"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=o["value"],
                                    label=o["label"]) for o in get_action_options(
                                    self._lang())],
                            mode=selector.SelectSelectorMode.DROPDOWN)),
                }))

    async def async_step_aircraft_edit(self, user_input=None):
        """Edit an existing aircraft."""
        index = self._index
        fleet = self._list_from(self._entry_data().get("aircraft", []))
        ac = self._safe_item(fleet, index)

        if user_input is not None:
            new_data = self._entry_data()
            fleet = self._list_from(new_data.get("aircraft", []))

            # Convert weights from lbs to kg if needed
            weight_unit = user_input.pop("weight_unit", "kg")
            if weight_unit == "lbs":
                user_input["empty_weight"] = round(
                    user_input["empty_weight"] * 0.453592, 2)
                user_input["max_tow"] = round(
                    user_input["max_tow"] * 0.453592, 2)

            # Convert distances from feet to meters if needed
            distance_unit = user_input.pop("distance_unit", "m")
            if distance_unit == "ft":
                user_input["baseline_roll"] = round(
                    user_input["baseline_roll"] * 0.3048, 2)
                user_input["baseline_50ft"] = round(
                    user_input["baseline_50ft"] * 0.3048, 2)
            
            # Process fuel configuration
            fuel_type = user_input.pop("fuel_type", ac.get("fuel", {}).get("type", "AVGAS"))
            fuel_burn_rate = user_input.pop("fuel_burn_rate", ac.get("fuel", {}).get("burn_rate", 0.0))
            fuel_tank_capacity = user_input.pop("fuel_tank_capacity", ac.get("fuel", {}).get("tank_capacity", 0.0))
            fuel_volume_unit = user_input.pop("fuel_volume_unit", ac.get("fuel", {}).get("burn_rate_unit", "liters"))
            
            user_input["fuel"] = {
                "type": fuel_type,
                "burn_rate": float(fuel_burn_rate),
                "burn_rate_unit": fuel_volume_unit,
                "tank_capacity": float(fuel_tank_capacity),
                "tank_capacity_unit": fuel_volume_unit,
                "notes": ac.get("fuel", {}).get("notes", "")
            }

            fleet[index] = user_input
            new_data["aircraft"] = fleet
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        airfields = [
            a.get(
                "name",
                "") for a in self._list_from(
                self._entry_data().get(
                    "airfields",
                    []))]
        airfield_options = [
            selector.SelectOptionDict(
                value=a,
                label=a) for a in airfields] if airfields else [
            selector.SelectOptionDict(
                value="",
                label="No airfields configured")]

        # Get hangars for dropdown
        hangars = self._list_from(self._entry_data().get("hangars", []))
        hangar_options = [
            selector.SelectOptionDict(
                value="",
                label="None (Use Airfield)")]
        for hangar in hangars:
            hangar_options.append(
                selector.SelectOptionDict(
                    value=hangar.get("name", ""),
                    label=f"{hangar.get('name', 'Hangar')} ({hangar.get('airfield_name', 'Unknown')})"
                )
            )

        return self.async_show_form(
            step_id="aircraft_edit",
            data_schema=vol.Schema({
                vol.Required("reg", default=ac.get("reg")): str,
                vol.Required("model", default=ac.get("model")): str,
                vol.Required("empty_weight", default=ac.get("empty_weight")): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=500, max=10000, step=50, unit_of_measurement="kg")
                ),
                vol.Required("max_tow", default=ac.get("max_tow")): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=500, max=10000, step=50, unit_of_measurement="kg")
                ),
                vol.Required("weight_unit", default="kg"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value="kg", label="Kilograms"),
                            selector.SelectOptionDict(value="lbs", label="Pounds"),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required("max_xwind", default=ac.get("max_xwind")): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=50, step=1, unit_of_measurement="kt")
                ),
                vol.Required("baseline_roll", default=ac.get("baseline_roll")): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10, max=750, step=5, unit_of_measurement="m")
                ),
                vol.Required("baseline_50ft", default=ac.get("baseline_50ft", 0)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10, max=1500, step=5, unit_of_measurement="m")
                ),
                vol.Required("distance_unit", default="m"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value="m", label="Meters"),
                            selector.SelectOptionDict(value="ft", label="Feet"),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                
                # Fuel configuration section
                vol.Required("fuel_type", default=ac.get("fuel", {}).get("type", "AVGAS")): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value="AVGAS", label="AVGAS (Aviation Gasoline)"),
                            selector.SelectOptionDict(value="MOGAS", label="MOGAS (Motor Gasoline)"),
                            selector.SelectOptionDict(value="JET_A", label="JET-A (Kerosene)"),
                            selector.SelectOptionDict(value="JET_B", label="JET-B (Wide-cut)"),
                            selector.SelectOptionDict(value="DIESEL", label="Diesel"),
                            selector.SelectOptionDict(value="NONE", label="No Fuel (Glider/Electric)"),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required("fuel_burn_rate", default=ac.get("fuel", {}).get("burn_rate", 0.0)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=500, step=0.5, unit_of_measurement="L/h")
                ),
                vol.Required("fuel_tank_capacity", default=ac.get("fuel", {}).get("tank_capacity", 0.0)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=2000, step=1, unit_of_measurement="L")
                ),
                vol.Required("fuel_volume_unit", default=ac.get("fuel", {}).get("burn_rate_unit", "liters")): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value="liters", label="Liters"),
                            selector.SelectOptionDict(value="gallons", label="US Gallons"),
                            selector.SelectOptionDict(value="gallons_imperial", label="Imperial Gallons"),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Optional("hangar", default=ac.get("hangar", "")): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=hangar_options,
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Optional("linked_airfield", default=ac.get("linked_airfield")): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=airfield_options,
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required("ifr_capable", default=ac.get("ifr_capable", False)): selector.BooleanSelector(),
            })
        )

    async def async_step_aircraft_delete(self, user_input=None):
        """Delete an aircraft."""
        if user_input is not None:
            if user_input["confirm"]:
                new_data = self._entry_data()
                fleet = self._list_from(new_data.get("aircraft", []))
                if 0 <= self._index < len(fleet):
                    fleet.pop(self._index)
                new_data["aircraft"] = fleet
                self.hass.config_entries.async_update_entry(
                    self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        return self.async_show_form(
            step_id="aircraft_delete",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "confirm",
                        default=False): selector.BooleanSelector()}),
            description_placeholders={
                "reg": self._safe_item(
                    self._list_from(
                        self._entry_data().get(
                            "aircraft",
                            [])),
                    self._index).get(
                    "reg",
                        "Aircraft")})

    async def async_step_pilot(self, user_input=None):
        """Sub-menu for pilot management."""
        pilots = self._list_from(self._entry_data().get("pilots", []))

        if pilots:
            return self.async_show_menu(
                step_id="pilot",
                menu_options=["pilot_add", "pilot_manage"]
            )

        # If no pilots exist, go straight to add form
        return await self.async_step_pilot_add()

    async def async_step_pilot_add(self, user_input=None):
        """Form to add a new pilot."""
        if user_input is not None:
            new_data = self._entry_data()
            pilots = self._list_from(new_data.get("pilots", []))
            pilots.append(user_input)
            new_data["pilots"] = pilots
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        return self.async_show_form(
            step_id="pilot_add",
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Required("email"): str,
                vol.Required("licence_number"): str,
                vol.Required("licence_type"): str,
                vol.Required("medical_expiry"): selector.DateSelector(),
                vol.Required("ifr_rating", default=False): selector.BooleanSelector(),
                vol.Required("night_rating", default=False): selector.BooleanSelector(),
                vol.Required("tailwheel_rating", default=False): selector.BooleanSelector(),
                vol.Required("complex_rating", default=False): selector.BooleanSelector(),
                vol.Required("high_performance_rating", default=False): selector.BooleanSelector(),
                vol.Required("multi_engine_rating", default=False): selector.BooleanSelector(),
                vol.Required("seaplane_rating", default=False): selector.BooleanSelector(),
                vol.Required("glider_rating", default=False): selector.BooleanSelector(),
                vol.Required("aerobatic_rating", default=False): selector.BooleanSelector(),
                vol.Required("mountain_rating", default=False): selector.BooleanSelector(),
            })
        )

    async def async_step_pilot_manage(self, user_input=None):
        """Menu to manage existing pilots."""
        pilots = self._list_from(self._entry_data().get("pilots", []))
        options = {str(i): p.get("name", f"Pilot {i}")
                   for i, p in enumerate(pilots)}

        if user_input is not None:
            self._index = int(user_input["index"])
            if user_input["action"] == "edit":
                return await self.async_step_pilot_edit()
            return await self.async_step_pilot_delete()

        return self.async_show_form(
            step_id="pilot_manage",
            data_schema=vol.Schema(
                {
                    vol.Required("index"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=k,
                                    label=v) for k,
                                v in options.items()],
                            mode=selector.SelectSelectorMode.DROPDOWN)),
                    vol.Required("action"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=o["value"],
                                    label=o["label"]) for o in get_action_options(
                                    self._lang())],
                            mode=selector.SelectSelectorMode.DROPDOWN)),
                }))

    async def async_step_pilot_edit(self, user_input=None):
        """Edit an existing pilot."""
        index = self._index
        pilots = self._list_from(self._entry_data().get("pilots", []))
        pilot = self._safe_item(pilots, index)

        if user_input is not None:
            new_data = self._entry_data()
            new_pilots = self._list_from(new_data.get("pilots", []))
            new_pilots[index] = user_input
            new_data["pilots"] = new_pilots
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        return self.async_show_form(
            step_id="pilot_edit",
            data_schema=vol.Schema({
                vol.Required("name", default=pilot.get("name")): str,
                vol.Required("email", default=pilot.get("email")): str,
                vol.Required("licence_number", default=pilot.get("licence_number")): str,
                vol.Required("licence_type", default=pilot.get("licence_type")): str,
                vol.Required("medical_expiry", default=pilot.get("medical_expiry")): selector.DateSelector(),
                vol.Required("ifr_rating", default=pilot.get("ifr_rating", False)): selector.BooleanSelector(),
                vol.Required("night_rating", default=pilot.get("night_rating", False)): selector.BooleanSelector(),
                vol.Required("tailwheel_rating", default=pilot.get("tailwheel_rating", False)): selector.BooleanSelector(),
                vol.Required("complex_rating", default=pilot.get("complex_rating", False)): selector.BooleanSelector(),
                vol.Required("high_performance_rating", default=pilot.get("high_performance_rating", False)): selector.BooleanSelector(),
                vol.Required("multi_engine_rating", default=pilot.get("multi_engine_rating", False)): selector.BooleanSelector(),
                vol.Required("seaplane_rating", default=pilot.get("seaplane_rating", False)): selector.BooleanSelector(),
                vol.Required("glider_rating", default=pilot.get("glider_rating", False)): selector.BooleanSelector(),
                vol.Required("aerobatic_rating", default=pilot.get("aerobatic_rating", False)): selector.BooleanSelector(),
                vol.Required("mountain_rating", default=pilot.get("mountain_rating", False)): selector.BooleanSelector(),
            })
        )

    async def async_step_pilot_delete(self, user_input=None):
        """Delete a pilot."""
        if user_input is not None:
            if user_input["confirm"]:
                new_data = self._entry_data()
                new_pilots = self._list_from(new_data.get("pilots", []))
                if 0 <= self._index < len(new_pilots):
                    new_pilots.pop(self._index)
                new_data["pilots"] = new_pilots
                self.hass.config_entries.async_update_entry(
                    self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        return self.async_show_form(
            step_id="pilot_delete",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "confirm",
                        default=False): selector.BooleanSelector()}),
            description_placeholders={
                "name": self._safe_item(
                    self._list_from(
                        self._entry_data().get(
                            "pilots",
                            [])),
                    self._index).get(
                    "name",
                        "Pilot")})

    async def async_step_ai(self, user_input=None):
        """Configure AI conversation assistant (generic across all tools)."""
        if user_input is not None:
            new_data = self._entry_data()
            new_data["ai_assistant"] = user_input
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        ai_config = self._entry_data().get("ai_assistant", {})
        use_custom = ai_config.get("use_custom_system_prompt", False)

        schema_dict = {
            vol.Required(
                "ai_agent_entity",
                default=ai_config.get(
                    "ai_agent_entity",
                    "")): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="conversation",
                    multiple=False)),
            vol.Optional(
                "use_custom_system_prompt",
                default=use_custom): selector.BooleanSelector(),
        }

        # Show custom prompt field if toggle is enabled
        if use_custom:
            schema_dict[vol.Optional("custom_system_prompt", default=ai_config.get(
                "custom_system_prompt", ""))] = selector.TextSelector()

        return self.async_show_form(
            step_id="ai",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "default_prompt_preview": DEFAULT_AI_SYSTEM_PROMPT[:200] + "..."
            }
        )

    async def async_step_briefing(self, _user_input=None):
        """Sub-menu for configuring automated briefings."""
        briefings = self._list_from(self._entry_data().get("briefings", []))

        if briefings:
            return self.async_show_menu(
                step_id="briefing",
                menu_options=["briefing_add", "briefing_manage"]
            )

        # If no briefings exist, go straight to add form
        return await self.async_step_briefing_add()

    async def async_step_briefing_add(self, user_input=None):
        """Form to add a new automated briefing."""
        if user_input is not None:
            new_data = self._entry_data()
            briefings = self._list_from(new_data.get("briefings", []))
            briefings.append(user_input)
            new_data["briefings"] = briefings
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        # Get existing airfields, aircraft, and pilots for selection
        airfields = [
            a.get(
                "name",
                "") for a in self._list_from(
                self._entry_data().get(
                    "airfields",
                    []))]
        aircraft = [
            a.get(
                "reg",
                "") for a in self._list_from(
                self._entry_data().get(
                    "aircraft",
                    []))]
        pilots = [
            p.get(
                "name",
                "") for p in self._list_from(
                self._entry_data().get(
                    "pilots",
                    []))]

        return self.async_show_form(
            step_id="briefing_add",
            data_schema=vol.Schema({
                vol.Required("airfield_name"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[selector.SelectOptionDict(value=a, label=a) for a in airfields],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required("aircraft_reg"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[selector.SelectOptionDict(value=a, label=a) for a in aircraft],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required("briefing_time"): selector.TimeSelector(),
                vol.Required("pilots"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[selector.SelectOptionDict(value=p, label=p) for p in pilots],
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST
                    )
                ),
                vol.Optional("enable_ai_reporting", default=False): selector.BooleanSelector(),
            })
        )

    async def async_step_briefing_manage(self, user_input=None):
        """Menu to manage existing briefings."""
        briefings = self._list_from(self._entry_data().get("briefings", []))

        if user_input is not None:
            action = user_input.get("action")
            index = user_input.get("briefing_index")

            if action == "edit" and index is not None:
                self._briefing_index = int(index)
                return await self.async_step_briefing_edit()
            elif action == "delete" and index is not None:
                self._briefing_index = int(index)
                return await self.async_step_briefing_delete()

        briefing_options = {
            str(i): f"{', '.join(b.get('pilots', []))} ({b['airfield_name']})"
            for i, b in enumerate(briefings)
        }

        return self.async_show_form(
            step_id="briefing_manage",
            data_schema=vol.Schema(
                {
                    vol.Required("briefing_index"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=k,
                                    label=v) for k,
                                v in briefing_options.items()],
                            mode=selector.SelectSelectorMode.DROPDOWN)),
                    vol.Required("action"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=o["value"],
                                    label=o["label"]) for o in get_action_options(
                                    self._lang())],
                            mode=selector.SelectSelectorMode.DROPDOWN)),
                }))

    async def async_step_briefing_edit(self, user_input=None):
        """Edit an existing automated briefing."""
        index = self._briefing_index
        briefings = self._list_from(self._entry_data().get("briefings", []))

        if index >= len(briefings):
            return self.async_abort(reason="reconfigure_successful")

        briefing = self._safe_item(briefings, index)

        if user_input is not None:
            new_data = self._entry_data()
            new_briefings = self._list_from(new_data.get("briefings", []))
            new_briefings[index] = user_input
            new_data["briefings"] = new_briefings
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        # Get existing airfields, aircraft, and pilots for selection
        airfields = [
            a.get(
                "name",
                "") for a in self._list_from(
                self._entry_data().get(
                    "airfields",
                    []))]
        aircraft = [
            a.get(
                "reg",
                "") for a in self._list_from(
                self._entry_data().get(
                    "aircraft",
                    []))]
        pilots = [
            p.get(
                "name",
                "") for p in self._list_from(
                self._entry_data().get(
                    "pilots",
                    []))]

        return self.async_show_form(
            step_id="briefing_edit",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "airfield_name",
                        default=briefing.get("airfield_name")): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=a,
                                    label=a) for a in airfields],
                            mode=selector.SelectSelectorMode.DROPDOWN)),
                    vol.Required(
                        "aircraft_reg",
                        default=briefing.get("aircraft_reg")): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=a,
                                    label=a) for a in aircraft],
                            mode=selector.SelectSelectorMode.DROPDOWN)),
                    vol.Required(
                        "briefing_time",
                        default=briefing.get("briefing_time")): selector.TimeSelector(),
                    vol.Required(
                        "pilots",
                        default=briefing.get(
                            "pilots",
                            [])): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=p,
                                    label=p) for p in pilots],
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST)),
                    vol.Optional(
                        "enable_ai_reporting",
                        default=briefing.get(
                            "enable_ai_reporting",
                            False)): selector.BooleanSelector(),
                }))

    async def async_step_briefing_delete(self, user_input=None):
        """Confirm deletion of a briefing."""
        index = self._briefing_index
        briefings = self._list_from(self._entry_data().get("briefings", []))

        if index >= len(briefings):
            return self.async_abort(reason="reconfigure_successful")

        briefing = self._safe_item(briefings, index)

        if user_input is not None:
            if user_input.get("confirm_delete"):
                new_data = self._entry_data()
                new_briefings = self._list_from(new_data.get("briefings", []))
                if 0 <= index < len(new_briefings):
                    new_briefings.pop(index)
                new_data["briefings"] = new_briefings
                self.hass.config_entries.async_update_entry(
                    self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        return self.async_show_form(
            step_id="briefing_delete",
            data_schema=vol.Schema({
                vol.Required("confirm_delete", default=False): selector.BooleanSelector(),
            }),
            description_placeholders={
                "briefing": f"{', '.join(briefing.get('pilots', []))} for {briefing.get('airfield_name')}"
            }
        )

    async def async_step_dashboard(self, user_input=None):
        """Manage Hangar Assistant dashboard."""
        if user_input is not None:
            if user_input.get("recreate_dashboard", False):
                # Recreate the dashboard directly to avoid service dependencies
                from . import async_create_dashboard

                await async_create_dashboard(
                    self.hass,
                    self._config_entry,
                    force_rebuild=True,
                    reason="options_flow",
                )
            if user_input.get("send_setup_help", False):
                instructions = (
                    "Hangar Assistant dashboard setup\n\n"
                    "1) In configuration.yaml add:\n"
                    "   lovelace:\n"
                    "     dashboards:\n"
                    "       hangar-assistant:\n"
                    "         mode: yaml\n"
                    "         title: Hangar Assistant\n"
                    "         icon: mdi:airplane\n"
                    "         show_in_sidebar: true\n"
                    "         filename: /config/custom_components/hangar_assistant/dashboard_templates/glass_cockpit.yaml\n"
                    "2) Reload dashboards (Settings → Dashboards → …) or restart HA.\n"
                    "3) Ensure input_select.airfield_selector (and optional input_select.aircraft_selector) exist with slugs matching your sensors.\n\n"
                    "An optional automation can listen for the event 'hangar_assistant_dashboard_setup' if you want to hook a script or helper flow.")
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": "Hangar Assistant Dashboard",
                        "message": instructions,
                        "notification_id": "hangar_assistant_dashboard_help",
                    },
                    blocking=False,
                )
            if user_input.get("fire_setup_event", False):
                self.hass.bus.async_fire("hangar_assistant_dashboard_setup")
            return self.async_create_entry(data=self._entry_options())

        # Get current dashboard info
        dashboard_info = self._entry_data().get("dashboard_info", {})
        current_version = dashboard_info.get("version", 0)
        last_updated = dashboard_info.get("last_updated", "Never")
        integration_version = dashboard_info.get(
            "integration_version", "Unknown")

        return self.async_show_form(
            step_id="dashboard",
            data_schema=vol.Schema({
                vol.Optional("recreate_dashboard", default=False): selector.BooleanSelector(),
                vol.Optional("send_setup_help", default=False): selector.BooleanSelector(),
                vol.Optional("fire_setup_event", default=False): selector.BooleanSelector(),
            }),
            description_placeholders={
                "current_version": str(current_version),
                "template_version": str(DEFAULT_DASHBOARD_VERSION),
                "last_updated": str(last_updated),
                "integration_version": str(integration_version),
            }
        )

    async def async_step_retention(self, user_input=None):
        """Configure data retention policy."""
        if user_input is not None:
            new_data = self._entry_data()
            new_data["retention"] = {
                "auto_delete_enabled": user_input.get(
                    "auto_delete_enabled", True), "retention_months": user_input.get(
                    "retention_months", 7)}
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        retention_config = self._entry_data().get("retention", {})

        return self.async_show_form(
            step_id="retention", data_schema=vol.Schema(
                {
                    vol.Optional(
                        "auto_delete_enabled", default=retention_config.get(
                            "auto_delete_enabled", True)): selector.BooleanSelector(), vol.Optional(
                        "retention_months", default=retention_config.get(
                            "retention_months", 7)): selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    min=1, max=120, step=1, unit_of_measurement="months")), }))

    # ========== Integrations Menu ==========

    async def async_step_integrations(self, _user_input=None):
        """Sub-menu for external integrations."""
        return self.async_show_menu(
            step_id="integrations",
            menu_options=["integrations_openweathermap", "integrations_notams"]
        )

    async def async_step_integrations_openweathermap(self, user_input=None):
        """Configure OpenWeatherMap integration."""
        if user_input is not None:
            new_data = self._entry_data()
            if "integrations" not in new_data:
                new_data["integrations"] = {}

            new_data["integrations"]["openweathermap"] = {
                "enabled": user_input.get(
                    "enabled",
                    False),
                "api_key": user_input.get(
                    "api_key",
                    ""),
                "cache_enabled": user_input.get(
                    "cache_enabled",
                    True),
                "update_interval": user_input.get(
                    "update_interval",
                    10),
                "cache_ttl": user_input.get(
                    "cache_ttl",
                    10),
                "consecutive_failures": new_data.get(
                    "integrations",
                    {}).get(
                    "openweathermap",
                    {}).get(
                    "consecutive_failures",
                    0),
                "last_error": new_data.get(
                    "integrations",
                    {}).get(
                    "openweathermap",
                    {}).get("last_error"),
                "last_success": new_data.get(
                    "integrations",
                    {}).get(
                    "openweathermap",
                    {}).get("last_success")}

            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        # Get current OWM config (check both locations for backward compat)
        integrations = self._entry_data().get("integrations", {})
        owm_config = integrations.get("openweathermap", {})

        # If not in integrations, check old settings location
        if not owm_config:
            settings = self._entry_data().get("settings", {})
            owm_config = {
                "enabled": settings.get("openweathermap_enabled", False),
                "api_key": settings.get("openweathermap_api_key", ""),
                "cache_enabled": settings.get("openweathermap_cache_enabled", True),
                "update_interval": settings.get("openweathermap_update_interval", 10),
                "cache_ttl": settings.get("openweathermap_cache_ttl", 10)
            }

        # Build interval options
        interval_options = [
            selector.SelectOptionDict(value=5, label="5 minutes"),
            selector.SelectOptionDict(value=10, label="10 minutes"),
            selector.SelectOptionDict(value=15, label="15 minutes"),
            selector.SelectOptionDict(value=30, label="30 minutes"),
            selector.SelectOptionDict(value=60, label="60 minutes")
        ]

        ttl_options = [
            selector.SelectOptionDict(value=5, label="5 minutes"),
            selector.SelectOptionDict(value=10, label="10 minutes"),
            selector.SelectOptionDict(value=15, label="15 minutes"),
            selector.SelectOptionDict(value=30, label="30 minutes")
        ]

        return self.async_show_form(
            step_id="integrations_openweathermap",
            data_schema=vol.Schema({
                vol.Required("enabled", default=owm_config.get("enabled", False)): selector.BooleanSelector(),
                vol.Optional("api_key", default=owm_config.get("api_key", "")): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                vol.Optional("cache_enabled", default=owm_config.get("cache_enabled", True)): selector.BooleanSelector(),
                vol.Optional("update_interval", default=owm_config.get("update_interval", 10)): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=interval_options, mode=selector.SelectSelectorMode.DROPDOWN)
                ),
                vol.Optional("cache_ttl", default=owm_config.get("cache_ttl", 10)): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=ttl_options, mode=selector.SelectSelectorMode.DROPDOWN)
                ),
            })
        )

    async def async_step_integrations_notams(self, user_input=None):
        """Configure NOTAM integration."""
        if user_input is not None:
            new_data = self._entry_data()
            if "integrations" not in new_data:
                new_data["integrations"] = {}

            new_data["integrations"]["notams"] = {
                "enabled": user_input.get(
                    "enabled",
                    True),
                "update_time": user_input.get(
                    "update_time",
                    "02:00"),
                "cache_days": user_input.get(
                    "cache_days",
                    7),
                "consecutive_failures": new_data.get(
                    "integrations",
                    {}).get(
                        "notams",
                        {}).get(
                            "consecutive_failures",
                            0),
                "last_error": new_data.get(
                    "integrations",
                    {}).get(
                    "notams",
                    {}).get("last_error"),
                "last_update": new_data.get(
                    "integrations",
                    {}).get(
                    "notams",
                    {}).get("last_update"),
                "stale_cache_allowed": True}

            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        # Get current NOTAM config
        integrations = self._entry_data().get("integrations", {})
        notam_config = integrations.get("notams", {
            "enabled": False,  # Default off for existing installs
            "update_time": "02:00",
            "cache_days": 7
        })

        # Check if this is a new install (no existing integrations)
        is_new_install = not integrations
        if is_new_install:
            # Enable by default for new installs
            notam_config["enabled"] = True

        # Build cache retention options
        cache_options = [
            selector.SelectOptionDict(value=1, label="1 day"),
            selector.SelectOptionDict(value=3, label="3 days"),
            selector.SelectOptionDict(value=7, label="7 days"),
            selector.SelectOptionDict(value=14, label="14 days"),
            selector.SelectOptionDict(value=30, label="30 days")
        ]

        return self.async_show_form(
            step_id="integrations_notams", data_schema=vol.Schema(
                {
                    vol.Required(
                        "enabled", default=notam_config.get(
                            "enabled", False)): selector.BooleanSelector(), vol.Optional(
                        "update_time", default=notam_config.get(
                            "update_time", "02:00")): selector.TimeSelector(), vol.Optional(
                                "cache_days", default=notam_config.get(
                                    "cache_days", 7)): selector.SelectSelector(
                                        selector.SelectSelectorConfig(
                                            options=cache_options, mode=selector.SelectSelectorMode.DROPDOWN)), }))
