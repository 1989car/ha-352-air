"""Async UDP status listener for the 352 fresh-air device.

Status model (validated against a live G30): the device broadcasts its status
frame to UDP port 11530 every ~2-8 seconds regardless of connection state.
The frame format and CRC were reverse-engineered and verified with real
captures (see protocol.parse_response).

Control over local UDP is *not* accepted while the device is cloud-online; it
is planned to go through the 352 cloud in a later milestone.  A light
subscribe query is sent periodically (it is harmless and prompts status
pushes); command helpers still exist for the offline/local-control scenario.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import socket
from collections.abc import Callable
from datetime import datetime

from .const import UDP_PORT
from .protocol import DeviceState, build_frame, parse_response

_LOGGER = logging.getLogger(__name__)

STATUS_STALE_AFTER = 60  # seconds without a status frame -> device unavailable


class Air352Hub:
    """Listens for a single 352 fresh-air device's status broadcasts."""

    def __init__(
        self,
        mac: str,
        host: str | None = None,
        model: str = "g30",
        device_type: int = 0x04,
        auth_code: int = 0xA31A,
        company_code: int = 0xF2,
    ) -> None:
        self.mac = mac.upper()
        self.host = host
        self.model = model
        self.device_type = device_type
        self.auth_code = auth_code
        self.company_code = company_code
        self._mac_bytes = bytes.fromhex(self.mac.replace(":", "").replace("-", ""))
        self._state = DeviceState()
        self._last_seen = 0.0
        self._listeners: list[Callable[[], None]] = []
        self._transport: asyncio.DatagramTransport | None = None
        self._outer_seq = 0
        self._command_seq = 0

    # -- state -----------------------------------------------------------------

    @property
    def state(self) -> DeviceState:
        return self._state

    @property
    def last_seen(self) -> float:
        return self._last_seen

    @property
    def available(self) -> bool:
        return self._last_seen > 0 and (datetime.now().timestamp() - self._last_seen) < STATUS_STALE_AFTER

    def register_callback(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def _notify(self) -> None:
        for cb in self._listeners:
            cb()

    # -- receiving -------------------------------------------------------------

    async def start_listener(self) -> None:
        """Bind UDP 11530 and start receiving status frames (idempotent)."""
        if self._transport is not None:
            return
        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass
        try:
            sock.bind(("0.0.0.0", UDP_PORT))
        except OSError as exc:
            _LOGGER.warning("无法绑定 UDP %s（可能已被占用）: %s", UDP_PORT, exc)
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: _StatusProtocol(self._on_datagram),
            sock=sock,
        )
        _LOGGER.info("352 状态监听已启动: udp 0.0.0.0:%s (device %s)", UDP_PORT, self.mac)

    def _on_datagram(self, data: bytes) -> None:
        # Only accept frames from our device (identified by its MAC).
        if len(data) >= 8 and data[2:8] != self._mac_bytes:
            return
        state = parse_response(data)
        if state is None:
            return
        self._state = state
        self._last_seen = datetime.now().timestamp()
        self._notify()

    async def close(self) -> None:
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    # -- keepalive / subscribe --------------------------------------------------

    def _next_outer_seq(self) -> int:
        self._outer_seq = (self._outer_seq + 1) % 0x8000
        return self._outer_seq

    def _next_command_seq(self) -> int:
        self._command_seq = (self._command_seq + 1) % 0x8000
        return self._command_seq

    async def async_nudge(self) -> None:
        """Send a harmless query to encourage a status push (best effort)."""
        if self._transport is None:
            return
        frame = build_frame(
            mac=self.mac,
            device_type=self.device_type,
            auth_code=self.auth_code,
            company_code=self.company_code,
            outer_seq=self._next_outer_seq(),
            command_seq=self._next_command_seq(),
            prefix=0x50,
            value=0x01,
        )
        if self.host:
            self._transport.sendto(frame, (self.host, UDP_PORT))
        else:
            self._transport.sendto(frame, ("255.255.255.255", UDP_PORT))

    # -- command helpers (local UDP; accepted only when the device is offline) ----

    async def async_send_command(self, prefix: int, value: int, two_byte_value: bool = False) -> None:
        if not self.host:
            _LOGGER.warning("未配置设备 IP，无法发送控制命令")
            return
        frame = build_frame(
            mac=self.mac,
            device_type=self.device_type,
            auth_code=self.auth_code,
            company_code=self.company_code,
            outer_seq=self._next_outer_seq(),
            command_seq=self._next_command_seq(),
            prefix=prefix,
            value=value,
            two_byte_value=two_byte_value,
        )
        self._transport.sendto(frame, (self.host, UDP_PORT))
        # Prompt an immediate status push so entities refresh without waiting
        # for the periodic broadcast (the device may pause pushes while off).
        await asyncio.sleep(0.2)
        await self.async_nudge()

    def optimistic_power(self, on: bool) -> None:
        """Immediately reflect an issued power command (real frames override)."""
        st = copy.copy(self._state)
        st.power = on
        if not on:
            st.wind_speed = 0
        self._state = st
        self._notify()


class _StatusProtocol(asyncio.DatagramProtocol):
    def __init__(self, on_datagram: Callable[[bytes], None]) -> None:
        self._on_datagram = on_datagram

    def datagram_received(self, data: bytes, addr) -> None:  # noqa: ANN001
        self._on_datagram(data)

    def error_received(self, exc: Exception) -> None:
        _LOGGER.debug("UDP error: %s", exc)
