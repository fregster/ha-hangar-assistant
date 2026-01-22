# Hangar Assistant v2601.2.0 Release Notes

**Release Date**: January 2026  
**Type**: Major Feature Release  
**Priority**: ⭐⭐⭐⭐⭐ HIGH

---

## Overview

Version 2601.2.0 is a comprehensive release consolidating three major feature sets into a single production-ready version:

1. **CheckWX Aviation Weather Integration** - Professional METAR/TAF data with official flight categories (FREE, 3000 req/day)
2. **External Integration Management System** - Centralized configuration with graceful degradation and health monitoring
3. **Global Unit Preference System** - Aviation or SI units throughout the integration

This release focuses on professional aviation weather data, robust external API management, improved reliability through graceful degradation, and enhanced user experience through flexible unit preferences.

---

## 🚀 Major Features

### 1. CheckWX Aviation Weather Integration

Professional aviation weather data from CheckWX, providing official METAR observations and TAF forecasts.

**Key Features:**
- ✅ **FREE Tier**: 3,000 requests/day (sufficient for home users with 1-5 airfields)
- ✅ **Official Aviation Format**: METAR/TAF standards used worldwide
- ✅ **Flight Categories**: Automatic VFR/MVFR/IFR/LIFR classification
- ✅ **Comprehensive Forecasts**: TAF terminal forecasts with change indicators
- ✅ **Station Information**: Auto-populate airfield data from ICAO codes
- ✅ **Multi-Level Caching**: Memory + persistent file-based caching protects rate limits
- ✅ **Graceful Degradation**: Uses stale cache when API unavailable

**New Sensors** (per airfield with ICAO code):
- `sensor.{airfield}_metar` - Current weather with flight category state
- `sensor.{airfield}_taf` - Terminal forecasts with validity periods
- `sensor.{airfield}_station_info` - Airport information and sunrise/sunset

### 2. Centralized Integration Management

All external integrations (OpenWeatherMap, NOTAMs, CheckWX) managed through unified menu.

**Key Features:**
- ✅ **Single Configuration Menu**: Access all integrations in one place
- ✅ **Auto-Disable Protection**: OWM automatically disables after 3 consecutive failures
- ✅ **Stale Cache Fallback**: NOTAM service uses old data during outages
- ✅ **Health Monitoring**: Binary sensors track integration status
- ✅ **Failure Tracking**: Consecutive failures, last error, last success timestamps
- ✅ **Automatic Migration**: Legacy settings automatically converted

**New Binary Sensors:**
- `binary_sensor.integration_health` - Overall integration health (healthy/warning/critical)
- `binary_sensor.notam_staleness_warning` - NOTAM cache freshness indicator

**Configuration Structure:**
```python
entry.data["integrations"] = {
    "openweathermap": {enabled, api_key, cache_enabled, intervals, failure_tracking},
    "notams": {enabled, update_time, cache_days, failure_tracking},
    "checkwx": {enabled, api_key, cache_settings}
}
```

### 3. Global Unit Preference System

Choose between aviation units or SI units for all sensors and calculations.

**Aviation Units** (default):
- Altitude: feet (ft)
- Speed: knots (kt)
- Weight: pounds (lbs)

**SI Units**:
- Altitude: meters (m)
- Speed: kilometers per hour (kph)
- Weight: kilograms (kg)

**Affected Sensors:**
- Density Altitude
- Estimated Cloud Base
- Carburetor Icing Risk Transition Altitude
- Runway Crosswind Components
- Calculated Ground Roll

**Configuration**: Available in integration's global settings via UI.

---

## 📊 CheckWX vs OpenWeatherMap

| Feature | CheckWX (Free) | OpenWeatherMap (Paid) |
|---------|----------------|----------------------|
| **Cost** | 100% FREE (3000 req/day) | ~$10-30/month |
| **Format** | Official aviation (METAR/TAF) | Consumer weather JSON |
| **Pilot Trust** | ✅ Industry standard | ⚠️ General purpose |
| **Flight Planning** | ✅ Required data | 🟡 Supplemental |
| **Forecasts** | TAF (9-30 hours, aviation) | 48h hourly + 8d daily |
| **Alerts** | ❌ Not included | ✅ Government alerts |
| **Best For** | VFR/IFR flight planning | Trend analysis, alerts |

