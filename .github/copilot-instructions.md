# AI Coding Agent Instructions: Hangar Assistant

## Project Overview
Hangar Assistant is a Home Assistant integration for aviation safety and compliance.
- **Domain**: `hangar_assistant`
- **Dependencies**: `fpdf2` (via `manifest.json`)
- **Versioning**: `YYYYNN.V.H` format (e.g., `2601.1.0`). Hotfix defaults to 0.

## Architecture & Data Model
- **Single ConfigEntry**: Configuration is centralized. `entry.data` holds `airfields` (list), `hangars` (list), and `aircraft` (list).
- **Hangar System**: Hangars belong to airfields. Aircraft can link to hangars (which implies their airfield) or directly to airfields (legacy).
- **Data Hierarchy**: Airfield → Hangar → Aircraft. Sensor fallback: hangar sensor → airfield sensor → global sensor.
- **Dynamic Entities**: `sensor.py` and `binary_sensor.py` iterate over config lists in `async_setup_entry` to create entities.
- **Device Grouping**: Entities for a specific airfield or aircraft share `device_info` linked via `_id_slug`.
- **Unique IDs**: Generated as `{_id_slug}_{class_name_lower}` (e.g., `ksfo_densityaltsensor`). Hangars use `{airfield_slug}_{hangar_slug}`.

## Backward Compatibility & Defaults

**CRITICAL PRINCIPLE**: Existing installations must NEVER break due to updates. End users have invested significant effort in their setup. Forcing reinstalls, migrations, or configuration changes is unacceptable.

### Default Values
- **Every new configuration option MUST have a sensible default** that maintains existing behavior:
  - New features default to disabled or use traditional/conservative settings
  - New sensor parameters use safe fallbacks (e.g., `default=0`, `default=None`, `default=""`)
  - Unit preferences default to aviation units (existing behavior)
  - New boolean flags default to `False` unless explicitly enabling is required for safety
  
  Example (✓ correct):
  ```python
  unit_preference = settings.get("unit_preference", DEFAULT_UNIT_PREFERENCE)  # Defaults to aviation
  timeout = config.get("timeout_seconds", 30)  # Safe default if missing
  ```

### Graceful Degradation
- **Handle missing config keys**: Always use `.get()` with defaults, never direct dictionary access
- **Validate and coerce types**: Check if values exist and are the expected type before use
- **Fallback behavior**: If a new feature is unavailable, degrade gracefully:
  ```python
  if global_setting := settings.get("feature_flag"):
      # Use new feature
  else:
      # Use original behavior
  ```
- **Skip optional sensors**: If required config is missing, skip sensor creation but don't error:
  ```python
  if all required fields present:
      entities.append(NewSensor(...))
  # Don't append if missing - user can add later via config
  ```

### Data Migrations
- **Automatic migrations**: If config structure changes, migrate in `async_setup_entry()` BEFORE using data
- **Non-destructive**: Never delete user data; transform it in-place or create new fields
- **Document migrations**: Add comments explaining version-specific migration logic

  Example:
  ```python
  # Migrate old config format to new (v2601.2.0+)
  if "elevation_ft" in airfield and "elevation" not in airfield:
      airfield["elevation"] = airfield["elevation_ft"] * 0.3048  # Convert to meters
  ```

### Testing for Compatibility
- **Test upgrade paths**: Include test cases for existing (old) configurations:
  ```python
  def test_sensor_works_without_new_setting():
      """Test sensor works when new optional setting is missing."""
      config = {"name": "Popham"}  # Deliberately omit new field
      sensor = DensityAltSensor(mock_hass, config, {})
      assert sensor is not None  # Must not crash
  ```
- **Verify existing entities still work**: After adding new features, ensure all existing sensors/binary sensors still report correct values
- **Cross-version testing**: Test with config from previous version to ensure no breaking changes

### Adding New Features Safely
1. **Add setting with default**: `setting = config.get("feature", DEFAULT_VALUE)`
2. **Make conditionally optional**: Use new feature IF present, else use original logic
3. **Include migration code**: If changing data structure, migrate old → new format automatically
4. **Test without new feature**: Verify sensors work if user hasn't configured new setting yet
5. **Document changes**: Note in release notes which features are optional vs. mandatory

