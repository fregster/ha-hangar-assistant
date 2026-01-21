# Hangar Architecture & Implementation Plan

## Executive Summary

Add "hangars" as first-class entities to enable per-hangar sensor monitoring and location-based automation. Each hangar belongs to an airfield and can store multiple aircraft. Aircraft link to hangars (which implies their airfield) rather than directly to airfields.

**Key Benefits:**
- Per-hangar temperature/humidity monitoring
- Location-based automation ("if aircraft in hangar and cold, turn on oil heater")
- Better organization for users with multiple hangars at the same airfield
- Future: Hangar occupancy tracking, security sensors, etc.

---

## 1. Data Model

### New Structure

```python
entry.data = {
    "airfields": [...],  # Existing
    "aircraft": [...],   # Existing, needs migration
    "hangars": [         # NEW
        {
            "name": "Hangar 3",
            "airfield_name": "Popham",  # Links to parent airfield
            "temp_sensor": "sensor.hangar3_temperature",  # Optional
            "humidity_sensor": "sensor.hangar3_humidity",  # Optional
            "_id_slug": "popham_hangar_3",  # Generated: {airfield_slug}_{hangar_slug}
        }
    ]
}
```

### Aircraft Changes

**OLD Format** (pre-hangar):
```python
{
    "reg": "G-ABCD",
    "type": "Piper PA-28",
    "airfield": "Popham",  # Direct airfield link
    ...
}
```

**NEW Format** (with hangar):
```python
{
    "reg": "G-ABCD",
    "type": "Piper PA-28",
    "hangar": "Hangar 3",  # NEW: Primary link via hangar
    "airfield": "Popham",  # Optional: Keep for backward compatibility
    ...
}
```

### Slugification

Hangar IDs generated from airfield + hangar name:
- **Airfield**: "Popham" → `popham`
- **Hangar**: "Hangar 3" → `hangar_3`
- **Hangar ID**: `popham_hangar_3`

This ensures unique IDs even if multiple airfields have "Hangar 1".

---

## 2. Migration Strategy

### Backward Compatibility Principles

**Critical**: Existing installations must continue working without changes.

### Migration Scenarios

| User State | Behavior |
|------------|----------|
| **No hangars configured** | Aircraft with `airfield` field work as before |
| **Hangars added, aircraft not migrated** | Aircraft with `airfield` still work (fallback) |
| **Aircraft migrated to hangar** | Uses hangar sensors, inherits airfield |

### Migration Code Pattern

```python
def _get_aircraft_airfield(aircraft_config):
    """Get airfield for aircraft, checking hangar first."""
    # Priority: hangar → direct airfield → None
    if hangar_name := aircraft_config.get("hangar"):
        # Find hangar and return its airfield
        hangars = entry.data.get("hangars", [])
        for hangar in hangars:
            if hangar["name"] == hangar_name:
                return hangar["airfield_name"]
    
    # Fallback to direct airfield link (legacy)
    return aircraft_config.get("airfield")

def _get_aircraft_temperature(aircraft_config):
    """Get temperature sensor for aircraft location."""
    # 1. Check if aircraft has hangar with temp sensor
    if hangar_name := aircraft_config.get("hangar"):
        hangar = _find_hangar(hangar_name)
        if hangar and hangar.get("temp_sensor"):
            return hangar["temp_sensor"]
        
        # 2. Hangar exists but no sensor → use airfield sensor
        if hangar:
            airfield_name = hangar["airfield_name"]
            airfield = _find_airfield(airfield_name)
            return airfield.get("temp_sensor")
    
    # 3. No hangar → use direct airfield (legacy)
    if airfield_name := aircraft_config.get("airfield"):
        airfield = _find_airfield(airfield_name)
        return airfield.get("temp_sensor")
    
    return None
```

### Automatic Migration Offer

When user adds first hangar, show notification:
> "You've added your first hangar! Would you like to assign your aircraft to hangars now?"

---

## 3. Config Flow Changes

### Main Menu Update

```python
menu_options = {
    "airfield": "Add or Edit an Airfield",
    "hangar": "Add or Edit a Hangar",  # NEW
    "aircraft": "Add or Edit an Aircraft",
    "pilot": "Add or Edit a Pilot",
    "briefing": "Add or Edit Automated Briefings",
    "global_config": "Global Configuration"
}
```

