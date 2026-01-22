# Hangar Assistant - UI/UX Implementation Plan

**Document Version**: 1.0  
**Date**: 22 January 2026  
**Status**: Implementation Ready  
**Target Release**: v2601.3.0  
**Estimated Timeline**: 7-10 days

---

## Table of Contents
- [Overview](#overview)
- [Implementation Phases](#implementation-phases)
- [Phase 1: Foundation](#phase-1-foundation)
- [Phase 2: Setup Wizard](#phase-2-setup-wizard)
- [Phase 3: API Integration Flows](#phase-3-api-integration-flows)
- [Phase 4: Dashboard Automation](#phase-4-dashboard-automation)
- [Phase 5: Templates & Validation](#phase-5-templates--validation)
- [Phase 6: Testing & Polish](#phase-6-testing--polish)
- [Code Implementation Details](#code-implementation-details)
- [Testing Strategy](#testing-strategy)
- [Rollout Plan](#rollout-plan)

---

## Overview

This plan implements the comprehensive first-time setup experience detailed in `FIRST_TIME_SETUP_UX_PLAN.md`. The implementation transforms Hangar Assistant from a complex aviation integration into an accessible, guided onboarding process.

**Key Goals:**
- ✅ Reduce time-to-value from 30+ minutes to <15 minutes
- ✅ Increase setup completion rate to 80%+
- ✅ Enable auto-population from CheckWX API
- ✅ Provide aircraft type templates
- ✅ Automate dashboard installation
- ✅ Real-time validation and error prevention

**Success Criteria:**
- Users complete setup without consulting documentation
- 70%+ users install dashboard via wizard
- 50%+ users configure at least one external API
- <5% setup-related support requests

---

## Implementation Phases

### Timeline Overview

```
Week 1: Foundation + Core Wizard (Days 1-5)
├── Day 1-2: Phase 1 - Foundation & detection
├── Day 3-4: Phase 2 - Core wizard steps
└── Day 5:   Phase 3 - API integration flows

Week 2: Advanced Features + Polish (Days 6-10)
├── Day 6-7: Phase 4 - Dashboard automation
├── Day 8:   Phase 5 - Templates & validation
└── Day 9-10: Phase 6 - Testing & polish
```

---

## Phase 1: Foundation
**Timeline**: Days 1-2  
**Estimated Effort**: 16 hours

### Task 1.1: First-Time Detection Logic
**File**: `custom_components/hangar_assistant/__init__.py`

```python
def should_show_setup_wizard(entry: ConfigEntry) -> bool:
    """Determine if setup wizard should be shown.
    
    Returns:
        True if this is a first-time setup or incomplete setup
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
```

**Test Cases**:
- ✅ Fresh install → Shows wizard
- ✅ Has airfields → Skips wizard
- ✅ Has aircraft → Skips wizard
- ✅ Setup flag set → Skips wizard

### Task 1.2: Wizard State Management
**File**: `custom_components/hangar_assistant/config_flow.py`

```python
class SetupWizardState:
    """State container for setup wizard progress."""
    
    def __init__(self):
        self.current_step: int = 0
        self.completed_steps: Set[str] = set()
        self.general_settings: Dict[str, Any] = {}
        self.api_configs: Dict[str, Any] = {}
        self.airfield_data: Optional[Dict] = None
        self.hangar_data: Optional[Dict] = None
        self.aircraft_data: Optional[Dict] = None
        self.sensor_links: Dict[str, str] = {}
        self.dashboard_method: str = "automatic"
    
    def mark_step_complete(self, step_name: str):
        """Mark a step as completed."""
        self.completed_steps.add(step_name)
    
    def can_skip_step(self, step_name: str) -> bool:
        """Check if a step can be skipped."""
        skip_rules = {
            "api_integrations": True,  # Always optional
            "add_hangar": True,  # Always optional
            "link_sensors": True,  # Optional if APIs configured
            "install_dashboard": True,  # Optional
        }
        return skip_rules.get(step_name, False)
    
    def get_progress_percentage(self) -> int:
        """Calculate setup progress percentage."""
        total_steps = 7
        return int((len(self.completed_steps) / total_steps) * 100)
```

### Task 1.3: Welcome Screen Constants
**File**: `custom_components/hangar_assistant/const.py`

```python
# Setup Wizard Constants
SETUP_WIZARD_VERSION = "1.0"

WELCOME_TITLE = "Welcome to Hangar Assistant!"
WELCOME_DESCRIPTION = """
The complete aviation safety and operations integration for Home Assistant.

What You Can Do:
• Monitor airfield conditions (weather, density altitude)
• Track aircraft performance limits & safety margins
• Get AI-generated pre-flight safety briefings
• Receive alerts for unsafe flying conditions
• Calculate fuel costs & trip planning
• Manage weight & balance
• Log flights & maintenance

Setup Time: 10-15 minutes
"""

SETUP_STEPS = [
    "General Settings",
    "External Integrations",
    "Add First Airfield",
    "Add Hangar (Optional)",
    "Add First Aircraft",
    "Connect Weather Sensors",
    "Install Dashboard",
]

# Aircraft Templates
AIRCRAFT_TEMPLATES = {
    "cessna_172": {
        "name": "Cessna 172 Skyhawk",
        "mtow_kg": 1157,
        "empty_weight_kg": 743,
        "min_runway_m": 500,
        "cruise_speed_kts": 105,
        "fuel_type": "AVGAS",
        "fuel_burn_lh": 35,
        "fuel_capacity_l": 155,
    },
    "piper_pa28": {
        "name": "Piper PA-28 Cherokee",
        "mtow_kg": 1111,
        "empty_weight_kg": 612,
        "min_runway_m": 480,
        "cruise_speed_kts": 110,
        "fuel_type": "AVGAS",
        "fuel_burn_lh": 38,
        "fuel_capacity_l": 189,
    },
    "diamond_da40": {
        "name": "Diamond DA40",
        "mtow_kg": 1150,
        "empty_weight_kg": 750,
        "min_runway_m": 400,
        "cruise_speed_kts": 130,
        "fuel_type": "AVGAS",
        "fuel_burn_lh": 28,
        "fuel_capacity_l": 155,
    },
    "cirrus_sr20": {
        "name": "Cirrus SR20",
        "mtow_kg": 1497,
        "empty_weight_kg": 953,
        "min_runway_m": 533,
        "cruise_speed_kts": 155,
        "fuel_type": "AVGAS",
        "fuel_burn_lh": 50,
        "fuel_capacity_l": 227,
    },
    "glider_generic": {
        "name": "Glider (Generic)",
        "mtow_kg": 600,
        "empty_weight_kg": 350,
        "min_runway_m": 300,
        "cruise_speed_kts": 60,
        "fuel_type": "NONE",
        "fuel_burn_lh": 0,
        "fuel_capacity_l": 0,
    },
}

# Validation Patterns
ICAO_PATTERN = r"^[A-Z]{4}$"
UK_REG_PATTERN = r"^[A-Z]-[A-Z]{4}$"
US_REG_PATTERN = r"^[A-Z]\d{4,5}[A-Z]?$"
EU_REG_PATTERN = r"^[A-Z]{2}-[A-Z]{3}$"
```

---

## Phase 2: Setup Wizard
**Timeline**: Days 3-4  
**Estimated Effort**: 16 hours

### Task 2.1: Wizard Flow Handler
**File**: `custom_components/hangar_assistant/config_flow.py`

```python
class HangarAssistantSetupWizardFlow(ConfigFlow, domain=DOMAIN):
    """Setup wizard for first-time configuration."""
    
    VERSION = 1
    
    def __init__(self):
        """Initialize setup wizard."""
        self.wizard_state = SetupWizardState()
    
    async def async_step_user(self, user_input=None):
        """Handle initial flow entry point."""
        # Check if wizard should be shown
        if should_show_setup_wizard(self.hass):
            return await self.async_step_welcome()
        else:
            # Skip to normal config flow
            return await self.async_step_manual_config()
    
    async def async_step_welcome(self, user_input=None):
        """Show welcome screen."""
        if user_input is not None:
            if user_input.get("start_wizard", True):
                return await self.async_step_general_settings()
            else:
                return await self.async_step_manual_config()
        
        return self.async_show_form(
            step_id="welcome",
            data_schema=vol.Schema({
                vol.Required("start_wizard", default=True): bool,
            }),
            description_placeholders={
                "title": WELCOME_TITLE,
                "description": WELCOME_DESCRIPTION,
                "steps": "\n".join(f"{i+1}. {step}" for i, step in enumerate(SETUP_STEPS)),
            },
        )
    
    async def async_step_general_settings(self, user_input=None):
        """Step 1: General settings."""
        errors = {}
        
        if user_input is not None:
            # Validate input
            self.wizard_state.general_settings = user_input
            self.wizard_state.mark_step_complete("general_settings")
            return await self.async_step_api_integrations()
        
        return self.async_show_form(
            step_id="general_settings",
            data_schema=vol.Schema({
                vol.Optional("setup_name", default=""): str,
                vol.Required("unit_preference", default="aviation"): vol.In(["aviation", "si"]),
                vol.Required("language", default="en"): vol.In(["en", "de", "es", "fr"]),
            }),
            errors=errors,
            description_placeholders={
                "step": "1 of 7",
                "progress": str(self.wizard_state.get_progress_percentage()),
            },
        )
    
    async def async_step_api_integrations(self, user_input=None):
        """Step 2: API integrations (optional but recommended)."""
        errors = {}
        
        if user_input is not None:
            if user_input.get("skip", False):
                self.wizard_state.mark_step_complete("api_integrations")
                return await self.async_step_add_airfield()
            
            # Handle API setup based on selections
            if user_input.get("setup_checkwx", False):
                return await self.async_step_checkwx_setup()
            elif user_input.get("setup_owm", False):
                return await self.async_step_owm_setup()
            else:
                self.wizard_state.mark_step_complete("api_integrations")
                return await self.async_step_add_airfield()
        
        return self.async_show_form(
            step_id="api_integrations",
            data_schema=vol.Schema({
                vol.Optional("setup_checkwx", default=False): bool,
                vol.Optional("setup_owm", default=False): bool,
                vol.Optional("skip", default=False): bool,
            }),
            errors=errors,
            description_placeholders={
                "step": "2 of 7",
                "progress": str(self.wizard_state.get_progress_percentage()),
                "recommendation": "⚡ Recommended: Setup APIs now to enable auto-population!",
            },
        )
```

### Task 2.2: CheckWX Setup Sub-Flow
**File**: `custom_components/hangar_assistant/config_flow.py`

```python
async def async_step_checkwx_setup(self, user_input=None):
    """Configure CheckWX API integration."""
    errors = {}
    
    if user_input is not None:
        api_key = user_input.get("api_key", "").strip()
        
        # Validate API key
        if not api_key:
            errors["api_key"] = "api_key_required"
        else:
            # Test connection
            from .utils.checkwx_client import CheckWXClient
            client = CheckWXClient(api_key, self.hass)
            
            try:
                # Test with a known ICAO code
                test_data = await client.get_metar("KJFK")
                if test_data:
                    # Success - store config
                    self.wizard_state.api_configs["checkwx"] = {
                        "enabled": True,
                        "api_key": api_key,
                        "metar_enabled": user_input.get("metar_enabled", True),
                        "taf_enabled": user_input.get("taf_enabled", True),
                        "station_enabled": user_input.get("station_enabled", True),
                        "metar_cache_minutes": user_input.get("metar_cache_minutes", 30),
                        "taf_cache_minutes": user_input.get("taf_cache_minutes", 360),
                    }
                    
                    # Show success message and continue
                    return self.async_show_form(
                        step_id="checkwx_success",
                        data_schema=vol.Schema({}),
                        description_placeholders={
                            "metar": test_data.get("raw_text", ""),
                            "decoded": str(test_data),
                        },
                    )
                else:
                    errors["api_key"] = "connection_failed"
            except Exception as e:
                _LOGGER.error("CheckWX API test failed: %s", e)
                errors["base"] = "api_test_failed"
    
    return self.async_show_form(
        step_id="checkwx_setup",
        data_schema=vol.Schema({
            vol.Required("api_key"): str,
            vol.Optional("metar_enabled", default=True): bool,
            vol.Optional("taf_enabled", default=True): bool,
            vol.Optional("station_enabled", default=True): bool,
            vol.Optional("metar_cache_minutes", default=30): vol.All(
                vol.Coerce(int), vol.Range(min=15, max=120)
            ),
            vol.Optional("taf_cache_minutes", default=360): vol.All(
                vol.Coerce(int), vol.Range(min=60, max=720)
            ),
        }),
        errors=errors,
        description_placeholders={
            "signup_url": "https://www.checkwxapi.com/signup",
            "instructions": "1. Visit signup URL\n2. Create free account\n3. Copy API key from profile",
        },
    )
```

### Task 2.3: Add Airfield with Auto-Populate
**File**: `custom_components/hangar_assistant/config_flow.py`

```python
async def async_step_add_airfield(self, user_input=None):
    """Step 3: Add first airfield."""
    errors = {}
    
    if user_input is not None:
        icao = user_input.get("icao", "").strip().upper()
        
        # Validate ICAO format
        if not re.match(ICAO_PATTERN, icao):
            errors["icao"] = "invalid_icao"
        else:
            # Check if user wants auto-populate
            if user_input.get("auto_populate", False):
                # Try CheckWX auto-population
                if "checkwx" in self.wizard_state.api_configs:
                    try:
                        station_data = await self._fetch_checkwx_station(icao)
                        if station_data:
                            # Show populated data for confirmation
                            return await self.async_step_airfield_confirm(station_data)
                        else:
                            errors["icao"] = "icao_not_found"
                    except Exception as e:
                        _LOGGER.error("CheckWX station fetch failed: %s", e)
                        errors["base"] = "auto_populate_failed"
                else:
                    errors["base"] = "no_api_configured"
            else:
                # Manual entry
                return await self.async_step_airfield_manual({"icao": icao})
    
    # Show form
    has_checkwx = "checkwx" in self.wizard_state.api_configs
    
    return self.async_show_form(
        step_id="add_airfield",
        data_schema=vol.Schema({
            vol.Required("icao"): str,
            vol.Optional("auto_populate", default=has_checkwx): bool,
        }),
        errors=errors,
        description_placeholders={
            "step": "3 of 7",
            "progress": str(self.wizard_state.get_progress_percentage()),
            "checkwx_available": "✨ CheckWX detected - auto-populate available!" if has_checkwx else "",
        },
    )

async def _fetch_checkwx_station(self, icao: str) -> Optional[Dict]:
    """Fetch station data from CheckWX."""
    from .utils.checkwx_client import CheckWXClient
    
    api_key = self.wizard_state.api_configs["checkwx"]["api_key"]
    client = CheckWXClient(api_key, self.hass)
    
    # Fetch station info
    station = await client.get_station_info(icao)
    if not station:
        return None
    
    # Fetch current METAR for additional data
    metar = await client.get_metar(icao)
    
    return {
        "icao": icao,
        "name": station.get("name", icao),
        "location": station.get("location", ""),
        "latitude": station.get("latitude"),
        "longitude": station.get("longitude"),
        "elevation_ft": station.get("elevation_ft"),
        "elevation_m": station.get("elevation_m"),
        "current_metar": metar.get("raw_text", "") if metar else None,
        "flight_category": metar.get("flight_category", "") if metar else None,
    }

async def async_step_airfield_confirm(self, station_data: Dict):
    """Confirm auto-populated airfield data."""
    if user_input is not None:
        if user_input.get("use_data", True):
            self.wizard_state.airfield_data = station_data
            self.wizard_state.mark_step_complete("add_airfield")
            return await self.async_step_add_hangar()
        else:
            # User wants to edit manually
            return await self.async_step_airfield_manual(station_data)
    
    return self.async_show_form(
        step_id="airfield_confirm",
        data_schema=vol.Schema({
            vol.Required("use_data", default=True): bool,
        }),
        description_placeholders={
            "icao": station_data["icao"],
            "name": station_data["name"],
            "location": station_data["location"],
            "elevation": f"{station_data.get('elevation_ft', 0)} ft / {station_data.get('elevation_m', 0)} m",
            "coordinates": f"{station_data.get('latitude', 0):.4f}°, {station_data.get('longitude', 0):.4f}°",
            "metar": station_data.get("current_metar", "N/A"),
            "flight_category": station_data.get("flight_category", "Unknown"),
        },
    )
```

### Task 2.4: Aircraft Template Selection
**File**: `custom_components/hangar_assistant/config_flow.py`

```python
async def async_step_add_aircraft(self, user_input=None):
    """Step 5: Add first aircraft."""
    errors = {}
    
    if user_input is not None:
        registration = user_input.get("registration", "").strip().upper()
        
        # Validate registration format
        if not self._validate_registration(registration):
            errors["registration"] = "invalid_registration"
        else:
            aircraft_type = user_input.get("aircraft_type", "")
            
            # Check if user wants to load template
            if user_input.get("load_template", False) and aircraft_type in AIRCRAFT_TEMPLATES:
                template = AIRCRAFT_TEMPLATES[aircraft_type]
                return await self.async_step_aircraft_template_confirm({
                    "registration": registration,
                    "template": aircraft_type,
                    **template
                })
            else:
                # Manual entry
                return await self.async_step_aircraft_manual({"registration": registration})
    
    return self.async_show_form(
        step_id="add_aircraft",
        data_schema=vol.Schema({
            vol.Required("registration"): str,
            vol.Optional("aircraft_type"): vol.In(list(AIRCRAFT_TEMPLATES.keys())),
            vol.Optional("load_template", default=False): bool,
        }),
        errors=errors,
        description_placeholders={
            "step": "5 of 7",
            "progress": str(self.wizard_state.get_progress_percentage()),
            "template_hint": "✨ Select aircraft type to load default specs",
        },
    )

def _validate_registration(self, registration: str) -> bool:
    """Validate aircraft registration format."""
    patterns = [UK_REG_PATTERN, US_REG_PATTERN, EU_REG_PATTERN]
    return any(re.match(pattern, registration) for pattern in patterns)

async def async_step_aircraft_template_confirm(self, template_data: Dict):
    """Confirm aircraft template data."""
    if user_input is not None:
        if user_input.get("use_template", True):
            self.wizard_state.aircraft_data = template_data
            self.wizard_state.mark_step_complete("add_aircraft")
            return await self.async_step_link_sensors()
        else:
            # User wants to customize
            return await self.async_step_aircraft_manual(template_data)
    
    template_name = AIRCRAFT_TEMPLATES[template_data["template"]]["name"]
    
    return self.async_show_form(
        step_id="aircraft_template_confirm",
        data_schema=vol.Schema({
            vol.Required("use_template", default=True): bool,
        }),
        description_placeholders={
            "registration": template_data["registration"],
            "template": template_name,
            "mtow": f"{template_data['mtow_kg']} kg",
            "runway": f"{template_data['min_runway_m']} m",
            "cruise": f"{template_data['cruise_speed_kts']} kts",
            "fuel_type": template_data["fuel_type"],
            "fuel_burn": f"{template_data['fuel_burn_lh']} L/h",
        },
    )
```

---

## Phase 3: API Integration Flows
**Timeline**: Day 5  
**Estimated Effort**: 8 hours

### Task 3.1: OpenWeatherMap Setup Flow
**File**: `custom_components/hangar_assistant/config_flow.py`

```python
async def async_step_owm_setup(self, user_input=None):
    """Configure OpenWeatherMap API integration."""
    errors = {}
    
    if user_input is not None:
        api_key = user_input.get("api_key", "").strip()
        
        if not api_key:
            errors["api_key"] = "api_key_required"
        else:
            # Test OWM connection
            from .utils.openweathermap import OpenWeatherMapClient
            client = OpenWeatherMapClient(api_key, self.hass)
            
            try:
                # Test with default location (will be replaced with actual airfield)
                test_data = await client.get_weather_data(51.5074, -0.1278)  # London
                if test_data:
                    self.wizard_state.api_configs["openweathermap"] = {
                        "enabled": True,
                        "api_key": api_key,
                        "cache_enabled": user_input.get("cache_enabled", True),
                        "update_interval": user_input.get("update_interval", 10),
                        "cache_ttl": user_input.get("cache_ttl", 10),
                    }
                    
                    return await self.async_step_api_integrations()  # Back to integrations menu
                else:
                    errors["api_key"] = "connection_failed"
            except Exception as e:
                _LOGGER.error("OWM API test failed: %s", e)
                errors["base"] = "api_test_failed"
    
    return self.async_show_form(
        step_id="owm_setup",
        data_schema=vol.Schema({
            vol.Required("api_key"): str,
            vol.Optional("cache_enabled", default=True): bool,
            vol.Optional("update_interval", default=10): vol.All(
                vol.Coerce(int), vol.Range(min=5, max=60)
            ),
            vol.Optional("cache_ttl", default=10): vol.All(
                vol.Coerce(int), vol.Range(min=5, max=60)
            ),
        }),
        errors=errors,
        description_placeholders={
            "signup_url": "https://openweathermap.org/api",
            "pricing": "~$0.0012 per call (~$10-30/month typical)",
            "warning": "⚠️  This is a PAID service",
        },
    )
```

---

## Phase 4: Dashboard Automation
**Timeline**: Days 6-7  
**Estimated Effort**: 16 hours

### Task 4.1: Dashboard Installation Service
**File**: `custom_components/hangar_assistant/services.py`

```python
async def async_install_dashboard(
    hass: HomeAssistant,
    entry: ConfigEntry,
    method: str = "automatic",
) -> Dict[str, Any]:
    """Install Glass Cockpit dashboard.
    
    This service is called from the setup wizard's final step.
    
    Args:
        hass: Home Assistant instance
        entry: Config entry with airfield/aircraft data
        method: "automatic" (via API) or "manual" (return YAML)
    
    Returns:
        Dict with installation status, URL, and any errors
    """
    if method == "automatic":
        try:
            # Load template from file
            template_content = await _load_dashboard_template_with_cache(hass)
            if not template_content:
                return {
                    "success": False,
                    "error": "template_load_failed",
                    "message": "Failed to load dashboard template"
                }
            
            # Substitute entity IDs based on config
            dashboard_yaml = await _substitute_entity_ids(
                template_content,
                entry.data.get("airfields", []),
                entry.data.get("aircraft", [])
            )
            
            # Parse YAML
            try:
                dashboard_config = yaml.safe_load(dashboard_yaml)
            except yaml.YAMLError as e:
                _LOGGER.error("Invalid dashboard YAML: %s", e)
                return {
                    "success": False,
                    "error": "yaml_parse_error",
                    "message": str(e)
                }
            
            # Install via Lovelace service
            await hass.services.async_call(
                "lovelace",
                "create_dashboard",
                {
                    "url_path": "hangar-glass-cockpit",
                    "title": "Hangar Glass Cockpit",
                    "icon": "mdi:airplane",
                    "require_admin": False,
                    "mode": "storage",  # UI-editable
                    "show_in_sidebar": True,
                    "config": dashboard_config,
                },
                blocking=True,
            )
            
            # Copy JavaScript state manager to www/
            await _install_dashboard_resources(hass)
            
            # Mark dashboard as installed in config
            entry_data = dict(entry.data)
            entry_data.setdefault("settings", {})
            entry_data["settings"]["dashboard_installed"] = True
            entry_data["settings"]["dashboard_url"] = "/hangar-glass-cockpit"
            
            hass.config_entries.async_update_entry(entry, data=entry_data)
            
            return {
                "success": True,
                "url": "/hangar-glass-cockpit",
                "message": "Dashboard installed successfully",
                "method": "automatic",
            }
            
        except Exception as e:
            _LOGGER.error("Dashboard installation failed: %s", e, exc_info=True)
            return {
                "success": False,
                "error": "installation_failed",
                "message": str(e)
            }
    
    else:  # method == "manual"
        try:
            # Generate YAML for manual installation
            template_content = await _load_dashboard_template_with_cache(hass)
            dashboard_yaml = await _substitute_entity_ids(
                template_content,
                entry.data.get("airfields", []),
                entry.data.get("aircraft", [])
            )
            
            return {
                "success": True,
                "method": "manual",
                "yaml": dashboard_yaml,
                "instructions": MANUAL_DASHBOARD_INSTALL_INSTRUCTIONS,
            }
            
        except Exception as e:
            _LOGGER.error("Manual dashboard generation failed: %s", e)
            return {
                "success": False,
                "error": "generation_failed",
                "message": str(e)
            }


async def _load_dashboard_template_with_cache(hass: HomeAssistant) -> Optional[str]:
    """Load dashboard template with file caching."""
    # Use existing mtime-based cache from sensor.py pattern
    global _dashboard_template_cache, _dashboard_template_mtime
    
    template_path = Path(__file__).parent / "dashboard_templates" / "glass_cockpit.yaml"
    
    try:
        current_mtime = template_path.stat().st_mtime
        
        if (_dashboard_template_cache is not None 
            and _dashboard_template_mtime == current_mtime):
            return _dashboard_template_cache
        
        def _read():
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        content = await hass.async_add_executor_job(_read)
        _dashboard_template_cache = content
        _dashboard_template_mtime = current_mtime
        
        return content
        
    except OSError as e:
        _LOGGER.error("Failed to load dashboard template: %s", e)
        return None


async def _substitute_entity_ids(
    template: str,
    airfields: List[Dict],
    aircraft: List[Dict]
) -> str:
    """Substitute placeholder entity IDs with actual configured entities.
    
    Args:
        template: Raw template YAML with placeholders
        airfields: List of configured airfields
        aircraft: List of configured aircraft
    
    Returns:
        Dashboard YAML with substituted entity IDs
    """
    # Get default airfield/aircraft (first in list)
    default_airfield = airfields[0] if airfields else None
    default_aircraft = aircraft[0] if aircraft else None
    
    if not default_airfield:
        raise ValueError("No airfields configured")
    
    # Create substitution map
    airfield_slug = _slugify(default_airfield["name"])
    aircraft_slug = _slugify(default_aircraft["reg"]) if default_aircraft else "aircraft"
    
    substitutions = {
        "{{default_airfield}}": airfield_slug,
        "{{default_aircraft}}": aircraft_slug,
        "{{airfield_name}}": default_airfield["name"],
        "{{aircraft_reg}}": default_aircraft["reg"] if default_aircraft else "N/A",
    }
    
    # Apply substitutions
    result = template
    for placeholder, value in substitutions.items():
        result = result.replace(placeholder, value)
    
    return result


async def _install_dashboard_resources(hass: HomeAssistant):
    """Copy dashboard JavaScript resources to www/ directory."""
    source_dir = Path(__file__).parent / "dashboard_templates"
    www_dir = Path(hass.config.path("www"))
    
    # Ensure www/ exists
    www_dir.mkdir(exist_ok=True)
    
    # Copy JavaScript files
    js_files = ["hangar_state_manager.js"]
    
    for js_file in js_files:
        source = source_dir / js_file
        dest = www_dir / js_file
        
        if source.exists():
            def _copy():
                import shutil
                shutil.copy2(source, dest)
            
            await hass.async_add_executor_job(_copy)
            _LOGGER.info("Copied dashboard resource: %s", js_file)


def _slugify(text: str) -> str:
    """Convert text to slug format."""
    return text.lower().replace(" ", "_").replace("-", "_")


# Module-level cache for dashboard template
_dashboard_template_cache: Optional[str] = None
_dashboard_template_mtime: Optional[float] = None

# Manual installation instructions
MANUAL_DASHBOARD_INSTALL_INSTRUCTIONS = """
# Manual Dashboard Installation

1. Copy the YAML below to a file: `/config/hangar_dashboard.yaml`

2. Add this to your `configuration.yaml`:

```yaml
lovelace:
  mode: yaml
  dashboards:
    hangar-glass-cockpit:
      mode: yaml
      title: Hangar Glass Cockpit
      icon: mdi:airplane
      show_in_sidebar: true
      filename: hangar_dashboard.yaml
```

3. Restart Home Assistant

4. Dashboard will appear in sidebar

For help, see: https://github.com/pfrye/ha-hangar-assistant/docs/dashboard_setup.md
"""
```

### Task 4.2: Dashboard Installation Flow Step
**File**: `custom_components/hangar_assistant/config_flow.py`

```python
async def async_step_install_dashboard(self, user_input=None):
    """Step 7: Install dashboard."""
    errors = {}
    
    if user_input is not None:
        method = user_input.get("installation_method", "automatic")
        
        if user_input.get("skip", False):
            # User skipped dashboard installation
            self.wizard_state.mark_step_complete("install_dashboard")
            return await self.async_step_complete()
        
        if method == "automatic":
            # Install dashboard via service
            result = await async_install_dashboard(
                self.hass,
                self._get_temp_entry(),
                method="automatic"
            )
            
            if result["success"]:
                self.wizard_state.dashboard_method = "automatic"
                self.wizard_state.mark_step_complete("install_dashboard")
                return await self.async_step_complete()
            else:
                errors["base"] = result.get("error", "installation_failed")
        
        elif method == "manual":
            # Generate manual instructions
            result = await async_install_dashboard(
                self.hass,
                self._get_temp_entry(),
                method="manual"
            )
            
            if result["success"]:
                return await self.async_step_dashboard_manual_instructions(result)
            else:
                errors["base"] = result.get("error", "generation_failed")
    
    return self.async_show_form(
        step_id="install_dashboard",
        data_schema=vol.Schema({
            vol.Required("installation_method", default="automatic"): vol.In([
                "automatic",
                "manual"
            ]),
            vol.Optional("skip", default=False): bool,
        }),
        errors=errors,
        description_placeholders={
            "step": "7 of 7",
            "progress": str(self.wizard_state.get_progress_percentage()),
            "dashboard_url": "/hangar-glass-cockpit",
            "features": """
• Live airfield conditions
• Aircraft performance margins
• Best runway selection
• AI safety briefings
• Fuel cost estimates
• NOTAMs and alerts
            """,
        },
    )

def _get_temp_entry(self) -> ConfigEntry:
    """Create temporary config entry for dashboard generation."""
    # Construct entry data from wizard state
    data = {
        "settings": self.wizard_state.general_settings,
        "integrations": self.wizard_state.api_configs,
        "airfields": [self.wizard_state.airfield_data] if self.wizard_state.airfield_data else [],
        "aircraft": [self.wizard_state.aircraft_data] if self.wizard_state.aircraft_data else [],
    }
    
    # Create mock config entry
    from homeassistant.config_entries import ConfigEntry
    return ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Hangar Assistant",
        data=data,
        source="user",
        options={},
    )
```

---

## Phase 5: Templates & Validation
**Timeline**: Day 8  
**Estimated Effort**: 8 hours

### Task 5.1: Real-Time Validation Helpers
**File**: `custom_components/hangar_assistant/validation.py`

```python
"""Validation helpers for setup wizard."""
import re
from typing import Tuple, Optional

# Validation patterns
ICAO_PATTERN = r"^[A-Z]{4}$"
UK_REG_PATTERN = r"^[A-Z]-[A-Z]{4}$"
US_REG_PATTERN = r"^[A-Z]\d{4,5}[A-Z]?$"
EU_REG_PATTERN = r"^[A-Z]{2}-[A-Z]{3}$"


def validate_icao(icao: str) -> Tuple[bool, Optional[str]]:
    """Validate ICAO airport code.
    
    Args:
        icao: ICAO code to validate (will be uppercased)
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not icao:
        return False, "ICAO code is required"
    
    icao = icao.strip().upper()
    
    if len(icao) != 4:
        return False, "ICAO codes are exactly 4 characters (e.g., EGHP, KJFK)"
    
    if not icao.isalpha():
        return False, "ICAO codes contain only letters (no numbers)"
    
    if not icao.isupper():
        return False, "ICAO codes must be uppercase"
    
    return True, None


def validate_registration(reg: str) -> Tuple[bool, Optional[str]]:
    """Validate aircraft registration.
    
    Args:
        reg: Aircraft registration to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not reg:
        return False, "Aircraft registration is required"
    
    reg = reg.strip().upper()
    
    if len(reg) < 3:
        return False, "Registration too short (e.g., G-ABCD, N12345)"
    
    # Check against known patterns
    patterns = {
        UK_REG_PATTERN: "UK format: G-ABCD",
        US_REG_PATTERN: "US format: N12345",
        EU_REG_PATTERN: "EU format: D-EFGH",
    }
    
    for pattern, example in patterns.items():
        if re.match(pattern, reg):
            return True, None
    
    return False, f"Registration format not recognized. Examples: {', '.join(patterns.values())}"


def validate_mtow(value: float, unit: str) -> Tuple[bool, Optional[str]]:
    """Validate Maximum Takeoff Weight.
    
    Args:
        value: MTOW value
        unit: "kg" or "lbs"
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if value <= 0:
        return False, "MTOW must be greater than 0"
    
    # Reasonable ranges for GA aircraft
    if unit == "kg":
        if value < 300 or value > 5000:
            return False, f"MTOW {value} kg seems unusual. Typical range: 300-5000 kg"
    elif unit == "lbs":
        if value < 660 or value > 11000:
            return False, f"MTOW {value} lbs seems unusual. Typical range: 660-11000 lbs"
    else:
        return False, f"Unknown unit: {unit}"
    
    return True, None


def validate_api_key(api_key: str, service: str) -> Tuple[bool, Optional[str]]:
    """Validate API key format.
    
    Args:
        api_key: API key to validate
        service: Service name ("checkwx", "openweathermap", etc.)
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not api_key or not api_key.strip():
        return False, "API key is required"
    
    api_key = api_key.strip()
    
    # Basic length checks
    if len(api_key) < 16:
        return False, "API key seems too short. Please check and try again."
    
    # Service-specific validation
    if service == "checkwx":
        # CheckWX keys are typically 32+ chars
        if len(api_key) < 32:
            return False, "CheckWX API keys are typically 32+ characters"
    
    elif service == "openweathermap":
        # OWM keys are typically 32 hex chars
        if len(api_key) != 32:
            return False, "OpenWeatherMap API keys are 32 characters"
        if not all(c in "0123456789abcdefABCDEF" for c in api_key):
            return False, "OpenWeatherMap API keys are hexadecimal"
    
    return True, None


def get_validation_icon(is_valid: bool) -> str:
    """Get validation icon for UI display.
    
    Args:
        is_valid: Whether validation passed
    
    Returns:
        Icon string (✅ or ❌)
    """
    return "✅" if is_valid else "❌"


def format_validation_message(is_valid: bool, message: Optional[str] = None) -> str:
    """Format validation message with icon.
    
    Args:
        is_valid: Whether validation passed
        message: Error or success message
    
    Returns:
        Formatted message with icon
    """
    icon = get_validation_icon(is_valid)
    if message:
        return f"{icon} {message}"
    return f"{icon} {'Valid' if is_valid else 'Invalid'}"
```

### Task 5.2: Quick Start Templates
**File**: `custom_components/hangar_assistant/templates.py`

```python
"""Quick start templates for common setup scenarios."""
from typing import Dict, List


QUICK_START_TEMPLATES = {
    "uk_ppl_single": {
        "name": "UK PPL Single Aircraft",
        "description": "Single piston aircraft at UK airfield",
        "estimated_time": "10 minutes",
        "includes": [
            "1 airfield (UK ICAO code)",
            "1 aircraft (Cessna 172 defaults)",
            "CheckWX integration",
            "NOTAM service",
            "Glass Cockpit dashboard",
        ],
        "default_settings": {
            "unit_preference": "aviation",
            "language": "en",
        },
        "recommended_apis": ["checkwx"],
        "aircraft_template": "cessna_172",
    },
    
    "us_sport_pilot": {
        "name": "US Sport Pilot",
        "description": "Light Sport Aircraft setup",
        "estimated_time": "12 minutes",
        "includes": [
            "1 airfield (US ICAO code)",
            "1 LSA aircraft",
            "CheckWX integration",
            "OpenWeatherMap",
            "Glass Cockpit dashboard",
        ],
        "default_settings": {
            "unit_preference": "aviation",
            "language": "en",
        },
        "recommended_apis": ["checkwx", "openweathermap"],
        "aircraft_template": None,  # Custom LSA
    },
    
    "glider_club": {
        "name": "Glider Club",
        "description": "Gliding operations setup",
        "estimated_time": "8 minutes",
        "includes": [
            "1 airfield",
            "1 glider (ASW 20 defaults)",
            "Thermal forecasting sensors",
            "CheckWX integration",
            "Glass Cockpit dashboard",
        ],
        "default_settings": {
            "unit_preference": "si",  # Gliders often use metric
            "language": "en",
        },
        "recommended_apis": ["checkwx", "openweathermap"],
        "aircraft_template": "glider_generic",
    },
    
    "flight_school": {
        "name": "Flight School",
        "description": "Multi-aircraft training environment",
        "estimated_time": "20 minutes",
        "includes": [
            "2 airfields",
            "3 aircraft (training fleet)",
            "CheckWX integration",
            "Fuel cost tracking",
            "Multi-aircraft dashboard",
        ],
        "default_settings": {
            "unit_preference": "aviation",
            "language": "en",
        },
        "recommended_apis": ["checkwx"],
        "aircraft_templates": ["cessna_172", "piper_pa28", "cessna_172"],
        "multi_aircraft": True,
    },
}


def get_template(template_id: str) -> Dict:
    """Get quick start template by ID.
    
    Args:
        template_id: Template identifier
    
    Returns:
        Template configuration dict
    
    Raises:
        KeyError: If template not found
    """
    return QUICK_START_TEMPLATES[template_id]


def list_templates() -> List[Dict]:
    """Get list of all available templates.
    
    Returns:
        List of template dicts with metadata
    """
    return [
        {
            "id": template_id,
            **template_data
        }
        for template_id, template_data in QUICK_START_TEMPLATES.items()
    ]


def apply_template(template_id: str, wizard_state) -> None:
    """Apply quick start template to wizard state.
    
    Args:
        template_id: Template to apply
        wizard_state: SetupWizardState instance to populate
    """
    template = get_template(template_id)
    
    # Apply default settings
    wizard_state.general_settings.update(template["default_settings"])
    
    # Mark APIs as recommended
    for api in template.get("recommended_apis", []):
        wizard_state.api_configs[api] = {"recommended": True}
    
    # Set aircraft template if specified
    if "aircraft_template" in template and template["aircraft_template"]:
        wizard_state.aircraft_template = template["aircraft_template"]
```

---

## Phase 6: Testing & Polish
**Timeline**: Days 9-10  
**Estimated Effort**: 16 hours

### Task 6.1: Setup Wizard Tests
**File**: `tests/test_setup_wizard.py`

```python
"""Tests for setup wizard flow."""
import pytest
from unittest.mock import MagicMock, patch
from custom_components.hangar_assistant.config_flow import (
    HangarAssistantSetupWizardFlow,
    SetupWizardState,
)
from custom_components.hangar_assistant.validation import (
    validate_icao,
    validate_registration,
    validate_mtow,
)


def test_should_show_welcome_first_time():
    """Test welcome screen shown for first-time users."""
    mock_entry = MagicMock()
    mock_entry.data = {"airfields": [], "aircraft": []}
    
    from custom_components.hangar_assistant import should_show_setup_wizard
    assert should_show_setup_wizard(mock_entry) is True


def test_should_skip_welcome_existing_setup():
    """Test welcome skipped for existing setups."""
    mock_entry = MagicMock()
    mock_entry.data = {
        "settings": {"setup_completed": True},
        "airfields": [{"name": "Test"}],
        "aircraft": [],
    }
    
    from custom_components.hangar_assistant import should_show_setup_wizard
    assert should_show_setup_wizard(mock_entry) is False


def test_wizard_state_progress():
    """Test wizard progress tracking."""
    state = SetupWizardState()
    assert state.get_progress_percentage() == 0
    
    state.mark_step_complete("general_settings")
    assert state.get_progress_percentage() == int(1/7 * 100)
    
    state.mark_step_complete("add_airfield")
    state.mark_step_complete("add_aircraft")
    assert state.get_progress_percentage() == int(3/7 * 100)


def test_validate_icao_valid():
    """Test ICAO validation with valid codes."""
    valid, error = validate_icao("EGHP")
    assert valid is True
    assert error is None
    
    valid, error = validate_icao("KJFK")
    assert valid is True
    assert error is None


def test_validate_icao_invalid():
    """Test ICAO validation with invalid codes."""
    # Too short
    valid, error = validate_icao("EGH")
    assert valid is False
    assert "4 characters" in error
    
    # Contains number
    valid, error = validate_icao("EGH1")
    assert valid is False
    assert "only letters" in error
    
    # Lowercase
    valid, error = validate_icao("eghp")
    assert valid is False
    assert "uppercase" in error


def test_validate_registration_uk():
    """Test UK registration validation."""
    valid, error = validate_registration("G-ABCD")
    assert valid is True
    assert error is None


def test_validate_registration_us():
    """Test US registration validation."""
    valid, error = validate_registration("N12345")
    assert valid is True
    assert error is None


def test_validate_mtow_kg():
    """Test MTOW validation in kilograms."""
    valid, error = validate_mtow(1157, "kg")
    assert valid is True
    assert error is None
    
    # Too low
    valid, error = validate_mtow(100, "kg")
    assert valid is False
    assert "unusual" in error


@pytest.mark.asyncio
async def test_checkwx_auto_populate(mock_hass):
    """Test CheckWX auto-population of airfield data."""
    flow = HangarAssistantSetupWizardFlow()
    flow.hass = mock_hass
    
    # Mock CheckWX client
    with patch("custom_components.hangar_assistant.config_flow.CheckWXClient") as mock_client:
        mock_client.return_value.get_station_info.return_value = {
            "name": "Popham Airfield",
            "latitude": 51.2017,
            "longitude": -1.2351,
            "elevation_ft": 550,
        }
        
        station_data = await flow._fetch_checkwx_station("EGHP")
        
        assert station_data is not None
        assert station_data["name"] == "Popham Airfield"
        assert station_data["icao"] == "EGHP"


@pytest.mark.asyncio
async def test_aircraft_template_load(mock_hass):
    """Test aircraft template loading."""
    from custom_components.hangar_assistant.const import AIRCRAFT_TEMPLATES
    
    template = AIRCRAFT_TEMPLATES["cessna_172"]
    assert template["mtow_kg"] == 1157
    assert template["fuel_type"] == "AVGAS"
    assert template["fuel_burn_lh"] == 35


@pytest.mark.asyncio
async def test_dashboard_installation_automatic(mock_hass):
    """Test automatic dashboard installation."""
    from custom_components.hangar_assistant.services import async_install_dashboard
    
    mock_entry = MagicMock()
    mock_entry.data = {
        "airfields": [{"name": "Popham", "icao": "EGHP"}],
        "aircraft": [{"reg": "G-ABCD", "type": "Cessna 172"}],
    }
    
    with patch("custom_components.hangar_assistant.services._load_dashboard_template_with_cache") as mock_load:
        mock_load.return_value = "views:\n  - title: Test\n    cards: []"
        
        result = await async_install_dashboard(mock_hass, mock_entry, method="automatic")
        
        assert result["success"] is True
        assert result["url"] == "/hangar-glass-cockpit"
```

### Task 6.2: End-to-End Wizard Test
**File**: `tests/test_wizard_e2e.py`

```python
"""End-to-end tests for complete wizard flow."""
import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_complete_wizard_flow_minimal(mock_hass):
    """Test complete wizard flow with minimal config (no APIs)."""
    from custom_components.hangar_assistant.config_flow import HangarAssistantSetupWizardFlow
    
    flow = HangarAssistantSetupWizardFlow()
    flow.hass = mock_hass
    
    # Step 1: Welcome
    result = await flow.async_step_welcome({"start_wizard": True})
    assert result["type"] == "form"
    assert result["step_id"] == "general_settings"
    
    # Step 2: General settings
    result = await flow.async_step_general_settings({
        "unit_preference": "aviation",
        "language": "en",
    })
    assert result["step_id"] == "api_integrations"
    
    # Step 3: Skip APIs
    result = await flow.async_step_api_integrations({"skip": True})
    assert result["step_id"] == "add_airfield"
    
    # Step 4: Add airfield manually
    result = await flow.async_step_add_airfield({
        "icao": "EGHP",
        "auto_populate": False,
    })
    assert result["step_id"] == "airfield_manual"
    
    # Continue through remaining steps...


@pytest.mark.asyncio
async def test_complete_wizard_flow_with_checkwx(mock_hass):
    """Test complete wizard flow with CheckWX integration."""
    from custom_components.hangar_assistant.config_flow import HangarAssistantSetupWizardFlow
    
    flow = HangarAssistantSetupWizardFlow()
    flow.hass = mock_hass
    
    # Mock CheckWX client responses
    with patch("custom_components.hangar_assistant.utils.checkwx_client.CheckWXClient") as mock_client:
        mock_client.return_value.get_metar = AsyncMock(return_value={"raw_text": "METAR KJFK..."})
        mock_client.return_value.get_station_info = AsyncMock(return_value={
            "name": "John F Kennedy Intl",
            "latitude": 40.6413,
            "longitude": -73.7781,
            "elevation_ft": 13,
        })
        
        # Go through full flow with CheckWX
        # ... (implement full flow)


@pytest.mark.asyncio
async def test_wizard_error_recovery(mock_hass):
    """Test wizard error handling and recovery."""
    from custom_components.hangar_assistant.config_flow import HangarAssistantSetupWizardFlow
    
    flow = HangarAssistantSetupWizardFlow()
    flow.hass = mock_hass
    
    # Invalid ICAO code
    result = await flow.async_step_add_airfield({
        "icao": "INVALID123",
        "auto_populate": False,
    })
    assert result["errors"]["icao"] == "invalid_icao"
    
    # Retry with valid ICAO
    result = await flow.async_step_add_airfield({
        "icao": "EGHP",
        "auto_populate": False,
    })
    assert "errors" not in result or not result["errors"]
```

### Task 6.3: UI String Localization
**File**: `custom_components/hangar_assistant/translations/en.json`

Add wizard strings:

```json
{
  "config": {
    "step": {
      "welcome": {
        "title": "Welcome to Hangar Assistant!",
        "description": "The complete aviation safety and operations integration for Home Assistant.\n\nSetup Time: 10-15 minutes",
        "data": {
          "start_wizard": "Start Setup Wizard"
        }
      },
      "general_settings": {
        "title": "General Settings (Step 1 of 7)",
        "description": "Configure basic preferences for your Hangar Assistant setup.",
        "data": {
          "setup_name": "Setup Name (Optional)",
          "unit_preference": "Unit Preference",
          "language": "Language"
        }
      },
      "api_integrations": {
        "title": "External Integrations (Step 2 of 7)",
        "description": "⚡ Recommended: Setup APIs now to enable auto-population!",
        "data": {
          "setup_checkwx": "Setup CheckWX (Free)",
          "setup_owm": "Setup OpenWeatherMap (Paid)",
          "skip": "Skip for Now"
        }
      },
      "checkwx_setup": {
        "title": "Configure CheckWX API",
        "description": "Get your free API key at: https://www.checkwxapi.com/signup",
        "data": {
          "api_key": "API Key",
          "metar_enabled": "Enable METAR (Current Weather)",
          "taf_enabled": "Enable TAF (Forecasts)",
          "station_enabled": "Auto-populate Station Data"
        }
      },
      "add_airfield": {
        "title": "Add Your First Airfield (Step 3 of 7)",
        "description": "📍 Where is your home base?",
        "data": {
          "icao": "ICAO Code (e.g., EGHP, KJFK)",
          "auto_populate": "Auto-populate from CheckWX"
        }
      },
      "airfield_confirm": {
        "title": "Confirm Airfield Data",
        "description": "✅ Station data retrieved successfully!",
        "data": {
          "use_data": "Use This Data"
        }
      },
      "add_aircraft": {
        "title": "Add Your First Aircraft (Step 5 of 7)",
        "description": "✈️ What aircraft do you fly?",
        "data": {
          "registration": "Registration (Tail Number)",
          "aircraft_type": "Aircraft Type",
          "load_template": "Load Default Specs"
        }
      },
      "install_dashboard": {
        "title": "Install Dashboard (Step 7 of 7)",
        "description": "📊 Add Glass Cockpit dashboard to your Home Assistant",
        "data": {
          "installation_method": "Installation Method",
          "skip": "Skip for Now"
        }
      },
      "complete": {
        "title": "🎉 Setup Complete!",
        "description": "Your Hangar Assistant is ready to fly!"
      }
    },
    "error": {
      "api_key_required": "API key is required",
      "connection_failed": "Connection test failed. Please check your API key.",
      "invalid_icao": "Invalid ICAO code. Must be 4 uppercase letters.",
      "invalid_registration": "Invalid registration format. Examples: G-ABCD, N12345",
      "icao_not_found": "ICAO code not found in CheckWX database",
      "auto_populate_failed": "Auto-population failed. Please enter data manually.",
      "installation_failed": "Dashboard installation failed. Try manual installation."
    }
  }
}
```

---

## Code Implementation Details

### File Structure Changes

```
custom_components/hangar_assistant/
├── __init__.py                    # Add should_show_setup_wizard()
├── config_flow.py                 # Add SetupWizardFlow class (major additions)
├── const.py                       # Add wizard constants, templates
├── validation.py                  # NEW: Validation helpers
├── templates.py                   # NEW: Quick start templates
├── services.py                    # Add async_install_dashboard()
└── translations/
    ├── en.json                    # Add wizard strings
    ├── de.json                    # Add wizard strings
    ├── es.json                    # Add wizard strings
    └── fr.json                    # Add wizard strings

tests/
├── test_setup_wizard.py           # NEW: Wizard unit tests
├── test_wizard_e2e.py             # NEW: End-to-end wizard tests
└── test_validation.py             # NEW: Validation function tests
```

### Integration Points

**1. Entry Point** (`__init__.py`):
```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hangar Assistant from a config entry."""
    
    # Check if wizard should be shown on first load
    if should_show_setup_wizard(entry):
        # Trigger config flow re-entry
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "reauth"},
                data=entry.data
            )
        )
    
    # Continue with normal setup...
```

**2. Config Entry Update** (after wizard completion):
```python
async def async_step_complete(self, user_input=None):
    """Final step - create config entry."""
    # Compile all wizard data
    config_data = {
        "settings": {
            **self.wizard_state.general_settings,
            "setup_completed": True,
            "setup_version": SETUP_WIZARD_VERSION,
            "setup_date": datetime.now().isoformat(),
        },
        "integrations": self.wizard_state.api_configs,
        "airfields": [self.wizard_state.airfield_data] if self.wizard_state.airfield_data else [],
        "aircraft": [self.wizard_state.aircraft_data] if self.wizard_state.aircraft_data else [],
        "hangars": [self.wizard_state.hangar_data] if self.wizard_state.hangar_data else [],
    }
    
    return self.async_create_entry(
        title="Hangar Assistant",
        data=config_data
    )
```

---

## Testing Strategy

### Unit Tests
- ✅ Validation functions (ICAO, registration, MTOW, API keys)
- ✅ Wizard state management
- ✅ Template loading and substitution
- ✅ Progress calculation

### Integration Tests
- ✅ CheckWX API mocking
- ✅ Dashboard installation (mocked Lovelace service)
- ✅ Config entry creation
- ✅ Entity creation after wizard

### End-to-End Tests
- ✅ Complete wizard flow (minimal config)
- ✅ Complete wizard flow (with CheckWX)
- ✅ Complete wizard flow (with templates)
- ✅ Error recovery and validation

### Manual Testing Checklist
```
□ Fresh install → Wizard appears
□ Existing install → Wizard skipped
□ CheckWX API key validation works
□ CheckWX auto-populate populates all fields
□ Aircraft template loads correct specs
□ Dashboard installs successfully (automatic)
□ Dashboard YAML generates correctly (manual)
□ All validation errors display correctly
□ Can skip optional steps
□ Can go back to previous steps
□ Progress bar updates correctly
□ Success screen shows correct summary
□ Entities created match config
□ Dashboard displays live data
```

---

## Rollout Plan

### Phase 1: Internal Testing (Week 1)
- Implement foundation and core wizard
- Unit tests + integration tests
- Manual testing on dev environment

### Phase 2: Beta Release (Week 2)
- Feature flag: `ENABLE_SETUP_WIZARD = True` (default: False)
- Invite beta testers via GitHub
- Collect feedback on UX flow

### Phase 3: Public Release (Week 3)
- Enable wizard by default for new installs
- Document manual config as alternative
- Update README with new setup flow

### Phase 4: Iteration (Ongoing)
- Monitor setup completion rates
- Gather user feedback
- Iterate on pain points
- Add more aircraft templates

---

## Success Metrics & Monitoring

### Telemetry (Privacy-Preserving)
```python
# Track wizard usage (no personal data)
wizard_metrics = {
    "wizard_version": SETUP_WIZARD_VERSION,
    "completed": bool,
    "steps_completed": int,
    "apis_configured": List[str],  # ["checkwx", "owm"]
    "dashboard_installed": bool,
    "template_used": Optional[str],
    "time_to_complete_seconds": int,
}

# Submit anonymized metrics (opt-in)
if user_consents_to_analytics:
    await async_submit_metrics(wizard_metrics)
```

### KPIs to Track
- **Setup Completion Rate**: Target 80%
- **Time to Value**: Target <15 minutes
- **API Adoption Rate**: Target 50% CheckWX
- **Dashboard Installation**: Target 70%
- **Support Requests**: Target <5% setup-related

---

## Backward Compatibility

**CRITICAL**: All changes must maintain 100% backward compatibility:

✅ **Existing installations** → Wizard never shown (setup_completed flag present)  
✅ **Manual config flow** → Always available as alternative  
✅ **Existing sensors** → Continue working without changes  
✅ **Config structure** → No breaking changes, only additions  
✅ **Dashboard** → Existing dashboards unaffected  

---

## Conclusion

This implementation plan provides a complete roadmap for transforming Hangar Assistant's onboarding experience. By following this phased approach, we'll deliver:

1. **Guided setup wizard** that gets users from install to dashboard in <15 minutes
2. **API auto-population** that eliminates tedious manual data entry
3. **Aircraft templates** that provide sensible defaults
4. **Real-time validation** that prevents configuration errors
5. **Automated dashboard installation** that delivers immediate value

**Estimated Total Effort**: 7-10 days (56-80 hours)

**Target Release**: v2601.3.0

**Expected Impact**:
- 3x increase in setup completion rate
- 2x reduction in time-to-value
- 50% reduction in setup-related support requests
- Significant improvement in user satisfaction and adoption

This UI/UX transformation will be a **game-changer** for Hangar Assistant's accessibility and user growth! 🚀✈️

---

**Document End**
