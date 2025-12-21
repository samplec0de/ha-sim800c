"""
Custom integration for SIM800C module with Home Assistant.

Supports SMS notifications.

For more details about this integration, please refer to
https://github.com/samplec0de/ha-sim800c
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .const import LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

__version__ = "0.1.0"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:  # noqa: ARG001
    """Set up the SIM800C component."""
    LOGGER.info("SIM800C integration loaded")
    return True