**Recommendation:** Use both! CheckWX for official weather, OWM for forecasts/alerts.

---

## 🔧 Configuration & Setup

### CheckWX Setup

1. **Get Free API Key:**
   - Visit https://www.checkwxapi.com/signup
   - Create free account (no credit card required)
   - Copy API key from profile

2. **Configure in Hangar Assistant:**
   - Settings → Devices & Services → Hangar Assistant → Configure
   - Select "Manage Integrations"
   - Enable CheckWX and paste API key
   - Adjust cache settings (defaults recommended)

3. **Enable for Airfields:**
   - Each airfield must have an ICAO code configured
   - Sensors automatically created for airfields with ICAO codes

### Integration Management Menu

**Accessing:**
1. Settings → Devices & Services → Hangar Assistant
2. Click **Configure**
3. Select **Manage Integrations**

**Available Settings:**
- Enable/disable each integration
- Configure API credentials
- Set update intervals and cache TTLs
- Review failure tracking status

### Unit Preference

**Setting Your Preference:**
1. Settings → Devices & Services → Hangar Assistant → Configure
2. Select "General Settings"
3. Choose "Aviation Units" or "SI Units"
4. Restart Home Assistant (sensors update on next calculation)

---

## 🎯 Rate Limit Protection & Caching

### CheckWX Rate Limits
- **Free Tier:** 3,000 requests/day
- **Warning System:** Alerts at 2,700/3,000 (90%)
- **Daily Reset:** 00:00 UTC

**Typical Usage** (per airfield, per day):
- METAR: ~48 requests (every 30 min)
- TAF: ~4 requests (every 6 hours)
- Station: ~0.14 requests (every 7 days)
- **Total for 3 airfields:** ~156 requests/day (95% under limit)

### OpenWeatherMap Protection
- **Auto-Disable:** After 3 consecutive failures (401/429/timeout)
- **Manual Re-Enable:** Via Integrations menu after fixing issue
- **Persistent Cache:** Survives restarts to prevent quota breaches
- **Warning Threshold:** 950/1000 daily calls

### NOTAM Graceful Degradation
- **Stale Cache Fallback:** Uses old data indefinitely during outages
- **Staleness Warning:** Binary sensor alerts when cache > 24 hours old
- **Daily Updates:** Scheduled at configured time (default: 02:00)
- **Cache Retention:** Configurable 1-30 days (default: 7)

---

## 🔒 Security & Privacy

- ✅ API keys stored securely (Home Assistant password fields)
- ✅ Keys never logged (sanitized in all log output)
- ✅ Async file operations (non-blocking I/O)
- ✅ Input validation (ICAO codes, API responses, file paths)
- ✅ Error handling (graceful degradation, no crashes)
- ✅ Persistent notifications for critical failures

---

## 📈 Performance Optimizations

- **CheckWX Caching:** 40-60% faster on cache hits
- **LRU Eviction:** Prevents memory bloat (100-1000 entry limits)
- **Persistent Cache:** Eliminates API calls during restarts
- **orjson Support:** 2-5x faster JSON parsing (if installed)
- **Sensor State Caching:** 60-second TTL for expensive calculations
- **Template Caching:** Dashboard template loaded once with mtime checks

---

## 🧪 Testing

**Comprehensive test coverage:**
- ✅ 280+ test cases across all features
- ✅ CheckWX client tests (25+ scenarios)
- ✅ Integration management tests (46+ scenarios)
- ✅ Unit preference tests (15+ scenarios)
- ✅ Cache hit/miss, LRU eviction, rate limiting
- ✅ Failure tracking and auto-disable behavior
- ✅ Migration from legacy settings structure
- ✅ Type checking (mypy) - 0 errors
- ✅ Linting (flake8) - 0 critical issues
- ✅ Zero warnings in test suite

---

## 🔄 Backward Compatibility

**100% backward compatible** - no breaking changes!

