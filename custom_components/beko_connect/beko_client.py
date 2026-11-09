"""Unofficial minimal client for the Beko Connect cloud (Cosa "kiwi" backend).

Speaks Engine.IO v3 / Socket.IO 1.x over a plain WebSocket and wraps requests
the same way sails.io.js does: the socket event name is the HTTP verb and the
payload is {method, url, data, headers}; the ack carries {body, statusCode}.

Only dependency: aiohttp (already shipped with Home Assistant).
Nothing here logs credentials or tokens.
"""
from __future__ import annotations

import asyncio
import itertools
import json
import logging
from typing import Any, Callable

_LOGGER = logging.getLogger(__name__)

BASE_URL = "wss://kiwi.cosa.com.tr/socket.io/"
PROVIDER = "beko"
_QUERY = {
    "EIO": "3",
    "transport": "websocket",
    "__sails_io_sdk_version": "1.2.1",
    "__sails_io_sdk_platform": "node",
    "__sails_io_sdk_language": "javascript",
}


class BekoApiError(Exception):
    """Raised for transport problems and for responses with ok == 0."""

    def __init__(self, code: Any = None, status: int | None = None) -> None:
        super().__init__(f"Beko API error (code={code}, status={status})")
        self.code = code
        self.status = status


# ---------------------------------------------------------------- codec ----
def encode_request(ack_id: int, verb: str, url: str,
                   data: dict | None, headers: dict) -> str:
    """Build a Socket.IO EVENT frame with ack id (text frame '42<id>[...]')."""
    payload = [verb, {"method": verb, "url": url,
                      "data": data or {}, "headers": headers}]
    return f"42{ack_id}{json.dumps(payload, separators=(',', ':'))}"


def decode(frame: str) -> tuple[str, int | None, Any]:
    """Return (kind, ack_id, payload) for one WebSocket text frame."""
    if not frame:
        return "empty", None, None
    eio = frame[0]
    if eio == "0":
        return "open", None, json.loads(frame[1:])
    if eio == "1":
        return "close", None, None
    if eio == "2":
        return "ping", None, None
    if eio == "3":
        return "pong", None, None
    if eio != "4" or len(frame) < 2:
        return "unknown", None, frame
    sio, rest = frame[1], frame[2:]
    if sio == "0":
        return "connect", None, None
    if sio == "1":
        return "disconnect", None, None
    if sio == "4":
        return "error", None, rest
    if sio in ("2", "3"):
        i = 0
        while i < len(rest) and rest[i].isdigit():
            i += 1
        ack_id = int(rest[:i]) if i else None
        payload = json.loads(rest[i:])
        return ("event" if sio == "2" else "ack"), ack_id, payload
    return "unknown", None, frame


