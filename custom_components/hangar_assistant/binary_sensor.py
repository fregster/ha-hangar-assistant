from __future__ import annotations

"""Binary sensor platform for Hangar Assistant."""
from datetime import datetime
import math
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, DEFAULT_UNIT_PREFERENCE, DEFAULT_STALE_WEATHER_MINUTES
from .utils.units import convert_speed, get_speed_unit

async def async_setup_entry(
    hass: HomeAssistant, 
    entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Hangar Assistant binary sensors from config entry.
    
    Creates safety alert entities for each configured airfield and pilot.
    These sensors act as annunciators that turn ON when alert conditions are met.
    
    Args:
        hass: Home Assistant instance
        entry: ConfigEntry containing airfields and pilots configuration
        async_add_entities: Callback to register new entities with Home Assistant
    
    Returns:
        None. Entities registered via async_add_entities callback.
    """
    entities = []
    global_settings = entry.data.get("settings", {}) if isinstance(entry.data, dict) else {}
    airfields = [a for a in entry.data.get("airfields", []) if isinstance(a, dict)] if isinstance(entry.data, dict) else []
    airfield_lookup = {
        (a.get("name") or "").lower(): a for a in airfields if a.get("name")
    }
    
    # Generate a Master Safety Alert for every Airfield in the list
    for airfield in airfields:
        entities.append(HangarMasterSafetyAlert(hass, airfield, global_settings))

    # Generate a Medical Alert for every Pilot in the list
    for pilot in entry.data.get("pilots", []):
        entities.append(PilotMedicalAlert(hass, pilot))

    # Generate a Crosswind Envelope alert for each aircraft linked to an airfield
    aircraft_list = entry.data.get("aircraft", []) if isinstance(entry.data, dict) else []
    for aircraft in aircraft_list:
        linked_name = (aircraft.get("linked_airfield") or "").lower()
        if not linked_name:
            continue
        airfield_config = airfield_lookup.get(linked_name)
        if not airfield_config:
            continue
        if not (
            airfield_config.get("wind_sensor")
            and airfield_config.get("wind_dir_sensor")
            and airfield_config.get("runways")
        ):
            continue

        entities.append(
            AircraftCrosswindAlert(
                hass,
                aircraft,
                airfield_config,
                global_settings,
            )
        )

    async_add_entities(entities)

class HangarMasterSafetyAlert(BinarySensorEntity):
    """Airfield safety annunciator that activates on hazardous conditions.
    
    This binary sensor monitors multiple safety parameters for an airfield and returns ON
    when dangerous conditions are detected. It serves as the primary safety alert for pilots.
    
    Alert Triggers:
        1. Weather Data Stale: Temperature sensor older than configured threshold (default 30 minutes)
        2. Carb Icing Risk Serious: Temperature < 25°C AND Dew Point Spread < 5°C
        3. VFR Compliance Violation: Cloud Base < 1000 ft (below safe VFR minimum)
        4. Moderate Carb Risk + Stale Data: Combined low-confidence icing threat
    
    Inputs (monitored sensors):
        - sensor.{airfield_slug}_weather_data_age: Minutes since last temperature update
        - sensor.{airfield_slug}_carb_risk: Current icing risk level
        - sensor.{airfield_slug}_cloud_base: Estimated cloud base height (feet AGL)
    
    Outputs:
        - is_on: True if ANY alert condition is present, False if all clear
        - Device Class: SAFETY (displays as \"Unsafe\" / \"Safe\" in UI)
        - Attributes: active_alerts (list of reasons), pilot_action_required (bool)
    
    Used by:
        - Dashboard critical alerts
        - Automation for notifications
        - Preflight decision making
    
    Example states:
        - ON (Unsafe): Weather data stale OR icing risk serious OR below VFR minima
        - OFF (Safe): Weather fresh AND icing risk acceptable AND within VFR envelope
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, config: dict, global_settings: dict | None = None):
        """Initialize the safety alert."""
        self.hass = hass
        self._config = config
        self._global_settings = global_settings or {}
        self._stale_threshold = self._global_settings.get(
            "stale_weather_minutes", DEFAULT_STALE_WEATHER_MINUTES
        )
        
        # Unique ID and Slugification (matches sensor.py logic)
        name_or_reg = config.get("name") or config.get("reg") or "unknown"
        self._id_slug = name_or_reg.lower().replace(" ", "_")
        self._attr_unique_id = f"{self._id_slug}_master_safety_alert"
        
        # Setting Device Class to SAFETY ensures 'Safe/Unsafe' in UI
        self._attr_device_class = BinarySensorDeviceClass.SAFETY
        
        # Link to the same Device as the sensors for this airfield
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._id_slug)},
            name=config.get("name") or config.get("reg"),
            manufacturer="Fregster Aviation",
            model="Hangar Assistant v2601.1",
        )
        # We listen to our own generated sensors
        self._freshness_id = f"sensor.{self._id_slug}_weather_data_age"
        self._carb_id = f"sensor.{self._id_slug}_carb_risk"
        self._cloud_base_id = f"sensor.{self._id_slug}_cloud_base"

    def _parse_freshness_minutes(self, state) -> int | None:
        """Convert the freshness sensor state to integer minutes if available."""
        if state and state.state not in ("unknown", "unavailable"):
            try:
                return int(float(state.state))
            except (TypeError, ValueError):
                return None
        return None

    def _resolve_stale_threshold(self, state) -> int:
        """Resolve the stale threshold from attributes or fall back to defaults."""
        if state and hasattr(state, "attributes"):
            attr_threshold = state.attributes.get("threshold_minutes")
            if isinstance(attr_threshold, (int, float, str)):
                try:
                    return int(float(attr_threshold))
                except (TypeError, ValueError):
                    return self._stale_threshold
        return self._stale_threshold

    async def async_added_to_hass(self) -> None:
        """Register callbacks for sibling sensors."""
        
        @callback
        def _update_state(_event):
            """Update the sensor state when a source entity changes."""
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._freshness_id, self._carb_id, self._cloud_base_id], _update_state
            )
        )

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Master Safety Alert"

    def _is_unsafe(self) -> bool:
        """Determine if current conditions represent an unsafe alert state.
        
        Evaluates 4 independent alert conditions:
        1. Stale weather data (beyond threshold)
        2. Serious carburettor icing risk
        3. Below VFR cloud clearance (< 1000 ft)
        4. Moderate icing risk with uncertain data (> 15 min old)
        
        Returns:
            True if ANY condition triggers an alert, False if all clear
        """
        freshness_state = self.hass.states.get(self._freshness_id)
        freshness_minutes = self._parse_freshness_minutes(freshness_state)
        freshness_threshold = self._resolve_stale_threshold(freshness_state)

        # 1. Check Data Freshness (>threshold mins = ALERT)
        if (
            freshness_minutes is not None
            and freshness_threshold is not None
            and freshness_minutes > freshness_threshold
        ):
            return True  # ALERT: Weather data is stale beyond configured guardrail

        # 2. Check Carb Icing Risk (Serious = ALERT)
        carb_state = self.hass.states.get(self._carb_id)
        if carb_state and carb_state.state == "Serious Risk":
            return True  # ALERT: Atmospheric conditions favor serious icing

        # 3. Check VFR Compliance: Cloud Base < 1000 ft = ALERT
        cloud_base_state = self.hass.states.get(self._cloud_base_id)
        if cloud_base_state and cloud_base_state.state not in ("unknown", "unavailable"):
            try:
                cloud_base = int(float(cloud_base_state.state))
                if cloud_base < 1000:
                    return True  # ALERT: Below VFR cloud clearance minimum
            except ValueError:
                pass

        # 4. Check Moderate Risk + Stale Data (combined low-confidence threat)
        if carb_state and carb_state.state == "Moderate Risk" and freshness_minutes is not None:
            if freshness_minutes > 15:
                return True  # ALERT: Moderate icing risk with uncertain data

        return False

    @property
    def is_on(self) -> bool:
        """Return True if an alert condition exists for THIS airfield."""
        return self._is_unsafe()

    @property
    def extra_state_attributes(self):
        """Provide detailed reasons for the alert state."""
        active_reasons = []
        
        # 1. Stale Weather Data
        f_state = self.hass.states.get(self._freshness_id)
        freshness_minutes = self._parse_freshness_minutes(f_state)
        freshness_threshold = self._resolve_stale_threshold(f_state)
        if (
            freshness_minutes is not None
            and freshness_threshold is not None
            and freshness_minutes > freshness_threshold
        ):
            active_reasons.append(
                f"Stale Weather Data ({freshness_minutes} min > {freshness_threshold} min)"
            )

        # 2. Carb Icing Risk
        c_state = self.hass.states.get(self._carb_id)
        if c_state and c_state.state == "Serious Risk":
            active_reasons.append("Serious Carb Icing Risk")
        elif c_state and c_state.state == "Moderate Risk" and freshness_minutes is not None:
            if freshness_minutes > 15:
                active_reasons.append("Moderate Carb Risk (Low Data Confidence)")

        # 3. VFR Compliance: Cloud Base
        cloud_state = self.hass.states.get(self._cloud_base_id)
        if cloud_state and cloud_state.state not in ("unknown", "unavailable"):
            try:
                cloud_base = int(float(cloud_state.state))
                if cloud_base < 1000:
                    active_reasons.append(f"Below VFR Cloud Minimum ({cloud_base} ft)")
            except ValueError:
                pass
                
        return {
            "airfield": self._config.get("name", "Unknown"),
            "active_alerts": active_reasons,
            "pilot_action_required": len(active_reasons) > 0,
            "alert_count": len(active_reasons),
            "last_updated": dt_util.now().isoformat(),
            "stale_threshold_minutes": freshness_threshold,
        }


