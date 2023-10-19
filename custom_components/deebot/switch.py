"""Switch module."""
import logging
from collections.abc import Callable
from typing import Any

from deebot_client.capabilities import Capabilities, CapabilitySetEnable
from deebot_client.events import EnableEvent
from deebot_client.vacuum_bot import VacuumBot
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory, EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import DeebotEntity
from .hub import DeebotHub

_LOGGER = logging.getLogger(__name__)

SWITCHES: set[
    tuple[Callable[[Capabilities], CapabilitySetEnable | None], SwitchEntityDescription]
] = {
    (
        lambda c: c.settings.advanced_mode,
        SwitchEntityDescription(
            key="advanced_mode",
            translation_key="advanced_mode",
            entity_registry_enabled_default=False,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:tune",
        ),
    ),
    (
        lambda c: c.clean.continuous,
        SwitchEntityDescription(
            key="continuous_cleaning",
            translation_key="continuous_cleaning",
            entity_registry_enabled_default=False,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:refresh-auto",
        ),
    ),
    (
        lambda c: c.settings.carpet_auto_fan_boost,
        SwitchEntityDescription(
            key="carpet_auto_fan_speed_boost",
            translation_key="carpet_auto_fan_speed_boost",
            entity_registry_enabled_default=False,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:fan-auto",
        ),
    ),
    (
        lambda c: c.clean.preference,
        SwitchEntityDescription(
            key="clean_preference",
            translation_key="clean_preference",
            entity_registry_enabled_default=False,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:broom",
        ),
    ),
    (
        lambda c: c.settings.true_detect,
        SwitchEntityDescription(
            key="true_detect",
            translation_key="true_detect",
            entity_registry_enabled_default=False,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:laser-pointer",
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    hub: DeebotHub = hass.data[DOMAIN][config_entry.entry_id]

    new_entities = []
    for vacbot in hub.vacuum_bots:
        for cap_fn, description in SWITCHES:
            if cap := cap_fn(vacbot.capabilities):
                new_entities.append(DeebotSwitchEntity(vacbot, description, cap))

    if new_entities:
        async_add_entities(new_entities)


class DeebotSwitchEntity(DeebotEntity, SwitchEntity):  # type: ignore
    """Deebot switch entity."""

    _attr_is_on = False

    def __init__(
        self,
        vacuum_bot: VacuumBot,
        entity_description: EntityDescription,
        capability: CapabilitySetEnable,
    ):
        super().__init__(vacuum_bot, entity_description)
        self._capability = capability

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_enable(event: EnableEvent) -> None:
            self._attr_is_on = event.enable
            self.async_write_ha_state()

        self.async_on_remove(
            self._vacuum_bot.events.subscribe(self._capability.event, on_enable)
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._vacuum_bot.execute_command(self._capability.set(True))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._vacuum_bot.execute_command(self._capability.set(False))
