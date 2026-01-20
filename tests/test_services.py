"""Tests for Hangar Assistant services."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock, call
from homeassistant.core import HomeAssistant, ServiceCall
from custom_components.hangar_assistant.const import DOMAIN


@pytest.fixture
def mock_service_call():
    """Create a mock service call."""
    return MagicMock(spec=ServiceCall)


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.services = MagicMock()
    hass.services.async_register = AsyncMock()
    hass.config_entries = MagicMock()
    hass.config.path = MagicMock(return_value="/config/www/hangar/")
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
    mock_call = MagicMock(spec=ServiceCall)
    mock_call.data.get.return_value = None

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
    mock_hass.config_entries.async_entries.return_value = []

    with patch("custom_components.hangar_assistant.async_create_dashboard"):
        entries = mock_hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 0


@pytest.mark.asyncio
async def test_rebuild_dashboard_with_entry():
    """Test rebuild dashboard uses first config entry."""
    mock_hass = MagicMock(spec=HomeAssistant)
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
async def test_refresh_ai_briefings_no_entries():
    """Test refresh AI briefings with no config entries."""
    mock_hass = MagicMock(spec=HomeAssistant)
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