### Version-Specific Behavior
- **Feature flags for major changes**: Use version checks if needed for compatibility
- **Log migration actions**: Inform users (debug level) when migrations occur
  ```python
  _LOGGER.debug("Migrating config from v2600 format: converting elevation to meters")
  ```

### Examples of CORRECT Approaches
✓ Unit preference system: Defaults to aviation (existing behavior), users opt-in to SI  
✓ Optional sensors: Only created if required config present, gracefully skipped if missing  
✓ New parameters: All have defaults, `.get()` used throughout, no required migrations  
✓ Global settings: Stored in settings dict with defaults for any missing keys  

### Examples of INCORRECT Approaches  
✗ Forcing a config format change without automatic migration  
✗ Removing fields from config without providing fallback values  
✗ Making a previously optional parameter required  
✗ Creating sensors/entities that fail if new features not configured  
✗ Changing default behavior without version-specific handling

## OpenWeatherMap Integration (Optional Feature)

The integration includes optional OpenWeatherMap (OWM) One Call API 3.0 support for professional weather data.

### Configuration Architecture

**Global Settings** (entry.data["settings"]):
- `openweathermap_api_key`: Optional API key (password field, empty string if not configured)
- `openweathermap_enabled`: Boolean (default: False) - master toggle
- `openweathermap_cache_enabled`: Boolean (default: True) - enable persistent caching
- `openweathermap_update_interval`: Integer (default: 10) - minutes between API calls
- `openweathermap_cache_ttl`: Integer (default: 10) - minutes cache remains valid

**Per-Airfield Settings** (airfield config):
- `weather_data_source`: String (default: "sensors") - options: "sensors", "openweathermap", "hybrid", "sensors_backup_owm"
- `use_owm_forecast`: Boolean (default: True) - create forecast sensors
- `use_owm_alerts`: Boolean (default: True) - create alert binary sensors

### Data Source Modes

| Mode | Behavior |
|------|----------|
| `"sensors"` | Use only HA sensors (default, current behavior) |
| `"openweathermap"` | Use only OWM API, ignore sensors |
| `"hybrid"` | OWM primary, fallback to sensors if OWM fails |
| `"sensors_backup_owm"` | Sensors primary, fallback to OWM if sensors unavailable |

### Caching Strategy

**Critical for rate limit protection:**
- **Two-level cache**: In-memory (session) + persistent file (survives restarts)
- **Persistent cache location**: `hass.config.path("hangar_assistant_cache/")`
- **Cache lookup order**: Memory cache → Persistent file → API call
- **Rate limit tracking**: Warns at 950/1000 daily calls
- **Restart protection**: Persistent cache prevents API calls during HA restarts/reloads

### OWM Data Points

**Current Weather** (replaces/augments sensor data):
- Temperature, dew point, pressure, wind (speed/direction/gust)
- Visibility, cloud coverage, humidity, UV index
- Weather description and icon

**Forecast Data** (new sensors):
- `sensor.{airfield}_weather_forecast_hourly`: 48-hour hourly forecast (JSON)
- `sensor.{airfield}_weather_forecast_daily`: 8-day daily forecast (JSON)
- `sensor.{airfield}_precipitation_forecast`: Minutes until next rain
- `sensor.{airfield}_uv_index`: Current UV index

**Alerts** (new binary sensors):
- `binary_sensor.{airfield}_government_weather_alert`: Active government weather warnings
- Attributes include sender, event type, severity, start/end times, description

### Implementation Patterns

**Sensor with OWM fallback:**
```python
def _get_temperature(self):
    """Get temperature with OWM fallback."""
    data_source = self.config.get("weather_data_source", "sensors")
    
    if data_source == "openweathermap":
        return self._get_owm_temperature()
    elif data_source == "sensors":
        return self._get_sensor_temperature()
    elif data_source == "hybrid":
        owm_temp = self._get_owm_temperature()
        return owm_temp if owm_temp is not None else self._get_sensor_temperature()
    elif data_source == "sensors_backup_owm":
        sensor_temp = self._get_sensor_temperature()
        return sensor_temp if sensor_temp is not None else self._get_owm_temperature()
```