### Hangar Menu

```python
async def async_step_hangar(self, _user_input=None):
    """Sub-menu for hangar management."""
    hangars = self._list_from(self._entry_data().get("hangars", []))
    
    if hangars:
        return self.async_show_menu(
            step_id="hangar",
            menu_options=["hangar_add", "hangar_manage"]
        )
    return await self.async_step_hangar_add()
```

### Hangar Add Form

```python
async def async_step_hangar_add(self, user_input=None):
    """Form to add a new hangar."""
    airfields = [a.get("name") for a in self._entry_data().get("airfields", [])]
    
    return self.async_show_form(
        step_id="hangar_add",
        data_schema=vol.Schema({
            vol.Required("name"): str,  # e.g., "Hangar 3"
            vol.Required("airfield_name"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=name, label=name)
                        for name in airfields
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Optional("temp_sensor"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional("humidity_sensor"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
        })
    )
```

### Aircraft Form Update

Add hangar selection, keep airfield for backward compat:

```python
# Get available hangars grouped by airfield
hangars = self._entry_data().get("hangars", [])
hangar_options = [
    selector.SelectOptionDict(value="", label="None (Select Airfield)")
] + [
    selector.SelectOptionDict(
        value=h["name"],
        label=f"{h['name']} ({h['airfield_name']})"
    ) for h in hangars
]

# Get airfields for fallback
airfields = [a.get("name") for a in self._entry_data().get("airfields", [])]

vol.Schema({
    # ... existing fields ...
    vol.Optional("hangar", default=aircraft.get("hangar", "")): selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=hangar_options,
            mode=selector.SelectSelectorMode.DROPDOWN
        )
    ),
    vol.Optional("airfield", default=aircraft.get("airfield", "")): selector.SelectSelector(
        # Only show if no hangar selected
        selector.SelectSelectorConfig(
            options=airfield_options,
            mode=selector.SelectSelectorMode.DROPDOWN
        )
    ),
})
```

**Form Logic**:
- If user selects hangar → disable airfield dropdown
- If user selects airfield directly → disable hangar dropdown
- At least one must be selected

---

## 4. Sensor Implementation

### Hangar-Aware Sensor Base Class

```python
class HangarAwareSensorBase:
    """Base for sensors that need hangar/airfield context."""
    
    def _get_temperature_sensor(self, aircraft_or_hangar_config):
        """Get temperature sensor with hangar → airfield fallback."""
        # Check if this is an aircraft config
        if "hangar" in aircraft_or_hangar_config:
            hangar_name = aircraft_or_hangar_config["hangar"]
            hangar = self._find_hangar(hangar_name)
            
            # Hangar has specific temp sensor
            if hangar and hangar.get("temp_sensor"):
                return hangar["temp_sensor"]
            
            # Use hangar's airfield sensor
            if hangar:
                airfield = self._find_airfield(hangar["airfield_name"])
                return airfield.get("temp_sensor")
        
        # Legacy: direct airfield link
        if "airfield" in aircraft_or_hangar_config:
            airfield = self._find_airfield(aircraft_or_hangar_config["airfield"])
            return airfield.get("temp_sensor")
        
        return None
    
    def _find_hangar(self, hangar_name):
        """Find hangar by name."""
        hangars = self.hass.data[DOMAIN].get("hangars", [])
        return next((h for h in hangars if h["name"] == hangar_name), None)
```

### Future Hangar-Specific Sensors

**`sensor.{hangar}_temperature`** (if hangar has temp sensor):
- State: Current temperature in hangar
- Attributes: `airfield`, `hangar_name`, `last_updated`

**`sensor.{hangar}_humidity`** (if hangar has humidity sensor):
- State: Current humidity in hangar
- Attributes: `airfield`, `hangar_name`, `last_updated`

**`binary_sensor.{aircraft}_in_hangar`** (future feature):
- State: ON if aircraft likely in hangar (based on location tracking)
- Requires: GPS tracking integration or manual toggle

---

## 5. Select Entity Updates

