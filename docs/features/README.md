# Features Documentation

This directory contains comprehensive documentation for all major features in Hangar Assistant. Each feature document follows a consistent template covering overview, configuration, use cases, troubleshooting, and best practices.

---

## Available Features

### 🚀 [Setup Wizard](setup_wizard.md)
**Status**: ✅ Available  
**Version**: 1.0 (v2601.2.0)  
**Difficulty**: Beginner

Guided 7-step onboarding experience that helps you configure Hangar Assistant in 10-15 minutes. Walks you through:
- General settings (language, units)
- API integrations (CheckWX, OpenWeatherMap, NOTAMs)
- Airfield configuration (with auto-population)
- Hangar setup (optional)
- Aircraft configuration (templates included)
- Sensor linking (optional)
- Dashboard installation

**Best for**: First-time users, students, anyone preferring guided setup over manual configuration.

---

### ✈️ [NOTAM Integration](notam_integration.md)
**Status**: ✅ Available (Free)  
**Version**: 1.0 (v2601.1.0)  
**Difficulty**: Beginner

Automatic UK NATS Notice to Airmen (NOTAM) integration providing:
- Daily scheduled updates (02:00)
- Location filtering by ICAO or geographic radius
- Persistent caching with graceful degradation
- Q-code parsing for human-readable categories
- Critical NOTAM highlighting
- Integration with AI briefings

**Best for**: UK-based pilots (EGXX airfields), pilots requiring NOTAM monitoring, flight schools tracking airfield status.

---

### 🌦️ [OpenWeatherMap Integration](openweathermap_integration.md)
**Status**: ✅ Available (Paid Service)  
**Version**: 1.0 (v2601.1.0)  
**Difficulty**: Intermediate

Professional weather forecasts and alerts via OpenWeatherMap One Call API 3.0:
- 48-hour hourly forecasts
- 8-day daily forecasts
- 60-minute precipitation forecasts
- Government weather alerts
- UV index monitoring
- Two-level persistent caching (rate limit protection)

**Cost**: ~£8-25/month (~$10-30 USD) depending on usage  
**Best for**: Cross-country pilots, pilots requiring forecast data, flight schools needing multi-day planning.

---

### 🤖 [AI Pre-Flight Briefing](ai_briefing.md)
**Status**: ✅ Available (Requires AI Service)  
**Version**: 1.0 (v2601.1.0)  
**Difficulty**: Intermediate

AI-generated comprehensive safety briefings synthesizing:
- Current weather conditions
- Performance calculations (density altitude, cloud base, crosswind)
- Safety alerts (carb icing, airframe icing, data age)
- NOTAMs (critical notices highlighted)
- Forecast trends (6-hour and 3-day)
- GO/NO-GO recommendations

**Features**:
- Text display on dashboard
- Text-to-speech delivery via TTS
- Scheduled morning briefings
- Mobile push notifications
- Integration with all data sources

**Cost**: AI service subscription required (~£0-20/month for Gemini/OpenAI)  
**Best for**: All pilots, especially cross-country and flight school operations.

---

### 📊 [Glass Cockpit Dashboard](glass_cockpit_dashboard.md)
**Status**: ✅ Available  
**Version**: 1.0 (v2601.1.0)  
**Difficulty**: Beginner (auto-install) to Intermediate (customization)

Aviation-themed Lovelace dashboard displaying:
- Live weather gauges (density altitude, cloud base, crosswind)
- Forecast charts (6-hour trends, 3-day outlook)
- NOTAM display with criticality indicators
- AI briefing text
- Safety alerts panel
- Performance metrics
- Per-device state management (each display remembers its airfield/aircraft)

**Installation Methods**:
- Automatic (2-3 seconds via Setup Wizard or service)
- Manual (YAML copy/paste for customization)

**Best for**: All users, essential for visual data monitoring in hangar or on mobile.

---

## Feature Comparison Matrix

| Feature | Free | Paid | AI Required | UK Only | Difficulty |
|---------|------|------|-------------|---------|------------|
| Setup Wizard | ✅ | - | - | - | Beginner |
| NOTAM Integration | ✅ | - | - | ✅ | Beginner |
| OpenWeatherMap | - | ✅ (~£8-25/mo) | - | - | Intermediate |
| AI Briefing | - | ✅ (~£0-20/mo) | ✅ | - | Intermediate |
| Glass Cockpit | ✅ | - | - | - | Beginner |

**Legend**:
- ✅ = Included/Required
- (~£X/mo) = Estimated monthly cost
- - = Not applicable

---

## Getting Started

### New Users
1. **Start here**: [Setup Wizard](setup_wizard.md) - Guides you through initial configuration
2. **Install dashboard**: [Glass Cockpit Dashboard](glass_cockpit_dashboard.md) - Visualize your data
3. **Enable free integrations**: [NOTAM Integration](notam_integration.md) - Add NOTAM data (UK only)
4. **Optional upgrades**: [OpenWeatherMap](openweathermap_integration.md) or [AI Briefing](ai_briefing.md)

