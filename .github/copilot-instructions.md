# AI Coding Agent Instructions: Hangar Assistant

## Architecture & Data Model
- **Single ConfigEntry**: Data stored in `entry.data` under keys `airfields` (list of dicts) and `aircraft` (list of dicts).
- **Dynamic Entities**: `sensor.py` and `binary_sensor.py` iterate over these lists in `async_setup_entry`.
- **Device Grouping**: All entities for a specific airfield or aircraft share a `device_info` linked via `_id_slug`.

## Key Patterns
- **Slugification**: Consistent ID generation: `_id_slug = (config.get("name") or config.get("reg")).lower().replace(" ", "_")`.
- **Entity ID Patterns**: Slugs are used to reference sibling sensors: `sensor.{_id_slug}_weather_data_age`.
- **Sensor Base**: `HangarSensorBase` provides `_get_sensor_value()` for safe state retrieval and conversion.
- **Aviation Formulas**: 
  - DA: `4000 + (120 * (temp - 15))` ft
  - Cloud Base: `((t - dp) / 2.5) * 1000` ft
  - Carb Risk: "Serious" if `T < 25` and `Spread < 5`.

## Implementation Details
- **Safety Alerts**: `HangarMasterSafetyAlert` is `on` if weather data > 30 mins old or Carb Risk is "Serious Risk".
- **File Management**: Use `hass.config.path("www/hangar/")` for PDF storage. Cleanup via `manual_cleanup` service in `__init__.py`.
- **Options Flow**: Updates to airfields/aircraft are handled via `HangarOptionsFlowHandler`, triggering a full reload of the entry.
- **Versioning**: Follows `YYYYNN.V` (e.g., `2601.1`).

## Common Tasks
- **New Sensor**: Subclass `HangarSensorBase`, implement `name` and `native_value`.
- **New Step**: Add to `HangarOptionsFlowHandler.async_step_init` menu and implement the step method.
- **CI/CD**: Hassfest and HACS validation via GitHub Actions (`validate.yml`). No local unit tests; verify via Developer Tools > States.
