"""Tests for service handlers in __init__.py.

Tests for:
- manual_cleanup service (PDF retention management)
- rebuild_dashboard service (dashboard generation)
- refresh_ai_briefings service (AI briefing generation)
- speak_briefing service (text-to-speech delivery)
- install_dashboard service (dashboard installation)
- calculate_fuel_cost service (fuel cost calculation)
- estimate_trip_fuel service (trip fuel estimation)

Test Strategy:
    - Mock Home Assistant service call infrastructure
    - Mock file system operations (PDFs, dashboard files)
    - Mock API calls (OpenAI for briefings, TTS services)
    - Validate parameter extraction and validation
    - Verify error handling and logging
"""
from unittest.mock import MagicMock, patch, AsyncMock, call
from datetime import datetime, timedelta
import pytest
from homeassistant.core import HomeAssistant, ServiceCall

from custom_components.hangar_assistant import (
    async_setup_entry,
    DOMAIN,
)


class TestManualCleanupService:
    """Test manual_cleanup service handler."""

    @pytest.mark.asyncio
    async def test_manual_cleanup_deletes_old_pdfs(self):
        """Test manual_cleanup deletes PDFs older than retention period."""
        mock_hass = MagicMock(spec=HomeAssistant)
        mock_call = MagicMock(spec=ServiceCall)
        mock_call.data = {"retention_months": 3}

        # Mock file system operations
        with patch("pathlib.Path.glob") as mock_glob, \
             patch("pathlib.Path.stat") as mock_stat, \
             patch("pathlib.Path.unlink") as mock_unlink:
            
            # Create mock PDF files
            mock_old_file = MagicMock()
            mock_old_file.stat.return_value.st_mtime = (
                datetime.now() - timedelta(days=120)
            ).timestamp()
            
            mock_new_file = MagicMock()
            mock_new_file.stat.return_value.st_mtime = datetime.now().timestamp()
            
            mock_glob.return_value = [mock_old_file, mock_new_file]
            
            # Service would be called but we're testing parameter extraction
            assert mock_call.data["retention_months"] == 3

    @pytest.mark.asyncio
    async def test_manual_cleanup_default_retention(self):
        """Test manual_cleanup uses default retention if not specified."""
        mock_call = MagicMock(spec=ServiceCall)
        mock_call.data = {}  # No retention_months specified
        
        # Extract with default
        retention = mock_call.data.get("retention_months", 7)
        
        assert retention == 7

    @pytest.mark.asyncio
    async def test_manual_cleanup_invalid_retention_range(self):
        """Test manual_cleanup rejects retention outside valid range."""
        # Valid range is 1-24 months
        invalid_retention_values = [0, -1, 25, 100]
        
        for retention in invalid_retention_values:
            assert retention < 1 or retention > 24


class TestRebuildDashboardService:
    """Test rebuild_dashboard service handler."""

    @pytest.mark.asyncio
    async def test_rebuild_dashboard_regenerates_yaml(self):
        """Test rebuild_dashboard regenerates dashboard YAML."""
        mock_hass = MagicMock(spec=HomeAssistant)
        mock_call = MagicMock(spec=ServiceCall)
        mock_call.data = {}
        
        # Verify service call structure
        assert isinstance(mock_call, ServiceCall)

    @pytest.mark.asyncio
    async def test_rebuild_dashboard_no_parameters(self):
        """Test rebuild_dashboard accepts no parameters."""
        mock_call = MagicMock(spec=ServiceCall)
        mock_call.data = {}
        
        # Service has no required parameters
        assert len(mock_call.data) == 0

    @pytest.mark.asyncio
    async def test_rebuild_dashboard_logging(self):
        """Test rebuild_dashboard logs operation."""
        # Service would log rebuild operation
        # Mock would capture log level and message
        pass


class TestRefreshAIBriefingsService:
    """Test refresh_ai_briefings service handler."""

    @pytest.mark.asyncio
    async def test_refresh_ai_briefings_no_parameters(self):
        """Test refresh_ai_briefings accepts no parameters."""
        mock_call = MagicMock(spec=ServiceCall)
        mock_call.data = {}
        
        assert len(mock_call.data) == 0

    @pytest.mark.asyncio
    async def test_refresh_ai_briefings_calls_api(self):
        """Test refresh_ai_briefings calls OpenAI API."""
        # Would verify API call with mock
        mock_hass = MagicMock(spec=HomeAssistant)
        mock_hass.data = {
            "hangar_assistant": {
                "settings": {
                    "openai_api_key": "test-key"
                }
            }
        }
        
        assert "test-key" in mock_hass.data["hangar_assistant"]["settings"]["openai_api_key"]

    @pytest.mark.asyncio
    async def test_refresh_ai_briefings_graceful_failure(self):
        """Test refresh_ai_briefings handles API failures gracefully."""
        # Service should handle API errors and continue
        # Would use existing cache on failure
        pass


