# NOTAM Integration

**Feature**: UK NATS Notice to Airmen (NOTAM) Integration  
**Version**: 1.0 (v2601.1.0)  
**Status**: ✅ Available (Free Service)

---

## Overview

The NOTAM Integration provides automatic access to UK NATS Aeronautical Information Service Notice to Airmen (NOTAM) data. NOTAMs are critical operational notices about airspace restrictions, runway closures, navigation aid outages, and other safety-critical information that pilots must review before flight.

**Before this integration**, pilots had to manually visit the UK NATS website, manually parse dense text-based NOTAMs, and cross-reference multiple sources during pre-flight planning.

**With this integration**, NOTAMs are automatically fetched daily, parsed into structured data, filtered by location, and presented in your dashboard with critical safety information highlighted.

---

## Key Benefits

✅ **Completely Free** - No API key required, UK NATS provides public access  
✅ **Automatic Updates** - Daily scheduled updates at 02:00  
✅ **Location Filtering** - Filter by ICAO code or geographic radius  
✅ **Graceful Degradation** - Uses stale cache indefinitely during network issues  
✅ **Persistent Cache** - Survives Home Assistant restarts  
✅ **Safety Integration** - NOTAMs appear in AI briefings and dashboard alerts  

---

## How It Works

### Data Source

The integration connects to the **UK NATS Pre-flight Information Bulletin (PIB)** XML feed:
- **URL**: https://pibs.nats.co.uk/operational/pibs/PIB.xml
- **Coverage**: UK airspace and airfields (EGXX ICAO codes)
- **Update Frequency**: UK NATS updates continuously; integration fetches daily
- **Format**: XML parsed into structured JSON

### Automatic Scheduling

The integration automatically:
1. **Schedules daily updates** at 02:00 (configurable via Settings)
2. **Fetches latest NOTAMs** from UK NATS PIB XML feed
3. **Parses XML** into structured data (ID, location, dates, text, Q-codes)
4. **Caches locally** with 7-day retention (configurable 1-30 days)
5. **Creates sensors** for each configured airfield with filtered NOTAMs

### Location Filtering

NOTAMs can be filtered by:
- **ICAO Code**: Exact match (e.g., "EGHP" for Popham)
- **Geographic Radius**: All NOTAMs within X nautical miles of airfield coordinates
- **Q-Code Categories**: Filter by type (aerodrome, airspace, navigation, etc.)

---

## NOTAM Data Structure

Each NOTAM contains:

| Field | Description | Example |
|-------|-------------|---------|
| `id` | NOTAM identifier | "A0123/25" |
| `location` | ICAO code | "EGHP" |
| `category` | Type of NOTAM | "AERODROME", "AIRSPACE", "NAVIGATION" |
| `start_time` | Effective date/time (ISO) | "2026-01-22T08:00:00Z" |
| `end_time` | Expiry date/time (ISO) | "2026-02-22T17:00:00Z" |
| `text` | Human-readable text | "RWY 03/21 CLOSED FOR MAINTENANCE" |
| `q_code` | Q-code classification | "QMRLC" (Runway closed) |
| `latitude` | Decimal degrees (if applicable) | 51.2471 |
| `longitude` | Decimal degrees (if applicable) | -1.2344 |

---

## Configuration

### Global Settings

**Path**: Settings → Integrations → Hangar Assistant → Configure → Integrations → NOTAMs

| Setting | Description | Default | Options |
|---------|-------------|---------|---------|
| **Enabled** | Master toggle | `True` (auto-enabled) | True/False |
| **Update Time** | Daily update schedule | `02:00` | HH:MM format |
| **Cache Days** | Cache retention period | `7` | 1-30 days |

### Per-Airfield Settings

NOTAMs are automatically filtered for each configured airfield based on:
- **ICAO Code**: Exact match for airfield-specific NOTAMs
- **Coordinates**: Geographic filtering with 50nm radius (default)
- **Radius** (optional): Customize search radius (5-200nm)

---

## Entities Created

### NOTAM Sensor

**Entity ID**: `sensor.{airfield_slug}_notams`

**State**: Count of active NOTAMs affecting the airfield

**Attributes**:
- `notams`: List of NOTAM dictionaries (full structured data)
- `critical_count`: Count of critical NOTAMs (runway closures, airspace restrictions)
- `last_updated`: Timestamp of last successful fetch
- `cache_age_hours`: Age of cached data
- `is_stale`: Boolean indicating if cache is expired
- `source`: "live" or "stale_cache"