**Backward Compatibility:**
- If no API key configured, OWM features completely hidden in UI
- All existing sensors work unchanged
- Per-airfield `weather_data_source` defaults to `"sensors"`
- No breaking changes for existing installations

### AI Briefing Enhancement

When OWM enabled, AI briefings include:
- 6-hour forecast trends
- 3-day daily forecast
- Government weather alerts
- Precipitation timing ("Rain in 42 minutes")
- Enhanced GO/NO-GO recommendations based on forecast

### Testing Requirements

**OWM-specific tests:**
- `test_openweathermap.py`: Client initialization, caching, API interactions, data extraction
- Mock API responses for all test scenarios
- Test cache hit/miss scenarios
- Test rate limit protection
- Test backward compatibility (sensors work without OWM)

**Integration tests:**
- Test sensor creation with different `weather_data_source` modes
- Test fallback behavior
- Test forecast sensor attributes
- Test alert sensor state transitions

✓ Global settings: Stored in settings dict with defaults for any missing keys  

### Examples of INCORRECT Approaches  
✗ Forcing a config format change without automatic migration  
✗ Removing fields from config without providing fallback values  
✗ Making a previously optional parameter required  
✗ Creating sensors/entities that fail if new features not configured  
✗ Changing default behavior without version-specific handling

## Key Patterns
- **Slugification**: Consistent ID generation: `_id_slug = (config.get("name") or config.get("reg")).lower().replace(" ", "_")`.
- **Sibling Entity Reference**: Sensors reference each other using constructed entity IDs (e.g., `HangarMasterSafetyAlert` monitors `sensor.{_id_slug}_weather_data_age`).
- **Base Class**: `HangarSensorBase` handles device registration, `_id_slug` generation, and safe state retrieval (`_get_sensor_value`).
- **Aviation Formulas**:
  - DA: `4000 + (120 * (temp - 15))` ft
  - Cloud Base: `((t - dp) / 2.5) * 1000` ft
  - Carb Risk: "Serious" if `T < 25` and `Spread < 5`.

## Code Documentation Standards

**All new classes and functions must include comprehensive docstrings** that follow this format:

### Class Docstrings
```python
class MyClass:
    """Brief one-line description of what the class does.
    
    Longer description explaining the purpose, key responsibilities, and how it fits into the system.
    
    Inputs (if applicable):
        - config_param: Description and expected type
        - another_param: Description and expected type
    
    Outputs/Behavior:
        - Brief description of what the class produces or manages
        - Key properties or methods
    
    Used by:
        - Dashboard cards
        - Automation triggers
        - Other systems that depend on this class
    
    Example:
        - Specific usage example if helpful
    """
```

### Function Docstrings
```python
def my_function(param1: str, param2: int) -> bool:
    """Brief description of what the function does.
    
    Longer explanation of the function's purpose, algorithm, or key behavior.
    
    Args:
        param1: Description and expected format/range
        param2: Description and expected format/range
    
    Returns:
        Description of return value and when it occurs
    
    Raises:
        ValueError: When inputs are invalid
    """
```

**Key Documentation Principles:**
- **Purpose**: Clearly state what the code does and why it exists
- **Inputs**: Document all parameters with types and expected values/ranges
- **Outputs**: Explain return values or behavior changes
- **Context**: Mention how the code integrates with the broader system
- **Examples**: Include usage examples for complex functions/classes
- **Comments**: Use inline comments for non-obvious logic or calculations (especially aviation formulas)