### Experienced Users
1. **Manual configuration**: Settings → Integrations → Hangar Assistant → Configure
2. **Select features**: Enable only the integrations you need
3. **Customize dashboard**: Edit YAML to match your preferences
4. **Automate**: Set up morning briefings, weather alerts, NOTAM notifications

---

## Feature Dependencies

```
Hangar Assistant (Core)
├── Setup Wizard (standalone)
├── Glass Cockpit Dashboard (standalone)
├── NOTAM Integration (standalone, UK only)
├── OpenWeatherMap Integration (requires API subscription)
└── AI Briefing
    ├── Requires: AI service (Gemini/OpenAI)
    └── Enhanced by: NOTAM + OpenWeatherMap (optional)
```

**Core Features** (always available):
- Airfield management
- Aircraft management
- Pilot information
- Sensor integrations
- Density altitude calculations
- Cloud base estimation
- Crosswind calculations
- Carburetor icing risk
- Safety alerts

**Optional Integrations** (enhance core features):
- NOTAMs (free, UK only)
- OpenWeatherMap (paid, worldwide)
- AI Briefing (paid AI service, worldwide)

---

## Documentation Standards

All feature documentation follows this template:

### Required Sections
1. **Overview** - What the feature does, before/after comparison
2. **Key Benefits** - Bullet list of advantages
3. **Configuration** - Setup instructions, settings reference
4. **Entities Created** - Sensors, binary sensors, select entities
5. **Use Cases** - Practical examples with code snippets
6. **Troubleshooting** - Common issues and solutions
7. **FAQ** - Frequently asked questions
8. **Best Practices** - Recommendations by user type
9. **Technical Details** - Implementation specifics for advanced users
10. **Related Documentation** - Cross-references
11. **Version History** - Feature changelog

### Style Guidelines
- **Aviation language** - Use pilot-friendly terminology (not technical jargon)
- **Real-world examples** - Actual code snippets and scenarios
- **Clear structure** - Headers, tables, lists for scannability
- **Visual indicators** - ✅ ❌ ⚠️ 🔄 emojis for status
- **Practical focus** - Show how to use, not just what exists

---

## Contributing Documentation

Found an error? Want to improve a feature document?

1. **Report issues**: GitHub Issues with `documentation` label
2. **Suggest improvements**: Open GitHub Discussion
3. **Submit updates**: Fork repo → edit docs → submit PR
4. **Follow template**: Use existing documents as guide

**Documentation source**: `docs/features/` in GitHub repository

---

## Additional Resources

### User Documentation
- [Main README](../../README.md) - Project overview and quick start
- [Entity Descriptions](../ENTITY_DESCRIPTIONS.md) - Complete sensor reference
- [Automation Examples](../HANGAR_AUTOMATION_EXAMPLES.md) - Practical automation ideas
- [Services Reference](../SERVICES.md) - All available services (if exists)

### Developer Documentation
- [Development Guide](../development/) - Code contribution guidelines
- [Architecture](../planning/) - Design documents and technical plans
- [Code Quality Tests](../CODE_QUALITY_TESTS.md) - Testing standards
- [Changelog](../../CHANGELOG.md) - Version history

### External Resources
- [Home Assistant Docs](https://www.home-assistant.io/docs/) - Home Assistant documentation
- [Aviation Safety](https://www.caa.co.uk/) - UK CAA resources
- [Weather Services](https://openweathermap.org/) - OpenWeatherMap API docs
- [NOTAM Information](https://pibs.nats.co.uk/) - UK NATS PIB service

---

## Feature Roadmap

### Upcoming Features (v2601.2.0+)

**In Development**:
- 🔄 Enhanced Setup Wizard with 40+ aircraft templates
- 🔄 Multi-country NOTAM support (EU, US FAA)
- 🔄 Historical weather logging and trend analysis
- 🔄 Flight log integration (track actual flights)

**Planned**:
- 🔄 CheckWX integration documentation (currently auto-configured)
- 🔄 Custom dashboard templates (minimal, instructor, student)
- 🔄 Voice-activated commands ("Show weather at Popham")
- 🔄 Mobile app companion (native iOS/Android)
- 🔄 Maintenance tracking integration
- 🔄 Fuel price monitoring

**Under Consideration**:
- 🔄 Aviation video feed integration (ADS-B, webcams)
- 🔄 Flight planning integration (SkyDemon, ForeFlight)
- 🔄 ATC frequency monitoring
- 🔄 ATIS/VOLMET audio integration

**Submit Feature Requests**: [GitHub Discussions](https://github.com/fregster/ha-hangar-assistant/discussions)

---

## Support & Community

**Found a Bug?** [Open an Issue](https://github.com/fregster/ha-hangar-assistant/issues)

**Have a Question?** [Ask in Discussions](https://github.com/fregster/ha-hangar-assistant/discussions)

**Want to Contribute?** [See Development Docs](../development/)

**Commercial Support**: Contact @fregster for flight school or aviation business support options

---

**Last Updated**: 22 January 2026  
**Documentation Version**: 1.0  
**Total Features Documented**: 5  
**Documentation Maintainer**: @fregster
