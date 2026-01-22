# Fuel Management

**Feature**: Aircraft Fuel Planning & Cost Tracking  
**Version**: 1.0 (v2601.2.0)  
**Status**: ✅ Available

---

## Overview

Fuel Management in Hangar Assistant provides comprehensive tools for monitoring fuel consumption, calculating trip costs, and planning fuel requirements. The system tracks burn rates, calculates endurance, monitors fuel weight for weight & balance, and estimates trip fuel needs with safety reserves.

**What you can do**:
- Monitor real-time fuel burn rate and endurance
- Calculate fuel costs for flights
- Estimate fuel requirements for trip planning
- Track fuel weight for weight & balance calculations
- Support multiple fuel types with automatic density corrections
- Work with any volume unit (liters, US gallons, Imperial gallons)

**Use cases**:
- Pre-flight fuel planning with reserve calculations
- Cost estimation for cross-country flights
- Weight & balance fuel weight calculations
- Fuel monitoring during flight (with connected sensors)
- Cost-sharing expense tracking

---

## Getting Started

### Prerequisites

- Hangar Assistant installed and configured
- At least one aircraft configured in your system
- Aircraft fuel data entered (see configuration section)

### Accessing Fuel Features

Fuel features are accessed through three main areas:

1. **Sensors**: Real-time fuel monitoring (burn rate, endurance, weight)
2. **Services**: Fuel calculations (cost estimation, trip planning)
3. **Dashboard Cards**: Visual fuel status displays

---

## Fuel Configuration

### Aircraft Fuel Settings

When adding or editing an aircraft, configure these fuel parameters:

#### Fuel Type
Select the type of fuel your aircraft uses:
- **AVGAS** (0.72 kg/L): Aviation gasoline (standard for most piston aircraft)
- **MOGAS** (0.75 kg/L): Motor gasoline (automotive fuel, approved for some aircraft)
- **JET A** (0.80 kg/L): Jet fuel (turbine aircraft, most common jet fuel)
- **JET B** (0.77 kg/L): Jet fuel (wide-cut, cold weather operations)
- **DIESEL** (0.84 kg/L): Aviation diesel (diesel piston engines)
- **NONE** (0.0 kg/L): No fuel system (gliders, electric aircraft)

💡 **Tip**: Fuel density values are at standard temperature (15°C/59°F). The system uses these for weight calculations.

#### Fuel Burn Rate
Your aircraft's typical fuel consumption in liters per hour at cruise power settings.

**Examples**:
- Cessna 172: 35 L/h (9.2 US gal/h)
- Piper PA-28: 38 L/h (10 US gal/h)
- Diamond DA42: 38 L/h total (19 L/h per engine)
- Cirrus SR22: 68 L/h (18 US gal/h)

📖 **Where to find**: Check your Pilot's Operating Handbook (POH) under "Performance Data" or "Fuel Consumption Charts"

#### Fuel Tank Capacity
Total usable fuel capacity in liters.

**Examples**:
- Cessna 172: 155 L (41 US gal)
- Piper PA-28: 189 L (50 US gal)
- Diamond DA42: 182 L (48 US gal)
- Cirrus SR22: 348 L (92 US gal)

⚠️ **Important**: Use **usable** fuel capacity, not total capacity. Unusable fuel (trapped in tanks/lines) cannot be used for flight planning.

#### Fuel Volume Unit
Choose your preferred unit for displaying fuel quantities:
- **Liters** (L): Metric standard
- **US Gallons** (US gal): United States aviation standard
- **Imperial Gallons** (Imp gal): UK aviation standard

💡 **Tip**: Set this to match your aircraft's fuel gauges and POH for easier cross-referencing.

---

## Fuel Sensors

When you configure fuel data for an aircraft (burn rate > 0), three sensors are automatically created:

### 1. Fuel Burn Rate Sensor

**Entity ID**: `sensor.{registration}_fuel_burn_rate`  
**Example**: `sensor.g_abcd_fuel_burn_rate`

**What it shows**: Current fuel consumption rate in your chosen unit

**Unit of Measurement**: 
- Liters: `L/h`
- US Gallons: `US gal/h`
- Imperial Gallons: `Imp gal/h`

