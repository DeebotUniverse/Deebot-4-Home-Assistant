"""Const module."""
from typing import Mapping, Type

from deebot_client.events import (
    BatteryEvent,
    CleanLogEvent,
    ErrorEvent,
    Event,
    FanSpeedEvent,
    LifeSpanEvent,
    RoomsEvent,
    StatsEvent,
    StatusEvent,
    WaterInfoEvent,
)
from deebot_client.models import VacuumState
from homeassistant.components.vacuum import (
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL

################################
# Do not change! Will be set by release workflow
INTEGRATION_VERSION = "main"  # git tag will be used
MIN_REQUIRED_HA_VERSION = "2021.12.0b0"  # set min required version in hacs.json
################################

# Values below can be changed
DOMAIN = "deebot"
ISSUE_URL = "https://github.com/DeebotUniverse/Deebot-4-Home-Assistant/issues"

STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{DOMAIN}
Version: {INTEGRATION_VERSION}
This is a custom component
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""

CONF_COUNTRY = "country"
CONF_CONTINENT = "continent"
CONF_BUMPER = "Bumper"
CONF_MODE_BUMPER = CONF_BUMPER
CONF_MODE_CLOUD = "Cloud (recommended)"
CONF_CLIENT_DEVICE_ID = "client_device_id"

# Bumper has no auth and serves the urls for all countries/continents
BUMPER_CONFIGURATION = {
    CONF_CONTINENT: "eu",
    CONF_COUNTRY: "it",
    CONF_PASSWORD: CONF_BUMPER,
    CONF_USERNAME: CONF_BUMPER,
    CONF_VERIFY_SSL: False,  # required as bumper is using self signed certificates
}

DEEBOT_DEVICES = f"{DOMAIN}_devices"

VACUUMSTATE_TO_STATE = {
    VacuumState.IDLE: STATE_IDLE,
    VacuumState.CLEANING: STATE_CLEANING,
    VacuumState.RETURNING: STATE_RETURNING,
    VacuumState.DOCKED: STATE_DOCKED,
    VacuumState.ERROR: STATE_ERROR,
    VacuumState.PAUSED: STATE_PAUSED,
}

LAST_ERROR = "last_error"


REFRESH_STR_TO_EVENT_DTO: Mapping[str, Type[Event]] = {
    "Battery": BatteryEvent,
    "Clean logs": CleanLogEvent,
    "Error": ErrorEvent,
    "Fan speed": FanSpeedEvent,
    "Life spans": LifeSpanEvent,
    "Rooms": RoomsEvent,
    "Stats": StatsEvent,
    "Status": StatusEvent,
    "Water": WaterInfoEvent,
}
REFRESH_MAP = "Map"

EVENT_CLEANING_JOB = "deebot_cleaning_job"
EVENT_CUSTOM_COMMAND = "deebot_custom_command"
