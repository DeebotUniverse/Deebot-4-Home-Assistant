"""Select module."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic

from deebot_client.capabilities import CapabilitySetTypes
from deebot_client.device import Device
from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .controller import DeebotController
from .entity import DeebotEntity, DeebotEntityDescription, EventT


@dataclass(kw_only=True, frozen=True)
class DeebotSelectEntityDescription(
    SelectEntityDescription,  # type: ignore
    DeebotEntityDescription,
    Generic[EventT],
):
    """Deebot select entity description."""

    current_option_fn: Callable[[EventT], str | None]
    options_fn: Callable[[CapabilitySetTypes], list[str]]


ENTITY_DESCRIPTIONS: tuple[DeebotSelectEntityDescription, ...] = (
    DeebotSelectEntityDescription(
        capability_fn=lambda caps: caps.water,
        current_option_fn=lambda e: e.amount.display_name,
        options_fn=lambda water: [amount.display_name for amount in water.types],
        key="water_amount",
        translation_key="water_amount",
        entity_registry_enabled_default=False,
        icon="mdi:water",
        entity_category=EntityCategory.CONFIG,
    ),
    DeebotSelectEntityDescription(
        capability_fn=lambda caps: caps.clean.work_mode,
        current_option_fn=lambda e: e.mode.display_name,
        options_fn=lambda cap: [mode.display_name for mode in cap.types],
        key="work_mode",
        translation_key="work_mode",
        entity_registry_enabled_default=False,
        icon="mdi:cog",
        entity_category=EntityCategory.CONFIG,
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
        DeebotSelectEntity, ENTITY_DESCRIPTIONS, async_add_entities
    )


class DeebotSelectEntity(
    DeebotEntity[CapabilitySetTypes[EventT, str], DeebotSelectEntityDescription],
    SelectEntity,  # type: ignore
):
    """Deebot select entity."""

    _attr_current_option: str | None = None

    def __init__(
        self,
        device: Device,
        capability: CapabilitySetTypes[EventT, str],
        entity_description: DeebotSelectEntityDescription | None = None,
        **kwargs: Any,
    ):
        super().__init__(device, capability, entity_description, **kwargs)
        self._attr_options = self.entity_description.options_fn(capability)

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_water_info(event: EventT) -> None:
            self._attr_current_option = self.entity_description.current_option_fn(event)
            self.async_write_ha_state()

        self.async_on_remove(
            self._device.events.subscribe(self._capability.event, on_water_info)
        )

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self._device.execute_command(self._capability.set(option))
