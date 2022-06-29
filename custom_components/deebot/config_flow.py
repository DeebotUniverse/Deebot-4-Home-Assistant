"""Config flow for Deebot integration."""
import logging
import random
import string
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from aiohttp import ClientError
from deebot_client import create_instances
from deebot_client.exceptions import InvalidAuthenticationError
from deebot_client.models import Configuration, DeviceInfo
from deebot_client.util import md5
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import (
    CONF_DEVICES,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client, selector

from . import get_bumper_device_id
from .const import (
    BUMPER_CONFIGURATION,
    CONF_CLIENT_DEVICE_ID,
    CONF_CONTINENT,
    CONF_COUNTRY,
    CONF_MODE_BUMPER,
    CONF_MODE_CLOUD,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Generate a random device ID on each bootup
DEEBOT_API_DEVICEID = "".join(
    random.choice(string.ascii_uppercase + string.digits) for _ in range(8)
)


class DeebotConfigFlow(ConfigFlow, domain=DOMAIN):  # type: ignore
    """Handle a config flow for Deebot."""

    VERSION = 3

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._robot_list: list[DeviceInfo] = []
        self._mode: str | None = None
        self._entry: ConfigEntry | None = None

    async def _async_retrieve_bots(
        self, domain_config: dict[str, Any]
    ) -> list[DeviceInfo]:
        verify_ssl = domain_config.get(CONF_VERIFY_SSL, True)
        deebot_config = Configuration(
            aiohttp_client.async_get_clientsession(self.hass, verify_ssl=verify_ssl),
            device_id=DEEBOT_API_DEVICEID,
            continent=domain_config[CONF_CONTINENT],
            country=domain_config[CONF_COUNTRY],
            verify_ssl=verify_ssl,
        )

        (_, api_client) = create_instances(
            deebot_config,
            domain_config[CONF_USERNAME],
            md5(domain_config[CONF_PASSWORD]),
        )

        return await api_client.get_devices()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        data = {}

        if user_input is not None:
            data.update(user_input)
            if len(data[CONF_COUNTRY]) != 2:
                errors[CONF_COUNTRY] = "invalid_country"

            if len(data[CONF_CONTINENT]) != 2:
                errors[CONF_CONTINENT] = "invalid_continent"

            if not errors:
                try:
                    self._robot_list = await self._async_retrieve_bots(data)
                except ClientError:
                    _LOGGER.debug("Cannot connect", exc_info=True)
                    errors["base"] = "cannot_connect"
                except InvalidAuthenticationError:
                    errors["base"] = "invalid_auth"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.error("Unexpected exception", exc_info=True)
                    errors["base"] = "unknown"

            if not errors:
                if self._entry:
                    # reauthentication
                    self.hass.config_entries.async_update_entry(self._entry, data=data)
                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(self._entry.entry_id)
                    )
                    return self.async_abort(reason="reauth_successful")

                self._async_abort_entries_match(
                    {CONF_USERNAME: user_input[CONF_USERNAME]}
                )

                if len(self._robot_list) == 0:
                    return self.async_abort(reason="no_supported_devices_found")

                self._data.update(data)
                return await self.async_step_robots()

        if self._entry:
            data.update(self._entry.data)
        elif self.show_advanced_options and self._mode is None:
            return await self.async_step_user_advanced()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=data.get(CONF_USERNAME, vol.UNDEFINED),
                    ): selector.selector({"text": {}}),
                    vol.Required(CONF_PASSWORD): selector.selector(
                        {"text": {"type": "password"}}
                    ),
                    vol.Required(
                        CONF_COUNTRY,
                        default=data.get(CONF_COUNTRY, vol.UNDEFINED),
                    ): selector.selector({"text": {}}),
                    vol.Required(
                        CONF_CONTINENT,
                        default=data.get(CONF_CONTINENT, vol.UNDEFINED),
                    ): selector.selector({"text": {}}),
                }
            ),
            errors=errors,
        )

    async def async_step_user_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle an advanced mode flow initialized by the user."""
        if user_input is not None:
            self._mode = user_input.get(CONF_MODE, CONF_MODE_CLOUD)
            if self._mode == CONF_MODE_BUMPER:
                config = {
                    **BUMPER_CONFIGURATION,
                    CONF_CLIENT_DEVICE_ID: get_bumper_device_id(self.hass),
                }
                return await self.async_step_user(user_input=config)

            return await self.async_step_user()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_MODE, default=CONF_MODE_CLOUD): vol.In(
                    [CONF_MODE_CLOUD, CONF_MODE_BUMPER]
                )
            }
        )

        return self.async_show_form(step_id="user_advanced", data_schema=data_schema)

    async def async_step_robots(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the robots selection step."""

        errors = {}
        if user_input is not None:
            try:
                if len(user_input[CONF_DEVICES]) < 1:
                    errors["base"] = "select_robots"
                else:
                    self._data.update(user_input)
                    return self.async_create_entry(
                        title=self._data[CONF_USERNAME], data=self._data
                    )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.error("Unexpected exception", exc_info=True)
                errors["base"] = "unknown"

        # If there is no user input or there were errors, show the form again, including any errors that were found with the input.
        robot_list_dict = {
            e["name"]: e.get("nick", e["name"]) for e in self._robot_list
        }
        options_schema = vol.Schema(
            {
                vol.Required(
                    CONF_DEVICES, default=list(robot_list_dict.keys())
                ): cv.multi_select(robot_list_dict)
            }
        )

        return self.async_show_form(
            step_id="robots", data_schema=options_schema, errors=errors
        )

    async def async_step_reauth(self, data: dict[str, Any]) -> FlowResult:
        """Handle initiation of re-authentication."""
        self._entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_user(data)
