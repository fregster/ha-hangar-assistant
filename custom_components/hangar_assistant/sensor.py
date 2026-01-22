from __future__ import annotations

"""Sensor platform for Hangar Assistant."""
import logging
import math
import time
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
)
from homeassistant.const import (
    STATE_UNKNOWN,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    UNIT_PREFERENCE_AVIATION,
    DEFAULT_UNIT_PREFERENCE,
    DEFAULT_STALE_WEATHER_MINUTES,
    DEFAULT_DA_CAUTION_FT,
    DEFAULT_DA_WARNING_FT,
    DEFAULT_FROST_TEMP_C,
    DEFAULT_SURFACE_ICE_SPREAD_C,
    DEFAULT_AIRFRAME_ICING_MIN_C,
    DEFAULT_AIRFRAME_ICING_MAX_C,
    DEFAULT_SATURATION_SPREAD_C,
    DEFAULT_SENSOR_CACHE_TTL_SECONDS,
)
from .utils.units import convert_altitude, convert_speed, get_altitude_unit, get_speed_unit
from .utils.notam import NOTAMClient

try:
    from timezonefinder import TimezoneFinder
except ImportError:  # pragma: no cover - handled in runtime fallback
    TimezoneFinder = None

_TZ_FINDER = TimezoneFinder() if TimezoneFinder else None

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Hangar Assistant sensors dynamically from config entry lists.

    This function creates all sensor entities based on configured airfields, aircraft, and pilots.
    For each airfield, it creates 15 sensors covering weather, performance, and safety metrics.
    For each aircraft, it creates ground roll calculation sensors.
    For each pilot, it creates qualification tracking sensors.

    Args:
        hass: Home Assistant instance for accessing state machine and config
        entry: ConfigEntry containing airfields, aircraft, pilots, and global settings
        async_add_entities: Callback to register new entities with Home Assistant

    Returns:
        None. Entities are registered via async_add_entities callback.
    """
    entities = []

    # 1. Process Airfields from the list
    global_settings = entry.data.get("settings", {})
    airfields = [
        a for a in entry.data.get(
            "airfields",
            []) if isinstance(
            a,
            dict)]
    airfield_lookup = {
        (a.get("name") or "").lower(): a for a in airfields if a.get("name")
    }

    # Check if NOTAM integration is enabled
    integrations = entry.data.get("integrations", {})
    notam_config = integrations.get("notams", {})
    notam_enabled = notam_config.get("enabled", False)
    
    # Check if CheckWX integration is enabled
    checkwx_config = integrations.get("checkwx", {})
    checkwx_enabled = checkwx_config.get("enabled", False)

    for airfield in airfields:
        entities.extend([
            DensityAltSensor(hass, airfield, global_settings),
            CloudBaseSensor(hass, airfield, global_settings),
            DataFreshnessSensor(hass, airfield, global_settings),
            CarbRiskSensor(hass, airfield, global_settings),
            CarbRiskTransitionSensor(hass, airfield, global_settings),
            IcingAdvisorySensor(hass, airfield, global_settings),
            DaylightCountdownSensor(hass, airfield, global_settings),
            BestRunwaySensor(hass, airfield, global_settings),
            PrimaryRunwayCrosswindSensor(hass, airfield, global_settings),
            IdealRunwayCrosswindSensor(hass, airfield, global_settings),
            RunwaySuitabilitySensor(hass, airfield, global_settings),
            AirfieldTimezoneSensor(hass, airfield, global_settings),
            AIBriefingSensor(hass, airfield, global_settings),
            AirfieldWeatherPassThrough(hass, airfield, "temp_sensor", "Temperature", SensorDeviceClass.TEMPERATURE, "°C", global_settings),
            AirfieldWeatherPassThrough(hass, airfield, "dp_sensor", "Dew Point", SensorDeviceClass.TEMPERATURE, "°C", global_settings),
            AirfieldWeatherPassThrough(hass, airfield, "pressure_sensor", "Pressure", SensorDeviceClass.PRESSURE, "hPa", global_settings),
            AirfieldWeatherPassThrough(hass, airfield, "wind_sensor", "Wind Speed", SensorDeviceClass.WIND_SPEED, "kn", global_settings),
            AirfieldWeatherPassThrough(hass, airfield, "wind_dir_sensor", "Wind Direction", None, "°", global_settings)
        ])

        # Add NOTAM sensor if integration is enabled
        if notam_enabled:
            entities.append(
                AirfieldNOTAMSensor(
                    hass,
                    airfield,
                    global_settings,
                    entry))
        
        # Add CheckWX sensors if integration is enabled and airfield has ICAO
        if checkwx_enabled and airfield.get("icao"):
            if checkwx_config.get("metar_enabled", True):
                entities.append(MetarSensor(hass, airfield, global_settings))
            
            if checkwx_config.get("taf_enabled", True):
                entities.append(TafSensor(hass, airfield, global_settings))
            
            if checkwx_config.get("station_enabled", True):
                entities.append(StationInfoSensor(hass, airfield, global_settings))

    # 2. Process Aircraft from the list
    for aircraft in entry.data.get("aircraft", []):
        linked_name = (aircraft.get("linked_airfield") or "").lower()
        linked_airfield = airfield_lookup.get(linked_name, {})
        entities.append(GroundRollSensor(hass, aircraft, global_settings))
        entities.append(
            PerformanceMarginSensor(
                hass,
                aircraft,
                linked_airfield,
                global_settings))
        
        # Add fuel sensors if fuel burn rate is configured
        fuel_config = aircraft.get("fuel", {})
        burn_rate = fuel_config.get("burn_rate", 0.0)
        if burn_rate > 0:
            entities.extend([
                FuelBurnRateSensor(hass, aircraft, global_settings),
                FuelEnduranceSensor(hass, aircraft, global_settings),
                FuelWeightSensor(hass, aircraft, global_settings),
            ])

    # 3. Process Pilots from the list
    for pilot in entry.data.get("pilots", []):
        entities.append(PilotInfoSensor(hass, pilot, global_settings))

    # 4. Add global integration health sensor
    entities.append(IntegrationHealthSensor(hass, entry, global_settings))

    # Add all generated entities to the system
    async_add_entities(entities)


class HangarSensorBase(SensorEntity):
    """Base class for all Hangar Assistant sensors.

    Provides common functionality for sensor initialization, device grouping, state tracking,
    and entity callbacks. All specialized sensors (DensityAltSensor, CarbRiskSensor, etc.)
    inherit from this class.

    Key features:
    - Automatic device grouping by airfield/aircraft via _id_slug
    - Safe state retrieval with _get_sensor_value() handling unavailable/unknown states
    - Extra attributes for UI display (config metadata, calculations, etc.)
    - State change callbacks to update when source entities change
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    # Shared state cache across all sensors (LRU with TTL)
    _state_cache: OrderedDict[str, tuple] = OrderedDict()
    _cache_ttl_seconds: int = DEFAULT_SENSOR_CACHE_TTL_SECONDS
    _max_cache_entries: int = 50

    def __init__(self, hass: HomeAssistant, config: dict,
                 global_settings: dict | None = None):
        """Initialize the sensor.

        Args:
            hass: Home Assistant instance
            config: Configuration dict for this sensor
            global_settings: Global settings including unit preference
        """
        self.hass = hass
        self._config = config
        self._global_settings = global_settings or {}
        self._unit_preference = self._global_settings.get(
            "unit_preference", DEFAULT_UNIT_PREFERENCE)
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

        # Initialize cache for sensor value lookups
        # {entity_id: (value, timestamp)}
        self._sensor_cache: dict[str, tuple[float, float]] = {}

    def _get_cached_state(self, cache_key: str):
        """Retrieve cached state if still valid (LRU-managed)."""
        if cache_key in self._state_cache:
            cached_value, cached_time = self._state_cache[cache_key]
            age = (dt_util.utcnow() - cached_time).total_seconds()
            if age < self._cache_ttl_seconds:
                self._state_cache.move_to_end(cache_key)
                return cached_value
        return None

    def _cache_state(self, cache_key: str, value) -> None:
        """Cache a state value with TTL and LRU eviction."""
        self._state_cache[cache_key] = (value, dt_util.utcnow())
        self._state_cache.move_to_end(cache_key)

        while len(self._state_cache) > self._max_cache_entries:
            self._state_cache.popitem(last=False)

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
                "icao_code": self._config.get("icao_code"),
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
        def _update_state(_event):
            """Update the sensor state when a source entity changes."""
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._source_entities, _update_state
            )
        )

    def _get_sensor_value(self, entity_id: str) -> float | None:
        """Safely fetch and convert a sensor state to float with TTL-based caching.

        Implements a simple time-based cache to reduce redundant state lookups.
        Cache entries expire after cache_ttl_seconds (default 60s).

        Args:
            entity_id: The entity ID to fetch the value for

        Returns:
            Float value of the sensor state, or None if unavailable/invalid
        """
        # Get cache TTL from global settings
        cache_ttl = self._global_settings.get(
            "cache_ttl_seconds", DEFAULT_SENSOR_CACHE_TTL_SECONDS)
        current_time = time.time()

        # Check cache first
        if entity_id in self._sensor_cache:
            cached_value, cached_time = self._sensor_cache[entity_id]
            if current_time - cached_time < cache_ttl:
                return cached_value

        # Cache miss or expired - fetch fresh value
        state = self.hass.states.get(entity_id)
        if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                value = float(state.state)
                # Store in cache with current timestamp
                self._sensor_cache[entity_id] = (value, current_time)

                # Cleanup: prevent unbounded growth (keep max 50 entries)
                if len(self._sensor_cache) > 50:
                    # Remove oldest entry
                    oldest_key = min(
                        self._sensor_cache.items(),
                        key=lambda x: x[1][1])[0]
                    del self._sensor_cache[oldest_key]

                return value
            except ValueError:
                _LOGGER.warning(
                    "Could not convert %s state to float: %s",
                    entity_id,
                    state.state)
                return None
        return None

# --- AIRFIELD ENTITIES ---


