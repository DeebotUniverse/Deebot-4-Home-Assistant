"""Deebot entity module."""
from deebot_client.events import StatusEvent
from deebot_client.events.event_bus import EventListener
from deebot_client.vacuum_bot import VacuumBot
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription

from . import DOMAIN


class DeebotEntity(Entity):  # type: ignore # lgtm [py/missing-equals]
    """Deebot entity."""

    _attr_should_poll = False
    _always_available: bool = False
    _attr_has_entity_name = True

    def __init__(
        self,
        vacuum_bot: VacuumBot,
        entity_description: EntityDescription | None = None,
    ):
        """Initialize the Sensor."""
        super().__init__()
        if entity_description:
            self.entity_description = entity_description
        elif not hasattr(self, "entity_description"):
            raise ValueError(
                '"entity_description" must be either set as class variable or passed on init!'
            )

        self._vacuum_bot: VacuumBot = vacuum_bot

        device_info = self._vacuum_bot.device_info
        self._attr_unique_id = device_info.did

        if self.entity_description.key:
            self._attr_unique_id += f"_{self.entity_description.key}"

        if self.entity_description.name:
            # Name provided, using the provided one
            return

        if self.entity_description.key != "":
            self._attr_name = self.entity_description.key.replace("_", " ").capitalize()

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device specific attributes."""
        device = self._vacuum_bot.device_info
        info = DeviceInfo(
            default_name="Deebot vacuum",
            identifiers={(DOMAIN, device.did)},
            manufacturer="Ecovacs",
            sw_version=self._vacuum_bot.fw_version,
        )

        if "nick" in device:
            info["name"] = device["nick"]

        if "deviceName" in device:
            info["model"] = device["deviceName"]

        return info

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        if not self._always_available:

            async def on_status(event: StatusEvent) -> None:
                self._attr_available = event.available
                self.async_write_ha_state()

            listener: EventListener = self._vacuum_bot.events.subscribe(
                StatusEvent, on_status
            )
            self.async_on_remove(listener.unsubscribe)