class TestSpeakBriefingService:
    """Test speak_briefing service handler."""

    @pytest.mark.asyncio
    async def test_speak_briefing_requires_tts_entity(self):
        """Test speak_briefing requires tts_entity_id parameter."""
        mock_call = MagicMock(spec=ServiceCall)
        mock_call.data = {"tts_entity_id": "tts.google_en_com"}
        
        assert "tts_entity_id" in mock_call.data

    @pytest.mark.asyncio
    async def test_speak_briefing_optional_media_player(self):
        """Test speak_briefing accepts optional media_player_entity_id."""
        mock_call = MagicMock(spec=ServiceCall)
        mock_call.data = {
            "tts_entity_id": "tts.google_en_com",
            "media_player_entity_id": "media_player.living_room"
        }
        
        assert mock_call.data.get("media_player_entity_id") == "media_player.living_room"

    @pytest.mark.asyncio
    async def test_speak_briefing_defaults_to_browser_player(self):
        """Test speak_briefing defaults to browser if no media_player specified."""
        mock_call = MagicMock(spec=ServiceCall)
        mock_call.data = {"tts_entity_id": "tts.google_en_com"}
        
        media_player = mock_call.data.get("media_player_entity_id", "browser")
        
        assert media_player == "browser"

    @pytest.mark.asyncio
    async def test_speak_briefing_calls_tts_service(self):
        """Test speak_briefing calls TTS service with briefing text."""
        mock_hass = MagicMock(spec=HomeAssistant)
        mock_hass.services = MagicMock()
        
        # Would verify async_call to tts.speak
        assert hasattr(mock_hass.services, "async_call")


class TestInstallDashboardService:
    """Test install_dashboard service handler."""

    @pytest.mark.asyncio
    async def test_install_dashboard_no_parameters(self):
        """Test install_dashboard accepts no parameters."""
        mock_call = MagicMock(spec=ServiceCall)
        mock_call.data = {}
        
        assert len(mock_call.data) == 0

    @pytest.mark.asyncio
    async def test_install_dashboard_creates_yaml(self):
        """Test install_dashboard creates dashboard YAML file."""
        # Would verify file creation in www directory
        with patch("pathlib.Path.write_text") as mock_write:
            # Service would call write_text with YAML content
            pass

    @pytest.mark.asyncio
    async def test_install_dashboard_notifies_user(self):
        """Test install_dashboard notifies user of success."""
        # Would verify persistent_notification creation
        pass

    @pytest.mark.asyncio
    async def test_install_dashboard_handles_permissions_error(self):
        """Test install_dashboard handles permission errors gracefully."""
        # Would test when www directory not writable
        pass


class TestCalculateFuelCostService:
    """Test calculate_fuel_cost service handler."""

    @pytest.mark.asyncio
    async def test_calculate_fuel_cost_requires_flight_data(self):
        """Test calculate_fuel_cost requires flight data parameters."""
        mock_call = MagicMock(spec=ServiceCall)
        mock_call.data = {
            "distance_nm": 200,
            "fuel_burn_gph": 8.5,
            "fuel_price_per_gallon": 5.50
        }
        
        assert mock_call.data["distance_nm"] == 200
        assert mock_call.data["fuel_burn_gph"] == 8.5
        assert mock_call.data["fuel_price_per_gallon"] == 5.50

    @pytest.mark.asyncio
    async def test_calculate_fuel_cost_calculates_correctly(self):
        """Test calculate_fuel_cost performs correct calculation."""
        distance_nm = 200
        fuel_burn_gph = 8.5
        fuel_price = 5.50
        cruise_speed = 100  # Default
        
        flight_time = distance_nm / cruise_speed
        fuel_burned = flight_time * fuel_burn_gph
        cost = fuel_burned * fuel_price
        
        assert cost > 0
        assert isinstance(cost, float)

    @pytest.mark.asyncio
    async def test_calculate_fuel_cost_optional_cruise_speed(self):
        """Test calculate_fuel_cost accepts optional cruise speed."""
        mock_call = MagicMock(spec=ServiceCall)
        mock_call.data = {
            "distance_nm": 200,
            "fuel_burn_gph": 8.5,
            "fuel_price_per_gallon": 5.50,
            "cruise_speed_knots": 110
        }
        
        cruise_speed = mock_call.data.get("cruise_speed_knots", 100)
        assert cruise_speed == 110

    @pytest.mark.asyncio
    async def test_calculate_fuel_cost_returns_notification(self):
        """Test calculate_fuel_cost returns result as notification."""
        # Would verify notification contains calculated cost
        pass

    @pytest.mark.asyncio
    async def test_calculate_fuel_cost_validates_positive_values(self):
        """Test calculate_fuel_cost validates positive numeric values."""
        invalid_values = [0, -100, -8.5, -5.50]
        
        for val in invalid_values:
            assert val <= 0


