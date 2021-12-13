"""Util module."""
import dataclasses
from enum import Enum
from typing import Any

from deebot_client.events.event_bus import EventListener
from deebot_client.util import DisplayNameIntEnum
from homeassistant.core import HomeAssistant
from homeassistant.util import uuid


def unsubscribe_listeners(listeners: list[EventListener]) -> None:
    """Unsubscribe from all listeners."""
    for listener in listeners:
        listener.unsubscribe()


def get_bumper_device_id(hass: HomeAssistant) -> str:
    """Return bumper device id."""
    try:
        location_name = hass.config.location_name.strip().replace(" ", "_")
    except Exception:  # pylint: disable=broad-except
        location_name = ""
    return f"Deebot-4-HA_{location_name}_{uuid.random_uuid_hex()[:4]}"


def dataclass_to_dict(obj: Any) -> dict[str, Any]:
    """Convert dataclass to dict and remove None fields."""
    dic = dataclasses.asdict(obj)
    for key, value in dic.copy().items():
        if value is None:
            dic.pop(key)
        elif isinstance(value, Enum):
            if isinstance(value, DisplayNameIntEnum):
                dic[key] = value.display_name
            else:
                dic[key] = value.value

    return dic
