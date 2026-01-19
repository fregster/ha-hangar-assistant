from __future__ import annotations

"""Sensor platform for Hangar Assistant."""
import logging
import math
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
)
from homeassistant.const import (
    UnitOfLength,
    STATE_UNKNOWN,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, 
    entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Hangar Assistant sensors dynamically from config entry lists."""
    entities = []
    
    # 1. Process Airfields from the list
    for airfield in entry.data.get("airfields", []):
        entities.extend([
            DensityAltSensor(hass, airfield),
            CloudBaseSensor(hass, airfield),
            DataFreshnessSensor(hass, airfield),
            CarbRiskSensor(hass, airfield),
            BestRunwaySensor(hass, airfield)
        ])

    # 2. Process Aircraft from the list
    for aircraft in entry.data.get("aircraft", []):
        entities.append(GroundRollSensor(hass, aircraft))

    # Add all generated entities to the system
    async_add_entities(entities)

class HangarSensorBase(SensorEntity):
    """Common logic for all Hangar Assistant sensors."""
    
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, config: dict):
        """Initialize the sensor."""
        self.hass = hass
        self._config = config
        # Use Name or Reg to create a safe unique ID 
        name_or_reg = config.get("name") or config.get("reg") or "unknown"
        self._id_slug = name_or_reg.lower().replace(" ", "_")
        self._attr_unique_id = f"{self._id_slug}_{self.__class__.__name__.lower()}"
        
        # Link to a Device in the UI for cleaner grouping
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._id_slug)},
            name=config.get("name") or config.get("reg"),
            manufacturer="Fregster Aviation",
            model="Hangar Assistant v2601.1",
        )
        self._source_entities: list[str] = []

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes of the sensor."""
        attrs = {}
        
        # Add relevant config data to attributes for UI visibility
        if "reg" in self._config:
            # Aircraft specific attributes
            attrs.update({
                "registration": self._config.get("reg"),
                "model": self._config.get("model"),
                "mtow_kg": self._config.get("max_tow"),
                "empty_weight_kg": self._config.get("empty_weight"),
                "max_xwind_kt": self._config.get("max_xwind"),
                "poh_ground_roll_m": self._config.get("baseline_roll"),
                "poh_50ft_dist_m": self._config.get("baseline_50ft"),
            })
        elif "runways" in self._config:
            # Airfield specific attributes
            attrs.update({
                "runways": self._config.get("runways"),
                "runway_length_m": self._config.get("runway_lengths"),
                "latitude": self._config.get("latitude"),
                "longitude": self._config.get("longitude"),
            })
            
        return attrs

    async def async_added_to_hass(self) -> None:
        """Register callbacks for source entities."""
        if not self._source_entities:
            return

        @callback
        def _update_state(event):
            """Update the sensor state when a source entity changes."""
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._source_entities, _update_state
            )
        )

    def _get_sensor_value(self, entity_id: str) -> float | None:
        """Safely fetch and convert a sensor state to float."""
        state = self.hass.states.get(entity_id)
        if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                return float(state.state)
            except ValueError:
                _LOGGER.warning("Could not convert %s state to float: %s", entity_id, state.state)
                return None
        return None

# --- AIRFIELD ENTITIES ---

class DensityAltSensor(HangarSensorBase):
    """Calculates Density Altitude for a specific airfield."""
    _attr_native_unit_of_measurement = UnitOfLength.FEET
    _attr_device_class = SensorDeviceClass.DISTANCE

    def __init__(self, hass: HomeAssistant, config: dict):
        super().__init__(hass, config)
        if sensor := config.get('temp_sensor'):
            self._source_entities = [sensor]

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Density Altitude"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        sensor_id = self._config.get('temp_sensor')
        if not sensor_id:
            return None
            
        temp = self._get_sensor_value(sensor_id)
        if temp is None:
            return None
        # Standard Aviation Formula: DA = Pressure Alt + (120 * (OAT - ISA_Temp))
        return round(4000 + (120 * (temp - 15)))

class CloudBaseSensor(HangarSensorBase):
    """Estimates Cloud Base height (AGL) for a specific airfield."""
    _attr_native_unit_of_measurement = UnitOfLength.FEET

    def __init__(self, hass: HomeAssistant, config: dict):
        super().__init__(hass, config)
        t_sensor = config.get('temp_sensor')
        dp_sensor = config.get('dp_sensor')
        if t_sensor and dp_sensor:
            self._source_entities = [t_sensor, dp_sensor]

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Est Cloud Base"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        t_id = self._config.get('temp_sensor')
        dp_id = self._config.get('dp_sensor')
        if not t_id or not dp_id:
            return None
            
        t = self._get_sensor_value(t_id)
        dp = self._get_sensor_value(dp_id)
        if t is None or dp is None:
            return None
        return round(((t - dp) / 2.5) * 1000)

