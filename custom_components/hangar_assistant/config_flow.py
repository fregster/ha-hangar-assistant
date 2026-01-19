import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN

class HangarAssistantConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hangar Assistant."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step to choose a configuration category."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["airfield", "aircraft", "pilot", "briefing"]
        )

    async def async_step_airfield(self, user_input=None):
        """Step to configure an Airfield with weather sensors."""
        if user_input is not None:
            return self.async_create_entry(
                title=f"Airfield: {user_input['name']}", 
                data={"type": "airfield", **user_input}
            )

        return self.async_show_form(
            step_id="airfield",
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Required("temp_sensor"): str,
                vol.Required("dp_sensor"): str,
                vol.Required("wind_sensor"): str,
                vol.Required("wind_dir_sensor"): str,
                vol.Required("runways"): str,
                vol.Required("runway_lengths"): str,
            })
        )

    async def async_step_aircraft(self, user_input=None):
        """Step to configure Aircraft performance profiles."""
        if user_input is not None:
            return self.async_create_entry(
                title=f"Aircraft: {user_input['reg']}", 
                data={"type": "aircraft", **user_input}
            )

        return self.async_show_form(
            step_id="aircraft",
            data_schema=vol.Schema({
                vol.Required("reg"): str,
                vol.Required("model"): str,
                vol.Required("empty_weight"): int,
                vol.Required("max_tow"): int,
                vol.Required("max_xwind"): int,
                vol.Required("baseline_roll"): int,
                vol.Required("baseline_50ft"): int,
            })
        )

    async def async_step_pilot(self, user_input=None):
        """Step to configure Pilot details for CAP 1590B compliance."""
        if user_input is not None:
            return self.async_create_entry(
                title=f"Pilot: {user_input['name']}", 
                data={"type": "pilot", **user_input}
            )

        return self.async_show_form(
            step_id="pilot",
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Required("licence_number"): str,
                vol.Required("licence_type"): str,
                vol.Required("medical_expiry"): str,
            })
        )

    async def async_step_briefing(self, user_input=None):
        """Step to configure AI Briefings and Data Retention."""
        if user_input is not None:
            return self.async_create_entry(
                title=f"Briefing: {user_input['email_recipient']}", 
                data={"type": "briefing", **user_input}
            )

        return self.async_show_form(
            step_id="briefing",
            data_schema=vol.Schema({
                vol.Required("airfield_name"): str,
                vol.Required("aircraft_reg"): str,
                vol.Required("briefing_time"): str,
                vol.Required("email_recipient"): str,
                vol.Optional("ai_agent_entity"): str,
                vol.Optional("auto_delete_enabled", default=True): bool,
                vol.Optional("retention_months", default=7): vol.All(
                    vol.Coerce(int), vol.Range(min=1)
                ),
            })
        )