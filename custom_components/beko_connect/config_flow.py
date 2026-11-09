"""Config flow: sign in with the Beko Connect account."""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .beko_client import BekoApiError, BekoCloudClient
from .const import DOMAIN, TRANSPORT_CODES


class BekoConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _validate(self, email: str, password: str) -> str | None:
        client = BekoCloudClient(async_get_clientsession(self.hass))
        try:
            await client.connect()
            await client.login(email, password)
        except BekoApiError as err:
            return "cannot_connect" if err.code in TRANSPORT_CODES else "invalid_auth"
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            return "cannot_connect"
        finally:
            await client.close()
        return None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL].strip().lower())
            self._abort_if_unique_id_configured()
            error = await self._validate(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
            if error is None:
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL], data=user_input)
            errors["base"] = error
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]):
        self._entry_to_fix = self.hass.config_entries.async_get_entry(
            self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        entry = self._entry_to_fix
        if user_input is not None:
            error = await self._validate(entry.data[CONF_EMAIL], user_input[CONF_PASSWORD])
            if error is None:
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]})
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )
