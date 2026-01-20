import sys
from types import SimpleNamespace
from datetime import datetime, timezone
from unittest.mock import MagicMock

# Minimal stubs for Home Assistant modules to allow config flow tests
class FlowResultType:
    FORM = "form"
    MENU = "menu"
    CREATE_ENTRY = "create_entry"
    ABORT = "abort"


class DataEntryFlowNS:
    RESULT_TYPE_FORM = FlowResultType.FORM
    RESULT_TYPE_MENU = FlowResultType.MENU
    RESULT_TYPE_CREATE_ENTRY = FlowResultType.CREATE_ENTRY
    RESULT_TYPE_ABORT = FlowResultType.ABORT


class OptionsFlow:
    """Stub OptionsFlow/ConfigFlow with helper response builders."""

    @classmethod
    def __init_subclass__(cls, **kwargs):  # noqa: D401 - stub
        return super().__init_subclass__()

    def async_show_form(self, **kwargs):
        return {"type": FlowResultType.FORM, **kwargs}

    def async_show_menu(self, **kwargs):
        return {"type": FlowResultType.MENU, **kwargs}

    def async_create_entry(self, **kwargs):
        return {"type": FlowResultType.CREATE_ENTRY, **kwargs}

    def async_abort(self, **kwargs):
        return {"type": FlowResultType.ABORT, **kwargs}


class HandlerRegistry:
    """No-op registry to satisfy @HANDLERS.register."""

    def register(self, _domain: str):
        def _decorator(cls):
            return cls
        return _decorator


class ConfigEntry:
    """Lightweight ConfigEntry stub for specs."""

    def __init__(self, **kwargs):
        self.data = kwargs.get("data", {}) or {}
        self.options = kwargs.get("options", {}) or {}
        self.title = kwargs.get("title", "")
        self.entry_id = kwargs.get("entry_id", "entry1")
        self.version = kwargs.get("version", 1)
        self.domain = kwargs.get("domain", "hangar_assistant")

    def add_to_hass(self, _hass):
        return None


mock_hass = SimpleNamespace()
config_entries_ns = SimpleNamespace(
    ConfigFlow=OptionsFlow,
    OptionsFlow=OptionsFlow,
    ConfigEntry=ConfigEntry,
    HANDLERS=HandlerRegistry(),
    SOURCE_USER="user",
)
mock_hass.config_entries = config_entries_ns
mock_hass.data_entry_flow = SimpleNamespace(
    FlowResultType=FlowResultType,
    RESULT_TYPE_FORM=FlowResultType.FORM,
    RESULT_TYPE_MENU=FlowResultType.MENU,
    RESULT_TYPE_CREATE_ENTRY=FlowResultType.CREATE_ENTRY,
    RESULT_TYPE_ABORT=FlowResultType.ABORT,
)
mock_hass.helpers = MagicMock()
mock_hass.util = SimpleNamespace(dt=SimpleNamespace(
    utcnow=lambda: datetime.now(timezone.utc),
    now=lambda: datetime.now(timezone.utc),
))
mock_hass.const = MagicMock()

sys.modules["homeassistant"] = mock_hass
sys.modules["homeassistant.data_entry_flow"] = SimpleNamespace(
    FlowResultType=FlowResultType,
    RESULT_TYPE_FORM=FlowResultType.FORM,
    RESULT_TYPE_MENU=FlowResultType.MENU,
    RESULT_TYPE_CREATE_ENTRY=FlowResultType.CREATE_ENTRY,
    RESULT_TYPE_ABORT=FlowResultType.ABORT,
)
sys.modules["homeassistant.components"] = MagicMock()
sys.modules["homeassistant.components.binary_sensor"] = MagicMock()
sys.modules["homeassistant.components.sensor"] = MagicMock()
core_mock = MagicMock()
core_mock.callback = lambda f: f
sys.modules["homeassistant.core"] = core_mock
sys.modules["homeassistant.helpers"] = mock_hass.helpers
sys.modules["homeassistant.util"] = mock_hass.util
sys.modules["homeassistant.const"] = mock_hass.const
sys.modules["homeassistant.helpers.entity"] = MagicMock()
sys.modules["homeassistant.helpers.event"] = MagicMock()
sys.modules["homeassistant.config_entries"] = config_entries_ns
sys.modules["homeassistant.helpers.entity_platform"] = MagicMock()
sys.modules["homeassistant.helpers.typing"] = MagicMock()
sys.modules["homeassistant.helpers.config_validation"] = mock_hass.helpers.config_validation
mock_hass.helpers.config_validation = MagicMock()
sys.modules["homeassistant.helpers.config_validation"] = mock_hass.helpers.config_validation

