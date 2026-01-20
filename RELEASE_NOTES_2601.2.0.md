# Hangar Assistant v2601.2.0 Release Notes

**Release Date**: 20 January 2026

## Overview
This release introduces a **global unit preference system** allowing users to work in either aviation units (feet, knots, pounds) or SI units (meters, kph, kilograms). It also improves code quality and reliability through enhanced type checking and comprehensive error detection patterns.

---

## 🎯 Major Features

### 1. **Global Unit Preference System**
Users can now select their preferred measurement system globally, affecting all sensors and calculations:

- **Aviation Units** (default): 
  - Altitude: feet (ft)
  - Speed: knots (kt)
  - Weight: pounds (lbs)

- **SI Units**: 
  - Altitude: meters (m)
  - Speed: kilometers per hour (kph)
  - Weight: kilograms (kg)

**Configuration**: Available in the integration's global settings via the Home Assistant UI.

**Affected Sensors**:
- Density Altitude
- Estimated Cloud Base
- Carburetor Icing Risk Transition Altitude
- Primary & Ideal Runway Crosswind Components
- Best Runway Selection (wind components)
- Calculated Ground Roll

---

## ✨ Improvements

### Code Quality & Reliability
- **Type Safety**: Full MyPy type checking (0 errors). All Optional types properly handled.
- **Syntax Validation**: Flake8 linting passes with no critical errors.
- **Test Coverage**: Comprehensive unit test suite (231 tests) covering:
  - Unit conversion functions and preferences
  - Sensor behavior with different unit settings
  - Configuration flow initialization
  - Integration scenarios
  - Backward compatibility

### Error Detection & Prevention
- **Backward Compatibility**: New unit preference defaults to aviation units (existing behavior)—users opt-in to SI.
- **Graceful Degradation**: Sensors work correctly if configuration is partially missing.
- **Comprehensive Documentation**: Added error prevention patterns to developer guidelines.

---

## 🔧 Technical Details

### New Module: `utils/units.py`
- **UnitPreference class**: Validates and manages unit preferences
- **Conversion functions**:
  - `convert_altitude()`: feet ↔ meters
  - `convert_speed()`: knots ↔ kph
  - `convert_weight()`: pounds ↔ kilograms
- **Unit getters**: Return appropriate unit strings for display

### Configuration Flow Updates
- Added `unit_preference` dropdown to global settings
- Updated all sensors to accept and respect the global unit preference
- Fixed Home Assistant API pattern for config entry management

### Sensor Updates
All 14+ sensors now:
- Accept `global_settings` parameter during initialization
- Store `_unit_preference` from settings
- Set `_attr_native_unit_of_measurement` dynamically based on user preference
- Convert calculated values to user's preferred unit before returning

---

## 🐛 Bug Fixes

### Config Entry Property Error
- **Issue**: `AttributeError: property 'config_entry' of 'HangarOptionsFlowHandler' object has no setter`
- **Root Cause**: Attempted direct assignment to read-only Home Assistant property
- **Solution**: Store config entry as private `_config_entry` attribute
- **Status**: ✅ Resolved and tested

---

## 📊 Validation & Testing

### Pre-release Quality Checks
- ✅ **MyPy Type Checking**: 0 errors across 7 source files
- ✅ **Flake8 Linting**: All critical errors resolved
- ✅ **Unit Tests**: 231/231 tests passing
- ✅ **Backward Compatibility**: Existing configurations work unchanged

### Test Categories
- Unit conversion functions (27 tests)
- Sensor unit behavior (13 tests)
- Configuration flow initialization (10 tests)
- Config validation (31 tests)
- Enhanced logic scenarios (7 tests)
- Integration scenarios (2 tests)
- Error handling (17 tests)
- PDF generation (24 tests)
- Binary sensors (1 test)
- Services (10 tests)
- And more...

---

## 📝 Breaking Changes

**None**. This release is fully backward compatible:
- Existing installations continue to work without any configuration changes
- Unit preference defaults to aviation units (preserving current behavior)
- No database migrations required

---

## 🚀 Migration Guide

### For Existing Users
1. Update to version 2601.2.0
2. No action required—your installation will continue working with aviation units
3. *Optional*: Go to **Settings → Devices & Services → Hangar Assistant → Configure** and select "SI Units" if preferred

### For New Users
1. Install Hangar Assistant
2. Configure airfields and aircraft as before
3. In global settings, choose your preferred unit system (Aviation or SI)

---

## 📚 Developer Changes

### Error Detection & Prevention Patterns
The project now includes comprehensive documentation on:
- Using **MyPy** for static type checking (catches property assignment errors early)
- **Flake8** for syntax validation
- **Unit testing** with proper mocking
- **Home Assistant API patterns** to avoid common pitfalls
- **Pre-commit validation checklist**

See `.github/copilot-instructions.md` for details.

---

## 🔐 Security & Compliance
- No security changes in this release
- All data remains stored locally on Home Assistant
- No new external dependencies required

---

## 📦 Dependency Changes
None. Existing dependencies remain:
- `fpdf2==2.7.8`

---

## 🙏 Contributing
Found a bug or have a feature request? Please open an issue on [GitHub](https://github.com/fregster/ha-hangar-assistant/issues).

---

## ✅ Checklist for v2601.2.0
- [x] Unit preference system fully implemented
- [x] All sensors updated with unit conversion
- [x] Configuration flow updated with preference option
- [x] 231 unit tests passing
- [x] MyPy type checking passes
- [x] Flake8 linting clean
- [x] Backward compatibility verified
- [x] Documentation updated
- [x] GitHub CI/CD validation passing

---

**For detailed technical information, refer to the code changes in the repository.**