class DensityAltSensor(HangarSensorBase):
    """Calculates Density Altitude (DA) for an airfield.

    Density Altitude is the effective altitude experienced by an aircraft's engines due to
    temperature and pressure conditions. Higher DA means thinner air, reducing aircraft performance.

    Formula: DA = PA + (120 * (OAT - ISA_temp_at_altitude))
    Where: PA = Pressure Altitude (elevation adjusted for barometric pressure)

    Inputs (from config):
        - elevation: Airfield elevation in meters
        - temp_sensor: Entity ID of temperature sensor (°C)
        - pressure_sensor: Entity ID of pressure sensor (hPa or inHg)

    Outputs:
        - native_value: Calculated Density Altitude in feet or meters based on unit preference
        - Range: Typically 500-10000 ft (1500-3000 m)

    Used by:
        - GroundRollSensor to adjust takeoff distance calculations
        - Dashboard to indicate aircraft performance capability
    """

    def __init__(self, hass: HomeAssistant, config: dict,
                 global_settings: dict | None = None):
        super().__init__(hass, config, global_settings)
        self._source_entities = []
        if sensor := config.get('temp_sensor'):
            self._source_entities.append(sensor)
        if sensor := config.get('pressure_sensor'):
            self._source_entities.append(sensor)
        elif global_sensor := self._global_settings.get('global_pressure_sensor'):
            self._source_entities.append(global_sensor)
        # Set unit based on preference
        self._attr_native_unit_of_measurement = get_altitude_unit(
            self._unit_preference)
        self._da_caution_ft = self._global_settings.get(
            "da_caution_ft", DEFAULT_DA_CAUTION_FT)
        self._da_warning_ft = self._global_settings.get(
            "da_warning_ft", DEFAULT_DA_WARNING_FT)

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Density Altitude"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor.

        Calculates DA in feet, then converts to user's preferred unit.
        """
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

        # Convert elevation to feet for calculation
        elevation_ft = elevation_m * 3.28084

        # Calculate Pressure Altitude (PA)
        # PA = Elevation + (Standard - Current) * Factor
        pa = elevation_ft
        if pressure:
            if pressure > 500:  # hPa
                pa += (1013.25 - pressure) * 30
            else:  # inHg
                pa += (29.92 - pressure) * 1000

        # Standard Aviation Formula: DA = PA + (120 * (OAT - ISA_Temp_at_alt))
        # ISA Temp drops ~2C per 1000ft
        isa_temp = 15 - (2 * (elevation_ft / 1000))
        da_feet = round(pa + (120 * (temp - isa_temp)))

        # Convert to user's preferred unit
        converted = convert_altitude(
            da_feet,
            from_feet=True,
            to_preference=self._unit_preference)
        return round(converted) if converted is not None else None

    @property
    def extra_state_attributes(self) -> dict:
        """Return density altitude advisory banner metadata."""
        attrs = super().extra_state_attributes

        da_value = self.native_value
        da_unit = self._attr_native_unit_of_measurement
        da_feet = None
        if da_value is not None:
            if self._unit_preference == UNIT_PREFERENCE_AVIATION:
                da_feet = da_value
            else:
                da_feet = convert_altitude(
                    da_value,
                    from_feet=False,
                    to_preference=UNIT_PREFERENCE_AVIATION,
                )
        da_feet = round(da_feet) if da_feet is not None else None

        status = "Unknown DA"
        severity = "unknown"
        recommendation = "Waiting for weather data."

        if da_feet is not None:
            status = "Nominal DA"
            severity = "normal"
            recommendation = "Performance near standard day; verify usual margins."
            if da_feet >= self._da_warning_ft:
                status = "High DA"
                severity = "warning"
                recommendation = "Significant performance penalty; ensure runway and climb margins."
            elif da_feet >= self._da_caution_ft:
                status = "Elevated DA"
                severity = "caution"
                recommendation = "Expect longer ground roll; lean mixture and confirm takeoff distance."

        attrs.update(
            {
                "da_status": status,
                "da_severity": severity,
                "da_recommendation": recommendation,
                "da_feet": da_feet,
                "da_unit": da_unit,
                "da_caution_threshold_ft": self._da_caution_ft,
                "da_warning_threshold_ft": self._da_warning_ft,
            }
        )
        return attrs


class CloudBaseSensor(HangarSensorBase):
    """Estimates cloud base height Above Ground Level (AGL).

    Uses the relationship between temperature and dew point to estimate where clouds form.
    This is important for VFR flying to ensure adequate cloud clearance.

    Formula: Cloud Base (ft AGL) = ((T - DP) / 2.5) * 1000
    Where: T = Temperature, DP = Dew Point (both in °C)

    Inputs (from config):
        - temp_sensor: Entity ID of temperature sensor (°C)
        - dp_sensor: Entity ID of dew point sensor (°C)

    Outputs:
        - native_value: Estimated cloud base in feet or meters above ground
        - Range: Typically 500-10000 ft (150-3000 m)

    Limitations:
        - Assumes typical atmospheric lapse rate
        - Only valid when T > DP (unsaturated air)
    """

    def __init__(self, hass: HomeAssistant, config: dict,
                 global_settings: dict | None = None):
        super().__init__(hass, config, global_settings)
        t_sensor = config.get('temp_sensor')
        dp_sensor = config.get('dp_sensor')
        if t_sensor and dp_sensor:
            self._source_entities = [t_sensor, dp_sensor]
        # Set unit based on preference
        self._attr_native_unit_of_measurement = get_altitude_unit(
            self._unit_preference)

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Est Cloud Base"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor.

        Calculates cloud base in feet, then converts to user's preferred unit.
        """
        t_id = self._config.get('temp_sensor')
        dp_id = self._config.get('dp_sensor')
        if not t_id or not dp_id:
            return None

        t = self._get_sensor_value(t_id)
        dp = self._get_sensor_value(dp_id)
        if t is None or dp is None:
            return None

        cb_feet = round(((t - dp) / 2.5) * 1000)
        # Convert to user's preferred unit
        converted = convert_altitude(
            cb_feet,
            from_feet=True,
            to_preference=self._unit_preference)
        return round(converted) if converted is not None else None


class DataFreshnessSensor(HangarSensorBase):
    """Monitors the age of weather sensor data to ensure currency.

    Tracks how long it's been since the temperature sensor last reported a value.
    This is critical for safety - stale data can lead to incorrect decisions.

    Inputs (from config):
        - temp_sensor: Entity ID of temperature sensor

    Outputs:
        - native_value: Age of data in minutes
        - Unit: min

    Thresholds:
        - < 5 min: Fresh (recommended for flight decisions)
        - 5-30 min: Acceptable
        - > 30 min: Stale (triggers Master Safety Alert)

    Used by:
        - HangarMasterSafetyAlert to trigger safety annunciator
        - Dashboard to indicate data reliability
    """
    _attr_native_unit_of_measurement = "min"
    _attr_should_poll = True

    def __init__(self, hass: HomeAssistant, config: dict,
                 global_settings: dict | None = None):
        super().__init__(hass, config, global_settings)
        self._stale_threshold = (
            global_settings or {}).get(
            "stale_weather_minutes",
            DEFAULT_STALE_WEATHER_MINUTES)

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

    @property
    def extra_state_attributes(self) -> dict:
        attrs = super().extra_state_attributes
        age_minutes = self.native_value
        threshold = self._stale_threshold or DEFAULT_STALE_WEATHER_MINUTES
        status = None
        if age_minutes is not None:
            if age_minutes <= 5:
                status = "fresh"
            elif age_minutes <= threshold:
                status = "acceptable"
            else:
                status = "stale"
        attrs.update(
            {
                "status": status,
                "threshold_minutes": threshold,
            }
        )
        return attrs


class CarbRiskSensor(HangarSensorBase):
    """Assesses carburetor icing risk based on temperature and humidity.

    Carburetor icing occurs when moisture in air freezes in the carburetor, potentially
    blocking fuel flow and causing engine failure. This is a serious hazard for piston aircraft.

    Risk Assessment Rules:
        - Serious Risk: T < 25°C AND Spread < 5°C (highly saturated air)
        - Moderate Risk: T < 30°C AND Spread < 10°C
        - Low Risk: All other conditions

    Where: Spread = Temperature - Dew Point (measure of humidity)

    Inputs (from config):
        - temp_sensor: Entity ID of temperature sensor (°C)
        - dp_sensor: Entity ID of dew point sensor (°C)

    Outputs:
        - native_value: Risk level string (\"Low Risk\", \"Moderate Risk\", \"Serious Risk\", \"Unknown\")
        - color: Attribute with risk color (green/amber/red/gray)

    Used by:
        - HangarMasterSafetyAlert to trigger when risk is \"Serious\"
        - Dashboard to highlight icing conditions
    """

    def __init__(self, hass: HomeAssistant, config: dict,
                 global_settings: dict | None = None):
        super().__init__(hass, config, global_settings)
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
    """Calculates the altitude where carburetor icing risk transitions from \"Low\" to \"Moderate\".

    Uses atmospheric lapse rates to predict when climbing will create carb icing conditions.
    This helps pilots avoid icing altitudes or prepare anti-ice systems.

    Assumptions:
        - Temperature decreases ~2°C per 1000 ft climb
        - Dew point spread closes ~1.5°C per 1000 ft climb

    Inputs (from config):
        - temp_sensor: Current temperature (°C)
        - dp_sensor: Current dew point (°C)

    Outputs:
        - native_value: Transition altitude in feet or meters AGL
        - 0 = Already in risk or no transition expected

    Used by:
        - Pilot briefing to indicate altitude restrictions
        - Flight planning to recommend flight levels
    """

    def __init__(self, hass: HomeAssistant, config: dict,
                 global_settings: dict | None = None):
        super().__init__(hass, config, global_settings)
        t_sensor = config.get('temp_sensor')
        dp_sensor = config.get('dp_sensor')
        if t_sensor and dp_sensor:
            self._source_entities = [t_sensor, dp_sensor]
        # Set unit based on preference
        self._attr_native_unit_of_measurement = get_altitude_unit(
            self._unit_preference)

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
        alt_feet = round(res) if res < 20000 else 0

        # Convert to user's preferred unit
        converted = convert_altitude(
            alt_feet,
            from_feet=True,
            to_preference=self._unit_preference)
        return round(converted) if converted is not None else None


