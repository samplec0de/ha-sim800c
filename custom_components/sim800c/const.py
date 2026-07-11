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
SERVICE_CALL_AND_PLAY = "call_and_play"
SERVICE_HANG_UP = "hang_up"

# Service fields
ATTR_TARGET = "target"
ATTR_MESSAGE = "message"
ATTR_FORCE_UNICODE = "force_unicode"
ATTR_RING_DURATION = "ring_duration"
ATTR_AUDIO_FILE = "audio_file"
ATTR_DURATION = "duration"
ATTR_VOLUME = "volume"

# Call-state strings (exposed via sensor.sim800c_call_state)
CALL_STATE_IDLE = "idle"
CALL_STATE_DIALING = "dialing"
CALL_STATE_RINGING = "ringing"
CALL_STATE_ACTIVE = "active"
CALL_STATE_INCOMING = "incoming"

# Events
EVENT_INCOMING_CALL = f"{DOMAIN}_incoming_call"
EVENT_INCOMING_SMS = f"{DOMAIN}_incoming_sms"
ATTR_CALLER = "caller"
ATTR_SENDER = "sender"
ATTR_TEXT = "text"
ATTR_TIMESTAMP = "timestamp"

# Dispatcher signal used to push modem state to entities
SIGNAL_UPDATE = f"{DOMAIN}_update"

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]