class AircraftCrosswindAlert(BinarySensorEntity):
    """Binary alert when crosswind exceeds the linked aircraft's envelope.
    
    Compares the minimum achievable crosswind across all runways at the linked airfield
    with the aircraft's maximum demonstrated crosswind limit. Raises a safety alert when
    current conditions exceed the envelope.

    Inputs:
        - aircraft.max_xwind: Maximum demonstrated crosswind (kt)
        - linked_airfield.wind_sensor: Wind speed sensor entity ID (kt)
        - linked_airfield.wind_dir_sensor: Wind direction sensor entity ID (degrees)
        - linked_airfield.runways: Comma-separated runway identifiers (e.g., "09, 27")

    Outputs:
        - is_on: True when min crosswind > max_xwind
        - Attributes: best_runway, min_crosswind, limit, wind details, runway matrix

    Used by:
        - Dashboard safety annunciation
        - Notifications to pilots/CFIs before departure
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(
        self,
        hass: HomeAssistant,
        aircraft_config: dict,
        airfield_config: dict,
        global_settings: dict | None = None,
    ):
        self.hass = hass
        self._aircraft = aircraft_config or {}
        self._airfield = airfield_config or {}
        self._unit_preference = (global_settings or {}).get("unit_preference", DEFAULT_UNIT_PREFERENCE)

        name_or_reg = self._aircraft.get("reg") or self._aircraft.get("name") or "unknown"
        self._id_slug = name_or_reg.lower().replace(" ", "_")
        self._attr_unique_id = f"{self._id_slug}_crosswind_alert"

        self._wind_sensor = self._airfield.get("wind_sensor")
        self._wind_dir_sensor = self._airfield.get("wind_dir_sensor")
        self._runways = self._airfield.get("runways", "")

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._id_slug)},
            name=self._aircraft.get("reg") or self._aircraft.get("name"),
            manufacturer="Fregster Aviation",
            model="Hangar Assistant v2601.1",
        )

        self._source_entities = [e for e in [self._wind_sensor, self._wind_dir_sensor] if e]

    async def async_added_to_hass(self) -> None:
        """Track wind sensor updates to refresh the alert state."""
        if not self._source_entities:
            return

        @callback
        def _update_state(_event):
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._source_entities, _update_state
            )
        )

    @property
    def name(self) -> str:
        return "Crosswind Envelope"

    def _get_sensor_value(self, entity_id: str) -> float | None:
        state = self.hass.states.get(entity_id)
        if state and state.state not in ("unknown", "unavailable"):
            try:
                return float(state.state)
            except ValueError:
                return None
        return None

    def _compute_crosswind(self) -> tuple[str | None, float | None, list[dict], float | None, float | None]:
        """Return best runway, min crosswind (kt), matrix, wind speed, wind dir."""
        if not (self._wind_sensor and self._wind_dir_sensor and self._runways):
            return None, None, [], None, None

        wind_speed = self._get_sensor_value(self._wind_sensor)
        wind_dir = self._get_sensor_value(self._wind_dir_sensor)
        if wind_speed is None or wind_dir is None:
            return None, None, [], wind_speed, wind_dir

        runways = [r.strip() for r in self._runways.split(",") if r.strip()]
        matrix: list[dict] = []
        best_runway = None
        min_crosswind = None

        for runway in runways:
            try:
                heading = int(runway) * 10
            except (ValueError, TypeError):
                continue

            angle_rad = math.radians(wind_dir - heading)
            angle_off = abs((wind_dir - heading + 180) % 360 - 180)
            crosswind_kt = abs(wind_speed * math.sin(angle_rad))
            headwind_kt = wind_speed * math.cos(angle_rad)

            crosswind_unit = convert_speed(crosswind_kt, from_knots=True, to_preference=self._unit_preference)
            headwind_unit = convert_speed(headwind_kt, from_knots=True, to_preference=self._unit_preference)
            tailwind_unit = abs(headwind_unit) if headwind_unit is not None and headwind_unit < 0 else 0

            matrix.append(
                {
                    "runway": runway,
                    "heading": heading,
                    "angle_off": round(angle_off, 1),
                    "crosswind": round(crosswind_unit, 1) if crosswind_unit is not None else None,
                    "headwind": round(headwind_unit, 1) if headwind_unit is not None else None,
                    "tailwind": round(tailwind_unit, 1) if tailwind_unit else 0,
                    "component_unit": get_speed_unit(self._unit_preference),
                }
            )

            if min_crosswind is None or crosswind_kt < min_crosswind:
                min_crosswind = crosswind_kt
                best_runway = runway

        return best_runway, min_crosswind, matrix, wind_speed, wind_dir

    @property
    def is_on(self) -> bool:
        try:
            max_limit = float(self._aircraft.get("max_xwind", 0))
        except (TypeError, ValueError):
            return False

        best_runway, min_crosswind, _, _, _ = self._compute_crosswind()
        if min_crosswind is None or best_runway is None:
            return False

        return min_crosswind > max_limit

    @property
    def extra_state_attributes(self):
        attrs = {
            "aircraft": self._aircraft.get("reg") or self._aircraft.get("name"),
            "airfield": self._airfield.get("name"),
            "max_crosswind_limit": self._aircraft.get("max_xwind"),
            "wind_unit": get_speed_unit(self._unit_preference),
        }

        best_runway, min_crosswind, matrix, wind_speed, wind_dir = self._compute_crosswind()

        if wind_speed is not None:
            attrs["wind_speed"] = round(
                convert_speed(wind_speed, from_knots=True, to_preference=self._unit_preference) or 0, 1
            )
        attrs["wind_direction"] = wind_dir

        if min_crosswind is not None:
            converted = convert_speed(
                min_crosswind,
                from_knots=True,
                to_preference=self._unit_preference,
            )
            attrs["min_crosswind"] = round(converted, 1) if converted is not None else None
            try:
                limit = float(self._aircraft.get("max_xwind", 0))
                attrs["within_limit"] = min_crosswind <= limit
            except (TypeError, ValueError):
                attrs["within_limit"] = None

        attrs["best_runway"] = best_runway
        if matrix:
            attrs["runway_matrix"] = matrix
            attrs["runways_evaluated"] = len(matrix)

        return attrs

class PilotMedicalAlert(BinarySensorEntity):
    """Trips if a pilot's medical has expired."""

    _attr_has_entity_name = True
    _attr_should_poll = True

    def __init__(self, hass: HomeAssistant, config: dict):
        """Initialize the medical alert."""
        self.hass = hass
        self._config = config
        
        # Unique ID and Slugification
        self._id_slug = config.get("name", "unknown").lower().replace(" ", "_")
        self._attr_unique_id = f"{self._id_slug}_medical_expiry_alert"
        
        # PROBLEM class shows as 'Problem/OK' or 'Detected/Clear'
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        
        # Group under a Pilot device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._id_slug)},
            name=config.get("name"),
            manufacturer="Fregster Aviation",
            model="Hangar Assistant v2601.1",
        )

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Medical Status"

    @property
    def is_on(self) -> bool:
        """Return True if the medical has expired."""
        expiry_str = self._config.get("medical_expiry")
        if not expiry_str:
            return False
        
        try:
            # Parse the YYYY-MM-DD date from config
            expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
            return expiry_date < dt_util.now().date()
        except (ValueError, TypeError):
            return False

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional info."""
        return {
            "expiry_date": self._config.get("medical_expiry"),
            "licence": self._config.get("licence_number")
        }
