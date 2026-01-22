# ADS-B Aircraft Tracking

## Overview
Real-time ADS-B and FLARM positions are now available inside Hangar Assistant. The integration gathers aircraft locations from your chosen sources (e.g., local dump1090, OpenSky Network, OGN) and exposes them as device trackers on the Hangar dashboard map. The feature is entirely optional and ships disabled by default to protect bandwidth and rate limits.

## Getting Started
1. Open **Settings → Devices & Services → Hangar Assistant → Configure** and enable **ADS-B tracking**.
2. Pick at least one source (OpenSky is the simplest free option; dump1090 gives the best low-latency local coverage).
3. Save and wait for the first update window (default 10 seconds) so device tracker entities can be created.
4. Open the **Hangar Assistant** dashboard; the **Traffic Awareness (ADS-B/FLARM)** section will map any aircraft discovered near your configured airfields.

## Step-by-Step Guide
### Step 1: Enable ADS-B
- Toggle **ADS-B tracking** on in the Hangar Assistant options flow.
- Leave the default sources (OpenSky and OGN) enabled, or switch to a local dump1090 feed if you have a receiver on your network.

### Step 2: Confirm credentials (if needed)
- OpenSky: optional username/password for higher limits; anonymous mode works for light usage.
- dump1090: ensure the JSON endpoint is reachable (default `http://localhost:8080/data/aircraft.json`).

### Step 3: Wait for entities
- Device trackers use the naming pattern `device_tracker.aircraft_<registration_or_icao24>` once a valid position arrives.
- Entities appear automatically; no helpers or YAML edits are required.

### Step 4: View on the dashboard
- Open the **Hangar Overview** view and scroll to **Traffic Awareness (ADS-B/FLARM)**.
- The map plots every available ADS-B/FLARM track alongside your Home zone; the list beneath shows the same aircraft in a compact table.

## Troubleshooting
- **No aircraft on the map**: Confirm ADS-B is enabled, at least one source is active, and your network allows outbound calls to the chosen API or local dump1090 host.
- **Entity IDs never appear**: Check Home Assistant logs for ADS-B client errors; rate limits or unreachable endpoints will pause updates until the next retry window.
- **Positions look stale**: Verify your update interval and cache TTL in the ADS-B settings; reduce the interval cautiously to avoid hitting free-tier limits.
- **Local receiver unreachable**: Open the dump1090 URL in a browser to confirm it responds; adjust host/port in the options flow if needed.

## FAQ
- **Is ADS-B required?** No. It remains opt-in and does not affect existing weather or performance sensors.
- **How often does it refresh?** Defaults to 10 seconds per source with a 30-second cache. Adjust in the ADS-B settings if you need slower polling to conserve credits.
- **What appears on the map?** Device trackers named `device_tracker.aircraft_*` derived from ADS-B/FLARM data. If no trackers exist, the section stays hidden.
- **Do I need selectors or helpers?** No. Entities are generated automatically from live aircraft data.
- **Which units are used?** Positions are in decimal degrees with altitude in feet and speed in knots (aviation defaults).

## Best Practices
- **Local pilots**: Prefer dump1090 for the most accurate, low-latency coverage around your airfield.
- **OpenSky-only users**: Keep the default cache TTL (30 seconds) to stay well within free-rate limits.
- **Minimal bandwidth setups**: Start with a single source and widen later; the map will merge all enabled sources automatically.
- **Display screens**: Use the per-device URL parameters (e.g., `?airfield=popham`) and the new traffic section for fixed wall displays.

## Technical Details (Advanced)
<details>
<summary>Click to expand</summary>

- Entity IDs follow `device_tracker.aircraft_<registration_or_icao24>`; attributes include latitude, longitude, altitude (ft), ground speed (kt), track (deg), source, and GPS accuracy.
- Source priority: dump1090 (1) → OpenSky (2) → OGN (3) → commercial APIs (disabled by default). Higher-priority data overwrites lower-priority duplicates.
- Caching: 30-second in-memory cache with LRU eviction to 5,000 aircraft entries by default.
- Configuration keys live under `entry.data["adsb"]` with per-source dictionaries; defaults keep everything off unless explicitly enabled.
- Dashboard template location: [custom_components/hangar_assistant/dashboard_templates/glass_cockpit.yaml](../../custom_components/hangar_assistant/dashboard_templates/glass_cockpit.yaml).

</details>

## Related Documentation
- Planning record: [docs/implemented/adsb_tracking_plan.md](../implemented/adsb_tracking_plan.md)
- Dashboard setup help: [custom_components/hangar_assistant/dashboard_templates/dashboard_setup_help.md](../../custom_components/hangar_assistant/dashboard_templates/dashboard_setup_help.md)
- ADS-B config flow: [custom_components/hangar_assistant/adsb_config_flow.py](../../custom_components/hangar_assistant/adsb_config_flow.py)

## Version History
- v2601.5.0: Initial ADS-B/FLARM tracking release with dashboard map integration.