class IcingAdvisorySensor(HangarSensorBase):
    """Provides a consolidated frost/carb/icing advisory strip for an airfield.

    This sensor fuses surface frost risk, carburetor icing risk, and in-flight
    icing potential into a single advisory string suitable for dashboard display.
    It draws from ambient temperature, dew point, and the sibling `CarbRiskSensor`
    to highlight when de-icing, carb heat, or icing avoidance procedures may be
    required.

    Inputs:
        - temp_sensor: Airfield temperature sensor (°C)
        - dp_sensor: Airfield dew point sensor (°C)
        - carb risk entity (sibling): sensor.{slug}_carb_risk (optional)

    Outputs/Behavior:
        - native_value: Advisory label (e.g., "Surface Ice Risk", "Frost Risk",
          "Airframe Icing Potential", "Serious Carb Icing", "Clear")
        - Attributes: severity (normal/caution/warning), recommendation text,
          flags for frost/surface ice/airframe icing potential, carb risk level,
          dewpoint spread, and thresholds used

    Used by:
        - Dashboard icing strip for pilots/CFIs
        - Preflight briefing to flag anti-ice/ground de-icing needs
    """

    _attr_icon = "mdi:snowflake-alert"

    def __init__(self, hass: HomeAssistant, config: dict,
                 global_settings: dict | None = None):
        super().__init__(hass, config, global_settings)
        t_sensor = config.get("temp_sensor")
        dp_sensor = config.get("dp_sensor")
        self._source_entities = [e for e in (t_sensor, dp_sensor) if e]

        self._frost_temp_c = self._global_settings.get(
            "frost_temp_c", DEFAULT_FROST_TEMP_C)
        self._surface_ice_spread_c = self._global_settings.get(
            "surface_ice_spread_c", DEFAULT_SURFACE_ICE_SPREAD_C)
        self._airframe_icing_min_c = self._global_settings.get(
            "airframe_icing_min_c", DEFAULT_AIRFRAME_ICING_MIN_C)
        self._airframe_icing_max_c = self._global_settings.get(
            "airframe_icing_max_c", DEFAULT_AIRFRAME_ICING_MAX_C)
        self._saturation_spread_c = self._global_settings.get(
            "saturation_spread_c", DEFAULT_SATURATION_SPREAD_C)
        self._carb_entity_id = f"sensor.{self._id_slug}_carb_risk"

    @property
    def name(self) -> str:
        return "Icing Advisory"

    def _get_carb_level(self) -> str:
        state = self.hass.states.get(self._carb_entity_id)
        if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return str(state.state)
        return "Unknown"

    def _evaluate(self) -> dict:
        t_id = self._config.get("temp_sensor")
        dp_id = self._config.get("dp_sensor")
        if not t_id or not dp_id:
            return {
                "label": "Unknown",
                "severity": "unknown",
                "recommendation": "Waiting for temperature and dew point.",
                "frost_risk": False,
                "surface_ice_risk": False,
                "airframe_icing_potential": False,
                "carb_risk_level": "Unknown",
                "spread_c": None,
                "temp_c": None,
            }

        temp = self._get_sensor_value(t_id)
        dp = self._get_sensor_value(dp_id)
        if temp is None or dp is None:
            return {
                "label": "Unknown",
                "severity": "unknown",
                "recommendation": "Waiting for temperature and dew point.",
                "frost_risk": False,
                "surface_ice_risk": False,
                "airframe_icing_potential": False,
                "carb_risk_level": "Unknown",
                "spread_c": None,
                "temp_c": temp,
            }

        spread = temp - dp
        frost_risk = 0 < temp <= self._frost_temp_c and spread <= self._saturation_spread_c
        surface_ice_risk = temp <= 0 and spread <= self._surface_ice_spread_c
        airframe_icing_potential = (
            self._airframe_icing_min_c <= temp <= self._airframe_icing_max_c
            and spread <= self._saturation_spread_c
        )
        carb_level = self._get_carb_level()

        label = "Clear"
        severity = "normal"
        recommendation = "No immediate icing or frost risks detected."

        if surface_ice_risk:
            label = "Surface Ice Risk"
            severity = "warning"
            recommendation = "Plan for de-icing and braking performance checks."
        elif frost_risk:
            label = "Frost Risk"
            severity = "caution"
            recommendation = "Inspect for frost; consider de-icing or sun warm-up."
        elif airframe_icing_potential:
            label = "Airframe Icing Potential"
            severity = "warning"
            recommendation = "Expect icing in visible moisture; plan anti-ice and escape strategy."
        elif carb_level == "Serious Risk":
            label = "Serious Carb Icing"
            severity = "warning"
            recommendation = "Use carb heat proactively; avoid low power in moisture."
        elif carb_level == "Moderate Risk":
            label = "Moderate Carb Icing"
            severity = "caution"
            recommendation = "Monitor carb temps; apply heat during descent or low power."

        return {
            "label": label,
            "severity": severity,
            "recommendation": recommendation,
            "frost_risk": frost_risk,
            "surface_ice_risk": surface_ice_risk,
            "airframe_icing_potential": airframe_icing_potential,
            "carb_risk_level": carb_level,
            "spread_c": round(spread, 1),
            "temp_c": round(temp, 1),
        }

    @property
    def native_value(self) -> str:
        return self._evaluate().get("label", "Unknown")

    @property
    def extra_state_attributes(self) -> dict:
        attrs = super().extra_state_attributes
        data = self._evaluate()
        attrs.update({"severity": data.get("severity"),
                      "recommendation": data.get("recommendation"),
                      "frost_risk": data.get("frost_risk"),
                      "surface_ice_risk": data.get("surface_ice_risk"),
                      "airframe_icing_potential": data.get("airframe_icing_potential"),
                      "carb_risk_level": data.get("carb_risk_level"),
                      "dewpoint_spread_c": data.get("spread_c"),
                      "temp_c": data.get("temp_c"),
                      "frost_temp_threshold_c": self._frost_temp_c,
                      "surface_ice_spread_threshold_c": self._surface_ice_spread_c,
                      "airframe_icing_min_c": self._airframe_icing_min_c,
                      "airframe_icing_max_c": self._airframe_icing_max_c,
                      "saturation_spread_threshold_c": self._saturation_spread_c,
                      })
        return attrs


class DaylightCountdownSensor(HangarSensorBase):
    """Provides legal daylight countdowns using Home Assistant sun events.

    Calculates minutes until the end of legal daylight (sunset + 30 minutes) when
    above the horizon, or minutes until legal daylight begins (30 minutes before
    next sunrise) when below the horizon. Uses Home Assistant's `sun.sun` entity
    to avoid external dependencies and falls back gracefully if unavailable.

    Inputs:
        - sun.sun entity (global HA sun integration)

    Outputs/Behavior:
        - native_value: Minutes until the next legal daylight boundary (int)
        - Attributes: phase (day/night), next_rising/next_setting, legal daylight
          start/end timestamps, and remaining/start countdowns in minutes

    Used by:
        - Dashboard daylight countdown strip for pre-flight checks
        - Briefings to indicate day/night legality window
    """

    _attr_icon = "mdi:weather-sunset"
    _attr_native_unit_of_measurement = "min"

    def __init__(self, hass: HomeAssistant, config: dict,
                 global_settings: dict | None = None):
        super().__init__(hass, config, global_settings)
        # Track sun state changes for live countdowns
        self._source_entities = ["sun.sun"]

    @property
    def name(self) -> str:
        return "Daylight Countdown"

    def _parse_iso(self, value: str | None):
        if not value:
            return None
        parsed = None
        # Prefer Home Assistant parser if available
        if hasattr(dt_util, "parse_datetime"):
            parsed = dt_util.parse_datetime(
                value)  # type: ignore[attr-defined]
        if parsed is None:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (TypeError, ValueError):
                return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _compute(self):
        now = dt_util.utcnow()
        sun = self.hass.states.get("sun.sun")
        if not sun:
            return None

        next_rising = self._parse_iso(sun.attributes.get("next_rising"))
        next_setting = self._parse_iso(sun.attributes.get("next_setting"))
        phase = "day" if sun.state == "above_horizon" else "night"

        daylight_end = next_setting + \
            timedelta(minutes=30) if next_setting else None
        daylight_start = next_rising - \
            timedelta(minutes=30) if next_rising else None

        countdown = None
        daylight_remaining = None
        daylight_starts_in = None

        if phase == "day" and daylight_end:
            diff = (daylight_end - now).total_seconds() / 60
            countdown = max(0, int(diff))
            daylight_remaining = countdown
        elif phase == "night" and daylight_start:
            diff = (daylight_start - now).total_seconds() / 60
            countdown = max(0, int(diff))
            daylight_starts_in = countdown

        return {
            "countdown": countdown,
            "phase": phase,
            "next_rising": next_rising.isoformat() if next_rising else None,
            "next_setting": next_setting.isoformat() if next_setting else None,
            "legal_daylight_end": daylight_end.isoformat() if daylight_end else None,
            "legal_daylight_start": daylight_start.isoformat() if daylight_start else None,
            "daylight_remaining_min": daylight_remaining,
            "daylight_starts_in_min": daylight_starts_in,
        }

    @property
    def native_value(self) -> int | None:
        data = self._compute()
        if not data:
            return None
        return data.get("countdown")

    @property
    def extra_state_attributes(self) -> dict:
        attrs = super().extra_state_attributes
        data = self._compute() or {}
        attrs.update(
            {
                "phase": data.get("phase"),
                "next_rising": data.get("next_rising"),
                "next_setting": data.get("next_setting"),
                "legal_daylight_end": data.get("legal_daylight_end"),
                "legal_daylight_start": data.get("legal_daylight_start"),
                "daylight_remaining_min": data.get("daylight_remaining_min"),
                "daylight_starts_in_min": data.get("daylight_starts_in_min"),
            }
        )
        return attrs


class PrimaryRunwayCrosswindSensor(HangarSensorBase):
    """Calculates the crosswind component for the primary runway.

    Crosswind is the component of wind perpendicular to the runway direction.
    Exceeding aircraft limitations can lead to loss of directional control.

    Formula: Crosswind = Wind Speed * sin(angle between wind and runway)

    Inputs (from config):
        - wind_sensor: Entity ID of wind speed sensor (knots)
        - wind_dir_sensor: Entity ID of wind direction sensor (degrees)
        - primary_runway: Runway identifier (e.g., \"21\" for 210 degree heading)

    Outputs:
        - native_value: Calculated crosswind component in knots or kph
        - Positive value always (absolute value)

    Used by:
        - Pilot briefing to assess runway suitability
        - Dashboard to display wind compatibility
    """

    def __init__(self, hass: HomeAssistant, config: dict,
                 global_settings: dict | None = None):
        super().__init__(hass, config, global_settings)
        w_sensor = config.get('wind_sensor')
        wd_sensor = config.get('wind_dir_sensor')
        if w_sensor and wd_sensor:
            self._source_entities = [w_sensor, wd_sensor]
        # Set unit based on preference
        self._attr_native_unit_of_measurement = get_speed_unit(
            self._unit_preference)

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
            crosswind_kt = abs(wind_speed * math.sin(angle_rad))
            # Convert to user's preferred unit
            crosswind_converted = convert_speed(
                crosswind_kt, from_knots=True, to_preference=self._unit_preference)
            return round(
                crosswind_converted,
                1) if crosswind_converted else None
        except (ValueError, TypeError):
            return None


class IdealRunwayCrosswindSensor(HangarSensorBase):
    """Calculates the minimum crosswind by finding the best runway option.

    Evaluates all available runways and determines which has the least crosswind,
    helping pilots select the most favorable runway for current wind conditions.

    Inputs (from config):
        - wind_sensor: Entity ID of wind speed sensor (knots)
        - wind_dir_sensor: Entity ID of wind direction sensor (degrees)
        - runways: Comma-separated list of runway identifiers (e.g., \"03, 21\")

    Outputs:
        - native_value: Minimum crosswind component in knots or kph
        - Calculated from best runway option

    Used by:
        - BestRunwaySensor as supporting calculation
        - Dashboard to show most favorable landing option
    """

    def __init__(self, hass: HomeAssistant, config: dict,
                 global_settings: dict | None = None):
        super().__init__(hass, config, global_settings)
        w_sensor = config.get('wind_sensor')
        wd_sensor = config.get('wind_dir_sensor')
        if w_sensor and wd_sensor:
            self._source_entities = [w_sensor, wd_sensor]
        # Set unit based on preference
        self._attr_native_unit_of_measurement = get_speed_unit(
            self._unit_preference)

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
        min_xwind = 999.0

        for r in runways:
            try:
                heading = int(r) * 10
                angle_rad = math.radians(wind_dir - heading)
                xwind = abs(wind_speed * math.sin(angle_rad))
                if xwind < min_xwind:
                    min_xwind = xwind
            except (ValueError, TypeError):
                continue

        if min_xwind == 999:
            return None

        # Convert to user's preferred unit
        min_xwind_converted = convert_speed(
            min_xwind, from_knots=True, to_preference=self._unit_preference)
        return round(min_xwind_converted, 1) if min_xwind_converted else None