## Entity Implementation Patterns
- **Safety Alerts**: `HangarMasterSafetyAlert` (Binary Sensor, class `SAFETY`) triggers if weather data > 30 mins old or Carb Risk is "Serious Risk".
- **File Management**: PDFs stored in `hass.config.path("www/hangar/")`. `manual_cleanup` service handles deletion.
- **AI Prompts**: All AI-related prompts (system prompts, briefing templates) must be stored as `.txt` files in the `custom_components/hangar_assistant/prompts/` directory. Do not hardcode complex prompts in Python code.
- **Reference Documentation**: Context-specific reference materials are stored as `.txt` files in `custom_components/hangar_assistant/references/`. These include:
  - `vfr.txt`: UK CAA Visual Flight Rules (VFR) requirements and minima
  - Other aviation regulations and compliance standards
  - Use these files as authoritative sources when implementing rules-based features
- **Config Flow**: `HangarAssistantConfigFlow` (single instance). `HangarOptionsFlowHandler` handles updates (`airfield`, `aircraft` menus) using `EntitySelector`.
- **Time Tracking**: `async_track_time_change` used for briefing schedules in `__init__.py`.

### Sensor Implementation
- Derive from `SensorEntity` (imported from `homeassistant.components.sensor`)
- Filter config entries by type in `async_setup_entry()` before creating entities
- Access Home Assistant state machine via `self.hass.states.get(entity_id)` for sensor reads
- Name pattern: `f"{config['name']} {metric_name}"` (e.g., "The Airfield Carb Risk")
- **Best Runway Logic**: Uses `BestRunwaySensor` to calculate optimal runway based on wind and provides `crosswind_component` as an attribute.
- **Map Integration**: Sensors for airfields should include `latitude` and `longitude` attributes to enable automatic plotting on map cards.

### Select Entity Implementation
- Derive from `SelectEntity` (imported from `homeassistant.components.select`)
- Provides built-in dropdowns for airfield, aircraft, and pilot selection without requiring user-created input_select helpers
- Options derived from config entry data: `entry.data.get("airfields")`, `entry.data.get("aircraft")`, etc.
- Uses `_slugify()` helper for consistent ID generation from names/registrations
- Pattern: `f"select.{entity_type}_selector"` (e.g., `select.airfield_selector`)
- Stores selected value in state; updates when user changes selection via UI
- Device grouping: All selectors share a common device info for dashboard organization
- Used by: Dashboard cards for dynamic filtering and context switching

### Dashboard & UI
- Template located in `dashboard_templates/glass_cockpit.yaml`.
- Uses Mushroom cards and ApexCharts (suggest these to users).
- Performance sliders: Uses `input_number` helpers (user-defined) to drive dynamic ground roll adjustments.

**Dashboard State Management (Per-Device Selection):**
- Each device/browser maintains independent airfield/aircraft view using `hangar_state_manager.js`
- Priority system: URL params → localStorage → config defaults → auto-detection
- **Fixed displays**: Use URL parameters for permanent selection
  - Example: `http://homeassistant:8123/hangar-glass-cockpit?airfield=popham&aircraft=g_abcd`
- **Interactive users**: Browser localStorage preserves last selection
- **Config defaults**: Set in Settings → General Settings → Default Dashboard Airfield/Aircraft
- **Backward compatibility**: Select entities remain functional for automations
- Implementation file: `dashboard_templates/hangar_state_manager.js`

## Services Development

Services are defined in `services.yaml` and registered in `__init__.py`. All services must follow Home Assistant service patterns:

### Service Registration Pattern
```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up integration and register services."""
    
    async def handle_service(call: ServiceCall) -> None:
        """Handle service call."""
        # Extract parameters
        param = call.data.get("param_name", default_value)
        # Perform action
        await async_do_something(param)
    
    hass.services.async_register(DOMAIN, "service_name", handle_service)
```

### Available Services

**manual_cleanup**: Purges aviation records (PDFs) older than specified retention period
- Parameters: `retention_months` (1-24, default: 7)
- Implementation: Scans `www/hangar/` directory, deletes files older than threshold
- Usage: Automation or manual maintenance

**rebuild_dashboard**: Forces fresh generation of dashboard from template
- Parameters: None
- Implementation: Regenerates dashboard YAML from `dashboard_templates/glass_cockpit.yaml`
- Usage: After config changes or template updates