**Example State**:
```yaml
state: 3
attributes:
  notams:
    - id: "A0123/25"
      location: "EGHP"
      category: "AERODROME"
      start_time: "2026-01-22T08:00:00Z"
      end_time: "2026-02-22T17:00:00Z"
      text: "RWY 03/21 CLOSED FOR MAINTENANCE"
      q_code: "QMRLC"
    - id: "A0124/25"
      location: "EGHP"
      category: "NAVIGATION"
      start_time: "2026-01-20T00:00:00Z"
      end_time: "2026-03-20T23:59:59Z"
      text: "NDB POH U/S"
      q_code: "QNBXX"
  critical_count: 1
  last_updated: "2026-01-22T02:00:15Z"
  cache_age_hours: 6.5
  is_stale: false
  source: "live"
```

### NOTAM Warning Binary Sensor (Optional)

**Entity ID**: `binary_sensor.{airfield_slug}_notam_stale_data`

**State**: 
- `On` (Warning) - Using stale cache due to fetch failures
- `Off` (OK) - Fresh data or acceptable cache age

**Device Class**: `problem`

**Attributes**:
- `consecutive_failures`: Count of failed fetch attempts
- `last_error`: Most recent error message
- `last_success`: Timestamp of last successful fetch

---

## Caching Strategy

### Why Caching Matters

NOTAMs change infrequently (hours to days), but are critical for flight safety. The integration prioritizes:
1. **Availability over freshness**: Better to have 24-hour-old NOTAMs than none
2. **Restart protection**: Cache survives HA restarts to prevent data loss
3. **Network resilience**: Continues working during internet outages

### Cache Behavior

| Scenario | Behavior |
|----------|----------|
| **Fresh data available** | Use live data, update cache |
| **Cache < 24 hours old** | Use cache, skip fetch |
| **Cache > 24 hours old** | Attempt fetch, use stale cache if fails |
| **Fetch fails 3+ times** | Create warning sensor, keep trying |
| **Network down indefinitely** | Use stale cache forever, warn user |

### Cache Location

**File**: `<config_dir>/hangar_assistant_cache/notams.json`

**Structure**:
```json
{
  "timestamp": "2026-01-22T02:00:15Z",
  "notams": [
    { "id": "A0123/25", "location": "EGHP", ... }
  ]
}
```

---

## Use Cases

### Dashboard Display

Display active NOTAMs on your Glass Cockpit dashboard:

```yaml
type: entities
title: Active NOTAMs - Popham
entities:
  - entity: sensor.popham_notams
    type: attribute
    attribute: notams
    name: Active Notices
```

### Critical NOTAM Alert

Trigger notification when critical NOTAMs appear:

```yaml
automation:
  - alias: "Critical NOTAM Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.popham_notams
        attribute: critical_count
        above: 0
    action:
      - service: notify.mobile_app
        data:
          title: "⚠️ Critical NOTAM"
          message: "{{ states.sensor.popham_notams.attributes.notams[0].text }}"
```

### Pre-Flight Briefing

NOTAMs automatically appear in AI-generated briefings:

```yaml
automation:
  - alias: "Morning Pre-Flight Briefing"
    trigger:
      - platform: time
        at: "06:00:00"
    action:
      - service: hangar_assistant.refresh_ai_briefings
      - service: hangar_assistant.speak_briefing
        data:
          tts_entity_id: tts.cloud
```

AI briefing includes:
- Count of active NOTAMs
- Critical NOTAMs highlighted
- Runway/airspace restrictions
- Navigation aid status

---

## Troubleshooting

### NOTAMs Not Appearing

**Symptoms**: NOTAM sensor shows 0 NOTAMs despite expecting some

**Causes**:
1. ICAO code not in UK NATS database (non-UK airfield)
2. No NOTAMs currently active for the airfield
3. Geographic filtering too restrictive (radius too small)

**Solutions**:
- Verify airfield ICAO code is correct (must be EGXX for UK)
- Check UK NATS PIB website directly: https://pibs.nats.co.uk/
- Increase search radius in airfield settings (default: 50nm)
- Check logs for XML parsing errors: `grep notam home-assistant.log`

### Stale Data Warning

**Symptoms**: `binary_sensor.{airfield}_notam_stale_data` is `On`

