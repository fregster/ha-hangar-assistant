# Hangar Automation Examples

This document provides practical automation examples using the hangar management system in Hangar Assistant.

## Overview

Hangars in Hangar Assistant can have:
- **Temperature sensors**: Monitor hangar internal temperature
- **Humidity sensors**: Track moisture levels for corrosion prevention
- **Location association**: Link aircraft to specific hangars at airfields

These features enable location-based automation for aircraft maintenance and safety.

---

## Example 1: Aircraft Oil Heater Control

Automatically start an oil heater when approaching the hangar and temperature is below threshold.

### Requirements
- Hangar with temperature sensor configured
- Oil heater controllable switch/plug
- Location tracking (device_tracker or person entity)
- Zone defined for the airfield

### Automation YAML

```yaml
automation:
  - alias: "Start Aircraft Oil Heater When Near Cold Hangar"
    description: "Preheat engine oil when approaching hangar and temp < 5°C"
    
    trigger:
      # Trigger when hangar temperature drops below threshold
      - platform: numeric_state
        entity_id: sensor.popham_hangar_3_temperature
        below: 5
    
    condition:
      # Only activate if approaching the hangar
      - condition: zone
        entity_id: device_tracker.phone
        zone: zone.popham_airfield
      # Only during daylight hours (optional safety check)
      - condition: sun
        after: sunrise
        before: sunset
      # Prevent repeated activations (cooldown period)
      - condition: template
        value_template: >
          {{ (as_timestamp(now()) - as_timestamp(states.switch.hangar3_oil_heater_g_abcd.last_changed)) > 3600 }}
    
    action:
      # Turn on the oil heater
      - service: switch.turn_on
        target:
          entity_id: switch.hangar3_oil_heater_g_abcd
      
      # Send notification
      - service: notify.mobile_app
        data:
          title: "Aircraft Preheating Started"
          message: >
            Oil heater activated for G-ABCD. Hangar 3 temperature: 
            {{ states('sensor.popham_hangar_3_temperature') }}°C
          data:
            priority: high
            ttl: 0
    
    mode: single
```

### Enhancements

**Distance-based activation:**
```yaml
condition:
  - condition: template
    value_template: >
      {% set hangar_lat = 51.2 %}
      {% set hangar_lon = -1.2 %}
      {% set my_lat = state_attr('device_tracker.phone', 'latitude') %}
      {% set my_lon = state_attr('device_tracker.phone', 'longitude') %}
      {{ distance(hangar_lat, hangar_lon, my_lat, my_lon) < 5 }}
```

**Time-based preheating:**
```yaml
trigger:
  - platform: time
    at: "07:00:00"

condition:
  - condition: numeric_state
    entity_id: sensor.popham_hangar_3_temperature
    below: 5
  - condition: state
    entity_id: calendar.flight_schedule
    state: "on"
```

---

## Example 2: Hangar Humidity Alert (Corrosion Prevention)

Alert when hangar humidity exceeds safe limits for prolonged periods.

### Requirements
- Hangar with humidity sensor configured
- Notification service configured

### Automation YAML

```yaml
automation:
  - alias: "Alert: High Humidity in Hangar"
    description: "Warn of corrosion risk when humidity remains high"
    
    trigger:
      - platform: numeric_state
        entity_id: sensor.popham_hangar_3_humidity
        above: 80
        for:
          hours: 2
    
    action:
      # Send persistent notification
      - service: persistent_notification.create
        data:
          title: "⚠️ Hangar Humidity Warning"
          message: >
            Hangar 3 humidity has been above 80% for 2 hours.
            Current: {{ states('sensor.popham_hangar_3_humidity') }}%
            
            Recommended actions:
            - Run dehumidifier
            - Check for water ingress
            - Inspect aircraft covers
          notification_id: "hangar_humidity_warning"
      
      # Send mobile notification
      - service: notify.mobile_app
        data:
          title: "Hangar Humidity Alert"
          message: "Hangar 3: {{ states('sensor.popham_hangar_3_humidity') }}% (>2hrs)"
          data:
            priority: high
            tag: "hangar_humidity"
            actions:
              - action: "DISMISS"
                title: "Dismiss"
              - action: "VIEW_HANGAR"
                title: "View Hangar"
    
    mode: single
```

### Enhancements

**Automatic dehumidifier control:**
```yaml
action:
  - service: switch.turn_on
    target:
      entity_id: switch.hangar3_dehumidifier
  
  - wait_template: >
      {{ states('sensor.popham_hangar_3_humidity') | float < 70 }}
    timeout: '04:00:00'
  
  - service: switch.turn_off
    target:
      entity_id: switch.hangar3_dehumidifier
```

