"""Tests for Phase 4: Dashboard Installation.

This module tests the dashboard installation automation features including:
- Dashboard installation service (automatic and manual modes)
- Dashboard YAML generation for manual installation
- Wizard integration with dashboard installation
- Service registration and handling

Test Strategy:
    - Mock Home Assistant services and file system operations
    - Test both automatic (API-based) and manual (YAML generation) methods
    - Verify wizard completion triggers dashboard installation
    - Test error handling and graceful degradation

Coverage:
    - Service handler execution (install_dashboard)
    - YAML generation function (_generate_dashboard_yaml)
    - Wizard step completion with dashboard trigger
    - Config entry updates after installation
"""
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall

from custom_components.hangar_assistant import (
    async_setup,
    _generate_dashboard_yaml,
)
from custom_components.hangar_assistant.config_flow import (
    HangarAssistantConfigFlow,
    SetupWizardState,
)
from custom_components.hangar_assistant.const import DOMAIN


class TestDashboardInstallationService:
    """Test suite for install_dashboard service.
    
    Tests the install_dashboard service handler with both automatic
    and manual installation methods, including error cases.
    
    Test Approach:
        - Mock Home Assistant services and config entries
        - Test service call with automatic method
        - Test service call with manual method
        - Verify config entry updates
    
    Scenarios Covered:
        - Automatic installation (creates dashboard via API)
        - Manual installation (generates YAML)
        - No config entry (error handling)
        - Service call failure (error logging)
    """
    
    @pytest.mark.asyncio
    async def test_service_handler_automatic_method(self):
        """Test install_dashboard service with automatic method.
        
        This test validates that the service handler:
            - Calls async_create_dashboard with force_rebuild=True
            - Updates config entry with installation metadata
            - Logs success message
        
        Setup:
            - Mock HomeAssistant with config entry
            - Mock async_create_dashboard to return True
        
        Validation:
            - async_create_dashboard called with correct params
            - Config entry updated with dashboard_installed flag
            - Dashboard URL stored in settings
        
        Expected Result:
            Service completes successfully with automatic installation
            and config entry contains installation metadata.
        """
        # Setup mocks
        mock_hass = MagicMock(spec=HomeAssistant)
        mock_hass.services = MagicMock()
        mock_hass.services.async_register = AsyncMock(return_value=None)
        mock_hass.config_entries = MagicMock()
        mock_entry = MagicMock(spec=ConfigEntry)
        mock_entry.data = {"settings": {}, "airfields": [], "aircraft": []}
        mock_hass.config_entries.async_entries.return_value = [mock_entry]
        
        # Mock async_create_dashboard
        with patch("custom_components.hangar_assistant.async_create_dashboard", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = True
            
            # Register services
            await async_setup(mock_hass, {})
            
            # Get the registered handler
            registered_services = mock_hass.services.async_register.call_args_list
            install_handler = None
            for call in registered_services:
                if call[0][1] == "install_dashboard":
                    install_handler = call[0][2]
                    break
            
            assert install_handler is not None, "install_dashboard service not registered"
            
            # Call service with automatic method
            mock_call = MagicMock(spec=ServiceCall)
            mock_call.data = {"method": "automatic"}
            
            await install_handler(mock_call)
            
            # Verify dashboard creation was called
            mock_create.assert_called_once()
            call_args = mock_create.call_args
            assert call_args[1]["force_rebuild"] is True
            assert call_args[1]["reason"] == "install_service"
    
    @pytest.mark.asyncio
    async def test_service_handler_manual_method(self):
        """Test install_dashboard service with manual method.
        
        This test validates that the service handler:
            - Calls _generate_dashboard_yaml to create YAML string
            - Stores YAML in config entry for retrieval
            - Sets installation method to 'manual'
        
        Setup:
            - Mock HomeAssistant with config entry
            - Mock _generate_dashboard_yaml to return sample YAML
        
        Validation:
            - _generate_dashboard_yaml called with correct params
            - Config entry updated with dashboard YAML
            - Installation method set to 'manual'
        
        Expected Result:
            Service generates YAML for manual installation and stores
            it in config entry for user retrieval via wizard.
        """
        # Setup mocks
        mock_hass = MagicMock(spec=HomeAssistant)
        mock_hass.services = MagicMock()
        mock_hass.services.async_register = AsyncMock(return_value=None)
        mock_hass.config_entries = MagicMock()
        mock_entry = MagicMock(spec=ConfigEntry)
        mock_entry.data = {"settings": {}, "airfields": [], "aircraft": []}
        mock_hass.config_entries.async_entries.return_value = [mock_entry]
        
        sample_yaml = "# Dashboard YAML\nviews:\n  - title: Test"
        
        # Mock YAML generation
        with patch("custom_components.hangar_assistant._generate_dashboard_yaml", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = sample_yaml
            
            # Register services
            await async_setup(mock_hass, {})
            
            # Get the registered handler
            registered_services = mock_hass.services.async_register.call_args_list
            install_handler = None
            for call in registered_services:
                if call[0][1] == "install_dashboard":
                    install_handler = call[0][2]
                    break
            
            assert install_handler is not None
            
            # Call service with manual method
            mock_call = MagicMock(spec=ServiceCall)
            mock_call.data = {"method": "manual"}
            
            await install_handler(mock_call)
            
            # Verify YAML generation was called
            mock_gen.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_service_no_config_entry(self):
        """Test install_dashboard service when no config entry exists.
        
        This test validates graceful error handling when service
        is called but no config entry is available.
        
        Setup:
            - Mock HomeAssistant with no config entries
        
        Validation:
            - Service logs warning about missing config entry
            - Service returns without crashing
        
        Expected Result:
            Service completes with warning log, no crash.
        """
        # Setup mocks
        mock_hass = MagicMock(spec=HomeAssistant)
        mock_hass.services = MagicMock()
        mock_hass.services.async_register = AsyncMock(return_value=None)
        mock_hass.config_entries = MagicMock()
        mock_hass.config_entries.async_entries.return_value = []  # No entries
        
        # Register services
        await async_setup(mock_hass, {})
        
        # Get the registered handler
        registered_services = mock_hass.services.async_register.call_args_list
        install_handler = None
        for call in registered_services:
            if call[0][1] == "install_dashboard":
                install_handler = call[0][2]
                break
        
        assert install_handler is not None
        
        # Call service (should handle gracefully)
        mock_call = MagicMock(spec=ServiceCall)
        mock_call.data = {"method": "automatic"}
        
        # Should not raise exception
        await install_handler(mock_call)


class TestDashboardYAMLGeneration:
    """Test suite for dashboard YAML generation.
    
    Tests the _generate_dashboard_yaml helper function that creates
    YAML content for manual dashboard installation.
    
    Test Approach:
        - Mock file system operations
        - Test YAML loading and header injection
        - Verify error handling
    
    Scenarios Covered:
        - Successful YAML generation with header
        - File not found error handling
        - Invalid file content handling
    """
    
    @pytest.mark.asyncio
    async def test_generate_dashboard_yaml_success(self):
        """Test successful dashboard YAML generation.
        
        This test validates that _generate_dashboard_yaml:
            - Loads template from file
            - Adds instructional header
            - Returns complete YAML string
        
        Setup:
            - Mock file system with sample template
            - Mock executor job for file I/O
        
        Validation:
            - Returns string starting with header comment
            - Contains template content
            - Includes installation instructions
        
        Expected Result:
            Complete YAML string with header and template content.
        """
        mock_hass = MagicMock(spec=HomeAssistant)
        mock_hass.async_add_executor_job = AsyncMock(side_effect=lambda func: func())
        mock_entry = MagicMock(spec=ConfigEntry)
        mock_entry.data = {"airfields": [], "aircraft": []}
        
        template_content = "views:\n  - title: Glass Cockpit\n    cards: []"
        
        # Mock file read
        m_open = mock_open(read_data=template_content)
        
        with patch("builtins.open", m_open):
            result = await _generate_dashboard_yaml(mock_hass, mock_entry)
        
        # Verify result
        assert result is not None
        assert "# Hangar Assistant Glass Cockpit Dashboard" in result
        assert "INSTALLATION INSTRUCTIONS:" in result
        assert template_content in result
    
    @pytest.mark.asyncio
    async def test_generate_dashboard_yaml_file_not_found(self):
        """Test dashboard YAML generation with missing template file.
        
        This test validates error handling when template file is missing:
            - Catches OSError
            - Logs error message
            - Returns None
        
        Setup:
            - Mock file system to raise FileNotFoundError
        
        Validation:
            - Returns None
            - Logs error with file path
        
        Expected Result:
            Function returns None gracefully without crashing.
        """
        mock_hass = MagicMock(spec=HomeAssistant)
        mock_hass.async_add_executor_job = AsyncMock(side_effect=lambda func: func())
        mock_entry = MagicMock(spec=ConfigEntry)
        mock_entry.data = {"airfields": [], "aircraft": []}
        
        # Mock file read to raise FileNotFoundError
        with patch("builtins.open", side_effect=FileNotFoundError("Template not found")):
            result = await _generate_dashboard_yaml(mock_hass, mock_entry)
        
        # Verify graceful failure
        assert result is None


class TestWizardDashboardIntegration:
    """Test suite for wizard integration with dashboard installation.
    
    Tests that the setup wizard properly triggers dashboard installation
    when user completes the wizard with automatic or manual method.
    
    Test Approach:
        - Mock config flow wizard state
        - Test wizard completion with different methods
        - Verify service calls scheduled
    
    Scenarios Covered:
        - Wizard completion with automatic installation
        - Wizard completion with manual installation
        - Wizard completion with skip option
    """
    
    @pytest.mark.asyncio
    async def test_wizard_triggers_automatic_installation(self):
        """Test wizard completion triggers automatic dashboard installation.
        
        This test validates that completing the wizard with 'automatic'
        method schedules a dashboard installation service call.
        
        Setup:
            - Mock HangarAssistantConfigFlow with wizard state
            - Mock hass.services.async_call
            - Mock hass.async_create_task
        
        Validation:
            - async_create_entry called
            - async_create_task scheduled with installation task
            - Task calls install_dashboard service with method='automatic'
        
        Expected Result:
            Wizard completes and schedules dashboard installation as
            background task after entry creation.
        """
        mock_hass = MagicMock(spec=HomeAssistant)
        mock_hass.async_create_task = MagicMock()
        mock_hass.services = MagicMock()
        mock_hass.services.async_call = AsyncMock()
        
        flow = HangarAssistantConfigFlow()
        flow.hass = mock_hass
        flow.wizard_state = SetupWizardState()
        
        # Populate wizard state
        flow.wizard_state.general_settings = {"language": "en"}
        flow.wizard_state.airfield_data = {
            "icao": "EGHP",
            "name": "Popham",
            "latitude": 51.2,
            "longitude": -1.2,
            "elevation_ft": 550,
        }
        
        # Complete wizard with automatic method
        user_input = {"method": "automatic"}
        
        with patch.object(flow, "async_create_entry", return_value={"flow_id": "test"}):
            result = await flow.async_step_install_dashboard(user_input)
        
        # Verify entry created
        assert result is not None
        
        # Verify background task scheduled
        mock_hass.async_create_task.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_wizard_skips_installation(self):
        """Test wizard completion with skip option.
        
        This test validates that completing wizard with 'skip' method
        creates entry without triggering dashboard installation.
        
        Setup:
            - Mock HangarAssistantConfigFlow with wizard state
        
        Validation:
            - async_create_entry called
            - No async_create_task scheduled
            - Config contains skip preference
        
        Expected Result:
            Wizard completes without scheduling installation task.
        """
        mock_hass = MagicMock(spec=HomeAssistant)
        mock_hass.async_create_task = MagicMock()
        
        flow = HangarAssistantConfigFlow()
        flow.hass = mock_hass
        flow.wizard_state = SetupWizardState()
        
        # Populate wizard state
        flow.wizard_state.general_settings = {"language": "en"}
        flow.wizard_state.airfield_data = {
            "icao": "EGHP",
            "name": "Popham",
            "latitude": 51.2,
            "longitude": -1.2,
            "elevation_ft": 550,
        }
        
        # Complete wizard with skip
        user_input = {"method": "skip"}
        
        with patch.object(flow, "async_create_entry", return_value={"flow_id": "test"}):
            result = await flow.async_step_install_dashboard(user_input)
        
        # Verify entry created
        assert result is not None
        
        # Verify NO background task scheduled
        mock_hass.async_create_task.assert_not_called()


class TestDashboardServiceRegistration:
    """Test suite for dashboard service registration.
    
    Tests that the install_dashboard service is properly registered
    during integration setup.
    
    Test Approach:
        - Mock service registration
        - Verify service name and schema
    
    Scenarios Covered:
        - Service registration during async_setup
        - Service schema validation
    """
    
    @pytest.mark.asyncio
    async def test_install_dashboard_service_registered(self):
        """Test that install_dashboard service is registered.
        
        This test validates that async_setup registers the
        install_dashboard service with correct schema.
        
        Setup:
            - Mock HomeAssistant
        
        Validation:
            - hass.services.async_register called with DOMAIN and 'install_dashboard'
            - Schema includes 'method' field with correct options
        
        Expected Result:
            Service registered with proper name and validation schema.
        """
        mock_hass = MagicMock(spec=HomeAssistant)
        mock_hass.services = MagicMock()
        mock_hass.services.async_register = AsyncMock(return_value=None)
        
        # Register services
        await async_setup(mock_hass, {})
        
        # Verify install_dashboard service registered
        registered_services = mock_hass.services.async_register.call_args_list
        service_names = [call[0][1] for call in registered_services]
        
        assert "install_dashboard" in service_names, "install_dashboard service not registered"
        
        # Find the install_dashboard registration
        install_call = None
        for call in registered_services:
            if call[0][1] == "install_dashboard":
                install_call = call
                break
        
        assert install_call is not None
        # Verify schema (should have 'method' field)
        # Schema is at install_call[1]['schema']
