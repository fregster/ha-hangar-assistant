from __future__ import annotations

import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from .const import DOMAIN, DEFAULT_AI_SYSTEM_PROMPT, DEFAULT_DASHBOARD_VERSION, UNIT_PREFERENCE_AVIATION, UNIT_PREFERENCE_SI, DEFAULT_UNIT_PREFERENCE, DEFAULT_SENSOR_CACHE_TTL_SECONDS
from .utils.i18n import get_available_languages, get_distance_unit_options, get_action_options, get_unit_preference_options

_LOGGER = logging.getLogger(__name__)

@config_entries.HANDLERS.register(DOMAIN)
class HangarAssistantConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle initial onboarding for Hangar Assistant.

    This config flow manages the first-time setup and enforces a single configuration
    entry for the integration.

    Inputs:
        - user_input: Optional dict submitted from the initial form (empty payload is
          sufficient to proceed).

    Outputs/Behavior:
        - Creates one blank ConfigEntry that users refine via the Options flow.
        - Aborts with reason "already_configured" if an entry already exists.

    Used by:
        - Devices & Services > Hangar Assistant (Configure button routes to
          HangarOptionsFlowHandler).

    Example:
        - User clicks "Add Integration" → selects Hangar Assistant → flow creates the
          entry and exposes the Configure menu.
    """
    VERSION = 1
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

    @classmethod
    @callback
    def async_get_options_flow(
        cls, config_entry: config_entries.ConfigEntry,
    ) -> HangarOptionsFlowHandler:
        """Directs 'Configure' button clicks to the Options Flow."""
        return HangarOptionsFlowHandler(config_entry)


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

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow.
        
        Args:
            config_entry: The ConfigEntry to manage options for.
        """
        super().__init__()
        # Store config_entry as a private attribute since OptionsFlow manages it as a property
        self._config_entry = config_entry

    def _entry_data(self) -> dict:
        """Return config entry data as a mutable dict, defaulting to empty."""
        return dict(self._config_entry.data or {})

    def _entry_options(self) -> dict:
        """Return config entry options as a mutable dict, defaulting to empty."""
        return dict(self._config_entry.options or {})

    @staticmethod
    def _list_from(value) -> list:
        """Return a safe list copy from stored data."""
        return list(value) if isinstance(value, list) else []

    def _safe_item(self, items: list, index: int) -> dict:
        """Return a dict item at index or an empty dict if out of range/invalid."""
        if 0 <= index < len(items):
            item = items[index]
            return item if isinstance(item, dict) else {}
        return {}

    def _lang(self) -> str:
        """Return the selected UI language (default 'en')."""
        return self._entry_data().get("settings", {}).get("language", "en")

    async def async_step_init(self, _user_input=None):
        """Main configuration menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["airfield", "aircraft", "pilot", "briefing", "global_config"]
        )

    async def async_step_global_config(self, _user_input=None):
        """Sub-menu for global system settings."""
        return self.async_show_menu(
            step_id="global_config",
            menu_options=["settings", "ai", "retention", "dashboard"]
        )

    async def async_step_settings(self, user_input=None):
        """Configure global system settings."""
        if user_input is not None:
            new_data = self._entry_data()
            new_data["settings"] = user_input
            self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        settings = self._entry_data().get("settings", {})

        # Dynamically build language options from available translation files
        language_options = [
            selector.SelectOptionDict(value=code, label=label)
            for code, label in get_available_languages()
        ]

        # Build airfield/aircraft options for default dashboard selection
        airfields = self._list_from(self._entry_data().get("airfields", []))
        aircraft = self._list_from(self._entry_data().get("aircraft", []))
        
        airfield_options = [
            selector.SelectOptionDict(value="", label="None (Auto-detect)")
        ] + [
            selector.SelectOptionDict(
                value=(af.get("name") or "").lower().replace(" ", "_"),
                label=af.get("name", "Unknown")
            ) for af in airfields
        ]
        
        aircraft_options = [
            selector.SelectOptionDict(value="", label="None (Auto-detect)")
        ] + [
            selector.SelectOptionDict(
                value=(ac.get("reg") or "").lower().replace(" ", "_"),
                label=f"{ac.get('type', 'Unknown')} ({ac.get('reg', 'Unknown')})"
            ) for ac in aircraft
        ]

        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema({
                vol.Required("language", default=settings.get("language", "en")): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=language_options,
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required("unit_preference", default=settings.get("unit_preference", DEFAULT_UNIT_PREFERENCE)): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=UNIT_PREFERENCE_AVIATION, label=get_unit_preference_options(self._lang())[0]["label"]),
                            selector.SelectOptionDict(value=UNIT_PREFERENCE_SI, label=get_unit_preference_options(self._lang())[1]["label"]),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Optional("global_pressure_sensor", default=settings.get("global_pressure_sensor")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="pressure")
                ),
                vol.Optional("default_pressure", default=settings.get("default_pressure", 1013.25)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=800, max=1100, step=0.1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="hPa")
                ),
                vol.Optional("cache_ttl_seconds", default=settings.get("cache_ttl_seconds", DEFAULT_SENSOR_CACHE_TTL_SECONDS)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=300, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="s")
                ),
                vol.Optional("default_dashboard_airfield", default=settings.get("default_dashboard_airfield", "")): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=airfield_options,
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Optional("default_dashboard_aircraft", default=settings.get("default_dashboard_aircraft", "")): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=aircraft_options,
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Optional("openweathermap_api_key", default=settings.get("openweathermap_api_key", "")): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                vol.Optional("openweathermap_enabled", default=settings.get("openweathermap_enabled", False)): selector.BooleanSelector(),
                vol.Optional("openweathermap_cache_enabled", default=settings.get("openweathermap_cache_enabled", True)): selector.BooleanSelector(),
                vol.Optional("openweathermap_update_interval", default=settings.get("openweathermap_update_interval", 10)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=5, max=60, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="min")
                ),
                vol.Optional("openweathermap_cache_ttl", default=settings.get("openweathermap_cache_ttl", 10)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=5, max=60, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="min")
                ),
            })
        )

    async def async_step_airfield(self, user_input=None):
        """Sub-menu for airfield management."""
        airfields = self._list_from(self._entry_data().get("airfields", []))
        
        if airfields:
            return self.async_show_menu(
                step_id="airfield",
                menu_options=["airfield_add", "airfield_manage"]
            )
        return await self.async_step_airfield_add()

    async def async_step_airfield_add(self, user_input=None):
        """Form to add a new airfield from scratch."""
        if user_input is not None:
            # Validate ICAO code format if provided
            icao_code = user_input.get("icao_code", "").strip().upper()
            if icao_code:
                if not (len(icao_code) == 4 and icao_code.isalpha()):
                    return self.async_show_form(
                        step_id="airfield_add",
                        errors={"icao_code": "ICAO codes must be exactly 4 uppercase letters (e.g., EGLL, KSFO)"},
                        data_schema=self._get_airfield_add_schema()
                    )
                user_input["icao_code"] = icao_code
            
            # Validate runway format (comma-separated identifiers)
            runways = user_input.get("runways", "").strip()
            if not runways:
                return self.async_show_form(
                    step_id="airfield_add",
                    errors={"runways": "At least one runway must be specified"},
                    data_schema=self._get_airfield_add_schema()
                )
            
            # Validate primary runway is in runway list
            primary = user_input.get("primary_runway", "").strip()
            runway_list = [r.strip() for r in runways.split(",")]
            if primary not in runway_list:
                return self.async_show_form(
                    step_id="airfield_add",
                    errors={"primary_runway": "Primary runway must be one of the available runways"},
                    data_schema=self._get_airfield_add_schema()
                )
            
            new_data = self._entry_data()
            airfields = self._list_from(new_data.get("airfields", []))
            
            # Convert runway_length and elevation from feet to meters if needed
            distance_unit = user_input.pop("distance_unit", "m")
            if distance_unit == "ft":
                user_input["runway_length"] = round(user_input["runway_length"] * 0.3048, 2)
                user_input["elevation"] = round(user_input["elevation"] * 0.3048, 2)
            
            airfields.append(user_input)
            new_data["airfields"] = airfields
            self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        return self.async_show_form(
            step_id="airfield_add",
            data_schema=self._get_airfield_add_schema()
        )
    
    def _get_airfield_add_schema(self) -> vol.Schema:
        """Return the schema for airfield add form."""
        return vol.Schema({
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
            vol.Required("distance_unit", default="m"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=o["value"], label=o["label"]) for o in get_distance_unit_options(self._lang())
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
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
            vol.Optional("temp_sensor"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional("dp_sensor"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional("pressure_sensor"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional("wind_sensor"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional("wind_dir_sensor"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional("radio_frequency"): str,
            vol.Optional("ppl_required", default=False): selector.BooleanSelector(),
            vol.Optional("weather_data_source", default="sensors"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value="sensors", label="Home Assistant Sensors"),
                        selector.SelectOptionDict(value="openweathermap", label="OpenWeatherMap (OWM) Only"),
                        selector.SelectOptionDict(value="hybrid", label="OWM Primary, Sensors Fallback"),
                        selector.SelectOptionDict(value="sensors_backup_owm", label="Sensors Primary, OWM Fallback"),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Optional("use_owm_forecast", default=True): selector.BooleanSelector(),
            vol.Optional("use_owm_alerts", default=True): selector.BooleanSelector(),
        })

    async def async_step_airfield_manage(self, user_input=None):
        """Menu to manage existing airfields."""
        airfields = self._list_from(self._entry_data().get("airfields", []))
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
                            selector.SelectOptionDict(value=o["value"], label=o["label"]) for o in get_action_options(self._lang())
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
            })
        )

    async def async_step_airfield_edit(self, user_input=None):
        """Edit an existing airfield."""
        index = self._index
        airfields = self._list_from(self._entry_data().get("airfields", []))
        airfield = self._safe_item(airfields, index)

        if user_input is not None:
            new_data = self._entry_data()
            airfields = self._list_from(new_data.get("airfields", []))
            
            # Convert runway_length and elevation from feet to meters if needed
            distance_unit = user_input.pop("distance_unit", "m")
            if distance_unit == "ft":
                user_input["runway_length"] = round(user_input["runway_length"] * 0.3048, 2)
                user_input["elevation"] = round(user_input["elevation"] * 0.3048, 2)
            
            airfields[index] = user_input
            new_data["airfields"] = airfields
            self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

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
                vol.Required("distance_unit", default="m"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=o["value"], label=o["label"]) for o in get_distance_unit_options(self._lang())
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
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
                vol.Optional("temp_sensor", default=airfield.get("temp_sensor")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional("dp_sensor", default=airfield.get("dp_sensor")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional("pressure_sensor", default=airfield.get("pressure_sensor")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional("wind_sensor", default=airfield.get("wind_sensor")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional("wind_dir_sensor", default=airfield.get("wind_dir_sensor")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional("radio_frequency", default=airfield.get("radio_frequency", "")): str,
                vol.Optional("ppl_required", default=airfield.get("ppl_required", False)): selector.BooleanSelector(),
                vol.Optional("weather_data_source", default=airfield.get("weather_data_source", "sensors")): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value="sensors", label="Home Assistant Sensors"),
                            selector.SelectOptionDict(value="openweathermap", label="OpenWeatherMap (OWM) Only"),
                            selector.SelectOptionDict(value="hybrid", label="OWM Primary, Sensors Fallback"),
                            selector.SelectOptionDict(value="sensors_backup_owm", label="Sensors Primary, OWM Fallback"),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Optional("use_owm_forecast", default=airfield.get("use_owm_forecast", True)): selector.BooleanSelector(),
                vol.Optional("use_owm_alerts", default=airfield.get("use_owm_alerts", True)): selector.BooleanSelector(),
            })
        )

    async def async_step_airfield_delete(self, user_input=None):
        """Delete an airfield."""
        if user_input is not None:
            if user_input["confirm"]:
                new_data = self._entry_data()
                airfields = self._list_from(new_data.get("airfields", []))
                if 0 <= self._index < len(airfields):
                    airfields.pop(self._index)
                new_data["airfields"] = airfields
                self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        return self.async_show_form(
            step_id="airfield_delete",
            data_schema=vol.Schema({
                vol.Required("confirm", default=False): selector.BooleanSelector()
            }),
            description_placeholders={"name": self._safe_item(self._list_from(self._entry_data().get("airfields", [])), self._index).get("name", "Airfield")}
        )


    async def async_step_aircraft(self, user_input=None):
        """Sub-menu for aircraft management."""
        fleet = self._list_from(self._entry_data().get("aircraft", []))
        
        if fleet:
            return self.async_show_menu(
                step_id="aircraft",
                menu_options=["aircraft_add", "aircraft_manage"]
            )
        return await self.async_step_aircraft_add()

    async def async_step_aircraft_add(self, user_input=None):
        """Form to add a new aircraft."""
        if user_input is not None:
            # Validate registration format (basic alphanumeric check)
            reg = user_input.get("reg", "").strip().upper()
            if not reg or not reg.replace("-", "").isalnum():
                return self.async_show_form(
                    step_id="aircraft_add",
                    errors={"reg": "Registration must contain only letters, numbers, and hyphens"},
                    data_schema=self._get_aircraft_add_schema()
                )
            user_input["reg"] = reg
            
            # Validate weights (empty weight must be less than MTOW)
            empty_weight = float(user_input.get("empty_weight", 0))
            max_tow = float(user_input.get("max_tow", 0))
            weight_unit = user_input.get("weight_unit", "kg")
            
            if empty_weight >= max_tow:
                return self.async_show_form(
                    step_id="aircraft_add",
                    errors={"empty_weight": "Empty weight must be less than MTOW"},
                    data_schema=self._get_aircraft_add_schema()
                )
            
            new_data = self._entry_data()
            fleet = self._list_from(new_data.get("aircraft", []))
            
            # Convert weights from lbs to kg if needed
            weight_unit = user_input.pop("weight_unit", "kg")
            if weight_unit == "lbs":
                user_input["empty_weight"] = round(float(user_input["empty_weight"]) * 0.453592, 2)
                user_input["max_tow"] = round(float(user_input["max_tow"]) * 0.453592, 2)
            
            # Convert distances from feet to meters if needed
            distance_unit = user_input.pop("distance_unit", "m")
            if distance_unit == "ft":
                user_input["baseline_roll"] = round(float(user_input["baseline_roll"]) * 0.3048, 2)
                user_input["baseline_50ft"] = round(float(user_input["baseline_50ft"]) * 0.3048, 2)
            
            fleet.append(user_input)
            new_data["aircraft"] = fleet
            self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        return self.async_show_form(
            step_id="aircraft_add",
            data_schema=self._get_aircraft_add_schema()
        )
    
    def _get_aircraft_add_schema(self) -> vol.Schema:
        """Return the schema for aircraft add form."""
        airfields = [a.get("name", "") for a in self._list_from(self._entry_data().get("airfields", []))]
        airfield_options = [selector.SelectOptionDict(value=a, label=a) for a in airfields] if airfields else [selector.SelectOptionDict(value="", label="No airfields configured")]
        
        return vol.Schema({
            vol.Required("reg"): str,
            vol.Required("model"): str,
            vol.Required("empty_weight", default=750): selector.NumberSelector(
                selector.NumberSelectorConfig(min=500, max=10000, step=50, unit_of_measurement="kg")
            ),
            vol.Required("max_tow", default=1200): selector.NumberSelector(
                selector.NumberSelectorConfig(min=500, max=10000, step=50, unit_of_measurement="kg")
            ),
            vol.Required("weight_unit", default="kg"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value="kg", label="Kilograms"),
                        selector.SelectOptionDict(value="lbs", label="Pounds"),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
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
            vol.Required("distance_unit", default="m"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value="m", label="Meters"),
                        selector.SelectOptionDict(value="ft", label="Feet"),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Optional("linked_airfield"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=airfield_options,
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required("ifr_capable", default=False): selector.BooleanSelector(),
        })

    async def async_step_aircraft_manage(self, user_input=None):
        """Menu to manage existing aircraft."""
        fleet = self._list_from(self._entry_data().get("aircraft", []))
        options = {str(i): f"{a.get('reg', 'Aircraft')} ({a.get('model', 'Unknown')})" for i, a in enumerate(fleet)}

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
                            selector.SelectOptionDict(value=o["value"], label=o["label"]) for o in get_action_options(self._lang())
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
            })
        )

    async def async_step_aircraft_edit(self, user_input=None):
        """Edit an existing aircraft."""
        index = self._index
        fleet = self._list_from(self._entry_data().get("aircraft", []))
        ac = self._safe_item(fleet, index)

        if user_input is not None:
            new_data = self._entry_data()
            fleet = self._list_from(new_data.get("aircraft", []))
            
            # Convert weights from lbs to kg if needed
            weight_unit = user_input.pop("weight_unit", "kg")
            if weight_unit == "lbs":
                user_input["empty_weight"] = round(user_input["empty_weight"] * 0.453592, 2)
                user_input["max_tow"] = round(user_input["max_tow"] * 0.453592, 2)
            
            # Convert distances from feet to meters if needed
            distance_unit = user_input.pop("distance_unit", "m")
            if distance_unit == "ft":
                user_input["baseline_roll"] = round(user_input["baseline_roll"] * 0.3048, 2)
                user_input["baseline_50ft"] = round(user_input["baseline_50ft"] * 0.3048, 2)
            
            fleet[index] = user_input
            new_data["aircraft"] = fleet
            self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        airfields = [a.get("name", "") for a in self._list_from(self._entry_data().get("airfields", []))]
        airfield_options = [selector.SelectOptionDict(value=a, label=a) for a in airfields] if airfields else [selector.SelectOptionDict(value="", label="No airfields configured")]
        
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
                vol.Required("weight_unit", default="kg"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value="kg", label="Kilograms"),
                            selector.SelectOptionDict(value="lbs", label="Pounds"),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
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
                vol.Required("distance_unit", default="m"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value="m", label="Meters"),
                            selector.SelectOptionDict(value="ft", label="Feet"),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Optional("linked_airfield", default=ac.get("linked_airfield")): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=airfield_options,
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
                new_data = self._entry_data()
                fleet = self._list_from(new_data.get("aircraft", []))
                if 0 <= self._index < len(fleet):
                    fleet.pop(self._index)
                new_data["aircraft"] = fleet
                self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        return self.async_show_form(
            step_id="aircraft_delete",
            data_schema=vol.Schema({
                vol.Required("confirm", default=False): selector.BooleanSelector()
            }),
            description_placeholders={"reg": self._safe_item(self._list_from(self._entry_data().get("aircraft", [])), self._index).get("reg", "Aircraft")}
        )

    async def async_step_pilot(self, user_input=None):
        """Sub-menu for pilot management."""
        pilots = self._list_from(self._entry_data().get("pilots", []))
        
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
            new_data = self._entry_data()
            pilots = self._list_from(new_data.get("pilots", []))
            pilots.append(user_input)
            new_data["pilots"] = pilots
            self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        return self.async_show_form(
            step_id="pilot_add",
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Required("email"): str,
                vol.Required("licence_number"): str,
                vol.Required("licence_type"): str,
                vol.Required("medical_expiry"): selector.DateSelector(),
                vol.Required("ifr_rating", default=False): selector.BooleanSelector(),
                vol.Required("night_rating", default=False): selector.BooleanSelector(),
                vol.Required("tailwheel_rating", default=False): selector.BooleanSelector(),
                vol.Required("complex_rating", default=False): selector.BooleanSelector(),
                vol.Required("high_performance_rating", default=False): selector.BooleanSelector(),
                vol.Required("multi_engine_rating", default=False): selector.BooleanSelector(),
                vol.Required("seaplane_rating", default=False): selector.BooleanSelector(),
                vol.Required("glider_rating", default=False): selector.BooleanSelector(),
                vol.Required("aerobatic_rating", default=False): selector.BooleanSelector(),
                vol.Required("mountain_rating", default=False): selector.BooleanSelector(),
            })
        )

    async def async_step_pilot_manage(self, user_input=None):
        """Menu to manage existing pilots."""
        pilots = self._list_from(self._entry_data().get("pilots", []))
        options = {str(i): p.get("name", f"Pilot {i}") for i, p in enumerate(pilots)}

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
                            selector.SelectOptionDict(value=o["value"], label=o["label"]) for o in get_action_options(self._lang())
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
            })
        )

    async def async_step_pilot_edit(self, user_input=None):
        """Edit an existing pilot."""
        index = self._index
        pilots = self._list_from(self._entry_data().get("pilots", []))
        pilot = self._safe_item(pilots, index)

        if user_input is not None:
            new_data = self._entry_data()
            new_pilots = self._list_from(new_data.get("pilots", []))
            new_pilots[index] = user_input
            new_data["pilots"] = new_pilots
            self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        return self.async_show_form(
            step_id="pilot_edit",
            data_schema=vol.Schema({
                vol.Required("name", default=pilot.get("name")): str,
                vol.Required("email", default=pilot.get("email")): str,
                vol.Required("licence_number", default=pilot.get("licence_number")): str,
                vol.Required("licence_type", default=pilot.get("licence_type")): str,
                vol.Required("medical_expiry", default=pilot.get("medical_expiry")): selector.DateSelector(),
                vol.Required("ifr_rating", default=pilot.get("ifr_rating", False)): selector.BooleanSelector(),
                vol.Required("night_rating", default=pilot.get("night_rating", False)): selector.BooleanSelector(),
                vol.Required("tailwheel_rating", default=pilot.get("tailwheel_rating", False)): selector.BooleanSelector(),
                vol.Required("complex_rating", default=pilot.get("complex_rating", False)): selector.BooleanSelector(),
                vol.Required("high_performance_rating", default=pilot.get("high_performance_rating", False)): selector.BooleanSelector(),
                vol.Required("multi_engine_rating", default=pilot.get("multi_engine_rating", False)): selector.BooleanSelector(),
                vol.Required("seaplane_rating", default=pilot.get("seaplane_rating", False)): selector.BooleanSelector(),
                vol.Required("glider_rating", default=pilot.get("glider_rating", False)): selector.BooleanSelector(),
                vol.Required("aerobatic_rating", default=pilot.get("aerobatic_rating", False)): selector.BooleanSelector(),
                vol.Required("mountain_rating", default=pilot.get("mountain_rating", False)): selector.BooleanSelector(),
            })
        )

    async def async_step_pilot_delete(self, user_input=None):
        """Delete a pilot."""
        if user_input is not None:
            if user_input["confirm"]:
                new_data = self._entry_data()
                new_pilots = self._list_from(new_data.get("pilots", []))
                if 0 <= self._index < len(new_pilots):
                    new_pilots.pop(self._index)
                new_data["pilots"] = new_pilots
                self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        return self.async_show_form(
            step_id="pilot_delete",
            data_schema=vol.Schema({
                vol.Required("confirm", default=False): selector.BooleanSelector()
            }),
            description_placeholders={"name": self._safe_item(self._list_from(self._entry_data().get("pilots", [])), self._index).get("name", "Pilot")}
        )

    async def async_step_ai(self, user_input=None):
        """Configure AI conversation assistant (generic across all tools)."""
        if user_input is not None:
            new_data = self._entry_data()
            new_data["ai_assistant"] = user_input
            self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        ai_config = self._entry_data().get("ai_assistant", {})
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

    async def async_step_briefing(self, _user_input=None):
        """Sub-menu for configuring automated briefings."""
        briefings = self._list_from(self._entry_data().get("briefings", []))
        
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
            new_data = self._entry_data()
            briefings = self._list_from(new_data.get("briefings", []))
            briefings.append(user_input)
            new_data["briefings"] = briefings
            self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        # Get existing airfields, aircraft, and pilots for selection
        airfields = [a.get("name", "") for a in self._list_from(self._entry_data().get("airfields", []))]
        aircraft = [a.get("reg", "") for a in self._list_from(self._entry_data().get("aircraft", []))]
        pilots = [p.get("name", "") for p in self._list_from(self._entry_data().get("pilots", []))]

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
        briefings = self._list_from(self._entry_data().get("briefings", []))
        
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
                            selector.SelectOptionDict(value=o["value"], label=o["label"]) for o in get_action_options(self._lang())
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
            })
        )

    async def async_step_briefing_edit(self, user_input=None):
        """Edit an existing automated briefing."""
        index = self._briefing_index
        briefings = self._list_from(self._entry_data().get("briefings", []))
        
        if index >= len(briefings):
            return self.async_abort(reason="reconfigure_successful")
        
        briefing = self._safe_item(briefings, index)

        if user_input is not None:
            new_data = self._entry_data()
            new_briefings = self._list_from(new_data.get("briefings", []))
            new_briefings[index] = user_input
            new_data["briefings"] = new_briefings
            self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        # Get existing airfields, aircraft, and pilots for selection
        airfields = [a.get("name", "") for a in self._list_from(self._entry_data().get("airfields", []))]
        aircraft = [a.get("reg", "") for a in self._list_from(self._entry_data().get("aircraft", []))]
        pilots = [p.get("name", "") for p in self._list_from(self._entry_data().get("pilots", []))]

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
        briefings = self._list_from(self._entry_data().get("briefings", []))
        
        if index >= len(briefings):
            return self.async_abort(reason="reconfigure_successful")
        
        briefing = self._safe_item(briefings, index)

        if user_input is not None:
            if user_input.get("confirm_delete"):
                new_data = self._entry_data()
                new_briefings = self._list_from(new_data.get("briefings", []))
                if 0 <= index < len(new_briefings):
                    new_briefings.pop(index)
                new_data["briefings"] = new_briefings
                self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

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
            if user_input.get("recreate_dashboard", False):
                # Recreate the dashboard directly to avoid service dependencies
                from . import async_create_dashboard

                await async_create_dashboard(
                    self.hass,
                    self._config_entry,
                    force_rebuild=True,
                    reason="options_flow",
                )
            if user_input.get("send_setup_help", False):
                instructions = (
                    "Hangar Assistant dashboard setup\n\n"
                    "1) In configuration.yaml add:\n"
                    "   lovelace:\n"
                    "     dashboards:\n"
                    "       hangar-assistant:\n"
                    "         mode: yaml\n"
                    "         title: Hangar Assistant\n"
                    "         icon: mdi:airplane\n"
                    "         show_in_sidebar: true\n"
                    "         filename: /config/custom_components/hangar_assistant/dashboard_templates/glass_cockpit.yaml\n"
                    "2) Reload dashboards (Settings → Dashboards → …) or restart HA.\n"
                    "3) Ensure input_select.airfield_selector (and optional input_select.aircraft_selector) exist with slugs matching your sensors.\n\n"
                    "An optional automation can listen for the event 'hangar_assistant_dashboard_setup' if you want to hook a script or helper flow."
                )
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": "Hangar Assistant Dashboard",
                        "message": instructions,
                        "notification_id": "hangar_assistant_dashboard_help",
                    },
                    blocking=False,
                )
            if user_input.get("fire_setup_event", False):
                self.hass.bus.async_fire("hangar_assistant_dashboard_setup")
            return self.async_create_entry(data=self._entry_options())

        # Get current dashboard info
        dashboard_info = self._entry_data().get("dashboard_info", {})
        current_version = dashboard_info.get("version", 0)
        last_updated = dashboard_info.get("last_updated", "Never")
        integration_version = dashboard_info.get("integration_version", "Unknown")
        
        return self.async_show_form(
            step_id="dashboard",
            data_schema=vol.Schema({
                vol.Optional("recreate_dashboard", default=False): selector.BooleanSelector(),
                vol.Optional("send_setup_help", default=False): selector.BooleanSelector(),
                vol.Optional("fire_setup_event", default=False): selector.BooleanSelector(),
            }),
            description_placeholders={
                "current_version": str(current_version),
                "template_version": str(DEFAULT_DASHBOARD_VERSION),
                "last_updated": str(last_updated),
                "integration_version": str(integration_version),
            }
        )

    async def async_step_retention(self, user_input=None):
        """Configure data retention policy."""
        if user_input is not None:
            new_data = self._entry_data()
            new_data["retention"] = {
                "auto_delete_enabled": user_input.get("auto_delete_enabled", True),
                "retention_months": user_input.get("retention_months", 7)
            }
            self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
            return self.async_create_entry(data=self._entry_options())

        retention_config = self._entry_data().get("retention", {})
        
        return self.async_show_form(
            step_id="retention",
            data_schema=vol.Schema({
                vol.Optional("auto_delete_enabled", default=retention_config.get("auto_delete_enabled", True)): selector.BooleanSelector(),
                vol.Optional("retention_months", default=retention_config.get("retention_months", 7)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=120, step=1, unit_of_measurement="months")
                ),
            })
        )