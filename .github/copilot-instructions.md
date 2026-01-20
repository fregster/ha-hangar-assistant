# AI Coding Agent Instructions: Hangar Assistant

## Project Overview
Hangar Assistant is a Home Assistant integration for aviation safety and compliance.
- **Domain**: `hangar_assistant`
- **Dependencies**: `fpdf2` (via `manifest.json`)
- **Versioning**: `YYYYNN.V.H` format (e.g., `2601.1.0`). Hotfix defaults to 0.

## Architecture & Data Model
- **Single ConfigEntry**: Configuration is centralized. `entry.data` holds `airfields` (list) and `aircraft` (list).
- **Dynamic Entities**: `sensor.py` and `binary_sensor.py` iterate over config lists in `async_setup_entry` to create entities.
- **Device Grouping**: Entities for a specific airfield or aircraft share `device_info` linked via `_id_slug`.
- **Unique IDs**: Generated as `{_id_slug}_{class_name_lower}` (e.g., `ksfo_densityaltsensor`).

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

## Key Patterns
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

### Dashboard & UI
- Template located in `dashboard_templates/glass_cockpit.yaml`.
- Uses Mushroom cards and ApexCharts (suggest these to users).
- Performance sliders: Uses `input_number` helpers (user-defined) to drive dynamic ground roll adjustments.

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
  - `test_formulas.py`: Pure python unit tests for aviation math.
  - `test_binary_sensor.py`: Binary sensor logic tests (mocked state retrieval).
  - `test_enhanced_logic.py`: Integration tests for complex logic (mocked HA system).
  - `test_integration.py`: End-to-end integration tests (mocked entity setup).
  - `test_sensor_coverage.py`, `test_config_flow_coverage.py`, `test_sensor_setup_coverage.py`: Additional coverage tests (all mock-based).
  - Run all tests: `.venv/bin/pytest tests/`

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

## Localization & Translations Guidance

To ensure a consistent, high-quality multilingual UI, follow these rules:

- **English is the source of truth**: Add or change UI strings first in `custom_components/hangar_assistant/strings.json` and `translations/en.json`. Treat English as the default pack.
- **Translate to available packs**: Mirror all English keys to the available language packs `translations/de.json`, `translations/es.json`, and `translations/fr.json`. If a precise translation isn’t available, temporarily copy the English string so the UI remains complete.
- **No hardcoded text**: Do not hardcode user-facing strings in Python or YAML. Use the HA translation framework (strings.json + translations/*.json) for config flows and entity names.
- **Deep key completeness**: Ensure each non-English pack contains all keys present in the English pack (including nested `options.step.*.*.data` and `menu_options`). A unit test must verify deep key parity across all packs.
- **When generating new content with AI**: Default to English phrasing, then translate into the available language packs where possible. Keep aviation terminology clear and consistent across languages.
- **Review and QA**: After changing translations, run `pytest` to confirm deep key completeness and that config flows render without placeholders.
