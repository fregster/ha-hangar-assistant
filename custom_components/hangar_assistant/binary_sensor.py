"""Binary sensor platform for Hangar Assistant."""
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hangar Assistant binary sensors dynamically."""
    entities = []
    
    # Generate a Master Safety Alert for every Airfield in the list
    for airfield in entry.data.get("airfields", []):
        entities.append(HangarMasterSafetyAlert(hass, airfield))

    async_add_entities(entities)

class HangarMasterSafetyAlert(BinarySensorEntity):
    """Annunciator that trips if airfield-specific safety parameters are exceeded."""

    def __init__(self, hass, config):
        """Initialize the safety alert."""
        self.hass = hass
        self._config = config
        
        # Unique ID and Slugification (matches sensor.py logic)
        self._id_slug = config["name"].lower().replace(" ", "_")
        self._attr_unique_id = f"{self._id_slug}_master_safety_alert"
        self._attr_name = f"{config['name']} Master Safety Alert"
        
        # Setting Device Class to SAFETY ensures 'Safe/Unsafe' in UI
        self._attr_device_class = BinarySensorDeviceClass.SAFETY
        
        # Link to the same Device as the sensors for this airfield
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._id_slug)},
            name=config["name"],
            manufacturer="Fregster Aviation",
            model="Hangar Assistant v2601.1",
        )

    @property
    def is_on(self) -> bool:
        """Return True if an alert condition exists for THIS airfield."""
        
        # 1. Check Data Freshness
        # This matches the entity_id pattern: sensor.[slug]_weather_data_age
        freshness_id = f"sensor.{self._id_slug}_weather_data_age"
        freshness_state = self.hass.states.get(freshness_id)
        
        if freshness_state and freshness_state.state not in ("unknown", "unavailable"):
            try:
                if int(float(freshness_state.state)) > 30:
                    return True  # ALERT: Weather data is stale (>30 mins)
            except ValueError:
                pass

        # 2. Check Carb Icing Risk
        carb_id = f"sensor.{self._id_slug}_carb_risk"
        carb_state = self.hass.states.get(carb_id)
        
        if carb_state and carb_state.state == "Serious Risk":
            return True  # ALERT: Atmospheric conditions favor serious icing

        return False

    @property
    def extra_state_attributes(self):
        """Provide detailed reasons for the alert state."""
        active_reasons = []
        
        # Logic for attributes
        f_state = self.hass.states.get(f"sensor.{self._id_slug}_weather_data_age")
        if f_state and f_state.state not in ("unknown", "unavailable"):
            try:
                if int(float(f_state.state)) > 30:
                    active_reasons.append("Stale Weather Data")
            except ValueError:
                pass

        c_state = self.hass.states.get(f"sensor.{self._id_slug}_carb_risk")
        if c_state and c_state.state == "Serious Risk":
            active_reasons.append("Serious Carb Icing Risk")
                
        return {
            "airfield": self._config["name"],
            "active_alerts": active_reasons,
            "pilot_action_required": len(active_reasons) > 0
        }