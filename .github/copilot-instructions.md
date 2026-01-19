# AI Coding Agent Instructions for Hangar Assistant

## Project Overview
**Hangar Assistant** is a Home Assistant custom integration that provides aviation decision support for GA/Glider pilots. It calculates real-time metrics (carburetor icing risk, density altitude, crosswind components, cloud base estimation) from local weather sensor data, transforming raw conditions into actionable pilot briefing materials.

## Architecture & Components

### Core Structure
- **Integration Domain**: `hangar_assistant` in `custom_components/`
- **Home Assistant Platforms**: Sensors (`sensor.py`) and binary sensors (`binary_sensor.py`)
- **Multi-config Entry Pattern**: Uses config flow (`config_flow.py`) to support 4 independent entry types:
  1. **Airfield**: Weather sensors + runway definitions (generates computation sensors)
  2. **Aircraft**: Performance baseline data (registration, weight, takeoff distances)
  3. **Pilot**: License/medical tracking (informational entries)
  4. **Briefing**: Email recipient + AI agent entity reference for report generation

### Data Flow
1. **Airfield Config** → Reads live sensor entities (temp, dew point, wind, wind direction)
2. **Sensor Calculation** → Applies aviation formulas (ISA lapse rate, FAA icing envelopes, crosswind math)
3. **Output Sensors** → Exposes results as Home Assistant sensor entities
4. **PDF Generation** → `utils/pdf_generator.py` uses fpdf2 to create CAP 1590B declarations

## Key Conventions

### Config Entry Pattern
- Each entry type has dedicated `async_step_*` method in config flow
- Data stored in `entry.data` dict with `"type"` key distinguishing entry purpose
- Setup retrieves all entries via `hass.config_entries.async_entries(DOMAIN)`

### Sensor Implementation
- Derive from `SensorEntity` (imported from `homeassistant.components.sensor`)
- Filter config entries by type in `async_setup_entry()` before creating entities
- Access Home Assistant state machine via `self.hass.states.get(entity_id)` for sensor reads
- Name pattern: `f"{config['name']} {metric_name}"` (e.g., "The Airfield Carb Risk")

### File Organization
- `const.py`: Domain, platform list (keep minimal)
- `__init__.py`: Setup hooks + service registration (e.g., `manual_cleanup` service)
- `config_flow.py`: Schema definitions using `voluptuous`, step routing via menu
- `sensor.py`: All sensor entities (even if expanding to many metrics)
- `utils/`: Specialized generators (PDF, reports) with external dependencies

## Integration Dependencies & External Patterns

### Required Packages
- `fpdf2==2.7.8`: PDF generation (CAP 1590B forms)
- `voluptuous`: Config flow schema validation (Home Assistant standard)
- Home Assistant types: `ConfigEntry`, `SensorEntity`, `BinarySensorEntity`, `ServiceCall`

### File System Access
- PDFs written to `/config/www/hangar/` (persistent Home Assistant storage)
- Cleanup service removes files older than retention period (default 7 months)

### Sensor Entity Reads
- Always check entity existence: `hass.states.get(entity_id)` returns `None` if missing
- Example pattern in `BackupSafetySensor`: Check multiple remote backup entities before falling back to warning state

## Developer Workflows

### Testing & Validation
- **HACS Validation**: Runs in CI via `hacs/action@main` — validates manifest.json and folder structure
- **Flake8 Linting**: Checks Python syntax (E9, F63, F7, F82 errors only in CI)
- **Manifest Version**: Verify semantic versioning in manifest matches intended releases

### Building/Deployments
- No build step required (pure Python integration)
- HACS installation: User adds repo as custom repository, then installs via Home Assistant UI
- Restart Home Assistant after installation to load integration

## Example Patterns to Follow

### Adding a New Sensor Type
1. Create new class inheriting from `SensorEntity` in `sensor.py`
2. Add `self._attr_name`, `self._attr_unit_of_measurement`, `state` property
3. In `async_setup_entry()`, filter config by type and instantiate:
   ```python
   if config.get("type") == "airfield":
       async_add_entities([YourNewSensor(hass, config)])
   ```
4. Test by restarting Home Assistant and checking Settings > Devices & Services

### Safety & Data Validation
- **Assume missing sensors**: Always handle `None` returns from state machine gracefully
- **Aviation domain**: Document ISA assumptions; never alter formulas without aviation references
- **Disclaimer**: All output must acknowledge non-operational status (see README safety note)

## Non-Patterns (Avoid)

- **Async Complexity**: Keep async/await simple; use `hass.config_entries.async_entries()` not manual registry parsing
- **Direct File I/O Outside Designated Paths**: Only write to `/config/www/hangar/`; never mix data storage
- **Config Schema Changes**: Versioning exists (`VERSION = 1` in config flow) — increment if changing schema