class RunwaySuitabilitySensor(HangarSensorBase):
    """Summarizes runway wind components and recommends the best runway.

    Provides a runway-by-runway matrix of crosswind/headwind/tailwind components using
    current wind direction and speed. Helps pilots and instructors quickly assess runway
    suitability before arrival at the airfield.

    Inputs (from config):
        - runways: Comma-separated list of runway identifiers (e.g., "03, 21")
        - wind_sensor: Entity ID of wind speed sensor (knots)
        - wind_dir_sensor: Entity ID of wind direction sensor (degrees)

    Outputs:
        - native_value: The recommended runway identifier with the lowest crosswind
        - extra_state_attributes: Runway matrix with crosswind/headwind components and
          unit-aware values for dashboard display

    Used by:
        - Dashboard suitability matrix cards
        - Crosswind envelope checks for quick decision support
    """

    _attr_icon = "mdi:run"

    def __init__(self, hass: HomeAssistant, config: dict,
                 global_settings: dict | None = None):
        super().__init__(hass, config, global_settings)
        w_sensor = config.get("wind_sensor")
        wd_sensor = config.get("wind_dir_sensor")
        if w_sensor and wd_sensor:
            self._source_entities = [w_sensor, wd_sensor]

    @property
    def name(self) -> str:
        return "Runway Suitability"

    def _evaluate_runways(
            self) -> tuple[str | None, list[dict], float | None, float | None, float | None]:
        """Compute best runway and per-runway components.

        Returns a tuple of (best_runway, matrix, min_crosswind_kt, wind_speed, wind_dir).
        Values fall back to None when inputs are missing to keep existing installs stable.
        """
        wd_id = self._config.get("wind_dir_sensor")
        w_id = self._config.get("wind_sensor")
        runways_value = self._config.get("runways")

        if not wd_id or not w_id or not runways_value:
            return None, [], None, None, None

        wind_dir = self._get_sensor_value(wd_id)
        wind_speed = self._get_sensor_value(w_id)
        if wind_dir is None or wind_speed is None:
            return None, [], None, wind_speed, wind_dir

        runways = [r.strip() for r in runways_value.split(",") if r.strip()]
        matrix: list[dict] = []
        best_runway = None
        min_crosswind = None

        for runway in runways:
            try:
                heading = int(runway) * 10
            except (ValueError, TypeError):
                continue

            angle_diff = abs((wind_dir - heading + 180) % 360 - 180)
            angle_rad = math.radians(wind_dir - heading)
            crosswind_kt = abs(wind_speed * math.sin(angle_rad))
            headwind_kt = wind_speed * math.cos(angle_rad)

            crosswind_unit = convert_speed(
                crosswind_kt,
                from_knots=True,
                to_preference=self._unit_preference)
            headwind_unit = convert_speed(
                headwind_kt,
                from_knots=True,
                to_preference=self._unit_preference)
            tailwind_unit = abs(
                headwind_unit) if headwind_unit is not None and headwind_unit < 0 else 0

            matrix.append(
                {
                    "runway": runway,
                    "heading": heading,
                    "angle_off": round(angle_diff, 1),
                    "crosswind": round(crosswind_unit, 1) if crosswind_unit is not None else None,
                    "headwind": round(headwind_unit, 1) if headwind_unit is not None else None,
                    "tailwind": round(tailwind_unit, 1) if tailwind_unit else 0,
                    "component_unit": get_speed_unit(self._unit_preference),
                }
            )

            if min_crosswind is None or crosswind_kt < min_crosswind:
                min_crosswind = crosswind_kt
                best_runway = runway

        return best_runway, matrix, min_crosswind, wind_speed, wind_dir

    @property
    def native_value(self) -> str | None:
        best_runway, _, _, _, _ = self._evaluate_runways()
        return best_runway

    @property
    def extra_state_attributes(self) -> dict:
        attrs = super().extra_state_attributes
        best_runway, matrix, min_crosswind, wind_speed, wind_dir = self._evaluate_runways()

        if matrix:
            attrs.update(
                {
                    "best_runway": best_runway,
                    "runway_matrix": matrix,
                    "runways_evaluated": len(matrix),
                    "wind_direction": wind_dir,
                    "wind_speed": convert_speed(
                        wind_speed,
                        from_knots=True,
                        to_preference=self._unit_preference) if wind_speed is not None else None,
                    "wind_unit": get_speed_unit(
                        self._unit_preference),
                })

            if min_crosswind is not None:
                min_crosswind_unit = convert_speed(
                    min_crosswind,
                    from_knots=True,
                    to_preference=self._unit_preference,
                )
                attrs["min_crosswind"] = round(
                    min_crosswind_unit, 1) if min_crosswind_unit is not None else None

        return attrs


class AIBriefingSensor(HangarSensorBase):
    """Stores and displays the latest AI-generated pre-flight briefing.

    Receives briefing text from the AI briefing generation service and makes it available
    in Home Assistant. The briefing includes weather interpretation, runway recommendations,
    and safety considerations.

    Inputs:
        - Listens for 'hangar_assistant_ai_briefing' bus events
        - Event data includes: airfield_name, text (briefing content)

    Outputs:
        - native_value: \"Ready\" or \"Waiting\" status
        - extra_state_attributes[\"briefing\"]: Full briefing text
        - extra_state_attributes[\"last_updated\"]: Timestamp of last update

    Event Trigger:
        - Activated by: refresh_ai_briefings service or scheduled briefing time

    Used by:
        - Dashboard to display formatted briefing
        - Mobile app to push notifications
    """

    _attr_icon = "mdi:robot"

    def __init__(self, hass: HomeAssistant, config: dict,
                 global_settings: dict | None = None):
        super().__init__(hass, config, global_settings)
        self._briefing_text = "Waiting for first briefing..."
        self._last_update = None

    @property
    def name(self) -> str:
        return "AI Pre-flight Briefing"

    @property
    def native_value(self) -> str:
        if self._last_update:
            return "Ready"
        return "Waiting"

    @property
    def extra_state_attributes(self) -> dict:
        attrs = super().extra_state_attributes
        attrs["last_updated"] = self._last_update
        attrs["briefing"] = self._briefing_text
        return attrs

    async def async_added_to_hass(self) -> None:
        """Register for AI briefing events."""
        await super().async_added_to_hass()

        @callback
        def _handle_ai_update(event):
            """Update state when a new AI briefing is received."""
            if event.data.get("airfield_name") == self._config.get("name"):
                self.async_update_briefing(event.data.get("text"))

        self.async_on_remove(
            self.hass.bus.async_listen(
                "hangar_assistant_ai_briefing",
                _handle_ai_update))

    @callback
    def async_update_briefing(self, briefing_text: str):
        """Update the sensor state with new AI text."""
        self._briefing_text = briefing_text
        self._last_update = dt_util.now().isoformat()
        self.async_write_ha_state()


class AirfieldTimezoneSensor(HangarSensorBase):
    """Provide the local timezone identifier for an airfield.

    Calculates the IANA timezone string from configured latitude/longitude using
    timezonefinder, falling back to the Home Assistant configured timezone when
    coordinates are missing or a lookup fails.

    Inputs (from config):
        - latitude: Airfield latitude (float)
        - longitude: Airfield longitude (float)

    Outputs:
        - native_value: IANA timezone string (e.g., "Europe/London")
        - extra_state_attributes:
            - source: "airfield_coords", "home_assistant", or "utc_fallback"

    Used by:
        - Briefings and scheduling to align times to the local airfield timezone.
    """

    @property
    def name(self) -> str:
        return "Airfield Timezone"

    @property
    def native_value(self) -> str | None:
        """Return the best-available timezone string for this airfield.

        Priority:
            1. Coordinate-based lookup using TimezoneFinder (if available)
            2. Home Assistant configured timezone
            3. UTC as final fallback
        """
        lat = self._config.get("latitude")
        lon = self._config.get("longitude")

        # Check if TimezoneFinder is available and we have coordinates
        if _TZ_FINDER is None:
            _LOGGER.debug(
                "TimezoneFinder not available, using Home Assistant timezone")
        elif lat is not None and lon is not None:
            # Attempt coordinate-based lookup
            try:
                tz_name = _TZ_FINDER.timezone_at(
                    lat=float(lat), lng=float(lon))
                if tz_name:
                    self._tz_source = "airfield_coords"
                    return tz_name
                else:
                    _LOGGER.debug(
                        "No timezone found for coordinates %s/%s", lat, lon)
            except (ValueError, TypeError) as exc:
                _LOGGER.warning(
                    "Invalid coordinates for timezone lookup: lat=%s, lon=%s: %s",
                    lat,
                    lon,
                    exc)
            except Exception as exc:  # pragma: no cover - defensive guard
                _LOGGER.debug(
                    "Timezone lookup failed for %s/%s: %s", lat, lon, exc)
        else:
            _LOGGER.debug(
                "Coordinates not provided for airfield, using fallback timezone")

        # Fall back to Home Assistant configured timezone
        ha_tz = getattr(self.hass.config, "time_zone", None)
        if ha_tz:
            self._tz_source = "home_assistant"
            return ha_tz

        # Final fallback to UTC
        _LOGGER.info("No timezone available, using UTC fallback for airfield")
        self._tz_source = "utc_fallback"
        return "UTC"

    @property
    def extra_state_attributes(self) -> dict:
        attrs = super().extra_state_attributes
        attrs["source"] = getattr(self, "_tz_source", None)
        return attrs


class AirfieldWeatherPassThrough(HangarSensorBase):
    """Passes through individual weather sensor values for consistent dashboard display.

    Creates individual sensors for temperature, dew point, pressure, and wind data
    so they appear grouped under the airfield device with consistent naming.
    This improves dashboard organization and reduces clutter.

    Inputs (from config, via sensor_key):
        - temp_sensor: Temperature sensor entity ID
        - dp_sensor: Dew point sensor entity ID
        - pressure_sensor: Pressure sensor entity ID
        - wind_sensor: Wind speed sensor entity ID
        - wind_dir_sensor: Wind direction sensor entity ID

    Outputs:
        - native_value: Raw value from source sensor
        - Unit: Converted to standard unit (°C, hPa, knots, degrees)
        - Device class: Set for proper icon display

    Created instances: 5 per airfield (one for each weather parameter)
    """

    def __init__(
            self,
            hass: HomeAssistant,
            config: dict,
            sensor_key: str,
            label: str,
            device_class=None,
            unit=None,
            global_settings: dict | None = None):
        super().__init__(hass, config, global_settings)
        self._sensor_key = sensor_key
        self._label = label
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        # Ensure each weather pass-through gets a stable, non-colliding
        # unique_id
        self._attr_unique_id = f"{self._id_slug}_weather_{sensor_key}"
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
    """Determines the best runway to use based on current wind conditions.

    Evaluates all available runways and selects the one with minimum crosswind component.
    This helps pilots quickly identify the most favorable runway for takeoff or landing.

    Algorithm:
        1. Calculate crosswind for each runway using wind speed and direction
        2. Select runway with minimum crosswind
        3. Return runway identifier (e.g., \"21\")

    Inputs (from config):
        - runways: Comma-separated list of runway identifiers (e.g., \"03, 21\")
        - wind_sensor: Entity ID of wind speed sensor (knots)
        - wind_dir_sensor: Entity ID of wind direction sensor (degrees)

    Outputs:
        - native_value: Best runway identifier (e.g., \"21\")
        - extra_state_attributes[\"crosswind_component\"]: Crosswind for selected runway (kt)
        - extra_state_attributes[\"headwind_component\"]: Headwind for selected runway (kt)

    Used by:
        - Dashboard to display recommended runway
        - Pilot briefing for runway selection
    """

    def __init__(self, hass: HomeAssistant, config: dict,
                 global_settings: dict | None = None):
        super().__init__(hass, config, global_settings)
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
        min_diff = 360.0

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
        """Return crosswind and headwind components in user's preferred units."""
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
                crosswind_kt = abs(wind_speed * math.sin(angle_rad))
                headwind_kt = wind_speed * math.cos(angle_rad)

                # Convert to user's preferred unit
                crosswind_converted = convert_speed(
                    crosswind_kt, from_knots=True, to_preference=self._unit_preference)
                headwind_converted = convert_speed(
                    headwind_kt, from_knots=True, to_preference=self._unit_preference)

                attrs["crosswind_component"] = round(
                    crosswind_converted, 1) if crosswind_converted else None
                attrs["headwind_component"] = round(
                    headwind_converted, 1) if headwind_converted else None
                attrs["wind_unit"] = get_speed_unit(self._unit_preference)
            except ValueError:
                pass

        return attrs