# Setup specific attributes needed for imports
class BinarySensorEntity:
    """Mock BinarySensorEntity."""
    _attr_has_entity_name = True
    _attr_should_poll = False
    
    @property
    def is_on(self):
        return None

class BinarySensorDeviceClass:
    SAFETY = "safety"
    PROBLEM = "problem"

from homeassistant.components.binary_sensor import BinarySensorEntity as BaseBinarySensorEntity
sys.modules["homeassistant.components.binary_sensor"].BinarySensorEntity = BinarySensorEntity
sys.modules["homeassistant.components.binary_sensor"].BinarySensorDeviceClass = BinarySensorDeviceClass

class SensorEntity:
    """Mock SensorEntity."""
    pass

sys.modules["homeassistant.components.sensor"].SensorEntity = SensorEntity

# DeviceInfo stub
class DeviceInfo(dict):
    """Lightweight DeviceInfo replacement for tests."""

sys.modules["homeassistant.helpers.entity"].DeviceInfo = DeviceInfo

# If the code does `class MySensor(BinarySensorEntity):`, MagicMock is fine.

# Setup dt util
from homeassistant.util import dt as dt_util

# Setup const
mock_hass.const.Platform = MagicMock()
mock_hass.const.Platform.SENSOR = "sensor"
mock_hass.const.Platform.BINARY_SENSOR = "binary_sensor"

# Setup config_validation
mock_hass.helpers.config_validation = MagicMock()
mock_hass.helpers.config_validation.config_entry_only_config_schema = MagicMock(return_value=MagicMock())


import pytest
from unittest.mock import AsyncMock


@pytest.fixture
def hass():
    """Minimal hass fixture for config flow tests."""
    h = MagicMock()
    h.config_entries = MagicMock()
    # Flow init/create entry stubs
    h.config_entries.flow = MagicMock()
    ha_root = sys.modules["homeassistant"]
    h.config_entries.flow.async_init = AsyncMock(return_value={
        "type": ha_root.data_entry_flow.RESULT_TYPE_FORM,
        "step_id": "user",
        "flow_id": "flow1",
    })
    h.config_entries.flow.async_configure = AsyncMock(return_value={
        "type": ha_root.data_entry_flow.RESULT_TYPE_CREATE_ENTRY,
        "title": "Hangar Assistant",
        "data": {},
    })
    h.config_entries.async_setup = AsyncMock(return_value=True)
    h.config_entries.options = MagicMock()
    h.config_entries.options.async_init = AsyncMock(return_value={
        "type": ha_root.data_entry_flow.RESULT_TYPE_MENU,
        "step_id": "init",
    })
    h.states = MagicMock()
    h.config = SimpleNamespace(time_zone="UTC")
    return h


@pytest.fixture
def mock_hass():
    """Generic hass mock with config/time_zone for sensor tests."""
    h = MagicMock()
    h.states = MagicMock()
    h.config = SimpleNamespace(time_zone="UTC")
    return h


@pytest.fixture
def mocker():
    """Provide a simple mocker compat layer."""
    from unittest import mock
    class Mocker:
        MagicMock = mock.MagicMock
        AsyncMock = mock.AsyncMock
        def patch(self, *args, **kwargs):
            p = mock.patch(*args, **kwargs)
            started = p.start()
            return started
    return Mocker()
