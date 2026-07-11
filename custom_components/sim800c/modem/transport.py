"""Serial transport: single owner of the port, serialized transactions."""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import serial

from .errors import ModemError, ModemTimeout

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Sequence

_DEFAULT_ERROR_TOKENS = ("ERROR", "+CME ERROR", "+CMS ERROR")
_ERROR_TOKEN_BYTES = (b"ERROR", b"+CME ERROR", b"+CMS ERROR")
# Byte values of CR / LF, used to trim the framing around a binary payload.
_CRLF_BYTES = (0x0D, 0x0A)


class Transaction:
    """A locked exchange with the modem. Not reentrant."""

    def __init__(self, transport: Transport) -> None:
        """Bind this transaction to the owning Transport."""
        self._t = transport

    async def send_line(self, command: str) -> None:
        """Write `command` followed by CRLF to the modem."""
        await asyncio.to_thread(
            self._t._write_sync,  # noqa: SLF001 — Transaction/Transport are intentionally coupled within this module
            f"{command}\r\n".encode(),
        )

    async def write_raw(self, data: bytes) -> None:
        """Write raw bytes to the modem without any framing."""
        await asyncio.to_thread(
            self._t._write_sync,  # noqa: SLF001 — Transaction/Transport are intentionally coupled within this module
            data,
        )

    async def read_until(
        self,
        tokens: Sequence[str],
        error_tokens: Sequence[str] = _DEFAULT_ERROR_TOKENS,
        timeout: float = 5.0,  # noqa: ASYNC109 — intentional API, not a cancellation timeout
    ) -> str:
        """Read from the modem until one of `tokens` or `error_tokens` appears."""
        return await asyncio.to_thread(
            self._t._read_until_sync,  # noqa: SLF001 — Transaction/Transport are intentionally coupled within this module
            tuple(tokens),
            tuple(error_tokens),
            timeout,
        )


class Transport:
    """Owns the serial port and serializes all access with a lock."""

    def __init__(
        self,
        device: str,
        baud: int,
        serial_factory: Callable[..., serial.Serial] = serial.Serial,
    ) -> None:
        """Configure the port to open; the port itself opens on connect()."""
        self._device = device
        self._baud = baud
        self._serial_factory = serial_factory
        self._serial: serial.Serial | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Open the serial port."""
        self._serial = await asyncio.to_thread(
            self._serial_factory, self._device, self._baud, timeout=0.1
        )

    async def close(self) -> None:
        """Close the serial port, if open."""
        if self._serial is not None:
            await asyncio.to_thread(self._serial.close)
            self._serial = None

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[Transaction]:
        """Yield a Transaction with exclusive access to the port."""
        async with self._lock:
            yield Transaction(self)

    async def execute(
        self,
        command: str,
        *,
        expect: Sequence[str] = ("OK",),
        error_tokens: Sequence[str] = _DEFAULT_ERROR_TOKENS,
        timeout: float = 5.0,  # noqa: ASYNC109 — intentional API, not a cancellation timeout
    ) -> str:
        """Send `command` and return the response once `expect` is seen."""
        async with self.transaction() as txn:
            await txn.send_line(command)
            return await txn.read_until(expect, error_tokens, timeout)

    async def read_file_bytes(
        self,
        command: str,
        size: int,
        timeout: float = 15.0,  # noqa: ASYNC109 — intentional API, not a cancellation timeout
    ) -> bytes:
        """
        Send `command` and read back a binary payload of `size` bytes.

        Used for AT+FSREAD, whose response frames the raw file bytes between a
        header and a trailing OK. Runs the blocking read in a worker thread and
        holds the port lock for the whole exchange, like execute().
        """
        async with self._lock:
            return await asyncio.to_thread(
                self._read_file_bytes_sync, command, size, timeout
            )

    # --- synchronous helpers (run in a worker thread) ---
    def _write_sync(self, data: bytes) -> None:
        assert self._serial is not None  # noqa: S101 — type-narrowing guard, not a validation check
        self._serial.write(data)
        self._serial.flush()

    def _read_until_sync(
        self, tokens: tuple[str, ...], error_tokens: tuple[str, ...], timeout: float
    ) -> str:
        assert self._serial is not None  # noqa: S101 — type-narrowing guard, not a validation check
        buffer = bytearray()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            waiting = self._serial.in_waiting
            if waiting:
                buffer.extend(self._serial.read(waiting))
                decoded = buffer.decode("utf-8", "ignore")
                if any(tok in decoded for tok in error_tokens):
                    msg = f"Modem error: {decoded.strip()!r}"
                    raise ModemError(msg)
                if any(tok in decoded for tok in tokens):
                    return decoded
            else:
                time.sleep(0.02)
        got = buffer.decode("utf-8", "ignore")
        msg = f"No {tokens!r} within {timeout}s; got {got!r}"
        raise ModemTimeout(msg)

    def _read_file_bytes_sync(self, command: str, size: int, timeout: float) -> bytes:
        assert self._serial is not None  # noqa: S101 — type-narrowing guard, not a validation check
        self._serial.write(f"{command}\r\n".encode())
        self._serial.flush()
        buffer = bytearray()
        deadline = time.monotonic() + timeout
        # TODO(hw): verify on SIM800 R14.18 — the exact FSREAD framing (any
        # header line before the payload, and the trailing OK) is provisional.
        # We read until we have at least `size` bytes plus an OK, then treat the
        # `size` bytes immediately before the trailing OK as the file payload.
        while time.monotonic() < deadline:
            waiting = self._serial.in_waiting
            if waiting:
                buffer.extend(self._serial.read(waiting))
                if len(buffer) >= size and b"OK" in buffer:
                    break
                # Only surface an error before the payload is complete; binary
                # data may coincidentally contain these tokens.
                if len(buffer) < size and any(
                    tok in buffer for tok in _ERROR_TOKEN_BYTES
                ):
                    decoded = buffer.decode("utf-8", "ignore").strip()
                    msg = f"Modem error reading file: {decoded!r}"
                    raise ModemError(msg)
            else:
                time.sleep(0.02)
        end = buffer.rfind(b"OK")
        if end == -1:
            msg = f"No OK terminator reading {size} bytes; got {len(buffer)} bytes"
            raise ModemTimeout(msg)
        # Trim the CR/LF that separates the payload from the trailing OK.
        while end > 0 and buffer[end - 1] in _CRLF_BYTES:
            end -= 1
        start = max(0, end - size)
        return bytes(buffer[start:end])
