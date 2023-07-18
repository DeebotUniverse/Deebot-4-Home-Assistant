"""Support for Deebot Vaccums."""
import base64
import logging
from collections.abc import MutableMapping
from typing import Any

from deebot_client.events.map import CachedMapInfoEvent, MapChangedEvent
from deebot_client.vacuum_bot import VacuumBot
from homeassistant.components.image import ImageEntity
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
        new_devices.append(DeebotMap(hass, vacbot))

    if new_devices:
        async_add_entities(new_devices)


class DeebotMap(DeebotEntity, ImageEntity):  # type: ignore
    """Deebot map."""

    entity_description = EntityDescription(
        key="map",
        translation_key="map",
        entity_registry_enabled_default=False,
    )

    _attr_should_poll = True

    def __init__(
        self,
        hass: HomeAssistant,
        vacuum_bot: VacuumBot,
    ):
        super().__init__(vacuum_bot, hass=hass)
        self._attr_extra_state_attributes: MutableMapping[str, Any] = {}

    def image(self) -> bytes | None:
        """Return bytes of image."""
        return base64.decodebytes(self._vacuum_bot.map.get_base64_map())

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        self._vacuum_bot.map.enable()

        async def on_info(event: CachedMapInfoEvent) -> None:
            self._attr_extra_state_attributes["map_name"] = event.name

        async def on_changed(event: MapChangedEvent) -> None:
            self._attr_image_last_updated = event.when
            self.async_write_ha_state()

        subscriptions = [
            self._vacuum_bot.events.subscribe(CachedMapInfoEvent, on_info),
            self._vacuum_bot.events.subscribe(MapChangedEvent, on_changed),
        ]

        def on_remove() -> None:
            for unsubscribe in subscriptions:
                unsubscribe()
            self._vacuum_bot.map.disable()

        self.async_on_remove(on_remove)