**refresh_ai_briefings**: Manually triggers AI briefing generation
- Parameters: None
- Implementation: Calls AI API with current weather/NOTAM data for all airfields
- Usage: On-demand briefing updates outside scheduled times

**speak_briefing**: Speaks current AI briefing via TTS
- Parameters: `tts_entity_id` (required), `media_player_entity_id` (optional)
- Implementation: Retrieves briefing text, calls TTS service, plays on media player
- Usage: Voice briefing delivery; defaults to browser player if available

### Service Best Practices
- Always use `async def` for service handlers
- Validate parameters with `.get()` and defaults
- Log service calls at debug level: `_LOGGER.debug(f"Service called: {call.data}")`
- Raise `ServiceValidationError` for invalid parameters (from `homeassistant.exceptions`)
- Use `hass.async_add_executor_job()` for blocking I/O operations
- Update related entities after service completion: `async_write_ha_state()`

## Utility Modules

Common functionality is organized in `utils/` directory:

### units.py - Unit Conversion
Provides conversion between aviation and SI units:
- **UnitPreference class**: Manages global unit preference (aviation/SI)
- **Conversion constants**: `FEET_TO_METERS`, `KNOTS_TO_KPH`, `POUNDS_TO_KG`
- **Conversion functions**: Bidirectional conversion with preference awareness
- Used by: All sensors for consistent unit display based on user preference
- Pattern: `convert_distance(value, from_unit, to_unit, preference)`

### i18n.py - Internationalization
Handles translation and localization:
- **SUPPORTED_LANGS**: `["en", "de", "es", "fr"]`
- **COMMON_LABELS**: Dictionary of reusable translated strings for UI elements
- **get_available_languages()**: Returns list of available language packs
- **validate_translations()**: Ensures deep key parity across all language files
- Used by: Config flow for localized labels, validation tests
- Pattern: `label = COMMON_LABELS["key"][lang]`

### pdf_generator.py - PDF Generation
Generates aviation compliance documents:
- **CAP1590BGenerator**: UK CAA cost-sharing declaration PDF
- Uses `fpdf2` library for PDF creation
- Stores output in `hass.config.path("www/hangar/")`
- Pattern: `generator.generate(output_path, pilot, aircraft, passengers, flight_details)`
- File naming: `{date}_{flight_type}_{airfield}.pdf`
- Cleanup: Managed by `manual_cleanup` service

### openweathermap.py - Weather API Integration
Provides professional weather data with robust caching:
- **OpenWeatherMapClient**: Client for OpenWeatherMap One Call API 3.0
- **Multi-level caching**: In-memory + persistent file-based caching
- **Rate limit protection**: Tracks API calls per day, warns at 950/1000 limit
- **Persistent cache directory**: `hass.config.path("hangar_assistant_cache/")`
- **Cache TTL**: Configurable (default: 10 minutes, matches OWM update frequency)
- **Data extraction methods**: `extract_current_weather()`, `extract_hourly_forecast()`, `extract_daily_forecast()`, `extract_minutely_forecast()`, `extract_alerts()`
- **Cache management**: `clear_cache()`, `get_cache_stats()`
- **Survives restarts**: Persistent cache protects against API limit breaches during system restarts
- Used by: Weather sensors, forecast sensors, alert sensors, AI briefing enrichment
- Pattern: 
  ```python
  client = OpenWeatherMapClient(api_key, hass, cache_enabled=True)
  data = await client.get_weather_data(latitude, longitude)
  current = client.extract_current_weather(data)
  ```

### hangar_helpers.py - Hangar Management & Backward Compatibility
Provides hangar-aware sensor fallback and aircraft-airfield resolution:
- **get_aircraft_airfield()**: Resolves airfield for aircraft with hangar → direct airfield → None priority
- **get_aircraft_hangar()**: Returns hangar config if aircraft assigned to hangar
- **get_hangar_sensor_value()**: Core fallback logic for environment sensors (hangar → airfield → global)
- **find_hangar_by_name()**: Locates hangar config by name
- **get_airfield_for_hangar()**: Gets airfield config for a hangar
- **get_hangar_temperature()**: Convenience function for temperature with full fallback chain
- **get_hangar_humidity()**: Convenience function for humidity with full fallback chain
- Used by: Sensors needing location-based data, migration logic, automation helpers
- Pattern:
  ```python
  from custom_components.hangar_assistant.utils.hangar_helpers import get_aircraft_airfield
  
  airfield = get_aircraft_airfield(aircraft_config, hangars, airfields)
  temp = get_hangar_sensor_value(hass, "temp_sensor", hangar, airfield, global_sensor)
  ```

