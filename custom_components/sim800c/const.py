"""Constants for sim800c."""

from logging import Logger, getLogger

from homeassistant.const import Platform

LOGGER: Logger = getLogger(__package__)

DOMAIN = "sim800c"

CONF_BAUD_RATE = "baud_rate"
DEFAULT_BAUD_RATE = 9600

# Services
SERVICE_SEND_SMS = "send_sms"
SERVICE_CALL = "call"
SERVICE_HANG_UP = "hang_up"

# Service fields
ATTR_TARGET = "target"
ATTR_MESSAGE = "message"
ATTR_FORCE_UNICODE = "force_unicode"
ATTR_RING_DURATION = "ring_duration"

# Call-state strings (exposed via sensor.sim800c_call_state)
CALL_STATE_IDLE = "idle"
CALL_STATE_DIALING = "dialing"
CALL_STATE_RINGING = "ringing"
CALL_STATE_ACTIVE = "active"
CALL_STATE_INCOMING = "incoming"

# Event fired on an incoming call
EVENT_INCOMING_CALL = f"{DOMAIN}_incoming_call"
ATTR_CALLER = "caller"

# Dispatcher signal used to push modem state to entities
SIGNAL_CALL_UPDATE = f"{DOMAIN}_call_update"

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]
