"""SIM800C domain logic on top of Transport."""

from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .encoding import choose_encoding, from_ucs2_hex, to_ucs2_hex
from .errors import ModemError, NotRegistered, SmsSendError

if TYPE_CHECKING:
    from .transport import Transport

_CSQ_RE = re.compile(r"\+CSQ:\s*(\d+),")
_CREG_RE = re.compile(r"\+CREG:\s*\d+,(\d+)")
_REGISTERED_STATS = {1, 5}
_CMGS_REF_RE = re.compile(r"\+CMGS:\s*(\d+)")
_CSQ_NOT_KNOWN = 99  # 3GPP TS 27.007 sentinel: signal strength not detectable

# +CMGL header, text mode. Base fields (CSDH=0):
#   +CMGL: <index>,"<stat>","<oa>","<alpha>","<scts>"
# With AT+CSDH=1 the modem appends <tooa>,<fo>,<pid>,<dcs>,<sca>,<tosca>,<length>;
# <dcs> (data coding scheme) is captured when that extended tail is present.
_CMGL_HEADER_RE = re.compile(
    r'\+CMGL:\s*(\d+),"[^"]*","([^"]*)","[^"]*","([^"]*)"'
    r"(?:,\d+,\d+,\d+,(\d+))?"
)
_DCS_UCS2_MASK = 0x08  # DCS alphabet bits == UCS2 (3GPP TS 23.038)
_UCS2_HEX_QUANTUM = 4  # one UCS2 code unit is 4 hex digits
# CSMP: fo=17, vp=167, pid=0, dcs=0 (GSM7) or dcs=8 (UCS2)
_CSMP_GSM = "AT+CSMP=17,167,0,0"
_CSMP_UCS2 = "AT+CSMP=17,167,0,8"

# +CLCC: <id>,<dir>,<stat>,<mode>,<mpty>[,"<number>",<type>[,"<alpha>"]]
_CLCC_RE = re.compile(
    r'\+CLCC:\s*\d+,(\d+),(\d+),\d+,\d+(?:,"([^"]*)")?',
)

# Audio playback into a voice call (proven on SIM800 R14.18 firmware).
# The AMR-NB file is uploaded to the modem's flash, then streamed into the
# active call's uplink so the *remote* party hears it.
_PLAY_PATH = "C:\\User\\ha_play.amr"
# Max bytes per AT+FSWRITE chunk accepted by this firmware.
_AUDIO_CHUNK_SIZE = 4096
# AT+FSWRITE mode: 1 = append (mode 0 is rejected by this firmware).
_FSWRITE_MODE_APPEND = 1
# AT+FSWRITE input-timeout argument (seconds the modem waits for the payload).
_FSWRITE_INPUT_TIMEOUT = 30
# AT+CREC output channel: 0 = into the call uplink (the remote hears it).
_CREC_CHANNEL_CALL = 0
# Default playback volume (0-100) for AT+CREC.
_CREC_DEFAULT_VOLUME = 90

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


