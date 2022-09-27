"""Diagnostics support for deebot."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICES, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from . import DOMAIN
from .hub import DeebotHub

REDACT_CONFIG = {CONF_USERNAME, CONF_PASSWORD, CONF_DEVICES, "title"}
REDACT_DEVICE = {"did", "name", "homeId"}


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    hub: DeebotHub = hass.data[DOMAIN][config_entry.entry_id]
    diag: dict[str, Any] = {
        "config": async_redact_data(config_entry.as_dict(), REDACT_CONFIG)
    }

    for bot in hub.vacuum_bots:
        for identifier in device.identifiers:
            if bot.device_info.did == identifier[1]:
                diag["device"] = async_redact_data(bot.device_info, REDACT_DEVICE)
                break

    return diag
