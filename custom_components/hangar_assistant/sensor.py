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
    global_settings = entry.data.get("settings", {})
    for airfield in entry.data.get("airfields", []):
        entities.extend([
            DensityAltSensor(hass, airfield, global_settings),
            CloudBaseSensor(hass, airfield),
            DataFreshnessSensor(hass, airfield),
            CarbRiskSensor(hass, airfield),
            CarbRiskTransitionSensor(hass, airfield),
            BestRunwaySensor(hass, airfield),
            PrimaryRunwayCrosswindSensor(hass, airfield),
            IdealRunwayCrosswindSensor(hass, airfield),
            AIBriefingSensor(hass, airfield),
            AirfieldWeatherPassThrough(hass, airfield, "temp_sensor", "Temperature", SensorDeviceClass.TEMPERATURE, "°C"),
            AirfieldWeatherPassThrough(hass, airfield, "dp_sensor", "Dew Point", SensorDeviceClass.TEMPERATURE, "°C"),
            AirfieldWeatherPassThrough(hass, airfield, "pressure_sensor", "Pressure", SensorDeviceClass.PRESSURE, "hPa"),
            AirfieldWeatherPassThrough(hass, airfield, "wind_sensor", "Wind Speed", SensorDeviceClass.WIND_SPEED, "kt"),
            AirfieldWeatherPassThrough(hass, airfield, "wind_dir_sensor", "Wind Direction", None, "°")
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
                "primary_runway": self._config.get("primary_runway"),
                "runway_length_m": self._config.get("runway_length"),
                "latitude": self._config.get("latitude"),
                "longitude": self._config.get("longitude"),
                "elevation_m": self._config.get("elevation"),
                "temp_sensor": self._config.get("temp_sensor"),
                "dp_sensor": self._config.get("dp_sensor"),
                "pressure_sensor": self._config.get("pressure_sensor"),
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

    def __init__(self, hass: HomeAssistant, config: dict, global_settings: dict = None):
        super().__init__(hass, config)
        self._global_settings = global_settings or {}
        self._source_entities = []
        if sensor := config.get('temp_sensor'):
            self._source_entities.append(sensor)
        if sensor := config.get('pressure_sensor'):
            self._source_entities.append(sensor)
        elif global_sensor := self._global_settings.get('global_pressure_sensor'):
            self._source_entities.append(global_sensor)

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Density Altitude"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        t_id = self._config.get('temp_sensor')
        p_id = self._config.get('pressure_sensor')
        gp_id = self._global_settings.get('global_pressure_sensor')
        elevation_m = self._config.get('elevation', 0)
        
        temp = self._get_sensor_value(t_id) if t_id else None
        
        # Priority: Airfield Sensor -> Global Sensor -> Default Value
        pressure = None
        if p_id:
            pressure = self._get_sensor_value(p_id)
        if pressure is None and gp_id:
            pressure = self._get_sensor_value(gp_id)
        if pressure is None:
            pressure = self._global_settings.get('default_pressure', 1013.25)
        
        if temp is None:
            return None

        # Convert elevation to feet
        elevation_ft = elevation_m * 3.28084

        # Calculate Pressure Altitude (PA)
        # PA = Elevation + (Standard - Current) * Factor
        pa = elevation_ft
        if pressure:
            if pressure > 500: # hPa
                pa += (1013.25 - pressure) * 30 
            else: # inHg
                pa += (29.92 - pressure) * 1000
        
        # Standard Aviation Formula: DA = PA + (120 * (OAT - ISA_Temp_at_alt))
        # ISA Temp drops ~2C per 1000ft
        isa_temp = 15 - (2 * (elevation_ft / 1000))
        return round(pa + (120 * (temp - isa_temp)))

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

class CarbRiskTransitionSensor(HangarSensorBase):
    """Calculates the altitude (AGL) where Carb Risk increases from Low."""
    _attr_native_unit_of_measurement = UnitOfLength.FEET

    def __init__(self, hass: HomeAssistant, config: dict):
        super().__init__(hass, config)
        t_sensor = config.get('temp_sensor')
        dp_sensor = config.get('dp_sensor')
        if t_sensor and dp_sensor:
            self._source_entities = [t_sensor, dp_sensor]

    @property
    def name(self) -> str:
        return "Carb Risk Transition Alt"

    @property
    def native_value(self) -> int | None:
        t_id = self._config.get('temp_sensor')
        dp_id = self._config.get('dp_sensor')
        if not t_id or not dp_id:
            return 0
            
        t0 = self._get_sensor_value(t_id)
        dp0 = self._get_sensor_value(dp_id)
        if t0 is None or dp0 is None:
            return 0
        
        # Risk is NOT Low if T < 30 AND Spread < 10
        # Transition happens when BOTH conditions are met.
        # But usually we want to know when we enter the "Moderate" zone.
        # Rule of thumb: T drops 2C/1000ft, Spread closes 1.5C/1000ft.
        
        spread0 = t0 - dp0
        
        # If already in risk, transition is 0
        if t0 < 30 and spread0 < 10:
            return 0
            
        # Alt to hit T=30
        alt_t30 = ((t0 - 30) / 2) * 1000 if t0 > 30 else 99999
        # Alt to hit Spread=10
        alt_s10 = ((spread0 - 10) / 1.5) * 1000 if spread0 > 10 else 99999
        
        # Transition occurs when we enter the "Moderate Risk" box.
        # This is a simplification, but we take the lower of the two 
        # that actually gets us into the T<30 and Spread<10 criteria.
        res = max(0, min(alt_t30, alt_s10))
        return round(res) if res < 20000 else 0

class PrimaryRunwayCrosswindSensor(HangarSensorBase):
    """Reports crosswind component for the Primary Runway."""
    _attr_native_unit_of_measurement = "kt"

    def __init__(self, hass: HomeAssistant, config: dict):
        super().__init__(hass, config)
        w_sensor = config.get('wind_sensor')
        wd_sensor = config.get('wind_dir_sensor')
        if w_sensor and wd_sensor:
            self._source_entities = [w_sensor, wd_sensor]

    @property
    def name(self) -> str:
        return "Primary Runway Crosswind"

    @property
    def native_value(self) -> float | None:
        w_id = self._config.get('wind_sensor')
        wd_id = self._config.get('wind_dir_sensor')
        primary = self._config.get('primary_runway')
        
        if not w_id or not wd_id or not primary:
            return None
            
        wind_speed = self._get_sensor_value(w_id)
        wind_dir = self._get_sensor_value(wd_id)
        
        if wind_speed is None or wind_dir is None:
            return None

        try:
            rwy_heading = int(primary.strip()) * 10
            angle_rad = math.radians(wind_dir - rwy_heading)
            return round(abs(wind_speed * math.sin(angle_rad)), 1)
        except (ValueError, TypeError):
            return None

class IdealRunwayCrosswindSensor(HangarSensorBase):
    """Reports crosswind component for the Ideal (Least Crosswind) Runway."""
    _attr_native_unit_of_measurement = "kt"

    def __init__(self, hass: HomeAssistant, config: dict):
        super().__init__(hass, config)
        w_sensor = config.get('wind_sensor')
        wd_sensor = config.get('wind_dir_sensor')
        if w_sensor and wd_sensor:
            self._source_entities = [w_sensor, wd_sensor]

    @property
    def name(self) -> str:
        return "Ideal Runway Crosswind"

    @property
    def native_value(self) -> float | None:
        # We find the best runway first (re-using logic from BestRunwaySensor)
        wd_id = self._config.get('wind_dir_sensor')
        w_id = self._config.get('wind_sensor')
        config_runways = self._config.get("runways")
        
        if not wd_id or not w_id or not config_runways:
            return None
            
        wind_dir = self._get_sensor_value(wd_id)
        wind_speed = self._get_sensor_value(w_id)
        
        if wind_dir is None or wind_speed is None:
            return None

        runways = [r.strip() for r in config_runways.split(",")]
        min_xwind = 999

        for r in runways:
            try:
                heading = int(r) * 10
                angle_rad = math.radians(wind_dir - heading)
                xwind = abs(wind_speed * math.sin(angle_rad))
                if xwind < min_xwind:
                    min_xwind = xwind
            except (ValueError, TypeError):
                continue

        return round(min_xwind, 1) if min_xwind != 999 else None

class AIBriefingSensor(HangarSensorBase):
    """Stores the latest AI-generated pre-flight briefing for the airfield."""
    
    _attr_icon = "mdi:robot-confused" # Default icon until text arrives

    def __init__(self, hass: HomeAssistant, config: dict):
        super().__init__(hass, config)
        self._state = "Waiting for first briefing..."
        self._last_update = None

    @property
    def name(self) -> str:
        return "AI Pre-flight Briefing"

    @property
    def native_value(self) -> str:
        return self._state

    @property
    def extra_state_attributes(self) -> dict:
        attrs = super().extra_state_attributes
        attrs["last_updated"] = self._last_update
        return attrs

    async def async_added_to_hass(self) -> None:
        """Register for AI briefing events."""
        await super().async_added_to_hass()
        
        @callback
        def _handle_ai_update(event):
            """Update state when a new AI briefing is received."""
            if event.data.get("airfield_name") == self._config.get("name"):
                # Use a task to update since we might be in a sync context
                self.hass.async_create_task(self.async_update_briefing(event.data.get("text")))
        
        self.async_on_remove(
            self.hass.bus.async_listen("hangar_assistant_ai_briefing", _handle_ai_update)
        )

    async def async_update_briefing(self, briefing_text: str):
        """Update the sensor state with new AI text."""
        self._state = briefing_text
        self._last_update = dt_util.now().isoformat()
        self._attr_icon = "mdi:robot-astray"
        self.async_write_ha_state()

class AirfieldWeatherPassThrough(HangarSensorBase):
    """Passes through a weather sensor value for dashboard consistency."""
    
    def __init__(self, hass: HomeAssistant, config: dict, sensor_key: str, label: str, device_class=None, unit=None):
        super().__init__(hass, config)
        self._sensor_key = sensor_key
        self._label = label
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        if sensor := config.get(sensor_key):
            self._source_entities = [sensor]

    @property
    def name(self) -> str:
        return f"Weather {self._label}"

    @property
    def native_value(self) -> float | None:
        sensor_id = self._config.get(self._sensor_key)
        if not sensor_id:
            return None
        return self._get_sensor_value(sensor_id)

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