# --- AIRCRAFT ENTITIES ---


class GroundRollSensor(HangarSensorBase):
    """Calculates adjusted takeoff distance based on density altitude conditions.

    Takes the published POH (Pilot's Operating Handbook) ground roll distance and adjusts
    it for current weather conditions. Higher density altitude increases required distance.

    Formula: Adjusted GR = POH GR * (1 + (DA / 1000) * 0.10)
    Where: 10% performance loss per 1000 ft of density altitude above sea level

    Inputs (from config):
        - baseline_roll: POH ground roll at sea level in meters
        - linked_airfield: Name of airfield to get density altitude

    Outputs:
        - native_value: Adjusted ground roll distance in meters
        - Falls back to 1.15x baseline if DA not available

    Used by:
        - Pilot to assess runway suitability (compare to available distance)
        - Dashboard to display go/no-go decision support

    Example: Baseline 500m, DA 5000ft => Adjusted = 500 * 1.50 = 750m
    """

    def __init__(self, hass: HomeAssistant, config: dict,
                 global_settings: dict | None = None):
        super().__init__(hass, config, global_settings)
        self._da_sensor_id: str | None = None
        if airfield_name := config.get("linked_airfield"):
            # Predict the DA sensor ID for the linked airfield
            slug = airfield_name.lower().replace(" ", "_")
            self._da_sensor_id = f"sensor.{slug}_density_altitude"
            self._source_entities = [self._da_sensor_id]
        # Set unit based on preference
        self._attr_native_unit_of_measurement = get_altitude_unit(
            self._unit_preference)

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Calculated Ground Roll"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor in meters or user's preferred unit."""
        base_m = self._config.get("baseline_roll", 0)

        if self._da_sensor_id:
            da = self._get_sensor_value(self._da_sensor_id)
            if da is not None:
                # Rule of thumb: 10% increase per 1000ft DA above sea level
                # We cap DA at 0 for this simple calculation
                # Note: DA is in user's preferred unit, need to normalize to
                # feet for calculation
                da_ft_converted = convert_altitude(
                    da,
                    from_feet=False,
                    to_preference="aviation") if self._unit_preference == "si" else da
                da_ft = da_ft_converted if da_ft_converted is not None else 0
                factor = 1 + (max(0, da_ft) / 1000) * 0.10
                adjusted_m = base_m * factor
                # Convert result to user's preferred unit
                adjusted_converted = convert_altitude(
                    adjusted_m, from_feet=False, to_preference=self._unit_preference)
                return round(
                    adjusted_converted) if adjusted_converted is not None else None

        # Fallback to a static safety factor if no DA is available
        adjusted_m = base_m * 1.15
        adjusted_converted = convert_altitude(
            adjusted_m, from_feet=False, to_preference=self._unit_preference)
        return round(
            adjusted_converted) if adjusted_converted is not None else None


class PerformanceMarginSensor(HangarSensorBase):
    """Calculates runway performance margin for the linked airfield.

    Uses the aircraft's adjusted ground roll (based on density altitude) and compares it
    to the available runway length to express remaining margin as a percentage. Defaults
    to conservative assumptions and safe fallbacks to preserve existing behavior when
    optional inputs are missing.

    Inputs (from config):
        - baseline_roll: POH ground roll at sea level in meters
        - linked_airfield: Name of the airfield to derive runway length and DA sensor
        - airfield.runway_length: Available runway length in meters (applied to all listed runways)
        - airfield.name: Used to locate DA sensor and best runway sibling sensor

    Outputs:
        - native_value: Margin percentage ((runway - required) / runway * 100)
        - Attributes: required_distance, available_runway, recommended_runway, DA used

    Used by:
        - Dashboard runway suitability panels
        - Pre-taxi go/no-go nudges for instructors and pilots
    """

    _attr_native_unit_of_measurement = "%"

    def __init__(
        self,
        hass: HomeAssistant,
        aircraft_config: dict,
        airfield_config: dict | None,
        global_settings: dict | None = None,
    ):
        super().__init__(hass, aircraft_config, global_settings)
        self._airfield = airfield_config or {}
        self._airfield_name = self._airfield.get(
            "name") or self._config.get("linked_airfield")
        self._runway_length_m = self._airfield.get("runway_length", 0) or 0

        self._da_sensor_id: str | None = None
        self._best_runway_id: str | None = None
        if self._airfield_name:
            slug = self._airfield_name.lower().replace(" ", "_")
            self._da_sensor_id = f"sensor.{slug}_density_altitude"
            self._best_runway_id = f"sensor.{slug}_best_runway"

        sources = []
        if self._da_sensor_id:
            sources.append(self._da_sensor_id)
        if self._best_runway_id:
            sources.append(self._best_runway_id)
        self._source_entities = sources

    @property
    def name(self) -> str:
        return "Runway Performance Margin"

    def _get_da_feet(self) -> float:
        if not self._da_sensor_id:
            return 0.0
        da_val = self._get_sensor_value(self._da_sensor_id)
        if da_val is None:
            return 0.0
        if self._unit_preference == "si":
            da_ft = convert_altitude(
                da_val, from_feet=False, to_preference="aviation")
            return float(da_ft) if da_ft is not None else 0.0
        return float(da_val)

    def _compute_required_distance_m(self) -> float:
        base_m = float(self._config.get("baseline_roll", 0) or 0)
        if base_m <= 0:
            return 0.0

        da_ft = self._get_da_feet()
        if da_ft <= 0:
            # Conservative fallback if DA missing: +15%
            return base_m * 1.15

        factor = 1 + (da_ft / 1000) * 0.10
        return base_m * factor

    def _recommended_runway(self) -> str | None:
        if not self._best_runway_id:
            return None
        state = self.hass.states.get(self._best_runway_id)
        if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return str(state.state)
        return None

    @property
    def native_value(self) -> float | None:
        if self._runway_length_m <= 0:
            return None

        required_m = self._compute_required_distance_m()
        if required_m <= 0:
            return None

        margin_pct = ((self._runway_length_m - required_m) /
                      self._runway_length_m) * 100
        return round(margin_pct, 1)

    @property
    def extra_state_attributes(self) -> dict:
        attrs = super().extra_state_attributes
        attrs.update(
            {
                "runway_length_m": self._runway_length_m,
                "runway_length_unit": get_altitude_unit(self._unit_preference),
                "airfield": self._airfield_name,
                "recommended_runway": self._recommended_runway(),
            }
        )

        required_m = self._compute_required_distance_m()
        required_unit = convert_altitude(
            required_m,
            from_feet=False,
            to_preference=self._unit_preference)
        attrs["required_distance"] = round(
            required_unit, 1) if required_unit is not None else None
        attrs["required_distance_unit"] = get_altitude_unit(
            self._unit_preference)
        attrs["density_altitude_ft"] = round(self._get_da_feet(), 1)

        return attrs


class PilotInfoSensor(HangarSensorBase):
    """Displays pilot qualification and license information.

    Stores and displays pilot credentials for compliance and safety tracking.
    Integrates with medical alert system to flag expired medical certificates.

    Inputs (from config):
        - name: Pilot name
        - licence_type: License category (e.g., \"Commercial\", \"Private\")
        - licence_number: License certificate number
        - email: Pilot contact email
        - medical_expiry: Medical certificate expiration date

    Outputs:
        - native_value: License type (e.g., "Commercial")
        - extra_state_attributes: Full pilot record including:
            - pilot_name
            - email
            - licence_number
            - medical_expiry (used by PilotMedicalAlert)
            - ratings: dict of boolean flags (IFR, Night, Tailwheel, Complex, High-Performance, Multi-Engine, Seaplane, Glider, Aerobatic, Mountain) defaulting to False unless explicitly set

    Used by:
        - Compliance logging
        - Medical alert system for expiry notifications
        - Dashboard crew display
    """

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Pilot Qualifications"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return self._config.get("licence_type")

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        ratings = {
            "ifr_rating": bool(self._config.get("ifr_rating", False)),
            "night_rating": bool(self._config.get("night_rating", False)),
            "tailwheel_rating": bool(self._config.get("tailwheel_rating", False)),
            "complex_rating": bool(self._config.get("complex_rating", False)),
            "high_performance_rating": bool(self._config.get("high_performance_rating", False)),
            "multi_engine_rating": bool(self._config.get("multi_engine_rating", False)),
            "seaplane_rating": bool(self._config.get("seaplane_rating", False)),
            "glider_rating": bool(self._config.get("glider_rating", False)),
            "aerobatic_rating": bool(self._config.get("aerobatic_rating", False)),
            "mountain_rating": bool(self._config.get("mountain_rating", False)),
        }

        return {
            "pilot_name": self._config.get("name"),
            "email": self._config.get("email"),
            "licence_number": self._config.get("licence_number"),
            "medical_expiry": self._config.get("medical_expiry"),
            "ratings": ratings,
        }


