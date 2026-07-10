"""SIM800C domain logic on top of Transport."""

from __future__ import annotations

import re

from .encoding import choose_encoding, to_ucs2_hex
from .errors import NotRegistered, SmsSendError
from .transport import Transport

_CSQ_RE = re.compile(r"\+CSQ:\s*(\d+),")
_CREG_RE = re.compile(r"\+CREG:\s*\d+,(\d+)")
_REGISTERED_STATS = {1, 5}


class Modem:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    async def initialize(self) -> None:
        await self._transport.execute("ATE0")
        await self._transport.execute("AT+CMGF=1")

    async def get_signal(self) -> int | None:
        resp = await self._transport.execute("AT+CSQ")
        match = _CSQ_RE.search(resp)
        if not match:
            return None
        rssi = int(match.group(1))
        if rssi == 99:
            return None
        return -113 + 2 * rssi

    async def get_registration(self) -> bool:
        resp = await self._transport.execute("AT+CREG?")
        match = _CREG_RE.search(resp)
        return bool(match) and int(match.group(1)) in _REGISTERED_STATS
