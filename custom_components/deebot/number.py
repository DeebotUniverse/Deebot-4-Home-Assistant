"""Number module."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic

from deebot_client.capabilities import CapabilitySet
from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from numpy import array_split

from .const import DOMAIN
from .controller import DeebotController
from .entity import DeebotEntity, DeebotEntityDescription, EventT


@dataclass(kw_only=True, frozen=True)
class DeebotNumberEntityDescription(
    NumberEntityDescription,  # type: ignore
    DeebotEntityDescription,
    Generic[EventT],
):
    """Deebot number entity description."""

    icon_fn: Callable[["DeebotNumberEntity"], str | None] = lambda _: None
    native_max_value_fn: Callable[[EventT], float | None] = lambda _: None
    value_fn: Callable[[EventT], float | None]


def _volume_icon(instance: "DeebotNumberEntity") -> str | None:
    """Return the icon for the volume number."""
    value = instance.native_value
    if value is not None:
        min_value = instance.native_min_value

        arrays = array_split(range(min_value + 1, instance.native_max_value + 1), 3)
        if value == min_value:
            return "mdi:volume-off"
        if value in arrays[0]:
            return "mdi:volume-low"
        if value in arrays[1]:
            return "mdi:volume-medium"
        if value in arrays[2]:
            return "mdi:volume-high"

    return "mdi:volume-medium"


ENTITY_DESCRIPTIONS: tuple[DeebotNumberEntityDescription, ...] = (
    DeebotNumberEntityDescription(
        capability_fn=lambda caps: caps.settings.volume,
        value_fn=lambda e: e.volume,
        native_max_value_fn=lambda e: e.maximum if e.maximum else None,
        key="volume",
        translation_key="volume",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=10,
        native_step=1.0,
        icon_fn=_volume_icon,
    ),
    DeebotNumberEntityDescription(
        capability_fn=lambda caps: caps.clean.count,
        value_fn=lambda e: e.count,
        key="clean_count",
        translation_key="clean_count",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        native_min_value=1,
        native_max_value=4,
        native_step=1.0,
        icon="mdi:counter",
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
        DeebotNumberEntity, ENTITY_DESCRIPTIONS, async_add_entities
    )


class DeebotNumberEntity(
    DeebotEntity[CapabilitySet[EventT, int], DeebotNumberEntityDescription],
    NumberEntity,  # type: ignore
):
    """Deebot number entity."""

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_event(event: EventT) -> None:
            self._attr_native_value = self.entity_description.value_fn(event)
            if maximum := self.entity_description.native_max_value_fn(event):
                self._attr_native_max_value = maximum
            if icon := self.entity_description.icon_fn(self):
                self._attr_icon = icon
            self.async_write_ha_state()

        self._subscribe(self._capability.event, on_event)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self._device.execute_command(self._capability.set(int(value)))
