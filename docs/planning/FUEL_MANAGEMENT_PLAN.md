# Fuel Management System - Implementation Plan

**Document Version**: 1.0  
**Date**: 21 January 2026  
**Status**: Planning Phase  
**Priority**: ⭐⭐⭐⭐ HIGH

---

## Table of Contents
- [Executive Summary](#executive-summary)
- [Data Model Design](#data-model-design)
- [Fuel Types & Standards](#fuel-types--standards)
- [Unit Preferences](#unit-preferences)
- [Configuration Structure](#configuration-structure)
- [Sensor Design](#sensor-design)
- [Service Design](#service-design)
- [Calculation Formulas](#calculation-formulas)
- [Future Integrations](#future-integrations)
- [Implementation Phases](#implementation-phases)
- [Backward Compatibility](#backward-compatibility)
- [Testing Strategy](#testing-strategy)

---

## Executive Summary

The Fuel Management System adds comprehensive fuel tracking and cost estimation capabilities to Hangar Assistant, enabling:

**Core Features:**
- Per-aircraft fuel burn rates and fuel type specifications
- Per-airfield fuel availability and pricing
- Flight fuel usage estimation
- Trip cost calculations
- Weight and performance impact calculations
- Fuel price comparison across airfields

**Strategic Value:**
- **Cost Management**: Track and predict fuel costs for budgeting
- **Trip Planning**: Find cheapest fuel along route
- **Weight & Balance**: Accurate fuel weight for W&B calculations
- **Performance**: Account for fuel burn in ground roll/climb performance
- **Compliance**: Maintain fuel records for cost-sharing declarations

**Implementation Timeline**: 5-7 days for Phase 1 (core features)

---

## Data Model Design

### Aircraft Fuel Specifications

Each aircraft needs fuel consumption and type data:

```python
aircraft = {
    "reg": "G-ABCD",
    "type": "Cessna 172",
    
    # Fuel specifications
    "fuel": {
        "type": str,                    # AVGAS, MOGAS, JET_A, NONE (glider)
        "burn_rate": float,             # Fuel burn per hour
        "burn_rate_unit": str,          # "liters" or "gallons" (US)
        "tank_capacity": float,         # Total usable fuel capacity
        "tank_capacity_unit": str,      # "liters" or "gallons" (US)
        
        # Optional: Different burn rates for different phases
        "burn_rates": {                 # Optional, advanced
            "taxi": float,              # Ground operations
            "cruise": float,            # Normal cruise power
            "climb": float,             # Full power climb
            "descent": float,           # Idle descent
        },
        
        # Weight data for W&B
        "fuel_density_kg_per_liter": float,  # Default per fuel type if not specified
        
        # Notes
        "notes": str,                   # "Based on POH cruise at 65% power"
    }
}
```

**Example - Cessna 172:**
```python
{
    "reg": "G-ABCD",
    "type": "Cessna 172",
    "fuel": {
        "type": "AVGAS",
        "burn_rate": 35.0,
        "burn_rate_unit": "liters",
        "tank_capacity": 155.0,
        "tank_capacity_unit": "liters",
        "notes": "Based on POH cruise at 65% power, 2400 RPM"
    }
}
```

**Example - Glider:**
```python
{
    "reg": "G-GLDR",
    "type": "ASW 20",
    "fuel": {
        "type": "NONE",
        "burn_rate": 0.0,
        "burn_rate_unit": "liters",
        "tank_capacity": 0.0,
        "tank_capacity_unit": "liters"
    }
}
```

**Example - Advanced (Twin Engine):**
```python
{
    "reg": "G-TWIN",
    "type": "Piper Seneca",
    "fuel": {
        "type": "AVGAS",
        "burn_rate": 68.0,  # Total for both engines
        "burn_rate_unit": "liters",
        "tank_capacity": 447.0,
        "tank_capacity_unit": "liters",
        "burn_rates": {
            "taxi": 15.0,
            "climb": 95.0,
            "cruise": 68.0,
            "descent": 25.0
        },
        "notes": "Both engines combined. Cruise at 65% power."
    }
}
```

### Airfield Fuel Services

Each airfield can optionally provide fuel services:

```python
airfield = {
    "name": "Popham",
    "icao": "EGHP",
    
    # Fuel services
    "fuel_services": [
        {
            "fuel_type": str,           # AVGAS, MOGAS, JET_A, etc.
            "available": bool,          # Currently available?
            "price": float,             # Price per unit
            "price_unit": str,          # "liters" or "gallons"
            "currency": str,            # "GBP", "USD", "EUR"
            "last_updated": str,        # ISO date "2026-01-21"
            "source": str,              # "manual", "airnav", "community", "api"
            "self_service": bool,       # Self-service or attended?
            "payment_methods": list,    # ["card", "cash", "account"]
            "hours": str,               # "0800-1800" or "24/7" or "PPR"
            "notes": str,               # "Call ahead for weekend service"
        }
    ]
}
```

**Example - Popham:**
```python
{
    "name": "Popham",
    "icao": "EGHP",
    "fuel_services": [
        {
            "fuel_type": "AVGAS",
            "available": True,
            "price": 2.45,
            "price_unit": "liters",
            "currency": "GBP",
            "last_updated": "2026-01-20",
            "source": "manual",
            "self_service": True,
            "payment_methods": ["card", "cash"],
            "hours": "0800-1800",
            "notes": "Self-service pump with card reader"
        },
        {
            "fuel_type": "MOGAS",
            "available": True,
            "price": 1.95,
            "price_unit": "liters",
            "currency": "GBP",
            "last_updated": "2026-01-20",
            "source": "manual",
            "self_service": True,
            "payment_methods": ["card", "cash"],
            "hours": "0800-1800",
            "notes": "Ethanol-free, suitable for rotax engines"
        }
    ]
}
```

**Example - No Fuel:**
```python
{
    "name": "Old Sarum",
    "icao": "EGLS",
    "fuel_services": []  # No fuel available
}
```

---

## Fuel Types & Standards

### Standardized Fuel Types

To ensure consistency and enable future integrations, use standardized fuel type codes:

```python
FUEL_TYPES = {
    "AVGAS": {
        "name": "Aviation Gasoline",
        "grades": ["100LL", "100", "UL91"],
        "density_kg_per_liter": 0.72,  # Typical at 15°C
        "density_lbs_per_gallon": 6.0,
        "color": "Blue (100LL)",
        "octane": "100",
    },
    "MOGAS": {
        "name": "Motor Gasoline",
        "grades": ["91", "95", "98"],
        "density_kg_per_liter": 0.75,
        "density_lbs_per_gallon": 6.25,
        "color": "Amber",
        "octane": "91-98",
        "notes": "Check POH for approval. Ethanol content restrictions apply."
    },
    "JET_A": {
        "name": "Jet-A (Kerosene)",
        "grades": ["Jet-A", "Jet-A1"],
        "density_kg_per_liter": 0.80,
        "density_lbs_per_gallon": 6.7,
        "color": "Clear/Straw",
        "notes": "For turbine engines"
    },
    "JET_B": {
        "name": "Jet-B (Wide-cut)",
        "grades": ["Jet-B"],
        "density_kg_per_liter": 0.77,
        "density_lbs_per_gallon": 6.4,
        "color": "Clear",
        "notes": "Cold weather fuel, rarely used"
    },
    "DIESEL": {
        "name": "Aviation Diesel",
        "grades": ["Jet-A1"],
        "density_kg_per_liter": 0.84,
        "density_lbs_per_gallon": 7.0,
        "color": "Clear",
        "notes": "For diesel piston engines (e.g., Diamond DA42)"
    },
    "NONE": {
        "name": "No Fuel",
        "grades": [],
        "density_kg_per_liter": 0.0,
        "density_lbs_per_gallon": 0.0,
        "color": "N/A",
        "notes": "Gliders, electric aircraft"
    }
}
```

### Fuel Density Constants

**Critical for weight calculations:**

```python
# Standard fuel densities at 15°C (59°F)
FUEL_DENSITY = {
    "AVGAS": {
        "kg_per_liter": 0.72,
        "lbs_per_gallon_us": 6.0,
        "lbs_per_gallon_imperial": 7.2,
    },
    "MOGAS": {
        "kg_per_liter": 0.75,
        "lbs_per_gallon_us": 6.25,
        "lbs_per_gallon_imperial": 7.5,
    },
    "JET_A": {
        "kg_per_liter": 0.80,
        "lbs_per_gallon_us": 6.7,
        "lbs_per_gallon_imperial": 8.0,
    },
    "DIESEL": {
        "kg_per_liter": 0.84,
        "lbs_per_gallon_us": 7.0,
        "lbs_per_gallon_imperial": 8.4,
    }
}
```

**Note**: Density varies with temperature. For precision, implement temperature correction:
```python
# Fuel expands with heat, density decreases
density_corrected = density_15C * (1 - 0.0012 * (temp_C - 15))
```

---

## Unit Preferences

### Supported Units

**Volume:**
- `liters` (L) - SI, Europe
- `gallons` (US gal) - United States
- `gallons_imperial` (UK gal) - United Kingdom (legacy)

**Burn Rate:**
- `liters_per_hour` (L/h)
- `gallons_per_hour` (gal/h US)
- `gallons_per_hour_imperial` (gal/h UK)

**Weight:**
- `kilograms` (kg) - SI
- `pounds` (lbs) - US/UK

**Price:**
- Per liter (common in Europe)
- Per gallon (US)

### Conversion Factors

```python
FUEL_CONVERSIONS = {
    "liters_to_us_gallons": 0.264172,
    "liters_to_imperial_gallons": 0.219969,
    "us_gallons_to_liters": 3.78541,
    "imperial_gallons_to_liters": 4.54609,
    "kg_to_lbs": 2.20462,
    "lbs_to_kg": 0.453592,
}
```

### User Preference System

Extend existing `unit_preference` system:

```python
entry.data["settings"]["unit_preference"] = "aviation"  # or "si"

# Fuel-specific overrides
entry.data["settings"]["fuel_volume_unit"] = "liters"  # or "gallons"
entry.data["settings"]["fuel_price_unit"] = "liters"   # or "gallons"
```

**Display Logic:**
- If `unit_preference == "aviation"`: Default to gallons (US)
- If `unit_preference == "si"`: Default to liters
- User can override specifically for fuel

---

## Configuration Structure

### Global Fuel Settings

```python
entry.data["settings"]["fuel"] = {
    # Units
    "volume_unit": str,              # "liters" or "gallons"
    "burn_rate_unit": str,           # "liters_per_hour" or "gallons_per_hour"
    "price_display_unit": str,       # "liters" or "gallons"
    
    # Defaults for new aircraft
    "default_fuel_type": str,        # "AVGAS"
    
    # Fuel price sources
    "enable_price_tracking": bool,   # Track price history
    "price_staleness_days": int,     # Warn if price older than X days (default: 30)
    
    # Community features
    "enable_community_prices": bool, # Submit/receive community fuel prices (future)
}
```

### Per-Aircraft Fuel Config

Integrated into existing aircraft config:

```python
aircraft = {
    "reg": "G-ABCD",
    "type": "Cessna 172",
    "make": "Cessna",
    "model": "172",
    
    # Existing fields
    "mtow": 1157,
    "airfield": "Popham",
    
    # NEW: Fuel configuration
    "fuel": {
        "type": "AVGAS",
        "burn_rate": 35.0,
        "burn_rate_unit": "liters",
        "tank_capacity": 155.0,
        "tank_capacity_unit": "liters",
        "notes": ""
    }
}
```

### Per-Airfield Fuel Services

Integrated into existing airfield config:

```python
airfield = {
    "name": "Popham",
    "icao": "EGHP",
    "latitude": 51.2,
    "longitude": -1.3,
    
    # Existing fields...
    
    # NEW: Fuel services
    "fuel_services": [
        {
            "fuel_type": "AVGAS",
            "available": True,
            "price": 2.45,
            "price_unit": "liters",
            "currency": "GBP",
            "last_updated": "2026-01-20",
            "source": "manual",
            "self_service": True,
            "payment_methods": ["card", "cash"],
            "hours": "0800-1800",
            "notes": ""
        }
    ]
}
```

---

## Sensor Design

### Sensors Per Aircraft

#### 1. `sensor.{aircraft}_fuel_burn_rate`

**State**: Fuel burn rate in user's preferred units

**Attributes**:
```python
{
    "aircraft": "G-ABCD",
    "fuel_type": "AVGAS",
    "burn_rate_liters_per_hour": 35.0,
    "burn_rate_gallons_per_hour": 9.2,
    "tank_capacity_liters": 155.0,
    "tank_capacity_gallons": 41.0,
    "endurance_hours": 4.4,  # tank_capacity / burn_rate
    "unit_of_measurement": "L/h"
}
```

**Device**: Links to aircraft device

**Unique ID**: `{aircraft_slug}_fuel_burn_rate`

#### 2. `sensor.{aircraft}_fuel_endurance`

**State**: Hours of flight time on full tanks

**Attributes**:
```python
{
    "aircraft": "G-ABCD",
    "endurance_hours": 4.4,
    "endurance_with_reserve_hours": 3.9,  # Minus 30 min reserve
    "tank_capacity_liters": 155.0,
    "burn_rate_liters_per_hour": 35.0,
    "reserve_minutes": 30
}
```

**Device Class**: `duration`

**Unit**: `h` (hours)

**Unique ID**: `{aircraft_slug}_fuel_endurance`

#### 3. `sensor.{aircraft}_fuel_weight`

**State**: Weight of full fuel load in user's preferred units

**Attributes**:
```python
{
    "aircraft": "G-ABCD",
    "fuel_type": "AVGAS",
    "volume_liters": 155.0,
    "weight_kg": 111.6,  # 155 * 0.72
    "weight_lbs": 246.0,
    "density_kg_per_liter": 0.72,
    "unit_of_measurement": "kg"
}
```

**Device Class**: `weight`

**Unique ID**: `{aircraft_slug}_fuel_weight`

### Sensors Per Airfield

#### 4. `sensor.{airfield}_fuel_price_avgas`

**State**: Current AVGAS price in local currency

**Attributes**:
```python
{
    "airfield": "Popham",
    "fuel_type": "AVGAS",
    "price": 2.45,
    "price_unit": "liters",
    "currency": "GBP",
    "price_per_gallon": 9.27,  # Converted
    "last_updated": "2026-01-20",
    "age_days": 1,
    "source": "manual",
    "available": True,
    "self_service": True,
    "hours": "0800-1800",
    "unit_of_measurement": "GBP/L"
}
```

**Device Class**: `monetary`

**Unique ID**: `{airfield_slug}_fuel_price_avgas`

**Note**: Create one sensor per fuel type available at airfield

#### 5. `sensor.{airfield}_cheapest_fuel`

**State**: Cheapest fuel type at airfield

**Attributes**:
```python
{
    "airfield": "Popham",
    "cheapest_fuel_type": "MOGAS",
    "cheapest_price": 1.95,
    "price_unit": "liters",
    "currency": "GBP",
    "all_fuels": [
        {"type": "MOGAS", "price": 1.95},
        {"type": "AVGAS", "price": 2.45}
    ]
}
```

**Unique ID**: `{airfield_slug}_cheapest_fuel`

### Cross-Reference Sensors

#### 6. `sensor.nearest_cheap_fuel_{fuel_type}`

**State**: Nearest airfield with cheapest {fuel_type}

**Attributes**:
```python
{
    "fuel_type": "AVGAS",
    "nearest_airfield": "Popham",
    "distance_nm": 0,  # If at home base
    "price": 2.45,
    "price_unit": "liters",
    "currency": "GBP",
    "comparison": [
        {"airfield": "Popham", "distance_nm": 0, "price": 2.45},
        {"airfield": "Old Sarum", "distance_nm": 25, "price": 2.65},
        {"airfield": "Southampton", "distance_nm": 35, "price": 2.55}
    ]
}
```

**Device**: Global device

**Unique ID**: `nearest_cheap_fuel_{fuel_type}`

---

## Service Design

### Service: `hangar_assistant.calculate_fuel_cost`

Calculate fuel cost for a flight.

**Parameters**:
```yaml
service: hangar_assistant.calculate_fuel_cost
data:
  aircraft: "G-ABCD"           # Aircraft registration
  flight_time_hours: 2.5       # Flight time in hours
  fuel_price_override: null    # Optional: Override airfield price
  include_reserve: true        # Add reserve fuel (30 min default)
```

**Returns**: Creates/updates sensor `sensor.{aircraft}_last_flight_fuel_cost`

```python
{
    "aircraft": "G-ABCD",
    "flight_time_hours": 2.5,
    "fuel_used_liters": 87.5,
    "fuel_price_per_liter": 2.45,
    "total_cost": 214.38,
    "currency": "GBP",
    "reserve_fuel_liters": 17.5,
    "total_fuel_with_reserve_liters": 105.0,
    "total_cost_with_reserve": 257.25
}
```

### Service: `hangar_assistant.estimate_trip_fuel`

Estimate fuel for a cross-country flight.

**Parameters**:
```yaml
service: hangar_assistant.estimate_trip_fuel
data:
  aircraft: "G-ABCD"
  departure: "EGHP"            # ICAO or airfield name
  destination: "EGKA"          # ICAO or airfield name
  alternate: "EGHI"            # Optional
  cruise_speed_kts: 105        # Optional, uses aircraft default
  wind_component: 0            # Optional, headwind (-) or tailwind (+)
```

**Returns**: Creates/updates sensor `sensor.{aircraft}_trip_fuel_estimate`

```python
{
    "aircraft": "G-ABCD",
    "route": "EGHP → EGKA (alt: EGHI)",
    "distance_nm": 45,
    "cruise_speed_kts": 105,
    "flight_time_hours": 0.43,  # Distance / speed
    "fuel_required_liters": 15.0,
    "reserve_liters": 17.5,
    "alternate_fuel_liters": 8.5,
    "total_fuel_liters": 41.0,
    "tank_capacity_liters": 155.0,
    "fuel_remaining_liters": 114.0,
    "endurance_remaining_hours": 3.3,
    
    # Cost breakdown
    "departure_fuel_price": 2.45,
    "destination_fuel_price": 2.65,
    "cost_if_fueled_at_departure": 100.45,
    "cost_if_fueled_at_destination": 108.65,
    "savings_by_fueling_at_departure": 8.20,
    "recommendation": "Fuel at EGHP (cheaper by £8.20)"
}
```

### Service: `hangar_assistant.update_fuel_price`

Manually update fuel price at airfield.

**Parameters**:
```yaml
service: hangar_assistant.update_fuel_price
data:
  airfield: "Popham"           # Airfield name or ICAO
  fuel_type: "AVGAS"           # Fuel type
  price: 2.50                  # Price per unit
  price_unit: "liters"         # "liters" or "gallons"
  currency: "GBP"              # Currency code
  notes: "Price increased"     # Optional notes
```

**Effect**: Updates airfield config, logs price history

### Service: `hangar_assistant.find_cheapest_fuel`

Find cheapest fuel within radius.

**Parameters**:
```yaml
service: hangar_assistant.find_cheapest_fuel
data:
  fuel_type: "AVGAS"           # Fuel type to search
  from_airfield: "Popham"      # Starting point
  radius_nm: 50                # Search radius in nautical miles
  include_travel_cost: true    # Factor in fuel cost to get there
```

**Returns**: Creates/updates sensor `sensor.cheapest_fuel_search_results`

```python
{
    "search": {
        "fuel_type": "AVGAS",
        "from_airfield": "Popham",
        "radius_nm": 50
    },
    "results": [
        {
            "airfield": "Old Sarum",
            "distance_nm": 25,
            "price_per_liter": 2.35,
            "savings_per_liter": 0.10,
            "travel_fuel_liters": 8.5,  # Fuel to get there
            "travel_cost": 20.83,
            "break_even_liters": 208.3,  # Must buy this much to break even
            "net_savings_50L": -15.83,   # Loss if only buying 50L
            "net_savings_100L": -5.83,   # Loss if buying 100L
            "net_savings_200L": 4.17,    # Profit if buying 200L
            "recommendation": "Not worth detour unless buying 200L+"
        },
        {
            "airfield": "Southampton",
            "distance_nm": 35,
            "price_per_liter": 2.55,
            "savings_per_liter": -0.10,  # More expensive
            "recommendation": "More expensive, do not divert"
        }
    ],
    "cheapest": "Old Sarum",
    "best_deal": "None - all options more expensive after travel cost"
}
```

---

## Calculation Formulas

### Fuel Consumption

**Basic Formula**:
```python
fuel_used = burn_rate * flight_time_hours
```

**With Reserve** (30 minutes standard):
```python
reserve_fuel = burn_rate * 0.5  # 30 minutes
total_fuel = fuel_used + reserve_fuel
```

**With Alternate** (diversion + 30 min reserve):
```python
alternate_fuel = (distance_to_alternate_nm / cruise_speed_kts) * burn_rate
total_fuel = fuel_used + alternate_fuel + reserve_fuel
```

### Fuel Weight

**Weight Calculation**:
```python
fuel_weight_kg = volume_liters * density_kg_per_liter
fuel_weight_lbs = volume_gallons * density_lbs_per_gallon
```

**Fuel density by type** (at 15°C):
- AVGAS: 0.72 kg/L (6.0 lbs/US gal)
- MOGAS: 0.75 kg/L (6.25 lbs/US gal)
- Jet-A: 0.80 kg/L (6.7 lbs/US gal)

### Endurance

**Flight Endurance**:
```python
endurance_hours = tank_capacity / burn_rate
endurance_with_reserve = (tank_capacity - reserve_fuel) / burn_rate
```

### Range

**Maximum Range** (no wind):
```python
range_nm = endurance_hours * cruise_speed_kts
```

**Range with Wind**:
```python
groundspeed_kts = cruise_speed_kts + wind_component  # (+tail, -head)
range_nm = endurance_hours * groundspeed_kts
```

### Cost Calculations

**Flight Cost**:
```python
cost = fuel_used * price_per_unit
```

**Cost per Nautical Mile**:
```python
cost_per_nm = (burn_rate / cruise_speed_kts) * price_per_unit
```

**Cost per Hour**:
```python
cost_per_hour = burn_rate * price_per_unit
```

### Break-Even Analysis (Fuel Diversion)

**Break-even fuel quantity**:
```python
# How much fuel must you buy to offset the cost of flying there?
travel_fuel = (distance_nm / cruise_speed_kts) * burn_rate
travel_cost = travel_fuel * home_price

price_difference = home_price - away_price
break_even_quantity = travel_cost / price_difference

# Only worth it if:
fuel_to_purchase > break_even_quantity
```

---

## Future Integrations

### Phase 2: External Fuel Price APIs

**Data Sources** (from EXTERNAL_INTEGRATIONS_RECOMMENDATIONS.md):

1. **AirNav.com** (US-focused)
   - Web scraping or paid API
   - Comprehensive US coverage
   - Includes FBO information

2. **Fuel Buddy** (Europe)
   - Potential API partnership
   - European airfield fuel prices

3. **Community-Driven Prices**
   - User-submitted prices via service
   - Aggregate and share (opt-in)
   - Gamification: "Thank you for updating fuel price!"

**Implementation**:
```python
# utils/fuel_price_client.py
class FuelPriceAggregator:
    """Multi-source fuel price aggregator."""
    
    async def fetch_prices(self, icao: str) -> Dict[str, float]:
        """Fetch from multiple sources, return best data."""
        # Try: API → Community → Manual → Stale cache
```

### Phase 3: Weight & Balance Integration

**Use fuel weight in W&B calculations**:
```python
# Fuel arm typically in front of CG
fuel_moment = fuel_weight * fuel_arm

# Update W&B sensors dynamically
sensor.aircraft_current_weight = empty_weight + fuel_weight + payload
sensor.aircraft_cg_position = total_moment / total_weight
```

### Phase 4: Performance Impact

**Account for fuel weight in performance**:
```python
# Heavier = longer ground roll, lower climb rate
ground_roll_adjusted = base_ground_roll * (current_weight / ref_weight)
climb_rate_adjusted = base_climb_rate * (ref_weight / current_weight)
```

### Phase 5: Trip Optimizer

**Multi-leg route optimization**:
- Find cheapest fuel along route
- Balance fuel load (weight) vs fuel stops
- Account for landing fees, time value
- Generate optimal fuel stop recommendations

---

## Implementation Phases

### Phase 1: Core Fuel Management (5-7 days)

**Day 1-2: Data Model & Config Flow**
- [ ] Add `fuel` object to aircraft config schema
- [ ] Add `fuel_services` array to airfield config schema
- [ ] Update config flow with fuel sections
- [ ] Create fuel type constants (`const.py`)
- [ ] Add fuel unit preferences to settings
- [ ] Migration logic (add fuel fields with defaults)

**Day 3-4: Sensors**
- [ ] `sensor.{aircraft}_fuel_burn_rate`
- [ ] `sensor.{aircraft}_fuel_endurance`
- [ ] `sensor.{aircraft}_fuel_weight`
- [ ] `sensor.{airfield}_fuel_price_{fuel_type}`
- [ ] `sensor.{airfield}_cheapest_fuel`

**Day 5-6: Services**
- [ ] `hangar_assistant.calculate_fuel_cost`
- [ ] `hangar_assistant.update_fuel_price`
- [ ] `hangar_assistant.estimate_trip_fuel`

**Day 7: Testing & Documentation**
- [ ] Unit tests for fuel calculations
- [ ] Config flow tests (migration, validation)
- [ ] Sensor tests
- [ ] Service tests
- [ ] Update README with fuel features

### Phase 2: Price Tracking (3-4 days)

**Features**:
- [ ] Price history logging (SQLite)
- [ ] Price trend sensors (up/down/stable)
- [ ] Price staleness warnings
- [ ] `sensor.fuel_price_history_{airfield}_{fuel_type}`
- [ ] Dashboard card: fuel price trends

### Phase 3: Advanced Features (5-7 days)

**Features**:
- [ ] `sensor.nearest_cheap_fuel_{fuel_type}`
- [ ] `hangar_assistant.find_cheapest_fuel` service
- [ ] Multi-airfield fuel comparison
- [ ] Break-even calculator for fuel diversions
- [ ] Trip optimizer (route-based fuel planning)

### Phase 4: External Integrations (Ongoing)

**Features**:
- [ ] AirNav.com API integration (US)
- [ ] Fuel Buddy API (Europe)
- [ ] Community price sharing (opt-in)
- [ ] Automated price updates

---

## Backward Compatibility

### CRITICAL Requirements

**✅ Existing installations must NOT break:**

1. **Default Values**: All fuel fields default to empty/zero
2. **Optional Feature**: Fuel management is opt-in
3. **Sensor Creation**: Only create fuel sensors if fuel data configured
4. **Config Migration**: Automatically add fuel structure to existing configs
5. **Graceful Degradation**: Other features work without fuel data

### Migration Strategy

```python
async def async_migrate_fuel_config(entry: ConfigEntry) -> None:
    """Add fuel structure to existing configs."""
    
    # Aircraft: Add fuel field if missing
    for aircraft in entry.data.get("aircraft", []):
        if "fuel" not in aircraft:
            aircraft["fuel"] = {
                "type": "AVGAS",  # Safe default for most GA aircraft
                "burn_rate": 0.0,  # User must configure
                "burn_rate_unit": "liters",
                "tank_capacity": 0.0,
                "tank_capacity_unit": "liters",
                "notes": ""
            }
    
    # Airfields: Add fuel_services if missing
    for airfield in entry.data.get("airfields", []):
        if "fuel_services" not in airfield:
            airfield["fuel_services"] = []  # No fuel by default
    
    # Settings: Add fuel preferences if missing
    if "fuel" not in entry.data.get("settings", {}):
        entry.data["settings"]["fuel"] = {
            "volume_unit": "liters",  # Default to SI
            "burn_rate_unit": "liters_per_hour",
            "price_display_unit": "liters",
            "enable_price_tracking": False,
            "price_staleness_days": 30
        }
```

### Sensor Conditional Creation

**Only create fuel sensors if data is configured:**

```python
async def async_setup_entry(hass, entry, async_add_entities):
    """Set up fuel sensors."""
    
    entities = []
    
    for aircraft in entry.data.get("aircraft", []):
        fuel_config = aircraft.get("fuel", {})
        
        # Only create if fuel burn rate is set
        if fuel_config.get("burn_rate", 0) > 0:
            entities.append(FuelBurnRateSensor(hass, aircraft, entry))
            entities.append(FuelEnduranceSensor(hass, aircraft, entry))
            entities.append(FuelWeightSensor(hass, aircraft, entry))
    
    for airfield in entry.data.get("airfields", []):
        fuel_services = airfield.get("fuel_services", [])
        
        # Create sensors for each fuel type available
        for service in fuel_services:
            if service.get("available", False):
                entities.append(FuelPriceSensor(hass, airfield, service, entry))
    
    async_add_entities(entities)
```

---

## Testing Strategy

### Unit Tests

**File**: `tests/test_fuel_calculations.py`

**Coverage**:
- Fuel burn calculation (basic, with reserve, with alternate)
- Fuel weight calculation (all fuel types)
- Endurance calculation
- Unit conversions (L ↔ gal, kg ↔ lbs)
- Cost calculations
- Break-even analysis

**File**: `tests/test_fuel_sensors.py`

**Coverage**:
- Sensor creation (conditional on config)
- State and attribute values
- Unit preference handling
- Fuel type validation
- Price staleness detection

**File**: `tests/test_fuel_services.py`

**Coverage**:
- `calculate_fuel_cost` service
- `update_fuel_price` service
- `estimate_trip_fuel` service
- `find_cheapest_fuel` service
- Parameter validation

**File**: `tests/test_fuel_config_flow.py`

**Coverage**:
- Fuel section in config flow
- Aircraft fuel configuration
- Airfield fuel services configuration
- Migration logic
- Validation (fuel type, units, prices)

### Integration Tests

**File**: `tests/test_fuel_integration.py`

**Coverage**:
- End-to-end fuel cost calculation
- Trip fuel estimation with real airfield data
- Price comparison across multiple airfields
- Sensor updates after price changes

### Manual Testing Checklist

- [ ] Add fuel data to aircraft via config flow
- [ ] Fuel burn rate sensor appears
- [ ] Endurance sensor calculates correctly
- [ ] Add fuel service to airfield
- [ ] Fuel price sensor appears
- [ ] Call `calculate_fuel_cost` service
- [ ] Verify cost calculation accuracy
- [ ] Update fuel price via service
- [ ] Price history tracked (if Phase 2)
- [ ] Trip fuel estimation with multiple airfields
- [ ] Cheapest fuel search (if Phase 3)
- [ ] Verify backward compatibility (existing config works)
- [ ] Verify glider (zero fuel) works correctly

---

## Dashboard Integration

### Fuel Card Examples

**Aircraft Fuel Status Card**:
```yaml
type: entities
title: G-ABCD Fuel Status
entities:
  - entity: sensor.g_abcd_fuel_burn_rate
    name: Burn Rate
  - entity: sensor.g_abcd_fuel_endurance
    name: Endurance
  - entity: sensor.g_abcd_fuel_weight
    name: Full Fuel Weight
  - type: section
    label: Local Fuel Prices
  - entity: sensor.popham_fuel_price_avgas
    name: Popham AVGAS
  - entity: sensor.popham_fuel_price_mogas
    name: Popham MOGAS
```

**Trip Fuel Estimator Card**:
```yaml
type: vertical-stack
cards:
  - type: button
    name: Estimate Trip Fuel
    tap_action:
      action: call-service
      service: hangar_assistant.estimate_trip_fuel
      data:
        aircraft: G-ABCD
        departure: EGHP
        destination: EGKA
  
  - type: markdown
    content: >
      **Trip Fuel Estimate**
      
      Route: {{ state_attr('sensor.g_abcd_trip_fuel_estimate', 'route') }}
      
      Distance: {{ state_attr('sensor.g_abcd_trip_fuel_estimate', 'distance_nm') }} nm
      
      Flight Time: {{ state_attr('sensor.g_abcd_trip_fuel_estimate', 'flight_time_hours') }} hours
      
      Fuel Required: {{ state_attr('sensor.g_abcd_trip_fuel_estimate', 'total_fuel_liters') }} L
      
      **Cost Analysis:**
      
      Fuel at {{ state_attr('sensor.g_abcd_trip_fuel_estimate', 'departure') }}: £{{ state_attr('sensor.g_abcd_trip_fuel_estimate', 'cost_if_fueled_at_departure') }}
      
      Fuel at {{ state_attr('sensor.g_abcd_trip_fuel_estimate', 'destination') }}: £{{ state_attr('sensor.g_abcd_trip_fuel_estimate', 'cost_if_fueled_at_destination') }}
      
      💡 {{ state_attr('sensor.g_abcd_trip_fuel_estimate', 'recommendation') }}
```

**Fuel Price Comparison Card**:
```yaml
type: custom:apexcharts-card
title: AVGAS Prices (50nm radius)
series:
  - entity: sensor.popham_fuel_price_avgas
    name: Popham
  - entity: sensor.old_sarum_fuel_price_avgas
    name: Old Sarum
  - entity: sensor.southampton_fuel_price_avgas
    name: Southampton
```

---

## Success Metrics

### Adoption Metrics
- **Goal**: 50% of users configure fuel data within 3 months
- **Metric**: Track % of aircraft with `burn_rate > 0`

### Usage Metrics
- **Goal**: Fuel cost service called 10+ times/month per active user
- **Metric**: Track service call frequency
- **Goal**: Fuel price updates 2+ times/month per airfield
- **Metric**: Track `update_fuel_price` service calls

### Data Quality
- **Goal**: 70% of airfields have at least one fuel service configured
- **Metric**: Count airfields with `fuel_services` array length > 0
- **Goal**: Average fuel price staleness < 30 days
- **Metric**: Track `age_days` attribute

### User Feedback
- **Goal**: Positive sentiment on fuel features
- **Metric**: Monitor GitHub issues/discussions
- **Target**: <5% bug reports related to fuel

---

## Appendix A: Config Flow Mockup

### Aircraft Configuration - Fuel Section

```
┌─────────────────────────────────────────┐
│ Configure Aircraft: G-ABCD              │
├─────────────────────────────────────────┤
│                                         │
│ Registration: G-ABCD                    │
│ Type: Cessna 172                        │
│                                         │
│ ▼ Fuel Configuration                   │
│                                         │
│   Fuel Type: [AVGAS ▼]                 │
│                                         │
│   Fuel Burn Rate: [35.0]  [L/h ▼]     │
│                                         │
│   Tank Capacity: [155.0]  [L ▼]        │
│                                         │
│   Notes:                                │
│   ┌───────────────────────────────────┐ │
│   │ Based on POH cruise at 65% power  │ │
│   └───────────────────────────────────┘ │
│                                         │
│   ☐ Advanced (per-phase burn rates)   │
│                                         │
│ [Cancel]              [Save]            │
└─────────────────────────────────────────┘
```

### Airfield Configuration - Fuel Services

```
┌─────────────────────────────────────────┐
│ Configure Airfield: Popham              │
├─────────────────────────────────────────┤
│                                         │
│ Name: Popham                            │
│ ICAO: EGHP                              │
│                                         │
│ ▼ Fuel Services                        │
│                                         │
│   ┌─ AVGAS ─────────────────────────┐  │
│   │                                  │  │
│   │ Available: ☑                     │  │
│   │                                  │  │
│   │ Price: [2.45] [GBP ▼] per [L ▼] │  │
│   │                                  │  │
│   │ Self-Service: ☑                  │  │
│   │                                  │  │
│   │ Hours: [0800-1800]               │  │
│   │                                  │  │
│   │ Notes: Self-service pump         │  │
│   │                                  │  │
│   │ [Remove AVGAS]                   │  │
│   └──────────────────────────────────┘  │
│                                         │
│   [+ Add Fuel Type]                     │
│                                         │
│ [Cancel]              [Save]            │
└─────────────────────────────────────────┘
```

---

## Appendix B: Fuel Type Reference

### AVGAS (Aviation Gasoline)

**Grades**: 100LL (Low Lead), 100, UL91 (Unleaded)

**Characteristics**:
- Octane: 100
- Color: Blue (100LL), Red (100), Colorless (UL91)
- Density: 0.72 kg/L (6.0 lbs/US gal)
- Use: Piston-engine aircraft

**Common Aircraft**: Cessna 172, Piper PA-28, Beechcraft Bonanza, etc.

### MOGAS (Motor Gasoline)

**Grades**: 91, 95, 98 octane (automotive fuel)

**Characteristics**:
- Octane: 91-98
- Color: Amber
- Density: 0.75 kg/L (6.25 lbs/US gal)
- Use: Approved piston engines (check POH)

**Important**: 
- Must be ethanol-free or approved for ethanol content
- STC (Supplemental Type Certificate) may be required
- Common in Rotax engines (UL, LSA aircraft)

**Common Aircraft**: Rotax-powered aircraft, some certified aircraft with STCs

### JET-A / JET-A1 (Kerosene)

**Grades**: Jet-A (US), Jet-A1 (International)

**Characteristics**:
- Flash point: 38°C (Jet-A1), 41°C (Jet-A)
- Color: Clear/Straw
- Density: 0.80 kg/L (6.7 lbs/US gal)
- Use: Turbine engines, diesel piston engines

**Common Aircraft**: Turboprops, jets, Diamond DA42 (diesel)

### DIESEL (Aviation Diesel)

**Characteristics**:
- Often same as Jet-A1
- Density: 0.84 kg/L (7.0 lbs/US gal)
- Use: Diesel piston engines

**Common Aircraft**: Diamond DA42/62 (Austro engines), Cessna Skyhawk JT-A

---

## Conclusion

The Fuel Management System provides comprehensive fuel tracking and cost analysis capabilities for Hangar Assistant users. By implementing this in phases, we can deliver immediate value (basic fuel tracking) while building toward advanced features (automated price updates, trip optimization).

**Key Benefits:**
- **Cost Control**: Track and predict fuel expenses
- **Trip Planning**: Optimize fuel stops and costs
- **Performance**: Account for fuel weight in calculations
- **Compliance**: Maintain fuel records for regulations

**Implementation Priority**: ⭐⭐⭐⭐ HIGH - Core feature requested by users

**Timeline**: 5-7 days for Phase 1 (immediate value), additional phases as resources permit

---

**Document End**
