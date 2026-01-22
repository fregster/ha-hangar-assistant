# Setup Wizard

**Feature**: Guided First-Time Setup Experience  
**Version**: 1.0 (v2601.2.0)  
**Status**: ✅ Available

---

## Overview

The Setup Wizard is a guided 7-step onboarding experience that helps you configure Hangar Assistant in less than 15 minutes. Whether you're a student pilot or an experienced aviator, the wizard walks you through every configuration step with clear instructions, real-time validation, and helpful examples.

**Before the wizard existed**, setting up Hangar Assistant required manually navigating complex menus, understanding Home Assistant concepts, and often took 30-45 minutes with a 40% abandonment rate.

**With the wizard**, first-time setup is streamlined to 10-15 minutes with an expected 80%+ completion rate.

---

## When Does the Wizard Appear?

The wizard **automatically launches** when you install Hangar Assistant for the first time. It detects fresh installations by checking if you have any configured airfields or aircraft.

**Existing users** will continue using the manual configuration options - your setup is never disrupted.

**Skipping the wizard**: If you prefer manual configuration, you can skip the wizard and access all settings through Settings → Integrations → Hangar Assistant → Configure.

---

## The 7-Step Journey

### Step 1: Welcome Screen

**What you'll see**: Overview of Hangar Assistant's capabilities and what the wizard will help you configure

**Time estimate**: 10-15 minutes for complete setup

**Options**:
- **Use Setup Wizard** (recommended) - Guided configuration
- **Skip to Manual Configuration** - Direct access to settings

---

### Step 2: General Settings

**What you'll configure**:
- **Language**: English, German, Spanish, or French
- **Unit Preference**: Aviation units (feet, knots, nautical miles) or SI units (meters, km/h, kilometers)
- **Cache Settings**: How long to keep sensor data (15-60 minutes)

**Why this matters**: These global settings affect how all data is displayed throughout Hangar Assistant and your dashboards.

**Time**: ~1 minute

---

### Step 3: API Integrations (Optional)

**What you'll configure**: External data sources for enhanced weather and operational data

