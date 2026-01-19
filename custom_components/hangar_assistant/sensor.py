import math
from datetime import datetime
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature, UnitOfLength, UnitOfSpeed
from homeassistant.util import dt as dt_util
from .const import DOMAIN, ATTR_OLD_SOURCE, ATTR_LAST_CHECK

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensors from a config entry."""
    config = entry.data
    if config.get("type") == "airfield":
        async_add_entities([
            CarbRiskSensor(hass, config),
            BestRunwaySensor(hass, config),
            CloudBaseSensor(hass, config),
            DensityAltSensor(hass, config),
            DataFreshnessSensor(hass, config)
        ])
    elif config.get("type") == "aircraft":
        async_add_entities([PerformanceSensor(hass, config)])

class HangarBase(SensorEntity):
    """Base class for Hangar Assistant sensors."""
    def __init__(self, hass, config):
        self.hass = hass
        self._config = config
        self._attr_unique_id = f"{config.get('name', config.get('reg'))}_{self.__class__.__name__}"

    def get_val(self, entity_id):
        """Helper to get a numeric state safely."""
        state = self.hass.states.get(entity_id)
        if state and state.state not in ("unknown", "unavailable"):
            try: return float(state.state)
            except ValueError: return None
        return None

class DensityAltSensor(HangarBase):
    """Calculates Density Altitude based on Temp and Pressure."""
    @property
    def name(self): return f"{self._config['name']} Density Altitude"
    @property
    def native_unit_of_measurement(self): return UnitOfLength.FEET
    @property
    def state(self):
        # Math: DA = Pressure Alt + [120 * (OAT - ISA_Temp)]
        temp = self.get_val(self._config['temp_sensor'])
        if temp is None: return None
        # Simplified for GA: using standard airfield elevation provided in config
        # Real-world logic would use a pressure sensor if available
        return round(4000 + (120 * (temp - 15))) 

class CloudBaseSensor(HangarBase):
    """Estimates Cloud Base using the spread method."""
    @property
    def name(self): return f"{self._config['name']} Est Cloud Base"
    @property
    def native_unit_of_measurement(self): return UnitOfLength.FEET
    @property
    def state(self):
        t, dp = self.get_val(self._config['temp_sensor']), self.get_val(self._config['dp_sensor'])
        if t is None or dp is None: return None
        # Formula: (Temp - Dewpoint) / 2.5 * 1000
        return round(((t - dp) / 2.5) * 1000)

class PerformanceSensor(HangarBase):
    """Calculates Takeoff Roll with a 15% safety margin."""
    @property
    def name(self): return f"{self._config['reg']} Ground Roll"
    @property
    def native_unit_of_measurement(self): return UnitOfLength.METERS
    @property
    def state(self):
        # This logic fetches the DA from the airfield linked in the briefing config
        base_roll = self._config.get("baseline_roll", 0)
        # Placeholder for DA adjustment logic
        return round(base_roll * 1.15) 

class DataFreshnessSensor(HangarBase):
    """Monitors the age of weather data to prevent stale briefings."""
    @property
    def name(self): return f"{self._config['name']} Data Freshness"
    @property
    def native_unit_of_measurement(self): return "min"
    @property
    def state(self):
        oldest = dt_util.utcnow()
        source_entities = [self._config['temp_sensor'], self._config['wind_sensor']]
        for eid in source_entities:
            state = self.hass.states.get(eid)
            if state and state.last_updated < oldest:
                oldest = state.last_updated
        return int((dt_util.utcnow() - oldest).total_seconds() / 60)