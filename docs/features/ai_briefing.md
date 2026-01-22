# AI Pre-Flight Briefing

**Feature**: AI-Generated Aviation Safety Briefings  
**Version**: 1.0 (v2601.1.0)  
**Status**: ✅ Available (Requires AI Service)

---

## Overview

The AI Pre-Flight Briefing feature generates comprehensive, pilot-focused safety briefings that synthesize weather conditions, NOTAMs, performance calculations, and regulatory compliance into natural language summaries. These briefings follow professional aviation briefing standards while adapting to your specific aircraft, airfield, and flight conditions.

**Before this feature**, pilots had to manually review 15+ individual sensors, cross-reference multiple data sources, perform mental calculations, and piece together a safety picture from raw numbers.

**With AI briefings**, all critical information is synthesized into a structured narrative briefing delivered via text, dashboard, or voice (TTS), saving 10-15 minutes of pre-flight preparation time.

---

## Key Benefits

✅ **Comprehensive** - Synthesizes 20+ sensors into one coherent briefing  
✅ **Professional Format** - Follows IMSAFE, PAVE, and standard briefing structure  
✅ **Context-Aware** - Adapts to your aircraft capabilities and airfield  
✅ **Spoken Delivery** - Text-to-speech for hands-free briefings  
✅ **Scheduled Updates** - Automatic morning briefings before flying  
✅ **GO/NO-GO Recommendations** - Clear safety guidance based on conditions  

---

## What's Included in a Briefing?

### 1. Current Conditions Summary
- Temperature, dew point, pressure (with units)
- Wind speed, direction, gusts
- Visibility and cloud conditions
- Weather phenomena (rain, fog, snow)

### 2. Performance Calculations
- **Density Altitude** - with impact on performance
- **Cloud Base** - VFR minima compliance
- **Crosswind Component** - vs. aircraft limits
- **Runway Recommendation** - best runway for conditions

### 3. Safety Alerts
- **Carburetor Icing Risk** - "Serious Risk" conditions highlighted
- **Airframe Icing** - temperature range warnings
- **Crosswind Limits** - aircraft capability vs. current conditions
- **Weather Data Age** - staleness warnings

### 4. NOTAMs (if enabled)
- Count of active NOTAMs
- Critical NOTAMs highlighted (runway closures, airspace restrictions)
- Effective dates and expiry times

### 5. Forecast Trends (if OWM enabled)
- **6-Hour Outlook** - hourly temperature, wind, cloud trends
- **3-Day Summary** - daily min/max, precipitation, conditions
- **Precipitation Timing** - "Rain in X minutes"
- **Government Alerts** - severe weather warnings

### 6. GO/NO-GO Recommendation
- **GO** - Conditions within limits
- **CAUTION** - Marginal conditions, brief considerations
- **NO-GO** - Conditions exceed aircraft/pilot/regulatory limits

### Example Briefing Output

