"""Config flow for Deebot integration."""
import logging
import random
import string
from types import MappingProxyType
from typing import Any

import voluptuous as vol
from aiohttp import ClientError
from deebot_client.api_client import ApiClient
from deebot_client.authentication import Authenticator, create_rest_config
from deebot_client.exceptions import InvalidAuthenticationError
from deebot_client.models import DeviceInfo
from deebot_client.util import md5
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import (
    CONF_DEVICES,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
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

    VERSION = 4

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._devices: list[DeviceInfo] = []
        self._mode: str | None = None
        self._entry: ConfigEntry | None = None

    @staticmethod
    @callback  # type: ignore[misc]
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> "DeebotOptionsFlowHandler":
        """Get the options flow for this handler."""
        return DeebotOptionsFlowHandler(config_entry)

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
                    self._devices = await _retrieve_devices(self.hass, data)
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

                if len(self._devices) == 0:
                    return self.async_abort(reason="no_supported_devices_found")

                self._data.update(data)
                return await self.async_step_options()

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
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                    ),
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                    vol.Required(
                        CONF_COUNTRY,
                        default=data.get(CONF_COUNTRY, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                    ),
                    vol.Required(
                        CONF_CONTINENT,
                        default=data.get(CONF_CONTINENT, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                    ),
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

        return self.async_show_form(
            step_id="user_advanced",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MODE, default=CONF_MODE_CLOUD
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                CONF_MODE_CLOUD,
                                CONF_MODE_BUMPER,
                            ]
                        )
                    )
                }
            ),
        )

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the options step."""

        errors = {}
        if user_input is not None:
            try:
                if len(user_input[CONF_DEVICES]) < 1:
                    errors[CONF_DEVICES] = "select_robots"
                else:
                    return self.async_create_entry(
                        title=self._data[CONF_USERNAME],
                        data=self._data,
                        options=user_input,
                    )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.error("Unexpected exception", exc_info=True)
                errors["base"] = "unknown"

        # If there is no user input or there were errors, show the form again, including any errors that were found with the input.
        return self.async_show_form(
            step_id="options",
            data_schema=_get_options_schema(self._devices, {}),
            errors=errors,
        )

    async def async_step_reauth(self, data: dict[str, Any]) -> FlowResult:
        """Handle initiation of re-authentication."""
        self._entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_user(data)


def _get_options_schema(
    devices: list[DeviceInfo], defaults: dict[str, Any] | MappingProxyType[str, Any]
) -> vol.Schema:
    """Return options schema."""
    select_options = []

    for entry in devices:
        api_info = entry.api_device_info
        label = api_info.get("nick", api_info["name"])
        if not label:
            label = api_info["name"]
        select_options.append(
            selector.SelectOptionDict(value=api_info["name"], label=label)
        )

    return vol.Schema(
        {
            vol.Required(
                CONF_DEVICES, default=defaults.get(CONF_DEVICES, vol.UNDEFINED)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=select_options,
                    multiple=True,
                )
            )
        }
    )


async def _retrieve_devices(
    hass: HomeAssistant, domain_config: dict[str, Any]
) -> list[DeviceInfo]:
    verify_ssl = domain_config.get(CONF_VERIFY_SSL, True)
    deebot_config = create_rest_config(
        aiohttp_client.async_get_clientsession(hass, verify_ssl=verify_ssl),
        device_id=DEEBOT_API_DEVICEID,
        country=domain_config[CONF_COUNTRY].upper(),
    )

    authenticator = Authenticator(
        deebot_config,
        domain_config[CONF_USERNAME],
        md5(domain_config[CONF_PASSWORD]),
    )
    api_client = ApiClient(authenticator)

    devices = await api_client.get_devices()
    return [device for device in devices if isinstance(device, DeviceInfo)]


class DeebotOptionsFlowHandler(OptionsFlow):  # type: ignore[misc]
    """Handle deebot options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._devices: list[DeviceInfo] | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        errors = {}
        if user_input is not None:
            try:
                if len(user_input[CONF_DEVICES]) < 1:
                    errors[CONF_DEVICES] = "select_robots"
                else:
                    return self.async_create_entry(
                        title=self._config_entry.title,
                        data=user_input,
                    )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.error("Unexpected exception", exc_info=True)
                errors["base"] = "unknown"

        if user_input is None:
            user_input = self._config_entry.options

        if not self._devices:
            try:
                self._devices = await _retrieve_devices(
                    self.hass, self._config_entry.data
                )
            except ClientError:
                _LOGGER.debug("Cannot connect", exc_info=True)
                return self.async_abort(reason="cannot_connect")
            except InvalidAuthenticationError:
                return self.async_abort(reason="invalid_auth")
            except Exception:  # pylint: disable=broad-except
                _LOGGER.error("Unexpected exception on getting devices", exc_info=True)
                return self.async_abort(reason="unknown_get_devices")

            if len(self._devices) == 0:
                return self.async_abort(reason="no_supported_devices_found")

        return self.async_show_form(
            step_id="init",
            data_schema=_get_options_schema(self._devices, user_input),
            errors=errors,
        )
