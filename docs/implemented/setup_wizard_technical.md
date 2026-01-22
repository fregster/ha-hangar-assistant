# Setup Wizard - Technical Documentation

**Feature**: Guided First-Time Configuration System  
**Version**: 1.0 (v2601.3.0)  
**Implementation**: Config Flow with State Machine Pattern

---

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [State Management](#state-management)
- [Flow Sequence](#flow-sequence)
- [Data Model](#data-model)
- [Background Task Management](#background-task-management)
- [Validation & Testing](#validation--testing)
- [Integration Points](#integration-points)
- [Performance Considerations](#performance-considerations)

---

## Architecture Overview

The Setup Wizard is implemented as a multi-step config flow integrated into Home Assistant's native configuration framework. It uses a state machine pattern to manage wizard progression and data collection across 7 sequential steps.

**Design Philosophy:**
- **Stateful**: Tracks progress via `SetupWizardState` dataclass
- **Resumable**: Users can exit and resume without data loss
- **Non-blocking**: Dashboard installation runs as background task
- **Fail-safe**: Validation prevents invalid data from being saved
- **Backward compatible**: Existing users unaffected, manual config remains available

**File Structure:**
```
custom_components/hangar_assistant/
├── config_flow.py           # SetupWizardState + async_step_* methods
├── templates.py             # Aircraft type templates
├── strings.json            # English translation keys
└── translations/           # Localized strings (en/de/es/fr)
```

**Related Tests:**
```
tests/
├── test_setup_wizard.py    # Unit tests for wizard state and flows
└── test_wizard_flow.py     # Integration tests for complete wizard journey
```

---

## State Management

### SetupWizardState Dataclass

The wizard state is managed by a dataclass that persists throughout the configuration process:

```python
@dataclass
class SetupWizardState:
    """Track setup wizard progress and user choices.
    
    Attributes:
        enabled: Whether wizard mode is active
        completed_steps: Set of step names completed (for progress tracking)
        last_airfield: Most recent airfield name (for resumption context)
        last_aircraft: Most recent aircraft reg (for resumption context)
    """
    enabled: bool = False
    completed_steps: set = field(default_factory=set)
    last_airfield: Optional[str] = None
    last_aircraft: Optional[str] = None
```

**Key Design Decisions:**
- **Set for completed_steps**: O(1) lookup, prevents duplicates, unordered (step order enforced by flow logic)
- **Optional last_* fields**: Enable context-aware resumption messages ("You were configuring G-ABCD...")
- **No serialization logic**: State lives in config flow instance memory, not persisted to disk

**State Lifecycle:**
1. **Initialization**: Created in `async_step_user()` if `entry.data` is empty (fresh install)
2. **Progress tracking**: Each `async_step_*` method adds step name to `completed_steps`
3. **Resumption**: If user exits wizard, `last_airfield`/`last_aircraft` show what was in progress
4. **Completion**: State discarded after `async_step_completion()` creates config entry

### First Load Detection

The wizard automatically appears for new installations:

```python
async def async_step_user(self, user_input=None):
    """Entry point for config flow.
    
    Logic:
        - If entry.data is empty (fresh install) → Show wizard welcome
        - If entry.data exists (existing install) → Show manual config menu
    """
    existing_data = self._entry_data()
    
    if not existing_data.get("airfields") and not existing_data.get("aircraft"):
        # Fresh install - launch wizard
        self._wizard_state = SetupWizardState(enabled=True)
        return await self.async_step_welcome()
    else:
        # Existing install - show manual config
        return await self.async_show_menu(...)
```

**Edge Cases Handled:**
- Partial config (airfield but no aircraft) → Manual config menu
- Empty lists (`airfields: []`) → Treated as fresh install
- Config corruption → Graceful fallback to manual config

---

## Flow Sequence

### Complete Step Flow

```
async_step_user()
    ├─ Fresh install? → async_step_welcome() ────────┐
    └─ Existing? → async_show_menu()                │
                                                     │
┌────────────────────────────────────────────────────┘
│
├─ Step 1: async_step_welcome()
│    ├─ "Use Setup Wizard" → async_step_general_settings()
│    └─ "Skip Wizard" → async_show_menu() [manual config]
│
├─ Step 2: async_step_general_settings()
│    ├─ Collect: language, unit_preference, cache_minutes
│    ├─ Save to entry.data["settings"]
│    └─ → async_step_airfield_setup()
│
├─ Step 3: async_step_airfield_setup()
│    ├─ Collect: name, icao, lat, lon, elevation, timezone
│    ├─ Validate: ICAO format (4 uppercase letters)
│    ├─ Save to entry.data["airfields"].append({...})
│    ├─ Update: wizard_state.last_airfield = name
│    └─ → async_step_aircraft_setup()
│
├─ Step 4: async_step_aircraft_setup()
│    ├─ Collect: reg, type, mtow, use_template
│    ├─ Template? → Apply from templates.py (AIRCRAFT_TEMPLATES)
│    ├─ Validate: Registration format (alphanumeric + hyphen)
│    ├─ Save to entry.data["aircraft"].append({...})
│    ├─ Update: wizard_state.last_aircraft = reg
│    └─ → async_step_checkwx_setup()
│
├─ Step 5: async_step_checkwx_setup()
│    ├─ Collect: api_key (optional)
│    ├─ Test: Connection validation if key provided
│    ├─ Save to entry.data["integrations"]["checkwx"]
│    ├─ "Skip for now" allowed
│    └─ → async_step_notam_setup()
│
├─ Step 6: async_step_notam_setup()
│    ├─ Collect: enable_notams (bool), update_time
│    ├─ Save to entry.data["integrations"]["notams"]
│    ├─ Default: Enabled (free service)
│    └─ → async_step_completion()
│
└─ Step 7: async_step_completion()
     ├─ Summary: Show what was configured
     ├─ Dashboard: Spawn background installation task
     ├─ Create Config Entry: await self.async_create_entry(...)
     └─ Return: Integration setup complete
```

### Step Implementation Pattern

Each step follows a consistent pattern:

```python
async def async_step_<step_name>(self, user_input=None):
    """Step N: <Description>.
    
    Collects: <data collected>
    Validates: <validation rules>
    Saves to: <config entry location>
    Next: <next step name>
    """
    # Mark step as started
    if self._wizard_state:
        self._wizard_state.completed_steps.add("<step_name>")
    
    # Form submission (user_input provided)
    if user_input is not None:
        # 1. Validate input
        errors = self._validate_<step_name>(user_input)
        if errors:
            return self.async_show_form(..., errors=errors)
        
        # 2. Save to config entry
        self._update_entry_data("<key>", user_input["field"])
        
        # 3. Update wizard state (if applicable)
        if self._wizard_state:
            self._wizard_state.last_<entity> = user_input["name"]
        
        # 4. Proceed to next step
        return await self.async_step_<next_step>()
    
    # Form display (initial load)
    return self.async_show_form(
        step_id="<step_name>",
        data_schema=vol.Schema({...}),
        description_placeholders={...}
    )
```

**Key Implementation Details:**
- **Early validation**: Input checked before state changes
- **Atomic updates**: Data saved immediately (no "commit" step)
- **Progressive enhancement**: Each step builds on previous data
- **Error recovery**: Validation errors redisplay form with error message

---

## Data Model

### Config Entry Structure

The wizard populates `entry.data` with this structure:

```python
entry.data = {
    "settings": {
        "language": str,              # "en", "de", "es", "fr"
        "unit_preference": str,       # "aviation" or "si"
        "cache_minutes": int,         # 15-60 minutes
    },
    
    "airfields": [
        {
            "name": str,              # "Popham Airfield"
            "icao": str,              # "EGHP" (validated: 4 uppercase letters)
            "latitude": float,        # 51.186111
            "longitude": float,       # -1.232778
            "elevation": float,       # 548 (feet or meters based on unit_preference)
            "timezone": str,          # "Europe/London"
        },
        # ... more airfields
    ],
    
    "aircraft": [
        {
            "reg": str,               # "G-ABCD" (validated: alphanumeric + hyphen)
            "type": str,              # "Cessna 172"
            "mtow": float,            # 2450 (kg or lbs based on unit_preference)
            
            # Optional: Applied from template if use_template=True
            "performance": {
                "vr": int,            # Rotation speed (kts)
                "vx": int,            # Best angle of climb (kts)
                "vy": int,            # Best rate of climb (kts)
                "vs0": int,           # Stall speed landing config (kts)
                "vs1": int,           # Stall speed clean config (kts)
                "approach_speed": int, # Final approach speed (kts)
            },
            
            "fuel": {
                "type": str,          # "AVGAS", "JET_A", etc.
                "burn_rate": float,   # Fuel burn per hour
                "volume_unit": str,   # "liters", "gallons_us"
                "tank_capacity": float, # Total usable fuel
            },
            
            "weights": {
                "basic_empty_weight": float,
                "max_payload": float,
            },
        },
        # ... more aircraft
    ],
    
    "integrations": {
        "checkwx": {
            "enabled": bool,
            "api_key": str,           # Password-masked in UI
        },
        
        "notams": {
            "enabled": bool,          # Default: True (free service)
            "update_time": str,       # "02:00" (HH:MM format)
        },
        
        "openweathermap": {
            # Configured via options flow, not wizard (v1.0)
        },
    },
}
```

**Design Rationale:**
- **Flat airfield structure**: No nested hangars in wizard (v1.0 simplification)
- **Optional performance data**: Applied from templates, editable later
- **Immediate availability**: Sensors created as soon as config entry saved
- **Extensible**: New fields can be added without breaking existing configs

---

## Background Task Management

### Dashboard Installation

Dashboard installation runs as a background task to avoid blocking the wizard completion:

```python
async def async_step_completion(self, user_input=None):
    """Final step: Show summary and install dashboard.
    
    Dashboard installation logic:
        1. Create config entry (async_create_entry)
        2. Spawn background task (hass.async_create_task)
        3. 2-second delay to ensure entry initialization completes
        4. Install dashboard YAML to lovelace/
        5. Show persistent notification on success/failure
    """
    # Create config entry first
    result = self.async_create_entry(
        title="Hangar Assistant",
        data=self._entry_data()
    )
    
    # Spawn dashboard installation task
    async def _install_dashboard_delayed():
        await asyncio.sleep(2)  # Wait for entry initialization
        
        try:
            dashboard_yaml = load_dashboard_template()
            path = self.hass.config.path("lovelace/hangar_cockpit.yaml")
            
            await self.hass.async_add_executor_job(
                _write_dashboard_file, path, dashboard_yaml
            )
            
            # Success notification
            await async_create_notification(
                self.hass,
                title="Dashboard Installed",
                message="Hangar Glass Cockpit dashboard is now available."
            )
        except Exception as e:
            _LOGGER.error("Dashboard installation failed: %s", e)
            # Provide manual instructions in notification
    
    self.hass.async_create_task(_install_dashboard_delayed())
    
    return result
```

**Key Design Decisions:**
- **2-second delay**: Ensures `entry` object fully initialized before dashboard uses it
- **Fire-and-forget**: Dashboard failure doesn't block wizard completion
- **User notification**: Success/failure communicated via persistent notification
- **Manual fallback**: If automatic install fails, wizard shows manual YAML + instructions

**Alternative Approach (Manual Only):**
If automatic dashboard installation is disabled (config option or permission issue):
```python
# Show manual instructions instead
return self.async_show_form(
    step_id="manual_dashboard",
    description_placeholders={
        "yaml_content": dashboard_yaml,
        "install_path": "config/lovelace/hangar_cockpit.yaml",
    }
)
```

---

## Validation & Testing

### Real-Time Input Validation

Each step validates user input before proceeding:

```python
def _validate_airfield(self, user_input: dict) -> dict:
    """Validate airfield data.
    
    Checks:
        - ICAO code: Exactly 4 uppercase letters (^[A-Z]{4}$)
        - Coordinates: Valid lat/lon ranges (-90 to 90, -180 to 180)
        - Elevation: Numeric and reasonable (0-30000 feet)
        - Timezone: Valid IANA timezone string
    
    Returns:
        dict: Error dictionary {field: error_key} or empty dict if valid
    """
    errors = {}
    
    icao = user_input.get("icao", "").strip().upper()
    if not re.match(r"^[A-Z]{4}$", icao):
        errors["icao"] = "invalid_icao_format"  # Lookup in strings.json
    
    # Latitude validation
    lat = user_input.get("latitude")
    if not -90 <= lat <= 90:
        errors["latitude"] = "invalid_latitude"
    
    # ... more validation
    
    return errors
```

**Validation Philosophy:**
- **Fail-fast**: Invalid data caught before state changes
- **User-friendly errors**: Error keys map to localized messages in `strings.json`
- **Real-time feedback**: Errors shown immediately on form (no page reload)
- **Helpful suggestions**: Error messages include examples (e.g., "ICAO codes like EGHP, KJFK")

### API Connection Testing

CheckWX API keys are validated in real-time:

```python
async def _test_checkwx_connection(self, api_key: str) -> bool:
    """Test CheckWX API key validity.
    
    Makes a lightweight API call to verify:
        - API key is valid
        - API key has remaining quota
        - CheckWX service is reachable
    
    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        client = CheckWXClient(api_key, self.hass)
        
        # Test with lightweight station info request
        result = await client.get_station_info("KJFK")
        
        return result is not None
    except Exception as e:
        _LOGGER.warning("CheckWX connection test failed: %s", e)
        return False
```

**User Experience:**
- "Testing connection..." indicator appears during validation
- Success: "✓ API key validated successfully"
- Failure: "✗ Unable to connect. Check your API key."
- Timeout: 10-second maximum wait, then shows error

---

## Integration Points

### Config Flow Registration

The wizard integrates with Home Assistant's config flow framework:

```python
# In config_flow.py
@config_entries.HANDLERS.register(DOMAIN)
class HangarAssistantConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Hangar Assistant."""
    
    VERSION = 1  # Config entry version (for migrations)
    
    def __init__(self):
        """Initialize config flow."""
        self._wizard_state: Optional[SetupWizardState] = None
    
    async def async_step_user(self, user_input=None):
        """Handle first step (auto-wizard or manual)."""
        # ... (see Flow Sequence section)
```

**Registration Mechanism:**
- `@config_entries.HANDLERS.register(DOMAIN)` decorator
- `VERSION` field for config entry migration tracking
- `domain=DOMAIN` links flow to integration manifest

### Entity Creation Trigger

Completing the wizard triggers entity creation:

```python
# In __init__.py
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hangar Assistant from a config entry.
    
    Called immediately after wizard completion (async_create_entry).
    
    Actions:
        1. Load entry.data (created by wizard)
        2. Create sensors for each airfield (MetarSensor, DensityAltSensor, etc.)
        3. Create sensors for each aircraft (FuelEnduranceSensor, WeightSensor, etc.)
        4. Register services (manual_cleanup, rebuild_dashboard, etc.)
        5. Schedule briefing updates (if configured)
    """
    airfields = entry.data.get("airfields", [])
    aircraft = entry.data.get("aircraft", [])
    
    # Sensors created in sensor.py:async_setup_entry()
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "binary_sensor", "select"])
    
    return True
```

**Entity Naming Convention:**
- Airfield sensors: `sensor.{airfield_slug}_density_altitude`
- Aircraft sensors: `sensor.{aircraft_reg_slug}_fuel_endurance`
- Slugification: Lowercase, underscores, special chars removed

---

## Performance Considerations

### Template Caching

Aircraft templates are cached in memory to avoid repeated disk I/O:

```python
# In templates.py
AIRCRAFT_TEMPLATES = {
    "cessna_172": {
        "type": "Cessna 172",
        "performance": {...},
        "fuel": {...},
        # ... preloaded at module import
    },
    # ... 6 more templates
}

def get_aircraft_template(template_name: str) -> dict:
    """Get aircraft template (O(1) lookup from preloaded dict)."""
    return AIRCRAFT_TEMPLATES.get(template_name, {}).copy()
```

**Performance Impact:**
- Cold start: ~5ms to load all templates
- Template application: <1ms (dict copy operation)
- Memory: ~20KB for all 7 templates

### Wizard State Memory Management

Wizard state is instance-scoped and garbage-collected after completion:

```python
# State lifecycle
self._wizard_state = SetupWizardState(enabled=True)  # Created
# ... user progresses through steps
await self.async_create_entry(...)  # Config entry created
# ... wizard_state goes out of scope, GC collects
```

**Memory Footprint:**
- SetupWizardState: ~200 bytes (bool + set + 2 strings)
- Form data: Temporary (discarded after each step)
- Total wizard memory: <1KB during active session

---

## Future Enhancements

### Planned Features (v2601.4.0+)

1. **Enhanced Templates**
   - Expand from 7 to 40+ aircraft types
   - Community-contributed templates
   - Template marketplace

2. **Quick-Start Scenarios**
   - "Student Pilot" → Pre-configure typical training aircraft
   - "Private Pilot" → Multi-aircraft fleet setup
   - "Glider Pilot" → Disable fuel sensors, enable soaring metrics

3. **Validation Improvements**
   - Live ICAO code lookup (verify airfield exists)
   - Coordinate validation via reverse geocoding
   - Duplicate detection (warn if airfield already configured)

4. **Dashboard Preview**
   - Show dashboard mockup before installation
   - Interactive preview with sample data
   - Customization options before install

5. **Resumption UI**
   - "Resume setup" button if wizard exited
   - Show progress bar (3 of 7 steps completed)
   - Quick jump to incomplete steps

---

## Related Documentation

- **User Guide**: [docs/features/setup_wizard.md](../features/setup_wizard.md) - Step-by-step walkthrough for pilots
- **Planning Document**: [docs/implemented/setup_wizard_plan.md](setup_wizard_plan.md) - Original design rationale
- **Config Flow API**: [Home Assistant Config Flow Docs](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/)
- **Testing**: [tests/test_setup_wizard.py](../../tests/test_setup_wizard.py) - Unit tests

---

**Last Updated**: 22 January 2026  
**Implementation Version**: v2601.3.0  
**Author**: Hangar Assistant Development Team
