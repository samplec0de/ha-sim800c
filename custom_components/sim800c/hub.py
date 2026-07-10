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

    from .modem import CallInfo

_MAX_ATTEMPTS = 3
_RETRY_BACKOFF = 2.0

# How often the background loop polls AT+CLCC to catch incoming calls.
_MONITOR_INTERVAL = 3.0
# Faster polling while we are actively driving an outgoing call.
_CALL_POLL_INTERVAL = 1.0
# Default seconds to let an outgoing call ring before auto-hanging-up.
DEFAULT_RING_DURATION = 30.0


@dataclass(frozen=True)
class CallResult:
    """Outcome of an outgoing call placed via async_call."""

    answered: bool
    """True if the other party picked up before we hung up."""
    final_state: str
    """One of 'answered', 'no_answer' (rang out), or 'ended' (remote hung up)."""


class ModemHub:
    """Serialize Home Assistant access to a single SIM800C modem."""

    def __init__(
        self,
        device: str,
        baud: int,
        on_state_change: Callable[[], None] | None = None,
        on_incoming_call: Callable[[str | None], None] | None = None,
    ) -> None:
        """Create a hub bound to the given serial device and baud rate."""
        self._transport = Transport(device, baud)
        self._modem = Modem(self._transport)
        self.signal_dbm: int | None = None
        self.registered: bool = False
        self.call_state: str = CALL_STATE_IDLE
        self.incoming_call: bool = False
        self.incoming_number: str | None = None
        self._send_lock = asyncio.Lock()
        self._call_lock = asyncio.Lock()
        self._state_lock = asyncio.Lock()
        self._monitor_task: asyncio.Task[None] | None = None
        self._on_state_change = on_state_change
        self._on_incoming_call = on_incoming_call

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
        while True:
            await asyncio.sleep(_MONITOR_INTERVAL)
            if self._call_lock.locked():
                # An outgoing call is driving state itself; don't double-poll.
                continue
            try:
                await self._refresh_call_state()
            except ModemError as err:
                LOGGER.debug("Call-state poll failed: %s", err)

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
        if self.incoming_call and not prev_incoming and self._on_incoming_call:
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