**Causes**:
1. Network connectivity issues
2. UK NATS PIB website temporarily unavailable
3. XML format changed (rare)
4. Firewall blocking HTTPS requests

**Solutions**:
- Check internet connectivity from Home Assistant host
- Test URL manually: `curl https://pibs.nats.co.uk/operational/pibs/PIB.xml`
- Check Home Assistant logs for error details
- Wait 24 hours - service will retry automatically
- Verify firewall allows outbound HTTPS to *.nats.co.uk

### XML Parsing Errors

**Symptoms**: Logs show "Failed to parse NOTAM XML"

**Causes**:
1. UK NATS changed XML schema (rare but possible)
2. Corrupted download (partial file)
3. Invalid XML characters in NOTAM text

**Solutions**:
- Check GitHub issues for known XML format changes
- Clear cache: Delete `<config_dir>/hangar_assistant_cache/notams.json`
- Wait for next scheduled update (02:00 next day)
- File bug report with XML sample if persistent

### Integration Disabled After Update

**Symptoms**: NOTAMs stop appearing after HA or integration update

**Causes**:
1. Integration settings migrated but NOTAMs not re-enabled
2. Configuration entry corrupted during update

**Solutions**:
- Go to Settings → Integrations → Hangar Assistant → Configure → Integrations
- Verify "NOTAMs Enabled" is checked
- Click Save to force re-initialization
- Restart Home Assistant if toggle not visible

---

## FAQ

### Is this service free?

**Yes!** UK NATS provides the PIB XML feed as a free public service for aviation safety. No API key, registration, or payment required.

### Does it work outside the UK?

**Partially.** The UK NATS PIB only covers UK airspace (EGXX ICAO codes). For international NOTAMs:
- **EU**: Use your country's AIS provider (many have XML feeds)
- **US**: FAA provides NOTAM API (requires implementation)
- **Worldwide**: ICAO NOTAM standards vary by country

Future versions may add support for other NOTAM sources.

### How often is data updated?

**Daily by default** at 02:00. This balances freshness with respectful API usage. UK NATS updates their feed continuously, but NOTAMs typically remain valid for hours to weeks.

**Can I change the update schedule?** Yes, via Settings → Integrations → Configure → Integrations → NOTAMs → Update Time.

### What happens if UK NATS is down?

**Graceful degradation**: The integration uses the last cached NOTAMs indefinitely. A warning sensor activates to alert you that data may be stale, but functionality continues.

**Critical**: Always check official sources before flight. This integration is supplementary only.

### Can I manually refresh NOTAMs?

**Yes**, via Developer Tools → Services:

```yaml
service: hangar_assistant.refresh_notams
data: {}
```

(Note: This service may be added in future versions. Currently, restarts trigger immediate refresh.)

### Are NOTAMs included in AI briefings?

**Yes!** Active NOTAMs automatically appear in AI-generated pre-flight briefings with:
- Critical NOTAMs highlighted first
- Runway/airspace restrictions summarized
- Navigation aid outages noted
- Validity periods included

### How much storage does caching use?

**Minimal** - typically 50-200KB for the JSON cache file. The cache contains only active NOTAMs relevant to your configured airfields, not the entire UK database.

### Can I export NOTAMs for offline use?

**Indirectly** - The sensor attributes contain full NOTAM data accessible via:
- Developer Tools → States → `sensor.{airfield}_notams` → Copy attributes
- Template sensors to format as needed
- Dashboard cards displaying NOTAM text

For official offline briefing packs, use UK NATS official services.

---

## Best Practices

### For VFR Pilots

1. **Enable for home + practice areas**: Configure NOTAMs for your departure airfield and common practice areas
2. **Check before every flight**: Review NOTAM sensor before engine start
3. **Combine with AI briefing**: Use `refresh_ai_briefings` service for comprehensive briefing
4. **Cross-reference official sources**: This integration supplements but doesn't replace official briefing

### For Cross-Country Planning

1. **Configure all enroute airfields**: Add NOTAMs for departure, destination, and alternates
2. **Review 24 hours before**: Check for newly issued NOTAMs affecting planned route
3. **Monitor during flight**: Dashboard visible on tablet shows real-time NOTAM count
4. **Post-flight review**: Check for NOTAMs issued during flight for situational awareness

### For Flight Schools

