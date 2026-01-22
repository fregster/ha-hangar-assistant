# Integration Management

**Feature**: Centralized External Integration Management  
**Version**: 1.0 (v2601.2.0)  
**Status**: ✅ Available

## Overview

The Integration Management feature provides a centralized menu for managing all external data sources (APIs, XML feeds, etc.) used by Hangar Assistant. Instead of scattering settings across different menus, all integrations are managed in one place with consistent configuration patterns.

**Key Benefits:**
- **Single Configuration Menu**: Manage OpenWeatherMap, NOTAMs, and future integrations from one location
- **Graceful Degradation**: Integrations fail gracefully without breaking core functionality
- **Health Monitoring**: Binary sensors track integration status and alert you to issues
- **Automatic Recovery**: Free services (NOTAMs) recover automatically; paid APIs (OWM) require manual re-enable after fixing issues

**When to Use:**
- Setting up OpenWeatherMap professional weather data
- Enabling/disabling NOTAM updates
- Troubleshooting integration failures
- Monitoring external data freshness

## Getting Started

### Prerequisites
- Hangar Assistant v2601.2.0 or later
- (Optional) OpenWeatherMap API key for professional weather data
- Internet connection for external data sources

### Accessing Integration Settings

1. Navigate to **Settings** → **Devices & Services** in Home Assistant
2. Find **Hangar Assistant** in your integrations list
3. Click **Configure**
4. Select **Manage Integrations** from the menu

You'll see a list of available integrations with current status indicators.

## Managing Integrations

### OpenWeatherMap (Optional, Paid API)

OpenWeatherMap provides professional weather data including forecasts, alerts, and minute-by-minute precipitation timing.

**Configuration Options:**
- **API Key**: Your OpenWeatherMap One Call API 3.0 key (password field)
- **Enable/Disable**: Master toggle for the integration
- **Update Interval**: Minutes between API calls (default: 10, range: 5-60)
- **Cache TTL**: Minutes cache remains valid (default: 10, range: 5-60)
- **Enable Caching**: Persistent cache to protect against API limit breaches (recommended: ON)

**Auto-Disable Behavior:**

To protect your API quota, OpenWeatherMap auto-disables after 3 consecutive failures:

1. **First Failure** (Warning): Logged, counter incremented, cached data used
2. **Second Failure** (Warning): Logged, counter incremented, cached data used
3. **Third Failure** (Critical): Integration auto-disabled, persistent notification created

**When auto-disabled:**
- Sensors continue using cached data (if available)
- No further API calls until you manually re-enable
- Persistent notification appears with recovery instructions

