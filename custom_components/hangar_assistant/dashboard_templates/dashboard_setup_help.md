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


Tip: Built-in selectors are created automatically from your configured airfields, aircraft, and pilots—no manual helpers are required.