### New Hangar Selector

**`select.hangar_selector`**:
- Options: All configured hangars
- Grouped by airfield in dropdown
- Used by: Dashboard for filtering hangar-specific data

### Dashboard State Manager Update

Update `hangar_state_manager.js` to support hangar selection:
```javascript
class HangarStateManager {
    static getSelectedHangar(hass) {
        // Priority: URL param → localStorage → config default
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('hangar')) return urlParams.get('hangar');
        
        const stored = localStorage.getItem('hangar_assistant_hangar');
        if (stored) return stored;
        
        return hass.states['sensor.settings']?.attributes?.default_dashboard_hangar || null;
    }
}
```

---

## 6. Automation Examples

### Example 1: Hangar Heater Control

```yaml
automation:
  - alias: "Start Aircraft Oil Heater When Near Cold Hangar"
    trigger:
      - platform: numeric_state
        entity_id: sensor.popham_hangar_3_temperature
        below: 5  # °C
    condition:
      - condition: state
        entity_id: device_tracker.phone
        state: "home"  # Or within geofence
      - condition: template
        value_template: >
          {{ distance('device_tracker.phone', 'zone.popham_airfield') < 5 }}
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.hangar3_oil_heater_g_abcd
```

### Example 2: Hangar Humidity Alert

```yaml
automation:
  - alias: "Alert High Humidity in Hangar"
    trigger:
      - platform: numeric_state
        entity_id: sensor.popham_hangar_3_humidity
        above: 80
        for:
          hours: 2
    action:
      - service: notify.mobile_app
        data:
          title: "Hangar Humidity High"
          message: "Hangar 3 humidity is {{ states('sensor.popham_hangar_3_humidity') }}%"
```

---

## 7. Translation Keys

### New Keys Required

**English** (`translations/en.json`):
```json
{
  "options": {
    "step": {
      "init": {
        "menu_options": {
          "hangar": "Add or Edit a Hangar"
        }
      },
      "hangar": {
        "title": "Hangar Management",
        "description": "Add or manage your aircraft hangars.",
        "menu_options": {
          "hangar_add": "Add New Hangar",
          "hangar_manage": "Manage Existing Hangars"
        }
      },
      "hangar_add": {
        "title": "Add Hangar",
        "description": "Create a new hangar at one of your airfields.",
        "data": {
          "name": "Hangar Name (e.g., Hangar 3)",
          "airfield_name": "Airfield",
          "temp_sensor": "Hangar Temperature Sensor (optional)",
          "humidity_sensor": "Hangar Humidity Sensor (optional)"
        }
      },
      "hangar_manage": {
        "title": "Manage Hangars",
        "description": "Select a hangar to edit or delete.",
        "data": {
          "index": "Select Hangar",
          "action": "Action"
        }
      },
      "hangar_edit": {
        "title": "Edit Hangar",
        "description": "Update hangar details.",
        "data": {
          "name": "Hangar Name",
          "airfield_name": "Airfield",
          "temp_sensor": "Temperature Sensor",
          "humidity_sensor": "Humidity Sensor"
        }
      },
      "hangar_delete": {
        "title": "Delete Hangar",
        "description": "Are you sure you want to delete {name}? Aircraft assigned to this hangar will revert to airfield-only."
      },
      "aircraft_add": {
        "data": {
          "hangar": "Hangar (optional)",
          "airfield": "Airfield (if no hangar)"
        }
      }
    }
  }
}
```

Repeat for DE, ES, FR with appropriate translations.

---

## 8. Testing Strategy

### Unit Tests

**`test_hangar_config_flow.py`**:
```python
def test_hangar_add():
    """Test adding a new hangar."""
    # Mock airfields exist
    # Call hangar_add form
    # Submit with name and airfield
    # Verify hangar added to entry.data

def test_hangar_requires_airfield():
    """Test hangar add fails without airfield."""
    # Submit hangar without airfield
    # Expect error

def test_hangar_edit():
    """Test editing existing hangar."""
    # Setup hangar
    # Call edit form
    # Change temp sensor
    # Verify changes saved

def test_hangar_delete():
    """Test deleting hangar."""
    # Setup hangar
    # Delete it
    # Verify removed from config
```

