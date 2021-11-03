"""Number module."""
import logging
from typing import List, Optional

from deebot_client.commands import SetVolume
from deebot_client.events import StatusEventDto, VolumeEventDto
from deebot_client.events.event_bus import EventListener
from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from numpy import array_split

from .const import DOMAIN
from .entity import DeebotEntity
from .hub import DeebotHub
from .util import unsubscribe_listeners

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
        new_devices.append(VolumeEntity(vacbot))

    if new_devices:
        async_add_entities(new_devices)


class VolumeEntity(DeebotEntity, NumberEntity):  # type: ignore
    """Volume number entity."""

    entity_description = NumberEntityDescription(
        key="volume",
        entity_registry_enabled_default=False,
    )

    _attr_min_value = 0
    _attr_max_value = 10
    _attr_step = 1.0
    _attr_value = None

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_status(event: StatusEventDto) -> None:
            if not event.available:
                self._attr_value = None
                self.async_write_ha_state()

        async def on_volume(event: VolumeEventDto) -> None:
            if event.maximum is not None:
                self._attr_max_value = event.maximum
            self._attr_value = event.volume
            self.async_write_ha_state()

        listeners: List[EventListener] = [
            self._vacuum_bot.events.subscribe(VolumeEventDto, on_volume),
            self._vacuum_bot.events.subscribe(StatusEventDto, on_status),
        ]
        self.async_on_remove(lambda: unsubscribe_listeners(listeners))

    @property
    def icon(self) -> Optional[str]:
        """Return the icon to use in the frontend, if any."""
        if self._attr_value is not None:
            arrays = array_split(  # type: ignore
                range(self._attr_min_value + 1, self._attr_max_value + 1), 3
            )
            if self._attr_value == self._attr_min_value:
                return "mdi:volume-off"
            if self._attr_value in arrays[0]:
                return "mdi:volume-low"
            if self._attr_value in arrays[1]:
                return "mdi:volume-medium"
            if self._attr_value in arrays[2]:
                return "mdi:volume-high"

        return "mdi:volume-medium"

    async def async_set_value(self, value: float) -> None:
        """Set new value."""
        await self._vacuum_bot.execute_command(SetVolume(int(value)))
