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

## Key Patterns
- **Slugification**: Consistent ID generation: `_id_slug = (config.get("name") or config.get("reg")).lower().replace(" ", "_")`.
- **Sibling Entity Reference**: Sensors reference each other using constructed entity IDs (e.g., `HangarMasterSafetyAlert` monitors `sensor.{_id_slug}_weather_data_age`).
- **Base Class**: `HangarSensorBase` handles device registration, `_id_slug` generation, and safe state retrieval (`_get_sensor_value`).
- **Aviation Formulas**:
  - DA: `4000 + (120 * (temp - 15))` ft
  - Cloud Base: `((t - dp) / 2.5) * 1000` ft
  - Carb Risk: "Serious" if `T < 25` and `Spread < 5`.

## Implementation Details
- **Safety Alerts**: `HangarMasterSafetyAlert` (Binary Sensor, class `SAFETY`) triggers if weather data > 30 mins old or Carb Risk is "Serious Risk".
- **File Management**: PDFs stored in `hass.config.path("www/hangar/")`. `manual_cleanup` service handles deletion.
- **AI Prompts**: All AI-related prompts (system prompts, briefing templates) must be stored as `.txt` files in the `custom_components/hangar_assistant/prompts/` directory. Do not hardcode complex prompts in Python code.
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
