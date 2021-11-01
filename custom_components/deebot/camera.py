"""Support for Deebot Vaccums."""
import base64
import logging
from typing import Any, Dict, Optional

from deebot_client.events import MapEventDto
from deebot_client.events.event_bus import EventListener
from deebot_client.vacuum_bot import VacuumBot
from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .helpers import get_device_info
from .hub import DeebotHub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    hub: DeebotHub = hass.data[DOMAIN][config_entry.entry_id]

    new_devices = []

    for vacbot in hub.vacuum_bots:
        new_devices.append(DeeboLiveCamera(vacbot, "liveMap"))

    if new_devices:
        async_add_entities(new_devices)


class DeeboLiveCamera(Camera):  # type: ignore
    """Deebot Live Camera."""

    _attr_entity_registry_enabled_default = False

    def __init__(self, vacuum_bot: VacuumBot, sensor_name: str):
        """Initialize the camera."""
        super().__init__()
        self._vacuum_bot: VacuumBot = vacuum_bot

        if self._vacuum_bot.device_info.nick is not None:
            name: str = self._vacuum_bot.device_info.nick
        else:
            # In case there is no nickname defined, use the device id
            name = self._vacuum_bot.device_info.did

        self._attr_name = f"{name}_{sensor_name}"
        self._attr_unique_id = f"{self._vacuum_bot.device_info.did}_{sensor_name}"

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        """Return device specific attributes."""
        return get_device_info(self._vacuum_bot)

    async def async_camera_image(
        self, width: Optional[int] = None, height: Optional[int] = None
    ) -> Optional[bytes]:
        """Return a still image response from the camera.

        Integrations may choose to ignore the height parameter in order to preserve aspect ratio
        """

        return base64.decodebytes(self._vacuum_bot.map.get_base64_map(width))

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_event(_: MapEventDto) -> None:
            self.schedule_update_ha_state()

        listener: EventListener = self._vacuum_bot.events.subscribe(
            MapEventDto, on_event
        )
        self.async_on_remove(listener.unsubscribe)
