"""Binary sensor platform for Hangar Assistant."""
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from .const import DOMAIN

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the binary sensors from a config entry."""
    config = config_entry.data
    
    # Safety alerts are specifically for Airfield configurations
    if config.get("type") == "airfield":
        async_add_entities([HangarMasterSafetyAlert(hass, config)])

class HangarMasterSafetyAlert(BinarySensorEntity):
    """Annunciator that trips if any safety parameter is exceeded."""

    def __init__(self, hass, config):
        """Initialize the safety alert."""
        self.hass = hass
        self._config = config
        self._attr_name = f"{config['name']} Master Safety Alert"
        self._attr_unique_id = f"{config['name']}_master_safety_alert"
        # 'PROBLEM' shows OK/Problem; 'SAFETY' shows Safe/Unsafe in UI
        self._attr_device_class = BinarySensorDeviceClass.SAFETY

    @property
    def is_on(self) -> bool:
        """Return True if an alert condition exists (Unsafe)."""
        
        # 1. Check Data Freshness (Stale data is a safety risk)
        freshness_id = f"sensor.{self._config['name'].lower().replace(' ', '_')}_data_freshness"
        freshness_state = self.hass.states.get(freshness_id)
        
        if freshness_state and freshness_state.state not in ("unknown", "unavailable"):
            if int(freshness_state.state) > 30:
                return True  # ALERT: Data is older than 30 minutes

        # 2. Check Carb Icing Risk
        carb_id = f"sensor.{self._config['name'].lower().replace(' ', '_')}_carb_risk"
        carb_state = self.hass.states.get(carb_id)
        
        if carb_state and "Serious Risk" in carb_state.state:
            return True  # ALERT: Serious icing risk detected

        # 3. Check Backup Integrity for Legal Records
        backup_id = f"sensor.{self._config['name'].lower().replace(' ', '_')}_backup_integrity"
        backup_state = self.hass.states.get(backup_id)
        
        if backup_state and "WARNING" in backup_state.state:
            return True  # ALERT: Legal records not backed up off-site

        return False

    @property
    def extra_state_attributes(self):
        """Return the specific cause of the alert for the UI."""
        reasons = []
        
        # Logic to populate the reason for the Red light
        freshness = self.hass.states.get(f"sensor.{self._config['name'].lower().replace(' ', '_')}_data_freshness")
        if freshness and int(freshness.state) > 30:
            reasons.append("Stale Weather Data")
            
        return {
            "active_alerts": reasons,
            "pilot_action_required": len(reasons) > 0
        }