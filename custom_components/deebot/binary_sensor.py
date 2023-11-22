"""Binary sensor module."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic

from deebot_client.capabilities import CapabilityEvent
from deebot_client.events.water_info import WaterInfoEvent
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .controller import DeebotController
from .entity import DeebotEntity, DeebotEntityDescription, EventT


@dataclass(kw_only=True)
class DeebotBinarySensorEntityDescription(
    BinarySensorEntityDescription,  # type: ignore
    DeebotEntityDescription,
    Generic[EventT],
):
    """Class describing Deebot binary sensor entity."""

    value_fn: Callable[[EventT], bool | None]
    icon_fn: Callable[[bool | None], str | None]


ENTITY_DESCRIPTIONS: tuple[DeebotBinarySensorEntityDescription, ...] = (
    DeebotBinarySensorEntityDescription[WaterInfoEvent](
        capability_fn=lambda caps: caps.water,
        value_fn=lambda e: e.mop_attached,
        icon_fn=lambda is_on: "mdi:water" if is_on else "mdi:water-off",
        key="mop_attached",
        translation_key="mop_attached",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    controller: DeebotController = hass.data[DOMAIN][config_entry.entry_id]
    controller.register_platform_add_entities(
        DeebotBinarySensor, ENTITY_DESCRIPTIONS, async_add_entities
    )


class DeebotBinarySensor(DeebotEntity[CapabilityEvent[EventT], DeebotBinarySensorEntityDescription], BinarySensorEntity):  # type: ignore
    """Deebot binary sensor."""

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_event(event: EventT) -> None:
            self._attr_is_on = self.entity_description.value_fn(event)
            self._attr_icon = self.entity_description.icon_fn(self._attr_is_on)
            self.async_write_ha_state()

        self.async_on_remove(
            self._device.events.subscribe(self._capability.event, on_event)
        )