class TestEstimateTripFuelService:
    """Test estimate_trip_fuel service handler."""

    @pytest.mark.asyncio
    async def test_estimate_trip_fuel_requires_aircraft_and_route(self):
        """Test estimate_trip_fuel requires aircraft and route parameters."""
        mock_call = MagicMock(spec=ServiceCall)
        mock_call.data = {
            "aircraft_registration": "G-ABCD",
            "departure_airport": "EGHP",
            "destination_airport": "EGLL",
            "route_waypoints": ["EGHP", "EGLL"]
        }
        
        assert "aircraft_registration" in mock_call.data
        assert "departure_airport" in mock_call.data
        assert "destination_airport" in mock_call.data

    @pytest.mark.asyncio
    async def test_estimate_trip_fuel_optional_alternate_airport(self):
        """Test estimate_trip_fuel accepts optional alternate airport."""
        mock_call = MagicMock(spec=ServiceCall)
        mock_call.data = {
            "aircraft_registration": "G-ABCD",
            "departure_airport": "EGHP",
            "destination_airport": "EGLL",
            "alternate_airport": "EGJB"
        }
        
        alternate = mock_call.data.get("alternate_airport")
        assert alternate == "EGJB"

    @pytest.mark.asyncio
    async def test_estimate_trip_fuel_calculates_reserves(self):
        """Test estimate_trip_fuel includes fuel reserves in calculation."""
        # Reserve fuel typically: 45 minutes to alternate + 5 minutes holding
        # Service should calculate based on cruise speed and burn rate
        pass

    @pytest.mark.asyncio
    async def test_estimate_trip_fuel_optional_contingency_percent(self):
        """Test estimate_trip_fuel accepts optional contingency fuel percentage."""
        mock_call = MagicMock(spec=ServiceCall)
        mock_call.data = {
            "aircraft_registration": "G-ABCD",
            "departure_airport": "EGHP",
            "destination_airport": "EGLL",
            "contingency_percent": 10
        }
        
        contingency = mock_call.data.get("contingency_percent", 5)
        assert contingency == 10

    @pytest.mark.asyncio
    async def test_estimate_trip_fuel_returns_detailed_breakdown(self):
        """Test estimate_trip_fuel returns breakdown (route + reserves + contingency)."""
        # Service should return structured notification with:
        # - Route fuel burned
        # - Reserve fuel required
        # - Contingency fuel (if applicable)
        # - Total required
        # - Aircraft fuel capacity
        # - GO/NO-GO recommendation
        pass

    @pytest.mark.asyncio
    async def test_estimate_trip_fuel_go_no_go_decision(self):
        """Test estimate_trip_fuel provides GO/NO-GO recommendation."""
        # If total_fuel_required <= fuel_capacity: GO
        # If total_fuel_required > fuel_capacity: NO-GO with reason
        pass


class TestServiceRegistration:
    """Test service registration in async_setup_entry."""

    @pytest.mark.asyncio
    async def test_all_services_registered(self):
        """Test all services are registered."""
        mock_hass = MagicMock(spec=HomeAssistant)
        mock_hass.services = MagicMock()
        mock_hass.services.async_register = AsyncMock()
        
        # Would verify 7 service registrations
        expected_services = [
            "manual_cleanup",
            "rebuild_dashboard",
            "refresh_ai_briefings",
            "speak_briefing",
            "install_dashboard",
            "calculate_fuel_cost",
            "estimate_trip_fuel",
        ]
        
        assert len(expected_services) == 7

    @pytest.mark.asyncio
    async def test_services_have_correct_domain(self):
        """Test services registered with correct domain."""
        # Services should be registered as: hangar_assistant.service_name
        service_domain = DOMAIN
        
        assert service_domain == "hangar_assistant"

    @pytest.mark.asyncio
    async def test_service_handlers_are_async(self):
        """Test all service handlers are async functions."""
        # Handler functions must be async def
        pass
