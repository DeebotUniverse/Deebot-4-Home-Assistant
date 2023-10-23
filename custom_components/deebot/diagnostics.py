"""Diagnostics support for deebot."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICES, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from . import DOMAIN
from .controller import DeebotController

REDACT_CONFIG = {CONF_USERNAME, CONF_PASSWORD, CONF_DEVICES, "title"}
REDACT_DEVICE = {"did", "name", "homeId"}


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    controller: DeebotController = hass.data[DOMAIN][config_entry.entry_id]
    diag: dict[str, Any] = {
        "config": async_redact_data(config_entry.as_dict(), REDACT_CONFIG)
    }

    diag["device"] = async_redact_data(
        controller.get_device_info(device), REDACT_DEVICE
    )

    return diag