```
HANGAR ASSISTANT PRE-FLIGHT BRIEFING
Popham Airfield (EGHP) - G-ABCD (Cessna 172)
Generated: 22 Jan 2026 06:30 UTC

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CURRENT CONDITIONS (as of 06:25 UTC):
Temperature: 8°C (46°F)
Dew Point: 5°C (41°F) - Spread 3°C
Pressure: 1013 hPa (29.92 inHg)
Wind: 270° at 12 knots, gusting 18 knots
Visibility: 10+ km
Sky: Few clouds at 4,000 ft

PERFORMANCE CALCULATIONS:
Density Altitude: 650 ft (field elevation 550 ft)
  → Performance within normal limits
Cloud Base: 1,200 ft AGL
  → Above VFR minima for local area flying
Crosswind Component: 12 knots on Runway 03
  → Within aircraft limits (15 knots max)
Best Runway: 03 (headwind component 6 knots)

SAFETY ALERTS:
✅ Weather data fresh (updated 5 minutes ago)
⚠️ CAUTION: Carburetor icing risk MODERATE
   Temperature 8°C, dew point spread 3°C
   → Apply carb heat during power reductions
✅ No airframe icing risk (temp above 0°C)
✅ Crosswind within limits

NOTAMS (2 active):
1. [CRITICAL] A0123/25 - RWY 21 CLOSED FOR MAINTENANCE
   Effective: 22 Jan 08:00 - 22 Jan 17:00 UTC
2. [INFO] A0124/25 - NDB POH U/S
   Effective: 20 Jan 00:00 - 20 Mar 23:59 UTC

FORECAST (Next 6 Hours):
06:00 → 12:00: Temperature rising 8→12°C
              Wind backing 270→250°, decreasing 12→8 knots
              Cloud base rising 4,000→6,000 ft
              Conditions IMPROVING through morning

3-DAY OUTLOOK:
• Thu 23 Jan: 4-10°C, W 10kt G20kt, 30% rain (2.5mm)
• Fri 24 Jan: 6-12°C, SW 8kt G15kt, Clear skies
• Sat 25 Jan: 8-14°C, S 5kt, Partly cloudy
  → Weekend looks favorable for cross-country

GOVERNMENT WEATHER ALERTS:
⚠️ STRONG WIND WARNING (Moderate severity)
   Effective: 22 Jan 06:00-18:00 UTC
   Gale force winds expected. Gusts 35-40 knots after 14:00.
   → Plan to return before 14:00 to avoid strong winds

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GO/NO-GO RECOMMENDATION: CAUTION

REASONS:
✅ Weather within VFR limits
✅ Performance margins acceptable
⚠️ Carburetor icing risk present - monitor closely
⚠️ Runway 21 closed - use Runway 03 only
⚠️ Strong winds forecast after 14:00 - plan early return

PILOT ACTIONS:
• Apply carb heat liberally during flight
• Avoid Runway 21 operations
• Monitor wind trends - plan to land before 14:00
• Review NOTAM A0123/25 details before taxi
• Cross-check official METAR before departure

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REGULATORY REMINDER:
This briefing is supplementary only. Always cross-reference
official sources (MET Office, NOTAM, AIP) before flight.

Safe flying!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Configuration

### AI Service Setup

**Required**: AI service integration (Gemini, OpenAI, etc.)

1. **Install AI Integration**:
   - Settings → Integrations → Add Integration
   - Search for "Google Generative AI" (Gemini) or "OpenAI Conversation"
   - Enter API key

2. **Configure in Hangar Assistant**:
   - Settings → Hangar Assistant → Configure → AI Settings
   - Select AI service entity
   - Configure briefing schedule (optional)

### Briefing Schedule

**Automatic Briefings** (optional):

| Setting | Description | Default | Example |
|---------|-------------|---------|---------|
| **Enabled** | Auto-generate briefings | `False` | Enable for morning briefings |
| **Time** | Briefing generation time | `06:00` | Before typical flying hours |
| **Days** | Days of week | All days | Mon-Sun for daily flying |
| **TTS Enabled** | Speak briefing via TTS | `False` | Enable for voice delivery |
| **TTS Entity** | Text-to-speech service | `None` | `tts.cloud` or `tts.google_translate` |
| **Media Player** | Audio output device | `None` | `media_player.kitchen` |

---

## Entities Created

### AI Briefing Sensor

**Entity ID**: `sensor.{airfield_slug}_ai_briefing`

**State**: Timestamp of last briefing generation

**Attributes**:
```yaml
state: "2026-01-22T06:30:15Z"
attributes:
  briefing_text: "HANGAR ASSISTANT PRE-FLIGHT BRIEFING\n..."
  go_no_go: "CAUTION"
  safety_alerts_count: 2
  critical_notams_count: 1
  conditions_summary: "VFR, carburetor icing risk moderate"
  generation_time_seconds: 3.2
  ai_model: "gemini-pro"
  word_count: 487
```

**Device Class**: `None` (custom sensor)

---

## Services

### refresh_ai_briefings

**Service**: `hangar_assistant.refresh_ai_briefings`

**Description**: Manually trigger AI briefing generation for all configured airfields

**Parameters**: None

**Example**:
```yaml
service: hangar_assistant.refresh_ai_briefings
```

**Use Cases**:
- Manual pre-flight briefing generation
- Button/script triggers
- Automation after weather update

---

### speak_briefing

**Service**: `hangar_assistant.speak_briefing`

**Description**: Speak the current AI briefing via TTS

**Parameters**:

| Parameter | Required | Description | Example |
|-----------|----------|-------------|---------|
| `tts_entity_id` | Yes | TTS engine entity | `tts.cloud` |
| `media_player_entity_id` | No | Target speaker | `media_player.kitchen` |

**Example**:
```yaml
service: hangar_assistant.speak_briefing
data:
  tts_entity_id: tts.cloud
  media_player_entity_id: media_player.hangar_speaker
```

**Behavior**:
- If no media player specified, uses browser media player (if available)
- Briefing spoken at normal speech rate (~150 words/min)
- Duration: ~3-5 minutes depending on conditions

---

## Use Cases

### Manual Pre-Flight Briefing

Button on dashboard triggers briefing generation and display:

```yaml
type: button
name: "Generate Pre-Flight Briefing"
icon: mdi:airplane-takeoff
tap_action:
  action: call-service
  service: hangar_assistant.refresh_ai_briefings