class AirfieldNOTAMSensor(HangarSensorBase):
    """Displays active NOTAMs (Notices to Airmen) for an airfield.

    Fetches and filters NOTAMs relevant to the airfield's location. Shows count of active
    NOTAMs as the sensor state, with full NOTAM details in attributes for dashboard display
    and AI briefing integration.

    Data is provided by the NOTAMClient, which fetches daily from UK NATS PIB XML feed.
    Gracefully handles stale data by showing last known NOTAMs with staleness warning.

    Inputs (from config):
        - icao_code: Airfield ICAO identifier (e.g., "EGKA")
        - latitude: Airfield latitude for proximity filtering
        - longitude: Airfield longitude for proximity filtering
        - name: Airfield name for display

    Outputs:
        - native_value: Count of active NOTAMs within 50nm radius
        - extra_state_attributes:
            - notams: Full list of NOTAM dicts (id, location, category, text, start, end, q_code)
            - airfield_notams: NOTAMs specific to this airfield's ICAO code
            - area_notams: NOTAMs within 50nm proximity
            - last_update: Timestamp of last successful NOTAM fetch
            - is_stale: Boolean indicating if cache is expired
            - cache_age_hours: Hours since last fetch

    Used by:
        - AI briefing system for NOTAM integration
        - Dashboard NOTAM display cards
        - Compliance logging for flight preparation
    """

    _attr_should_poll = True  # Enable polling for async updates

    def __init__(
            self,
            hass: HomeAssistant,
            config: dict,
            global_settings: dict,
            entry: ConfigEntry):
        """Initialize the NOTAM sensor.

        Args:
            hass: Home Assistant instance
            config: Airfield configuration dict
            global_settings: Global settings
            entry: ConfigEntry for accessing NOTAM client
        """
        super().__init__(hass, config, global_settings)
        self._entry = entry
        self._attr_icon = "mdi:alert-circle-outline"

        # Extract airfield coordinates for proximity filtering
        self._icao = config.get("icao_code")
        self._latitude = config.get("latitude")
        self._longitude = config.get("longitude")

        # Store last fetched NOTAMs
        self._notams: list[dict] = []
        self._is_stale = True
        self._last_update_time: datetime | None = None
        self._cache_stats: dict = {}

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "NOTAMs"

    @property
    def native_value(self) -> int:
        """Return the count of active NOTAMs."""
        return len(self._notams)

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes including full NOTAM details."""
        attrs = super().extra_state_attributes

        # Separate NOTAMs by relevance
        airfield_notams = [n for n in self._notams if n.get(
            "location") == self._icao] if self._icao else []
        area_notams = [n for n in self._notams if n not in airfield_notams]

        # Get last update from config
        integrations = self._entry.data.get("integrations", {})
        notam_config = integrations.get("notams", {})

        attrs.update(
            {
                "notams": self._notams,
                "airfield_notams": airfield_notams,
                "area_notams": area_notams,
                "last_update": notam_config.get("last_update"),
                "is_stale": self._is_stale,
                "cache_age_hours": self._cache_stats.get(
                    "age_hours",
                    0) if self._cache_stats.get("exists") else None,
                "consecutive_failures": notam_config.get(
                    "consecutive_failures",
                    0),
            })

        return attrs

    async def async_update(self) -> None:
        """Fetch NOTAMs for this airfield."""
        integrations = self._entry.data.get("integrations", {})
        notam_config = integrations.get("notams", {})
        cache_days = notam_config.get("cache_days", 7)

        notam_client = NOTAMClient(self.hass, cache_days, self._entry)

        try:
            # Fetch all NOTAMs (client handles its own caching)
            all_notams, is_stale = await notam_client.fetch_notams()

            # Filter for this airfield's location
            filtered_notams = notam_client.filter_by_location(
                all_notams,
                self._icao,
                self._latitude,
                self._longitude,
                radius_nm=50
            )

            # Update state
            self._notams = filtered_notams
            self._is_stale = is_stale
            self._last_update_time = dt_util.utcnow()
            self._cache_stats = notam_client.get_cache_stats()

        except Exception as e:
            _LOGGER.error(
                "Failed to fetch NOTAMs for %s: %s",
                self._config.get("name"),
                e)
            # Keep existing cached data


class FuelBurnRateSensor(HangarSensorBase):
    """Fuel burn rate sensor for aircraft.
    
    Displays the aircraft's fuel consumption rate in user's preferred units
    (liters/hour or gallons/hour). Only created if burn_rate > 0 in config.
    
    Inputs (from aircraft config):
        - fuel.burn_rate: Burn rate value
        - fuel.burn_rate_unit: Unit (liters, gallons, gallons_imperial)
        - fuel.type: Fuel type (AVGAS, MOGAS, etc.)
    
    Outputs:
        - native_value: Burn rate in user's preferred units
        - Attributes: burn_rate_liters_per_hour, burn_rate_gallons_per_hour,
                     fuel_type, tank_capacity
    
    Used by:
        - Dashboard fuel status cards
        - Trip fuel calculations
        - Cost estimations
    """
    
    _attr_icon = "mdi:fuel"
    
    def __init__(self, hass: HomeAssistant, config: dict, global_settings: dict | None = None):
        super().__init__(hass, config, global_settings)
        from .utils.units import get_fuel_burn_rate_unit
        self._attr_native_unit_of_measurement = get_fuel_burn_rate_unit(self._unit_preference)
    
    @property
    def name(self) -> str:
        return f"{self._config.get('reg', 'Aircraft')} Fuel Burn Rate"
    
    @property
    def native_value(self) -> float | None:
        """Return fuel burn rate in user's preferred units."""
        from .utils.units import convert_fuel_volume
        
        fuel_config = self._config.get("fuel", {})
        burn_rate = fuel_config.get("burn_rate", 0.0)
        burn_rate_unit = fuel_config.get("burn_rate_unit", "liters")
        
        if burn_rate <= 0:
            return None
        
        # Convert to user's preferred unit
        if self._unit_preference == "aviation":
            # Convert to gallons/hour
            return convert_fuel_volume(burn_rate, from_unit=burn_rate_unit, to_unit="gallons")
        else:
            # Convert to liters/hour
            return convert_fuel_volume(burn_rate, from_unit=burn_rate_unit, to_unit="liters")
    
    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        from .utils.units import convert_fuel_volume
        
        attrs = super().extra_state_attributes
        fuel_config = self._config.get("fuel", {})
        burn_rate = fuel_config.get("burn_rate", 0.0)
        burn_rate_unit = fuel_config.get("burn_rate_unit", "liters")
        tank_capacity = fuel_config.get("tank_capacity", 0.0)
        tank_capacity_unit = fuel_config.get("tank_capacity_unit", "liters")
        
        # Convert burn rate to both units for reference
        burn_rate_liters = convert_fuel_volume(burn_rate, from_unit=burn_rate_unit, to_unit="liters")
        burn_rate_gallons = convert_fuel_volume(burn_rate, from_unit=burn_rate_unit, to_unit="gallons")
        
        # Convert tank capacity to both units
        capacity_liters = convert_fuel_volume(tank_capacity, from_unit=tank_capacity_unit, to_unit="liters")
        capacity_gallons = convert_fuel_volume(tank_capacity, from_unit=tank_capacity_unit, to_unit="gallons")
        
        attrs.update({
            "fuel_type": fuel_config.get("type", "AVGAS"),
            "burn_rate_liters_per_hour": round(burn_rate_liters, 2) if burn_rate_liters else 0,
            "burn_rate_gallons_per_hour": round(burn_rate_gallons, 2) if burn_rate_gallons else 0,
            "tank_capacity_liters": round(capacity_liters, 2) if capacity_liters else 0,
            "tank_capacity_gallons": round(capacity_gallons, 2) if capacity_gallons else 0,
        })
        
        return attrs


class FuelEnduranceSensor(HangarSensorBase):
    """Fuel endurance sensor for aircraft.
    
    Calculates flight time available on full tanks, accounting for reserve fuel.
    Only created if burn_rate > 0 in config.
    
    Inputs (from aircraft config):
        - fuel.tank_capacity: Total usable fuel
        - fuel.burn_rate: Fuel consumption rate
        - fuel.tank_capacity_unit: Unit of capacity
        - fuel.burn_rate_unit: Unit of burn rate
    
    Outputs:
        - native_value: Endurance in hours (excluding reserve)
        - Attributes: endurance_with_reserve, total_endurance, reserve_minutes
    
    Used by:
        - Dashboard fuel cards
        - Trip planning calculations
    """
    
    _attr_icon = "mdi:clock-outline"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "h"
    
    def __init__(self, hass: HomeAssistant, config: dict, global_settings: dict | None = None):
        super().__init__(hass, config, global_settings)
    
    @property
    def name(self) -> str:
        return f"{self._config.get('reg', 'Aircraft')} Fuel Endurance"
    
    @property
    def native_value(self) -> float | None:
        """Return fuel endurance in hours."""
        from .utils.units import calculate_fuel_endurance
        from .const import DEFAULT_FUEL_RESERVE_MINUTES
        
        fuel_config = self._config.get("fuel", {})
        tank_capacity = fuel_config.get("tank_capacity", 0.0)
        burn_rate = fuel_config.get("burn_rate", 0.0)
        volume_unit = fuel_config.get("tank_capacity_unit", "liters")
        
        if burn_rate <= 0 or tank_capacity <= 0:
            return None
        
        # Get reserve from global settings
        settings = self._global_settings or {}
        fuel_settings = settings.get("fuel", {})
        reserve_minutes = fuel_settings.get("reserve_minutes", DEFAULT_FUEL_RESERVE_MINUTES)
        
        endurance = calculate_fuel_endurance(
            tank_capacity,
            burn_rate,
            volume_unit,
            reserve_minutes
        )
        
        return round(endurance, 2) if endurance else None
    
    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        from .utils.units import calculate_fuel_endurance
        from .const import DEFAULT_FUEL_RESERVE_MINUTES
        
        attrs = super().extra_state_attributes
        fuel_config = self._config.get("fuel", {})
        tank_capacity = fuel_config.get("tank_capacity", 0.0)
        burn_rate = fuel_config.get("burn_rate", 0.0)
        volume_unit = fuel_config.get("tank_capacity_unit", "liters")
        
        # Get reserve from global settings
        settings = self._global_settings or {}
        fuel_settings = settings.get("fuel", {})
        reserve_minutes = fuel_settings.get("reserve_minutes", DEFAULT_FUEL_RESERVE_MINUTES)
        
        # Calculate endurance with and without reserve
        total_endurance = calculate_fuel_endurance(tank_capacity, burn_rate, volume_unit, reserve_minutes=0)
        usable_endurance = calculate_fuel_endurance(tank_capacity, burn_rate, volume_unit, reserve_minutes)
        
        attrs.update({
            "total_endurance_hours": round(total_endurance, 2) if total_endurance else 0,
            "usable_endurance_hours": round(usable_endurance, 2) if usable_endurance else 0,
            "reserve_minutes": reserve_minutes,
        })
        
        return attrs