**Use cases**:
- Monitoring fuel economy
- Verifying POH performance data
- Tracking deviations from expected consumption

**Example values**:
- Cessna 172: 35 L/h, 9.2 US gal/h, 7.7 Imp gal/h
- Piper PA-28: 38 L/h, 10.0 US gal/h, 8.4 Imp gal/h

---

### 2. Fuel Endurance Sensor

**Entity ID**: `sensor.{registration}_fuel_endurance`  
**Example**: `sensor.g_abcd_fuel_endurance`

**What it shows**: Maximum flight time with current fuel load (minus safety reserve)

**Unit of Measurement**: Hours (decimal)

**Safety Reserve**: 30 minutes automatically deducted from calculations

**Formula**:
```
Endurance = (Tank Capacity / Burn Rate) - 0.5 hours
```

**Example**:
- Cessna 172 with 155L capacity at 35 L/h:
  - Raw endurance: 155 / 35 = 4.43 hours
  - With reserve: 4.43 - 0.5 = **3.93 hours** (3 hours 56 minutes)

**Use cases**:
- Pre-flight range planning
- Fuel stop calculations for cross-country flights
- Safety margin verification

⚠️ **Safety Note**: The 30-minute reserve is the legal VFR minimum in most jurisdictions. Consider increasing reserve for night flying, IMC, or unfamiliar airports.

---

### 3. Fuel Weight Sensor

**Entity ID**: `sensor.{registration}_fuel_weight`  
**Example**: `sensor.g_abcd_fuel_weight`

**What it shows**: Total weight of fuel in tank

**Unit of Measurement**: Kilograms (kg) or Pounds (lbs) based on unit preference

**Formula**:
```
Fuel Weight = Tank Capacity × Fuel Density
```

**Example**:
- Cessna 172 with 155L AVGAS (0.72 kg/L):
  - Weight: 155 × 0.72 = **111.6 kg** (246 lbs)

**Use cases**:
- Weight & balance calculations
- Payload capacity planning
- Takeoff weight verification

**Attributes**:
- `fuel_type`: Type of fuel (AVGAS, JET A, etc.)
- `density_kg_per_liter`: Fuel density value used
- `volume_liters`: Volume in liters
- `volume_unit`: Display unit preference

💡 **Tip**: Link this sensor to your weight & balance automation to automatically recalculate CG when fuel changes.

---

## Fuel Services

Hangar Assistant provides two services for fuel calculations:

### 1. Calculate Fuel Cost

**Service**: `hangar_assistant.calculate_fuel_cost`

**What it does**: Calculates total fuel cost for a flight based on duration and fuel price

**Parameters**:

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `aircraft_reg` | string | ✅ | Aircraft registration (tail number) | `G-ABCD` |
| `flight_time_hours` | number | ✅ | Flight duration in decimal hours | `2.5` |
| `fuel_price_per_liter` | number | ✅ | Fuel price per liter | `1.85` |

**How to call**:

```yaml
service: hangar_assistant.calculate_fuel_cost
data:
  aircraft_reg: "G-ABCD"
  flight_time_hours: 2.5
  fuel_price_per_liter: 1.85
```

**Output**: Fires event `hangar_assistant_fuel_cost_calculated` with:

```json
{
  "aircraft_reg": "G-ABCD",
  "flight_time_hours": 2.5,
  "fuel_consumed_liters": 87.5,
  "fuel_consumed_display": "87.5 L (23.1 US gal)",
  "fuel_price_per_liter": 1.85,
  "total_cost": 161.88,
  "currency": "GBP"
}
```

**Real-world example**:
- Aircraft: Cessna 172 (35 L/h burn rate)
- Flight time: 2.5 hours
- Fuel price: £1.85/liter
- **Result**: 87.5 L consumed, total cost £161.88

**Use cases**:
- Pre-flight cost estimation
- Cost-sharing expense calculations (CAP 1590B)
- Budgeting for cross-country flights
- Comparing fuel prices between airfields

---

### 2. Estimate Trip Fuel

**Service**: `hangar_assistant.estimate_trip_fuel`

**What it does**: Calculates required fuel for a trip with safety reserves

