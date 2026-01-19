# ✈️ Hangar Assistant
**The Glass Cockpit for your Home Assistant**

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
![Version](https://img.shields.io/badge/version-2601.1.0-blue)

Hangar Assistant is a specialized integration for General Aviation pilots, designed to bridge the gap between your home automation and the cockpit. It provides real-time safety metrics, performance calculations (Density Altitude, Cloud Base), and helps maintain legal compliance for CAP 1590B.

## 🚀 Key Features
- **Dynamic Fleet Management**: Add multiple aircraft and airfields via the UI.
- **Safety Annunciator**: A "Master Safety Alert" binary sensor for every airfield.
- **Density Altitude & Performance**: Automated calculations based on your local weather sensors.
- **Legal Compliance**: Automated data retention and CAP 1590B PDF generation support.
- **Pilot-Centric UI**: Designed to be viewed on tablets and integrated into "Glass Cockpit" style dashboards.

---

## 🛠️ Installation

### Option 1: HACS (Recommended)
1. Open **HACS** in Home Assistant.
2. Click the three dots in the top right and select **Custom repositories**.
3. Add `https://github.com/fregster/ha-hangar-assistant` with category **Integration**.
4. Click **Download** and restart Home Assistant.

### Option 2: Manual
1. Download the latest release.
2. Copy the `hangar_assistant` folder to your `custom_components` directory.
3. Restart Home Assistant.

---

## 📖 Setup Guide

### 1. Initial Onboarding
Go to **Settings > Devices & Services** and click **Add Integration**. Search for **Hangar Assistant**. 
*Note: The initial setup is a simple "Welcome" step. You do not need any sensors or tail numbers ready to get started.*

### 2. Adding Airfields & Aircraft
Once installed, click the **Configure** button on the Hangar Assistant card. You can then choose:
* **Add Airfield**: Select your temperature, dew point, and wind sensors from a dropdown menu.
* **Add Aircraft**: Enter your POH ground roll and MTOW data.
* **Add Pilot**: Save your PIC details for automated flight logs.

### 3. Safety Monitoring
Every airfield you add creates a **Master Safety Alert**. This sensor will turn **Unsafe (On)** if:
- Weather data is older than 30 minutes.
- Atmospheric conditions present a "Serious Risk" of Carb Icing.
- Legal backup integrity is compromised.

---

## 📊 Dashboard Integration
We recommend using the **Mushroom Card** pack or the **Pilot's Dashboard YAML** provided in our documentation to create a dedicated aviation tab in your Home Assistant.

---

## 🛡️ Legal & Privacy
This integration is designed to assist pilots but **MUST NOT** be used as the primary source of navigation or flight safety decisions. Always refer to your official POH and official METAR/TAF sources.
- **Data Retention**: Local records are purged after 7 months by default to comply with standard pilot record-keeping recommendations.

---

## 🤝 Support
Found a bug? [Open an issue on GitHub](https://github.com/fregster/ha-hangar-assistant/issues).
Created by **@fregster**.

---

## Integration Testing

[![Hassfest](https://img.shields.io/github/actions/workflow/status/fregster/ha-hangar-assistant/validate.yml?label=Hassfest&job=Hassfest%20(HA%20Official))](https://github.com/fregster/ha-hangar-assistant/actions/workflows/validate.yml)
[![HACS Validation](https://img.shields.io/github/actions/workflow/status/fregster/ha-hangar-assistant/validate.yml?label=HACS%20Validation&job=HACS%20(Store%20Compliance))](https://github.com/fregster/ha-hangar-assistant/actions/workflows/validate.yml)
[![Linting](https://img.shields.io/github/actions/workflow/status/fregster/ha-hangar-assistant/validate.yml?label=Linting&job=Lint%20(Code%20Quality))](https://github.com/fregster/ha-hangar-assistant/actions/workflows/validate.yml)