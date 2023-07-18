"""Select module."""
import logging

from deebot_client.commands import SetWaterInfo
from deebot_client.events import WaterAmount, WaterInfoEvent
from homeassistant.components.select import SelectEntity, SelectEntityDescription
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
        new_devices.append(WaterInfoSelect(vacbot))

    if new_devices:
        async_add_entities(new_devices)


class WaterInfoSelect(DeebotEntity, SelectEntity):  # type: ignore
    """Water info select entity."""

    entity_description = SelectEntityDescription(
        key="water_amount",
        translation_key="water_amount",
        entity_registry_enabled_default=False,
        icon="mdi:water",
        entity_category=EntityCategory.CONFIG,
    )

    _attr_options = [amount.display_name for amount in WaterAmount]
    _attr_current_option: str | None = None

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_water_info(event: WaterInfoEvent) -> None:
            self._attr_current_option = event.amount.display_name
            self.async_write_ha_state()

        self.async_on_remove(
            self._vacuum_bot.events.subscribe(WaterInfoEvent, on_water_info)
        )

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self._vacuum_bot.execute_command(SetWaterInfo(option))