class FuelWeightSensor(HangarSensorBase):
    """Fuel weight sensor for aircraft.
    
    Calculates weight of full fuel load based on fuel type density.
    Used for weight & balance calculations.
    
    Inputs (from aircraft config):
        - fuel.tank_capacity: Total usable fuel
        - fuel.type: Fuel type (determines density)
        - fuel.tank_capacity_unit: Unit of capacity
    
    Outputs:
        - native_value: Fuel weight in user's preferred units (kg or lbs)
        - Attributes: weight_kg, weight_lbs, volume_liters, fuel_type, density
    
    Used by:
        - Weight & balance calculations
        - Performance adjustments
        - Dashboard weight displays
    """
    
    _attr_icon = "mdi:weight"
    _attr_device_class = SensorDeviceClass.WEIGHT
    
    def __init__(self, hass: HomeAssistant, config: dict, global_settings: dict | None = None):
        super().__init__(hass, config, global_settings)
        from .utils.units import get_weight_unit
        self._attr_native_unit_of_measurement = get_weight_unit(self._unit_preference)
    
    @property
    def name(self) -> str:
        return f"{self._config.get('reg', 'Aircraft')} Fuel Weight"
    
    @property
    def native_value(self) -> float | None:
        """Return fuel weight in user's preferred units."""
        from .utils.units import calculate_fuel_weight, convert_weight
        
        fuel_config = self._config.get("fuel", {})
        tank_capacity = fuel_config.get("tank_capacity", 0.0)
        tank_capacity_unit = fuel_config.get("tank_capacity_unit", "liters")
        fuel_type = fuel_config.get("type", "AVGAS")
        
        if tank_capacity <= 0:
            return None
        
        # Calculate weight in kg
        weight_kg = calculate_fuel_weight(tank_capacity, fuel_type, tank_capacity_unit)
        
        # Convert to user's preferred unit
        weight = convert_weight(weight_kg, from_pounds=False, to_preference=self._unit_preference)
        
        return round(weight, 2) if weight else None
    
    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        from .utils.units import calculate_fuel_weight, convert_weight, convert_fuel_volume
        from .const import FUEL_DENSITY
        
        attrs = super().extra_state_attributes
        fuel_config = self._config.get("fuel", {})
        tank_capacity = fuel_config.get("tank_capacity", 0.0)
        tank_capacity_unit = fuel_config.get("tank_capacity_unit", "liters")
        fuel_type = fuel_config.get("type", "AVGAS")
        
        # Calculate weight in kg
        weight_kg = calculate_fuel_weight(tank_capacity, fuel_type, tank_capacity_unit)
        weight_lbs = convert_weight(weight_kg, from_pounds=False, to_preference="aviation")
        
        # Convert volume to liters for reference
        volume_liters = convert_fuel_volume(tank_capacity, from_unit=tank_capacity_unit, to_unit="liters")
        
        # Get density
        density_data = FUEL_DENSITY.get(fuel_type, {})
        
        attrs.update({
            "fuel_type": fuel_type,
            "volume_liters": round(volume_liters, 2) if volume_liters else 0,
            "weight_kg": round(weight_kg, 2) if weight_kg else 0,
            "weight_lbs": round(weight_lbs, 2) if weight_lbs else 0,
            "density_kg_per_liter": density_data.get("kg_per_liter", 0),
        })
        
        return attrs
class MetarSensor(HangarSensorBase):
    """Sensor for CheckWX METAR (current weather observations).
    
    Displays current aviation weather in METAR format with decoded data.
    State shows flight category (VFR/MVFR/IFR/LIFR), attributes contain
    all weather parameters.
    
    Inputs:
        - airfield: Airfield config with ICAO code
        - global_settings: CheckWX API configuration
    
    Outputs:
        - State: Flight category (VFR, MVFR, IFR, LIFR)
        - Attributes: temperature, dewpoint, wind, visibility, clouds, barometer
    
    Used by:
        - AI briefing generation
        - Dashboard weather displays
        - Flight planning calculations
    
    Update Interval:
        - 30 minutes default (configurable per CheckWX config)
        - Uses cached data if API unavailable
    """
    
    _attr_icon = "mdi:weather-partly-cloudy"
    
    def __init__(self, hass: HomeAssistant, config: dict, global_settings: dict | None = None):
        super().__init__(hass, config, global_settings)
        self._metar_data = None
        self._last_update = None
        
        # Get CheckWX configuration
        self._integrations = global_settings.get("integrations", {}) if global_settings else {}
        self._checkwx_config = self._integrations.get("checkwx", {})
        self._update_interval_minutes = self._checkwx_config.get("metar_cache_minutes", 30)
        
        # Initialize CheckWX client
        self._client = None
        if self._checkwx_config.get("enabled") and self._checkwx_config.get("api_key"):
            from .utils.checkwx_client import CheckWXClient
            self._client = CheckWXClient(
                api_key=self._checkwx_config["api_key"],
                hass=hass,
                cache_enabled=True,
                metar_cache_minutes=self._checkwx_config.get("metar_cache_minutes", 15)
            )
    
    @property
    def name(self) -> str:
        return f"{self._config.get('name', 'Airfield')} METAR"
    
    @property
    def native_value(self) -> str | None:
        """Return flight category as state."""
        if self._metar_data:
            return self._metar_data.get("flight_category", "UNKNOWN")
        return None
    
    @property
    def extra_state_attributes(self) -> dict:
        """Return METAR data as attributes."""
        attrs = super().extra_state_attributes
        
        if self._metar_data:
            # Temperature
            temp_data = self._metar_data.get("temperature", {})
            attrs["temperature_celsius"] = temp_data.get("celsius")
            attrs["temperature_fahrenheit"] = temp_data.get("fahrenheit")
            
            # Dewpoint
            dp_data = self._metar_data.get("dewpoint", {})
            attrs["dewpoint_celsius"] = dp_data.get("celsius")
            attrs["dewpoint_fahrenheit"] = dp_data.get("fahrenheit")
            
            # Wind
            wind_data = self._metar_data.get("wind", {})
            attrs["wind_degrees"] = wind_data.get("degrees")
            attrs["wind_speed_kts"] = wind_data.get("speed_kts")
            attrs["wind_speed_kph"] = wind_data.get("speed_kph")
            attrs["wind_gust_kts"] = wind_data.get("gust_kts")
            
            # Barometer
            baro_data = self._metar_data.get("barometer", {})
            attrs["barometer_hpa"] = baro_data.get("hpa")
            attrs["barometer_inhg"] = baro_data.get("hg")
            
            # Visibility
            vis_data = self._metar_data.get("visibility", {})
            attrs["visibility_miles"] = vis_data.get("miles")
            attrs["visibility_meters"] = vis_data.get("meters")
            
            # Clouds
            clouds = self._metar_data.get("clouds", [])
            attrs["clouds"] = clouds
            attrs["cloud_layers"] = len(clouds)
            
            # Ceiling
            ceiling_data = self._metar_data.get("ceiling", {})
            attrs["ceiling_feet"] = ceiling_data.get("feet")
            attrs["ceiling_meters"] = ceiling_data.get("meters")
            
            # Humidity
            humidity_data = self._metar_data.get("humidity", {})
            attrs["humidity_percent"] = humidity_data.get("percent")
            
            # Observation time
            attrs["observed"] = self._metar_data.get("observed")
            
            # Raw METAR text
            attrs["raw_metar"] = self._metar_data.get("raw_text")
            
            # ICAO
            attrs["icao"] = self._metar_data.get("icao")
            
            # Last update timestamp
            attrs["last_update"] = self._last_update.isoformat() if self._last_update else None
        
        attrs["update_interval_minutes"] = self._update_interval_minutes
        
        return attrs
    
    async def async_update(self) -> None:
        """Fetch latest METAR data from CheckWX."""
        if not self._client:
            _LOGGER.debug("CheckWX client not configured for METAR sensor")
            return
        
        icao = self._config.get("icao")
        if not icao or len(icao) != 4:
            _LOGGER.warning("Invalid ICAO code for METAR sensor: %s", icao)
            return
        
        try:
            # Fetch METAR (uses cache if within TTL)
            metar_data = await self._client.get_metar(icao, decoded=True)
            
            if metar_data:
                self._metar_data = metar_data
                self._last_update = dt_util.utcnow()
                _LOGGER.debug("METAR updated for %s: %s", icao, metar_data.get("flight_category"))
            else:
                _LOGGER.warning("No METAR data returned for %s", icao)
        
        except Exception as e:
            _LOGGER.error("Error fetching METAR for %s: %s", icao, e)


# ==============================================================================
# CheckWX TAF Sensor
# ==============================================================================

class TafSensor(HangarSensorBase):
    """Sensor for CheckWX TAF (Terminal Aerodrome Forecast).
    
    Displays aviation weather forecast in TAF format with decoded periods.
    State shows validity period, attributes contain forecast periods with
    change indicators (FM, BECMG, TEMPO, PROB).
    
    Inputs:
        - airfield: Airfield config with ICAO code
        - global_settings: CheckWX API configuration
    
    Outputs:
        - State: Validity period (e.g., "Valid 22/12:00Z to 23/12:00Z")
        - Attributes: issued time, forecast periods array, raw TAF text
    
    Used by:
        - AI briefing generation
        - Flight planning (future conditions)
        - Dashboard forecast displays
    
    Update Interval:
        - 6 hours default (TAFs issued every 6 hours)
        - Uses cached data if API unavailable
    """
    
    _attr_icon = "mdi:weather-partly-rainy"
    
    def __init__(self, hass: HomeAssistant, config: dict, global_settings: dict | None = None):
        super().__init__(hass, config, global_settings)
        self._taf_data = None
        self._last_update = None
        
        # Get CheckWX configuration
        self._integrations = global_settings.get("integrations", {}) if global_settings else {}
        self._checkwx_config = self._integrations.get("checkwx", {})
        self._update_interval_minutes = self._checkwx_config.get("taf_cache_minutes", 360)
        
        # Initialize CheckWX client
        self._client = None
        if self._checkwx_config.get("enabled") and self._checkwx_config.get("api_key"):
            from .utils.checkwx_client import CheckWXClient
            self._client = CheckWXClient(
                api_key=self._checkwx_config["api_key"],
                hass=hass,
                cache_enabled=True,
                taf_cache_minutes=self._checkwx_config.get("taf_cache_minutes", 360)
            )
    
    @property
    def name(self) -> str:
        return f"{self._config.get('name', 'Airfield')} TAF"
    
    @property
    def native_value(self) -> str | None:
        """Return validity period as state."""
        if self._taf_data:
            timestamp = self._taf_data.get("timestamp", {})
            from_time = timestamp.get("from", "")
            to_time = timestamp.get("to", "")
            
            if from_time and to_time:
                # Format: "Valid 22/12:00Z to 23/12:00Z"
                from_dt = datetime.fromisoformat(from_time.replace("Z", "+00:00"))
                to_dt = datetime.fromisoformat(to_time.replace("Z", "+00:00"))
                
                return f"Valid {from_dt.strftime('%d/%H:%M')}Z to {to_dt.strftime('%d/%H:%M')}Z"
        
        return None
    
    @property
    def extra_state_attributes(self) -> dict:
        """Return TAF data as attributes."""
        attrs = super().extra_state_attributes
        
        if self._taf_data:
            # Timestamp info
            timestamp = self._taf_data.get("timestamp", {})
            attrs["issued"] = timestamp.get("issued")
            attrs["valid_from"] = timestamp.get("from")
            attrs["valid_to"] = timestamp.get("to")
            
            # Forecast periods
            forecast = self._taf_data.get("forecast", [])
            attrs["forecast_periods"] = forecast
            attrs["period_count"] = len(forecast)
            
            # Raw TAF text
            attrs["raw_taf"] = self._taf_data.get("raw_text")
            
            # ICAO
            attrs["icao"] = self._taf_data.get("icao")
            
            # Last update timestamp
            attrs["last_update"] = self._last_update.isoformat() if self._last_update else None
        
        attrs["update_interval_minutes"] = self._update_interval_minutes
        
        return attrs
    
    async def async_update(self) -> None:
        """Fetch latest TAF data from CheckWX."""
        if not self._client:
            _LOGGER.debug("CheckWX client not configured for TAF sensor")
            return
        
        icao = self._config.get("icao")
        if not icao or len(icao) != 4:
            _LOGGER.warning("Invalid ICAO code for TAF sensor: %s", icao)
            return
        
        try:
            # Fetch TAF (uses cache if within TTL)
            taf_data = await self._client.get_taf(icao, decoded=True)
            
            if taf_data:
                self._taf_data = taf_data
                self._last_update = dt_util.utcnow()
                _LOGGER.debug("TAF updated for %s", icao)
            else:
                _LOGGER.warning("No TAF data returned for %s", icao)
        
        except Exception as e:
            _LOGGER.error("Error fetching TAF for %s: %s", icao, e)


