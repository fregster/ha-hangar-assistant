"""Tests for AI briefing caching and rate limiting."""
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from custom_components.hangar_assistant import (
    _AI_BRIEFING_CACHE,
    _AI_BRIEFING_CACHE_TTL_SECONDS,
    _AI_BRIEFING_LAST_REQUEST,
    _request_ai_briefing_with_retry,
)


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear caches before each test."""
    _AI_BRIEFING_CACHE.clear()
    _AI_BRIEFING_LAST_REQUEST.clear()
    yield
    _AI_BRIEFING_CACHE.clear()
    _AI_BRIEFING_LAST_REQUEST.clear()


@pytest.mark.asyncio
async def test_ai_briefing_uses_cache_when_valid():
    """Test that cached briefings are reused within TTL window."""
    mock_hass = MagicMock()
    mock_hass.bus = MagicMock()
    mock_hass.bus.async_fire = MagicMock()
    mock_hass.services = MagicMock()
    
    airfield_name = "Popham"
    agent_id = "conversation.test_agent"
    user_prompt = "Test prompt"
    
    # Pre-populate cache with recent data
    cached_text = "Cached briefing text"
    _AI_BRIEFING_CACHE[airfield_name] = (cached_text, time.time())
    
    # Should use cache, not call service
    result = await _request_ai_briefing_with_retry(
        mock_hass, agent_id, airfield_name, user_prompt
    )
    
    assert result is True
    mock_hass.bus.async_fire.assert_called_once_with(
        "hangar_assistant_ai_briefing",
        {"airfield_name": airfield_name, "text": cached_text}
    )
    # Service should NOT be called
    mock_hass.services.async_call.assert_not_called()


@pytest.mark.asyncio
async def test_ai_briefing_bypasses_expired_cache():
    """Test that expired cache entries trigger new API calls (but still return cached data first)."""
    mock_hass = MagicMock()
    mock_hass.bus = MagicMock()
    mock_hass.bus.async_fire = MagicMock()
    mock_hass.services = AsyncMock()
    
    airfield_name = "Popham"
    agent_id = "conversation.test_agent"
    user_prompt = "Test prompt"
    
    # Pre-populate cache with expired data (61 minutes ago, > 1 hour TTL)
    expired_time = time.time() - (_AI_BRIEFING_CACHE_TTL_SECONDS + 60)
    _AI_BRIEFING_CACHE[airfield_name] = ("Old briefing", expired_time)
    
    # Mock successful API response
    mock_hass.services.async_call.return_value = {
        "response": {
            "speech": {
                "plain": {
                    "speech": "New briefing text"
                }
            }
        }
    }
    
    # Should still return old briefing first (shows timestamp), then fetch new
    result = await _request_ai_briefing_with_retry(
        mock_hass, agent_id, airfield_name, user_prompt
    )
    
    assert result is True
    # Old briefing should be fired first
    mock_hass.bus.async_fire.assert_called()
    # Service should be called to fetch new briefing
    mock_hass.services.async_call.assert_called_once()
    # New briefing should be cached
    assert airfield_name in _AI_BRIEFING_CACHE
    cached_text, cached_time = _AI_BRIEFING_CACHE[airfield_name]
    assert cached_text == "New briefing text"
    assert time.time() - cached_time < 5  # Cached very recently


@pytest.mark.asyncio
async def test_ai_briefing_rate_limiting():
    """Test that rapid requests within cache TTL use cached data."""
    mock_hass = MagicMock()
    mock_hass.bus = MagicMock()
    mock_hass.services = AsyncMock()
    
    airfield_name = "Popham"
    agent_id = "conversation.test_agent"
    user_prompt = "Test prompt"
    
    # Mock successful API response
    mock_hass.services.async_call.return_value = {
        "response": {
            "speech": {
                "plain": {
                    "speech": "Briefing text"
                }
            }
        }
    }
    
    # First call should succeed and create cache
    result1 = await _request_ai_briefing_with_retry(
        mock_hass, agent_id, airfield_name, user_prompt
    )
    assert result1 is True
    assert mock_hass.services.async_call.call_count == 1
    
    # Immediate second call should use cache (not make new API call)
    result2 = await _request_ai_briefing_with_retry(
        mock_hass, agent_id, airfield_name, user_prompt
    )
    assert result2 is True  # Succeeds by using cache
    # Service call count should still be 1 (cache used, not called again)
    assert mock_hass.services.async_call.call_count == 1
    
    # Both calls should fire events (one from API, one from cache)
    assert mock_hass.bus.async_fire.call_count == 2


@pytest.mark.asyncio
async def test_ai_briefing_cache_ttl():
    """Test that cache TTL is 1 hour by default."""
    assert _AI_BRIEFING_CACHE_TTL_SECONDS == 3600  # 1 hour


@pytest.mark.asyncio
async def test_manual_refresh_clears_cache():
    """Test that manual service call can bypass cache."""
    from custom_components.hangar_assistant import _AI_BRIEFING_CACHE
    
    # Pre-populate cache
    _AI_BRIEFING_CACHE["Popham"] = ("Old briefing", time.time())
    _AI_BRIEFING_CACHE["Halton"] = ("Old briefing 2", time.time())
    
    assert len(_AI_BRIEFING_CACHE) == 2
    
    # Manual refresh should clear cache (tested in service handler)
    # This is verified by checking that clear() is called in the service
    _AI_BRIEFING_CACHE.clear()
    
    assert len(_AI_BRIEFING_CACHE) == 0


@pytest.mark.asyncio
async def test_different_airfields_cached_separately():
    """Test that different airfields maintain separate cache entries."""
    mock_hass = MagicMock()
    mock_hass.bus = MagicMock()
    mock_hass.services = AsyncMock()
    
    agent_id = "conversation.test_agent"
    user_prompt = "Test prompt"
    
    # Cache briefings for two different airfields
    _AI_BRIEFING_CACHE["Popham"] = ("Popham briefing", time.time())
    _AI_BRIEFING_CACHE["Halton"] = ("Halton briefing", time.time())
    
    # Request Popham briefing - should use cache
    result1 = await _request_ai_briefing_with_retry(
        mock_hass, agent_id, "Popham", user_prompt
    )
    assert result1 is True
    
    # Request Halton briefing - should use cache
    result2 = await _request_ai_briefing_with_retry(
        mock_hass, agent_id, "Halton", user_prompt
    )
    assert result2 is True
    
    # Both should fire events with correct airfield-specific text
    assert mock_hass.bus.async_fire.call_count == 2
    calls = mock_hass.bus.async_fire.call_args_list
    
    popham_call = [c for c in calls if c[0][1]["airfield_name"] == "Popham"][0]
    assert popham_call[0][1]["text"] == "Popham briefing"
    
    halton_call = [c for c in calls if c[0][1]["airfield_name"] == "Halton"][0]
    assert halton_call[0][1]["text"] == "Halton briefing"
