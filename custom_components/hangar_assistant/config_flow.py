from __future__ import annotations

import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from .const import DOMAIN, DEFAULT_AI_SYSTEM_PROMPT, DEFAULT_DASHBOARD_VERSION

_LOGGER = logging.getLogger(__name__)

class HangarAssistantConfigFlow(config_entries.ConfigFlow):
    """Handle initial onboarding for Hangar Assistant.
    
    This config flow manages the initial setup when users add the integration.
    Since Hangar Assistant only supports a single configuration entry, this flow
    prevents duplicate entries and creates a blank entry to start configuration.
    
    After initial setup, users access the full configuration through the Options flow.
    
    Steps:
        1. async_step_user: Check for existing entry, create blank entry if allowed
    
    After this flow completes:
        - Users see the \"Configure\" button to access HangarOptionsFlowHandler
        - They can add airfields, aircraft, and pilots through the Options menu
    """
    VERSION = 1
    DOMAIN = DOMAIN

    async def async_step_user(self, user_input=None):
        """Initial step when adding the integration for the first time.
        
        Checks if an entry already exists (integration only supports single instance).
        If allowed, creates a blank ConfigEntry that will be edited through the Options flow.
        
        Args:
            user_input: None on first load, empty dict on form submission
        
        Returns:
            - async_abort(reason=\"already_configured\") if entry exists
            - async_create_entry(\"Hangar Assistant\", {}) on first-time setup
            - async_show_form(\"user\") to display the form
        """
        # Ensure only one instance of the integration is installed
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            # Create a blank entry to get the user started
            return self.async_create_entry(title="Hangar Assistant", data={})

        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> HangarOptionsFlowHandler:
        """Directs 'Configure' button clicks to the Options Flow."""
        return HangarOptionsFlowHandler()