```

Display briefing text in dashboard:

```yaml
type: markdown
title: "Current Briefing"
content: >
  {{ state_attr('sensor.popham_ai_briefing', 'briefing_text') }}
```

---

### Automated Morning Briefing

Generate and speak briefing every morning:

```yaml
automation:
  - alias: "Morning Pre-Flight Briefing"
    trigger:
      - platform: time
        at: "06:00:00"
    condition:
      # Only on flying days (weekends for recreational pilots)
      - condition: time
        weekday:
          - sat
          - sun
    action:
      # Generate fresh briefing
      - service: hangar_assistant.refresh_ai_briefings
      # Wait for generation to complete
      - delay:
          seconds: 5
      # Speak briefing in kitchen
      - service: hangar_assistant.speak_briefing
        data:
          tts_entity_id: tts.cloud
          media_player_entity_id: media_player.kitchen
```

---

### Mobile Notification with Briefing

Send briefing to mobile app:

```yaml
automation:
  - alias: "Send Morning Briefing to Phone"
    trigger:
      - platform: time
        at: "06:30:00"
    action:
      - service: hangar_assistant.refresh_ai_briefings
      - delay:
          seconds: 5
      - service: notify.mobile_app_iphone
        data:
          title: "☀️ Morning Briefing - Popham"
          message: >
            {{ state_attr('sensor.popham_ai_briefing', 'conditions_summary') }}
            
            GO/NO-GO: {{ state_attr('sensor.popham_ai_briefing', 'go_no_go') }}
          data:
            actions:
              - action: "VIEW_FULL_BRIEFING"
                title: "View Full Briefing"
```

---

### Pre-Departure Checklist Integration

Trigger briefing when pre-flight checklist starts:

```yaml
automation:
  - alias: "Pre-Flight Checklist Started"
    trigger:
      - platform: state
        entity_id: input_boolean.preflight_checklist_active
        to: "on"
    action:
      # Generate fresh briefing
      - service: hangar_assistant.refresh_ai_briefings
      # Wait for generation
      - delay:
          seconds: 5
      # Display on hangar tablet
      - service: browser_mod.navigate
        data:
          path: /hangar-briefing
          device_id: hangar_tablet
      # Optional: Speak briefing
      - service: hangar_assistant.speak_briefing
        data:
          tts_entity_id: tts.cloud
```

---

### Weather Change Alert with Briefing

Trigger new briefing when significant weather change detected:

```yaml
automation:
  - alias: "Weather Deterioration - Generate New Briefing"
    trigger:
      # Wind increased significantly
      - platform: numeric_state
        entity_id: sensor.popham_wind_speed
        above: 15
      # Or carb icing risk increased
      - platform: state
        entity_id: sensor.popham_carb_risk
        to: "Serious Risk"
    action:
      - service: hangar_assistant.refresh_ai_briefings
      - service: notify.all_devices
        data:
          title: "⚠️ Weather Change Detected"
          message: "New briefing generated due to changing conditions. Review before flight."
