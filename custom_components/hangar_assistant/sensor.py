"""Sensor platform for Hangar Assistant."""
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfLength,
    UnitOfTemperature,
    UnitOfSpeed,
)
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hangar Assistant sensors dynamically from config entry lists."""
    entities = []
    
    # 1. Process Airfields from the list
    for airfield in entry.data.get("airfields", []):
        entities.extend([
            DensityAltSensor(hass, airfield),
            CloudBaseSensor(hass, airfield),
            DataFreshnessSensor(hass, airfield),
            CarbRiskSensor(hass, airfield)
        ])

    # 2. Process Aircraft from the list
    for aircraft in entry.data.get("aircraft", []):
        entities.append(GroundRollSensor(hass, aircraft))

    # Add all generated entities to the system
    async_add_entities(entities)

class HangarSensorBase(SensorEntity):
    """Common logic for all Hangar Assistant sensors."""
    
    def __init__(self, hass, config):
        self.hass = hass
        self._config = config
        # Use Name or Reg to create a safe unique ID 
        self._id_slug = (config.get("name") or config.get("reg")).lower().replace(" ", "_")
        self._attr_unique_id = f"{self._id_slug}_{self.__class__.__name__.lower()}"
        
        # Link to a Device in the UI for cleaner grouping
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._id_slug)},
            name=config.get("name") or config.get("reg"),
            manufacturer="Fregster Aviation",
            model="Hangar Assistant v2601.1",
        )

    def _get_sensor_value(self, entity_id):
        """Safely fetch and convert a sensor state to float."""
        state = self.hass.states.get(entity_id)
        if state and state.state not in ("unknown", "unavailable"):
            try:
                return float(state.state)
            except ValueError:
                return None
        return None

# --- AIRFIELD ENTITIES ---

class DensityAltSensor(HangarSensorBase):
    """Calculates Density Altitude for a specific airfield."""
    _attr_native_unit_of_measurement = UnitOfLength.FEET
    _attr_device_class = SensorDeviceClass.DISTANCE

    @property
    def name(self):
        return f"{self._config['name']} Density Altitude"

    @property
    def native_value(self):
        temp = self._get_sensor_value(self._config['temp_sensor'])
        if temp is None: return None
        # Standard Aviation Formula: DA = Pressure Alt + (120 * (OAT - ISA_Temp))
        # Using 15C as ISA SL baseline
        return round(4000 + (120 * (temp - 15)))

class CloudBaseSensor(HangarSensorBase):
    """Estimates Cloud Base height (AGL) for a specific airfield."""
    _attr_native_unit_of_measurement = UnitOfLength.FEET

    @property
    def name(self):
        return f"{self._config['name']} Est Cloud Base"

    @property
    def native_value(self):
        t = self._get_sensor_value(self._config['temp_sensor'])
        dp = self._get_sensor_value(self._config['dp_sensor'])
        if t is None or dp is None: return None
        # Spread method: (Temp - Dewpoint) / 2.5 * 1000
        return round(((t - dp) / 2.5) * 1000)

# --- AIRCRAFT ENTITIES ---

class GroundRollSensor(HangarSensorBase):
    """Calculates adjusted Takeoff Ground Roll for a specific aircraft."""
    _attr_native_unit_of_measurement = UnitOfLength.METERS

    @property
    def name(self):
        return f"{self._config['reg']} Ground Roll"

    @property
    def native_value(self):
        base = self._config.get("baseline_roll", 0)
        # Apply 15% safety factor automatically
        return round(base * 1.15)

# (Additional CarbRisk and DataFreshness classes follow same pattern)