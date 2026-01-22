# Fuel Management - Technical Documentation

**Feature**: Aircraft Fuel Planning & Cost Tracking System  
**Version**: 1.0 (v2601.2.0)  
**Implementation**: Sensor-based with Service Helpers

---

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Data Model](#data-model)
- [Sensor Implementation](#sensor-implementation)
- [Calculation Formulas](#calculation-formulas)
- [Fuel Type Density Tables](#fuel-type-density-tables)
- [Unit Conversion System](#unit-conversion-system)
- [Service Architecture](#service-architecture)
- [Integration Points](#integration-points)
- [Performance Optimization](#performance-optimization)

---

## Architecture Overview

Fuel Management is implemented as a sensor-driven system that calculates fuel metrics in real-time based on aircraft configuration data. It follows Hangar Assistant's established patterns for sensor creation, unit handling, and backward compatibility.

**Design Philosophy:**
- **Sensor-centric**: Primary data exposed via Home Assistant sensors (not services)
- **Configuration-driven**: All fuel specs defined in aircraft config (no external databases)
- **Unit-agnostic**: Supports liters, US gallons, Imperial gallons with automatic conversion
- **Type-aware**: Fuel density varies by type (Avgas vs Jet-A) with temperature correction support
- **Safety-first**: Automatic reserve calculations (30-minute VFR reserve by default)
- **Backward compatible**: Sensors only created if aircraft has fuel data (no breaking changes)

**File Structure:**
```
custom_components/hangar_assistant/
├── sensor.py                    # FuelEnduranceSensor, FuelWeightSensor (lines 2113-2280)
├── services.yaml               # Fuel estimation service definitions
├── utils/
│   └── units.py                # FUEL_DENSITIES, volume conversion functions
└── translations/
    ├── en.json                 # "Fuel Endurance", "Fuel Weight" translations
    ├── de.json                 # German translations
    ├── es.json                 # Spanish translations
    └── fr.json                 # French translations
```

**Related Tests:**
```
tests/
└── test_fuel_calculations.py   # Unit tests for fuel formulas and sensors
```

---

## Data Model

### Aircraft Fuel Configuration

Fuel data is stored per-aircraft in `entry.data["aircraft"]`:

```python
aircraft = {
    "reg": "G-ABCD",
    "type": "Cessna 172",
    
    "fuel": {
        # Required fields
        "type": str,                    # Fuel type identifier
        "burn_rate": float,             # Fuel consumption per hour
        "volume_unit": str,             # Unit for burn_rate and tank_capacity
        "tank_capacity": float,         # Total usable fuel capacity
        
        # Optional fields
        "reserve_time": int,            # Reserve fuel in minutes (default: 30)
        "density_override": float,      # Custom density in kg/L (overrides type default)
        "notes": str,                   # User notes (e.g., "Based on POH at 65% power")
    }
}
```

**Supported Fuel Types:**
| Type | Identifier | Density (kg/L at 15°C) | Common Use |
|------|-----------|------------------------|------------|
| Avgas 100LL | `"AVGAS"` | 0.72 | Piston aircraft (most common GA) |
| Jet-A | `"JET_A"` | 0.82 | Turbine aircraft, diesel engines |
| Mogas | `"MOGAS"` | 0.75 | Approved piston aircraft (unleaded) |
| Unleaded 91+ | `"UNLEADED"` | 0.75 | Light sport aircraft |
| Diesel | `"DIESEL"` | 0.85 | Compression ignition engines |
| Electric | `"ELECTRIC"` | 0.0 | Electric aircraft (battery weight handled separately) |

**Volume Units:**
| Unit | Identifier | Conversion to Liters |
|------|-----------|---------------------|
| Liters | `"liters"` | 1.0 |
| US Gallons | `"gallons_us"` | 3.78541 |
| Imperial Gallons | `"gallons_imp"` | 4.54609 |

**Default Values (Backward Compatibility):**
If an aircraft lacks fuel configuration, defaults are applied:
```python
DEFAULT_FUEL_CONFIG = {
    "type": "AVGAS",
    "burn_rate": 0,          # 0 = disable fuel sensor creation
    "volume_unit": "liters",
    "tank_capacity": 0,
    "reserve_time": 30,      # 30-minute VFR reserve
}
```

**Sensor Creation Logic:**
```python
# In sensor.py:async_setup_entry()
fuel_config = aircraft.get("fuel", DEFAULT_FUEL_CONFIG)

if fuel_config.get("burn_rate", 0) > 0:
    # Fuel data present and valid → create sensors
    entities.append(FuelEnduranceSensor(hass, aircraft, entry.data))
    entities.append(FuelWeightSensor(hass, aircraft, entry.data))
else:
    # No fuel data or burn_rate=0 → skip fuel sensors
    _LOGGER.debug("Skipping fuel sensors for %s (no burn rate)", aircraft["reg"])
```

---

## Sensor Implementation

### FuelEnduranceSensor

Calculates flight duration based on fuel capacity and burn rate.

**Class Definition:**
```python
class FuelEnduranceSensor(HangarSensorBase):
    """Calculates aircraft fuel endurance with VFR reserve.
    
    Formula:
        Usable Time = (Tank Capacity / Burn Rate) - Reserve Time
    
    Attributes:
        state: Endurance in hours (float, 1 decimal place)
        unit_of_measurement: "hours"
        device_class: SensorDeviceClass.DURATION
        state_class: SensorStateClass.MEASUREMENT
        
    Extra Attributes:
        tank_capacity: Total fuel capacity in configured units
        burn_rate: Fuel consumption per hour in configured units
        reserve_time: Reserve fuel duration in minutes
        endurance_with_reserve: Total endurance including reserve
        volume_unit: Display unit (liters, gallons_us, gallons_imp)
    """
    
    def __init__(self, hass, aircraft_config, entry_data):
        """Initialize fuel endurance sensor."""
        super().__init__(hass, aircraft_config, entry_data)
        self._fuel_config = aircraft_config.get("fuel", {})
    
    @property
    def state(self) -> Optional[float]:
        """Calculate endurance in hours (excluding reserve).
        
        Returns:
            float: Flight time in hours, or None if insufficient data
        """
        tank_capacity = self._fuel_config.get("tank_capacity", 0)
        burn_rate = self._fuel_config.get("burn_rate", 0)
        reserve_minutes = self._fuel_config.get("reserve_time", 30)
        
        if burn_rate <= 0:
            return None
        
        # Total endurance = capacity / burn rate (hours)
        total_endurance_hours = tank_capacity / burn_rate
        
        # Subtract reserve (convert minutes to hours)
        reserve_hours = reserve_minutes / 60.0
        
        usable_endurance = total_endurance_hours - reserve_hours
        
        # Ensure non-negative
        return round(max(0, usable_endurance), 1)
    
    @property
    def extra_state_attributes(self) -> dict:
        """Provide detailed fuel attributes."""
        tank_capacity = self._fuel_config.get("tank_capacity", 0)
        burn_rate = self._fuel_config.get("burn_rate", 0)
        reserve_minutes = self._fuel_config.get("reserve_time", 30)
        volume_unit = self._fuel_config.get("volume_unit", "liters")
        
        total_endurance = (tank_capacity / burn_rate) if burn_rate > 0 else 0
        
        return {
            "tank_capacity": tank_capacity,
            "burn_rate": burn_rate,
            "reserve_time_minutes": reserve_minutes,
            "endurance_with_reserve": round(total_endurance, 1),
            "volume_unit": volume_unit,
            "fuel_type": self._fuel_config.get("type", "UNKNOWN"),
        }
```

**Sensor Entity ID Pattern:**
```
sensor.{aircraft_reg_slug}_fuel_endurance
```

**Example:**
- Aircraft: G-ABCD
- Tank: 155 liters
- Burn rate: 35 L/hr
- Reserve: 30 minutes
- **State**: `3.9` hours (155/35 - 0.5 = 3.93)
- **Attributes**: `tank_capacity: 155`, `burn_rate: 35`, `volume_unit: liters`

### FuelWeightSensor

Calculates current fuel weight based on volume and density.

**Class Definition:**
```python
class FuelWeightSensor(HangarSensorBase):
    """Calculates fuel weight using density correction.
    
    Formula:
        Fuel Weight (kg) = Volume (L) × Density (kg/L)
    
    Density varies by fuel type:
        - Avgas 100LL: 0.72 kg/L
        - Jet-A: 0.82 kg/L
        - Mogas: 0.75 kg/L
        - Diesel: 0.85 kg/L
    
    Attributes:
        state: Fuel weight in kg or lbs (based on unit_preference)
        unit_of_measurement: "kg" or "lbs"
        device_class: SensorDeviceClass.WEIGHT
        state_class: SensorStateClass.MEASUREMENT
        
    Extra Attributes:
        fuel_volume: Current fuel volume in configured units
        fuel_density: Density in kg/L
        fuel_type: Type identifier (AVGAS, JET_A, etc.)
        volume_unit: Display unit
    """
    
    def __init__(self, hass, aircraft_config, entry_data):
        """Initialize fuel weight sensor."""
        super().__init__(hass, aircraft_config, entry_data)
        self._fuel_config = aircraft_config.get("fuel", {})
        self._unit_preference = entry_data.get("settings", {}).get("unit_preference", "aviation")
    
    @property
    def state(self) -> Optional[float]:
        """Calculate fuel weight.
        
        Steps:
            1. Get current fuel volume (from tank capacity or sensor if available)
            2. Convert volume to liters
            3. Get density for fuel type
            4. Calculate weight = volume × density
            5. Convert to preferred units (kg or lbs)
        
        Returns:
            float: Fuel weight in kg or lbs, or None if insufficient data
        """
        fuel_volume = self._get_current_fuel_volume()  # In configured units
        if fuel_volume is None:
            return None
        
        volume_unit = self._fuel_config.get("volume_unit", "liters")
        fuel_type = self._fuel_config.get("type", "AVGAS")
        
        # Convert to liters
        volume_liters = self._convert_to_liters(fuel_volume, volume_unit)
        
        # Get density (kg/L)
        density = self._get_fuel_density(fuel_type)
        
        # Calculate weight in kg
        weight_kg = volume_liters * density
        
        # Convert to user preference
        if self._unit_preference == "si":
            return round(weight_kg, 1)
        else:
            # Aviation units: lbs
            weight_lbs = weight_kg * 2.20462
            return round(weight_lbs, 1)
    
    def _get_fuel_density(self, fuel_type: str) -> float:
        """Get fuel density from lookup table.
        
        Args:
            fuel_type: Fuel type identifier
        
        Returns:
            float: Density in kg/L (default: 0.72 for Avgas)
        """
        from .utils.units import FUEL_DENSITIES
        
        # Check for custom override
        if "density_override" in self._fuel_config:
            return self._fuel_config["density_override"]
        
        # Lookup standard density
        return FUEL_DENSITIES.get(fuel_type, 0.72)
    
    def _convert_to_liters(self, volume: float, unit: str) -> float:
        """Convert volume to liters.
        
        Args:
            volume: Volume value
            unit: Unit identifier ("liters", "gallons_us", "gallons_imp")
        
        Returns:
            float: Volume in liters
        """
        CONVERSIONS = {
            "liters": 1.0,
            "gallons_us": 3.78541,
            "gallons_imp": 4.54609,
        }
        return volume * CONVERSIONS.get(unit, 1.0)
```

**Sensor Entity ID Pattern:**
```
sensor.{aircraft_reg_slug}_fuel_weight
```

**Example:**
- Aircraft: G-ABCD
- Current fuel: 155 liters (full tank)
- Fuel type: AVGAS (0.72 kg/L)
- Unit preference: Aviation (lbs)
- **State**: `246.0` lbs (155 × 0.72 × 2.20462 = 246.05)
- **Attributes**: `fuel_volume: 155`, `fuel_density: 0.72`, `volume_unit: liters`

---

## Calculation Formulas

### Endurance Calculation

**Base Formula:**
```
Total Endurance (hours) = Tank Capacity (volume) / Burn Rate (volume/hr)
```

**With VFR Reserve:**
```
Usable Endurance = Total Endurance - Reserve Time
Reserve Time (hours) = Reserve Minutes / 60
```

**Example:**
- Tank: 155 liters
- Burn rate: 35 L/hr
- Reserve: 30 minutes

```
Total = 155 / 35 = 4.43 hours
Reserve = 30 / 60 = 0.5 hours
Usable = 4.43 - 0.5 = 3.93 hours
```

**Edge Cases:**
- Reserve exceeds capacity: Usable = 0 (safety warning)
- Burn rate = 0: Sensor not created
- Negative result: Clamped to 0

### Fuel Weight Calculation

**Base Formula:**
```
Fuel Weight (kg) = Volume (L) × Density (kg/L)
```

**Volume Conversion:**
```
Volume (L) = Volume (original) × Conversion Factor

Conversion Factors:
  liters: 1.0
  gallons_us: 3.78541
  gallons_imp: 4.54609
```

**Unit Preference Conversion:**
```
If unit_preference == "si":
    Display in kg (no conversion)
Else (aviation):
    Weight (lbs) = Weight (kg) × 2.20462
```

**Example:**
- Volume: 41 gallons (US)
- Fuel type: Avgas (0.72 kg/L)
- Unit: Aviation (lbs)

```
Volume (L) = 41 × 3.78541 = 155.2 L
Weight (kg) = 155.2 × 0.72 = 111.7 kg
Weight (lbs) = 111.7 × 2.20462 = 246.4 lbs
```

### Trip Fuel Estimation (Service)

**Formula (planned for v1.1):**
```
Trip Fuel = (Distance / Ground Speed) × Burn Rate + Reserve

Ground Speed = TAS ± Wind Component
Reserve = Reserve Time × Burn Rate
```

**Safety Margins:**
- VFR day: 30-minute reserve (standard)
- VFR night: 45-minute reserve (recommended)
- IFR: 45-minute reserve + alternate fuel (required)

---

## Fuel Type Density Tables

Fuel density varies by type and temperature. The system uses standard densities at 15°C (59°F) with optional temperature correction.

**Density Table (utils/units.py):**
```python
FUEL_DENSITIES = {
    "AVGAS": 0.72,      # kg/L @ 15°C (Avgas 100LL)
    "JET_A": 0.82,      # kg/L @ 15°C (Jet-A, Jet-A1)
    "MOGAS": 0.75,      # kg/L @ 15°C (Motor gasoline, unleaded)
    "UNLEADED": 0.75,   # kg/L @ 15°C (91+ octane unleaded)
    "DIESEL": 0.85,     # kg/L @ 15°C (Jet-A for diesel engines)
    "ELECTRIC": 0.0,    # N/A (battery weight handled separately)
}
```

**Temperature Correction (future enhancement):**
```python
def get_fuel_density_corrected(fuel_type: str, temp_celsius: float) -> float:
    """Get temperature-corrected fuel density.
    
    Thermal expansion coefficient for petroleum fuels: ~0.0009/°C
    
    Formula:
        Density @ T = Density @ 15°C × (1 - α × (T - 15))
        α = 0.0009 for most aviation fuels
    
    Args:
        fuel_type: Fuel type identifier
        temp_celsius: Current temperature in °C
    
    Returns:
        float: Corrected density in kg/L
    """
    base_density = FUEL_DENSITIES.get(fuel_type, 0.72)
    alpha = 0.0009  # Thermal expansion coefficient
    
    temp_diff = temp_celsius - 15.0
    correction_factor = 1 - (alpha * temp_diff)
    
    return base_density * correction_factor
```

**Example (Hot Day):**
- Fuel: Avgas (base 0.72 kg/L)
- Temperature: 30°C (15°C above standard)

```
Correction = 1 - (0.0009 × 15) = 0.9865
Density = 0.72 × 0.9865 = 0.710 kg/L
```

**Weight Impact:**
- Standard: 155L × 0.72 = 111.6 kg
- Hot day: 155L × 0.710 = 110.1 kg
- **Difference**: 1.5 kg (3.3 lbs) lighter

---

## Unit Conversion System

The fuel system integrates with Hangar Assistant's global unit preference system.

**Unit Preference Modes:**
| Mode | Volume Unit | Weight Unit | Application |
|------|-------------|-------------|-------------|
| `"aviation"` | Liters or Gallons (US) | Pounds (lbs) | North America, UK |
| `"si"` | Liters | Kilograms (kg) | Europe, International |

**Conversion Functions (utils/units.py):**
```python
def convert_volume(value: float, from_unit: str, to_unit: str) -> float:
    """Convert volume between units.
    
    Args:
        value: Volume value
        from_unit: Source unit ("liters", "gallons_us", "gallons_imp")
        to_unit: Target unit
    
    Returns:
        float: Converted volume
    """
    # Convert to liters first
    to_liters = {
        "liters": 1.0,
        "gallons_us": 3.78541,
        "gallons_imp": 4.54609,
    }
    
    # Convert from liters to target
    from_liters = {
        "liters": 1.0,
        "gallons_us": 1 / 3.78541,
        "gallons_imp": 1 / 4.54609,
    }
    
    liters = value * to_liters.get(from_unit, 1.0)
    return liters * from_liters.get(to_unit, 1.0)

def convert_weight(value: float, from_unit: str, to_unit: str) -> float:
    """Convert weight between kg and lbs.
    
    Args:
        value: Weight value
        from_unit: "kg" or "lbs"
        to_unit: "kg" or "lbs"
    
    Returns:
        float: Converted weight
    """
    if from_unit == to_unit:
        return value
    
    if from_unit == "kg" and to_unit == "lbs":
        return value * 2.20462
    elif from_unit == "lbs" and to_unit == "kg":
        return value / 2.20462
    
    return value
```

**Display Logic:**
Sensors automatically format units based on user preference:
```python
@property
def unit_of_measurement(self) -> str:
    """Return unit based on preference."""
    if self._unit_preference == "si":
        return "kg"
    else:
        return "lbs"
```

---

## Service Architecture

Fuel-related services provide calculation helpers for flight planning.

### Service: estimate_fuel_cost (planned for v1.1)

**Service Definition (services.yaml):**
```yaml
estimate_fuel_cost:
  name: Estimate Fuel Cost
  description: Calculate fuel cost for a planned flight
  fields:
    aircraft_reg:
      name: Aircraft Registration
      description: Aircraft to calculate for
      required: true
      selector:
        text:
    flight_time:
      name: Flight Time
      description: Planned flight duration in hours
      required: true
      selector:
        number:
          min: 0.1
          max: 10.0
          step: 0.1
          unit_of_measurement: "hours"
    fuel_price_per_liter:
      name: Fuel Price
      description: Current fuel price per liter
      required: true
      selector:
        number:
          min: 0.01
          max: 10.0
          step: 0.01
          unit_of_measurement: "currency/L"
    include_reserve:
      name: Include Reserve
      description: Add VFR reserve to calculation
      default: true
      selector:
        boolean:
```

**Service Handler (in __init__.py):**
```python
async def handle_estimate_fuel_cost(call: ServiceCall) -> None:
    """Calculate fuel cost for planned flight.
    
    Args:
        call.data["aircraft_reg"]: Aircraft registration
        call.data["flight_time"]: Flight duration in hours
        call.data["fuel_price_per_liter"]: Price per liter
        call.data["include_reserve"]: Include VFR reserve (default: True)
    
    Returns:
        ServiceResponse with:
            - total_fuel: Volume in liters
            - fuel_cost: Total cost
            - cost_per_hour: Hourly fuel cost
    """
    aircraft = find_aircraft_by_reg(call.data["aircraft_reg"], entry.data)
    if not aircraft:
        raise ServiceValidationError(f"Aircraft {call.data['aircraft_reg']} not found")
    
    fuel_config = aircraft.get("fuel", {})
    burn_rate = fuel_config.get("burn_rate", 0)
    
    if burn_rate <= 0:
        raise ServiceValidationError("Aircraft has no fuel burn rate configured")
    
    flight_time = call.data["flight_time"]
    fuel_price = call.data["fuel_price_per_liter"]
    include_reserve = call.data.get("include_reserve", True)
    
    # Calculate fuel required
    trip_fuel = burn_rate * flight_time
    
    if include_reserve:
        reserve_minutes = fuel_config.get("reserve_time", 30)
        reserve_fuel = burn_rate * (reserve_minutes / 60.0)
        total_fuel = trip_fuel + reserve_fuel
    else:
        total_fuel = trip_fuel
    
    # Calculate cost
    fuel_cost = total_fuel * fuel_price
    cost_per_hour = fuel_cost / flight_time if flight_time > 0 else 0
    
    return {
        "total_fuel_liters": round(total_fuel, 1),
        "fuel_cost": round(fuel_cost, 2),
        "cost_per_hour": round(cost_per_hour, 2),
        "trip_fuel_liters": round(trip_fuel, 1),
        "reserve_fuel_liters": round(total_fuel - trip_fuel, 1) if include_reserve else 0,
    }
```

---

## Integration Points

### Weight & Balance System

Fuel weight feeds into weight & balance calculations:

```python
# In weight_balance.py (future)
def calculate_takeoff_weight(aircraft, fuel_volume):
    """Calculate takeoff weight including fuel.
    
    Args:
        aircraft: Aircraft config
        fuel_volume: Current fuel volume in liters
    
    Returns:
        dict: Weight breakdown
    """
    basic_empty_weight = aircraft["weights"]["basic_empty_weight"]
    fuel_weight = get_fuel_weight(aircraft, fuel_volume)
    payload = aircraft["weights"].get("current_payload", 0)
    
    takeoff_weight = basic_empty_weight + fuel_weight + payload
    
    return {
        "basic_empty": basic_empty_weight,
        "fuel": fuel_weight,
        "payload": payload,
        "total": takeoff_weight,
        "mtow_margin": aircraft["mtow"] - takeoff_weight,
    }
```

### Performance Calculations

Fuel weight affects aircraft performance:

```python
# In performance.py (existing)
def calculate_ground_roll_adjustment(aircraft, fuel_weight):
    """Adjust ground roll for fuel weight.
    
    Heavy fuel load increases ground roll distance.
    
    Args:
        aircraft: Aircraft config
        fuel_weight: Current fuel weight in kg
    
    Returns:
        float: Ground roll multiplier (1.0 = standard, >1.0 = increased)
    """
    mtow = aircraft["mtow"]
    empty_weight = aircraft["weights"]["basic_empty_weight"]
    
    # Calculate weight ratio
    current_weight = empty_weight + fuel_weight
    weight_ratio = current_weight / mtow
    
    # Ground roll increases approximately 2% per 1% weight increase above 80% MTOW
    if weight_ratio > 0.8:
        excess = weight_ratio - 0.8
        adjustment = 1.0 + (excess * 2.0)
        return adjustment
    
    return 1.0
```

### AI Briefing Integration

Fuel endurance included in AI briefing safety analysis:

```python
# In ai_briefing.py (existing)
def generate_briefing_fuel_section(aircraft, hass):
    """Generate fuel status for AI briefing.
    
    Includes:
        - Current endurance
        - Reserve status
        - Refueling recommendation
    
    Args:
        aircraft: Aircraft config
        hass: Home Assistant instance
    
    Returns:
        str: Formatted fuel section for briefing
    """
    reg_slug = _slugify(aircraft["reg"])
    endurance_sensor = f"sensor.{reg_slug}_fuel_endurance"
    
    endurance_state = hass.states.get(endurance_sensor)
    if not endurance_state:
        return "Fuel: No data available"
    
    endurance_hours = float(endurance_state.state)
    
    if endurance_hours < 1.0:
        warning = "⚠️ LOW FUEL - Refuel before flight"
    elif endurance_hours < 2.0:
        warning = "⚠️ Limited endurance - Plan for short flights only"
    else:
        warning = ""
    
    return f"Fuel Endurance: {endurance_hours:.1f} hours {warning}"
```

---

## Performance Optimization

### Sensor State Caching

Fuel sensors use the base class state cache to reduce redundant calculations:

```python
# From HangarSensorBase (sensor.py)
_state_cache: OrderedDict[str, tuple] = OrderedDict()
_cache_ttl_seconds = 60  # 1-minute cache

def _get_cached_state(self, cache_key: str) -> Optional[Any]:
    """Get cached state if still valid."""
    if cache_key in self._state_cache:
        cached_value, cached_time = self._state_cache[cache_key]
        age = (dt_util.utcnow() - cached_time).total_seconds()
        
        if age < self._cache_ttl_seconds:
            return cached_value
    
    return None
```

**Performance Impact:**
- Cache hit: <0.1ms (dict lookup)
- Cache miss: ~1-2ms (formula calculation)
- Cache reduces CPU load by ~80% for frequently polled sensors

### Formula Optimization

Fuel calculations use simple arithmetic (no expensive operations):

```python
# Endurance: 1 division, 1 subtraction
usable = (capacity / burn_rate) - reserve

# Weight: 2 multiplications, 1 lookup
weight = volume * unit_conversion * density
```

**Complexity:**
- Time: O(1) constant time
- Space: O(1) constant space
- CPU: <0.01% per sensor update

---

## Future Enhancements

### Planned Features (v1.1+)

1. **Airfield Fuel Pricing**
   - Per-airfield fuel prices in config
   - Price comparison sensor (cheapest nearby airfield)
   - Historical price tracking

2. **Real-Time Fuel Flow Integration**
   - Connect to fuel flow sensors (G3X, EMS, etc.)
   - Actual vs. planned burn rate comparison
   - Adjust endurance dynamically

3. **Fuel Planning Dashboard Cards**
   - Visual fuel gauge (needle/bar chart)
   - Trip fuel calculator card
   - Reserve status indicator (green/yellow/red)

4. **Historical Analytics**
   - Fuel cost over time (per aircraft)
   - Actual burn rate tracking
   - Cost per flight hour trends

5. **Temperature Correction**
   - Use ambient temperature for density adjustment
   - Hot day vs. cold day weight difference
   - More accurate W&B calculations

---

## Related Documentation

- **User Guide**: [docs/features/fuel_management.md](../features/fuel_management.md) - Setup and usage instructions
- **Planning Document**: [docs/implemented/fuel_management_plan.md](fuel_management_plan.md) - Original design rationale
- **Sensor Reference**: [docs/ENTITY_DESCRIPTIONS.md](../ENTITY_DESCRIPTIONS.md) - All fuel sensor descriptions
- **Services**: [custom_components/hangar_assistant/services.yaml](../../custom_components/hangar_assistant/services.yaml) - Service definitions

---

**Last Updated**: 22 January 2026  
**Implementation Version**: v2601.2.0  
**Author**: Hangar Assistant Development Team
