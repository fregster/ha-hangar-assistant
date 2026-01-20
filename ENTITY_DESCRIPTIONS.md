# Entity Descriptions (Tooltips) for Hangar Assistant

## Implementation Guide

Home Assistant supports entity descriptions through the `strings.json` file. Here's what needs to be added:

### Current Issue
The `strings.json` file currently has minimal entity definitions:
```json
"entity": {
  "sensor": {
    "carb_risk": { "name": "Carb Risk" },
    "best_runway": { "name": "Best Runway" },
    // ... etc
  }
}
```

### Solution: Add Descriptions

Replace the `"entity"` section in `/custom_components/hangar_assistant/strings.json` (starting around line 286) with:

```json
  "entity": {
    "sensor": {
      "density_altitude": {
        "name": "Density Altitude",
        "state": {
          "description": "Pressure altitude corrected for non-standard temperature. Higher DA reduces aircraft performance."
        }
      },
      "cloud_base": {
        "name": "Cloud Base",
        "state": {
          "description": "Estimated cloud base height using temperature-dewpoint spread method. VFR minima apply."
        }
      },
      "carb_risk": {
        "name": "Carb Risk",
        "state": {
          "description": "Carburetor icing risk based on temperature and humidity. Serious risk requires carb heat usage."
        }
      },
      "best_runway": {
        "name": "Best Runway",
        "state": {
          "description": "Recommended runway based on wind direction. Minimizes crosswind component."
        }
      },
      "performance_margin": {
        "name": "Performance Margin",
        "state": {
          "description": "Percentage of runway remaining after calculated ground roll. Higher values indicate safer margins."
        }
      },
      "ground_roll": {
        "name": "Ground Roll",
        "state": {
          "description": "Estimated takeoff distance adjusted for density altitude. Based on POH baseline performance."
        }
      },
      "data_freshness": {
        "name": "Weather Data Age",
        "state": {
          "description": "Time since weather sensors last updated. Stale data triggers safety alerts."
        }
      },
      "icing_advisory": {
        "name": "Icing Advisory",
        "state": {
          "description": "Combined assessment of frost, carburetor icing, and airframe icing risks."
        }
      },
      "daylight_countdown": {
        "name": "Daylight Remaining",
        "state": {
          "description": "Hours until sunset or sunrise. Critical for pilots without night rating."
        }
      },
      "timezone": {
        "name": "Timezone",
        "state": {
          "description": "Local timezone for the airfield based on geographic coordinates."
        }
      },
      "ai_briefing": {
        "name": "AI Briefing",
        "state": {
          "description": "AI-generated pre-flight briefing covering weather, performance, and safety considerations."
        }
      },
      "pilotinfosensor": {
        "name": "Pilot Qualifications",
        "state": {
          "description": "Pilot-in-Command licence type and qualifications."
        }
      },
      "backup_integrity": {
        "name": "Backup Integrity",
        "state": {
          "description": "Integrity status of configuration backups."
        }
      }
    },
    "binary_sensor": {
      "safety_alert": {
        "name": "Master Safety Alert",
        "state": {
          "description": "Composite safety alert monitoring weather data age and critical carb icing conditions."
        }
      },
      "crosswind_alert": {
        "name": "Crosswind Alert",
        "state": {
          "description": "Alert when crosswind component exceeds aircraft limitations specified in POH."
        }
      },
      "pilotmedicalalert": {
        "name": "Medical Expiry Alert",
        "state": {
          "description": "Alert when pilot medical certificate is approaching expiry (within 30 days) or has expired."
        }
      }
    }
  }
```

### Then Update Translation Files

Copy the same structure to all translation files:
- `/custom_components/hangar_assistant/translations/en.json`
- `/custom_components/hangar_assistant/translations/de.json` (translate descriptions to German)
- `/custom_components/hangar_assistant/translations/es.json` (translate descriptions to Spanish)
- `/custom_components/hangar_assistant/translations/fr.json` (translate descriptions to French)

### How It Works

Once added, these descriptions will appear:
1. **Entity Info Dialog**: When users click the "i" icon next to an entity
2. **More Info Dialog**: In the entity's more-info popup
3. **Developer Tools**: In the States tab when inspecting entities
4. **Voice Assistants**: To provide context for voice commands

### Testing

After updating the files:
1. Restart Home Assistant
2. Go to Developer Tools → States
3. Find a Hangar Assistant entity
4. Click the info icon - you should see the description

### Benefits

- **User Onboarding**: New users understand what each sensor does
- **Safety**: Critical sensors like "Carb Risk" have clear warnings
- **Professionalism**: Shows attention to detail and user experience
- **Accessibility**: Screen readers can announce descriptions
- **AI Integration**: Better context for voice assistants and AI features
