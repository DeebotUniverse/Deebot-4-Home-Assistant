"""Support for Deebot Vacuums."""
import logging
from collections.abc import Mapping, Sequence
from typing import Any

import voluptuous as vol
from deebot_client.capabilities import Capabilities
from deebot_client.device import Device
from deebot_client.events import (
    BatteryEvent,
    CustomCommandEvent,
    FanSpeedEvent,
    ReportStatsEvent,
    RoomsEvent,
    StateEvent,
)
from deebot_client.models import CleanAction, CleanMode, Room, State
from homeassistant.components.vacuum import (
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    StateVacuumEntity,
    StateVacuumEntityDescription,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.config_validation import make_entity_service_schema
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import (
    DOMAIN,
    EVENT_CLEANING_JOB,
    EVENT_CUSTOM_COMMAND,
    REFRESH_MAP,
    REFRESH_STR_TO_EVENT_DTO,
)
from .controller import DeebotController
from .entity import DeebotEntity
from .util import dataclass_to_dict

_LOGGER = logging.getLogger(__name__)

_STATE_TO_VACUUM_STATE = {
    State.IDLE: STATE_IDLE,
    State.CLEANING: STATE_CLEANING,
    State.RETURNING: STATE_RETURNING,
    State.DOCKED: STATE_DOCKED,
    State.ERROR: STATE_ERROR,
    State.PAUSED: STATE_PAUSED,
}


# Must be kept in sync with services.yaml
SERVICE_REFRESH = "refresh"
SERVICE_REFRESH_CATEGORY = "category"
SERVICE_REFRESH_SCHEMA = make_entity_service_schema(
    {
        vol.Required(SERVICE_REFRESH_CATEGORY): vol.In(
            [*REFRESH_STR_TO_EVENT_DTO.keys(), REFRESH_MAP]
        )
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    controller: DeebotController = hass.data[DOMAIN][config_entry.entry_id]

    def vacuum_entity_generator(
        device: Device,
    ) -> Sequence[DeebotVacuum]:
        return [DeebotVacuum(device)]

    controller.register_platform_add_entities_generator(
        async_add_entities, vacuum_entity_generator
    )

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_REFRESH,
        SERVICE_REFRESH_SCHEMA,
        "service_refresh",
    )


_ATTR_ROOMS = "rooms"


class DeebotVacuum(
    DeebotEntity[Capabilities, StateVacuumEntityDescription],
    StateVacuumEntity,  # type: ignore
):
    """Deebot Vacuum."""

    _unrecorded_attributes = frozenset({_ATTR_ROOMS})

    _attr_supported_features = (
        VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.SEND_COMMAND
        | VacuumEntityFeature.LOCATE
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.START
    )

    def __init__(self, device: Device):
        """Initialize the Deebot Vacuum."""
        capabilities = device.capabilities
        super().__init__(
            device,
            capabilities,
            StateVacuumEntityDescription(key="", translation_key="bot", name=None),
        )

        self._rooms: list[Room] = []

        self._attr_fan_speed_list = [
            level.display_name for level in capabilities.fan_speed.types
        ]

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_battery(event: BatteryEvent) -> None:
            self._attr_battery_level = event.value
            self.async_write_ha_state()

        async def on_custom_command(event: CustomCommandEvent) -> None:
            self.hass.bus.fire(EVENT_CUSTOM_COMMAND, dataclass_to_dict(event))

        async def on_fan_speed(event: FanSpeedEvent) -> None:
            self._attr_fan_speed = event.speed.display_name
            self.async_write_ha_state()

        async def on_report_stats(event: ReportStatsEvent) -> None:
            self.hass.bus.fire(EVENT_CLEANING_JOB, dataclass_to_dict(event))

        async def on_rooms(event: RoomsEvent) -> None:
            self._rooms = event.rooms
            self.async_write_ha_state()

        async def on_status(event: StateEvent) -> None:
            self._attr_state = _STATE_TO_VACUUM_STATE[event.state]
            self.async_write_ha_state()

        subscriptions = [
            self._device.events.subscribe(self._capability.battery.event, on_battery),
            self._device.events.subscribe(
                self._capability.fan_speed.event, on_fan_speed
            ),
            self._device.events.subscribe(
                self._capability.stats.report.event, on_report_stats
            ),
            self._device.events.subscribe(self._capability.state.event, on_status),
        ]

        if custom := self._capability.custom:
            subscriptions.append(
                self._device.events.subscribe(custom.event, on_custom_command)
            )
        if map_caps := self._capability.map:
            subscriptions.append(
                self._device.events.subscribe(map_caps.rooms.event, on_rooms)
            )

        def unsubscribe() -> None:
            for sub in subscriptions:
                sub()

        self.async_on_remove(unsubscribe)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes.

        Implemented by platform classes. Convention for attribute names
        is lowercase snake_case.
        """
        attributes: dict[str, Any] = {}
        rooms: dict[str, Any] = {}
        for room in self._rooms:
            # convert room name to snake_case to meet the convention
            room_name = slugify(room.name)
            room_values = rooms.get(room_name)
            if room_values is None:
                rooms[room_name] = room.id
            elif isinstance(room_values, list):
                room_values.append(room.id)
            else:
                # Convert from int to list
                rooms[room_name] = [room_values, room.id]

        if rooms:
            attributes[_ATTR_ROOMS] = rooms

        return attributes

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        await self._device.execute_command(self._capability.fan_speed.set(fan_speed))

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""
        await self._device.execute_command(self._capability.charge.execute())

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner."""
        await self._clean_command(CleanAction.STOP)

    async def async_pause(self) -> None:
        """Pause the vacuum cleaner."""
        await self._clean_command(CleanAction.PAUSE)

    async def async_start(self) -> None:
        """Start the vacuum cleaner."""
        await self._clean_command(CleanAction.START)

    async def _clean_command(self, action: CleanAction) -> None:
        await self._device.execute_command(
            self._capability.clean.action.command(action)
        )

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate the vacuum cleaner."""
        await self._device.execute_command(self._capability.play_sound.execute())

    async def async_send_command(
        self, command: str, params: dict[str, Any] | None = None, **kwargs: Any
    ) -> None:
        """Send a command to a vacuum cleaner."""
        _LOGGER.debug("async_send_command %s with %s", command, params)

        if command in ["spot_area", "custom_area"]:
            if params is None:
                raise RuntimeError("Params are required!")

            if command in "spot_area":
                await self._device.execute_command(
                    self._capability.clean.action.area(
                        CleanMode.SPOT_AREA,
                        str(params["rooms"]),
                        params.get("cleanings", 1),
                    )
                )
            elif command == "custom_area":
                await self._device.execute_command(
                    self._capability.clean.action.area(
                        CleanMode.CUSTOM_AREA,
                        str(params["coordinates"]),
                        params.get("cleanings", 1),
                    )
                )
        else:
            await self._device.execute_command(
                self._capability.custom.set(command, params)
            )

    async def service_refresh(self, category: str) -> None:
        """Service to manually refresh."""
        _LOGGER.debug("Manually refresh %s", category)
        event = REFRESH_STR_TO_EVENT_DTO.get(category, None)
        if event:
            self._device.events.request_refresh(event)
        elif category == REFRESH_MAP:
            self._device.map.refresh()
        else:
            _LOGGER.warning(
                'Service "refresh" called with unknown category: %s', category
            )
