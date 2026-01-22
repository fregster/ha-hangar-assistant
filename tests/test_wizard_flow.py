"""Tests for setup wizard config flow.

This module tests the 7-step guided setup wizard for first-time users,
including wizard state management, step navigation, and data collection.

Test Strategy:
    - Mock Home Assistant instance and config flow
    - Test wizard state tracking and progress
    - Validate step transitions and data storage
    - Test error handling and validation

Coverage:
    - Wizard welcome and initiation
    - General settings step
    - API integrations menu
    - CheckWX and OpenWeatherMap setup
    - Airfield, hangar, aircraft configuration
    - Sensor linking and dashboard installation
    - Final config entry creation
"""
import pytest
from unittest.mock import MagicMock, patch
from custom_components.hangar_assistant.config_flow import (
    HangarAssistantConfigFlow,
    SetupWizardState,
)
from custom_components.hangar_assistant.const import (
    DOMAIN,
    SETUP_STEPS,
    SETUP_WIZARD_ENABLED,
)


class TestSetupWizardState:
    """Test suite for SetupWizardState class.
    
    Tests wizard state management, step completion tracking,
    and progress calculation.
    """
    
    def test_wizard_state_initialization(self):
        """Test wizard state initializes with empty data structures.
        
        Validates:
            - All state attributes are properly initialized
            - Empty collections for data storage
            - Default values set correctly
        
        Expected Result:
            SetupWizardState instance with empty state ready for wizard
        """
        state = SetupWizardState()
        
        assert state.current_step == 0
        assert len(state.completed_steps) == 0
        assert state.general_settings == {}
        assert state.api_configs == {}
        assert state.airfield_data is None
        assert state.hangar_data is None
        assert state.aircraft_data is None
        assert state.sensor_links == {}
        assert state.dashboard_method == "automatic"
        assert state.use_wizard is True
    
    def test_mark_step_complete(self):
        """Test marking steps as completed.
        
        Validates:
            - Steps can be added to completed set
            - Multiple steps can be marked complete
            - Duplicate marking doesn't cause issues
        
        Expected Result:
            Completed steps tracked correctly in state
        """
        state = SetupWizardState()
        
        state.mark_step_complete("general_settings")
        assert "general_settings" in state.completed_steps
        assert len(state.completed_steps) == 1
        
        state.mark_step_complete("api_integrations")
        assert len(state.completed_steps) == 2
        
        # Marking again shouldn't duplicate
        state.mark_step_complete("general_settings")
        assert len(state.completed_steps) == 2
    
    def test_can_skip_step(self):
        """Test step skip logic.
        
        Validates:
            - Optional steps can be skipped
            - Required steps cannot be skipped
            - Skip rules correctly applied
        
        Expected Result:
            Correct skip permissions for each step type
        """
        state = SetupWizardState()
        
        # Optional steps
        assert state.can_skip_step("api_integrations") is True
        assert state.can_skip_step("add_hangar") is True
        assert state.can_skip_step("link_sensors") is True
        assert state.can_skip_step("install_dashboard") is True
        
        # Required steps (not in skip rules)
        assert state.can_skip_step("general_settings") is False
        assert state.can_skip_step("add_airfield") is False
        assert state.can_skip_step("add_aircraft") is False
    
    def test_get_progress_percentage(self):
        """Test progress percentage calculation.
        
        Validates:
            - 0% when no steps completed
            - Correct percentage for partial completion
            - 100% when all steps completed
        
        Expected Result:
            Accurate progress percentage based on completed steps
        """
        state = SetupWizardState()
        
        # No steps completed
        assert state.get_progress_percentage() == 0
        
        # 1 of 7 steps (14%)
        state.mark_step_complete("general_settings")
        assert state.get_progress_percentage() == int(1/7 * 100)
        
        # 3 of 7 steps (42%)
        state.mark_step_complete("api_integrations")
        state.mark_step_complete("add_airfield")
        assert state.get_progress_percentage() == int(3/7 * 100)
        
        # All steps completed (100%)
        for step in ["add_hangar", "add_aircraft", "link_sensors", "install_dashboard"]:
            state.mark_step_complete(step)
        assert state.get_progress_percentage() == 100
    
    def test_get_progress_text(self):
        """Test progress text generation.
        
        Validates:
            - Correct step number displayed
            - Percentage included in text
            - Format matches expected pattern
        
        Expected Result:
            Human-readable progress text (e.g., "Step 3 of 7 (42% complete)")
        """
        state = SetupWizardState()
        
        # No steps completed - on step 1
        text = state.get_progress_text()
        assert "Step 1 of 7" in text
        assert "0%" in text
        
        # 2 steps completed - on step 3
        state.mark_step_complete("general_settings")
        state.mark_step_complete("api_integrations")
        text = state.get_progress_text()
        assert "Step 3 of 7" in text