# ==============================================================================
# CheckWX Station Info Sensor
# ==============================================================================

class StationInfoSensor(HangarSensorBase):
    """Sensor for CheckWX station/airport information.
    
    Displays airport station data including name, location, elevation, and
    sunrise/sunset times. State shows airport name, attributes contain all
    geographic and time data.
    
    Inputs:
        - airfield: Airfield config with ICAO code
        - global_settings: CheckWX API configuration
    
    Outputs:
        - State: Airport name (e.g., "John F Kennedy International Airport")
        - Attributes: elevation, coordinates, sunrise/sunset, timezone
    
    Used by:
        - Auto-population service (pre-fill airfield data)
        - Dashboard location displays
        - Timezone calculations
    
    Update Interval:
        - 7 days (station info changes rarely)
        - Heavily cached to preserve API rate limit
    """
    
    _attr_icon = "mdi:airport"
    
    def __init__(self, hass: HomeAssistant, config: dict, global_settings: dict | None = None):
        super().__init__(hass, config, global_settings)
        self._station_data = None
        self._suntimes_data = None
        self._last_update = None
        
        # Get CheckWX configuration
        self._integrations = global_settings.get("integrations", {}) if global_settings else {}
        self._checkwx_config = self._integrations.get("checkwx", {})
        
        # Initialize CheckWX client
        self._client = None
        if self._checkwx_config.get("enabled") and self._checkwx_config.get("api_key"):
            from .utils.checkwx_client import CheckWXClient
            self._client = CheckWXClient(
                api_key=self._checkwx_config["api_key"],
                hass=hass,
                cache_enabled=True,
                station_cache_minutes=10080  # 7 days
            )
    
    @property
    def name(self) -> str:
        return f"{self._config.get('name', 'Airfield')} Station Info"
    
    @property
    def native_value(self) -> str | None:
        """Return airport name as state."""
        if self._station_data:
            return self._station_data.get("name", "Unknown Airport")
        return None
    
    @property
    def extra_state_attributes(self) -> dict:
        """Return station information as attributes."""
        attrs = super().extra_state_attributes
        
        if self._station_data:
            # Basic info
            attrs["icao"] = self._station_data.get("icao")
            attrs["iata"] = self._station_data.get("iata")
            attrs["airport_name"] = self._station_data.get("name")
            attrs["city"] = self._station_data.get("city")
            attrs["airport_type"] = self._station_data.get("type")
            
            # Country
            country = self._station_data.get("country", {})
            attrs["country_code"] = country.get("code")
            attrs["country_name"] = country.get("name")
            
            # Elevation
            elevation = self._station_data.get("elevation", {})
            attrs["elevation_feet"] = elevation.get("feet")
            attrs["elevation_meters"] = elevation.get("meters")
            
            # Coordinates
            latitude = self._station_data.get("latitude", {})
            longitude = self._station_data.get("longitude", {})
            attrs["latitude"] = latitude.get("decimal")
            attrs["longitude"] = longitude.get("decimal")
            
            # Geometry (for mapping)
            geometry = self._station_data.get("geometry", {})
            attrs["geometry_type"] = geometry.get("type")
            attrs["coordinates"] = geometry.get("coordinates")
        
        # Sunrise/sunset times
        if self._suntimes_data:
            local_times = self._suntimes_data.get("local", {})
            attrs["sunrise_local"] = local_times.get("sunrise")
            attrs["sunset_local"] = local_times.get("sunset")
            attrs["dawn_local"] = local_times.get("dawn")
            attrs["dusk_local"] = local_times.get("dusk")
            
            utc_times = self._suntimes_data.get("utc", {})
            attrs["sunrise_utc"] = utc_times.get("sunrise")
            attrs["sunset_utc"] = utc_times.get("sunset")
            
            timezone = self._suntimes_data.get("timezone", {})
            attrs["timezone_id"] = timezone.get("tzid")
        
        # Last update timestamp
        attrs["last_update"] = self._last_update.isoformat() if self._last_update else None
        
        return attrs
    
    async def async_update(self) -> None:
        """Fetch station info and sunrise/sunset from CheckWX."""
        if not self._client:
            _LOGGER.debug("CheckWX client not configured for station info sensor")
            return
        
        icao = self._config.get("icao")
        if not icao or len(icao) != 4:
            _LOGGER.warning("Invalid ICAO code for station info sensor: %s", icao)
            return
        
        try:
            # Fetch station info (heavily cached - 7 days)
            station_data = await self._client.get_station_info(icao)
            
            if station_data:
                self._station_data = station_data
                _LOGGER.debug("Station info updated for %s", icao)
            else:
                _LOGGER.warning("No station data returned for %s", icao)
            
            # Fetch sunrise/sunset times (cached 12 hours)
            suntimes_data = await self._client.get_sunrise_sunset(icao)
            
            if suntimes_data:
                self._suntimes_data = suntimes_data
                _LOGGER.debug("Sunrise/sunset updated for %s", icao)
            
            self._last_update = dt_util.utcnow()
        
        except Exception as e:
            _LOGGER.error("Error fetching station info for %s: %s", icao, e)


# ==============================================================================
# Registration in async_setup_entry()
# ==============================================================================

# Add to airfield loop in async_setup_entry():
"""
    # Check if CheckWX integration is enabled
    checkwx_config = integrations.get("checkwx", {})
    checkwx_enabled = checkwx_config.get("enabled", False)
    
    for airfield in airfields:
        # ... existing sensors ...
        
        # Add CheckWX sensors if integration is enabled and airfield has ICAO
        if checkwx_enabled and airfield.get("icao"):
            if checkwx_config.get("metar_enabled", True):
                entities.append(MetarSensor(hass, airfield, global_settings))
            
            if checkwx_config.get("taf_enabled", True):
                entities.append(TafSensor(hass, airfield, global_settings))
            
            if checkwx_config.get("station_enabled", True):
                entities.append(StationInfoSensor(hass, airfield, global_settings))
"""


class IntegrationHealthSensor(SensorEntity):
    """Monitor health status of external integrations (OWM, NOTAM, CheckWX).

    This sensor provides centralized monitoring of all external data sources,
    tracking failures, last update times, and overall integration health.

    State Values:
        - "healthy": All enabled integrations functioning normally
        - "warning": One integration experiencing issues
        - "critical": Two or more integrations failing

    Attributes:
        - openweathermap: {enabled, consecutive_failures, last_error, last_success}
        - notams: {enabled, consecutive_failures, last_error, last_update}
        - checkwx: {enabled, consecutive_failures, last_error, last_success}
        - failing_integrations: List of integration names with failures
        - last_updated: Last sensor update timestamp

    Used by:
        - Dashboard health status displays
        - Automation triggers for integration failures
        - Admin monitoring of integration reliability

    Example:
        State: "warning"
        Attributes:
            openweathermap: {enabled: true, consecutive_failures: 2, last_error: "API key invalid"}
            notams: {enabled: true, consecutive_failures: 0, last_update: "2026-01-22T10:00:00"}
            checkwx: {enabled: false, consecutive_failures: 0}
            failing_integrations: ["openweathermap"]
    """

    _attr_has_entity_name = True
    _attr_should_poll = True  # Poll to detect config changes
    _attr_icon = "mdi:heart-pulse"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        global_settings: dict | None = None
    ):
        """Initialize integration health sensor.

        Args:
            hass: Home Assistant instance
            entry: Config entry with integration settings
            global_settings: Global settings dict
        """
        self.hass = hass
        self._entry = entry
        self._global_settings = global_settings or {}

        self._attr_unique_id = f"{DOMAIN}_integration_health"
        self._attr_name = "Integration Health"

        # Device info for grouping
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "hangar_assistant_system")},
            name="Hangar Assistant System",
            manufacturer="Hangar Assistant",
            model="Integration Monitor",
        )

    @property
    def state(self) -> str:
        """Return health status based on integration failures.

        Returns:
            "healthy", "warning", or "critical"
        """
        integrations = self._entry.data.get("integrations", {})
        
        failing_count = 0

        # Check OWM
        owm_config = integrations.get("openweathermap", {})
        if owm_config.get("enabled") and owm_config.get("consecutive_failures", 0) > 0:
            failing_count += 1

        # Check NOTAM
        notam_config = integrations.get("notams", {})
        if notam_config.get("enabled") and notam_config.get("consecutive_failures", 0) > 0:
            failing_count += 1

        # Check CheckWX
        checkwx_config = integrations.get("checkwx", {})
        if checkwx_config.get("enabled") and checkwx_config.get("consecutive_failures", 0) > 0:
            failing_count += 1

        if failing_count == 0:
            return "healthy"
        elif failing_count == 1:
            return "warning"
        else:
            return "critical"

    @property
    def extra_state_attributes(self) -> dict:
        """Return detailed integration status.

        Returns:
            Dict with per-integration status and failing list
        """
        integrations = self._entry.data.get("integrations", {})

        failing_integrations = []

        # OWM status
        owm_config = integrations.get("openweathermap", {})
        owm_status = {
            "enabled": owm_config.get("enabled", False),
            "consecutive_failures": owm_config.get("consecutive_failures", 0),
            "last_error": owm_config.get("last_error"),
            "last_success": owm_config.get("last_success"),
        }
        if owm_status["enabled"] and owm_status["consecutive_failures"] > 0:
            failing_integrations.append("openweathermap")

        # NOTAM status
        notam_config = integrations.get("notams", {})
        notam_status = {
            "enabled": notam_config.get("enabled", False),
            "consecutive_failures": notam_config.get("consecutive_failures", 0),
            "last_error": notam_config.get("last_error"),
            "last_update": notam_config.get("last_update"),
        }
        if notam_status["enabled"] and notam_status["consecutive_failures"] > 0:
            failing_integrations.append("notams")

        # CheckWX status
        checkwx_config = integrations.get("checkwx", {})
        checkwx_status = {
            "enabled": checkwx_config.get("enabled", False),
            "consecutive_failures": checkwx_config.get("consecutive_failures", 0),
            "last_error": checkwx_config.get("last_error"),
            "last_success": checkwx_config.get("last_success"),
        }
        if checkwx_status["enabled"] and checkwx_status["consecutive_failures"] > 0:
            failing_integrations.append("checkwx")

        return {
            "openweathermap": owm_status,
            "notams": notam_status,
            "checkwx": checkwx_status,
            "failing_integrations": failing_integrations,
            "last_updated": dt_util.utcnow().isoformat(),
        }

    async def async_update(self) -> None:
        """Update sensor state (polled every 5 minutes)."""
        # State is computed from config entry data, no fetch needed
        pass

