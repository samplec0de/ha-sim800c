"""Shared test fixtures for the SIM800C modem layer."""

from __future__ import annotations

import re

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Make custom_components discoverable to Home Assistant's loader in tests."""
    return


class FakeSerial:
    """
    A scripted stand-in for serial.Serial.

    Rules map a regex matched against each written line/payload to the bytes
    the modem should emit in response. Matching a rule enqueues its response
    into the read buffer, which read()/in_waiting then drain.
    """

    def __init__(self, rules: list[tuple[str, bytes]] | None = None) -> None:
        """Initialize the fake serial port with an optional response rule set."""
        self.rules = rules or []
        self.is_open = True
        self.written: list[bytes] = []
        self._read_buffer = bytearray()

    # --- API used by Transport ---
    @property
    def in_waiting(self) -> int:
        """Return the number of bytes currently queued for reading."""
        return len(self._read_buffer)

    def read(self, size: int) -> bytes:
        """Read and consume up to `size` bytes from the read buffer."""
        chunk = bytes(self._read_buffer[:size])
        del self._read_buffer[:size]
        return chunk

    def write(self, data: bytes) -> int:
        """Record the written bytes and enqueue any matching rule's response."""
        self.written.append(data)
        for pattern, response in self.rules:
            if re.search(pattern, data.decode("utf-8", "ignore")):
                self._read_buffer.extend(response)
                break
        return len(data)

    def flush(self) -> None:
        """No-op flush to satisfy the serial.Serial interface."""

    def close(self) -> None:
        """Mark the fake port as closed."""
        self.is_open = False

    # --- test helper ---
    def push(self, data: bytes) -> None:
        """Manually enqueue bytes to be read (unsolicited responses)."""
        self._read_buffer.extend(data)
