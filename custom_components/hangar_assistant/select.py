from __future__ import annotations

"""Select platform for Hangar Assistant.

Provides built-in dropdowns for airfield, aircraft, and pilot selection without
requiring user-created helpers. Options are derived from the configured
entities in the config entry and expose stable entity_ids for dashboard binding.
"""

import logging
from typing import Iterable, List

try:
    from homeassistant.components.select import SelectEntity
except ImportError:  # pragma: no cover - fallback for minimal test environments
    class SelectEntity:  # type: ignore[no-redef]
        """Minimal stub used when Home Assistant's select entity is unavailable."""

        _attr_has_entity_name = True
        _attr_should_poll = False

        def __init__(self, *args, **kwargs) -> None:
            super().__init__()

        def async_write_ha_state(self) -> None:
            return None

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _slugify(value: str | None) -> str:
    """Convert a name/registration to a slug suitable for entity options."""
    return (value or "").strip().lower().replace(" ", "_")


def _extract_slugs(items: Iterable[dict], keys: List[str]) -> list[str]:
    """Extract unique slugs from a sequence of dicts using preferred keys.

    Args:
        items: Iterable of configuration dicts (airfields, aircraft, or pilots).
        keys: Ordered list of field names to inspect for a usable identifier.

    Returns:
        Ordered list of slugified identifiers with duplicates removed while
        preserving first-seen order.
    """
    seen: set[str] = set()
    slugs: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in keys:
            raw = item.get(key)
            if raw:
                slug = _slugify(str(raw))
                if slug and slug not in seen:
                    seen.add(slug)
                    slugs.append(slug)
                break
    return slugs


class HangarSelectBase(SelectEntity):
    """Base class for Hangar Assistant select entities.

    Handles option storage, current selection, and exposes a stable entity_id so
    dashboard templates can bind directly without user-created helpers.

    Args:
        entry: ConfigEntry for the integration
        label: Display name for the select
        options: List of selectable slugs
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:format-list-bulleted"

    def __init__(
            self,
            entry: ConfigEntry,
            label: str,
            options: list[str],
            entity_slug: str) -> None:
        super().__init__()
        self._entry = entry
        self._options = options
        self._current_option = options[0] if options else None
        self._attr_name = label
        self._attr_unique_id = f"{entry.entry_id}_{entity_slug}"
        self.entity_id = f"select.{DOMAIN}_{entity_slug}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "selectors")},
            name="Hangar Assistant Selectors",
            manufacturer="Fregster Aviation",
            model="Hangar Assistant v2601.2",
        )

    @property
    def options(self) -> list[str]:
        """Return available options."""
        return self._options

    @property
    def current_option(self) -> str | None:
        """Return the selected option or None when unset."""
        return self._current_option

    async def async_select_option(self, option: str) -> None:
        """Handle option selection from the UI.

        Raises:
            ValueError: If the option is not present in the allowed list.
        """
        if option not in self._options:
            raise ValueError(f"Invalid option: {option}")
        self._current_option = option
        self.async_write_ha_state()


class AirfieldSelect(HangarSelectBase):
    """Dropdown for selecting an airfield configured in Hangar Assistant.

    Options are slugs derived from configured airfield names to match sensor IDs
    (e.g., "Popham" -> "popham").
    """

    def __init__(self, entry: ConfigEntry, options: list[str]) -> None:
        super().__init__(entry, "Airfield Selector", options, "airfield_selector")


class AircraftSelect(HangarSelectBase):
    """Dropdown for selecting an aircraft from the configured fleet.

    Options prefer registration (`reg`) falling back to the aircraft name so the
    selection aligns with sensor entity IDs.
    """

    def __init__(self, entry: ConfigEntry, options: list[str]) -> None:
        super().__init__(entry, "Aircraft Selector", options, "aircraft_selector")


class PilotSelect(HangarSelectBase):
    """Dropdown for selecting a pilot configured in Hangar Assistant.

    Options use pilot `name` or `pilot_name` fields; slugs are lowercased with
    spaces replaced by underscores to keep dashboard bindings consistent.
    """

    def __init__(self, entry: ConfigEntry, options: list[str]) -> None:
        super().__init__(entry, "Pilot Selector", options, "pilot_selector")


class HangarSelect(HangarSelectBase):
    """Dropdown for selecting a hangar configured in Hangar Assistant.

    Options are slugs derived from configured hangar names in the format
    "{airfield_slug}_{hangar_slug}" to match entity ID patterns.
    """

    def __init__(self, entry: ConfigEntry, options: list[str]) -> None:
        super().__init__(entry, "Hangar Selector", options, "hangar_selector")


def _build_airfield_options(entry: ConfigEntry) -> list[str]:
    """Return slugs for all configured airfields in the config entry."""
    return _extract_slugs(
        entry.data.get(
            "airfields", []), [
            "name", "icao_code"])


def _build_aircraft_options(entry: ConfigEntry) -> list[str]:
    """Return slugs for all configured aircraft in the config entry."""
    return _extract_slugs(entry.data.get("aircraft", []), ["reg", "name"])


def _build_pilot_options(entry: ConfigEntry) -> list[str]:
    """Return slugs for all configured pilots in the config entry."""
    return _extract_slugs(entry.data.get("pilots", []), ["name", "pilot_name"])


def _build_hangar_options(entry: ConfigEntry) -> list[str]:
    """Return slugs for all configured hangars in the config entry.

    Hangar slugs are in the format "{airfield_slug}_{hangar_slug}" to match
    the entity ID pattern and ensure uniqueness across airfields.
    """
    hangars = entry.data.get("hangars", [])
    slugs: list[str] = []
    seen: set[str] = set()

    for hangar in hangars:
        if not isinstance(hangar, dict):
            continue

        hangar_name = hangar.get("name", "")
        airfield_name = hangar.get("airfield_name", "")

        if hangar_name and airfield_name:
            # Generate composite slug: {airfield}_{hangar}
            airfield_slug = _slugify(airfield_name)
            hangar_slug = _slugify(hangar_name)
            composite_slug = f"{airfield_slug}_{hangar_slug}"

            if composite_slug and composite_slug not in seen:
                seen.add(composite_slug)
                slugs.append(composite_slug)

    return slugs


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hangar Assistant select entities from the config entry.

    Registers four select entities (airfield, hangar, aircraft, pilot) derived
    from the stored configuration so dashboards can bind directly without user
    helpers.
    """
    airfield_options = _build_airfield_options(entry)
    hangar_options = _build_hangar_options(entry)
    aircraft_options = _build_aircraft_options(entry)
    pilot_options = _build_pilot_options(entry)

    entities: list[SelectEntity] = []
    entities.append(AirfieldSelect(entry, airfield_options))
    entities.append(HangarSelect(entry, hangar_options))
    entities.append(AircraftSelect(entry, aircraft_options))
    entities.append(PilotSelect(entry, pilot_options))

    async_add_entities(entities)
    _LOGGER.debug(
        "Hangar select entities registered: airfields=%s, hangars=%s, aircraft=%s, pilots=%s",
        len(airfield_options),
        len(hangar_options),
        len(aircraft_options),
        len(pilot_options),
    )
