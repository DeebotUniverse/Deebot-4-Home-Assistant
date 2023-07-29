"""Support for Deebot Vaccums."""
import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from deebot_client.commands import (
    Charge,
    Clean,
    FanSpeedLevel,
    PlaySound,
    SetFanSpeed,
    SetRelocationState,
    SetWaterInfo,
)
from deebot_client.commands.clean import CleanAction, CleanArea, CleanMode
from deebot_client.commands.custom import CustomCommand
from deebot_client.events import (
    BatteryEvent,
    CustomCommandEvent,
    ErrorEvent,
    FanSpeedEvent,
    ReportStatsEvent,
    RoomsEvent,
    StateEvent,
)
from deebot_client.models import Room
from deebot_client.vacuum_bot import VacuumBot
from homeassistant.components.vacuum import (
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
    LAST_ERROR,
    REFRESH_MAP,
    REFRESH_STR_TO_EVENT_DTO,
    VACUUMSTATE_TO_STATE,
)
from .entity import DeebotEntity
from .hub import DeebotHub
from .util import dataclass_to_dict

_LOGGER = logging.getLogger(__name__)


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
    hub: DeebotHub = hass.data[DOMAIN][config_entry.entry_id]

    new_devices = []
    for vacbot in hub.vacuum_bots:
        new_devices.append(DeebotVacuum(vacbot))

    if new_devices:
        async_add_entities(new_devices)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_REFRESH,
        SERVICE_REFRESH_SCHEMA,
        "service_refresh",
    )


class DeebotVacuum(DeebotEntity, StateVacuumEntity):  # type: ignore
    """Deebot Vacuum."""

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
    _attr_fan_speed_list = [level.display_name for level in FanSpeedLevel]

    def __init__(self, vacuum_bot: VacuumBot):
        """Initialize the Deebot Vacuum."""
        super().__init__(
            vacuum_bot,
            StateVacuumEntityDescription(key="", translation_key="bot", name=None),
        )

        self._rooms: list[Room] = []
        self._last_error: ErrorEvent | None = None

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_battery(event: BatteryEvent) -> None:
            self._attr_battery_level = event.value
            self.async_write_ha_state()

        async def on_custom_command(event: CustomCommandEvent) -> None:
            self.hass.bus.fire(EVENT_CUSTOM_COMMAND, dataclass_to_dict(event))

        async def on_error(event: ErrorEvent) -> None:
            self._last_error = event
            self.async_write_ha_state()

        async def on_fan_speed(event: FanSpeedEvent) -> None:
            self._attr_fan_speed = event.speed.display_name
            self.async_write_ha_state()

        async def on_report_stats(event: ReportStatsEvent) -> None:
            self.hass.bus.fire(EVENT_CLEANING_JOB, dataclass_to_dict(event))

        async def on_rooms(event: RoomsEvent) -> None:
            self._rooms = event.rooms
            self.async_write_ha_state()

        async def on_status(event: StateEvent) -> None:
            self._attr_state = VACUUMSTATE_TO_STATE[event.state]
            self.async_write_ha_state()

        subscriptions = [
            self._vacuum_bot.events.subscribe(BatteryEvent, on_battery),
            self._vacuum_bot.events.subscribe(CustomCommandEvent, on_custom_command),
            self._vacuum_bot.events.subscribe(ErrorEvent, on_error),
            self._vacuum_bot.events.subscribe(FanSpeedEvent, on_fan_speed),
            self._vacuum_bot.events.subscribe(ReportStatsEvent, on_report_stats),
            self._vacuum_bot.events.subscribe(RoomsEvent, on_rooms),
            self._vacuum_bot.events.subscribe(StateEvent, on_status),
        ]

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
            attributes["rooms"] = rooms

        if self._last_error:
            attributes[
                LAST_ERROR
            ] = f"{self._last_error.description} ({self._last_error.code})"

        return attributes

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        await self._vacuum_bot.execute_command(SetFanSpeed(fan_speed))

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""
        await self._vacuum_bot.execute_command(Charge())

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner."""
        await self._vacuum_bot.execute_command(Clean(CleanAction.STOP))

    async def async_pause(self) -> None:
        """Pause the vacuum cleaner."""
        await self._vacuum_bot.execute_command(Clean(CleanAction.PAUSE))

    async def async_start(self) -> None:
        """Start the vacuum cleaner."""
        await self._vacuum_bot.execute_command(Clean(CleanAction.START))

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate the vacuum cleaner."""
        await self._vacuum_bot.execute_command(PlaySound())

    async def async_send_command(
        self, command: str, params: dict[str, Any] | None = None, **kwargs: Any
    ) -> None:
        """Send a command to a vacuum cleaner."""
        _LOGGER.debug("async_send_command %s with %s", command, params)

        if command in ["relocate", SetRelocationState.name]:
            _LOGGER.warning("DEPRECATED! Please use relocate button entity instead.")
            await self._vacuum_bot.execute_command(SetRelocationState())
        elif command == "auto_clean":
            clean_type = params.get("type", "auto") if params else "auto"
            if clean_type == "auto":
                _LOGGER.warning('DEPRECATED! Please use "vacuum.start" instead.')
                await self.async_start()
        elif command in ["spot_area", "custom_area", "set_water"]:
            if params is None:
                raise RuntimeError("Params are required!")

            if command in "spot_area":
                await self._vacuum_bot.execute_command(
                    CleanArea(
                        mode=CleanMode.SPOT_AREA,
                        area=str(params["rooms"]),
                        cleanings=params.get("cleanings", 1),
                    )
                )
            elif command == "custom_area":
                await self._vacuum_bot.execute_command(
                    CleanArea(
                        mode=CleanMode.CUSTOM_AREA,
                        area=str(params["coordinates"]),
                        cleanings=params.get("cleanings", 1),
                    )
                )
            elif command == "set_water":
                _LOGGER.warning("DEPRECATED! Please use water select entity instead.")
                await self._vacuum_bot.execute_command(SetWaterInfo(params["amount"]))
        else:
            await self._vacuum_bot.execute_command(CustomCommand(command, params))

    async def service_refresh(self, category: str) -> None:
        """Service to manually refresh."""
        _LOGGER.debug("Manually refresh %s", category)
        event = REFRESH_STR_TO_EVENT_DTO.get(category, None)
        if event:
            self._vacuum_bot.events.request_refresh(event)
        elif category == REFRESH_MAP:
            self._vacuum_bot.map.refresh()
        else:
            _LOGGER.warning(
                'Service "refresh" called with unknown category: %s', category
            )