```

---

## Troubleshooting

### Briefing Not Generating

**Symptoms**: Service called but sensor state doesn't update

**Causes**:
1. AI service not configured or unavailable
2. API key invalid or expired
3. Rate limit exceeded on AI service
4. Required sensors missing or unavailable

**Solutions**:
- Verify AI service entity exists: Developer Tools → States
- Check AI service logs for errors
- Test AI service independently: Developer Tools → Services → `conversation.process`
- Ensure temperature, wind, pressure sensors available
- Check API quota/billing on AI provider dashboard

---

### Briefing Text Incomplete or Cut Off

**Symptoms**: Briefing ends abruptly or missing sections

**Causes**:
1. AI model response truncated (token limit)
2. Network timeout during generation
3. Complex conditions requiring longer response

**Solutions**:
- Use AI model with higher token limits (e.g., Gemini Pro vs. Flash)
- Simplify configured data (disable unused integrations temporarily)
- Increase timeout in AI service configuration
- Retry generation - variability in AI responses

---

### TTS Not Speaking Briefing

**Symptoms**: `speak_briefing` service completes but no audio

**Causes**:
1. TTS entity invalid or unavailable
2. Media player entity offline or muted
3. Briefing text empty (no briefing generated yet)
4. TTS service rate limited

**Solutions**:
- Test TTS service independently: Settings → TTS → Test
- Verify media player online: Developer Tools → States
- Generate briefing first: `refresh_ai_briefings` → wait 5s → `speak_briefing`
- Check media player volume/mute status
- Try alternative TTS engine: `tts.google_translate` (free)

---

### Inaccurate GO/NO-GO Recommendations

**Symptoms**: AI recommends GO when conditions seem marginal (or vice versa)

**Causes**:
1. Aircraft limits not configured correctly
2. Missing sensor data (AI assumes safe defaults)
3. AI model interpretation variability
4. Pilot experience level not factored

**Solutions**:
- Verify aircraft crosswind limits in configuration
- Ensure all weather sensors online and reporting
- Review briefing text for reasoning behind recommendation
- **Always use pilot judgment** - AI is advisory only
- Update prompts in `prompts/preflight_brief.txt` if needed

---

### Briefing Doesn't Include Forecasts/NOTAMs

**Symptoms**: Briefing missing forecast or NOTAM sections

**Causes**:
1. OpenWeatherMap integration disabled (no forecasts)
2. NOTAM integration disabled
3. Airfield configured without these integrations

**Solutions**:
- Enable OWM: Settings → Integrations → OWM → Enable
- Enable NOTAMs: Settings → Integrations → NOTAMs → Enable
- Verify airfield uses integrations: Airfield settings → Data sources
- Generate new briefing after enabling integrations

---

## FAQ

### Is an AI subscription required?

**Yes.** AI briefings require one of:
- **Google Gemini** (free tier available, paid for higher limits)
- **OpenAI GPT** (paid subscription, ~$20/month)
- **Other Home Assistant-compatible AI services**

**Cost considerations**:
- 1 briefing = ~1,000-2,000 tokens
- Gemini free tier: 60 requests/minute (sufficient)
- OpenAI: ~$0.01-0.03 per briefing

**Recommendation**: Start with Gemini free tier.

---

### How long does briefing generation take?

**Typical**: 3-5 seconds

**Factors affecting speed**:
- AI model (Gemini Flash ~1s, GPT-4 ~5s)
- Network latency
- Complexity (NOTAMs, forecasts add data)
- API service load

**Best practice**: Call `refresh_ai_briefings` at least 10 seconds before `speak_briefing`.

---

### Can I customize the briefing format?

**Yes!** Briefing prompts stored in `custom_components/hangar_assistant/prompts/preflight_brief.txt`

**Advanced users** can edit this file to:
- Change briefing structure
- Add/remove sections
- Adjust language/tone
- Include custom checkpoints

**Note**: Requires integration reload after changes.

---

### Are briefings stored historically?

**No.** Only the most recent briefing is stored in the sensor state. For historical logging:

```yaml
# Create history sensor
- platform: template
  sensors:
    briefing_history:
      value_template: "{{ states('sensor.popham_ai_briefing') }}"
      attribute_templates:
        briefing_text: "{{ state_attr('sensor.popham_ai_briefing', 'briefing_text') }}"
        timestamp: "{{ now() }}"
```

Then use **Recorder** integration to log to database.

---

### Can briefings be printed?

**Indirectly** - Save briefing text to file:

```yaml
automation:
  - alias: "Save Briefing to File"
    trigger:
      - platform: state
        entity_id: sensor.popham_ai_briefing
    action:
      - service: notify.pdf_file
        data:
          message: "{{ state_attr('sensor.popham_ai_briefing', 'briefing_text') }}"
          title: "Pre-Flight Briefing {{ now().strftime('%Y-%m-%d %H:%M') }}"
```

Or use **File Notification** to save as text:

```yaml
notify:
  - platform: file
    name: briefing_log
    filename: /config/www/briefings/briefing_{{ now().strftime('%Y%m%d_%H%M') }}.txt
