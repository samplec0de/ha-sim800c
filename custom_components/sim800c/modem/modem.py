"""SIM800C domain logic on top of Transport."""

from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .encoding import choose_encoding, to_ucs2_hex
from .errors import ModemError, NotRegistered, SmsSendError

if TYPE_CHECKING:
    from .transport import Transport

_CSQ_RE = re.compile(r"\+CSQ:\s*(\d+),")
_CREG_RE = re.compile(r"\+CREG:\s*\d+,(\d+)")
_REGISTERED_STATS = {1, 5}
_CMGS_REF_RE = re.compile(r"\+CMGS:\s*(\d+)")
_CSQ_NOT_KNOWN = 99  # 3GPP TS 27.007 sentinel: signal strength not detectable
# CSMP: fo=17, vp=167, pid=0, dcs=0 (GSM7) or dcs=8 (UCS2)
_CSMP_GSM = "AT+CSMP=17,167,0,0"
_CSMP_UCS2 = "AT+CSMP=17,167,0,8"

# +CLCC: <id>,<dir>,<stat>,<mode>,<mpty>[,"<number>",<type>[,"<alpha>"]]
_CLCC_RE = re.compile(
    r'\+CLCC:\s*\d+,(\d+),(\d+),\d+,\d+(?:,"([^"]*)")?',
)

# +CLCC <dir> field (3GPP TS 27.007)
CALL_DIR_OUTGOING = 0  # mobile-originated
CALL_DIR_INCOMING = 1  # mobile-terminated

# +CLCC <stat> field (3GPP TS 27.007)
CALL_STAT_ACTIVE = 0  # connected — the other party answered
CALL_STAT_HELD = 1
CALL_STAT_DIALING = 2  # MO, dialing
CALL_STAT_ALERTING = 3  # MO, remote is ringing
CALL_STAT_INCOMING = 4  # MT, ringing
CALL_STAT_WAITING = 5  # MT, call waiting


@dataclass(frozen=True)
class CallInfo:
    """A snapshot of the modem's current call, as reported by AT+CLCC."""

    direction: int
    """CALL_DIR_OUTGOING or CALL_DIR_INCOMING."""
    state: int
    """One of the CALL_STAT_* values."""
    number: str | None
    """The remote party's number, if the modem reported one (needs +CLIP)."""

    @property
    def is_incoming(self) -> bool:
        """True if this is a mobile-terminated (incoming) call."""
        return self.direction == CALL_DIR_INCOMING

    @property
    def is_answered(self) -> bool:
        """True once the call is connected (the other party picked up)."""
        return self.state == CALL_STAT_ACTIVE


class Modem:
    """High-level SIM800C AT-command operations built on top of Transport."""

    def __init__(self, transport: Transport) -> None:
        """Wrap the given Transport with SIM800C domain operations."""
        self._transport = transport

    async def initialize(self) -> None:
        """Disable echo, enter SMS text mode, and enable caller-ID reporting."""
        await self._transport.execute("ATE0")
        await self._transport.execute("AT+CMGF=1")
        # Report the caller's number on incoming calls (best-effort: some
        # SIM/network combinations reject this without a subscription).
        with contextlib.suppress(ModemError):
            await self._transport.execute("AT+CLIP=1")

    async def get_signal(self) -> int | None:
        """Return the signal strength in dBm, or None if not known."""
        resp = await self._transport.execute("AT+CSQ")
        match = _CSQ_RE.search(resp)
        if not match:
            return None
        rssi = int(match.group(1))
        if rssi == _CSQ_NOT_KNOWN:
            return None
        return -113 + 2 * rssi

    async def get_registration(self) -> bool:
        """Return True if the modem is registered on the network."""
        resp = await self._transport.execute("AT+CREG?")
        match = _CREG_RE.search(resp)
        return bool(match) and int(match.group(1)) in _REGISTERED_STATS

    async def send_sms(
        self,
        number: str,
        text: str,
        force_unicode: bool = False,  # noqa: FBT001, FBT002 — public API, matches the send_sms service field
    ) -> int:
        """Send an SMS to `number` and return the modem's +CMGS reference."""
        if not await self.get_registration():
            msg = "Modem is not registered on the network"
            raise NotRegistered(msg)

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
            msg = f"No +CMGS confirmation, got {final.strip()!r}"
            raise SmsSendError(msg)
        return int(match.group(1))

    async def dial(self, number: str) -> None:
        """Dial `number` as a voice call (a leading '+' is added if missing)."""
        if not number.startswith("+"):
            number = f"+{number}"
        await self._transport.execute(f"ATD{number};")

    async def hangup(self) -> None:
        """Hang up any active call."""
        await self._transport.execute("ATH")

    async def get_current_call(self) -> CallInfo | None:
        """Return the modem's current call via AT+CLCC, or None if idle."""
        resp = await self._transport.execute("AT+CLCC")
        match = _CLCC_RE.search(resp)
        if not match:
            return None
        direction = int(match.group(1))
        state = int(match.group(2))
        number = match.group(3) or None
        return CallInfo(direction=direction, state=state, number=number)