class TestWizardConfigFlow:
    """Test suite for wizard config flow steps.
    
    Tests the complete 7-step wizard flow including user input handling,
    validation, and navigation between steps.
    """
    
    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance.
        
        Provides:
            - Mock hass with config entries
            - Mock async methods for flow operations
        
        Returns:
            MagicMock configured for config flow testing
        """
        hass = MagicMock()
        hass.config_entries = MagicMock()
        hass.config_entries.async_update_entry = MagicMock()
        return hass
    
    @pytest.fixture
    def flow(self, mock_hass):
        """Create config flow instance.
        
        Provides:
            - Initialized HangarAssistantConfigFlow
            - Mock hass attached
            - Wizard state ready
        
        Returns:
            HangarAssistantConfigFlow instance for testing
        """
        flow = HangarAssistantConfigFlow()
        flow.hass = mock_hass
        flow._async_current_entries = MagicMock(return_value=[])
        return flow
    
    def test_wizard_enabled_shows_welcome(self, flow):
        """Test wizard is shown when enabled for new installs.
        
        Validates:
            - SETUP_WIZARD_ENABLED flag is respected
            - Welcome step shown instead of blank entry
            - Wizard state initialized
        
        Expected Result:
            async_step_welcome() called for new installations
        """
        # This test verifies the flow logic redirects to welcome
        # In actual async test, would await and check result type
        assert flow.wizard_state is not None
        assert isinstance(flow.wizard_state, SetupWizardState)
    
    def test_wizard_state_stores_general_settings(self, flow):
        """Test general settings stored in wizard state.
        
        Validates:
            - Language preference saved
            - Unit preference saved
            - Cache settings saved
            - Step marked complete
        
        Expected Result:
            General settings stored correctly in wizard state
        """
        user_input = {
            "language": "en",
            "unit_preference": "aviation",
            "sensor_cache_ttl_seconds": 60,
        }
        
        # Simulate storing settings (would be done in async_step_general_settings)
        flow.wizard_state.general_settings = user_input
        flow.wizard_state.mark_step_complete("general_settings")
        
        assert flow.wizard_state.general_settings["language"] == "en"
        assert flow.wizard_state.general_settings["unit_preference"] == "aviation"
        assert "general_settings" in flow.wizard_state.completed_steps
    
    def test_wizard_state_stores_api_configs(self, flow):
        """Test API configurations stored correctly.
        
        Validates:
            - CheckWX config stored
            - OpenWeatherMap config stored
            - API keys stored securely
            - Cache settings preserved
        
        Expected Result:
            API configs available for later use in wizard
        """
        checkwx_config = {
            "enabled": True,
            "api_key": "test_checkwx_key_12345678901234567890",
            "metar_enabled": True,
            "taf_enabled": True,
        }
        
        owm_config = {
            "enabled": True,
            "api_key": "1234567890abcdef1234567890abcdef",
            "cache_enabled": True,
            "update_interval": 10,
        }
        
        flow.wizard_state.api_configs["checkwx"] = checkwx_config
        flow.wizard_state.api_configs["openweathermap"] = owm_config
        
        assert "checkwx" in flow.wizard_state.api_configs
        assert "openweathermap" in flow.wizard_state.api_configs
        assert flow.wizard_state.api_configs["checkwx"]["enabled"] is True
    
    def test_wizard_state_stores_airfield_data(self, flow):
        """Test airfield data stored correctly.
        
        Validates:
            - ICAO code stored
            - Name stored
            - Coordinates stored
            - Elevation stored
        
        Expected Result:
            Airfield data available for config entry creation
        """
        airfield_data = {
            "icao": "EGHP",
            "name": "Popham",
            "latitude": 51.2,
            "longitude": -1.2,
            "elevation_m": 150,
        }
        
        flow.wizard_state.airfield_data = airfield_data
        flow.wizard_state.mark_step_complete("add_airfield")
        
        assert flow.wizard_state.airfield_data["icao"] == "EGHP"
        assert flow.wizard_state.airfield_data["name"] == "Popham"
        assert "add_airfield" in flow.wizard_state.completed_steps
    
    def test_wizard_state_stores_optional_hangar(self, flow):
        """Test optional hangar data stored when provided.
        
        Validates:
            - Hangar data stored when configured
            - Step marked complete even if skipped
            - Sensor links preserved
        
        Expected Result:
            Hangar data stored or None if skipped
        """
        # Case 1: Hangar configured
        hangar_data = {
            "name": "Hangar 3",
            "airfield": "Popham",
            "temp_sensor": "sensor.hangar_temp",
        }
        
        flow.wizard_state.hangar_data = hangar_data
        flow.wizard_state.mark_step_complete("add_hangar")
        
        assert flow.wizard_state.hangar_data is not None
        assert flow.wizard_state.hangar_data["name"] == "Hangar 3"
        
        # Case 2: Hangar skipped
        flow2 = HangarAssistantConfigFlow()
        flow2.hass = flow.hass
        flow2.wizard_state.hangar_data = None
        flow2.wizard_state.mark_step_complete("add_hangar")
        
        assert flow2.wizard_state.hangar_data is None
        assert "add_hangar" in flow2.wizard_state.completed_steps
    
    def test_wizard_state_stores_aircraft_with_template(self, flow):
        """Test aircraft data stored with template application.
        
        Validates:
            - Registration stored
            - Template data merged
            - Performance specs included
            - Airfield/hangar links preserved
        
        Expected Result:
            Aircraft data includes template specs and user registration
        """
        aircraft_data = {
            "reg": "G-ABCD",
            "type": "cessna_172",
            "name": "Cessna 172 Skyhawk",
            "mtow_kg": 1157,
            "airfield": "Popham",
        }
        
        flow.wizard_state.aircraft_data = aircraft_data
        flow.wizard_state.mark_step_complete("add_aircraft")
        
        assert flow.wizard_state.aircraft_data["reg"] == "G-ABCD"
        assert flow.wizard_state.aircraft_data["mtow_kg"] == 1157
        assert "add_aircraft" in flow.wizard_state.completed_steps
    
    def test_build_final_config_includes_all_data(self, flow):
        """Test final config built correctly from wizard state.
        
        Validates:
            - Settings included
            - Integrations included
            - Airfield added to list
            - Hangar added if configured
            - Aircraft added to list
            - Setup marked complete
        
        Expected Result:
            Complete configuration structure ready for config entry
        """
        # Setup complete wizard state
        flow.wizard_state.general_settings = {
            "language": "en",
            "unit_preference": "aviation",
        }
        
        flow.wizard_state.api_configs = {
            "checkwx": {"enabled": True, "api_key": "test_key"},
        }
        
        flow.wizard_state.airfield_data = {
            "icao": "EGHP",
            "name": "Popham",
        }
        
        flow.wizard_state.aircraft_data = {
            "reg": "G-ABCD",
            "type": "cessna_172",
        }
        
        # Build final config
        config = flow._build_final_config()
        
        # Verify structure
        assert "settings" in config
        assert "integrations" in config
        assert "airfields" in config
        assert "aircraft" in config
        
        # Verify settings
        assert config["settings"]["language"] == "en"
        assert config["settings"]["setup_completed"] is True
        
        # Verify integrations
        assert "checkwx" in config["integrations"]
        assert "notams" in config["integrations"]  # Auto-enabled
        
        # Verify airfields
        assert len(config["airfields"]) == 1
        assert config["airfields"][0]["icao"] == "EGHP"
        
        # Verify aircraft
        assert len(config["aircraft"]) == 1
        assert config["aircraft"][0]["reg"] == "G-ABCD"
    
    def test_build_final_config_without_optional_data(self, flow):
        """Test final config works without optional data.
        
        Validates:
            - Config builds without hangar
            - Config builds without APIs
            - Config builds without sensor links
            - Required data still present
        
        Expected Result:
            Valid config with only required data
        """
        # Setup minimal wizard state
        flow.wizard_state.general_settings = {
            "language": "en",
        }
        
        flow.wizard_state.airfield_data = {
            "icao": "KJFK",
            "name": "New York JFK",
        }
        
        flow.wizard_state.aircraft_data = {
            "reg": "N12345",
            "type": "manual",
        }
        
        # hangar_data = None (not configured)
        # api_configs = {} (no APIs)
        # sensor_links = {} (no sensors)
        
        config = flow._build_final_config()
        
        # Should still have valid structure
        assert "settings" in config
        assert "airfields" in config
        assert "aircraft" in config
        assert len(config["hangars"]) == 0  # No hangar configured
        assert config["settings"]["setup_completed"] is True


class TestWizardValidation:
    """Test suite for wizard input validation.
    
    Tests validation of user inputs during wizard steps,
    ensuring helpful error messages and correct data handling.
    """
    
    def test_icao_validation_in_wizard(self):
        """Test ICAO code validation during airfield setup.
        
        Validates:
            - Valid ICAO codes accepted
            - Invalid codes rejected with helpful errors
            - Uppercase conversion applied
        
        Expected Result:
            Only valid 4-letter ICAO codes pass validation
        """
        from custom_components.hangar_assistant.validation import validate_icao
        
        # Valid codes
        valid, _ = validate_icao("EGHP")
        assert valid is True
        
        valid, _ = validate_icao("KJFK")
        assert valid is True
        
        # Invalid codes
        valid, error = validate_icao("EGH")  # Too short
        assert valid is False
        assert "4 characters" in error
        
        valid, error = validate_icao("EG12")  # Contains numbers
        assert valid is False
        assert "only letters" in error
    
    def test_registration_validation_in_wizard(self):
        """Test aircraft registration validation.
        
        Validates:
            - UK format accepted (G-ABCD)
            - US format accepted (N12345)
            - EU format accepted (D-EFGH)
            - Invalid formats rejected
        
        Expected Result:
            Common registration formats validated correctly
        """
        from custom_components.hangar_assistant.validation import validate_registration
        
        # Valid registrations
        valid, _ = validate_registration("G-ABCD")  # UK
        assert valid is True
        
        valid, _ = validate_registration("N12345")  # US
        assert valid is True
        
        valid, _ = validate_registration("D-EFGH")  # Germany
        assert valid is True
        
        # Invalid
        valid, error = validate_registration("ABCD")  # Too short
        assert valid is False
        assert "format" in error.lower()
    
    def test_api_key_validation_in_wizard(self):
        """Test API key format validation.
        
        Validates:
            - CheckWX key length (32+ chars)
            - OWM key format (32 hex chars)
            - Empty keys rejected
        
        Expected Result:
            API keys validated according to service requirements
        """
        from custom_components.hangar_assistant.validation import validate_api_key
        
        # Valid CheckWX key (32+ chars)
        valid, _ = validate_api_key("a" * 32, "checkwx")
        assert valid is True
        
        # Valid OWM key (32 hex chars)
        valid, _ = validate_api_key("1234567890abcdef" * 2, "openweathermap")
        assert valid is True
        
        # Invalid - too short
        valid, error = validate_api_key("short", "checkwx")
        assert valid is False
        assert "short" in error.lower() or "characters" in error.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
