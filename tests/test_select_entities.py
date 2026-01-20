from __future__ import annotations

import pytest
from types import SimpleNamespace

from custom_components.hangar_assistant.select import (
    _build_airfield_options,
    _build_aircraft_options,
    _build_pilot_options,
    AirfieldSelect,
    AircraftSelect,
    PilotSelect,
    async_setup_entry,
)


def _mock_entry(data: dict) -> SimpleNamespace:
    return SimpleNamespace(entry_id="test-entry", data=data)


def test_option_builders_slugify_and_deduplicate() -> None:
    entry = _mock_entry(
        {
            "airfields": [{"name": "Popham"}, {"name": "Popham"}, {"icao_code": "KJFK"}],
            "aircraft": [{"reg": "G-ABCD"}, {"name": "N12345"}],
            "pilots": [{"name": "Jane Doe"}, {"pilot_name": "Jane Doe"}, {"name": "John"}],
        }
    )

    assert _build_airfield_options(entry) == ["popham", "kjfk"]
    assert _build_aircraft_options(entry) == ["g-abcd", "n12345"]
    assert _build_pilot_options(entry) == ["jane_doe", "john"]


@pytest.mark.asyncio
async def test_async_setup_entry_creates_select_entities(hass) -> None:
    entry = _mock_entry(
        {
            "airfields": [{"name": "Popham"}],
            "aircraft": [{"reg": "G-ABCD"}],
            "pilots": [{"name": "Alice"}],
        }
    )

    created = []

    await async_setup_entry(hass, entry, lambda ents: created.extend(ents))

    assert len(created) == 3
    airfield, aircraft, pilot = created
    assert airfield.options == ["popham"]
    assert aircraft.options == ["g-abcd"]
    assert pilot.options == ["alice"]
    assert airfield.current_option == "popham"
    assert aircraft.current_option == "g-abcd"
    assert pilot.current_option == "alice"
    assert airfield.entity_id == "select.hangar_assistant_airfield_selector"


@pytest.mark.asyncio
async def test_select_rejects_invalid_option() -> None:
    entry = _mock_entry({"airfields": [{"name": "Popham"}]})
    selector = AirfieldSelect(entry, ["popham"])

    with pytest.raises(ValueError):
        await selector.async_select_option("not-valid")

    await selector.async_select_option("popham")
    assert selector.current_option == "popham"
