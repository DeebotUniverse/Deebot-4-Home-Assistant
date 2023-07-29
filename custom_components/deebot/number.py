"""Number module."""
from deebot_client.commands import SetCleanCount, SetVolume
from deebot_client.events import CleanCountEvent, VolumeEvent
from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from numpy import array_split

from .const import DOMAIN
from .entity import DeebotEntity
from .hub import DeebotHub


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
        new_devices.append(CleanCountEntity(vacbot))

    if new_devices:
        async_add_entities(new_devices)


class VolumeEntity(DeebotEntity, NumberEntity):  # type: ignore
    """Volume number entity."""

    entity_description = NumberEntityDescription(
        key="volume",
        translation_key="volume",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    )

    _attr_native_min_value = 0
    _attr_native_max_value = 10
    _attr_native_step = 1.0
    _attr_native_value: float | None = None

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_volume(event: VolumeEvent) -> None:
            if event.maximum is not None:
                self._attr_native_max_value = event.maximum
            self._attr_native_value = event.volume
            self.async_write_ha_state()

        self.async_on_remove(self._vacuum_bot.events.subscribe(VolumeEvent, on_volume))

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if self._attr_native_value is not None:
            arrays = array_split(
                range(self._attr_native_min_value + 1, self._attr_native_max_value + 1),
                3,
            )
            if self._attr_native_value == self._attr_native_min_value:
                return "mdi:volume-off"
            if self._attr_native_value in arrays[0]:
                return "mdi:volume-low"
            if self._attr_native_value in arrays[1]:
                return "mdi:volume-medium"
            if self._attr_native_value in arrays[2]:
                return "mdi:volume-high"

        return "mdi:volume-medium"

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self._vacuum_bot.execute_command(SetVolume(int(value)))


class CleanCountEntity(DeebotEntity, NumberEntity):  # type: ignore
    """Clean count number entity."""

    entity_description = NumberEntityDescription(
        key="clean_count",
        translation_key="clean_count",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    )

    _attr_native_min_value = 1
    _attr_native_max_value = 4
    _attr_native_step = 1.0
    _attr_native_value: float | None = None
    _attr_icon = "mdi:counter"

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_clean_count(event: CleanCountEvent) -> None:
            self._attr_native_value = event.count
            self.async_write_ha_state()

        self.async_on_remove(
            self._vacuum_bot.events.subscribe(CleanCountEvent, on_clean_count)
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self._vacuum_bot.execute_command(SetCleanCount(int(value)))
