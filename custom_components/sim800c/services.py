"""Service registration for SIM800C."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_FORCE_UNICODE,
    ATTR_MESSAGE,
    ATTR_TARGET,
    DOMAIN,
    SERVICE_SEND_SMS,
)
from .modem import ModemError

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

    from .hub import ModemHub

SEND_SMS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TARGET): vol.All(cv.ensure_list, [cv.string]),
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_FORCE_UNICODE, default=False): cv.boolean,
    }
)


def async_register_services(hass: HomeAssistant) -> None:
    """Register the sim800c.send_sms service."""

    async def _handle_send_sms(call: ServiceCall) -> None:
        hubs: list[ModemHub] = list(hass.data[DOMAIN].values())
        if not hubs:
            msg = "No SIM800C modem configured"
            raise HomeAssistantError(msg)
        hub = hubs[0]
        try:
            await hub.async_send_sms(
                call.data[ATTR_TARGET],
                call.data[ATTR_MESSAGE],
                call.data[ATTR_FORCE_UNICODE],
            )
        except ModemError as err:
            msg = f"SMS send failed: {err}"
            raise HomeAssistantError(msg) from err

    if not hass.services.has_service(DOMAIN, SERVICE_SEND_SMS):
        hass.services.async_register(
            DOMAIN, SERVICE_SEND_SMS, _handle_send_sms, schema=SEND_SMS_SCHEMA
        )