---

## Example 3: Hangar Occupancy Tracking (Future Feature)

Track which aircraft are currently in which hangars based on location or manual tracking.

### Requirements
- Aircraft GPS tracker or manual input_boolean helpers
- Hangar configured in Hangar Assistant

### Helper Setup

```yaml
input_boolean:
  aircraft_g_abcd_in_hangar:
    name: "G-ABCD in Hangar 3"
    icon: mdi:airplane-landing

input_datetime:
  aircraft_g_abcd_last_seen:
    name: "G-ABCD Last Seen"
    has_date: true
    has_time: true
```

### Automation YAML

```yaml
automation:
  - alias: "Track Aircraft Hangar Entry"
    description: "Log when aircraft enters hangar"
    
    trigger:
      - platform: state
        entity_id: input_boolean.aircraft_g_abcd_in_hangar
        to: "on"
    
    action:
      # Update last seen timestamp
      - service: input_datetime.set_datetime
        target:
          entity_id: input_datetime.aircraft_g_abcd_last_seen
        data:
          datetime: "{{ now().isoformat() }}"
      
      # Log to logbook
      - service: logbook.log
        data:
          name: "Aircraft Movement"
          message: "G-ABCD entered Hangar 3"
          entity_id: input_boolean.aircraft_g_abcd_in_hangar
      
      # Update sensor (if using custom sensor)
      - service: sensor.hangar_occupancy_update
        data:
          hangar: "Hangar 3"
          aircraft: "G-ABCD"
          action: "enter"
```

---

## Example 4: Hangar Security Door Monitoring

Monitor hangar door status and alert if left open.

### Requirements
- Door sensor (binary_sensor with device_class: door)
- Notification service

### Automation YAML

```yaml
automation:
  - alias: "Alert: Hangar Door Left Open"
    description: "Notify if hangar door open for more than 10 minutes"
    
    trigger:
      - platform: state
        entity_id: binary_sensor.hangar3_door
        to: "on"
        for:
          minutes: 10
    
    condition:
      # Only alert outside working hours
      - condition: time
        after: "18:00:00"
        before: "07:00:00"
    
    action:
      - service: notify.mobile_app
        data:
          title: "🚪 Hangar Door Alert"
          message: "Hangar 3 door has been open for 10 minutes"
          data:
            priority: high
            tag: "hangar_door_open"
            actions:
              - action: "DISMISS"
                title: "I know"
              - action: "CALL_SECURITY"
                title: "Call Security"
      
      # Optional: Trigger security camera recording
      - service: camera.record
        target:
          entity_id: camera.hangar3_exterior
        data:
          duration: 300
```

---

## Example 5: Hangar Climate Monitoring Dashboard Card

Display hangar conditions vs. airfield conditions on dashboard.

### Lovelace Card YAML

```yaml
type: vertical-stack
cards:
  - type: custom:mushroom-title-card
    title: "Hangar 3 Conditions"
    subtitle: "Popham Airfield"
  
  - type: horizontal-stack
    cards:
      - type: custom:mushroom-entity-card
        entity: sensor.popham_hangar_3_temperature
        name: Hangar Temp
        icon: mdi:thermometer
        icon_color: >
          {% set temp = states('sensor.popham_hangar_3_temperature') | float %}
          {% if temp < 5 %}red
          {% elif temp < 15 %}orange
          {% else %}green
          {% endif %}
      
      - type: custom:mushroom-entity-card
        entity: sensor.popham_temperature
        name: Airfield Temp
        icon: mdi:thermometer-lines
        icon_color: blue
  
  - type: horizontal-stack
    cards:
      - type: custom:mushroom-entity-card
        entity: sensor.popham_hangar_3_humidity
        name: Hangar Humidity
        icon: mdi:water-percent
        icon_color: >
          {% set humidity = states('sensor.popham_hangar_3_humidity') | float %}
          {% if humidity > 80 %}red
          {% elif humidity > 70 %}orange
          {% else %}green
          {% endif %}
      
      - type: custom:mushroom-entity-card
        entity: sensor.popham_humidity
        name: Airfield Humidity
        icon: mdi:water-outline
        icon_color: cyan
  
  - type: custom:mini-graph-card
    name: "24-Hour Hangar Temperature"
    entities:
      - entity: sensor.popham_hangar_3_temperature
        name: Hangar
        color: '#ff6b6b'
      - entity: sensor.popham_temperature
        name: Airfield
        color: '#4ecdc4'
    hours_to_show: 24
    points_per_hour: 4
    line_width: 2
    smoothing: true
```

