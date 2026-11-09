"""Connection handling + shared state for Beko Connect."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .beko_client import BekoApiError, BekoCloudClient
from .const import DOMAIN, RESYNC_INTERVAL, TRANSPORT_CODES

_LOGGER = logging.getLogger(__name__)


class BekoCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Holds one WebSocket connection; server pushes update the data live."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass, _LOGGER, name=DOMAIN, config_entry=entry,
            update_interval=RESYNC_INTERVAL,
        )
        self._email = entry.data[CONF_EMAIL]
        self._password = entry.data[CONF_PASSWORD]
        self._closing = False
        self._reconnect_task: asyncio.Task | None = None
        self.client = BekoCloudClient(async_get_clientsession(hass))
        self.client.add_listener(self._on_event)
        self.client.set_disconnect_callback(self._on_disconnect)

    async def _connect(self) -> None:
        await self.client.close()
        try:
            await self.client.connect()
            await self.client.login(self._email, self._password)
        except BekoApiError as err:
            await self.client.close()
            if err.code in TRANSPORT_CODES:
                raise UpdateFailed(f"Beko cloud unreachable: {err}") from err
            raise ConfigEntryAuthFailed("Beko login rejected") from err
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as err:
            await self.client.close()
            raise UpdateFailed(f"Beko cloud unreachable: {err}") from err

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        if not self.client.connected:
            await self._connect()
        try:
            data: dict[str, dict[str, Any]] = {}
            for endpoint in await self.client.get_endpoints():
                data[endpoint["id"]] = await self.client.get_endpoint(endpoint["id"])
            return data
        except BekoApiError as err:
            raise UpdateFailed(f"Beko API error: {err}") from err

    @callback
    def _on_event(self, name: str, payload: Any) -> None:
        """Server push: {'verb': 'updated', 'id': ..., 'data': {changed fields}}."""
        if name != "endpoint" or not isinstance(payload, dict):
            return
        if payload.get("verb") != "updated" or not self.data:
            return
        endpoint_id, changes = payload.get("id"), payload.get("data")
        if endpoint_id not in self.data or not isinstance(changes, dict):
            return
        merged = {**self.data, endpoint_id: {**self.data[endpoint_id], **changes}}
        self.async_set_updated_data(merged)

    @callback
    def _on_disconnect(self) -> None:
        if self._closing:
            return
        if self._reconnect_task and not self._reconnect_task.done():
            return
        _LOGGER.warning("Beko cloud connection lost, reconnecting")
        self._reconnect_task = self.hass.async_create_background_task(
            self._reconnect(), f"{DOMAIN}_reconnect")

    async def _reconnect(self) -> None:
        delay = 5
        while not self._closing:
            await asyncio.sleep(delay)
            await self.async_refresh()
            if self.last_update_success:
                _LOGGER.info("Beko cloud connection restored")
                return
            delay = min(delay * 2, 300)

    async def async_send(self, endpoint_id: str, type_: str, value: Any) -> None:
        try:
            await self.client.send_ac_state(endpoint_id, type_, value)
        except BekoApiError as err:
            raise HomeAssistantError(f"Command failed: {err}") from err

    async def async_shutdown(self) -> None:
        self._closing = True
        if self._reconnect_task:
            self._reconnect_task.cancel()
        await self.client.close()
        await super().async_shutdown()


class BekoEntity(CoordinatorEntity[BekoCoordinator]):
    """Base class: one device per endpoint."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BekoCoordinator, endpoint_id: str,
                 key: str | None = None) -> None:
        super().__init__(coordinator)
        self.endpoint_id = endpoint_id
        first = coordinator.data[endpoint_id]
        device = first.get("device") or {}
        self._attr_unique_id = f"{endpoint_id}_{key}" if key else endpoint_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, endpoint_id)},
            name=first.get("name") or "Beko klima",
            manufacturer="Beko",
            model="Wi-Fi AC module (Cosa)",
            hw_version=device.get("hardwareVersion"),
            sw_version=device.get("version"),
        )

    @property
    def ep(self) -> dict[str, Any]:
        return self.coordinator.data.get(self.endpoint_id, {})

    async def send(self, type_: str, value: Any) -> None:
        await self.coordinator.async_send(self.endpoint_id, type_, value)