# --------------------------------------------------------------- client ----
class BekoCloudClient:
    """One WebSocket connection; call connect() then login()."""

    def __init__(self, session, *, url: str = BASE_URL,
                 provider: str = PROVIDER, request_timeout: float = 20) -> None:
        self._session = session
        self._url = url
        self._provider = provider
        self._timeout = request_timeout
        self._token: str | None = None
        self._ws = None
        self._reader: asyncio.Task | None = None
        self._ids = itertools.count(1)
        self._pending: dict[int, asyncio.Future] = {}
        self._listeners: list[Callable[[str, Any], None]] = []
        self._on_disconnect: Callable[[], None] | None = None
        self._pinger: asyncio.Task | None = None
        self._last_rx = 0.0
        self._opened = asyncio.Event()
        self._connected = asyncio.Event()
        self.connected = False

    # -- public helpers ----------------------------------------------------
    @property
    def token(self) -> str | None:
        return self._token

    def set_token(self, token: str | None) -> None:
        self._token = token

    def add_listener(self, cb: Callable[[str, Any], None]) -> None:
        """cb(event_name, payload) is called for every server push."""
        self._listeners.append(cb)

    def set_disconnect_callback(self, cb: Callable[[], None]) -> None:
        self._on_disconnect = cb

    # -- connection --------------------------------------------------------
    async def connect(self, timeout: float = 15) -> None:
        self._opened.clear()
        self._connected.clear()
        try:
            self._ws = await asyncio.wait_for(
                self._session.ws_connect(
                    self._url, params=_QUERY, heartbeat=None), timeout)
        except asyncio.TimeoutError as err:
            raise BekoApiError("handshake_timeout") from err
        self._reader = asyncio.ensure_future(self._read_loop())
        try:
            await asyncio.wait_for(self._opened.wait(), timeout)
        except asyncio.TimeoutError as err:
            await self.close()
            raise BekoApiError("handshake_timeout") from err
        # Server normally sends the Socket.IO CONNECT ('40') right away;
        # do not hang if it does not.
        try:
            await asyncio.wait_for(self._connected.wait(), 3)
        except asyncio.TimeoutError:
            _LOGGER.debug("No Socket.IO CONNECT packet, continuing anyway")
        self.connected = True

    async def close(self) -> None:
        self.connected = False
        self._stop_pinger()
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        if self._reader is not None:
            self._reader.cancel()
            self._reader = None

    async def _read_loop(self) -> None:
        from aiohttp import WSMsgType  # lazy: keeps codec importable alone

        try:
            async for msg in self._ws:
                if msg.type == WSMsgType.TEXT:
                    await self._handle_frame(msg.data)
                elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING,
                                  WSMsgType.CLOSED, WSMsgType.ERROR):
                    break
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Reader stopped", exc_info=True)
        finally:
            self._handle_closed()

    async def _handle_frame(self, frame: str) -> None:
        try:
            kind, ack_id, payload = decode(frame)
        except (ValueError, IndexError):
            _LOGGER.debug("Undecodable frame ignored")
            return
        self._last_rx = asyncio.get_running_loop().time()
        if kind == "open":
            self._opened.set()
            self._start_pinger(payload or {})
        elif kind == "ping":
            await self._ws.send_str("3")
        elif kind == "connect":
            self._connected.set()
        elif kind == "ack":
            fut = self._pending.pop(ack_id, None)
            if fut is not None and not fut.done():
                fut.set_result(payload)
        elif kind == "event":
            name = payload[0] if payload else None
            arg = payload[1] if len(payload) > 1 else None
            for cb in list(self._listeners):
                try:
                    cb(name, arg)
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Listener failed")
        elif kind in ("close", "disconnect"):
            await self._ws.close()

    # Engine.IO v3: the CLIENT must send a ping ('2') every pingInterval and
    # the server answers with pong ('3'). Without it the cloud drops the socket.
    def _start_pinger(self, info: dict) -> None:
        self._stop_pinger()
        interval = float(info.get("pingInterval", 25000)) / 1000
        timeout = float(info.get("pingTimeout", 60000)) / 1000
        self._pinger = asyncio.ensure_future(self._ping_loop(interval, timeout))

    def _stop_pinger(self) -> None:
        if self._pinger is not None:
            self._pinger.cancel()
            self._pinger = None

    async def _ping_loop(self, interval: float, timeout: float) -> None:
        loop = asyncio.get_running_loop()
        try:
            while True:
                await asyncio.sleep(interval)
                if loop.time() - self._last_rx > interval + timeout:
                    _LOGGER.debug("Ping timeout, closing")
                    await self._ws.close()
                    return
                await self._ws.send_str("2")
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Pinger stopped", exc_info=True)

    def _handle_closed(self) -> None:
        was_connected = self.connected
        self.connected = False
        self._stop_pinger()
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(BekoApiError("connection_closed"))
        self._pending.clear()
        if was_connected and self._on_disconnect:
            self._on_disconnect()

    # -- requests ----------------------------------------------------------
    async def request(self, verb: str, url: str, data: dict | None = None,
                      *, auth: bool = True) -> Any:
        if not self.connected or self._ws is None:
            raise BekoApiError("not_connected")
        headers = {"provider": self._provider}
        if auth and self._token:
            headers["authToken"] = self._token
        ack_id = next(self._ids)
        fut = asyncio.get_running_loop().create_future()
        self._pending[ack_id] = fut
        await self._ws.send_str(encode_request(ack_id, verb, url, data, headers))
        try:
            payload = await asyncio.wait_for(fut, self._timeout)
        except asyncio.TimeoutError as err:
            self._pending.pop(ack_id, None)
            raise BekoApiError("timeout") from err
        resp = payload[0] if payload else {}
        body = resp.get("body", resp) if isinstance(resp, dict) else resp
        status = resp.get("statusCode") if isinstance(resp, dict) else None
        if (status is not None and status >= 400) or (
                isinstance(body, dict) and body.get("ok") == 0):
            code = body.get("code") if isinstance(body, dict) else None
            raise BekoApiError(code, status)
        return body

    # -- API calls (found in the Beko Connect app) -------------------------
    async def login(self, email: str, password: str) -> str:
        body = await self.request(
            "post", "/api/users/login",
            {"email": email, "password": password}, auth=False)
        self._token = body["authToken"]
        return self._token

    async def get_endpoints(self) -> list[dict]:
        return (await self.request("get", "/api/endpoints/getEndpoints"))["endpoints"]

    async def get_endpoint(self, endpoint_id: str) -> dict:
        body = await self.request(
            "post", "/api/endpoints/getEndpoint", {"endpoint": endpoint_id})
        return body["endpoint"]

    async def send_ac_state(self, endpoint_id: str, type_: str, value: Any) -> Any:
        """type_: acPower, acMode, targetTemperature, acFanSpeed, acTurbo, ..."""
        return await self.request(
            "post", "/api/endpoints/sendACState",
            {"endpoint": endpoint_id, "type": type_, "value": value})
