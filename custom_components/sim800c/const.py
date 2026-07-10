"""Constants for sim800c."""

from logging import Logger, getLogger

from homeassistant.const import Platform

LOGGER: Logger = getLogger(__package__)

DOMAIN = "sim800c"

CONF_BAUD_RATE = "baud_rate"
DEFAULT_BAUD_RATE = 9600

SERVICE_SEND_SMS = "send_sms"
ATTR_TARGET = "target"
ATTR_MESSAGE = "message"
ATTR_FORCE_UNICODE = "force_unicode"

PLATFORMS = [Platform.SENSOR]
