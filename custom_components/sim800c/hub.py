"""Home Assistant-facing wrapper around the modem layer."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .const import (
    CALL_STATE_ACTIVE,
    CALL_STATE_DIALING,
    CALL_STATE_IDLE,
    CALL_STATE_INCOMING,
    CALL_STATE_RINGING,
    LOGGER,
)
from .modem import (
    CALL_STAT_ACTIVE,
    CALL_STAT_ALERTING,
    Modem,
    ModemError,
    NotRegistered,
    Transport,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from .modem import CallInfo, SmsMessage

_MAX_ATTEMPTS = 3
_RETRY_BACKOFF = 2.0

# How often the background loop polls AT+CLCC to catch incoming calls.
_MONITOR_INTERVAL = 3.0
# Poll for received SMS every Nth monitor tick (~9s at the default interval);
# SMS is far less latency-sensitive than call state.
_SMS_POLL_EVERY = 3
# Faster polling while we are actively driving an outgoing call.
_CALL_POLL_INTERVAL = 1.0
# Default seconds to let an outgoing call ring before auto-hanging-up.
DEFAULT_RING_DURATION = 30.0
# Default playback volume (0-100) for call_and_play.
DEFAULT_PLAY_VOLUME = 90
# Grace seconds added after a known clip length before hanging up.
_PLAYBACK_TAIL = 2.0
# Hard cap on how long we wait for playback when the clip length is unknown.
_PLAYBACK_MAX = 60.0


@dataclass(frozen=True)
class CallResult:
    """Outcome of an outgoing call placed via async_call."""

    answered: bool
    """True if the other party picked up before we hung up."""
    final_state: str
    """One of 'answered', 'no_answer' (rang out), or 'ended' (remote hung up)."""
    played: bool = False
    """True if the audio clip was played into the answered call."""


class ModemHub:
    """Serialize Home Assistant access to a single SIM800C modem."""

    def __init__(
        self,
        device: str,
        baud: int,
        on_state_change: Callable[[], None] | None = None,
        on_incoming_call: Callable[[str | None], None] | None = None,
        on_incoming_sms: Callable[[SmsMessage], None] | None = None,
    ) -> None:
        """Create a hub bound to the given serial device and baud rate."""
        self._transport = Transport(device, baud)
        self._modem = Modem(self._transport)
        self.signal_dbm: int | None = None
        self.registered: bool = False
        self.call_state: str = CALL_STATE_IDLE
        self.incoming_call: bool = False
        self.incoming_number: str | None = None
        self.last_caller: str | None = None
        self.last_sms: SmsMessage | None = None
        self._send_lock = asyncio.Lock()
        self._call_lock = asyncio.Lock()
        self._state_lock = asyncio.Lock()
        self._sms_lock = asyncio.Lock()
        self._monitor_task: asyncio.Task[None] | None = None
        self._on_state_change = on_state_change
        self._on_incoming_call = on_incoming_call
        self._on_incoming_sms = on_incoming_sms

    async def async_start(self) -> None:
        """Open the serial connection, initialize, and start call monitoring."""
        await self._transport.connect()
        await self._modem.initialize()

    def start_monitoring(self) -> None:
        """Start the background loop that watches for incoming calls."""
        if self._monitor_task is None:
            self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def async_stop(self) -> None:
        """Stop monitoring and close the serial connection."""
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitor_task
            self._monitor_task = None
        await self._transport.close()

    async def async_update_diagnostics(self) -> None:
        """Refresh cached registration and signal-strength state."""
        self.registered = await self._modem.get_registration()
        self.signal_dbm = await self._modem.get_signal()

    # --- outgoing calls -------------------------------------------------

    async def async_call(
        self, target: str, ring_duration: float = DEFAULT_RING_DURATION
    ) -> CallResult:
        """
        Place a voice call, watch it, and auto-hang-up.

        Dials `target`, then polls the call state until the other party answers,
        the remote end hangs up, or `ring_duration` seconds elapse — whichever
        comes first — and then hangs up. Returns whether the call was answered.
        """
        async with self._call_lock:
            await self._modem.dial(target)
            LOGGER.info("Calling %s (ring up to %ss)", target, ring_duration)
            loop = asyncio.get_running_loop()
            deadline = loop.time() + ring_duration
            answered = False
            saw_call = False
            remote_ended = False

            while loop.time() < deadline:
                await asyncio.sleep(_CALL_POLL_INTERVAL)
                call = await self._refresh_call_state()
                if call is None:
                    if saw_call:
                        remote_ended = True
                        break
                    continue
                saw_call = True
                if call.is_answered:
                    answered = True
                    break

            await self._safe_hangup()
            async with self._state_lock:
                self._apply_call(None)

            if answered:
                final_state = "answered"
            elif remote_ended:
                final_state = "ended"
            else:
                final_state = "no_answer"
            LOGGER.info("Call to %s finished: %s", target, final_state)
            return CallResult(answered=answered, final_state=final_state)

    async def async_call_and_play(
        self,
        target: str,
        audio: bytes,
        duration: float | None = None,
        ring_duration: float = DEFAULT_RING_DURATION,
        volume: int = DEFAULT_PLAY_VOLUME,
    ) -> CallResult:
        """
        Place a call and play an AMR-NB clip into it so the callee hears it.

        Uploads `audio` to the modem, dials `target`, and — once the other party
        answers — plays the clip into the call's uplink. If `duration` (the known
        clip length in seconds) is given, the call is held that long plus a short
        tail; otherwise playback is watched until the call drops or a 60s cap is
        reached. The call is always auto-hung-up. Returns whether it was answered
        and whether the clip was played.
        """
        async with self._call_lock:
            # Upload before dialing so the file is ready the moment we connect.
            await self._modem.upload_audio(audio)
            await self._modem.dial(target)
            LOGGER.info(
                "Calling %s to play audio (ring up to %ss)", target, ring_duration
            )
            loop = asyncio.get_running_loop()
            deadline = loop.time() + ring_duration
            answered = False
            played = False
            saw_call = False
            remote_ended = False

            while loop.time() < deadline:
                await asyncio.sleep(_CALL_POLL_INTERVAL)
                call = await self._refresh_call_state()
                if call is None:
                    if saw_call:
                        remote_ended = True
                        break
                    continue
                saw_call = True
                if call.is_answered:
                    answered = True
                    break

            if answered:
                LOGGER.info("Call to %s answered; playing audio", target)
                await self._modem.play_audio(volume)
                played = True
                await self._await_playback(duration)
                await self._modem.stop_audio()

            await self._safe_hangup()
            async with self._state_lock:
                self._apply_call(None)

            if answered:
                final_state = "answered"
            elif remote_ended:
                final_state = "ended"
            else:
                final_state = "no_answer"
            LOGGER.info(
                "Call-and-play to %s finished: %s (played=%s)",
                target,
                final_state,
                played,
            )
            return CallResult(answered=answered, final_state=final_state, played=played)

    async def _await_playback(self, duration: float | None) -> None:
        """Hold the call while the clip plays, then return."""
        if duration is not None:
            await asyncio.sleep(duration + _PLAYBACK_TAIL)
            return
        # Unknown clip length: poll until the call drops or the hard cap hits.
        loop = asyncio.get_running_loop()
        deadline = loop.time() + _PLAYBACK_MAX
        while loop.time() < deadline:
            await asyncio.sleep(_CALL_POLL_INTERVAL)
            if await self._refresh_call_state() is None:
                return

    async def async_hang_up(self) -> None:
        """Hang up the current call, if any."""
        await self._safe_hangup()
        async with self._state_lock:
            self._apply_call(None)

    async def _safe_hangup(self) -> None:
        try:
            await self._modem.hangup()
        except ModemError as err:
            # ATH with no active call errors on some firmware; harmless.
            LOGGER.debug("Hang-up returned an error (likely no active call): %s", err)

    # --- background monitoring -----------------------------------------

    async def _monitor_loop(self) -> None:
        ticks = 0
        while True:
            await asyncio.sleep(_MONITOR_INTERVAL)
            if self._call_lock.locked():
                # An outgoing call is driving state itself; don't double-poll.
                continue
            try:
                await self._refresh_call_state()
            except ModemError as err:
                LOGGER.debug("Call-state poll failed: %s", err)

            ticks += 1
            if ticks % _SMS_POLL_EVERY == 0:
                try:
                    await self.async_poll_incoming_sms()
                except ModemError as err:
                    LOGGER.debug("SMS poll failed: %s", err)

    async def async_poll_incoming_sms(self) -> None:
        """Read unread SMS, emit them, and delete each from the modem."""
        async with self._sms_lock:
            messages = await self._modem.list_unread_sms()
            for message in messages:
                LOGGER.info("SMS received from %s", message.sender)
                self.last_sms = message
                if self._on_incoming_sms:
                    self._on_incoming_sms(message)
                try:
                    await self._modem.delete_sms(message.index)
                except ModemError as err:
                    # Already marked READ by the list, so it won't re-fire;
                    # deletion is only to free storage.
                    LOGGER.warning("Could not delete SMS %s: %s", message.index, err)
            if messages and self._on_state_change:
                self._on_state_change()

    async def _refresh_call_state(self) -> CallInfo | None:
        """Poll AT+CLCC once and update cached call state atomically."""
        async with self._state_lock:
            call = await self._modem.get_current_call()
            self._apply_call(call)
            return call

    def _apply_call(self, call: CallInfo | None) -> None:
        """Recompute cached call state from a CLCC snapshot; fire callbacks."""
        prev_state = self.call_state
        prev_incoming = self.incoming_call

        if call is None:
            self.call_state = CALL_STATE_IDLE
            self.incoming_call = False
            self.incoming_number = None
        elif call.is_incoming:
            self.incoming_call = True
            self.incoming_number = call.number
            self.call_state = (
                CALL_STATE_ACTIVE if call.is_answered else CALL_STATE_INCOMING
            )
        else:
            self.incoming_call = False
            self.incoming_number = None
            self.call_state = _outgoing_state(call.state)

        # Fire the incoming-call event on the rising edge only.
        if self.incoming_call and not prev_incoming:
            # Persist the caller's number when known; never overwrite a known
            # last_caller with None, and never clear it when the call ends.
            if self.incoming_number is not None:
                self.last_caller = self.incoming_number
            if self._on_incoming_call:
                LOGGER.info("Incoming call from %s", self.incoming_number or "unknown")
                self._on_incoming_call(self.incoming_number)

        if (
            self.call_state != prev_state or self.incoming_call != prev_incoming
        ) and self._on_state_change:
            self._on_state_change()

    # --- SMS (unchanged) ------------------------------------------------

    async def async_send_sms(
        self,
        targets: list[str],
        message: str,
        force_unicode: bool,  # noqa: FBT001 -- positional call site fixed by services.py/tests
    ) -> None:
        """Send an SMS to each target, retrying transient failures."""
        async with self._send_lock:
            for target in targets:
                await self._send_one(target, message, force_unicode=force_unicode)

    async def _send_one(
        self, target: str, message: str, *, force_unicode: bool
    ) -> None:
        last_err: ModemError | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                ref = await self._modem.send_sms(target, message, force_unicode)
            except NotRegistered:
                raise  # not transient — surface immediately
            except ModemError as err:
                last_err = err
                LOGGER.warning(
                    "SMS attempt %s/%s to %s failed: %s",
                    attempt,
                    _MAX_ATTEMPTS,
                    target,
                    err,
                )
                if attempt < _MAX_ATTEMPTS:
                    await asyncio.sleep(_RETRY_BACKOFF * attempt)
            else:
                LOGGER.info("SMS sent to %s (+CMGS ref %s)", target, ref)
                return
        if last_err is None:  # pragma: no cover - defensive, loop always sets it
            msg = "SMS send failed with no recorded error"
            raise RuntimeError(msg)
        raise last_err


def _outgoing_state(stat: int) -> str:
    """Map a CLCC <stat> for an outgoing call to a human call-state string."""
    if stat == CALL_STAT_ACTIVE:
        return CALL_STATE_ACTIVE
    if stat == CALL_STAT_ALERTING:
        return CALL_STATE_RINGING
    return CALL_STATE_DIALING