class DataFreshnessSensor(HangarSensorBase):
    """Monitors age of weather data in minutes."""
    _attr_native_unit_of_measurement = "min"
    _attr_should_poll = True

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Weather Data Age"

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        sensor_id = self._config.get('temp_sensor')
        if not sensor_id:
            return None
            
        state = self.hass.states.get(sensor_id)
        if not state:
            return None
        from homeassistant.util import dt as dt_util
        diff = dt_util.utcnow() - state.last_updated
        return int(diff.total_seconds() / 60)

class CarbRiskSensor(HangarSensorBase):
    """Assesses Carb Icing Risk level."""
    
    def __init__(self, hass: HomeAssistant, config: dict):
        super().__init__(hass, config)
        t_sensor = config.get('temp_sensor')
        dp_sensor = config.get('dp_sensor')
        if t_sensor and dp_sensor:
            self._source_entities = [t_sensor, dp_sensor]

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Carb Risk"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        t_id = self._config.get('temp_sensor')
        dp_id = self._config.get('dp_sensor')
        if not t_id or not dp_id:
            return "Unknown"
            
        t = self._get_sensor_value(t_id)
        dp = self._get_sensor_value(dp_id)
        if t is None or dp is None:
            return "Unknown"
        
        spread = t - dp
        if t < 25 and spread < 5:
            return "Serious Risk"
        if t < 30 and spread < 10:
            return "Moderate Risk"
        return "Low Risk"

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes for the card to use."""
        attrs = super().extra_state_attributes
        risk_level = self.native_value
        color_map = {
            "Serious Risk": "red",
            "Moderate Risk": "amber",
            "Low Risk": "green",
            "Unknown": "gray"
        }
        attrs["color"] = color_map.get(risk_level, "gray")
        return attrs

class BestRunwaySensor(HangarSensorBase):
    """Determines the best runway based on current wind."""

    def __init__(self, hass: HomeAssistant, config: dict):
        super().__init__(hass, config)
        w_sensor = config.get('wind_sensor')
        wd_sensor = config.get('wind_dir_sensor')
        if w_sensor and wd_sensor:
            self._source_entities = [w_sensor, wd_sensor]

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Best Runway"

    @property
    def native_value(self) -> str | None:
        """Return the best runway identifier."""
        wd_id = self._config.get('wind_dir_sensor')
        if not wd_id:
            return None
            
        wind_dir = self._get_sensor_value(wd_id)
        if wind_dir is None:
            return None

        # Parse runways (e.g., "03, 21")
        config_runways = self._config.get("runways")
        if not config_runways:
            return None
            
        runways = [r.strip() for r in config_runways.split(",")]
        if not runways:
            return None

        best_runway = None
        min_diff = 360

        for r in runways:
            try:
                # Convert runway "03" to 30 degrees
                heading = int(r) * 10
                diff = abs((wind_dir - heading + 180) % 360 - 180)
                if diff < min_diff:
                    min_diff = diff
                    best_runway = r
            except ValueError:
                continue

        return best_runway

    @property
    def extra_state_attributes(self) -> dict:
        """Return crosswind and headwind components."""
        attrs = super().extra_state_attributes
        w_id = self._config.get('wind_sensor')
        wd_id = self._config.get('wind_dir_sensor')
        
        if not w_id or not wd_id:
            return attrs
            
        wind_speed = self._get_sensor_value(w_id)
        wind_dir = self._get_sensor_value(wd_id)
        best_rwy = self.native_value

        if wind_speed is not None and wind_dir is not None and best_rwy:
            try:
                rwy_heading = int(best_rwy) * 10
                angle_rad = math.radians(wind_dir - rwy_heading)
                attrs["crosswind_component"] = round(abs(wind_speed * math.sin(angle_rad)), 1)
                attrs["headwind_component"] = round(wind_speed * math.cos(angle_rad), 1)
            except ValueError:
                pass
        
        return attrs

# --- AIRCRAFT ENTITIES ---

class GroundRollSensor(HangarSensorBase):
    """Calculates adjusted Takeoff Ground Roll for a specific aircraft."""
    _attr_native_unit_of_measurement = UnitOfLength.METERS

    def __init__(self, hass: HomeAssistant, config: dict):
        super().__init__(hass, config)
        self._da_sensor_id: str | None = None
        if airfield_name := config.get("linked_airfield"):
            # Predict the DA sensor ID for the linked airfield
            slug = airfield_name.lower().replace(" ", "_")
            self._da_sensor_id = f"sensor.{slug}_density_altitude"
            self._source_entities = [self._da_sensor_id]

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Calculated Ground Roll"

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        base = self._config.get("baseline_roll", 0)
        
        if self._da_sensor_id:
            da = self._get_sensor_value(self._da_sensor_id)
            if da is not None:
                # Rule of thumb: 10% increase per 1000ft DA above sea level
                # We cap DA at 0 for this simple calculation
                factor = 1 + (max(0, da) / 1000) * 0.10
                return round(base * factor)
        
        # Fallback to a static safety factor if no DA is available
        return round(base * 1.15)