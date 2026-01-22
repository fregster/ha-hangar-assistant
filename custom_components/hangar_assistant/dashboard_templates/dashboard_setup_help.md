# Hangar Assistant Dashboard Setup (Sidebar)

Use this reference if your dashboard is missing from the sidebar or you want to recreate it quickly.

## Option A: YAML dashboard (recommended)
Add this to `configuration.yaml`:

```yaml
lovelace:
  dashboards:
    hangar-assistant:
      mode: yaml
      title: Hangar Assistant
      icon: mdi:airplane
      show_in_sidebar: true
      filename: /config/custom_components/hangar_assistant/dashboard_templates/glass_cockpit.yaml
```

Then reload dashboards (Settings → Dashboards → three-dots → Reload Resources) or restart Home Assistant.

## Option B: UI dashboard
1) Settings → Dashboards → **Add Dashboard**
2) Title: **Hangar Assistant**, Icon: `mdi:airplane`, Show in sidebar: On
3) If using YAML mode, point the filename to `/config/custom_components/hangar_assistant/dashboard_templates/glass_cockpit.yaml` (or paste the template into a new dashboard if using storage mode).

## Built-in selectors
The integration now exposes dropdown entities automatically:

- select.hangar_assistant_airfield_selector
- select.hangar_assistant_aircraft_selector
- select.hangar_assistant_pilot_selector

These mirror your configured airfields/aircraft/pilots—no manual helpers needed. Use them in dashboards or automations if you want explicit selection rather than auto-detect.

## ADS-B aircraft map

- Device tracker entities for ADS-B/FLARM targets use the pattern `device_tracker.aircraft_*`.
- The glass cockpit dashboard automatically maps them; no extra helpers or filters are required.
- If no ADS-B sources are enabled, the section hides itself and the rest of the dashboard continues to function normally.

## Automation hook (optional)
If you enable "Fire 'hangar_assistant_dashboard_setup' event" in the config flow, you can listen for it and ensure helpers/dashboards are set up:

```yaml
automation:
  - alias: Hangar Assistant Dashboard Setup Hook
    trigger:
      - platform: event
        event_type: hangar_assistant_dashboard_setup
    action:
      - service: persistent_notification.create
        data:
          title: "Hangar Assistant Dashboard"
          message: "Dashboard setup event fired. If the dashboard is missing, add the YAML entry or reload dashboards."
```

Tip: Built-in selectors are created automatically from your configured airfields, aircraft, and pilots—no manual helpers are required.

---

## Per-Device Dashboard State Management

### Overview

The dashboard now supports **per-device airfield and aircraft selection**, allowing multiple displays to show different aircraft simultaneously.

### How It Works

Each device maintains its own view using a priority-based system:

1. **URL Parameters** (Highest) - For fixed wall displays
2. **localStorage** (Medium) - Preserves user's last selection
3. **Config Defaults** (Low) - Set in General Settings
4. **Auto-Detection** (Fallback) - First available entity

### Setup Examples

**Fixed Wall Display** (always shows G-ABCD):
```
http://homeassistant:8123/hangar-glass-cockpit?aircraft=g_abcd
```

**Interactive Users:**
- No URL params needed
- Selection saved in browser automatically
- Each device/browser remembers independently

**Config Defaults:**
1. Configure → Global Configuration → General Settings
2. Set "Default Dashboard Airfield" and "Default Dashboard Aircraft"

### Migration Notes

- **Existing setups:** No changes required - backward compatible
- **Select entities:** Still work for automations
- **New feature:** Optional - old behavior continues if not configured

### Technical Details

JavaScript module: `dashboard_templates/hangar_state_manager.js`
- Handles state management
- URL param detection
- localStorage persistence
- Config default fallback