**Parameters**:

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `aircraft_reg` | string | ✅ | Aircraft registration | `G-ABCD` |
| `departure_icao` | string | ❌ | Departure airfield ICAO code | `EGHP` |
| `destination_icao` | string | ❌ | Destination airfield ICAO code | `EGTK` |
| `distance_nm` | number | ✅ | Distance in nautical miles | `75` |
| `cruise_speed_kts` | number | ✅ | Cruise speed in knots | `105` |

**How to call**:

```yaml
service: hangar_assistant.estimate_trip_fuel
data:
  aircraft_reg: "G-ABCD"
  departure_icao: "EGHP"
  destination_icao: "EGTK"
  distance_nm: 75
  cruise_speed_kts: 105
```

**Output**: Fires event `hangar_assistant_trip_fuel_estimated` with:

```json
{
  "aircraft_reg": "G-ABCD",
  "departure_icao": "EGHP",
  "destination_icao": "EGTK",
  "distance_nm": 75,
  "cruise_speed_kts": 105,
  "estimated_time_hours": 0.71,
  "fuel_required_liters": 42.14,
  "fuel_required_display": "42.1 L (11.1 US gal)",
  "reserve_fuel_liters": 17.5,
  "total_fuel_liters": 59.64,
  "fuel_available_liters": 155.0,
  "fuel_margin_liters": 95.36,
  "sufficient_fuel": true
}
```

**Calculations**:
1. **Flight Time**: Distance ÷ Cruise Speed
   - 75 nm ÷ 105 kts = 0.71 hours (43 minutes)

2. **Fuel Required**: Flight Time × Burn Rate
   - 0.71 hours × 35 L/h = 24.64 liters

3. **Reserve Fuel**: 30 minutes of burn rate
   - 0.5 hours × 35 L/h = 17.5 liters

4. **Total Required**: Fuel Required + Reserve Fuel + 10% contingency
   - 24.64 + 17.5 + 2.46 = 42.14 liters

5. **Fuel Margin**: Available - Total Required
   - 155 - 42.14 = 95.36 liters remaining

**Use cases**:
- Cross-country flight planning
- Fuel stop calculations for long routes
- Safety margin verification
- Payload capacity planning (remaining weight budget)

⚠️ **Safety Note**: Always add contingency fuel for:
- Headwinds
- Diversions to alternate airports
- Holding patterns or delays
- Navigation inefficiencies

---

## Troubleshooting

### Problem: Fuel sensors not appearing

**Symptoms**: Expected fuel sensors missing after configuring aircraft

**Solution**:
1. Check fuel burn rate is > 0 in aircraft configuration
2. Verify aircraft has fuel type other than "NONE"
3. Restart Home Assistant to force entity refresh
4. Check Developer Tools → States for sensor entities

---

### Problem: Fuel calculations seem incorrect

**Symptoms**: Endurance or cost calculations don't match manual calculations

**Solution**:
1. Verify fuel burn rate in aircraft config matches POH
2. Check fuel volume unit is set correctly
3. Confirm fuel type matches your aircraft (AVGAS vs MOGAS)
4. Remember 30-minute reserve is automatically deducted
5. Check unit conversions if using non-liter displays

---

### Problem: Service calls not working

**Symptoms**: `calculate_fuel_cost` or `estimate_trip_fuel` service fails

**Solution**:
1. Verify aircraft registration exactly matches config (case-sensitive)
2. Check all required parameters are provided
3. Ensure aircraft has fuel burn rate configured
4. Review Home Assistant logs for specific error messages

---

## FAQ

### Can I track fuel for multiple aircraft?

Yes! Each aircraft you configure gets its own set of fuel sensors. Configure fuel data for each aircraft individually, and sensors will appear with their respective registration slugs.

### What if my aircraft uses different fuel types?

Configure each aircraft with its appropriate fuel type. The system supports AVGAS, MOGAS, JET A, JET B, and DIESEL, each with correct density values for accurate weight calculations.

### How accurate are the endurance calculations?

Endurance calculations are based on your configured burn rate and assume:
- Cruise power settings (not full throttle)
- Standard atmospheric conditions
- Level flight (not climbing)
- No headwind/tailwind compensation

Always add contingency fuel for real-world conditions.

