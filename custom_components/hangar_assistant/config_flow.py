import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from .const import DOMAIN

class HangarAssistantConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle initial onboarding for Hangar Assistant."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Initial step when adding the integration for the first time."""
        # Ensure only one instance of the integration is installed
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            # Create a blank entry to get the user started
            return self.async_create_entry(title="Hangar Assistant", data={})

        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Directs 'Configure' button clicks to the Options Flow."""
        return HangarOptionsFlowHandler(config_entry)


class HangarOptionsFlowHandler(config_entries.OptionsFlow):
    """Manages the 'Configure' menu for adding/editing data."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Main configuration menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_airfield", "add_aircraft", "add_pilot"]
        )

    async def async_step_add_airfield(self, user_input=None):
        """Sub-menu for adding a new airfield with entity selectors."""
        if user_input is not None:
            # We append new airfields to the existing entry data
            new_data = dict(self.config_entry.data)
            airfields = new_data.setdefault("airfields", [])
            airfields.append(user_input)
            
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(title="", data={})

        # Schema using entity selectors for better UX
        return self.async_show_form(
            step_id="add_airfield",
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Required("temp_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Required("dp_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Required("wind_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="wind_speed")
                ),
                vol.Required("wind_dir_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required("runways"): str,
                vol.Required("runway_lengths"): str,
            })
        )

    async def async_step_add_aircraft(self, user_input=None):
        """Sub-menu for adding a new aircraft profile."""
        if user_input is not None:
            new_data = dict(self.config_entry.data)
            fleet = new_data.setdefault("aircraft", [])
            fleet.append(user_input)
            
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="add_aircraft",
            data_schema=vol.Schema({
                vol.Required("reg"): str,
                vol.Required("model"): str,
                vol.Required("empty_weight"): int,
                vol.Required("max_tow"): int,
                vol.Required("max_xwind"): int,
                vol.Required("baseline_roll"): int,
            })
        )