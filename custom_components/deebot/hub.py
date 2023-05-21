"""Hub module."""
import logging
import random
import string
from collections.abc import Mapping
from typing import Any

from deebot_client.api_client import ApiClient
from deebot_client.authentication import Authenticator
from deebot_client.exceptions import InvalidAuthenticationError
from deebot_client.models import Configuration
from deebot_client.mqtt_client import MqttClient, MqttConfiguration
from deebot_client.util import md5
from deebot_client.vacuum_bot import VacuumBot
from homeassistant.const import (
    CONF_DEVICES,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client

from .const import CONF_CLIENT_DEVICE_ID, CONF_CONTINENT, CONF_COUNTRY

_LOGGER = logging.getLogger(__name__)


class DeebotHub:
    """Deebot Hub."""

    def __init__(self, hass: HomeAssistant, config: Mapping[str, Any]):
        self._hass_config: Mapping[str, Any] = config
        self._hass: HomeAssistant = hass
        self.vacuum_bots: list[VacuumBot] = []
        verify_ssl = config.get(CONF_VERIFY_SSL, True)
        device_id = config.get(CONF_CLIENT_DEVICE_ID)

        if not device_id:
            # Generate a random device ID on each bootup
            device_id = "".join(
                random.choice(string.ascii_uppercase + string.digits) for _ in range(12)
            )

        deebot_config = Configuration(
            aiohttp_client.async_get_clientsession(self._hass, verify_ssl=verify_ssl),
            device_id=device_id,
            country=config.get(CONF_COUNTRY, "it").lower(),
            continent=config.get(CONF_CONTINENT, "eu").lower(),
            verify_ssl=config.get(CONF_VERIFY_SSL, True),
        )

        self._authenticator = Authenticator(
            deebot_config,
            config.get(CONF_USERNAME, ""),
            md5(config.get(CONF_PASSWORD, "")),
        )
        self._api_client = ApiClient(self._authenticator)

        mqtt_config = MqttConfiguration(config=deebot_config)
        self._mqtt: MqttClient = MqttClient(mqtt_config, self._authenticator)

    async def async_setup(self) -> None:
        """Init hub."""
        try:
            await self.teardown()

            devices = await self._api_client.get_devices()

            await self._mqtt.connect()

            for device in devices:
                if device["name"] in self._hass_config.get(CONF_DEVICES, []):
                    bot = VacuumBot(device, self._authenticator)
                    _LOGGER.debug("New vacbot found: %s", device["name"])
                    await bot.initialize(self._mqtt)
                    self.vacuum_bots.append(bot)

            _LOGGER.debug("Hub setup complete")
        except InvalidAuthenticationError as ex:
            raise ConfigEntryAuthFailed from ex
        except Exception as ex:
            msg = "Error during setup"
            _LOGGER.error(msg, exc_info=True)
            raise ConfigEntryNotReady(msg) from ex

    async def teardown(self) -> None:
        """Disconnect hub."""
        for bot in self.vacuum_bots:
            await bot.teardown()
        await self._mqtt.disconnect()
        await self._authenticator.teardown()

    @property
    def name(self) -> str:
        """Return the name of the hub."""
        return "Deebot Hub"
