# Glass Cockpit Dashboard

**Feature**: Aviation-Themed Interactive Dashboard  
**Version**: 1.0 (v2601.1.0)  
**Status**: ✅ Available (Auto-Install or Manual)

---

## Overview

The Glass Cockpit Dashboard is a beautiful, aviation-themed Lovelace dashboard that transforms Home Assistant into a modern flight deck display. Inspired by Garmin G1000/G3000 avionics, it presents all Hangar Assistant data in a pilot-friendly layout optimized for tablets, wall-mounted displays, and desktop browsers.

**Before this dashboard**, pilots had to navigate multiple Home Assistant tabs, individual entity cards, and the default UI to find aviation data scattered across different views.

**With the Glass Cockpit**, all flight-critical information is centralized in one aviation-themed interface that feels like sitting in a modern aircraft cockpit.

---

## Key Benefits

✅ **Aviation-Themed UI** - Looks and feels like real glass cockpit avionics  
✅ **Mobile-Responsive** - Works on phone, tablet, desktop  
✅ **Per-Device Views** - Each display remembers its own airfield/aircraft selection  
✅ **Live Data** - Real-time updates from sensors and integrations  
✅ **Auto-Install** - Setup wizard installs dashboard automatically  
✅ **Customizable** - Full YAML access for modifications  

---

## Dashboard Sections

### 1. Header / Navigation
- **Airfield Selector** - Switch between configured airfields
- **Aircraft Selector** - Switch between configured aircraft
- **Last Updated** - Data freshness indicator
- **Current Conditions Summary** - Quick glance weather

### 2. Primary Flight Display (PFD) Area
- **Density Altitude** - Large, easy-to-read gauge
- **Cloud Base** - VFR minima compliance indicator
- **Crosswind Component** - Color-coded by severity
- **Best Runway** - Recommended runway with wind component

### 3. Multi-Function Display (MFD) Area
- **Weather Conditions** - Temperature, dew point, pressure, humidity
- **Wind Information** - Speed, direction, gusts with animated icon
- **Performance Metrics** - Ground roll, performance margin
- **Safety Alerts** - Master safety alert, carb icing risk

### 4. Navigation / Flight Planning
- **NOTAMs** - Active notices with criticality indicators
- **Weather Alerts** - Government warnings (if OWM enabled)
- **AI Briefing** - Full briefing text display
- **Forecast Trends** - 6-hour and 3-day outlook (if OWM enabled)

### 5. Aircraft Information
- **Selected Aircraft** - Registration, type, specs
- **Performance Limits** - MTOW, crosswind limits, fuel capacity
- **Fuel Endurance** - Calculated endurance at current settings
- **Pilot Information** - PIC details (if configured)

### 6. Footer / Status
- **Integration Status** - CheckWX, OWM, NOTAM connection status
- **Data Age Indicators** - Sensor freshness warnings
- **Service Actions** - Quick buttons for refresh/rebuild

---

## Installation Methods

### Automatic Installation (Recommended)

**Via Setup Wizard**:
1. Install Hangar Assistant integration
2. Complete setup wizard (Steps 1-7)
3. Step 8: Select "Automatic Installation"
4. Dashboard installs in 2-3 seconds
5. Appears in sidebar immediately

**Via Service Call**:
```yaml
service: hangar_assistant.install_dashboard
data:
  method: automatic
```

**Advantages**:
- ✅ Zero configuration required
- ✅ Installs in seconds
- ✅ Appears in sidebar automatically
- ✅ Updates handled by integration

**Requirements**:
- Lovelace UI must be in storage mode (default)
- Sufficient permissions to create dashboards

---

### Manual Installation

**Via Setup Wizard**:
1. Complete setup wizard Steps 1-7
2. Step 8: Select "Manual Installation"
3. Copy generated YAML
4. Follow 9-step installation guide in YAML

**Via Service Call**:
```yaml
service: hangar_assistant.install_dashboard
data:
  method: manual
```
Returns YAML in service response

**Via File System**:
1. Navigate to `custom_components/hangar_assistant/dashboard_templates/`
2. Copy `glass_cockpit.yaml` content
3. Follow manual installation guide

