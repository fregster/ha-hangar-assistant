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
- **Testing**: Local tests in `tests/`. Run with `pytest`.
  - `test_formulas.py`: Pure python unit tests for aviation math.
  - `test_integration.py` & `test_binary_sensor.py`: Integration tests.
- **Validation**: CI/CD uses GitHub Actions (`validate.yml`) for Hassfest/HACS validation.
- **New Sensor Workflow**:
  1. Subclass `HangarSensorBase`.
  2. Implement `name` property and logic.
  3. Add to `async_setup_entry` in `sensor.py`.
