"""Home Assistant-facing wrapper around the modem layer."""

from __future__ import annotations

import asyncio

from .const import LOGGER
from .modem import Modem, ModemError, NotRegistered, Transport

_MAX_ATTEMPTS = 3
_RETRY_BACKOFF = 2.0


class ModemHub:
    """Serialize Home Assistant access to a single SIM800C modem."""

    def __init__(self, device: str, baud: int) -> None:
        """Create a hub bound to the given serial device and baud rate."""
        self._transport = Transport(device, baud)
        self._modem = Modem(self._transport)
        self.signal_dbm: int | None = None
        self.registered: bool = False
        self._send_lock = asyncio.Lock()

    async def async_start(self) -> None:
        """Open the serial connection and initialize the modem."""
        await self._transport.connect()
        await self._modem.initialize()

    async def async_stop(self) -> None:
        """Close the serial connection."""
        await self._transport.close()

    async def async_update_diagnostics(self) -> None:
        """Refresh cached registration and signal-strength state."""
        self.registered = await self._modem.get_registration()
        self.signal_dbm = await self._modem.get_signal()

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
