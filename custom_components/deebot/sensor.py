"""Sensor module."""
from collections.abc import Callable, MutableMapping, Sequence
from dataclasses import dataclass
from math import floor
from typing import Any, Generic, TypeVar

from deebot_client.capabilities import CapabilityEvent, CapabilityLifeSpan
from deebot_client.device import Device
from deebot_client.events import (
    BatteryEvent,
    CleanLogEvent,
    ErrorEvent,
    Event,
    LifeSpan,
    LifeSpanEvent,
    NetworkInfoEvent,
    StatsEvent,
    TotalStatsEvent,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    AREA_SQUARE_METERS,
    ATTR_BATTERY_LEVEL,
    CONF_DESCRIPTION,
    PERCENTAGE,
    TIME_HOURS,
    TIME_MINUTES,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .controller import DeebotController
from .entity import DeebotEntity, DeebotEntityDescription, EventT


@dataclass(kw_only=True)
class DeebotSensorEntityDescription(
    SensorEntityDescription,  # type: ignore
    DeebotEntityDescription,
    Generic[EventT],
):
    """Deebot sensor entity description."""

    extra_state_attributes_fn: Callable[
        [EventT], MutableMapping[str, Any]
    ] | None = None
    value_fn: Callable[[EventT], StateType]


def _clean_log_event_value(event: CleanLogEvent) -> str | None:
    if event.logs:
        log = event.logs[0]
        return log.stop_reason.display_name
    return None


def _clean_log_event_attributes(event: CleanLogEvent) -> MutableMapping[str, Any]:
    if event.logs:
        log = event.logs[0]
        return {
            "timestamp": log.timestamp,
            "image_url": log.image_url,
            "type": log.type,
            "area": log.area,
            "duration": log.duration / 60,
        }

    return {}


ENTITY_DESCRIPTIONS: tuple[DeebotSensorEntityDescription, ...] = (
    # Stats
    DeebotSensorEntityDescription[StatsEvent](
        key="stats_area",
        capability_fn=lambda caps: caps.stats.clean,
        value_fn=lambda e: e.area,
        translation_key="stats_area",
        icon="mdi:floor-plan",
        native_unit_of_measurement=AREA_SQUARE_METERS,
        entity_registry_enabled_default=False,
    ),
    DeebotSensorEntityDescription[StatsEvent](
        key="stats_time",
        capability_fn=lambda caps: caps.stats.clean,
        value_fn=lambda e: round(e.time / 60) if e.time else None,
        translation_key="stats_time",
        icon="mdi:timer-outline",
        native_unit_of_measurement=TIME_MINUTES,
        entity_registry_enabled_default=False,
    ),
    DeebotSensorEntityDescription[StatsEvent](
        capability_fn=lambda caps: caps.stats.clean,
        value_fn=lambda e: e.type,
        key="stats_type",
        translation_key="stats_type",
        icon="mdi:cog",
        entity_registry_enabled_default=False,
    ),
    # TotalStats
    DeebotSensorEntityDescription[TotalStatsEvent](
        capability_fn=lambda caps: caps.stats.total,
        value_fn=lambda e: e.area,
        key="stats_total_area",
        translation_key="stats_total_area",
        icon="mdi:floor-plan",
        native_unit_of_measurement=AREA_SQUARE_METERS,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DeebotSensorEntityDescription[TotalStatsEvent](
        capability_fn=lambda caps: caps.stats.total,
        value_fn=lambda e: round(e.time / 3600),
        key="stats_total_time",
        translation_key="stats_total_time",
        icon="mdi:timer-outline",
        native_unit_of_measurement=TIME_HOURS,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DeebotSensorEntityDescription[TotalStatsEvent](
        capability_fn=lambda caps: caps.stats.total,
        value_fn=lambda e: e.cleanings,
        key="stats_total_cleanings",
        translation_key="stats_total_cleanings",
        icon="mdi:counter",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DeebotSensorEntityDescription[BatteryEvent](
        capability_fn=lambda caps: caps.battery,
        value_fn=lambda e: e.value,
        key=ATTR_BATTERY_LEVEL,
        translation_key=ATTR_BATTERY_LEVEL,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DeebotSensorEntityDescription[NetworkInfoEvent](
        capability_fn=lambda caps: caps.network,
        value_fn=lambda e: e.ip,
        key="wifi_ip",
        translation_key="wifi_ip",
        icon="mdi:ip-network-outline",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DeebotSensorEntityDescription[NetworkInfoEvent](
        capability_fn=lambda caps: caps.network,
        value_fn=lambda e: e.rssi,
        key="wifi_rssi",
        translation_key="wifi_rssi",
        icon="mdi:signal-variant",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DeebotSensorEntityDescription[NetworkInfoEvent](
        capability_fn=lambda caps: caps.network,
        value_fn=lambda e: e.ssid,
        key="wifi_ssid",
        translation_key="wifi_ssid",
        icon="mdi:wifi",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


@dataclass
class DeebotLifeSpanSensorMixin:
    """Deebot life span sensor mixin."""

    component: LifeSpan


@dataclass
class DeebotLifeSpanSensorEntityDescription(
    SensorEntityDescription, DeebotLifeSpanSensorMixin  # type: ignore
):
    """Class describing Deebot sensor entity."""


LIFE_SPAN_DESCRIPTIONS: tuple[DeebotLifeSpanSensorEntityDescription, ...] = (
    DeebotLifeSpanSensorEntityDescription(
        component=LifeSpan.BRUSH,
        key="life_span_brush",
        translation_key="life_span_brush",
        icon="mdi:broom",
        entity_registry_enabled_default=False,
        native_unit_of_measurement="%",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DeebotLifeSpanSensorEntityDescription(
        component=LifeSpan.FILTER,
        key="life_span_filter",
        translation_key="life_span_filter",
        icon="mdi:air-filter",
        entity_registry_enabled_default=False,
        native_unit_of_measurement="%",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DeebotLifeSpanSensorEntityDescription(
        component=LifeSpan.SIDE_BRUSH,
        key="life_span_side_brush",
        translation_key="life_span_side_brush",
        icon="mdi:broom",
        entity_registry_enabled_default=False,
        native_unit_of_measurement="%",
        entity_category=EntityCategory.DIAGNOSTIC,
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
        DeebotSensor, ENTITY_DESCRIPTIONS, async_add_entities
    )

    def last_error_entity_generator(
        device: Device,
    ) -> Sequence[LastErrorSensor]:
        if capability := device.capabilities.error:
            return [(LastErrorSensor(device, capability))]
        return []

    def last_cleaning_entity_generator(
        device: Device,
    ) -> Sequence[LastCleaningSensor]:
        if capability := device.capabilities.clean.log:
            return [(LastCleaningSensor(device, capability))]
        return []

    def life_span_entity_generator(device: Device) -> Sequence[LifeSpanSensor]:
        new_entities = []
        capability = device.capabilities.life_span
        for description in LIFE_SPAN_DESCRIPTIONS:
            if description.component in capability.types:
                new_entities.append(LifeSpanSensor(device, capability, description))
        return new_entities

    controller.register_platform_add_entities_generator(
        async_add_entities,
        (
            life_span_entity_generator,
            last_error_entity_generator,
            last_cleaning_entity_generator,
        ),
    )


class DeebotSensor(
    DeebotEntity[CapabilityEvent, DeebotSensorEntityDescription],
    SensorEntity,  # type: ignore
):
    """Deebot sensor."""

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_event(event: Event) -> None:
            value = self.entity_description.value_fn(event)
            if value is None:
                return

            self._attr_native_value = value
            if attr_fn := self.entity_description.extra_state_attributes_fn:
                self._attr_extra_state_attributes = attr_fn(event)
            self.async_write_ha_state()

        self.async_on_remove(
            self._device.events.subscribe(self._capability.event, on_event)
        )


T = TypeVar("T", bound=Event)


class LifeSpanSensor(
    DeebotEntity[CapabilityLifeSpan, DeebotLifeSpanSensorEntityDescription],
    SensorEntity,  # type: ignore
):
    """Life span sensor."""

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_event(event: LifeSpanEvent) -> None:
            if event.type == self.entity_description.component:
                self._attr_native_value = event.percent
                self._attr_extra_state_attributes = {
                    "remaining": floor(event.remaining / 60)
                }
                self.async_write_ha_state()

        self.async_on_remove(
            self._device.events.subscribe(self._capability.event, on_event)
        )


class LastErrorSensor(
    DeebotEntity[CapabilityEvent[ErrorEvent], SensorEntityDescription],
    SensorEntity,  # type: ignore
):
    """Last error sensor."""

    _always_available: bool = True
    _unrecorded_attributes = frozenset({CONF_DESCRIPTION})
    entity_description: SensorEntityDescription = SensorEntityDescription(
        key="last_error",
        translation_key="last_error",
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

        self.async_on_remove(
            self._device.events.subscribe(self._capability.event, on_event)
        )


class LastCleaningSensor(
    DeebotEntity[CapabilityEvent[CleanLogEvent], SensorEntityDescription],
    SensorEntity,  # type: ignore
):
    """Last cleaning sensor."""

    _always_available: bool = True
    entity_description: SensorEntityDescription = SensorEntityDescription(
        key="last_cleaning",
        translation_key="last_cleaning",
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

        self.async_on_remove(
            self._device.events.subscribe(self._capability.event, on_event)
        )
