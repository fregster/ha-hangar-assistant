"""Hangar helper utilities for Hangar Assistant.

This module provides helper functions for managing hangar-aware aircraft and sensors,
including backward compatibility logic for aircraft that reference airfields directly.

Key Functions:
    - get_aircraft_airfield: Resolves airfield for aircraft (hangar → direct airfield → None)
    - get_aircraft_hangar: Returns hangar config for aircraft if assigned
    - get_hangar_sensor: Gets sensor value with fallback (hangar → airfield → global)
    - find_hangar_by_name: Locates hangar config by name
    - get_airfield_for_hangar: Gets airfield config for a hangar

Used by:
    - Sensors that need location-based data (temperature, humidity)
    - Binary sensors for condition checks
    - Services and automation helpers
"""

from __future__ import annotations
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


def get_aircraft_airfield(
        aircraft_config: dict,
        hangars: list,
        airfields: list) -> dict | None:
    """Get airfield config for an aircraft, with hangar priority.

    Resolution order:
        1. If aircraft has hangar → return hangar's airfield
        2. If aircraft has direct airfield link → return that airfield
        3. Return None if neither configured

    Args:
        aircraft_config: Aircraft configuration dict
        hangars: List of all hangar configs
        airfields: List of all airfield configs

    Returns:
        Airfield config dict or None if not found
    """
    # Check hangar first (new pattern)
    if hangar_name := aircraft_config.get("hangar"):
        hangar = find_hangar_by_name(hangar_name, hangars)
        if hangar:
            airfield_name = hangar.get("airfield_name")
            for airfield in airfields:
                if airfield.get("name") == airfield_name:
                    return airfield

    # Fallback to direct airfield link (legacy pattern)
    if airfield_name := aircraft_config.get("linked_airfield"):
        for airfield in airfields:
            if airfield.get("name") == airfield_name:
                return airfield

    return None


def get_aircraft_hangar(aircraft_config: dict, hangars: list) -> dict | None:
    """Get hangar config for an aircraft if assigned.

    Args:
        aircraft_config: Aircraft configuration dict
        hangars: List of all hangar configs

    Returns:
        Hangar config dict or None if not assigned to a hangar
    """
    if hangar_name := aircraft_config.get("hangar"):
        return find_hangar_by_name(hangar_name, hangars)
    return None


def find_hangar_by_name(hangar_name: str, hangars: list) -> dict | None:
    """Find hangar config by name.

    Args:
        hangar_name: Name of the hangar to find
        hangars: List of all hangar configs

    Returns:
        Hangar config dict or None if not found
    """
    for hangar in hangars:
        if hangar.get("name") == hangar_name:
            return hangar
    return None


def get_airfield_for_hangar(
        hangar_config: dict,
        airfields: list) -> dict | None:
    """Get airfield config for a hangar.

    Args:
        hangar_config: Hangar configuration dict
        airfields: List of all airfield configs

    Returns:
        Airfield config dict or None if not found
    """
    airfield_name = hangar_config.get("airfield_name")
    for airfield in airfields:
        if airfield.get("name") == airfield_name:
            return airfield
    return None


def get_hangar_sensor_value(
    hass,
    sensor_type: str,
    hangar_config: dict | None,
    airfield_config: dict | None,
    global_sensor: str | None = None
) -> Any:
    """Get sensor value with fallback hierarchy: hangar → airfield → global.

    This is the core fallback logic for environment sensors. Allows aircraft in
    hangars to use hangar-specific sensors, with graceful degradation to airfield
    or global sensors if not available.

    Args:
        hass: Home Assistant instance
        sensor_type: Type of sensor ('temp_sensor', 'humidity_sensor', etc.)
        hangar_config: Hangar configuration dict (optional)
        airfield_config: Airfield configuration dict (optional)
        global_sensor: Global fallback sensor entity ID (optional)

    Returns:
        Sensor state value (float/str) or None if unavailable

    Example:
        temp = get_hangar_sensor_value(
            hass,
            'temp_sensor',
            hangar_config=my_hangar,
            airfield_config=my_airfield,
            global_sensor='sensor.weather_temperature'
        )
    """
    # Try sensors in priority order
    for source_name, config, key in [
        ("Hangar", hangar_config, sensor_type),
        ("Airfield", airfield_config, sensor_type),
        ("Global", {"sensor_type": global_sensor}, "sensor_type"),
    ]:
        if value := _try_get_sensor_value(hass, config, key, source_name):
            return value

    return None


