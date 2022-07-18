"""Sensor module."""
import logging
from collections.abc import Callable
from math import floor
from typing import TypeVar

from deebot_client.events import (
    CleanLogEvent,
    ErrorEvent,
    Event,
    LifeSpan,
    LifeSpanEvent,
    StatsEvent,
    TotalStatsEvent,
)
from deebot_client.events.event_bus import EventListener
from deebot_client.vacuum_bot import VacuumBot
from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    AREA_SQUARE_METERS,
    CONF_DESCRIPTION,
    TIME_HOURS,
    TIME_MINUTES,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN, LAST_ERROR
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
            new_devices.append(LifeSpanSensor(vacbot, component))

        new_devices.extend(
            [
                LastCleaningJobSensor(vacbot),
                LastErrorSensor(vacbot),
                # Stats
                DeebotGenericSensor(
                    vacbot,
                    SensorEntityDescription(
                        key="stats_area",
                        icon="mdi:floor-plan",
                        native_unit_of_measurement=AREA_SQUARE_METERS,
                        entity_registry_enabled_default=False,
                    ),
                    StatsEvent,
                    lambda e: e.area,
                ),
                DeebotGenericSensor(
                    vacbot,
                    SensorEntityDescription(
                        key="stats_time",
                        icon="mdi:timer-outline",
                        native_unit_of_measurement=TIME_MINUTES,
                        entity_registry_enabled_default=False,
                    ),
                    StatsEvent,
                    lambda e: round(e.time / 60) if e.time else None,
                ),
                DeebotGenericSensor(
                    vacbot,
                    SensorEntityDescription(
                        key="stats_type",
                        icon="mdi:cog",
                        entity_registry_enabled_default=False,
                    ),
                    StatsEvent,
                    lambda e: e.type,
                ),
                # TotalStats
                DeebotGenericSensor(
                    vacbot,
                    SensorEntityDescription(
                        key="stats_total_area",
                        icon="mdi:floor-plan",
                        native_unit_of_measurement=AREA_SQUARE_METERS,
                        entity_registry_enabled_default=False,
                        state_class=SensorStateClass.TOTAL_INCREASING,
                    ),
                    TotalStatsEvent,
                    lambda e: e.area,
                ),
                DeebotGenericSensor(
                    vacbot,
                    SensorEntityDescription(
                        key="stats_total_time",
                        icon="mdi:timer-outline",
                        native_unit_of_measurement=TIME_HOURS,
                        entity_registry_enabled_default=False,
                        state_class=SensorStateClass.TOTAL_INCREASING,
                    ),
                    TotalStatsEvent,
                    lambda e: round(e.time / 3600),
                ),
                DeebotGenericSensor(
                    vacbot,
                    SensorEntityDescription(
                        key="stats_total_cleanings",
                        icon="mdi:counter",
                        entity_registry_enabled_default=False,
                        state_class=SensorStateClass.TOTAL_INCREASING,
                    ),
                    TotalStatsEvent,
                    lambda e: e.cleanings,
                ),
            ]
        )

    if new_devices:
        async_add_entities(new_devices)


T = TypeVar("T", bound=Event)


class DeebotGenericSensor(DeebotEntity, SensorEntity):  # type: ignore
    """Deebot generic sensor."""

    def __init__(
        self,
        vacuum_bot: VacuumBot,
        entity_descrption: SensorEntityDescription,
        event_type: type[T],
        extract_value: Callable[[T], StateType],
    ):
        """Initialize the Sensor."""
        super().__init__(vacuum_bot, entity_descrption)
        self._event_type = event_type
        self._extract_value = extract_value

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_event(event: T) -> None:
            value = self._extract_value(event)
            if value is not None:
                self._attr_native_value = value
                self.async_write_ha_state()

        listener: EventListener = self._vacuum_bot.events.subscribe(
            self._event_type, on_event
        )
        self.async_on_remove(listener.unsubscribe)


class LastErrorSensor(DeebotEntity, SensorEntity):  # type: ignore
    """Last error sensor."""

    _always_available = True
    entity_description = SensorEntityDescription(
        key=LAST_ERROR,
        icon="mdi:alert-circle",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_event(event: ErrorEvent) -> None:
            self._attr_native_value = event.code
            self._attr_extra_state_attributes = {CONF_DESCRIPTION: event.description}
            self.async_write_ha_state()

        listener: EventListener = self._vacuum_bot.events.subscribe(
            ErrorEvent, on_event
        )
        self.async_on_remove(listener.unsubscribe)


class LifeSpanSensor(DeebotEntity, SensorEntity):  # type: ignore
    """Life span sensor."""

    def __init__(self, vacuum_bot: VacuumBot, component: LifeSpan):
        """Initialize the Sensor."""
        entity_description = SensorEntityDescription(
            key=f"life_span_{component.name.lower()}",
            icon="mdi:air-filter" if component == LifeSpan.FILTER else "mdi:broom",
            entity_registry_enabled_default=False,
            native_unit_of_measurement="%",
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        super().__init__(vacuum_bot, entity_description)
        self._component = component

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_event(event: LifeSpanEvent) -> None:
            if event.type == self._component:
                self._attr_native_value = event.percent
                self._attr_extra_state_attributes = {
                    "remaining": floor(event.remaining / 60)
                }
                self.async_write_ha_state()

        listener: EventListener = self._vacuum_bot.events.subscribe(
            LifeSpanEvent, on_event
        )
        self.async_on_remove(listener.unsubscribe)


class LastCleaningJobSensor(DeebotEntity, SensorEntity):  # type: ignore
    """Last cleaning job sensor."""

    _always_available = True
    entity_description = SensorEntityDescription(
        key="last_cleaning",
        icon="mdi:history",
        entity_registry_enabled_default=False,
    )

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_event(event: CleanLogEvent) -> None:
            if event.logs:
                log = event.logs[0]
                self._attr_native_value = log.stop_reason.display_name
                self._attr_extra_state_attributes = {
                    "timestamp": log.timestamp,
                    "image_url": log.image_url,
                    "type": log.type,
                    "area": log.area,
                    "duration": log.duration / 60,
                }
                self.async_write_ha_state()

        listener: EventListener = self._vacuum_bot.events.subscribe(
            CleanLogEvent, on_event
        )
        self.async_on_remove(listener.unsubscribe)
