"""Constants for sim800c."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "sim800c"

# Configuration constants
CONF_BAUD_RATE = "baud_rate"
DEFAULT_BAUD_RATE = 9600