1. **Configure training areas**: NOTAM sensors for airfield + all practice areas
2. **Daily briefing automation**: Auto-speak NOTAMs at instructor briefing time
3. **Dashboard in briefing room**: Permanent display showing active NOTAMs
4. **Student awareness**: Teach students to check NOTAM sensor before pre-flight

### For Maintenance Monitoring

1. **Track facility NOTAMs**: Monitor NOTAMs affecting your hangar/airfield services
2. **Alert on critical changes**: Automation triggers when runway/taxiway closures appear
3. **Historical logging**: Keep NOTAM cache for maintenance planning (30-day retention)

---

## Technical Details

### XML Parsing Security

The integration uses **defusedxml** library (if available) to protect against XML External Entity (XXE) attacks. If defusedxml isn't installed, standard ElementTree is used with entity expansion disabled.

**Security considerations**:
- XML source is trusted (UK government)
- No user-supplied XML parsed
- Cache files validated before use
- All file operations wrapped in executor jobs

### Performance Optimization

**Single cache read**: The fetch logic reads the cache file once and reuses the data if network fetch fails, avoiding redundant I/O operations.

**LRU memory cache**: Parsed NOTAM data is cached in memory (OrderedDict with LRU eviction) to prevent repeated parsing.

**Async file operations**: All file I/O wrapped in `hass.async_add_executor_job()` to prevent blocking the event loop.

### Q-Code Parsing

The integration includes a full Q-code parser (`utils/qcode_parser.py`) that translates cryptic NOTAM Q-codes into human-readable categories:

| Q-Code | Category | Example |
|--------|----------|---------|
| `QMRLC` | Runway closed | "RWY 03/21 CLOSED" |
| `QNBXX` | Navigation aid U/S | "NDB POH UNSERVICEABLE" |
| `QFAXX` | Airspace restriction | "PARACHUTING IN PROGRESS" |
| `QLXLC` | Lighting U/S | "PAPI RWY 21 U/S" |

Full Q-code reference: [ICAO Annex 15](https://www.icao.int/safety/OPS/OPS-Tools/Pages/NOTAM.aspx)

### Failure Recovery

The integration tracks consecutive failures and implements progressive backoff:
1. **1-2 failures**: Log warning, use stale cache
2. **3+ failures**: Create warning binary sensor
3. **10+ failures**: Persistent notification to user
4. **Auto-recovery**: Counter resets on successful fetch

### Migration from Previous Versions

**v2601.1.0+**: NOTAMs moved to "Integrations" configuration menu with improved settings. Existing installations automatically migrate settings during upgrade.

**Backward compatibility**: If NOTAM settings are missing, integration defaults to:
- Enabled: `True` (free service, safe to auto-enable)
- Update Time: `02:00`
- Cache Days: `7`

---

## Related Documentation

- [OpenWeatherMap Integration](openweathermap_integration.md) - Paid weather forecast service
- [API Integrations Overview](api_integrations.md) - Managing all external integrations
- [AI Briefing Service](ai_briefing.md) - How NOTAMs appear in generated briefings
- [Sensor Reference](../ENTITY_DESCRIPTIONS.md) - Complete list of NOTAM sensor attributes
- [Security Best Practices](../development/SECURITY.md) - XML parsing and caching security

---

## Version History

### v1.0 (v2601.1.0 - January 2026)
- ✅ Initial release with UK NATS PIB XML integration
- ✅ Persistent caching with stale fallback
- ✅ Location filtering by ICAO and geographic radius
- ✅ Q-code parser for human-readable categories
- ✅ Daily scheduled updates at 02:00
- ✅ Graceful degradation on network failures
- ✅ Integration with AI briefing service
- ✅ Warning sensors for stale data

### Planned Enhancements (v2601.2.0+)
- 🔄 Manual refresh service (`hangar_assistant.refresh_notams`)
- 🔄 Customizable severity filtering (critical only, all NOTAMs)
- 🔄 NOTAM expiry notifications (automation trigger)
- 🔄 Multi-country NOTAM support (EU AIS, FAA NOTAM API)
- 🔄 Historical NOTAM logging (CSV export)
- 🔄 Dashboard card template for NOTAM display
- 🔄 Mobile app push notifications for critical NOTAMs

---

**Last Updated**: 22 January 2026  
**Feature Version**: 1.0  
**Target Users**: UK-based pilots (PPL, student pilots, flight instructors)  
**Difficulty Level**: Beginner (automatic, no configuration required)  
**Cost**: Free (UK NATS public service)
