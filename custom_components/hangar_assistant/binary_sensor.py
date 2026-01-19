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
        
        # Unique ID and Slugification
        self._id_slug = config["name"].lower().replace(" ", "_")
        self._attr_unique_id = f"{self._id_slug}_master_safety_alert"
        self._attr_name = f"{config['name']} Master Safety Alert"
        
        # Setting Device Class to SAFETY ensures 'Safe/Unsafe' or 'Clear/Alert' in UI
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
        
        # 1. Check Data Freshness for this specific airfield
        freshness_id = f"sensor.{self._id_slug}_weather_data_age"
        freshness_state = self.hass.states.get(freshness_id)
        
        if freshness_state and freshness_state.state not in ("unknown", "unavailable"):
            if int(float(freshness_state.state)) > 30:
                return True  # ALERT: Weather data is stale

        # 2. Check Carb Icing Risk for this specific airfield
        carb_id = f"sensor.{self._id_slug}_carb_risk"
        carb_state = self.hass.states.get(carb_id)
        
        if carb_state and "Serious Risk" in carb_state.state:
            return True  # ALERT: Atmospheric conditions favor serious icing

        return False

    @property
    def extra_state_attributes(self):
        """Provide detailed reasons for the alert state."""
        active_reasons = []
        
        # Check freshness again for attribute reporting
        f_state = self.hass.states.get(f"sensor.{self._id_slug}_weather_data_age")
        if f_state and f_state.state not in ("unknown", "unavailable"):
            if int(float(f_state.state)) > 30:
                active_reasons.append("Stale Weather Data (>30m)")
                
        return {
            "airfield": self._config["name"],
            "active_alerts": active_reasons,
            "pilot_action_required": len(active_reasons) > 0
        }