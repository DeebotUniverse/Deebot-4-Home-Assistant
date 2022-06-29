"""Support for Deebot Vaccums."""
import base64
import logging

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import DeebotEntity
from .hub import DeebotHub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    hub: DeebotHub = hass.data[DOMAIN][config_entry.entry_id]

    new_devices = []

    for vacbot in hub.vacuum_bots:
        new_devices.append(DeeboLiveCamera(vacbot))

    if new_devices:
        async_add_entities(new_devices)


class DeeboLiveCamera(DeebotEntity, Camera):  # type: ignore
    """Deebot Live Camera."""

    entity_description = EntityDescription(
        key="live_map", entity_registry_enabled_default=False
    )

    _attr_should_poll = True

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera.

        Integrations may choose to ignore the height parameter in order to preserve aspect ratio
        """

        return base64.decodebytes(self._vacuum_bot.map.get_base64_map(width))

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        self._vacuum_bot.map.enable()

        def disable() -> None:
            self._vacuum_bot.map.disable()

        self.async_on_remove(disable)