### Brand Directory
Contains branding assets:
- Integration logo and icons for HACS/HA UI
- Used by Home Assistant for integration marketplace display
- Files: `icon.png`, `logo.png` (if present)

## Developer Workflow & Testing

### Unit Testing Best Practices
- **Mandatory Test Coverage**: For any code edits, new functions, or new classes, you MUST create or update corresponding unit tests. Tests must be added to the appropriate test file in the `tests/` directory.
- **Use Mocks, Not Real HA System**: Create unit tests with `unittest.mock` (MagicMock, patch) rather than requiring the full Home Assistant system. Mock `hass`, `states`, and `config_entries` as needed.
- **Mock Architecture Example**:
  ```python
  from unittest.mock import MagicMock
  mock_hass = MagicMock()
  mock_hass.states = MagicMock()
  mock_hass.states.get.return_value = MagicMock(state="15")
  sensor = DensityAltSensor(mock_hass, config, entry_data)
  ```
- **Avoid Integration Loader**: Do NOT use `hass.config_entries.flow.async_init()` or similar integration discovery features in unit tests—the integration may not be discoverable in test environments. Instead, instantiate flow handlers directly and mock their dependencies.
- **Property Patching**: Cannot patch class properties directly. Instead, create mock instances with properties set via `MagicMock` attributes (e.g., `mock_entry.data = {"key": "value"}`).
- **Timezone Awareness**: Use `homeassistant.util.dt.utcnow()` for timezone-aware datetimes in tests (not `datetime.utcnow()`).

### Local Development & Testing
- **Development Environment**: Solutions are developed locally on the developer's machine.
- **Remote Testing**: Code is tested on a remote Home Assistant server before release to ensure real-world integration with actual HA instances.
- **Testing**: Local unit tests in `tests/` directory. Run with `pytest`.
  - Run all tests: `.venv/bin/pytest tests/`
  - Run with coverage: `.venv/bin/pytest tests/ --cov=custom_components/hangar_assistant`

### Test File Reference

| Test File | Purpose | Coverage |
|-----------|---------|----------|
| `test_formulas.py` | Pure Python aviation math (DA, cloud base, carb risk) | Formula accuracy, edge cases |
| `test_binary_sensor.py` | Binary sensor logic (safety alerts, warnings) | State determination, mocked dependencies |
| `test_sensor_coverage.py` | Sensor entity creation and attributes | All sensor types, device info, unique IDs |
| `test_sensor_setup_coverage.py` | Sensor platform setup flow | `async_setup_entry()`, entity registration |
| `test_sensor_unit_preference.py` | Unit conversion in sensors | Aviation vs SI units, preference handling |
| `test_sensor_caching.py` | Sensor state caching behavior | Performance optimization, cache invalidation |
| `test_config_flow.py` | Config flow user interactions | Form validation, data storage |
| `test_config_flow_coverage.py` | Config flow edge cases | Error handling, partial configs |
| `test_config_flow_init.py` | Options flow initialization | Flow handler setup without errors |
| `test_hangar_config_flow.py` | Hangar config flow and helpers | Hangar CRUD, sensor fallback, backward compat |
| `test_enhanced_logic.py` | Complex integration logic | Multi-sensor interactions, mocked HA system |
| `test_integration.py` | End-to-end integration tests | Full setup flow, entity coordination |
| `test_select_entities.py` | Select entity implementation | Dropdown options, state updates |
| `test_services.py` | Service handlers and registration | Service calls, parameter validation |
| `test_pdf_generator.py` | PDF generation functionality | CAP1590B output, file creation |
| `test_pdf_edge_cases.py` | PDF generation edge cases | Missing data, special characters |
| `test_unit_conversion.py` | Unit conversion utilities | `units.py` functions, preference system |
| `test_i18n_labels.py` | Translation label availability | COMMON_LABELS completeness |
| `test_languages.py` | Language pack validation | Deep key parity across all languages |
| `test_json_validation.py` | JSON file structure | Valid JSON, no duplicates/concatenation |
| `test_config_validation.py` | Config entry validation | Schema compliance, required fields |
| `test_input_validation.py` | User input sanitization | XSS prevention, type coercion |
| `test_error_handling.py` | Exception handling | Graceful degradation, error messages |
| `test_scenarios.py` | Real-world usage scenarios | Complete workflows, integration tests |
| `test_performance_margin.py` | Aircraft performance calculations | Margin of safety, ground roll adjustments |
| `test_runway_suitability.py` | Runway selection logic | Wind component calculations, suitability |
| `test_code_quality_validation.py` | Code quality checks | Complexity, async usage, clean imports |