**Manual Installation Steps**:
1. Go to Settings → Dashboards
2. Click "Add Dashboard"
3. Name: "Hangar Glass Cockpit"
4. Icon: `mdi:airplane-takeoff`
5. Click "Create"
6. Click three-dot menu → "Edit Dashboard"
7. Click three-dot menu → "Raw Configuration Editor"
8. Paste YAML
9. Click "Save"

**Advantages**:
- ✅ Full control over YAML before installation
- ✅ Allows customization before first use
- ✅ Works on YAML-mode Lovelace configurations
- ✅ No Lovelace API dependencies

---

## Per-Device State Management

### How It Works

The dashboard uses **per-device selection persistence**, meaning:
- **Tablet in hangar** - Shows Popham + G-ABCD (your aircraft)
- **Phone in car** - Shows different airfield + aircraft
- **Desktop at home** - Shows another combination

**Each device remembers its own view** using browser localStorage.

### Selection Priority

1. **URL Parameters** (highest priority):
   - `?airfield=popham&aircraft=g_abcd`
   - Used for fixed displays (wall-mounted tablets)

2. **Browser localStorage**:
   - Last selected airfield/aircraft for this device
   - Survives page refreshes and browser restarts

3. **Config Defaults**:
   - Set in Settings → General Settings → Defaults
   - Used when no other selection exists

4. **Auto-Detection** (lowest priority):
   - First configured airfield/aircraft
   - Fallback if all else fails

### Setting Up Fixed Displays

**Example: Wall-mounted tablet in hangar always shows Popham + G-ABCD**

URL:
```
http://homeassistant:8123/hangar-glass-cockpit?airfield=popham&aircraft=g_abcd
```

Use this URL in:
- Kiosk mode apps
- Tablet home screen shortcuts
- Wallboard configurations

**Example: Instructor tablet shows flight school airfield**

URL:
```
http://homeassistant:8123/hangar-glass-cockpit?airfield=oxford&aircraft=g_flyt
```

**Benefit**: Multiple displays can show different airfields simultaneously without interfering with each other.

---

## Required Dependencies

### HACS Integrations

The Glass Cockpit uses these custom cards (auto-prompted during setup):

1. **Mushroom Cards** - Modern, beautiful UI components
   - Install via HACS → Frontend
   - Search "Mushroom"
   - Click Install

2. **ApexCharts Card** - Forecast and trend charts
   - Install via HACS → Frontend
   - Search "ApexCharts Card"
   - Click Install

3. **Card Mod** (Optional) - Advanced styling
   - Install via HACS → Frontend
   - Search "Card Mod"
   - Enhances visual appearance

### Verification

After installing dependencies:
1. Clear browser cache (Ctrl+F5 or Cmd+Shift+R)
2. Refresh dashboard
3. If cards show "Custom element doesn't exist" → reinstall dependency

---

## Dashboard Features

### Live Weather Gauges

**Density Altitude Gauge**:
- Color-coded by severity:
  - 🟢 Green: < 2,000 ft
  - 🟡 Yellow: 2,000-4,000 ft
  - 🔴 Red: > 4,000 ft
- Shows impact on aircraft performance
- Updates every sensor refresh

**Crosswind Component Indicator**:
- Dynamic calculation based on best runway
- Color-coded vs. aircraft limits:
  - 🟢 Safe: < 70% of limit
  - 🟡 Caution: 70-90% of limit
  - 🔴 Unsafe: > 90% of limit

**Cloud Base Display**:
- VFR minima compliance indicator
- Shows AGL height
- Calculated from temperature/dew point spread

---

### Weather Trends (OWM Required)

**6-Hour Forecast Chart**:
- Temperature trend line
- Wind speed overlay
- Cloud base progression
- Hover for exact values

**3-Day Outlook Cards**:
- Daily min/max temperatures
- Precipitation probability
- Wind speeds and gusts
- Weather description icons

**Precipitation Timeline**:
- Minute-by-minute next 60 minutes
- "Rain in X minutes" countdown
- Intensity graph

---

### NOTAM Display

**Active NOTAMs List**:
- Count badge (e.g., "3 Active NOTAMs")
- Expandable cards per NOTAM
- Criticality indicators:
  - 🔴 CRITICAL: Runway closures, airspace restrictions
  - 🟡 IMPORTANT: Navigation aid outages, lighting issues
  - 🔵 INFO: Routine notices
