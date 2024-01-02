"""Switch module."""
from dataclasses import dataclass
from typing import Any

from deebot_client.capabilities import CapabilitySetEnable
from deebot_client.events import EnableEvent
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .controller import DeebotController
from .entity import DeebotEntity, DeebotEntityDescription


@dataclass(kw_only=True, frozen=True)
class DeebotSwitchEntityDescription(
    SwitchEntityDescription,  # type: ignore
    DeebotEntityDescription,
):
    """Deebot switch entity description."""


ENTITY_DESCRIPTIONS: tuple[DeebotSwitchEntityDescription, ...] = (
    DeebotSwitchEntityDescription(
        capability_fn=lambda c: c.settings.advanced_mode,
        key="advanced_mode",
        translation_key="advanced_mode",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:tune",
    ),
    DeebotSwitchEntityDescription(
        capability_fn=lambda c: c.clean.continuous,
        key="continuous_cleaning",
        translation_key="continuous_cleaning",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:refresh-auto",
    ),
    DeebotSwitchEntityDescription(
        capability_fn=lambda c: c.settings.carpet_auto_fan_boost,
        key="carpet_auto_fan_speed_boost",
        translation_key="carpet_auto_fan_speed_boost",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:fan-auto",
    ),
    DeebotSwitchEntityDescription(
        capability_fn=lambda c: c.clean.preference,
        key="clean_preference",
        translation_key="clean_preference",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:broom",
    ),
    DeebotSwitchEntityDescription(
        capability_fn=lambda c: c.settings.true_detect,
        key="true_detect",
        translation_key="true_detect",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:laser-pointer",
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
        DeebotSwitchEntity, ENTITY_DESCRIPTIONS, async_add_entities
    )


class DeebotSwitchEntity(
    DeebotEntity[CapabilitySetEnable, DeebotSwitchEntityDescription],
    SwitchEntity,  # type: ignore
):
    """Deebot switch entity."""

    _attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_event(event: EnableEvent) -> None:
            self._attr_is_on = event.enable
            self.async_write_ha_state()

        self._subscribe(self._capability.event, on_event)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._device.execute_command(self._capability.set(True))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._device.execute_command(self._capability.set(False))