- ✅ CheckWX is opt-in (disabled by default)
- ✅ Integration management automatically migrates settings
- ✅ Unit preference defaults to aviation units (existing behavior)
- ✅ All existing sensors unchanged
- ✅ Config flow preserves existing settings
- ✅ No manual intervention required

**Automatic Migration:**
- Settings migrated from `entry.data["settings"]` to `entry.data["integrations"]`
- OpenWeatherMap settings preserved exactly
- NOTAM configuration added with defaults
- Failure tracking fields initialized
- Airfield/aircraft/hangar data untouched

---

## 🐛 Bug Fixes

### Fixed Issues

1. **Config Entry Property Error**:
   - **Issue**: `AttributeError: property 'config_entry' of 'HangarOptionsFlowHandler' object has no setter`
   - **Root Cause**: Attempted direct assignment to read-only Home Assistant property
   - **Solution**: Store config entry as private `_config_entry` attribute
   - **Status**: ✅ Resolved and tested

2. **OWM Rate Limit Breaches on Restart**:
   - **Issue**: Home Assistant restarts triggered API calls, wasting quota
   - **Fix**: Persistent cache now survives restarts, no API calls until cache expires
   - **Impact**: Protects API quota during frequent restarts/reloads

3. **NOTAM Service Outages Breaking Sensors**:
   - **Issue**: NOTAM XML fetch failures caused sensors to show unavailable
   - **Fix**: Stale cache fallback keeps sensors working with old data
   - **Impact**: Uninterrupted service even during UK NATS downtime

4. **Scattered Integration Settings**:
   - **Issue**: OWM settings spread across multiple menus
   - **Fix**: Centralized integration menu for all external data sources
   - **Impact**: Clearer organization, easier configuration

---

## 📚 Documentation

### User-Facing Documentation
- **Integration Management Guide**: `docs/features/integrations_management.md`
- **CheckWX Integration**: `docs/features/checkwx_integration.md`
- **Setup Wizard**: `docs/features/setup_wizard.md` (CheckWX section added)
- **Unit Preferences**: Section added to README.md
- **Translations**: English, German, Spanish, French (complete)

### Developer Documentation
- **CheckWX Planning**: `docs/implemented/checkwx_integration_plan.md`
- **Integration Architecture**: `docs/development/INTEGRATION_ARCHITECTURE.md`
- **API Clients**: Fully documented in `utils/` directory
- **Test Suites**: Comprehensive docstrings in all test files

---

## 🚀 Upgrade Instructions

### HACS Users
1. Open HACS → Integrations → Hangar Assistant
2. Click **Update** when v2601.2.0 appears
3. Restart Home Assistant
4. Verify migration completed (check logs)

### Manual Install Users
1. Download v2601.2.0 from GitHub releases
2. Replace `custom_components/hangar_assistant/` directory
3. Restart Home Assistant
4. Verify migration completed (check logs)

### Post-Upgrade Actions

**Required:**
- None! Migration is fully automatic.

**Recommended:**
1. Review **Manage Integrations** menu to verify settings migrated correctly
2. Add `binary_sensor.integration_health` to main dashboard
3. Add `binary_sensor.notam_staleness_warning` to pre-flight view
4. Optionally configure CheckWX for official aviation weather
5. Test OWM/NOTAM/CheckWX connections to verify functionality
6. Set up automation for integration failure notifications (optional)

---

## 🔮 Future Enhancements

### Planned for v2601.3.0+ (Q1 2026)

1. **ADS-B Aircraft Tracking** (Phase 1):
   - dump1090 local receiver support
   - OpenSky Network integration (free)
   - Open Gliding Network (FLARM support)
   - Device tracker entities per aircraft
   - Traffic sensors per airfield

2. **ATIS Integration**:
   - Airport information service
   - D-ATIS support for UK airfields
   - Automated briefing updates

3. **Integration Templates**:
   - Pre-configured setups for common scenarios
   - "UK PPL Standard" template
   - "US Sport Pilot" template
   - "Glider Pilot" template

---

## 🙏 Acknowledgments

- **CheckWX API**: Excellent free aviation weather service
- **OpenWeatherMap**: Comprehensive weather API documentation
- **UK NATS**: Public PIB XML feed access for NOTAMs
- **Home Assistant Community**: Integration patterns and best practices
- **Community Feedback**: Pilots who requested official aviation weather format
- **Early Testers**: Beta testers who validated implementations

