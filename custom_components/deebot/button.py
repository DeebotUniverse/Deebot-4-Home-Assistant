"""Binary sensor module."""
import logging

from deebot_client.commands import ResetLifeSpan, SetRelocationState
from deebot_client.events import LifeSpan
from deebot_client.vacuum_bot import VacuumBot
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
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
        for component in LifeSpan:
            new_devices.append(DeebotResetLifeSpanButtonEntity(vacbot, component))
        new_devices.append(DeebotRelocateButtonEntity(vacbot))

    if new_devices:
        async_add_entities(new_devices)


class DeebotResetLifeSpanButtonEntity(DeebotEntity, ButtonEntity):  # type: ignore
    """Deebot reset life span button entity."""

    def __init__(self, vacuum_bot: VacuumBot, component: LifeSpan):
        entity_description = ButtonEntityDescription(
            key=f"life_span_{component.name.lower()}_reset",
            icon="mdi:air-filter" if component == LifeSpan.FILTER else "mdi:broom",
            entity_registry_enabled_default=True,  # Can be enabled as they don't poll data
            entity_category=EntityCategory.CONFIG,
        )
        super().__init__(vacuum_bot, entity_description)
        self._component = component

    async def async_press(self) -> None:
        """Press the button."""
        await self._vacuum_bot.execute_command(ResetLifeSpan(self._component))


class DeebotRelocateButtonEntity(DeebotEntity, ButtonEntity):  # type: ignore
    """Deebot relocate button entity."""

    entity_description = ButtonEntityDescription(
        key="relocate",
        icon="mdi:map-marker-question",
        entity_registry_enabled_default=True,  # Can be enabled as they don't poll data
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    async def async_press(self) -> None:
        """Press the button."""
        await self._vacuum_bot.execute_command(SetRelocationState())