- Effective dates and expiry times
- Q-code translation (human-readable)

**Example Display**:
```
🔴 CRITICAL (1)
━━━━━━━━━━━━━━━━━━━━━━━━━━━
A0123/25 - RWY 21 CLOSED
22 Jan 08:00 - 22 Jan 17:00 UTC

🟡 IMPORTANT (1)
━━━━━━━━━━━━━━━━━━━━━━━━━━━
A0124/25 - NDB POH U/S
20 Jan - 20 Mar 2026
```

---

### Safety Alerts Panel

**Master Safety Alert**:
- Large ON/OFF indicator
- Reasons listed when active:
  - "Weather data > 30 minutes old"
  - "Carb icing: Serious Risk"
  - "Crosswind exceeds aircraft limits"

**Individual Alert Cards**:
- Carb Icing Risk (with color coding)
- Airframe Icing Risk
- Crosswind Alert
- Weather Data Age Warning

---

### AI Briefing Display

**Full Briefing Text**:
- Scrollable markdown card
- Formatted with sections
- GO/NO-GO highlighted
- Copy button for mobile sharing

**Quick Summary Card**:
- Conditions summary (one line)
- GO/NO-GO recommendation
- Alert count
- Generation timestamp

**Refresh Button**:
- One-tap briefing regeneration
- Loading indicator during generation
- Auto-updates display when complete

---

## Customization

### Changing Colors

Edit YAML to change color schemes:

```yaml
# Find the card you want to customize
type: gauge
entity: sensor.popham_density_altitude
# Change these values:
needle_color: "#FF0000"  # Red needle
severity:
  green: 0
  yellow: 2000
  red: 4000
```

### Adding Custom Cards

Insert new cards between existing sections:

```yaml
# After weather section, add custom wind rose:
- type: custom:windrose-card
  entity: sensor.popham_wind_direction
  title: "Wind Rose - Last 24 Hours"
```

### Removing Sections

Comment out sections you don't need:

```yaml
# # 6-Hour Forecast (OWM Required)
# - type: ...
#   cards:
#     ...
```

### Rearranging Layout

Dashboard uses **sections** layout - reorder by moving entire sections:

```yaml
views:
  - sections:
      - title: "Primary Flight Display"  # Move this section
        cards: ...
      - title: "Weather Conditions"       # Before this section
        cards: ...
```

---

## Troubleshooting

### Dashboard Not Appearing in Sidebar

**Symptoms**: Automatic installation completed but dashboard missing

**Causes**:
1. Lovelace cache not refreshed
2. Dashboard created but not added to sidebar
3. Permissions issue during creation

**Solutions**:
- Refresh browser with cache clear (Ctrl+F5 / Cmd+Shift+R)
- Check Settings → Dashboards → verify "Hangar Glass Cockpit" exists
- Restart Home Assistant
- Try manual installation method

---

### Cards Showing "Custom Element Doesn't Exist"

**Symptoms**: Dashboard loads but cards show error message

**Causes**:
1. Mushroom or ApexCharts not installed
2. HACS resources not loaded
3. Browser cache preventing resource load

**Solutions**:
- Install Mushroom: HACS → Frontend → Search "Mushroom"
- Install ApexCharts: HACS → Frontend → Search "ApexCharts Card"
- Clear browser cache completely
- Check HACS → Frontend → ensure both installed
- Restart Home Assistant after installing

---

### Airfield/Aircraft Selector Not Working

**Symptoms**: Clicking selector doesn't change displayed data

**Causes**:
1. Select entities not created (integration setup incomplete)
2. JavaScript state manager not loaded
3. Browser localStorage blocked (privacy mode)

**Solutions**:
- Verify select entities exist: Developer Tools → States → search "select."
- Check browser console for JavaScript errors (F12)
- Disable privacy/incognito mode (blocks localStorage)
- Reload dashboard with Ctrl+F5

---

### Forecast Charts Empty (OWM Enabled)

**Symptoms**: OWM configured but forecast sections blank

**Causes**:
1. OWM API key invalid
2. Rate limit exceeded
3. Forecast sensors not created
4. ApexCharts card not installed

