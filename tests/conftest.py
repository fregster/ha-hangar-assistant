import sys
from unittest.mock import MagicMock

# Create mocks for Home Assistant modules
mock_hass = MagicMock()
sys.modules["homeassistant"] = mock_hass
sys.modules["homeassistant.components"] = MagicMock()
sys.modules["homeassistant.components.binary_sensor"] = MagicMock()
sys.modules["homeassistant.components.sensor"] = MagicMock()
sys.modules["homeassistant.core"] = MagicMock()
sys.modules["homeassistant.helpers"] = MagicMock()
sys.modules["homeassistant.helpers.entity"] = MagicMock()
sys.modules["homeassistant.helpers.event"] = MagicMock()
sys.modules["homeassistant.config_entries"] = MagicMock()
sys.modules["homeassistant.helpers.entity_platform"] = MagicMock()
sys.modules["homeassistant.util"] = MagicMock()
sys.modules["homeassistant.helpers.typing"] = MagicMock()
sys.modules["homeassistant.helpers.config_validation"] = MagicMock()
sys.modules["homeassistant.const"] = MagicMock()

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

from homeassistant.components.binary_sensor import BinarySensorEntity as BaseBinarySensorEntity
sys.modules["homeassistant.components.binary_sensor"].BinarySensorEntity = BinarySensorEntity
sys.modules["homeassistant.components.binary_sensor"].BinarySensorDeviceClass = BinarySensorDeviceClass

class SensorEntity:
    """Mock SensorEntity."""
    pass

sys.modules["homeassistant.components.sensor"].SensorEntity = SensorEntity

# If the code does `class MySensor(BinarySensorEntity):`, MagicMock is fine.

# Setup dt util
from homeassistant.util import dt as dt_util
# We might need to configure this mock in tests, but basic structure is there.

# Setup const
import homeassistant.const
homeassistant.const.Platform = MagicMock()
homeassistant.const.Platform.SENSOR = "sensor"
homeassistant.const.Platform.BINARY_SENSOR = "binary_sensor"

# Setup config_validation
import homeassistant.helpers.config_validation
homeassistant.helpers.config_validation.config_entry_only_config_schema = MagicMock(return_value=MagicMock())