```

---

### Are briefings compliant with aviation regulations?

**No!** Briefings are **supplementary only** and do NOT replace:
- Official METAR/TAF
- NOTAMs from official sources (NATS, FAA)
- AIP/Chart review
- Pilot judgment and decision-making

**Use AI briefings** as a starting point and always cross-reference official sources.

---

### Can I generate briefings for multiple airfields?

**Yes!** `refresh_ai_briefings` generates briefings for **all configured airfields** simultaneously.

Each airfield gets its own sensor:
- `sensor.popham_ai_briefing`
- `sensor.biggin_hill_ai_briefing`
- `sensor.headcorn_ai_briefing`

**Cost consideration**: More airfields = more AI API calls. Budget accordingly.

---

### Does it work offline?

**No.** AI briefings require:
- Internet connectivity
- Active AI service subscription
- Home Assistant online

**Fallback**: Review individual sensors manually if internet unavailable.

---

## Best Practices

### For Student Pilots

1. **Morning routine**: Auto-generate briefing at 06:00 for lesson review
2. **Pre-flight**: Read full briefing text, don't just rely on GO/NO-GO
3. **Instructor review**: Discuss briefing with instructor before flight
4. **Learn from AI**: Note how AI synthesizes data for situational awareness
5. **Cross-reference**: Always check official METAR/TAF with instructor

---

### For Private Pilots

1. **Night-before planning**: Generate briefing evening before cross-country
2. **Morning refresh**: Regenerate briefing morning-of for updated conditions
3. **Mobile alerts**: Push briefing summary to phone before leaving home
4. **Voice briefings**: Speak briefing while performing pre-flight inspection
5. **Trend monitoring**: Compare briefings over 24 hours for weather trends

---

### For Flight Schools

1. **Daily briefing board**: Display all airfield briefings in briefing room
2. **Student awareness**: Teach students to generate and interpret briefings
3. **Standardization**: Use AI briefings as baseline for instructor briefings
4. **Safety culture**: Automate alerts when NO-GO conditions detected
5. **Record keeping**: Log briefings for post-flight incident analysis

---

### For Cross-Country Planning

1. **Departure + destination briefings**: Generate for both airfields
2. **Route weather**: Include enroute alternates in configuration
3. **Trend analysis**: Generate briefings 24h, 12h, and 2h before departure
4. **Forecast integration**: Use OWM 3-day outlook for go/no-go decision
5. **Enroute updates**: Mobile app notifications if conditions change

---

## Technical Details

### Prompt Engineering

Briefing prompts located in `prompts/preflight_brief.txt` include:
- Aviation-specific terminology
- Structured output format requirements
- Safety-first decision-making logic
- Context injection (aircraft type, pilot experience, etc.)

**Prompt structure**:
1. **System role**: "You are an experienced flight instructor..."
2. **Data injection**: Current conditions, NOTAMs, forecasts
3. **Output format**: Structured sections, markdown formatting
4. **Safety guidance**: GO/NO-GO criteria

---

### Data Sources

AI briefings synthesize:
- **Home Assistant sensors**: Temperature, wind, pressure, humidity
- **Calculated values**: Density altitude, cloud base, crosswind
- **NOTAM data**: UK NATS PIB XML (if enabled)
- **Forecast data**: OpenWeatherMap API (if enabled)
- **Aircraft data**: Type, performance limits, crosswind limits
- **Airfield data**: ICAO, elevation, runway configuration

---

### Performance Considerations

**Cache briefing text**: Sensor state cached to prevent redundant AI calls

**Rate limiting**: Integration tracks AI API calls (no automatic rate limiting - monitor manually)

**Async generation**: Briefing generation non-blocking, Home Assistant responsive during generation

---

### Security & Privacy

**API keys**: Never logged, stored in config entry (encrypted at rest)

**Briefing text**: Stored in sensor state (accessible via dashboard/automations)

**No external storage**: Briefings not sent to third parties beyond AI service

**Data sanitization**: All user input sanitized before inclusion in prompts

---

## Related Documentation

- [Setup Wizard](setup_wizard.md) - Initial configuration walkthrough
- [NOTAM Integration](notam_integration.md) - NOTAM data in briefings
- [OpenWeatherMap Integration](openweathermap_integration.md) - Forecast data in briefings
- [Services Reference](../SERVICES.md) - Detailed service documentation
- [Automation Examples](../HANGAR_AUTOMATION_EXAMPLES.md) - Briefing automation ideas

---

## Version History

### v1.0 (v2601.1.0 - January 2026)
- ✅ Initial release with Gemini/OpenAI support
- ✅ Structured briefing format (conditions, performance, safety, forecasts)
- ✅ GO/NO-GO recommendations
- ✅ TTS delivery via `speak_briefing` service
- ✅ Scheduled briefing generation
- ✅ NOTAM and forecast integration
- ✅ Mobile notification support

### Planned Enhancements (v2601.2.0+)
- 🔄 Multi-language briefings (French, German, Spanish)
- 🔄 Pilot experience level customization (student, PPL, CPL)
- 🔄 Custom briefing templates (VFR, IFR, cross-country, local)
- 🔄 Historical briefing comparison ("conditions 24 hours ago")
- 🔄 Voice-interactive briefings (ask follow-up questions)
- 🔄 PDF generation for briefing printouts
- 🔄 Flight school-specific briefing formats

---

**Last Updated**: 22 January 2026  
**Feature Version**: 1.0  
**Target Users**: All pilots (student through CPL)  
**Difficulty Level**: Intermediate (requires AI service setup)  
**Cost**: AI service subscription required (~£0-20/month)
