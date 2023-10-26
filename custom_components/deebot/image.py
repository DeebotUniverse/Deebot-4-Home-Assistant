"""Support for Deebot image entities."""
import base64
from collections.abc import MutableMapping, Sequence
from typing import Any

from deebot_client.capabilities import CapabilityMap
from deebot_client.device import Device
from deebot_client.events.map import CachedMapInfoEvent, MapChangedEvent
from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .controller import DeebotController
from .entity import DeebotEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    controller: DeebotController = hass.data[DOMAIN][config_entry.entry_id]

    def image_entity_generator(
        device: Device,
    ) -> Sequence[DeebotMap]:
        new_entities = []
        if caps := device.capabilities.map:
            new_entities.append(DeebotMap(hass, device, caps))

        return new_entities

    controller.register_platform_add_entities_generator(
        async_add_entities, image_entity_generator
    )


class DeebotMap(
    DeebotEntity[CapabilityMap, EntityDescription],
    ImageEntity,  # type: ignore
):
    """Deebot map."""

    _attr_should_poll = True

    def __init__(self, hass: HomeAssistant, device: Device, capability: CapabilityMap):
        super().__init__(
            device,
            capability,
            EntityDescription(
                key="map",
                translation_key="map",
                entity_registry_enabled_default=False,
            ),
            hass=hass,
        )
        self._attr_extra_state_attributes: MutableMapping[str, Any] = {}

    def image(self) -> bytes | None:
        """Return bytes of image."""
        return base64.decodebytes(self._device.map.get_base64_map())

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        self._device.map.enable()

        async def on_info(event: CachedMapInfoEvent) -> None:
            self._attr_extra_state_attributes["map_name"] = event.name

        async def on_changed(event: MapChangedEvent) -> None:
            self._attr_image_last_updated = event.when
            self.async_write_ha_state()

        subscriptions = [
            self._device.events.subscribe(self._capability.chached_info.event, on_info),
            self._device.events.subscribe(self._capability.changed.event, on_changed),
        ]

        def on_remove() -> None:
            for unsubscribe in subscriptions:
                unsubscribe()
            self._device.map.disable()

        self.async_on_remove(on_remove)