---

## 📝 Complete Changelog

### Added
- CheckWX API client with multi-level caching (`utils/checkwx_client.py`)
- `MetarSensor` for current weather observations
- `TafSensor` for terminal aerodrome forecasts
- `StationInfoSensor` for airport information
- Centralized integration management menu
- `IntegrationHealthSensor` binary sensor for overall health
- `NOTAMStalenessWarning` binary sensor for cache freshness
- OpenWeatherMap auto-disable after 3 consecutive failures
- NOTAM stale cache fallback for graceful degradation
- Global unit preference system (`utils/units.py`)
- Unit conversion functions (altitude, speed, weight)
- Automatic migration from legacy settings structure
- Comprehensive test suites (280+ tests total)
- User-facing documentation for all features
- Translation support (English, German, Spanish, French)

### Changed
- `async_setup_entry()` in `sensor.py` to register CheckWX sensors
- `async_setup_entry()` in `binary_sensor.py` to register health sensors
- Config flow to include integration management menu
- Config flow to support CheckWX API setup
- All sensors to respect global unit preference
- Dashboard templates to display METAR/TAF data
- AI briefing templates to include CheckWX data
- Config entry structure from `settings` to `integrations` namespace

### Fixed
- Config entry property assignment error in OptionsFlowHandler
- OWM rate limit breaches on Home Assistant restart
- NOTAM sensor unavailability during service outages
- Scattered integration settings across multiple menus
- Type checking errors (mypy now passes with 0 errors)

### Security
- API keys never logged (sanitized in all outputs)
- Async file operations for persistent cache (non-blocking)
- Input validation for ICAO codes, file paths, and API responses
- Persistent notifications for critical integration failures

### Performance
- Multi-level caching reduces API calls by 40-60%
- LRU eviction prevents memory bloat
- orjson support for 2-5x faster JSON parsing
- Persistent cache eliminates restart-induced API calls
- Sensor state caching with 60-second TTL
- Template caching with mtime checks (40-60% speedup)

---

## ✅ Upgrade Checklist

Before upgrading:
- [ ] Backup Home Assistant configuration
- [ ] Note current API keys (OWM, CheckWX if configured)
- [ ] Review current integration settings
- [ ] Check available disk space for cache files

After upgrading:
- [ ] Verify migration completed (check logs for success message)
- [ ] Review **Manage Integrations** menu (Settings → HA → Configure)
- [ ] Add health sensors to dashboard
- [ ] Test OWM connection (if configured)
- [ ] Test NOTAM updates working
- [ ] Optionally configure CheckWX (free tier)
- [ ] Set up failure notification automation (optional)

---

## 📖 Version Information

**Version**: v2601.2.0  
**Release Date**: January 2026  
**Minimum HA Version**: 2024.1.0  
**Python Version**: 3.11+  
**Dependencies**: fpdf2 (unchanged)

**Previous Version**: v2601.1.2 (Unit preferences, code quality)  
**Next Version**: v2601.3.0 (ADS-B tracking Phase 1, planned Q1 2026)

---

## 📝 Support & Feedback

### Getting Help

1. **Documentation**: Start with feature-specific docs in `docs/features/`
2. **FAQ**: Check FAQ sections in feature documentation
3. **Logs**: Enable debug logging for detailed diagnostics
4. **GitHub Issues**: Report bugs with logs and config details
5. **Discussions**: Ask questions in GitHub Discussions

### Reporting Issues

Include in bug reports:
- Hangar Assistant version (v2601.2.0)
- Home Assistant version
- Relevant log snippets (sanitize API keys!)
- Integration health sensor attributes
- Steps to reproduce

### Feature Requests

Use GitHub Discussions → Ideas category for:
- New integration suggestions
- Configuration improvements
- Automation templates
- Documentation enhancements

---

**Thank you for using Hangar Assistant! Safe flying. ✈️**

**Full Release**: https://github.com/prefixfelix/hangar-assistant/releases/tag/v2601.2.0