**Solutions**:
- Verify OWM sensors exist: `sensor.{airfield}_weather_forecast_hourly`
- Check OWM integration status: Settings → Integrations → Hangar Assistant
- Review logs for OWM errors: `grep openweathermap home-assistant.log`
- Install ApexCharts: HACS → Frontend → ApexCharts Card
- Increase update interval if rate limited

---

### NOTAM Section Always Empty

**Symptoms**: NOTAM integration enabled but dashboard shows no NOTAMs

**Causes**:
1. No active NOTAMs for airfield (correct behavior)
2. NOTAM sensor not created
3. NOTAM fetch failed (using stale empty cache)

**Solutions**:
- Verify NOTAMs exist: Check UK NATS PIB website
- Check sensor exists: `sensor.{airfield}_notams`
- Review sensor attributes: Developer Tools → States → sensor
- Check logs: `grep notam home-assistant.log`
- Force refresh: Restart Home Assistant

---

### Performance Issues / Slow Loading

**Symptoms**: Dashboard takes 10+ seconds to load or stutters

**Causes**:
1. Too many chart cards (resource intensive)
2. Long forecast history queries
3. Browser/device underpowered
4. Network latency

**Solutions**:
- Reduce forecast data points: Edit ApexCharts `data_generator`
- Disable unused sections (comment out in YAML)
- Use simpler cards for low-power devices (replace gauges with entities)
- Increase sensor cache intervals: Settings → General Settings
- Use dedicated tablet/kiosk hardware

---

## FAQ

### Can I use this dashboard without Mushroom cards?

**Technically yes**, but it won't look right. Mushroom provides:
- Modern, aviation-themed styling
- Consistent card design
- Responsive mobile layout
- Icon animations

**Alternative**: Manually convert to standard `entities` and `gauge` cards, but significant work required.

---

### Does the dashboard work on mobile phones?

**Yes!** The dashboard is fully responsive:
- **Phone (portrait)**: Single-column layout, cards stack vertically
- **Tablet (portrait/landscape)**: Two-column layout
- **Desktop**: Full multi-column layout

**Optimization**: Sections auto-arrange based on screen width.

---

### Can I have multiple dashboard variants?

**Yes!** Create dashboard copies for different use cases:

1. **Duplicate Dashboard**:
   - Settings → Dashboards → Hangar Glass Cockpit
   - Three-dot menu → "Duplicate"
   - Rename: "Hangar Glass Cockpit - Minimal"

2. **Customize Each**:
   - Edit "Minimal" version → remove forecast sections
   - Edit "Full" version → keep everything
   - Create "Mobile" version → simplified layout

3. **Use Device-Specific**:
   - Tablet → Full version
   - Phone → Minimal version
   - Wall display → Single-airfield fixed version

---

### How do I update the dashboard after integration updates?

**Automatic Installation**:
- Dashboard auto-rebuilds on major version updates
- Integration detects version change, reinstalls dashboard
- Your manual edits **will be lost** (backup first)

**Manual Installation**:
- You must manually update YAML from new version
- Copy new template: `custom_components/hangar_assistant/dashboard_templates/glass_cockpit.yaml`
- Merge with your customizations

**Recommendation**: Keep customizations minimal or use separate custom cards to preserve across updates.

---

### Can I use this dashboard with non-Hangar Assistant entities?

**Yes!** The dashboard is just YAML - add any Home Assistant entities:

```yaml
# Add your own weather station sensor
- type: sensor
  entity: sensor.backyard_weather_temp
  name: "Backyard Weather Station"
```

Mix Hangar Assistant entities with your own weather hardware, home sensors, etc.

---

### Does it work with dark mode?

**Yes!** The dashboard adapts to Home Assistant theme:
- Dark mode → Dark cockpit theme (black/grey)
- Light mode → Bright cockpit theme (white/grey)

**Recommendation**: Dark mode looks more like real avionics.

---

### Can I share my dashboard config with other pilots?

**Yes!** Export YAML and share:

1. **Export Dashboard**:
   - Settings → Dashboards → Hangar Glass Cockpit
   - Three-dot menu → "Raw Configuration Editor"
   - Copy all YAML