### Can I change fuel units after configuration?

Yes! Edit your aircraft configuration and change the `fuel_volume_unit` setting. Sensors will immediately update to display in your new unit preference.

### What if I don't know my exact burn rate?

Check your Pilot's Operating Handbook (POH) performance charts. Typical cruise burn rates:
- Small trainers (C152, PA-28): 25-40 L/h
- Large trainers (C172, C182): 35-50 L/h
- High-performance singles (SR20, SR22): 50-80 L/h
- Light twins (DA42, Seneca): 60-100 L/h

When in doubt, use a slightly higher burn rate for safety margins.

### Does the system track actual fuel remaining?

No - the sensors show **capacity-based calculations**, not real-time fuel levels. For actual fuel tracking, you would need a connected fuel flow sensor or fuel quantity sensor from your aircraft.

### What is the 30-minute reserve based on?

The 30-minute reserve is the **legal VFR minimum** in most jurisdictions (UK CAA, FAA, EASA). This is the minimum fuel you must have at your destination. Consider adding more reserve for:
- Night flying (45-60 minutes)
- IMC operations (45 minutes)
- Unfamiliar airports
- Mountain flying
- Over-water operations

---

## Best Practices

### For Student Pilots

- **Learn fuel planning**: Use the trip estimation service to practice calculating fuel requirements
- **Safety first**: Always physically verify fuel levels before flight - never rely solely on calculations
- **Build habits**: Check fuel sensors as part of your pre-flight checklist
- **Ask your instructor**: Confirm your aircraft's actual burn rate matches POH figures

### For Private Pilots

- **Trip planning**: Use `estimate_trip_fuel` for all cross-country flights
- **Cost tracking**: Log `calculate_fuel_cost` results for expense tracking
- **Weight & balance**: Include fuel weight sensor in W&B automations
- **Fuel stops**: Plan fuel stops when remaining fuel drops below 1 hour endurance

### For Glider Pilots

- **No fuel system**: Configure fuel type as "NONE" to disable fuel sensors
- **Tow costs**: Use the cost calculation service to track tow plane fuel costs
- **Self-launch gliders**: Configure fuel data if you have an engine

### For Commercial Operators

- **Cost recovery**: Track fuel costs per flight for accurate billing
- **Fleet monitoring**: Configure fuel data for all aircraft in your fleet
- **Safety margins**: Consider increasing reserve fuel beyond 30-minute minimum
- **Regulatory compliance**: Ensure fuel planning meets CAA/EASA/FAA requirements

---

## Technical Details (Advanced)

<details>
<summary>Click to expand</summary>

### Fuel Density Values

All fuel densities are at standard temperature (15°C/59°F):

| Fuel Type | Density (kg/L) | Density (lbs/US gal) | Notes |
|-----------|----------------|----------------------|-------|
| AVGAS | 0.72 | 6.0 | 100LL aviation gasoline |
| MOGAS | 0.75 | 6.3 | Automotive gasoline (unleaded) |
| JET A | 0.80 | 6.7 | Most common jet fuel |
| JET B | 0.77 | 6.4 | Wide-cut jet fuel (cold weather) |
| DIESEL | 0.84 | 7.0 | Aviation diesel (Jet A1 compatible) |
| NONE | 0.0 | 0.0 | No fuel system |

### Volume Conversion Factors

```python
LITERS_TO_US_GALLONS = 0.264172
LITERS_TO_IMP_GALLONS = 0.219969
US_GALLONS_TO_LITERS = 3.78541
IMP_GALLONS_TO_LITERS = 4.54609
```

### Sensor State Calculation

**Fuel Burn Rate Sensor**:
```python
burn_rate_liters_per_hour = aircraft["fuel"]["burn_rate"]
converted_rate = convert_fuel_volume(burn_rate_liters_per_hour, "liters", unit_preference)
state = round(converted_rate, 1)
```

**Fuel Endurance Sensor**:
```python
capacity_liters = aircraft["fuel"]["tank_capacity"]
burn_rate = aircraft["fuel"]["burn_rate"]
reserve_hours = 0.5  # 30 minutes
endurance = (capacity_liters / burn_rate) - reserve_hours
state = round(endurance, 2)
```

