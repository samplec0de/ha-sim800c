"""Typed modem errors."""


class ModemError(Exception):
    """Base error for the modem layer."""


class ModemTimeout(ModemError):
    """No expected token arrived before the timeout."""


class NotRegistered(ModemError):
    """The modem is not registered on the network."""


class SmsSendError(ModemError):
    """The modem reported a failure sending an SMS."""
