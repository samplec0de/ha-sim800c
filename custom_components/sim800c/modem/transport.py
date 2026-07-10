"""Serial transport: single owner of the port, serialized transactions."""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Callable, Sequence

import serial

from .errors import ModemError, ModemTimeout

_DEFAULT_ERROR_TOKENS = ("ERROR", "+CME ERROR", "+CMS ERROR")


class Transaction:
    """A locked exchange with the modem. Not reentrant."""

    def __init__(self, transport: "Transport") -> None:
        self._t = transport

    async def send_line(self, command: str) -> None:
        await asyncio.to_thread(self._t._write_sync, f"{command}\r\n".encode())

    async def write_raw(self, data: bytes) -> None:
        await asyncio.to_thread(self._t._write_sync, data)

    async def read_until(
        self,
        tokens: Sequence[str],
        error_tokens: Sequence[str] = _DEFAULT_ERROR_TOKENS,
        timeout: float = 5.0,
    ) -> str:
        return await asyncio.to_thread(
            self._t._read_until_sync, tuple(tokens), tuple(error_tokens), timeout
        )


class Transport:
    """Owns the serial port and serializes all access with a lock."""

    def __init__(
        self,
        device: str,
        baud: int,
        serial_factory: Callable[..., serial.Serial] = serial.Serial,
    ) -> None:
        self._device = device
        self._baud = baud
        self._serial_factory = serial_factory
        self._serial: serial.Serial | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        self._serial = await asyncio.to_thread(
            self._serial_factory, self._device, self._baud, timeout=0.1
        )

    async def close(self) -> None:
        if self._serial is not None:
            await asyncio.to_thread(self._serial.close)
            self._serial = None

    @asynccontextmanager
    async def transaction(self):
        async with self._lock:
            yield Transaction(self)

    async def execute(
        self,
        command: str,
        *,
        expect: Sequence[str] = ("OK",),
        error_tokens: Sequence[str] = _DEFAULT_ERROR_TOKENS,
        timeout: float = 5.0,
    ) -> str:
        async with self.transaction() as txn:
            await txn.send_line(command)
            return await txn.read_until(expect, error_tokens, timeout)

    # --- synchronous helpers (run in a worker thread) ---
    def _write_sync(self, data: bytes) -> None:
        assert self._serial is not None
        self._serial.write(data)
        self._serial.flush()

    def _read_until_sync(
        self, tokens: tuple[str, ...], error_tokens: tuple[str, ...], timeout: float
    ) -> str:
        assert self._serial is not None
        buffer = bytearray()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            waiting = self._serial.in_waiting
            if waiting:
                buffer.extend(self._serial.read(waiting))
                decoded = buffer.decode("utf-8", "ignore")
                if any(tok in decoded for tok in error_tokens):
                    raise ModemError(f"Modem error: {decoded.strip()!r}")
                if any(tok in decoded for tok in tokens):
                    return decoded
            else:
                time.sleep(0.02)
        raise ModemTimeout(
            f"No {tokens!r} within {timeout}s; got {buffer.decode('utf-8', 'ignore')!r}"
        )