**Fuel Weight Sensor**:
```python
capacity_liters = aircraft["fuel"]["tank_capacity"]
density_kg_per_liter = FUEL_DENSITY[fuel_type]
weight_kg = capacity_liters * density_kg_per_liter
state = round(weight_kg, 1)
```

### Service Event Schema

**Fuel Cost Calculated Event**:
```json
{
  "event_type": "hangar_assistant_fuel_cost_calculated",
  "data": {
    "aircraft_reg": "string",
    "flight_time_hours": "number",
    "fuel_consumed_liters": "number",
    "fuel_consumed_display": "string",
    "fuel_price_per_liter": "number",
    "total_cost": "number",
    "currency": "string"
  }
}
```

**Trip Fuel Estimated Event**:
```json
{
  "event_type": "hangar_assistant_trip_fuel_estimated",
  "data": {
    "aircraft_reg": "string",
    "departure_icao": "string",
    "destination_icao": "string",
    "distance_nm": "number",
    "cruise_speed_kts": "number",
    "estimated_time_hours": "number",
    "fuel_required_liters": "number",
    "fuel_required_display": "string",
    "reserve_fuel_liters": "number",
    "total_fuel_liters": "number",
    "fuel_available_liters": "number",
    "fuel_margin_liters": "number",
    "sufficient_fuel": "boolean"
  }
}
```

### Config Entry Structure

Aircraft fuel configuration:
```python
{
  "reg": "G-ABCD",
  "model": "Cessna 172",
  "fuel": {
    "type": "AVGAS",  # or MOGAS, JET_A, JET_B, DIESEL, NONE
    "burn_rate": 35,  # liters per hour
    "tank_capacity": 155,  # liters (usable)
    "volume_unit": "liters"  # or us_gallons, imp_gallons
  }
}
```

### Backward Compatibility

If an aircraft config lacks fuel data, default values are applied:
```python
{
  "type": "AVGAS",
  "burn_rate": 0,  # Disables fuel sensor creation
  "tank_capacity": 0,
  "volume_unit": "liters"
}
```

Sensors are only created when `burn_rate > 0`, ensuring existing aircraft without fuel config don't get empty sensors.

</details>

---

## Related Documentation

- [Setup Wizard](setup_wizard.md) - Configure aircraft with fuel data during first-time setup
- [AI Briefing](ai_briefing.md) - AI briefings include fuel endurance in safety analysis
- [Glass Cockpit Dashboard](glass_cockpit_dashboard.md) - Add fuel cards to your dashboard
- [Services Documentation](/custom_components/hangar_assistant/services.yaml) - Full service specifications

## Technical Details (Advanced)

<details>
<summary>Click to expand technical implementation details</summary>

For developers and advanced users interested in the fuel management system architecture, comprehensive technical documentation is available covering:

- **Data Model**: Aircraft fuel configuration structure and defaults
- **Sensor Implementation**: FuelEnduranceSensor and FuelWeightSensor class details
- **Calculation Formulas**: Mathematical formulas for endurance, weight, and reserves
- **Fuel Type Density Tables**: Density values for all supported fuel types
- **Unit Conversion System**: Multi-unit volume and weight conversions
- **Service Architecture**: Fuel cost estimation and trip planning services
- **Integration Points**: Weight & balance, performance calculations, AI briefing
- **Performance Optimization**: State caching and formula complexity analysis

**Read the technical documentation**: [docs/implemented/fuel_management_technical.md](../implemented/fuel_management_technical.md)

</details>

---

## Version History

### v1.0 (v2601.2.0) - Current
- Initial fuel management release
- Three aircraft fuel sensors (burn rate, endurance, weight)
- Two fuel calculation services (cost, trip estimation)
- Support for 6 fuel types with density corrections
- Multi-unit volume display (liters, US gallons, Imperial gallons)
- Automatic 30-minute VFR reserve calculation
- Backward compatible with existing aircraft configs

### Planned Enhancements
- Airfield fuel price tracking sensors
- Cheapest fuel finder (multi-airfield comparison)
- Fuel flow sensor integration (real-time tracking)
- Historical fuel cost analytics
- Fuel planning dashboard cards
- Integration with flight logging for actual vs. planned fuel
