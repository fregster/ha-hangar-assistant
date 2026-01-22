/**
 * Hangar Assistant Dashboard State Manager
 * 
 * Manages per-device airfield/aircraft selection using:
 * 1. URL parameters (highest priority) - for fixed wall displays
 * 2. localStorage (medium priority) - for interactive user preferences
 * 3. Config defaults (low priority) - from integration settings
 * 4. Auto-detection (fallback) - first available entity
 * 
 * Usage in dashboard:
 *   const airfield = HangarStateManager.getAirfield(hass);
 *   const aircraft = HangarStateManager.getAircraft(hass);
 * 
 * For fixed displays, bookmark URL with:
 *   http://homeassistant:8123/hangar-glass-cockpit?airfield=popham&aircraft=g_abcd
 */

class HangarStateManager {
  /**
   * Get current airfield slug using priority: URL > localStorage > config > auto
   * 
   * Args:
   *   hass: Home Assistant object with states and config
   * 
   * Returns:
   *   String airfield slug (e.g., "popham") or null if none available
   */
  static getAirfield(hass) {
    // Priority 1: URL parameter
    const urlParams = new URLSearchParams(window.location.search);
    const urlAirfield = urlParams.get('airfield');
    if (urlAirfield) {
      // Save to localStorage for future visits
      this.setAirfield(urlAirfield);
      return urlAirfield;
    }

    // Priority 2: localStorage (user's last selection)
    const storedAirfield = localStorage.getItem('hangar_assistant_airfield');
    if (storedAirfield && storedAirfield !== '') {
      return storedAirfield;
    }

    // Priority 3: Config default from integration settings
    const configDefault = this._getConfigDefault(hass, 'default_dashboard_airfield');
    if (configDefault && configDefault !== '') {
      return configDefault;
    }

    // Priority 4: Auto-detect first available airfield sensor
    return this._autoDetectAirfield(hass);
  }

  /**
   * Get current aircraft slug using priority: URL > localStorage > config > auto
   * 
   * Args:
   *   hass: Home Assistant object with states and config
   * 
   * Returns:
   *   String aircraft slug (e.g., "g_abcd") or null if none available
   */
  static getAircraft(hass) {
    // Priority 1: URL parameter
    const urlParams = new URLSearchParams(window.location.search);
    const urlAircraft = urlParams.get('aircraft');
    if (urlAircraft) {
      // Save to localStorage for future visits
      this.setAircraft(urlAircraft);
      return urlAircraft;
    }

    // Priority 2: localStorage (user's last selection)
    const storedAircraft = localStorage.getItem('hangar_assistant_aircraft');
    if (storedAircraft && storedAircraft !== '') {
      return storedAircraft;
    }

    // Priority 3: Config default from integration settings
    const configDefault = this._getConfigDefault(hass, 'default_dashboard_aircraft');
    if (configDefault && configDefault !== '') {
      return configDefault;
    }

    // Priority 4: Auto-detect first available aircraft sensor
    return this._autoDetectAircraft(hass);
  }

  /**
   * Set airfield selection in localStorage
   * 
   * Args:
   *   airfieldSlug: String slug like "popham"
   */
  static setAirfield(airfieldSlug) {
    if (airfieldSlug && airfieldSlug !== '') {
      localStorage.setItem('hangar_assistant_airfield', airfieldSlug);
    }
  }

  /**
   * Set aircraft selection in localStorage
   * 
   * Args:
   *   aircraftSlug: String slug like "g_abcd"
   */
  static setAircraft(aircraftSlug) {
    if (aircraftSlug && aircraftSlug !== '') {
      localStorage.setItem('hangar_assistant_aircraft', aircraftSlug);
    }
  }

  /**
   * Clear stored preferences (reset to config defaults or auto-detect)
   */
  static clearStoredPreferences() {
    localStorage.removeItem('hangar_assistant_airfield');
    localStorage.removeItem('hangar_assistant_aircraft');
  }

  /**
   * Get config default from integration settings (internal helper)
   * 
   * Args:
   *   hass: Home Assistant object
   *   settingKey: Key like 'default_dashboard_airfield'
   * 
   * Returns:
   *   String value or null
   */
  static _getConfigDefault(hass, settingKey) {
    try {
      // Try to read from sensor attributes (integration exposes settings via sensor)
      const settingsSensor = hass.states['sensor.hangar_assistant_settings'];
      if (settingsSensor && settingsSensor.attributes) {
        return settingsSensor.attributes[settingKey] || null;
      }
    } catch (e) {
      console.warn('Could not read Hangar Assistant config defaults:', e);
    }
    return null;
  }

  /**
   * Auto-detect first available airfield from entities (internal helper)
   * 
   * Args:
   *   hass: Home Assistant object with states
   * 
   * Returns:
   *   String airfield slug or null
   */
  static _autoDetectAirfield(hass) {
    try {
      // Find first sensor with _master_safety_alert suffix (indicates airfield)
      const states = Object.values(hass.states);
      const airfieldSensor = states.find(entity => 
        entity.entity_id.startsWith('binary_sensor.') &&
        entity.entity_id.endsWith('_master_safety_alert')
      );
      
      if (airfieldSensor) {
        // Extract slug: binary_sensor.popham_master_safety_alert -> popham
        return airfieldSensor.entity_id
          .replace('binary_sensor.', '')
          .replace('_master_safety_alert', '');
      }
    } catch (e) {
      console.warn('Could not auto-detect airfield:', e);
    }
    return null;
  }

  /**
   * Auto-detect first available aircraft from entities (internal helper)
   * 
   * Args:
   *   hass: Home Assistant object with states
   * 
   * Returns:
   *   String aircraft slug or null
   */
  static _autoDetectAircraft(hass) {
    try {
      // Find first sensor with _performance_margin suffix (indicates aircraft)
      const states = Object.values(hass.states);
      const aircraftSensor = states.find(entity =>
        entity.entity_id.startsWith('sensor.') &&
        entity.entity_id.endsWith('_performance_margin')
      );
      
      if (aircraftSensor) {
        // Extract slug: sensor.g_abcd_performance_margin -> g_abcd
        return aircraftSensor.entity_id
          .replace('sensor.', '')
          .replace('_performance_margin', '');
      }
    } catch (e) {
      console.warn('Could not auto-detect aircraft:', e);
    }
    return null;
  }

  /**
   * Get the select entity state (for backward compatibility with existing dashboards)
   * Falls back to this manager if select entity is unavailable
   * 
   * Args:
   *   hass: Home Assistant object
   *   entityId: Select entity ID like 'select.hangar_assistant_airfield_selector'
   *   fallbackType: 'airfield' or 'aircraft'
   * 
   * Returns:
   *   String slug
   */
  static getSelectOrFallback(hass, entityId, fallbackType) {
    try {
      const selectState = hass.states[entityId];
      if (selectState && selectState.state && selectState.state !== 'unknown' && selectState.state !== 'unavailable') {
        return selectState.state;
      }
    } catch (e) {
      console.warn(`Select entity ${entityId} not available, using fallback`);
    }

    // Fallback to our priority system
    if (fallbackType === 'airfield') {
      return this.getAirfield(hass);
    } else if (fallbackType === 'aircraft') {
      return this.getAircraft(hass);
    }
    return null;
  }
}

// Export for use in dashboard cards
window.HangarStateManager = HangarStateManager;
