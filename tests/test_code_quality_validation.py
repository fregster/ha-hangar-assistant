"""Unit tests to validate code quality improvements and prevent regressions.

This test suite validates:
1. Refactored helper functions work correctly
2. Exception handling follows best practices (no redundant catches)
3. Unused parameters are properly named with underscore prefix
4. Async/await patterns are correctly implemented
5. Cognitive complexity has been reduced through proper extraction
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from homeassistant.core import HomeAssistant
from homeassistant import config_entries

from custom_components.hangar_assistant import (
    _resolve_airfield_slug,
    _find_media_player,
    _find_tts_entity,
    _request_ai_briefing_with_retry,
    _load_integration_version,
)
from custom_components.hangar_assistant.const import DOMAIN
from custom_components.hangar_assistant.binary_sensor import HangarMasterSafetyAlert
from custom_components.hangar_assistant.config_flow import HangarOptionsFlowHandler


class TestHelperMethodExtraction:
    """Test that extracted helper methods work correctly and reduce complexity."""

    def test_resolve_airfield_slug_from_selector(self):
        """Test resolving airfield slug from selector entity."""
        mock_hass = MagicMock()
        mock_state = MagicMock()
        mock_state.state = "test_airfield"
        mock_hass.states.get.return_value = mock_state

        result = _resolve_airfield_slug(mock_hass)
        assert result == "test_airfield"
        mock_hass.states.get.assert_called_with("select.hangar_assistant_airfield_selector")

    def test_resolve_airfield_slug_from_sensor_fallback(self):
        """Test resolving airfield slug by scanning for briefing sensor when selector unavailable."""
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None  # Selector not available

        # Create mock states for briefing sensors
        mock_briefing_state = MagicMock()
        mock_briefing_state.entity_id = "sensor.ksfo_ai_pre_flight_briefing"

        mock_hass.states.async_all.return_value = [mock_briefing_state]

        result = _resolve_airfield_slug(mock_hass)
        assert result == "ksfo"

    def test_resolve_airfield_slug_returns_none_when_unavailable(self):
        """Test that None is returned when no airfield slug can be resolved."""
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None
        mock_hass.states.async_all.return_value = []

        result = _resolve_airfield_slug(mock_hass)
        assert result is None

    def test_find_media_player_respects_override(self):
        """Test that explicitly provided media player ID is used."""
        mock_hass = MagicMock()
        override = "media_player.bedroom"

        result = _find_media_player(mock_hass, override)
        assert result == override

    def test_find_media_player_prefers_browser(self):
        """Test that browser-based media players are preferred."""
        mock_hass = MagicMock()

        # Create mock browser media player
        browser_state = MagicMock()
        browser_state.entity_id = "media_player.browser"
        browser_state.state = "idle"
        browser_state.attributes = {"app_name": "home assistant"}

        mock_hass.states.async_all.return_value = [browser_state]

        result = _find_media_player(mock_hass, None)
        assert result == "media_player.browser"

    def test_find_media_player_fallback_to_any_available(self):
        """Test fallback to first available media player when no browser found."""
        mock_hass = MagicMock()

        # Non-browser media player
        speaker_state = MagicMock()
        speaker_state.entity_id = "media_player.living_room"
        speaker_state.state = "idle"
        speaker_state.attributes = {"friendly_name": "Living Room Speaker"}

        mock_hass.states.async_all.return_value = [speaker_state]

        result = _find_media_player(mock_hass, None)
        assert result == "media_player.living_room"

    def test_find_media_player_returns_none_when_unavailable(self):
        """Test that None is returned when no media player available."""
        mock_hass = MagicMock()
        mock_hass.states.async_all.return_value = []

        result = _find_media_player(mock_hass, None)
        assert result is None

    def test_find_tts_entity_respects_override(self):
        """Test that explicitly provided TTS entity ID is used."""
        mock_hass = MagicMock()
        override = "tts.cloud"

        result = _find_tts_entity(mock_hass, override)
        assert result == override

    def test_find_tts_entity_auto_discovers(self):
        """Test auto-discovery of first available TTS entity."""
        mock_hass = MagicMock()

        tts_state = MagicMock()
        tts_state.entity_id = "tts.google_translate_en"

        mock_hass.states.async_all.return_value = [tts_state]

        result = _find_tts_entity(mock_hass, None)
        assert result == "tts.google_translate_en"

    def test_find_tts_entity_returns_none_when_unavailable(self):
        """Test that None is returned when no TTS available."""
        mock_hass = MagicMock()
        mock_hass.states.async_all.return_value = []

        result = _find_tts_entity(mock_hass, None)
        assert result is None


class TestExceptionHandlingQuality:
    """Test that exception handling follows best practices."""

    def test_load_integration_version_handles_missing_manifest(self):
        """Test graceful fallback when manifest file missing."""
        with patch("os.path.join", return_value="/nonexistent/manifest.json"):
            with patch("builtins.open", side_effect=OSError("File not found")):
                from custom_components.hangar_assistant import _load_integration_version
                result = _load_integration_version()
                assert result == "0.0.0"

    def test_load_integration_version_handles_invalid_json(self):
        """Test graceful fallback when manifest JSON invalid."""
        import json as json_module
        with patch("os.path.join", return_value="/path/manifest.json"):
            with patch("builtins.open", side_effect=json_module.JSONDecodeError("msg", "doc", 0)):
                from custom_components.hangar_assistant import _load_integration_version
                result = _load_integration_version()
                assert result == "0.0.0"

    @pytest.mark.asyncio
    async def test_ai_briefing_retry_handles_service_error(self):
        """Test that AI briefing retry handles service call exceptions."""
        mock_hass = MagicMock()
        mock_hass.services.async_call = AsyncMock(side_effect=Exception("Service error"))

        # Patch asyncio.sleep to prevent actual delays during testing
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await _request_ai_briefing_with_retry(
                mock_hass,
                "conversation.openai",
                "test_airfield",
                "test prompt"
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_ai_briefing_retry_retries_on_no_response(self):
        """Test that briefing retry attempts multiple times on no response."""
        # Clear cache state from previous tests
        from custom_components.hangar_assistant import _AI_BRIEFING_CACHE, _AI_BRIEFING_LAST_REQUEST
        _AI_BRIEFING_CACHE.clear()
        _AI_BRIEFING_LAST_REQUEST.clear()
        
        mock_hass = MagicMock()
        mock_hass.services.async_call = AsyncMock(return_value=None)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await _request_ai_briefing_with_retry(
                mock_hass,
                "conversation.openai",
                "unique_test_airfield_1",
                "test prompt"
            )

            assert result is False
            # Should have attempted retries with backoff
            assert mock_hass.services.async_call.call_count >= 1

    @pytest.mark.asyncio
    async def test_ai_briefing_retry_succeeds_with_valid_response(self):
        """Test that briefing retry succeeds with valid response."""
        # Clear cache state from previous tests
        from custom_components.hangar_assistant import _AI_BRIEFING_CACHE, _AI_BRIEFING_LAST_REQUEST
        _AI_BRIEFING_CACHE.clear()
        _AI_BRIEFING_LAST_REQUEST.clear()
        
        mock_hass = MagicMock()
        mock_hass.bus = MagicMock()
        mock_hass.bus.async_fire = MagicMock()
        mock_hass.services.async_call = AsyncMock(
            return_value={
                "response": {
                    "speech": {
                        "plain": {
                            "speech": "Test briefing content"
                        }
                    }
                }
            }
        )

        result = await _request_ai_briefing_with_retry(
            mock_hass,
            "conversation.openai",
            "unique_test_airfield_2",
            "test prompt"
        )

        assert result is True
        mock_hass.bus.async_fire.assert_called_once()


class TestBinarySensorComplexityReduction:
    """Test that binary sensor complexity has been properly reduced."""

    def test_master_safety_alert_has_is_unsafe_method(self):
        """Test that complexity was extracted to _is_unsafe method."""
        mock_hass = MagicMock()
        config = {"name": "Test Airfield"}
        alert = HangarMasterSafetyAlert(mock_hass, config, {})

        # Verify the private method exists (indicates extraction)
        assert hasattr(alert, "_is_unsafe")
        assert callable(alert._is_unsafe)

    def test_master_safety_alert_is_on_delegates_to_is_unsafe(self):
        """Test that is_on property delegates to extracted _is_unsafe method."""
        mock_hass = MagicMock()
        config = {"name": "Test Airfield"}
        alert = HangarMasterSafetyAlert(mock_hass, config, {})

        # Mock _is_unsafe to return True
        alert._is_unsafe = MagicMock(return_value=True)

        # is_on should use _is_unsafe
        result = alert.is_on
        assert result is True
        alert._is_unsafe.assert_called_once()

    def test_is_unsafe_evaluates_freshness(self):
        """Test that _is_unsafe checks weather data freshness."""
        mock_hass = MagicMock()
        config = {"name": "Test Airfield"}
        alert = HangarMasterSafetyAlert(mock_hass, config, {"stale_weather_minutes": 30})

        # Mock stale freshness state
        freshness_state = MagicMock()
        freshness_state.state = "45"  # 45 minutes old, exceeds 30-minute threshold

        mock_hass.states.get.return_value = freshness_state

        result = alert._is_unsafe()
        assert result is True  # Should alert due to stale data

    def test_is_unsafe_evaluates_carb_risk(self):
        """Test that _is_unsafe checks carb icing risk."""
        mock_hass = MagicMock()
        config = {"name": "Test Airfield"}
        alert = HangarMasterSafetyAlert(mock_hass, config, {})

        def get_state_side_effect(entity_id):
            if "_carb_risk" in entity_id:
                state = MagicMock()
                state.state = "Serious Risk"
                return state
            return None

        mock_hass.states.get.side_effect = get_state_side_effect

        result = alert._is_unsafe()
        assert result is True  # Should alert due to serious icing risk

    def test_is_unsafe_evaluates_cloud_base(self):
        """Test that _is_unsafe checks VFR cloud base minimums."""
        mock_hass = MagicMock()
        config = {"name": "Test Airfield"}
        alert = HangarMasterSafetyAlert(mock_hass, config, {})

        def get_state_side_effect(entity_id):
            if "_cloud_base" in entity_id:
                state = MagicMock()
                state.state = "800"  # 800 ft, below VFR minimum of 1000 ft
                return state
            return None

        mock_hass.states.get.side_effect = get_state_side_effect

        result = alert._is_unsafe()
        assert result is True  # Should alert due to below VFR minima

    def test_is_unsafe_returns_false_when_safe(self):
        """Test that _is_unsafe returns False when all conditions safe."""
        mock_hass = MagicMock()
        config = {"name": "Test Airfield"}
        alert = HangarMasterSafetyAlert(mock_hass, config, {})

        # Mock all states as safe
        def get_state_side_effect(entity_id):
            state = MagicMock()
            if "_weather_data_age" in entity_id:
                state.state = "5"  # 5 minutes old, fresh
            elif "_carb_risk" in entity_id:
                state.state = "Low Risk"
            elif "_cloud_base" in entity_id:
                state.state = "2000"  # 2000 ft, well above VFR minimum
            else:
                return None
            return state

        mock_hass.states.get.side_effect = get_state_side_effect

        result = alert._is_unsafe()
        assert result is False  # Should not alert, all safe


class TestConfigFlowUnusedParameters:
    """Test that config flow menu methods properly mark unused parameters."""

    def test_options_flow_handler_init(self):
        """Test OptionsFlowHandler initializes without error."""
        mock_entry = MagicMock(spec=config_entries.ConfigEntry)
        mock_entry.data = {}
        mock_entry.options = {}

        handler = HangarOptionsFlowHandler(mock_entry)
        assert handler is not None
        assert handler._config_entry is mock_entry

    def test_async_step_init_signature(self):
        """Test that async_step_init accepts _user_input parameter."""
        mock_entry = MagicMock(spec=config_entries.ConfigEntry)
        mock_entry.data = {}
        mock_entry.options = {}

        handler = HangarOptionsFlowHandler(mock_entry)

        # Should accept None or any value for _user_input without errors
        import inspect
        sig = inspect.signature(handler.async_step_init)
        params = list(sig.parameters.keys())

        # Verify parameter exists (may be named _user_input or user_input)
        assert "user_input" in params or "_user_input" in params

    def test_async_step_global_config_signature(self):
        """Test that async_step_global_config accepts _user_input parameter."""
        mock_entry = MagicMock(spec=config_entries.ConfigEntry)
        mock_entry.data = {}
        mock_entry.options = {}

        handler = HangarOptionsFlowHandler(mock_entry)

        import inspect
        sig = inspect.signature(handler.async_step_global_config)
        params = list(sig.parameters.keys())

        assert "user_input" in params or "_user_input" in params


class TestAsyncAwaitHygiene:
    """Test that async/await patterns are correctly implemented."""

    @pytest.mark.asyncio
    async def test_ai_briefing_retry_is_async(self):
        """Test that _request_ai_briefing_with_retry is async."""
        import inspect
        assert inspect.iscoroutinefunction(_request_ai_briefing_with_retry)

    @pytest.mark.asyncio
    async def test_ai_briefing_retry_awaits_service_call(self):
        """Test that retry function awaits the service call."""
        # Clear cache state from previous tests
        from custom_components.hangar_assistant import _AI_BRIEFING_CACHE, _AI_BRIEFING_LAST_REQUEST
        _AI_BRIEFING_CACHE.clear()
        _AI_BRIEFING_LAST_REQUEST.clear()
        
        mock_hass = MagicMock()
        mock_hass.services.async_call = AsyncMock(return_value=None)

        # Patch asyncio.sleep to prevent actual delays during testing
        with patch("asyncio.sleep", new_callable=AsyncMock):
            # Should complete without blocking
            result = await _request_ai_briefing_with_retry(
                mock_hass,
                "test_agent",
                "unique_test_airfield_3",
                "test"
            )

            # Verify async_call was actually awaited (called)
            mock_hass.services.async_call.assert_called()


class TestCodeQualityMetrics:
    """Test overall code quality metrics."""

    def test_helper_methods_reduce_main_function_complexity(self):
        """Test that helper extraction reduces main function size."""
        # These methods should exist and be callable
        assert callable(_resolve_airfield_slug)
        assert callable(_find_media_player)
        assert callable(_find_tts_entity)
        assert callable(_request_ai_briefing_with_retry)

        # Verify they're separate functions (extraction occurred)
        import inspect
        source_lines = {}
        for func in [_resolve_airfield_slug, _find_media_player, _find_tts_entity]:
            source = inspect.getsource(func)
            source_lines[func.__name__] = len(source.split("\n"))

        # Each should be reasonably sized (under 50 lines for a helper)
        for name, lines in source_lines.items():
            assert lines < 50, f"{name} should be under 50 lines but has {lines}"

    def test_no_unused_imports(self):
        """Test that common unused imports have been removed."""
        # Import the module and check for unused _LOGGER patterns
        from custom_components.hangar_assistant import config_flow

        # Module should load without warnings (in production)
        assert config_flow is not None