def _try_get_sensor_value(
    hass, config: dict | None, key: str, source_name: str
) -> float | None:
    """Try to get numeric value from a sensor config.

    Args:
        hass: Home Assistant instance
        config: Config dict containing sensor entity ID
        key: Key to look up sensor entity ID
        source_name: Name of source for logging ("Hangar", "Airfield", "Global")

    Returns:
        Numeric sensor value or None if unavailable/invalid
    """
    if not config:
        return None

    sensor_id = config.get(key)
    if not sensor_id:
        return None

    state = hass.states.get(sensor_id)
    if not state or state.state in ["unavailable", "unknown", "none", ""]:
        return None

    try:
        return float(state.state)
    except (ValueError, TypeError):
        _LOGGER.debug(
            f"{source_name} sensor {sensor_id} has non-numeric value: {state.state}"
        )
        return None


def get_hangar_temperature(
    hass,
    aircraft_config: dict | None = None,
    hangar_config: dict | None = None,
    airfield_config: dict | None = None,
    global_sensor: str | None = None
) -> float | None:
    """Convenience function to get temperature with full fallback chain.

    Args:
        hass: Home Assistant instance
        aircraft_config: Aircraft config (will resolve hangar/airfield automatically)
        hangar_config: Explicit hangar config (overrides aircraft hangar)
        airfield_config: Explicit airfield config (overrides aircraft airfield)
        global_sensor: Global temperature sensor entity ID

    Returns:
        Temperature in Celsius or None
    """
    # If aircraft provided, resolve hangar/airfield
    if aircraft_config and not hangar_config and not airfield_config:
        from homeassistant.core import HomeAssistant
        if isinstance(hass, HomeAssistant):
            entry_data = hass.data.get("hangar_assistant", {})
            hangars = entry_data.get("hangars", [])
            airfields = entry_data.get("airfields", [])

            hangar_config = get_aircraft_hangar(aircraft_config, hangars)
            airfield_config = get_aircraft_airfield(
                aircraft_config, hangars, airfields)

    return get_hangar_sensor_value(
        hass, "temp_sensor", hangar_config, airfield_config, global_sensor
    )


def get_hangar_humidity(
    hass,
    aircraft_config: dict | None = None,
    hangar_config: dict | None = None,
    airfield_config: dict | None = None,
    global_sensor: str | None = None
) -> float | None:
    """Convenience function to get humidity with full fallback chain.

    Args:
        hass: Home Assistant instance
        aircraft_config: Aircraft config (will resolve hangar/airfield automatically)
        hangar_config: Explicit hangar config (overrides aircraft hangar)
        airfield_config: Explicit airfield config (overrides aircraft airfield)
        global_sensor: Global humidity sensor entity ID

    Returns:
        Humidity percentage or None
    """
    # If aircraft provided, resolve hangar/airfield
    if aircraft_config and not hangar_config and not airfield_config:
        from homeassistant.core import HomeAssistant
        if isinstance(hass, HomeAssistant):
            entry_data = hass.data.get("hangar_assistant", {})
            hangars = entry_data.get("hangars", [])
            airfields = entry_data.get("airfields", [])

            hangar_config = get_aircraft_hangar(aircraft_config, hangars)
            airfield_config = get_aircraft_airfield(
                aircraft_config, hangars, airfields)

    return get_hangar_sensor_value(
        hass, "humidity_sensor", hangar_config, airfield_config, global_sensor
    )
