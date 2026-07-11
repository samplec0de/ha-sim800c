"""Standalone SIM800C modem layer (no Home Assistant imports)."""

from .errors import ModemError, ModemTimeout, NotRegistered, SmsSendError
from .modem import (
    CALL_DIR_INCOMING,
    CALL_DIR_OUTGOING,
    CALL_STAT_ACTIVE,
    CALL_STAT_ALERTING,
    CALL_STAT_DIALING,
    CALL_STAT_HELD,
    CALL_STAT_INCOMING,
    CALL_STAT_WAITING,
    CallInfo,
    Modem,
    SmsMessage,
)
from .transport import Transport

__all__ = [
    "CALL_DIR_INCOMING",
    "CALL_DIR_OUTGOING",
    "CALL_STAT_ACTIVE",
    "CALL_STAT_ALERTING",
    "CALL_STAT_DIALING",
    "CALL_STAT_HELD",
    "CALL_STAT_INCOMING",
    "CALL_STAT_WAITING",
    "CallInfo",
    "Modem",
    "ModemError",
    "ModemTimeout",
    "NotRegistered",
    "SmsMessage",
    "SmsSendError",
    "Transport",
]
