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
            menu_options=["airfield", "aircraft", "pilot", "briefing"]
        )

    async def async_step_airfield(self, user_input=None):
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
            step_id="airfield",
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

    async def async_step_aircraft(self, user_input=None):
        """Sub-menu for adding a new aircraft profile."""
        if user_input is not None:
            new_data = dict(self.config_entry.data)
            fleet = new_data.setdefault("aircraft", [])
            fleet.append(user_input)
            
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(title="", data={})

        # Get list of configured airfields to allow linking
        airfields = self.config_entry.data.get("airfields", [])
        airfield_options = {a["name"]: a["name"] for a in airfields}

        return self.async_show_form(
            step_id="aircraft",
            data_schema=vol.Schema({
                vol.Required("reg"): str,
                vol.Required("model"): str,
                vol.Required("empty_weight"): int,
                vol.Required("max_tow"): int,
                vol.Required("max_xwind"): int,
                vol.Required("baseline_roll"): int,
                vol.Optional("linked_airfield"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[selector.SelectOptionDict(value=k, label=v) for k, v in airfield_options.items()],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
            })
        )

    async def async_step_pilot(self, user_input=None):
        """Sub-menu for adding pilot information."""
        if user_input is not None:
            new_data = dict(self.config_entry.data)
            new_data["pilot"] = user_input
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="pilot",
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Required("licence_number"): str,
                vol.Required("licence_type"): str,
                vol.Required("medical_expiry"): selector.DateSelector(),
            })
        )

    async def async_step_briefing(self, user_input=None):
        """Sub-menu for configuring automated briefings."""
        if user_input is not None:
            new_data = dict(self.config_entry.data)
            briefings = new_data.setdefault("briefings", [])
            briefings.append(user_input)
            
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(title="", data={})

        # Get existing airfields and aircraft for selection
        airfields = [a["name"] for a in self.config_entry.data.get("airfields", [])]
        aircraft = [a["reg"] for a in self.config_entry.data.get("aircraft", [])]

        return self.async_show_form(
            step_id="briefing",
            data_schema=vol.Schema({
                vol.Required("airfield_name"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=airfields, mode=selector.SelectSelectorMode.DROPDOWN)
                ),
                vol.Required("aircraft_reg"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=aircraft, mode=selector.SelectSelectorMode.DROPDOWN)
                ),
                vol.Required("briefing_time"): selector.TimeSelector(),
                vol.Required("email_recipient"): str,
                vol.Optional("auto_delete_enabled", default=True): bool,
                vol.Optional("retention_months", default=7): int,
            })
        )