#### CheckWX (FREE) ✅
- **What it provides**: Real-time METAR, TAF, and airfield station data
- **Setup**: Free API key (30 seconds to sign up)
- **Cache settings**: 15-60 minutes for METAR, 3-12 hours for TAF
- **Benefits**: Auto-populate airfield data, live weather conditions
- **Sign up**: [checkwxapi.com](https://www.checkwxapi.com/signup)

#### OpenWeatherMap (Paid) ⚠️
- **What it provides**: Forecasts, precipitation alerts, government weather warnings
- **Cost**: ~$10-30/month depending on usage
- **Setup**: API key from your OWM account
- **Cache settings**: 5-60 minute update intervals
- **Benefits**: 48-hour hourly forecasts, 8-day daily forecasts, weather alerts
- **Sign up**: [openweathermap.org/api](https://openweathermap.org/api)

#### NOTAMs (FREE, Auto-Enabled) ✅
- **What it provides**: UK NATS Notice to Airmen data
- **Setup**: None required - automatically enabled for UK airfields
- **Update schedule**: Daily at 02:00
- **Cache retention**: 7 days

**Options**:
- Configure CheckWX now
- Configure OpenWeatherMap now
- Skip (configure later)

**Time**: 2 minutes (or skip if you prefer sensor-based data only)

---

### Step 4: Add Your First Airfield

**What you'll configure**: Your home airfield or most frequently used airport

**Required information**:
- **ICAO Code**: 4-letter airport code (e.g., EGHP for Popham, KJFK for JFK)
- **Airfield Name**: Display name (e.g., "Popham Airfield")
- **Coordinates**: Latitude and longitude (decimal degrees)
- **Elevation**: Field elevation in feet or meters

**Smart features**:
- **Real-time ICAO validation**: Instant feedback on valid codes
- **Auto-population**: If CheckWX is configured, airfield data loads automatically
- **Examples provided**: Each field shows format examples

**Time**: 2 minutes (30 seconds with auto-population)

---

### Step 5: Add a Hangar (Optional)

**What you'll configure**: If you keep your aircraft in a hangar with its own environmental sensors

**Information needed**:
- **Hangar Name**: Descriptive name (e.g., "North Hangar", "My Hangar at Popham")
- **Associated Airfield**: Links hangar to the airfield from Step 4
- **Temperature Sensor**: Link existing Home Assistant sensor (optional)
- **Humidity Sensor**: Link existing Home Assistant sensor (optional)

**Why hangars matter**: Aircraft stored in hangars may experience different conditions than airfield weather stations. Hangar-specific sensors provide more accurate performance calculations.

**Options**:
- Configure hangar now
- Skip (you can add hangars later via Settings)

**Time**: 1 minute (or skip)

---

### Step 6: Add Your Aircraft

**What you'll configure**: Your aircraft's specifications for performance calculations and safety alerts

**Required information**:
- **Registration**: Aircraft tail number (e.g., G-ABCD, N12345, D-EFGH)
- **Type**: Aircraft make and model

**Aircraft Templates** (Auto-fill specs):
- **Cessna 172 Skyhawk**: Most popular trainer
- **Piper PA-28 Cherokee/Warrior**: Popular trainer and cross-country aircraft
- **Diamond DA40**: Modern composite trainer
- **Cirrus SR20**: High-performance single
- **Robin DR400**: French touring aircraft
- **Glider**: Soaring aircraft
- **Tecnam P2008**: Light sport aircraft

**Template benefits**: Selecting a template automatically fills:
- Maximum Takeoff Weight (MTOW)
- Typical cruise speed
- Fuel capacity
- Performance limitations
- Crosswind limits

**Manual entry**: If your aircraft isn't in the templates, you can enter specifications manually

**Time**: 1 minute (with template) or 3 minutes (manual)

---

### Step 7: Link Weather Sensors (Optional)

**What you'll configure**: Connect existing Home Assistant weather sensors for real-time data

**Sensors you can link**:
- **Temperature**: For density altitude calculations
- **Humidity**: For carburetor icing risk
- **Pressure**: For altimeter settings and density altitude
- **Wind Speed**: For crosswind components and runway selection
- **Wind Direction**: For runway selection and safety alerts

**When to use sensors vs. APIs**:
- **Sensors**: You have weather station hardware at your airfield (most accurate)
- **APIs**: You don't have local sensors (CheckWX/OWM provide data)
- **Hybrid**: Both (sensors primary, API as backup)

**Options**:
- Link sensors now
- Skip (APIs will be used if configured, or you can add sensors later)

**Time**: 2 minutes (or skip)

---

### Step 8: Install Dashboard

**What you'll configure**: How to install the Glass Cockpit dashboard

**The Glass Cockpit Dashboard** is a beautiful, aviation-themed Lovelace dashboard that displays:
- Live weather conditions and trends
- Density altitude and performance warnings
- Runway selection with crosswind components
- Carburetor icing risk alerts
- NOTAMs and weather alerts
- Fuel calculations and endurance
- AI-generated pre-flight briefings

**Installation Methods**:

#### Automatic (Recommended) ✨
- **How it works**: Dashboard installs automatically in 2-3 seconds
- **What happens**: Dashboard appears in your sidebar immediately
- **Best for**: Most users (easiest option)

#### Manual (Advanced)
- **How it works**: Wizard generates complete YAML with instructions
- **What happens**: You copy/paste YAML into Home Assistant's dashboard editor
- **Best for**: Users who want to customize before installation
- **Instructions included**: 9-step guide in the YAML file

#### Skip (Install Later)
- **How it works**: Wizard completes without dashboard
- **What happens**: You can run `install_dashboard` service anytime via Developer Tools
- **Best for**: Advanced users who prefer custom dashboards

**Time**: 1 minute

---

## After the Wizard

### What Gets Created

Once you complete the wizard, Hangar Assistant creates:

1. **Config Entry**: Stores all your settings (language, units, API keys)
2. **Airfield Entity**: Represents your configured airfield
3. **Aircraft Entity**: Represents your configured aircraft
4. **Sensors**: 20+ sensors including:
   - Density altitude
   - Cloud base estimation
   - Carburetor icing risk
   - Crosswind components
   - Weather data age
   - AI pre-flight briefing
5. **Binary Sensors**: Safety alerts including:
   - Master safety alert
   - Weather data freshness
   - Crosswind limits
   - Performance warnings
6. **Select Entities**: For switching between airfields/aircraft
7. **Dashboard** (if installed): Glass Cockpit with all configured entities

### What You Can Do Immediately

**View Real-Time Conditions**:
- Check your airfield's current density altitude
- See carburetor icing risk
- Monitor cloud base estimations

**Receive Safety Alerts**:
- Crosswind exceeds your aircraft's limits
- Weather data becomes stale
- Unsafe flying conditions detected

**Generate AI Briefings**:
- Run `hangar_assistant.refresh_ai_briefings` service
- Receive comprehensive pre-flight safety briefings
- Spoken briefings via TTS (text-to-speech)

**Use the Glass Cockpit Dashboard**:
- Open from sidebar (if auto-installed)
- View all aviation data in one place
- Responsive design works on mobile, tablet, and desktop

### Adding More Configuration

You can always add more airfields, aircraft, and hangars:

1. Go to **Settings** → **Devices & Services**
2. Find **Hangar Assistant**
3. Click **Configure**
4. Use the options menu to add:
   - Additional airfields
   - More aircraft
   - Hangars with sensors
   - API integrations
   - Dashboard settings

---

## Troubleshooting

### Wizard Won't Appear

**Symptoms**: You installed Hangar Assistant but the wizard didn't launch

**Causes**:
1. You already have airfields or aircraft configured (not a first-time install)
2. Setup completion flag is set (from a previous partial setup)

**Solutions**:
- Use the manual configuration: Settings → Integrations → Hangar Assistant → Configure
- Delete and reinstall the integration (⚠️ loses all data)

### ICAO Code Not Recognized

**Symptoms**: Wizard says ICAO code is invalid

**Causes**:
1. Code is lowercase (must be uppercase: EGHP not eghp)
2. Code is not exactly 4 characters
3. Code contains spaces or special characters

**Solutions**:
- Use uppercase 4-letter codes only
- Examples: EGHP (UK), KJFK (US), LFPG (France), EDDF (Germany)

### CheckWX Auto-Population Fails

**Symptoms**: After entering ICAO code, data doesn't load automatically

**Causes**:
1. API key not configured or invalid
2. ICAO code not in CheckWX database
3. Network connectivity issues

**Solutions**:
- Verify API key is correct (32+ characters)
- Try a major airport ICAO first (e.g., KJFK)
- Use manual entry if auto-population unavailable

### Aircraft Template Doesn't Match

**Symptoms**: Template specs don't match your aircraft's POH (Pilot Operating Handbook)

**Causes**:
1. Template is for a different variant (e.g., Cessna 172N vs 172S)
2. Your aircraft has modifications (e.g., STOL kit)

**Solutions**:
- Use template as starting point, then edit values manually
- Configure via Settings after wizard completion
- Submit a feature request for your specific aircraft variant

### Dashboard Doesn't Appear

**Symptoms**: Selected "Automatic" but dashboard not in sidebar

**Causes**:
1. Background installation task still running (wait 5 seconds)
2. Dashboard installation failed (check logs)
3. Lovelace service unavailable

**Solutions**:
- Refresh browser (Ctrl+F5 or Cmd+Shift+R)
- Check Home Assistant logs for errors
- Run `install_dashboard` service manually via Developer Tools
- Use "Manual" method and install via UI

---

## FAQ

### Can I change settings after completing the wizard?

**Yes!** All settings are editable:
- Go to Settings → Integrations → Hangar Assistant → Configure
- Add/edit/remove airfields, aircraft, hangars
- Update API keys and cache settings
- Change language and units

### Can I run the wizard again?

**No, not automatically.** Once completed, the wizard won't appear again. This prevents disrupting your existing configuration.

**Alternative**: Use the options flow (Settings → Configure) which provides the same functionality in menu form.

### What if I skip a step?

**No problem!** Optional steps can be skipped:
- API integrations (Step 3)
- Hangar configuration (Step 5)
- Sensor linking (Step 7)
- Dashboard installation (Step 8)

You can configure these later via Settings.

### Do I need APIs for the integration to work?

**No!** APIs are optional enhancements:
- **Sensors only**: Use Home Assistant weather sensors (most accurate for your location)
- **APIs only**: Use CheckWX/OpenWeatherMap without local sensors
- **Both**: Best of both worlds - sensors as primary, APIs as backup/enrichment

### What happens to my data if I uninstall?

**All data is deleted** when you remove the integration:
- Config entry (settings, airfields, aircraft)
- All entities (sensors, binary sensors)
- Dashboard (if installed automatically)

**Before uninstalling**: Export YAML dashboard if you want to keep it.

### Can I use this for multiple airfields?

**Yes!** Add multiple airfields via Settings → Configure after wizard completion. Each airfield gets its own set of sensors and can be selected via the airfield selector entity.

### Can I track multiple aircraft?

**Yes!** Add multiple aircraft via Settings → Configure. Each aircraft gets its own performance sensors and safety alerts. Switch between aircraft using the aircraft selector entity.

### Is this suitable for commercial operations?

**No!** Hangar Assistant is for **recreational flying only**:
- Not certified for commercial aviation
- Not approved by CAA/FAA/EASA
- Should not be used as sole source of operational data
- Always cross-reference with official sources (MET office, NOTAMs, AIP)

---

## Best Practices

### For Student Pilots

1. **Start with your training airfield**: Configure your school's location first
2. **Use aircraft templates**: Select your primary trainer (e.g., Cessna 172)
3. **Enable all safety alerts**: Crosswind, density altitude, carburetor icing
4. **Link school weather station**: If your school has Home Assistant sensors
5. **Auto-install dashboard**: Easiest way to see all data during pre-flight

### For Private Pilots

1. **Configure home airfield + destinations**: Add airfields you frequently visit
2. **Link your home weather station**: Most accurate data for your hangar
3. **Configure both API integrations**: CheckWX (free) for basics, OWM (paid) for forecasts
4. **Use aircraft templates then customize**: Adjust for your specific aircraft variant
5. **Enable AI briefings**: Get comprehensive safety briefings before each flight

### For Glider Pilots

1. **Use "Glider" template**: Pre-configured for soaring operations
2. **Focus on weather sensors**: Thermals, wind speed, cloud base critical
3. **Enable CheckWX**: Free METAR/TAF for cross-country planning
4. **Link multiple airfields**: Home field plus common landing-out sites
5. **Customize dashboard**: Emphasize cloud base, visibility, wind patterns

### For Light Sport Aircraft (LSA)

1. **Use "Tecnam P2008" template** (or closest match)
2. **Enable crosswind alerts**: LSA have stricter limits
3. **Monitor density altitude**: Performance margins tighter than GA aircraft
4. **Link hangar sensors**: Small aircraft more sensitive to temperature/humidity
5. **Enable all safety features**: Lower operational margins require more monitoring

---

## Technical Details

### Wizard State Management

The wizard uses a `SetupWizardState` class to track your progress:
- Current step (1-7)
- Completed steps
- Progress percentage
- All configuration data

**Progress is saved** between steps, so you can close and resume (though config entry isn't created until Step 8 completes).

### Validation Rules

**ICAO Codes**: Must match pattern `^[A-Z]{4}$` (exactly 4 uppercase letters)

**Aircraft Registrations**:
- UK: `G-XXXX` (G- prefix, 4 alphanumeric characters)
- US: `N12345` (N prefix, 1-5 alphanumeric characters)
- Germany: `D-XXXX` (D- prefix, 4 alphanumeric characters)
- Other formats accepted with warnings

**API Keys**:
- CheckWX: 32+ characters, alphanumeric
- OpenWeatherMap: 32 hexadecimal characters

**Coordinates**: Decimal degrees format, validated ranges

### Background Tasks

When you select "Automatic" dashboard installation:
1. Wizard completes and creates config entry
2. Background task scheduled (non-blocking)
3. Task sleeps 2 seconds (ensures entry fully initialized)
4. `install_dashboard` service called with `method=automatic`
5. Dashboard installs via Lovelace API
6. Success logged, dashboard appears in sidebar

**Why the delay?** Config entry needs time to fully initialize in Home Assistant's internal registry. The 2-second delay prevents service calls before the entry is ready.

### Backward Compatibility

**Existing installations** are never affected:
- Wizard detection checks for existing data
- Setup completion flag prevents re-triggering
- Manual configuration remains available
- No breaking changes to config entry structure

---

## Related Documentation

- [Aircraft Templates](aircraft_templates.md) - Full list of pre-configured aircraft
- [API Integrations](api_integrations.md) - Detailed setup guides for CheckWX, OWM, NOTAMs
- [Dashboard Guide](dashboard_guide.md) - Using the Glass Cockpit dashboard
- [Sensor Reference](../ENTITY_DESCRIPTIONS.md) - Complete sensor list and descriptions
- [Automation Examples](../HANGAR_AUTOMATION_EXAMPLES.md) - Pre-flight automation ideas

## Technical Details (Advanced)

<details>
<summary>Click to expand technical implementation details</summary>

For developers and advanced users interested in the underlying architecture of the Setup Wizard, comprehensive technical documentation is available covering:

- **State Management**: SetupWizardState dataclass and progress tracking
- **Flow Sequence**: Complete step-by-step implementation details (async_step_* methods)
- **Data Model**: How wizard data maps to config entry structure
- **Background Task Management**: Dashboard installation async task pattern
- **Validation Logic**: Real-time input validation and API connection testing
- **Integration Points**: How the wizard triggers entity creation
- **Performance Considerations**: Template caching and memory management

**Read the technical documentation**: [docs/implemented/setup_wizard_technical.md](../implemented/setup_wizard_technical.md)

</details>

---

## Version History

### v1.0 (v2601.2.0 - 22 January 2026)
- ✅ Initial release with 7-step guided wizard
- ✅ API integration flows (CheckWX, OpenWeatherMap, NOTAMs)
- ✅ Aircraft templates (7 types)
- ✅ Automatic dashboard installation
- ✅ Manual YAML generation with instructions
- ✅ Real-time validation for all inputs
- ✅ Progress tracking and skip options

### Planned Enhancements (v2601.3.0+)
- 🔄 40+ aircraft templates (currently 7)
- 🔄 Quick-start scenarios (student, PPL, CPL, glider)
- 🔄 Enhanced validation rules
- 🔄 Screenshot gallery in wizard
- 🔄 Tutorial video integration
- 🔄 Complete translations (DE, ES, FR)
- 🔄 "Download YAML" button for manual installation

---

**Last Updated**: 22 January 2026  
**Feature Version**: 1.0  
**Target Users**: Student pilots, private pilots, flight instructors, aviation enthusiasts  
**Difficulty Level**: Beginner (no Home Assistant experience required)