### GitHub & Continuous Integration
- **Repository**: All code changes are pushed to GitHub repository.
- **GitHub Actions CI/CD**: Automated workflows run on every commit/PR:
  - **Code Validation** (`validate.yml`): Runs Hassfest validation and HACS compliance checks.
  - **Linting**: flake8 and mypy type checking on all Python files.
  - **Release Tests**: Automated tests execute against the code to verify functionality.
- **Deployment**: GitHub Actions handles automated releases and package distribution to HACS (Home Assistant Community Store).
- **Version Management**: Follows `YYYYNN.V.H` format (e.g., `2601.1.0`). GitHub Actions tags releases and creates release notes.

### New Sensor Workflow
1. Subclass `HangarSensorBase`.
2. Implement `name` property and logic.
3. Add to `async_setup_entry` in `sensor.py`.
4. Write unit tests in `tests/` covering the new functionality.
5. Run local tests: `.venv/bin/pytest tests/`
6. Run flake8 and mypy for code quality.
7. Deploy to remote Home Assistant server for integration testing.
8. Push to GitHub and let CI/CD pipeline validate.

## Error Detection & Prevention

### Type Checking (MyPy)
The project uses **mypy** for static type checking. This catches many errors before runtime:

**Run locally before committing:**
```bash
.venv/bin/mypy custom_components/hangar_assistant --ignore-missing-imports
```

