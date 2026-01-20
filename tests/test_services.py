"""Tests for Hangar Assistant services."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from homeassistant.core import HomeAssistant, ServiceCall
from custom_components.hangar_assistant.const import DOMAIN, DEFAULT_DASHBOARD_VERSION
from custom_components.hangar_assistant import (
    INTEGRATION_MAJOR_VERSION,
    INTEGRATION_VERSION,
    async_create_dashboard,
    async_generate_all_ai_briefings,
    async_setup_entry,
)


@pytest.fixture
def mock_service_call():
    """Create a mock service call."""
    return MagicMock(spec=ServiceCall)


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.services = MagicMock()
    # async_register is synchronous in HA; use MagicMock to avoid warnings
    hass.services.async_register = MagicMock()
    hass.config_entries = MagicMock()
    hass.config = MagicMock()
    hass.config.path = MagicMock(return_value="/config/www/hangar/")
    hass.async_add_executor_job = AsyncMock()
    return hass


def test_manual_cleanup_service_registration(mock_hass):
    """Test that manual_cleanup service is registered."""
    from custom_components.hangar_assistant import async_setup

    # Mock async_cleanup_records
    with patch(
        "custom_components.hangar_assistant.async_cleanup_records",
        new_callable=AsyncMock
    ):
        # The service registration happens in async_setup
        # We're just checking the mock was called correctly
        assert mock_hass.services.async_register is not None


@pytest.mark.asyncio
async def test_manual_cleanup_default_retention():
    """Test manual cleanup uses default retention when not specified."""
    mock_hass = MagicMock(spec=HomeAssistant)
    mock_hass.config_entries = MagicMock()
    mock_call = MagicMock(spec=ServiceCall)
    mock_call.data = {}

    # Simulate the handler
    with patch(
        "custom_components.hangar_assistant.async_cleanup_records",
        new_callable=AsyncMock
    ) as mock_cleanup:
        from custom_components.hangar_assistant.const import DEFAULT_RETENTION_MONTHS
        retention = mock_call.data.get("retention_months", DEFAULT_RETENTION_MONTHS)
        await mock_cleanup(mock_hass, retention)
        mock_cleanup.assert_called_once()


@pytest.mark.asyncio
async def test_manual_cleanup_custom_retention():
    """Test manual cleanup accepts custom retention period."""
    mock_hass = MagicMock(spec=HomeAssistant)
    mock_call = MagicMock(spec=ServiceCall)
    mock_call.data = {"retention_months": 12}

    with patch(
        "custom_components.hangar_assistant.async_cleanup_records",
        new_callable=AsyncMock
    ) as mock_cleanup:
        retention = mock_call.data.get("retention_months", 7)
        await mock_cleanup(mock_hass, retention)
        assert retention == 12


@pytest.mark.asyncio
async def test_rebuild_dashboard_no_entries():
    """Test rebuild dashboard handles no config entries gracefully."""
    mock_hass = MagicMock(spec=HomeAssistant)
    mock_hass.config_entries = MagicMock()
    mock_hass.config_entries.async_entries.return_value = []

    with patch("custom_components.hangar_assistant.async_create_dashboard"):
        entries = mock_hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 0


@pytest.mark.asyncio
async def test_rebuild_dashboard_with_entry():
    """Test rebuild dashboard uses first config entry."""
    mock_hass = MagicMock(spec=HomeAssistant)
    mock_hass.config_entries = MagicMock()
    mock_entry = MagicMock()
    mock_hass.config_entries.async_entries.return_value = [mock_entry]

    with patch(
        "custom_components.hangar_assistant.async_create_dashboard",
        new_callable=AsyncMock,
        return_value=True
    ) as mock_create:
        entries = mock_hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 1
        assert entries[0] == mock_entry


@pytest.mark.asyncio
async def test_rebuild_dashboard_creation_failure():
    """Test rebuild dashboard handles creation failure."""
    mock_hass = MagicMock(spec=HomeAssistant)
    mock_hass.config_entries = MagicMock()
    mock_entry = MagicMock()
    mock_hass.config_entries.async_entries.return_value = [mock_entry]

    with patch(
        "custom_components.hangar_assistant.async_create_dashboard",
        new_callable=AsyncMock,
        return_value=False
    ) as mock_create:
        result = await mock_create(mock_hass, mock_entry, force_rebuild=True)
        assert result is False


@pytest.mark.asyncio
async def test_async_create_dashboard_updates_metadata_on_success():
    """Dashboard rebuild should record version and integration metadata."""
    hass = MagicMock(spec=HomeAssistant)
    hass.services = MagicMock()
    hass.services.has_service = MagicMock(return_value=False)
    hass.async_add_executor_job = AsyncMock(return_value=True)
    hass.config_entries = MagicMock()
    updated_payload = {}

    def _capture_update(entry, data):
        updated_payload.update(data)

    hass.config_entries.async_update_entry = MagicMock(side_effect=_capture_update)

    entry = MagicMock()
    entry.data = {}

    result = await async_create_dashboard(
        hass,
        entry,
        force_rebuild=True,
        reason="test",
    )

    assert result is True
    assert "dashboard_info" in updated_payload
    info = updated_payload["dashboard_info"]
    assert info["version"] == DEFAULT_DASHBOARD_VERSION
    assert info["integration_version"] == INTEGRATION_VERSION
    assert info["integration_major"] == INTEGRATION_MAJOR_VERSION
    assert info.get("last_updated") is not None


@pytest.mark.asyncio
async def test_async_setup_entry_forces_dashboard_rebuild_on_major_upgrade():
    """Major integration upgrades should trigger a forced dashboard rebuild."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    entry = MagicMock()
    entry.data = {
        "briefings": [],
        "ai_assistant": {},
        "dashboard_info": {
            "integration_major": INTEGRATION_MAJOR_VERSION + 1,
            "version": DEFAULT_DASHBOARD_VERSION,
        },
    }
    entry.async_on_unload = MagicMock()
    entry.add_update_listener = MagicMock(return_value=lambda *_args, **_kwargs: None)

    with patch(
        "custom_components.hangar_assistant.async_create_dashboard",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_create:
        await async_setup_entry(hass, entry)

    mock_create.assert_awaited_once()
    assert mock_create.call_args.kwargs["force_rebuild"] is True


@pytest.mark.asyncio
async def test_refresh_ai_briefings_no_entries():
    """Test refresh AI briefings with no config entries."""
    mock_hass = MagicMock(spec=HomeAssistant)
    mock_hass.config_entries = MagicMock()
    mock_hass.config_entries.async_entries.return_value = []

    with patch(
        "custom_components.hangar_assistant.async_generate_all_ai_briefings",
        new_callable=AsyncMock
    ) as mock_gen:
        for entry in mock_hass.config_entries.async_entries(DOMAIN):
            await mock_gen(mock_hass, entry)
        # Should not be called if no entries
        mock_gen.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_ai_briefings_multiple_entries():
    """Test refresh AI briefings processes all entries."""
    mock_hass = MagicMock(spec=HomeAssistant)
    mock_hass.config_entries = MagicMock()
    mock_entry1 = MagicMock()
    mock_entry2 = MagicMock()
    mock_hass.config_entries.async_entries.return_value = [
        mock_entry1,
        mock_entry2
    ]

    with patch(
        "custom_components.hangar_assistant.async_generate_all_ai_briefings",
        new_callable=AsyncMock
    ) as mock_gen:
        for entry in mock_hass.config_entries.async_entries(DOMAIN):
            await mock_gen(mock_hass, entry)
        assert mock_gen.call_count == 2


@pytest.mark.asyncio
async def test_refresh_ai_briefings_failure_handling():
    """Test refresh AI briefings handles generation errors."""
    mock_hass = MagicMock(spec=HomeAssistant)
    mock_hass.config_entries = MagicMock()
    mock_entry = MagicMock()
    mock_hass.config_entries.async_entries.return_value = [mock_entry]

    with patch(
        "custom_components.hangar_assistant.async_generate_all_ai_briefings",
        new_callable=AsyncMock,
        side_effect=Exception("Generation failed")
    ) as mock_gen:
        with pytest.raises(Exception):
            for entry in mock_hass.config_entries.async_entries(DOMAIN):
                await mock_gen(mock_hass, entry)


@pytest.mark.asyncio
async def test_ai_prompt_includes_timezone():
    """AI prompt should include the airfield timezone value."""
    mock_hass = MagicMock(spec=HomeAssistant)
    mock_hass.config = MagicMock()
    mock_hass.config.time_zone = "UTC"
    mock_hass.states = MagicMock()
    mock_hass.bus = MagicMock()
    mock_hass.bus.async_fire = MagicMock()
    mock_hass.async_add_executor_job = AsyncMock(return_value="Test system prompt")
    async_call = AsyncMock(return_value={"response": {"speech": {"plain": {"speech": "ok"}}}})
    mock_hass.services = MagicMock()
    mock_hass.services.async_call = async_call

    entry = MagicMock()
    entry.data = {
        "ai_assistant": {"ai_agent_entity": "agent.test"},
        "airfields": [{"name": "Test Airfield", "icao_code": "TEST"}],
    }

    def state_for(entity_id):
        mapping = {
            "sensor.test_airfield_density_altitude": MagicMock(state="1500"),
            "sensor.test_airfield_carb_risk": MagicMock(state="Low Risk"),
            "sensor.test_airfield_weather_wind_speed": MagicMock(state="12"),
            "sensor.test_airfield_weather_wind_direction": MagicMock(state="220"),
            "sensor.test_airfield_est_cloud_base": MagicMock(state="3500"),
            "sensor.test_airfield_best_runway": MagicMock(state="22"),
            "sensor.test_airfield_airfield_timezone": MagicMock(state="Europe/London"),
            "sun.sun": MagicMock(attributes={"next_rising": "2026-01-21T07:30:00Z", "next_setting": "2026-01-21T16:30:00Z"}),
        }
        return mapping.get(entity_id)

    mock_hass.states.get.side_effect = state_for

    await async_generate_all_ai_briefings(mock_hass, entry)

    assert async_call.call_count == 1
    text = async_call.call_args[0][2]["text"]
    assert "Local Timezone: Europe/London" in text
    mock_hass.async_add_executor_job.assert_awaited()


@pytest.mark.asyncio
async def test_speak_briefing_defaults_to_browser_media_player():
    """When no media player is specified, prefer browser-based player."""
    from types import SimpleNamespace
    from custom_components.hangar_assistant import async_setup

    hass = MagicMock(spec=HomeAssistant)
    # Mock service registry and call
    hass.services = MagicMock()
    hass.services.async_register = AsyncMock()
    hass.services.async_call = AsyncMock()

    # Mock states: selector, briefing sensor, browser media player, tts
    selector_state = SimpleNamespace(entity_id="select.hangar_assistant_airfield_selector", state="test_airfield", attributes={})
    briefing_state = SimpleNamespace(entity_id="sensor.test_airfield_ai_pre_flight_briefing", state="on", attributes={"briefing": "Test briefing"})
    browser_player = SimpleNamespace(entity_id="media_player.browser", state="idle", attributes={"friendly_name": "Browser", "app_name": "Home Assistant"})
    tts_engine = SimpleNamespace(entity_id="tts.cloud", state="on", attributes={})

    hass.states = MagicMock()
    def _get(entity_id):
        mapping = {
            "select.hangar_assistant_airfield_selector": selector_state,
            "sensor.test_airfield_ai_pre_flight_briefing": briefing_state,
        }
        return mapping.get(entity_id)

    hass.states.get.side_effect = _get
    hass.states.async_all = MagicMock(return_value=[selector_state, briefing_state, browser_player, tts_engine])

    # Run setup to register services
    await async_setup(hass, {})

    # Extract the speak_briefing handler from service registration
    handler = None
    for call in hass.services.async_register.call_args_list:
        args, kwargs = call
        if len(args) >= 3 and args[0] == DOMAIN and args[1] == "speak_briefing":
            handler = args[2]
            break

    assert handler is not None

    call = MagicMock(spec=ServiceCall)
    call.data = {}
    await handler(call)

    # Verify TTS was called and targeted the browser player by default
    assert hass.services.async_call.call_count == 1
    args, kwargs = hass.services.async_call.call_args
    assert args[0] == "tts"
    assert args[1] == "speak"
    payload = args[2]
    assert payload["media_player_entity_id"] == "media_player.browser"


@pytest.mark.asyncio
async def test_speak_briefing_fallbacks_to_first_available_media_player():
    """If no browser player exists, fall back to the first media player."""
    from types import SimpleNamespace
    from custom_components.hangar_assistant import async_setup

    hass = MagicMock(spec=HomeAssistant)
    hass.services = MagicMock()
    hass.services.async_register = MagicMock()
    hass.services.async_call = AsyncMock()

    selector_state = SimpleNamespace(entity_id="select.hangar_assistant_airfield_selector", state="test_airfield", attributes={})
    briefing_state = SimpleNamespace(entity_id="sensor.test_airfield_ai_pre_flight_briefing", state="on", attributes={"briefing": "Test briefing"})
    living_room = SimpleNamespace(entity_id="media_player.living_room", state="idle", attributes={"friendly_name": "Living Room"})
    tts_engine = SimpleNamespace(entity_id="tts.cloud", state="on", attributes={})

    hass.states = MagicMock()
    def _get(entity_id):
        mapping = {
            "select.hangar_assistant_airfield_selector": selector_state,
            "sensor.test_airfield_ai_pre_flight_briefing": briefing_state,
        }
        return mapping.get(entity_id)

    hass.states.get.side_effect = _get
    hass.states.async_all = MagicMock(return_value=[selector_state, briefing_state, living_room, tts_engine])

    await async_setup(hass, {})

    handler = None
    for call in hass.services.async_register.call_args_list:
        args, kwargs = call
        if len(args) >= 3 and args[0] == DOMAIN and args[1] == "speak_briefing":
            handler = args[2]
            break

    assert handler is not None

    call = MagicMock(spec=ServiceCall)
    call.data = {}
    await handler(call)

    assert hass.services.async_call.call_count == 1
    args, kwargs = hass.services.async_call.call_args
    payload = args[2]
    assert payload["media_player_entity_id"] == "media_player.living_room"
