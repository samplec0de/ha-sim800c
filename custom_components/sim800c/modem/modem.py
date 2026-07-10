"""SIM800C domain logic on top of Transport."""

from __future__ import annotations

import re

from .encoding import choose_encoding, to_ucs2_hex
from .errors import ModemError, NotRegistered, SmsSendError
from .transport import Transport

_CSQ_RE = re.compile(r"\+CSQ:\s*(\d+),")
_CREG_RE = re.compile(r"\+CREG:\s*\d+,(\d+)")
_REGISTERED_STATS = {1, 5}
_CMGS_REF_RE = re.compile(r"\+CMGS:\s*(\d+)")
# CSMP: fo=17, vp=167, pid=0, dcs=0 (GSM7) or dcs=8 (UCS2)
_CSMP_GSM = "AT+CSMP=17,167,0,0"
_CSMP_UCS2 = "AT+CSMP=17,167,0,8"


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

    async def send_sms(
        self, number: str, text: str, force_unicode: bool = False
    ) -> int:
        if not await self.get_registration():
            raise NotRegistered("Modem is not registered on the network")

        if not number.startswith("+"):
            number = f"+{number}"

        encoding = choose_encoding(text, force_unicode)
        if encoding == "UCS2":
            await self._transport.execute('AT+CSCS="UCS2"')
            await self._transport.execute(_CSMP_UCS2)
            address = to_ucs2_hex(number)
            body = to_ucs2_hex(text).encode("ascii")
        else:
            await self._transport.execute('AT+CSCS="GSM"')
            await self._transport.execute(_CSMP_GSM)
            address = number
            body = text.encode("ascii")

        try:
            async with self._transport.transaction() as txn:
                await txn.send_line(f'AT+CMGS="{address}"')
                await txn.read_until((">",), timeout=5.0)
                await txn.write_raw(body + b"\x1a")
                final = await txn.read_until(("+CMGS",), timeout=15.0)
        except ModemError as err:
            raise SmsSendError(str(err)) from err

        match = _CMGS_REF_RE.search(final)
        if not match:
            raise SmsSendError(f"No +CMGS confirmation, got {final.strip()!r}")
        return int(match.group(1))

    async def dial(self, number: str) -> None:
        if not number.startswith("+"):
            number = f"+{number}"
        await self._transport.execute(f"ATD{number};")

    async def hangup(self) -> None:
        await self._transport.execute("ATH")