**Common issues caught by mypy:**
- Assigning to read-only properties (e.g., `self.config_entry = value` when it's a property)
- Type mismatches in function arguments/returns
- Accessing non-existent attributes on objects
- None vs non-None type violations

**Key pattern - Home Assistant OptionsFlow:**
The `OptionsFlow` base class from Home Assistant defines `config_entry` as a read-only property. Do NOT try to assign to it directly:

❌ WRONG:
```python
def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
    super().__init__()
    self.config_entry = config_entry  # ERROR: property has no setter
```

✓ CORRECT:
```python
def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
    super().__init__()
    # Store as private attribute if you need to reference it
    self._config_entry = config_entry
```

### Linting (Flake8)
Catches syntax errors, undefined names, and code complexity issues:

**Run locally:**
```bash
.venv/bin/flake8 custom_components/hangar_assistant --count --select=E9,F63,F7,F82 --show-source --statistics
```

### Unit Tests
Tests catch logical errors and integration issues:

**Run locally:**
```bash
.venv/bin/pytest tests/ -v
```

**Best practices for config flow testing:**
- Mock the `ConfigEntry` and `HA` objects properly
- Test that `__init__` completes without errors
- Verify that data methods (`_entry_data()`, `_entry_options()`) work correctly
- Test with partial/missing config to ensure graceful handling

Example:
```python
def test_options_flow_init():
    """Test OptionsFlowHandler initialization without errors."""
    mock_entry = MagicMock(spec=config_entries.ConfigEntry)
    mock_entry.data = {"airfields": []}
    mock_entry.options = {}
    
    # Should initialize without raising AttributeError
    handler = HangarOptionsFlowHandler(mock_entry)
    assert handler._config_entry is mock_entry
```

### Pre-commit Validation Checklist
Before pushing code, run this locally:

```bash
# 1. Type checking
.venv/bin/mypy custom_components/hangar_assistant --ignore-missing-imports

# 2. Syntax & quality
.venv/bin/flake8 custom_components/hangar_assistant --count --select=E9,F63,F7,F82 --show-source --statistics

# 3. All tests
.venv/bin/pytest tests/ -v

# 4. Complex checks
.venv/bin/flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127
```

### CI/CD Pipeline
The GitHub Actions pipeline runs automatically on every commit and performs:
1. **Hassfest**: Official Home Assistant validation
2. **Flake8**: Code quality checks
3. **MyPy**: Type checking (catches property assignment errors)
4. **Pytest**: All unit tests must pass

**If CI/CD fails after your changes:**
- Check the specific error message in GitHub Actions logs
- Run the same check locally to reproduce
- Fix locally and verify with tools above
- Push corrected code

### Home Assistant API Patterns to Watch
These commonly cause runtime errors if not properly typed/used:

1. **Read-only properties**: Check HA documentation for `@property` vs `@property.setter`
2. **Config entry data**: Always use `.get()` with defaults, never direct dictionary access
3. **State machine access**: Handle `None` and "unavailable" states gracefully
4. **Async functions**: All `async_*` methods must be awaited in async context
5. **Event listeners**: Remember to call `async_on_remove()` to prevent memory leaks

### Code Quality & SonarLint Standards

To maintain a high-quality codebase and pass automated analysis, follow these rules:

- **Refactor for Complexity**: Keep functions focused. If a function's cognitive complexity exceeds 15 (e.g., deeply nested logic, many branches), refactor it into smaller, descriptive private methods.
- **Clean Async Usage**:
    - Only use the `async` keyword if the function contains an `await` statement.
    - Never perform blocking I/O (like `open()`, `os.*`, or `yaml.load()`) directly in an `async` function. Always wrap them in `hass.async_add_executor_job`.
- **Unused Parameters**: If a required callback parameter (like `now` in `async_track_time_change` or `call` in service handlers) is not used, prefix it with an underscore (e.g., `_now`, `_call`) or omit it if the API allows.
- **Exception Handling**:
    - Avoid catching redundant exceptions (e.g., don't catch `OSError` and `FileNotFoundError` in the same block, as `FileNotFoundError` is a subclass of `OSError`).
    - Use specific exceptions rather than a broad `Exception` where possible.
- **Clean Imports**: Remove any unused imports. If an import is only needed for type checking, use `if TYPE_CHECKING:`.

### Localization & Translations Guidance

To ensure a consistent, high-quality multilingual UI, follow these rules:

- **English is the source of truth**: Add or change UI strings first in `custom_components/hangar_assistant/strings.json` and `translations/en.json`. Treat English as the default pack.
- **Complete translations in all packs**: Mirror every English key to `translations/de.json`, `translations/es.json`, and `translations/fr.json` with fully translated values. Do **not** leave English placeholders in non-English packs once translations exist.
- **No duplicate or concatenated JSON**: Each translation file must contain a single JSON object only. Do not paste the English file beneath or alongside a translation; validate with `pytest tests/test_json_validation.py -q` after edits.
- **Fallback only when necessary**: If a precise translation truly isn’t available, you may temporarily copy the English string—but track and replace it with a proper translation as soon as possible. Document any temporary English entries in the PR description.
- **No hardcoded text**: Do not hardcode user-facing strings in Python or YAML. Use the HA translation framework (strings.json + translations/*.json) for config flows and entity names.
- **Deep key completeness**: Ensure each non-English pack contains all keys present in the English pack (including nested `options.step.*.*.data` and `menu_options`). A unit test must verify deep key parity across all packs.
- **When generating new content with AI**: Default to English phrasing, then translate into the available language packs where possible. Keep aviation terminology clear and consistent across languages.
- **Review and QA**: After changing translations, run `pytest` to confirm deep key completeness and that config flows render without placeholders.
