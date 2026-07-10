"""Home Assistant-facing wrapper around the modem layer."""

from __future__ import annotations

import asyncio

from .const import LOGGER
from .modem import Modem, ModemError, NotRegistered, Transport

_MAX_ATTEMPTS = 3
_RETRY_BACKOFF = 2.0


class ModemHub:
    def __init__(self, device: str, baud: int) -> None:
        self._transport = Transport(device, baud)
        self._modem = Modem(self._transport)
        self.signal_dbm: int | None = None
        self.registered: bool = False

    async def async_start(self) -> None:
        await self._transport.connect()
        await self._modem.initialize()

    async def async_stop(self) -> None:
        await self._transport.close()

    async def async_update_diagnostics(self) -> None:
        self.registered = await self._modem.get_registration()
        self.signal_dbm = await self._modem.get_signal()

    async def async_send_sms(
        self, targets: list[str], message: str, force_unicode: bool
    ) -> None:
        for target in targets:
            await self._send_one(target, message, force_unicode)

    async def _send_one(
        self, target: str, message: str, force_unicode: bool
    ) -> None:
        last_err: ModemError | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                ref = await self._modem.send_sms(target, message, force_unicode)
                LOGGER.info("SMS sent to %s (+CMGS ref %s)", target, ref)
                return
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
        assert last_err is not None
        raise last_err