@dataclass(frozen=True)
class SmsMessage:
    """A received SMS as parsed from AT+CMGL, decoded to text."""

    index: int
    """Storage slot on the modem; used to delete the message."""
    sender: str
    """Originating address (phone number)."""
    timestamp: str
    """Service-centre timestamp, e.g. '24/07/11,02:30:00+12' (raw, as reported)."""
    text: str
    """Decoded message body (GSM or UCS2)."""


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
        # Show full text-mode headers (incl. DCS) so AT+CMGL exposes the
        # encoding of each received message. Best-effort: harmless if refused.
        with contextlib.suppress(ModemError):
            await self._transport.execute("AT+CSDH=1")

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

    async def list_unread_sms(self) -> list[SmsMessage]:
        """
        Read and return unread received SMS via AT+CMGL="REC UNREAD".

        Listing unread messages also marks them READ on the modem, so a
        subsequent poll will not return them again even if deletion fails.
        """
        resp = await self._transport.execute(
            'AT+CMGL="REC UNREAD"',
            timeout=10.0,
        )
        return _parse_cmgl(resp)

    async def delete_sms(self, index: int) -> None:
        """Delete the message stored at `index` (AT+CMGD)."""
        await self._transport.execute(f"AT+CMGD={index}")

    async def upload_audio(self, data: bytes) -> None:
        """
        Upload an AMR-NB clip to the modem's flash for later playback.

        Overwrites any previously uploaded clip, then writes `data` in
        <=4096-byte chunks via chunked AT+FSWRITE (append mode). The file must
        exist (AT+FSCREATE) before it can be written to.
        """
        # Remove any previous file; ignore ERROR when it does not yet exist.
        with contextlib.suppress(ModemError):
            await self._transport.execute(f"AT+FSDEL={_PLAY_PATH}")
        await self._transport.execute(f"AT+FSCREATE={_PLAY_PATH}")

        async with self._transport.transaction() as txn:
            for start in range(0, len(data), _AUDIO_CHUNK_SIZE):
                chunk = data[start : start + _AUDIO_CHUNK_SIZE]
                await txn.send_line(
                    f"AT+FSWRITE={_PLAY_PATH},{_FSWRITE_MODE_APPEND},"
                    f"{len(chunk)},{_FSWRITE_INPUT_TIMEOUT}"
                )
                await txn.read_until((">",), timeout=5.0)
                await txn.write_raw(chunk)
                await txn.read_until(("OK",), timeout=10.0)

    async def play_audio(self, volume: int = _CREC_DEFAULT_VOLUME) -> None:
        """Play the uploaded clip into the active call (AT+CREC=4)."""
        await self._transport.execute(
            f'AT+CREC=4,"{_PLAY_PATH}",{_CREC_CHANNEL_CALL},{volume}'
        )

    async def stop_audio(self) -> None:
        """Stop any in-progress playback (AT+CREC=5); best-effort."""
        with contextlib.suppress(ModemError):
            await self._transport.execute("AT+CREC=5")


def _parse_cmgl(resp: str) -> list[SmsMessage]:
    """Parse an AT+CMGL text-mode response into SmsMessage records."""
    lines = resp.replace("\r\n", "\n").split("\n")
    # Drop the final "OK" terminator (and blank lines around it) so it does
    # not get absorbed into the last message's body. Only the single trailing
    # terminator is removed, so a message body that itself ends in "OK" stays.
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and lines[-1].strip() == "OK":
        lines.pop()
    while lines and not lines[-1].strip():
        lines.pop()

    messages: list[SmsMessage] = []
    i = 0
    while i < len(lines):
        header = _CMGL_HEADER_RE.search(lines[i])
        if not header:
            i += 1
            continue
        index = int(header.group(1))
        sender = header.group(2)
        timestamp = header.group(3)
        dcs = int(header.group(4)) if header.group(4) is not None else None

        # Body spans the following lines until the next header or the end.
        body_lines: list[str] = []
        i += 1
        while i < len(lines) and not _CMGL_HEADER_RE.search(lines[i]):
            body_lines.append(lines[i])
            i += 1
        body = "\n".join(body_lines).strip("\n")

        if dcs is not None and (dcs & _DCS_UCS2_MASK):
            text = from_ucs2_hex(body)
            sender = from_ucs2_hex(sender) if _looks_like_ucs2_hex(sender) else sender
        else:
            text = body
        messages.append(
            SmsMessage(index=index, sender=sender, timestamp=timestamp, text=text)
        )
    return messages


def _looks_like_ucs2_hex(value: str) -> bool:
    """Return True if `value` is a plausible UCS2 hex string (4-aligned hex)."""
    return (
        len(value) >= _UCS2_HEX_QUANTUM
        and len(value) % _UCS2_HEX_QUANTUM == 0
        and all(c in "0123456789ABCDEFabcdef" for c in value)
    )