class HangarOptionsFlowHandler(config_entries.OptionsFlow):
    """Manages the 'Configure' menu for adding/editing data.
    
    This handler provides the full configuration interface accessed through the
    \"Configure\" button in Settings > Devices & Services > Hangar Assistant.
    
    Main Menu Structure:
        - Airfield (add/manage airfields)
        - Aircraft (add/manage aircraft)
        - Pilot (add/manage pilots)
        - Briefing (add/manage scheduled briefings)
        - Global Config (settings, AI prompts, retention, dashboard)
    
    Data Flow:
        1. User navigates menu: async_step_init
        2. Selects category (airfield/aircraft/pilot/briefing/global_config)
        3. Chooses action (add/edit/delete) if applicable
        4. Completes form and data is saved to entry.data via async_update_entry
    
    Each submenu has add/edit/delete/manage options for managing the corresponding lists.
    """

    async def async_step_init(self, user_input=None):
        """Main configuration menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["airfield", "aircraft", "pilot", "briefing", "global_config"]
        )

    async def async_step_global_config(self, user_input=None):
        """Sub-menu for global system settings."""
        return self.async_show_menu(
            step_id="global_config",
            menu_options=["settings", "ai", "retention", "dashboard"]
        )

    async def async_step_settings(self, user_input=None):
        """Configure global system settings."""
        if user_input is not None:
            new_data = dict(self.config_entry.data)
            new_data["settings"] = user_input
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(data=dict(self.config_entry.options))

        settings = self.config_entry.data.get("settings", {})
        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema({
                vol.Required("language", default=settings.get("language", "en")): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[selector.SelectOptionDict(value="en", label="English")],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Optional("global_pressure_sensor", default=settings.get("global_pressure_sensor")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="pressure")
                ),
                vol.Optional("default_pressure", default=settings.get("default_pressure", 1013.25)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=800, max=1100, step=0.1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="hPa")
                ),
            })
        )

    async def async_step_airfield(self, user_input=None):
        """Sub-menu for airfield management."""
        airfields = self.config_entry.data.get("airfields", [])
        
        if airfields:
            return self.async_show_menu(
                step_id="airfield",
                menu_options=["airfield_add", "airfield_manage"]
            )
        return await self.async_step_airfield_add()

    async def async_step_airfield_add(self, user_input=None):
        """Form to add a new airfield from scratch."""
        if user_input is not None:
            new_data = dict(self.config_entry.data)
            airfields = list(new_data.get("airfields", []))
            airfields.append(user_input)
            new_data["airfields"] = airfields
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(data=dict(self.config_entry.options))

        return self.async_show_form(
            step_id="airfield_add",
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Optional("icao_code"): str,
                vol.Required("latitude", default=51.47): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-90, max=90, step="any", mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Required("longitude", default=-0.45): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-180, max=180, step="any", mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Required("elevation", default=25): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-500, max=9000, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="m")
                ),
                vol.Required("runways"): str,
                vol.Required("primary_runway"): str,
                vol.Required("runway_length", default=500): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=100, 
                        max=2000, 
                        step=1, 
                        mode=selector.NumberSelectorMode.SLIDER,
                        unit_of_measurement="m"
                    )
                ),
                vol.Required("temp_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Required("dp_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Required("pressure_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required("wind_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="speed")
                ),
                vol.Required("wind_dir_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            })
        )

    async def async_step_airfield_manage(self, user_input=None):
        """Menu to manage existing airfields."""
        airfields = self.config_entry.data.get("airfields", [])
        options = {str(i): a.get("name", f"Airfield {i}") for i, a in enumerate(airfields)}

        if user_input is not None:
            self._index = int(user_input["index"])
            if user_input["action"] == "edit":
                return await self.async_step_airfield_edit()
            return await self.async_step_airfield_delete()

        return self.async_show_form(
            step_id="airfield_manage",
            data_schema=vol.Schema({
                vol.Required("index"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[selector.SelectOptionDict(value=k, label=v) for k, v in options.items()],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required("action"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value="edit", label="Edit"),
                            selector.SelectOptionDict(value="delete", label="Delete")
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
            })
        )

    async def async_step_airfield_edit(self, user_input=None):
        """Edit an existing airfield."""
        index = self._index
        airfields = self.config_entry.data.get("airfields", [])
        airfield = airfields[index]

        if user_input is not None:
            new_data = dict(self.config_entry.data)
            airfields = list(new_data.get("airfields", []))
            airfields[index] = user_input
            new_data["airfields"] = airfields
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(data=dict(self.config_entry.options))

        return self.async_show_form(
            step_id="airfield_edit",
            data_schema=vol.Schema({
                vol.Required("name", default=airfield.get("name")): str,
                vol.Optional("icao_code", default=airfield.get("icao_code", "")): str,
                vol.Required("latitude", default=airfield.get("latitude")): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-90, max=90, step="any", mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Required("longitude", default=airfield.get("longitude")): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-180, max=180, step="any", mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Required("elevation", default=airfield.get("elevation", 0)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-500, max=9000, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="m")
                ),
                vol.Required("runways", default=airfield.get("runways")): str,
                vol.Required("primary_runway", default=airfield.get("primary_runway")): str,
                vol.Required("runway_length", default=airfield.get("runway_length", 500)): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=100, 
                        max=2000, 
                        step=1, 
                        mode=selector.NumberSelectorMode.SLIDER,
                        unit_of_measurement="m"
                    )
                ),
                vol.Required("temp_sensor", default=airfield.get("temp_sensor")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Required("dp_sensor", default=airfield.get("dp_sensor")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Required("pressure_sensor", default=airfield.get("pressure_sensor")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="pressure")
                ),
                vol.Required("wind_sensor", default=airfield.get("wind_sensor")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="wind_speed")
                ),
                vol.Required("wind_dir_sensor", default=airfield.get("wind_dir_sensor")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            })
        )

    async def async_step_airfield_delete(self, user_input=None):
        """Delete an airfield."""
        if user_input is not None:
            if user_input["confirm"]:
                new_data = dict(self.config_entry.data)
                airfields = list(new_data.get("airfields", []))
                airfields.pop(self._index)
                new_data["airfields"] = airfields
                self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(data=dict(self.config_entry.options))

        return self.async_show_form(
            step_id="airfield_delete",
            data_schema=vol.Schema({
                vol.Required("confirm", default=False): selector.BooleanSelector()
            }),
            description_placeholders={"name": self.config_entry.data["airfields"][self._index]["name"]}
        )


    async def async_step_aircraft(self, user_input=None):
        """Sub-menu for aircraft management."""
        fleet = self.config_entry.data.get("aircraft", [])
        
        if fleet:
            return self.async_show_menu(
                step_id="aircraft",
                menu_options=["aircraft_add", "aircraft_manage"]
            )
        return await self.async_step_aircraft_add()

    async def async_step_aircraft_add(self, user_input=None):
        """Form to add a new aircraft."""
        if user_input is not None:
            new_data = dict(self.config_entry.data)
            fleet = list(new_data.get("aircraft", []))
            fleet.append(user_input)
            new_data["aircraft"] = fleet
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(data=dict(self.config_entry.options))

        airfields = [a["name"] for a in self.config_entry.data.get("airfields", [])]
        return self.async_show_form(
            step_id="aircraft_add",
            data_schema=vol.Schema({
                vol.Required("reg"): str,
                vol.Required("model"): str,
                vol.Required("empty_weight", default=750): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=500, max=10000, step=50, unit_of_measurement="kg")
                ),
                vol.Required("max_tow", default=1200): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=500, max=10000, step=50, unit_of_measurement="kg")
                ),
                vol.Required("max_xwind", default=15): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=50, step=1, unit_of_measurement="kt")
                ),
                vol.Required("baseline_roll", default=300): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10, max=750, step=5, unit_of_measurement="m")
                ),
                vol.Required("baseline_50ft", default=600): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10, max=1500, step=5, unit_of_measurement="m")
                ),
                vol.Optional("linked_airfield"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[selector.SelectOptionDict(value=a, label=a) for a in airfields],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required("ifr_capable", default=False): selector.BooleanSelector(),
            })
        )

    async def async_step_aircraft_manage(self, user_input=None):
        """Menu to manage existing aircraft."""
        fleet = self.config_entry.data.get("aircraft", [])
        options = {str(i): f"{a['reg']} ({a['model']})" for i, a in enumerate(fleet)}

        if user_input is not None:
            self._index = int(user_input["index"])
            if user_input["action"] == "edit":
                return await self.async_step_aircraft_edit()
            return await self.async_step_aircraft_delete()

        return self.async_show_form(
            step_id="aircraft_manage",
            data_schema=vol.Schema({
                vol.Required("index"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[selector.SelectOptionDict(value=k, label=v) for k, v in options.items()],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required("action"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value="edit", label="Edit"),
                            selector.SelectOptionDict(value="delete", label="Delete")
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
            })
        )

    async def async_step_aircraft_edit(self, user_input=None):
        """Edit an existing aircraft."""
        index = self._index
        fleet = self.config_entry.data.get("aircraft", [])
        ac = fleet[index]

        if user_input is not None:
            new_data = dict(self.config_entry.data)
            fleet = list(new_data.get("aircraft", []))
            fleet[index] = user_input
            new_data["aircraft"] = fleet
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(data=dict(self.config_entry.options))

        airfields = [a["name"] for a in self.config_entry.data.get("airfields", [])]
        return self.async_show_form(
            step_id="aircraft_edit",
            data_schema=vol.Schema({
                vol.Required("reg", default=ac.get("reg")): str,
                vol.Required("model", default=ac.get("model")): str,
                vol.Required("empty_weight", default=ac.get("empty_weight")): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=500, max=10000, step=50, unit_of_measurement="kg")
                ),
                vol.Required("max_tow", default=ac.get("max_tow")): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=500, max=10000, step=50, unit_of_measurement="kg")
                ),
                vol.Required("max_xwind", default=ac.get("max_xwind")): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=50, step=1, unit_of_measurement="kt")
                ),
                vol.Required("baseline_roll", default=ac.get("baseline_roll")): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10, max=750, step=5, unit_of_measurement="m")
                ),
                vol.Required("baseline_50ft", default=ac.get("baseline_50ft", 0)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10, max=1500, step=5, unit_of_measurement="m")
                ),
                vol.Optional("linked_airfield", default=ac.get("linked_airfield")): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[selector.SelectOptionDict(value=a, label=a) for a in airfields],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required("ifr_capable", default=ac.get("ifr_capable", False)): selector.BooleanSelector(),
            })
        )

    async def async_step_aircraft_delete(self, user_input=None):
        """Delete an aircraft."""
        if user_input is not None:
            if user_input["confirm"]:
                new_data = dict(self.config_entry.data)
                fleet = list(new_data.get("aircraft", []))
                fleet.pop(self._index)
                new_data["aircraft"] = fleet
                self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(data=dict(self.config_entry.options))

        return self.async_show_form(
            step_id="aircraft_delete",
            data_schema=vol.Schema({
                vol.Required("confirm", default=False): selector.BooleanSelector()
            }),
            description_placeholders={"reg": self.config_entry.data["aircraft"][self._index]["reg"]}
        )

    async def async_step_pilot(self, user_input=None):
        """Sub-menu for pilot management."""
        pilots = self.config_entry.data.get("pilots", [])
        
        if pilots:
            return self.async_show_menu(
                step_id="pilot",
                menu_options=["pilot_add", "pilot_manage"]
            )
        
        # If no pilots exist, go straight to add form
        return await self.async_step_pilot_add()

    async def async_step_pilot_add(self, user_input=None):
        """Form to add a new pilot."""
        if user_input is not None:
            new_data = dict(self.config_entry.data)
            pilots = list(new_data.get("pilots", []))
            pilots.append(user_input)
            new_data["pilots"] = pilots
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(data=dict(self.config_entry.options))

        return self.async_show_form(
            step_id="pilot_add",
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Required("email"): str,
                vol.Required("licence_number"): str,
                vol.Required("licence_type"): str,
                vol.Required("medical_expiry"): selector.DateSelector(),
            })
        )

    async def async_step_pilot_manage(self, user_input=None):
        """Menu to manage existing pilots."""
        pilots = self.config_entry.data.get("pilots", [])
        options = {str(i): p["name"] for i, p in enumerate(pilots)}

        if user_input is not None:
            self._index = int(user_input["index"])
            if user_input["action"] == "edit":
                return await self.async_step_pilot_edit()
            return await self.async_step_pilot_delete()

        return self.async_show_form(
            step_id="pilot_manage",
            data_schema=vol.Schema({
                vol.Required("index"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[selector.SelectOptionDict(value=k, label=v) for k, v in options.items()],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required("action"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value="edit", label="Edit"),
                            selector.SelectOptionDict(value="delete", label="Delete")
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
            })
        )

    async def async_step_pilot_edit(self, user_input=None):
        """Edit an existing pilot."""
        index = self._index
        pilots = self.config_entry.data.get("pilots", [])
        pilot = pilots[index]

        if user_input is not None:
            new_data = dict(self.config_entry.data)
            new_pilots = list(new_data.get("pilots", []))
            new_pilots[index] = user_input
            new_data["pilots"] = new_pilots
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(data=dict(self.config_entry.options))

        return self.async_show_form(
            step_id="pilot_edit",
            data_schema=vol.Schema({
                vol.Required("name", default=pilot.get("name")): str,
                vol.Required("email", default=pilot.get("email")): str,
                vol.Required("licence_number", default=pilot.get("licence_number")): str,
                vol.Required("licence_type", default=pilot.get("licence_type")): str,
                vol.Required("medical_expiry", default=pilot.get("medical_expiry")): selector.DateSelector(),
            })
        )

    async def async_step_pilot_delete(self, user_input=None):
        """Delete a pilot."""
        if user_input is not None:
            if user_input["confirm"]:
                new_data = dict(self.config_entry.data)
                new_pilots = list(new_data.get("pilots", []))
                new_pilots.pop(self._index)
                new_data["pilots"] = new_pilots
                self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(data=dict(self.config_entry.options))

        return self.async_show_form(
            step_id="pilot_delete",
            data_schema=vol.Schema({
                vol.Required("confirm", default=False): selector.BooleanSelector()
            }),
            description_placeholders={"name": self.config_entry.data["pilots"][self._index]["name"]}
        )

    async def async_step_ai(self, user_input=None):
        """Configure AI conversation assistant (generic across all tools)."""
        if user_input is not None:
            new_data = dict(self.config_entry.data)
            new_data["ai_assistant"] = user_input
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(data=dict(self.config_entry.options))

        ai_config = self.config_entry.data.get("ai_assistant", {})
        use_custom = ai_config.get("use_custom_system_prompt", False)

        schema_dict = {
            vol.Required("ai_agent_entity", default=ai_config.get("ai_agent_entity", "")): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="conversation",
                    multiple=False
                )
            ),
            vol.Optional("use_custom_system_prompt", default=use_custom): selector.BooleanSelector(),
        }

        # Show custom prompt field if toggle is enabled
        if use_custom:
            schema_dict[vol.Optional("custom_system_prompt", default=ai_config.get("custom_system_prompt", ""))] = selector.TextSelector()

        return self.async_show_form(
            step_id="ai",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "default_prompt_preview": DEFAULT_AI_SYSTEM_PROMPT[:200] + "..."
            }
        )

    async def async_step_briefing(self, user_input=None):
        """Sub-menu for configuring automated briefings."""
        briefings = self.config_entry.data.get("briefings", [])
        
        if briefings:
            return self.async_show_menu(
                step_id="briefing",
                menu_options=["briefing_add", "briefing_manage"]
            )
        
        # If no briefings exist, go straight to add form
        return await self.async_step_briefing_add()

    async def async_step_briefing_add(self, user_input=None):
        """Form to add a new automated briefing."""
        if user_input is not None:
            new_data = dict(self.config_entry.data)
            briefings = list(new_data.get("briefings", []))
            briefings.append(user_input)
            new_data["briefings"] = briefings
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(data=dict(self.config_entry.options))

        # Get existing airfields, aircraft, and pilots for selection
        airfields = [a["name"] for a in self.config_entry.data.get("airfields", [])]
        aircraft = [a["reg"] for a in self.config_entry.data.get("aircraft", [])]
        pilots = [p["name"] for p in self.config_entry.data.get("pilots", [])]

        return self.async_show_form(
            step_id="briefing_add",
            data_schema=vol.Schema({
                vol.Required("airfield_name"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[selector.SelectOptionDict(value=a, label=a) for a in airfields],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required("aircraft_reg"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[selector.SelectOptionDict(value=a, label=a) for a in aircraft],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required("briefing_time"): selector.TimeSelector(),
                vol.Required("pilots"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[selector.SelectOptionDict(value=p, label=p) for p in pilots],
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST
                    )
                ),
                vol.Optional("enable_ai_reporting", default=False): selector.BooleanSelector(),
            })
        )

    async def async_step_briefing_manage(self, user_input=None):
        """Menu to manage existing briefings."""
        briefings = self.config_entry.data.get("briefings", [])
        
        if user_input is not None:
            action = user_input.get("action")
            index = user_input.get("briefing_index")
            
            if action == "edit" and index is not None:
                self._briefing_index = int(index)
                return await self.async_step_briefing_edit()
            elif action == "delete" and index is not None:
                self._briefing_index = int(index)
                return await self.async_step_briefing_delete()
        
        briefing_options = {
            str(i): f"{', '.join(b.get('pilots', []))} ({b['airfield_name']})" 
            for i, b in enumerate(briefings)
        }

        return self.async_show_form(
            step_id="briefing_manage",
            data_schema=vol.Schema({
                vol.Required("briefing_index"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[selector.SelectOptionDict(value=k, label=v) for k, v in briefing_options.items()],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required("action"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value="edit", label="Edit"),
                            selector.SelectOptionDict(value="delete", label="Delete")
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
            })
        )

    async def async_step_briefing_edit(self, user_input=None):
        """Edit an existing automated briefing."""
        index = self._briefing_index
        briefings = self.config_entry.data.get("briefings", [])
        
        if index >= len(briefings):
            return self.async_abort(reason="reconfigure_successful")
        
        briefing = briefings[index]

        if user_input is not None:
            new_data = dict(self.config_entry.data)
            new_briefings = list(new_data.get("briefings", []))
            new_briefings[index] = user_input
            new_data["briefings"] = new_briefings
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(data=dict(self.config_entry.options))

        # Get existing airfields, aircraft, and pilots for selection
        airfields = [a["name"] for a in self.config_entry.data.get("airfields", [])]
        aircraft = [a["reg"] for a in self.config_entry.data.get("aircraft", [])]
        pilots = [p["name"] for p in self.config_entry.data.get("pilots", [])]

        return self.async_show_form(
            step_id="briefing_edit",
            data_schema=vol.Schema({
                vol.Required("airfield_name", default=briefing.get("airfield_name")): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[selector.SelectOptionDict(value=a, label=a) for a in airfields],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required("aircraft_reg", default=briefing.get("aircraft_reg")): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[selector.SelectOptionDict(value=a, label=a) for a in aircraft],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required("briefing_time", default=briefing.get("briefing_time")): selector.TimeSelector(),
                vol.Required("pilots", default=briefing.get("pilots", [])): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[selector.SelectOptionDict(value=p, label=p) for p in pilots],
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST
                    )
                ),
                vol.Optional("enable_ai_reporting", default=briefing.get("enable_ai_reporting", False)): selector.BooleanSelector(),
            })
        )

    async def async_step_briefing_delete(self, user_input=None):
        """Confirm deletion of a briefing."""
        index = self._briefing_index
        briefings = self.config_entry.data.get("briefings", [])
        
        if index >= len(briefings):
            return self.async_abort(reason="reconfigure_successful")
        
        briefing = briefings[index]

        if user_input is not None:
            if user_input.get("confirm_delete"):
                new_data = dict(self.config_entry.data)
                new_briefings = list(new_data.get("briefings", []))
                new_briefings.pop(index)
                new_data["briefings"] = new_briefings
                self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(data=dict(self.config_entry.options))

        return self.async_show_form(
            step_id="briefing_delete",
            data_schema=vol.Schema({
                vol.Required("confirm_delete", default=False): selector.BooleanSelector(),
            }),
            description_placeholders={
                "briefing": f"{', '.join(briefing.get('pilots', []))} for {briefing.get('airfield_name')}"
            }
        )

    async def async_step_dashboard(self, user_input=None):
        """Manage Hangar Assistant dashboard."""
        if user_input is not None:
            if user_input.get("action") == "rebuild":
                # Call the rebuild service
                await self.hass.services.async_call("hangar_assistant", "rebuild_dashboard")
            return self.async_create_entry(data=dict(self.config_entry.options))

        # Get current dashboard info
        dashboard_info = self.config_entry.data.get("dashboard_info", {})
        current_version = dashboard_info.get("version", 0)
        last_updated = dashboard_info.get("last_updated", "Never")
        
        return self.async_show_form(
            step_id="dashboard",
            data_schema=vol.Schema({
                vol.Required("action", default="rebuild"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value="rebuild", label="Rebuild Dashboard"),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
            }),
            description_placeholders={
                "current_version": str(current_version),
                "template_version": str(DEFAULT_DASHBOARD_VERSION),
                "last_updated": str(last_updated)
            }
        )

    async def async_step_retention(self, user_input=None):
        """Configure data retention policy."""
        if user_input is not None:
            new_data = dict(self.config_entry.data)
            new_data["retention"] = {
                "auto_delete_enabled": user_input.get("auto_delete_enabled", True),
                "retention_months": user_input.get("retention_months", 7)
            }
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(data=dict(self.config_entry.options))

        retention_config = self.config_entry.data.get("retention", {})
        
        return self.async_show_form(
            step_id="retention",
            data_schema=vol.Schema({
                vol.Optional("auto_delete_enabled", default=retention_config.get("auto_delete_enabled", True)): selector.BooleanSelector(),
                vol.Optional("retention_months", default=retention_config.get("retention_months", 7)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=120, step=1, unit_of_measurement="months")
                ),
            })
        )