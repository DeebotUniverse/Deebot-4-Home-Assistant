"""Helpers module."""

from homeassistant.core import HomeAssistant
from homeassistant.util import uuid


def get_bumper_device_id(hass: HomeAssistant) -> str:
    """Return bumper device id."""
    try:
        location_name = hass.config.location_name.strip().replace(" ", "_")
    except Exception:  # pylint: disable=broad-except
        location_name = ""
    return f"Deebot-4-HA_{location_name}_{uuid.random_uuid_hex()[:4]}"
