# Hangar Assistant for Home Assistant

**Hangar Assistant** is a pre-flight decision support tool for General Aviation and Glider pilots. It transforms raw local weather data into actionable aviation metrics.

## Features
* **Carb Icing Risk:** Real-time probability assessment based on FAA/EASA icing charts.
* **Risk Altitude:** Predicts the altitude at which you will encounter carburetor icing conditions during a climb.
* **Density Altitude:** Calculates current density altitude to assist in takeoff performance planning.
* **Crosswind Component:** Real-time calculation of crosswind for your specific runway heading.
* **Estimated Cloud Base:** Predicts AGL cloud base using the temperature/dew point spread (Standard Lapse Rate).

## Installation
1.  Add this repository to **HACS** as a Custom Repository.
2.  Install the "Hangar Assistant" integration.
3.  Restart Home Assistant.
4.  Go to **Settings > Devices & Services > Add Integration** and search for "Hangar Assistant".

## Configuration
During setup, you will be asked to provide:
* **Location Name:** A label for the sensors (e.g., "The Airfield").
* **Sensors:** Local entities for Temperature, Dew Point, Wind Speed, and Wind Direction.
* **Runway Heading:** The magnetic heading of your primary runway (e.g., 27 for 270°).

## ⚠️ Safety Disclaimer
**NOT FOR OPERATIONAL USE.** Hangar Assistant is a secondary reference tool. All calculations are based on the International Standard Atmosphere (ISA) and standard lapse rates which may not reflect actual localized conditions. Always consult official METAR/TAF briefings, POH performance charts, and NOTAMs before flight. The pilot in command is solely responsible for the safe operation of the aircraft.

---
*Developed for the GA and Gliding Community.*
