# Changelog

All notable changes to this project will be documented in this file.

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
