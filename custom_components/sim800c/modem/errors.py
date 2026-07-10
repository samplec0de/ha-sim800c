"""Typed modem errors."""


class ModemError(Exception):
    """Base error for the modem layer."""


class ModemTimeout(ModemError):  # noqa: N818 — public API name, not renaming
    """No expected token arrived before the timeout."""


class NotRegistered(ModemError):  # noqa: N818 — public API name, not renaming
    """The modem is not registered on the network."""


class SmsSendError(ModemError):
    """The modem reported a failure sending an SMS."""