**`test_hangar_migration.py`**:
```python
def test_aircraft_airfield_fallback():
    """Test aircraft without hangar uses direct airfield."""
    # Aircraft with airfield="Popham", no hangar
    # Get airfield
    # Verify returns "Popham"

def test_aircraft_hangar_priority():
    """Test aircraft with hangar uses hangar's airfield."""
    # Aircraft with hangar="Hangar 3" and airfield="Popham"
    # Hangar 3 belongs to "Goodwood"
    # Get airfield
    # Verify returns "Goodwood" (hangar wins)

def test_sensor_hangar_fallback():
    """Test sensor uses hangar sensor, then airfield sensor."""
    # Hangar with temp_sensor
    # Get temp
    # Verify uses hangar sensor
    
    # Hangar without temp_sensor
    # Get temp
    # Verify uses airfield sensor
```

---

## 9. Implementation Order

### Phase 1: Core Infrastructure
1. Add `hangars` list to data model
2. Create hangar config flow (add/edit/delete)
3. Add translations for all new keys
4. Unit tests for hangar CRUD

### Phase 2: Aircraft Integration
5. Update aircraft form with hangar dropdown
6. Implement backward compat helper functions
7. Migration code for old configs
8. Unit tests for migration

### Phase 3: Sensor Integration
9. Add hangar-aware sensor helper methods
10. Update existing sensors to use hangar context
11. Integration tests

### Phase 4: Dashboard & Automation
12. Add hangar select entity
13. Update dashboard state manager
14. Document automation examples
15. Update copilot instructions

---

## 10. Future Enhancements

### Phase 2 Features (Post-Launch)
- **Hangar Occupancy Tracking**: `binary_sensor.{hangar}_occupied` based on aircraft locations
- **Hangar Security Sensors**: Door sensors, motion detection
- **Multi-Hangar Aircraft**: Aircraft can belong to multiple hangars (timeshare/rental)
- **Hangar Capacity**: Max aircraft per hangar, visual occupancy display
- **Hangar Maintenance**: Track hangar maintenance schedules, inspections

### Phase 3 Features (Advanced)
- **Hangar Climate Control**: Automated heater/dehumidifier based on targets
- **Hangar Access Log**: Track who entered hangar (via door sensors/NFC)
- **Hangar Sharing**: Share hangar details with co-owners/syndicate members

---

## 11. Breaking Changes & Risks

### None Expected

This is a purely additive feature:
- Old configs continue working via fallback logic
- No existing data deleted or modified
- Users opt-in by adding hangars
- Aircraft can remain at airfield level indefinitely

### Migration Risks

**Low Risk**:
- Helper functions check hangar first, fall back to airfield
- If hangar deleted, aircraft reverts to airfield (if set)
- Worst case: user reconfigures aircraft (non-destructive)

---

## 12. Questions for User

Before implementing, confirm:

1. **Hangar Naming**: Should hangars have globally unique names, or scoped to airfield?
   - **Recommended**: Scoped to airfield (allows "Hangar 1" at each airfield)
   - **ID**: Use `{airfield_slug}_{hangar_slug}` for uniqueness

2. **Multiple Hangars per Aircraft**: Should aircraft support multiple hangars?
   - **Recommended**: Start with single hangar (simplicity)
   - **Future**: Add multi-hangar support if needed

3. **Hangar Location**: Should hangars have lat/lon coordinates?
   - **Recommended**: Not initially (inherit from airfield)
   - **Future**: Add for large airfields with distant hangars

4. **Dashboard Default**: Add "default hangar" to global settings?
   - **Recommended**: Yes, for dashboard URL param fallback

5. **Hangar Select Entity**: Create `select.hangar_selector` for dashboard?
   - **Recommended**: Yes, matches existing airfield/aircraft pattern

---

## Summary

Hangars provide:
- ✅ Per-hangar environmental monitoring
- ✅ Location-based automation triggers
- ✅ Better organization for multi-hangar users
- ✅ Backward compatible with existing configs
- ✅ Foundation for future occupancy/security features

Implementation is low-risk, high-value, and follows existing architectural patterns.
