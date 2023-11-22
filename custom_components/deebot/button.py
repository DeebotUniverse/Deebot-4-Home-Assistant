"""Binary sensor module."""
from collections.abc import Sequence
from dataclasses import dataclass

from deebot_client.capabilities import CapabilityExecute
from deebot_client.device import Device
from deebot_client.events import LifeSpan
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .controller import DeebotController
from .entity import DeebotEntity, DeebotEntityDescription


@dataclass(kw_only=True)
class DeebotButtonEntityDescription(
    ButtonEntityDescription,  # type: ignore
    DeebotEntityDescription,
):
    """Class describing debbot button entity."""


ENTITY_DESCRIPTIONS: tuple[DeebotButtonEntityDescription, ...] = (
    DeebotButtonEntityDescription(
        capability_fn=lambda caps: caps.map.relocation if caps.map else None,
        key="relocate",
        translation_key="relocate",
        icon="mdi:map-marker-question",
        entity_registry_enabled_default=True,  # Can be enabled as they don't poll data
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
        DeebotButtonEntity, ENTITY_DESCRIPTIONS, async_add_entities
    )

    def generate_reset_life_span(
        device: Device,
    ) -> Sequence[DeebotResetLifeSpanButtonEntity]:
        return [
            DeebotResetLifeSpanButtonEntity(device, component)
            for component in device.capabilities.life_span.types
        ]

    controller.register_platform_add_entities_generator(
        async_add_entities, generate_reset_life_span
    )


class DeebotResetLifeSpanButtonEntity(
    DeebotEntity[None, ButtonEntityDescription],
    ButtonEntity,  # type: ignore
):
    """Deebot reset life span button entity."""

    def __init__(self, device: Device, component: LifeSpan):
        key = f"life_span_{component.name.lower()}_reset"
        entity_description = ButtonEntityDescription(
            key=key,
            translation_key=key,
            icon="mdi:air-filter" if component == LifeSpan.FILTER else "mdi:broom",
            entity_registry_enabled_default=True,  # Can be enabled as they don't poll data
            entity_category=EntityCategory.CONFIG,
        )
        super().__init__(device, None, entity_description)
        self._command = device.capabilities.life_span.reset(component)

    async def async_press(self) -> None:
        """Press the button."""
        await self._device.execute_command(self._command)


class DeebotButtonEntity(
    DeebotEntity[CapabilityExecute, DeebotButtonEntityDescription],
    ButtonEntity,  # type: ignore
):
    """Deebot button entity."""

    async def async_press(self) -> None:
        """Press the button."""
        await self._device.execute_command(self._capability.execute())
