"""Deebot entity module."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from deebot_client.capabilities import Capabilities
from deebot_client.device import Device
from deebot_client.events import AvailabilityEvent
from deebot_client.events.base import Event
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription

from .const import DOMAIN

_EntityDescriptionT = TypeVar("_EntityDescriptionT", bound=EntityDescription)
CapabilityT = TypeVar("CapabilityT")
EventT = TypeVar("EventT", bound=Event)


@dataclass
class DeebotDescription(Generic[CapabilityT]):
    """Deebot description."""

    capability_fn: Callable[[Capabilities], CapabilityT | None]


@dataclass
class DeebotEntityDescription(
    EntityDescription,  # type: ignore
    DeebotDescription[CapabilityT],
):
    """Deebot Entity Description."""

    always_available: bool = False


class DeebotEntity(Entity, Generic[CapabilityT, _EntityDescriptionT]):  # type: ignore
    """Deebot entity."""

    entity_description: _EntityDescriptionT

    _attr_should_poll = False
    _always_available: bool = False
    _attr_has_entity_name = True

    def __init__(
        self,
        device: Device,
        capability: CapabilityT,
        entity_description: _EntityDescriptionT | None = None,
        **kwargs: Any,
    ):
        """Initialize entity."""
        super().__init__(**kwargs)
        if entity_description:
            self.entity_description = entity_description
        elif not hasattr(self, "entity_description"):
            raise ValueError(
                '"entity_description" must be either set as class variable or passed on init!'
            )

        self._device = device
        self._capability = capability

        device_info = self._device.device_info
        self._attr_unique_id = device_info.did

        if self.entity_description.key:
            self._attr_unique_id += f"_{self.entity_description.key}"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device specific attributes."""
        device = self._device.device_info
        info = DeviceInfo(
            identifiers={(DOMAIN, device.did)},
            manufacturer="Ecovacs",
            sw_version=self._device.fw_version,
        )

        if nick := device.api_device_info.get("nick"):
            info["name"] = nick

        if model := device.api_device_info.get("deviceName"):
            info["model"] = model

        return info

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        if not self._always_available:

            async def on_available(event: AvailabilityEvent) -> None:
                self._attr_available = event.available
                self.async_write_ha_state()

            self.async_on_remove(
                self._device.events.subscribe(AvailabilityEvent, on_available)
            )