2. **Share**: Post on:
   - Home Assistant Community Forum
   - GitHub discussions
   - Aviation forums
   - Reddit r/homeassistant

3. **Import**: Others paste YAML into their dashboards

**Note**: Entity IDs must match or be updated in YAML.

---

## Best Practices

### For Hangar Displays

1. **Use wall-mounted tablet** - 10-12" tablet in hangar (Kindle Fire, iPad)
2. **Fixed URL with parameters** - Set specific airfield/aircraft in URL
3. **Kiosk mode** - Use Fully Kiosk Browser or Kiosk Mode apps
4. **Auto-refresh** - Enable in kiosk app to prevent stale data
5. **Weatherproof enclosure** - Protect tablet from humidity/temperature

### For Mobile Use

1. **Add to home screen** - Save as PWA for quick access
2. **Disable auto-lock** - Keep screen on during pre-flight
3. **Bookmark with parameters** - Quick access to your aircraft
4. **Offline handling** - Check entity states before departing hangar WiFi
5. **Mobile data fallback** - Remote access via Nabu Casa or VPN

### For Flight Schools

1. **Instructor tablets** - Fixed URL per instructor's aircraft
2. **Student briefing board** - Wall display showing all aircraft
3. **Rotate displays** - Auto-cycle through aircraft every 30 seconds
4. **Simplified version** - Remove advanced features for students
5. **QR codes** - Post QR codes in aircraft for instant dashboard access

### For Cross-Country Pilots

1. **Multi-airfield view** - Configure destination airfields in advance
2. **Route weather** - Monitor departure + destination + alternates
3. **Trend charts** - Review 3-day forecast before long trips
4. **NOTAM tracking** - Check enroute NOTAMs from dashboard
5. **Mobile briefing** - Generate AI briefing from phone while enroute

---

## Technical Details

### State Manager JavaScript

The dashboard includes `hangar_state_manager.js` for per-device state:

**Features**:
- URL parameter parsing
- localStorage read/write
- Select entity monitoring
- Auto-sync across cards

**Implementation**:
```javascript
// Embedded in dashboard YAML:
type: markdown
content: |
  <script src="/local/hangar_state_manager.js"></script>
```

**Browser Support**:
- Chrome/Edge: ✅ Full support
- Firefox: ✅ Full support
- Safari: ✅ Full support (iOS 11+)
- IE11: ❌ Not supported (use modern browser)

### Performance Optimizations

**Sensor Caching**: Dashboard reads cached sensor states (60s TTL) to reduce load

**Lazy Loading**: Forecast charts only load when section visible

**Conditional Rendering**: OWM/NOTAM sections hidden if integrations disabled

**Resource Efficiency**: Mushroom cards use minimal DOM nodes

---

## Related Documentation

- [Setup Wizard](setup_wizard.md) - Initial dashboard installation
- [NOTAM Integration](notam_integration.md) - NOTAM display configuration
- [OpenWeatherMap Integration](openweathermap_integration.md) - Forecast chart data
- [AI Briefing](ai_briefing.md) - Briefing text display
- [Customization Guide](../CUSTOMIZATION.md) - Advanced dashboard modifications

---

## Version History

### v1.0 (v2601.1.0 - January 2026)
- ✅ Initial release with auto-install capability
- ✅ Per-device state management
- ✅ Mushroom card-based layout
- ✅ ApexCharts forecast visualization
- ✅ NOTAM criticality display
- ✅ AI briefing integration
- ✅ Mobile-responsive design
- ✅ Dark mode support
- ✅ Fixed display URL parameters

### Planned Enhancements (v2601.2.0+)
- 🔄 Dashboard template gallery (minimal, full, instructor)
- 🔄 Drag-and-drop dashboard editor
- 🔄 Custom color themes (G1000, G3000, classic analog)
- 🔄 Voice-activated commands ("Show Popham weather")
- 🔄 Animated weather radar overlay
- 🔄 Multi-aircraft comparison view
- 🔄 Flight log integration (recent flights display)

---

**Last Updated**: 22 January 2026  
**Feature Version**: 1.0  
**Target Users**: All pilots using Hangar Assistant  
**Difficulty Level**: Beginner (auto-install) to Intermediate (customization)  
**Cost**: Free (requires HACS custom cards - also free)
