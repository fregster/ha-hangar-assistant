# Changelog

All notable changes to this project will be documented in this file.

## [2601.1.2] - 2026-01-19

### Added
- **Pilot Management**: Added email field for pilots (stored privately) and support for multi-pilot briefing recipients.
- **ICAO Support**: Airfields now include an optional ICAO code field for better identification.
- **AI Prompt Management**: Moved complex AI prompts to external `.txt` files in a dedicated `prompts/` directory.
- **Manual Refresh**: Added `hangar_assistant.refresh_ai_briefings` service to manually trigger AI updates.

### Changed
- **AI Briefings**: Large briefing texts are now stored in sensor attributes to bypass the 255-character state limit.
- **Dashboard Templates**: Updated Glass Cockpit and Pilot Dashboard to v2 with inline AI briefings.

### Fixed
- **NameError**: Resolved missing `dt_util` import in `sensor.py`.
- **AI Reliability**: Improved error handling and logging for conversation service responses.

## [2601.1.1] - 2026-01-19

### Fixed
- **Hotfix**: Resolved `AttributeError` in `async_setup` caused by incorrect use of `cv.Optional`. Replaced with `vol.Optional`.

## [2601.1.0] - 2026-01-19

### Added
- **Initial Release** of Hangar Assistant.
- **Dynamic Fleet Management**: UI-based configuration for multiple airfields and aircraft.
- **Aviation Safety Sensors**: 
  - Real-time Density Altitude (DA) calculations.
  - Estimated Cloud Base (AGL).
  - Categorical Carburetor Icing Risk assessments.
  - Weather data freshness monitoring.
- **Master Safety Alert**: Binary sensor annunciator that trips on stale data or high carb icing risk.
- **Calculated Ground Roll**: Aircraft-specific takeoff performance adjusted by real-time Density Altitude.
- **Automated Briefings**: Scheduled daily briefing notifications via Home Assistant services.
- **Legal Compliance**: CAP 1590B PDF generation support and automated record retention/cleanup.
- **CI/CD Pipeline**: GitHub Actions for Hassfest, HACS validation, MyPy type checking, and Pytest coverage.
- **Translations**: Initial English (`en`) support.
- **UI Templates**: Glass cockpit and pilot dashboard YAML templates.