---

## Example 6: Pre-Flight Hangar Checklist Automation

Automate pre-flight checks based on hangar conditions.

### Script YAML

```yaml
script:
  preflight_hangar_check:
    alias: "Pre-Flight Hangar Checks"
    description: "Automated hangar condition checks before flight"
    
    sequence:
      # Check hangar temperature
      - if:
          - condition: numeric_state
            entity_id: sensor.popham_hangar_3_temperature
            below: 5
        then:
          - service: notify.mobile_app
            data:
              title: "❄️ Cold Start Warning"
              message: >
                Hangar temperature is {{ states('sensor.popham_hangar_3_temperature') }}°C.
                Consider preheating engine oil.
      
      # Check hangar humidity
      - if:
          - condition: numeric_state
            entity_id: sensor.popham_hangar_3_humidity
            above: 70
        then:
          - service: notify.mobile_app
            data:
              title: "💧 Humidity Check"
              message: >
                Hangar humidity is {{ states('sensor.popham_hangar_3_humidity') }}%.
                Inspect for condensation on aircraft.
      
      # Check hangar door
      - if:
          - condition: state
            entity_id: binary_sensor.hangar3_door
            state: "off"
        then:
          - service: notify.mobile_app
            data:
              title: "🚪 Reminder"
              message: "Hangar 3 door is closed. Remember to open before engine start."
      
      # Log checklist completion
      - service: logbook.log
        data:
          name: "Pre-Flight"
          message: "Hangar checks completed for G-ABCD"
```

**Usage in automation:**
```yaml
automation:
  - alias: "Run Pre-Flight Checks on Calendar Event"
    trigger:
      - platform: calendar
        event: start
        entity_id: calendar.flight_schedule
    action:
      - service: script.preflight_hangar_check
```

---

## Best Practices

### 1. Sensor Validation
Always validate sensor states before taking action:
```yaml
condition:
  - condition: template
    value_template: >
      {{ states('sensor.popham_hangar_3_temperature') not in ['unavailable', 'unknown'] }}
```

### 2. Cooldown Periods
Prevent rapid repeated triggers:
```yaml
mode: single
max_exceeded: silent
```

### 3. Notification Deduplication
Use tags to prevent notification spam:
```yaml
data:
  tag: "hangar_temp_alert"
```

### 4. Safety Interlocks
Add multiple conditions for safety-critical actions:
```yaml
condition:
  - condition: state
    entity_id: binary_sensor.hangar_occupancy
    state: "off"
  - condition: time
    after: "06:00:00"
    before: "22:00:00"
```

### 5. Fallback Sensors
Use airfield sensors if hangar sensors unavailable (built into Hangar Assistant helpers).

---

## Advanced: Integration with Hangar Assistant Sensors

Hangar Assistant sensors automatically use hangar sensor fallback logic. Example sensor attributes:

```yaml
sensor.g_abcd_density_altitude:
  temperature_source: sensor.popham_hangar_3_temperature  # Hangar sensor used
  temperature: 12.5
  airfield: Popham
  hangar: Hangar 3
```

Use these attributes in automations:
```yaml
condition:
  - condition: template
    value_template: >
      {{ state_attr('sensor.g_abcd_density_altitude', 'hangar') == 'Hangar 3' }}
```

---

## Troubleshooting

### Hangar Sensor Not Used
1. Check hangar configuration in Hangar Assistant settings
2. Verify sensor entity ID is correct
3. Ensure sensor state is not "unavailable"
4. Check automation trace for condition failures

### Automation Not Triggering
1. Verify trigger entity states in Developer Tools → States
2. Check automation logs: Developer Tools → Logs
3. Test manually: Developer Tools → Services
4. Review automation traces

### Multiple Notifications
1. Add `mode: single` to automation
2. Use notification tags for deduplication
3. Add cooldown conditions with `for:` duration

---

## Future Enhancements

Planned features for hangar management:
- **Occupancy tracking**: Binary sensor for hangar occupancy
- **Capacity limits**: Maximum aircraft per hangar
- **Access logs**: Track hangar access via NFC/RFID
- **Climate control automation**: Automatic heater/dehumidifier scheduling
- **Maintenance tracking**: Hangar-specific maintenance schedules

---

## Related Documentation

- [HANGAR_ARCHITECTURE_PLAN.md](HANGAR_ARCHITECTURE_PLAN.md) - Complete technical architecture
- [Hangar Assistant README](README.md) - Integration overview
- [Dashboard Templates](dashboard_templates/) - Pre-built hangar dashboard cards