**Recovery Steps:**
1. Check your API key validity at [openweathermap.org](https://openweathermap.org/api)
2. Verify your account status (subscription active, quota available)
3. Fix any issues (renew subscription, regenerate key, etc.)
4. Return to **Manage Integrations** → **OpenWeatherMap**
5. Click **Re-enable** or toggle the Enable switch
6. Integration resets failure counter and resumes normal operation

**Rate Limit Protection:**
- Multi-level caching (memory + persistent file)
- Persistent cache survives Home Assistant restarts
- Warns at 950/1000 daily API calls
- Update interval configurable to control quota usage

### NOTAMs (Free Service)

NOTAM (Notice to Airmen) integration provides aviation safety alerts from the UK NATS PIB XML feed.

**Configuration Options:**
- **Enable/Disable**: Master toggle (default: enabled for new installs)
- **Update Time**: Daily update time in HH:MM format (default: 02:00)
- **Cache Retention**: Days to retain cached NOTAMs (default: 7, range: 1-30)

**Stale Cache Fallback:**

NOTAMs use graceful degradation - if updates fail, stale cache is used indefinitely:

1. **Fresh Data (<24 hours)**: Normal operation, no warnings
2. **Stale Data (24-48 hours)**: Used without warning (slight staleness acceptable)
3. **Very Stale (>48 hours)**: Binary sensor warning triggered, stale data still used
4. **Never Updated**: Binary sensor warning triggered, empty NOTAM list returned

**Why No Auto-Disable?**

Unlike paid APIs, NOTAMs never auto-disable because:
- Free service with no quota limits
- Stale NOTAM data is better than no data
- Integration keeps trying to recover automatically
- User doesn't need to take action

**Recovery:**
- Automatic on next scheduled update
- Network issues resolve themselves
- No manual intervention required
- If issues persist, check UK NATS PIB feed status

## Health Monitoring

Two binary sensors monitor integration health and alert you to issues.

### Integration Health Sensor

**Entity ID**: `binary_sensor.integration_health`  
**Device Class**: `problem`  
**States**:
- **OFF (Healthy)**: All integrations working normally
- **ON (Problem)**: One or more integrations has failures

**Attributes:**
- `severity`: healthy, warning, or critical
- `owm_failures`: OpenWeatherMap consecutive failure count
- `owm_enabled`: OWM integration status
- `owm_last_error`: Last error message from OWM
- `owm_last_success`: Timestamp of last successful OWM update
- `notam_failures`: NOTAM consecutive failure count
- `notam_enabled`: NOTAM integration status
- `notam_last_error`: Last error message from NOTAMs
- `notam_last_success`: Timestamp of last successful NOTAM update
- `disabled_integrations`: List of auto-disabled integrations

**Severity Levels:**
- **Healthy**: All integrations working, no failures
- **Warning**: 1-2 consecutive failures, still trying
- **Critical**: 3+ consecutive failures, OWM auto-disabled

**Use Cases:**
- Dashboard health indicator
- Automation trigger for notifications
- Debugging integration issues

**Example Automation:**
```yaml
automation:
  - alias: "Hangar: Alert on Integration Failure"
    trigger:
      - platform: state
        entity_id: binary_sensor.integration_health
        to: "on"
    condition:
      - condition: template
        value_template: "{{ state_attr('binary_sensor.integration_health', 'severity') == 'critical' }}"
    action:
      - service: notify.mobile_app
        data:
          message: "Hangar Assistant integration failure: {{ state_attr('binary_sensor.integration_health', 'disabled_integrations') }}"
```

### NOTAM Staleness Warning

**Entity ID**: `binary_sensor.notam_staleness_warning`  
**Device Class**: `problem`  
**States**:
- **OFF (Fresh)**: NOTAM data updated within 48 hours
- **ON (Stale)**: NOTAM data >48 hours old or never updated

**Attributes:**
- `status`: fresh, stale, never_updated, or disabled
- `cache_age_hours`: Hours since last successful NOTAM update
- `threshold_hours`: Staleness threshold (48 hours)
- `last_update`: ISO timestamp of last successful update

**Use Cases:**
- Monitor NOTAM data freshness
- Alert before planned flights if data is stale
- Dashboard indicator for data reliability

**Example Dashboard Card:**
```yaml
type: entity
entity: binary_sensor.notam_staleness_warning
name: NOTAM Data Status
icon: mdi:alert-circle
state_color: true
```

## Troubleshooting

### OpenWeatherMap Issues

#### Problem: OWM Auto-Disabled After 3 Failures
**Symptoms**: Persistent notification, weather forecast sensors show unavailable  
**Solution**:
1. Check persistent notification for specific error (401, 429, timeout)
2. Verify API key at [openweathermap.org](https://openweathermap.org/api)
3. Check subscription status (active, quota available)
4. If 401 Unauthorized: Regenerate API key, update in Integration settings
5. If 429 Rate Limit: Wait until daily quota resets (midnight UTC)
6. If timeout: Check network connectivity
7. Re-enable integration in **Manage Integrations** → **OpenWeatherMap**

#### Problem: Weather Sensors Show Stale Data
**Symptoms**: Sensors update infrequently, timestamps don't change  
**Solution**:
1. Check `binary_sensor.integration_health` state and attributes
2. Review `owm_last_success` timestamp in attributes
3. If recent success but stale data: Increase update interval (Settings → OpenWeatherMap)
4. If no recent success: Follow auto-disable recovery steps above
5. Check Home Assistant logs for detailed error messages

#### Problem: Rate Limit Warnings in Logs
**Symptoms**: Log messages about approaching API limit (950/1000 calls)  
**Solution**:
1. Reduce update interval (e.g., 10 → 15 minutes)
2. Reduce number of airfields using OWM (use sensors mode for some)
3. Disable OWM for airfields you visit less frequently
4. Verify no duplicate API calls (only one integration should use key)
5. Consider upgrading OWM plan for higher quota

### NOTAM Issues

#### Problem: NOTAM Staleness Warning Triggered
**Symptoms**: `binary_sensor.notam_staleness_warning` turns ON  
**Solution**:
1. Check `cache_age_hours` attribute to see how stale data is
2. If >48 hours: Wait for next scheduled update (check `update_time` setting)
3. If continues: Check UK NATS PIB feed status ([pibs.nats.co.uk](https://pibs.nats.co.uk/operational/pibs/PIB.xml))
4. If feed accessible but updates fail: Check Home Assistant logs for errors
5. If feed down: Use stale cache until service recovers (automatic)

#### Problem: No NOTAMs Ever Retrieved
**Symptoms**: NOTAM sensors show empty list, `status` attribute is "never_updated"  
**Solution**:
1. Verify NOTAM integration is enabled (Settings → Manage Integrations → NOTAMs)
2. Check Home Assistant logs for XML parsing errors
3. Test UK NATS PIB feed accessibility manually
4. Verify network connectivity from Home Assistant host
5. Check firewall rules (allow HTTPS to pibs.nats.co.uk)
6. Restart Home Assistant to trigger fresh fetch attempt

#### Problem: NOTAMs Not Updating Daily
**Symptoms**: `cache_age_hours` grows beyond 24-48 hours  
**Solution**:
1. Check `update_time` setting (default: 02:00)
2. Verify Home Assistant was running at update time
3. Check logs for scheduled update errors
4. Manually restart integration to force update
5. If persistent: Disable and re-enable NOTAM integration

### General Integration Issues

#### Problem: Integration Settings Not Saving
**Symptoms**: Changes revert after reopening config flow  
**Solution**:
1. Complete the entire config flow before closing
2. Don't use browser back button during configuration
3. Check Home Assistant logs for config entry update errors
4. Restart Home Assistant and try again
5. If persistent: Report bug with logs

#### Problem: Health Sensors Not Appearing
**Symptoms**: `binary_sensor.integration_health` doesn't exist  
**Solution**:
1. Verify Hangar Assistant v2601.2.0 or later
2. Reload integration (Settings → Devices & Services → Hangar Assistant → Reload)
3. Check that integrations namespace exists in config (Developer Tools → States)
4. If missing: Restart Home Assistant to trigger migration
5. If still missing: Report bug with version info

## FAQ

### How do I know if my OpenWeatherMap API key is valid?
Check `binary_sensor.integration_health` attributes - `owm_last_error` will show "401 Unauthorized" if key is invalid. Test at [openweathermap.org/api](https://openweathermap.org/api).

### Can I use Hangar Assistant without any external integrations?
Yes! All core sensors work with Home Assistant's built-in sensors. OWM and NOTAMs are optional enhancements.

### What happens during Home Assistant restarts?
Persistent cache prevents API calls during restarts. Integrations use cached data until next scheduled update. No API quota wasted.

### How often do integrations update?
- **OWM**: Configurable (default: every 10 minutes)
- **NOTAMs**: Daily at configured time (default: 02:00)

### Does auto-disable delete my API key?
No - auto-disable only prevents API calls. Your API key is preserved. Re-enabling resumes operation immediately.

### Can I temporarily disable an integration without losing settings?
Yes - toggle the "Enable" switch in **Manage Integrations**. Settings are preserved, no API calls made when disabled.

### What's the difference between disabling and auto-disable?
- **Manual disable**: You chose to turn off, can re-enable anytime
- **Auto-disable**: System protection after 3 failures, requires manual re-enable after fixing issue

### How do I test if integrations are working?
Check `binary_sensor.integration_health` state and attributes. OFF = healthy. Review `last_success` timestamps to confirm recent updates.

### Can I use multiple OpenWeatherMap API keys?
No - one API key per Hangar Assistant installation. To monitor multiple locations, add them as airfields and configure each to use OWM.

### What happens to forecast sensors when OWM is disabled?
They show "unavailable" state. Dashboard cards gracefully hide unavailable entities. Re-enabling OWM restores forecasts.

## Best Practices

### For Student Pilots
- **Start with defaults**: Use free NOTAMs initially, add OWM later if needed
- **Monitor health sensor**: Add to main dashboard to catch issues early
- **Check before flights**: Review NOTAM staleness warning before planning

### For Private Pilots
- **Enable OWM for home field**: Use professional weather where you fly most
- **Use sensor mode for others**: Save API quota for less-visited airfields
- **Set up notifications**: Automate alerts for integration failures
- **Review monthly quota**: Check OWM usage to optimize update intervals

### For Instructors/Commercial Users
- **Premium OWM plan**: Higher quota for multiple airfields
- **Strict monitoring**: Use health sensors in automations
- **Redundancy**: Configure hybrid mode (OWM + sensors) for reliability
- **Regular audits**: Weekly review of integration health logs

### For All Users
- **Enable caching**: Always keep OWM cache enabled to protect quota
- **Reasonable update intervals**: Don't set below 10 minutes unless necessary
- **Monitor health sensors**: Add to dashboard for visibility
- **Check before updates**: Review integration status before HA updates
- **Document API keys**: Store OWM key securely outside of HA (password manager)

## Technical Details (Advanced)

<details>
<summary>Click to expand</summary>

### Configuration Structure

Integrations are stored in `entry.data["integrations"]` namespace:

```python
{
    "integrations": {
        "openweathermap": {
            "enabled": bool,
            "api_key": str,  # password field
            "cache_enabled": bool,
            "update_interval": int,  # minutes
            "cache_ttl": int,  # minutes
            "consecutive_failures": int,
            "last_error": str,  # optional
            "last_success": str,  # ISO timestamp, optional
        },
        "notams": {
            "enabled": bool,
            "update_time": str,  # "HH:MM" format
            "cache_days": int,
            "consecutive_failures": int,
            "last_error": str,  # optional
            "last_success": str,  # ISO timestamp, optional
        }
    }
}
```

### Migration from Legacy Settings

Existing installations automatically migrate from `entry.data["settings"]` to `entry.data["integrations"]` on first load of v2601.2.0:

1. OWM settings moved from `settings.openweathermap_*` to `integrations.openweathermap.*`
2. NOTAM config added with defaults:
   - **Existing installs**: `enabled=False` (opt-in)
   - **New installs**: `enabled=True` (out-of-box experience)
3. Failure tracking fields initialized (`consecutive_failures=0`)
4. Migration logged for debugging

Migration is idempotent (safe to run multiple times).

### Client Architecture

Each integration has a dedicated client class:
- `custom_components/hangar_assistant/utils/openweathermap.py`: OWM client
- `custom_components/hangar_assistant/utils/notam.py`: NOTAM client

Clients handle:
- API calls with error handling
- Multi-level caching (memory + persistent)
- Failure tracking and auto-disable logic
- Persistent notification creation
- Graceful degradation

### Health Sensor Implementation

Health sensors in `binary_sensor.py`:
- `IntegrationHealthSensor`: Monitors all integrations
- `NOTAMStalenessWarning`: Tracks NOTAM data age

Update mechanism:
- Polled every 60 seconds (Home Assistant default)
- Read from `config_entry.data["integrations"]`
- No external API calls (reads tracking data only)

### Cache Locations

Persistent caches stored in:
- **OWM**: `<config_dir>/hangar_assistant_cache/owm_<lat>_<lon>.json`
- **NOTAM**: `<config_dir>/hangar_assistant_cache/notams.json`

Cache structure:
```json
{
    "cached_at": "2026-01-22T10:30:00Z",
    "data": { ... }
}
```

### Customization Options

Advanced users can modify cache behavior via `customize.yaml`:
```yaml
# Adjust health sensor update frequency
binary_sensor.integration_health:
  scan_interval: 30  # seconds (default: 60)

binary_sensor.notam_staleness_warning:
  scan_interval: 300  # seconds (default: 60)
```

</details>

## Related Documentation

- **[OpenWeatherMap Integration](openweathermap_integration.md)**: Detailed OWM feature guide
- **[NOTAM Integration](notam_integration.md)**: Detailed NOTAM feature guide
- **[Setup Wizard](setup_wizard.md)**: Initial integration configuration
- **[Dashboard Guide](glass_cockpit_dashboard.md)**: Adding health sensors to dashboard

## Version History

### v1.0 (v2601.2.0) - 22 January 2026
- Initial release of centralized integration management
- OpenWeatherMap auto-disable on 3 consecutive failures
- NOTAM stale cache fallback (graceful degradation)
- Integration health monitoring sensors
- Automatic migration from legacy settings namespace
- Comprehensive failure tracking and user notifications

### Planned Enhancements
- CheckWX integration (weather station data)
- METAR/TAF integration (aviation weather reports)
- ATIS integration (airport information service)
- Integration templates for common setups
- Advanced automation examples
