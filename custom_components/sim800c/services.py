"""Service registration for SIM800C."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_AUDIO_FILE,
    ATTR_DURATION,
    ATTR_FORCE_UNICODE,
    ATTR_MESSAGE,
    ATTR_RING_DURATION,
    ATTR_TARGET,
    ATTR_VOLUME,
    DOMAIN,
    SERVICE_CALL,
    SERVICE_CALL_AND_PLAY,
    SERVICE_HANG_UP,
    SERVICE_SEND_SMS,
)
from .modem import ModemError

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse

    from .hub import ModemHub

SEND_SMS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TARGET): vol.All(cv.ensure_list, [cv.string]),
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_FORCE_UNICODE, default=False): cv.boolean,
    }
)

CALL_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TARGET): cv.string,
        vol.Optional(ATTR_RING_DURATION): vol.All(
            vol.Coerce(float), vol.Range(min=1, max=120)
        ),
    }
)

CALL_AND_PLAY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TARGET): cv.string,
        vol.Required(ATTR_AUDIO_FILE): cv.string,
        vol.Optional(ATTR_DURATION): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional(ATTR_RING_DURATION): vol.All(
            vol.Coerce(float), vol.Range(min=1, max=120)
        ),
        vol.Optional(ATTR_VOLUME, default=90): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100)
        ),
    }
)

HANG_UP_SCHEMA = vol.Schema({})


def _read_audio_file(hass: HomeAssistant, path: str) -> bytes:
    """Validate `path` is allowed and readable, and return its bytes."""
    if not hass.config.is_allowed_path(path):
        msg = f"Audio file path is not allowed: {path}"
        raise HomeAssistantError(msg)
    try:
        return Path(path).read_bytes()
    except OSError as err:
        msg = f"Could not read audio file {path}: {err}"
        raise HomeAssistantError(msg) from err


def _first_hub(hass: HomeAssistant) -> ModemHub:
    hubs: list[ModemHub] = list(hass.data[DOMAIN].values())
    if not hubs:
        msg = "No SIM800C modem configured"
        raise HomeAssistantError(msg)
    return hubs[0]


def async_register_services(hass: HomeAssistant) -> None:
    """Register the sim800c.send_sms/call/call_and_play/hang_up services."""

    async def _handle_send_sms(call: ServiceCall) -> None:
        hub = _first_hub(hass)
        try:
            await hub.async_send_sms(
                call.data[ATTR_TARGET],
                call.data[ATTR_MESSAGE],
                call.data[ATTR_FORCE_UNICODE],
            )
        except ModemError as err:
            msg = f"SMS send failed: {err}"
            raise HomeAssistantError(msg) from err

    async def _handle_call(call: ServiceCall) -> ServiceResponse:
        hub = _first_hub(hass)
        kwargs = {}
        if ATTR_RING_DURATION in call.data:
            kwargs["ring_duration"] = call.data[ATTR_RING_DURATION]
        try:
            result = await hub.async_call(call.data[ATTR_TARGET], **kwargs)
        except ModemError as err:
            msg = f"Call failed: {err}"
            raise HomeAssistantError(msg) from err
        return {"answered": result.answered, "state": result.final_state}

    async def _handle_call_and_play(call: ServiceCall) -> ServiceResponse:
        hub = _first_hub(hass)
        path = call.data[ATTR_AUDIO_FILE]
        audio = await hass.async_add_executor_job(_read_audio_file, hass, path)
        kwargs: dict[str, object] = {}
        if ATTR_DURATION in call.data:
            kwargs["duration"] = call.data[ATTR_DURATION]
        if ATTR_RING_DURATION in call.data:
            kwargs["ring_duration"] = call.data[ATTR_RING_DURATION]
        kwargs["volume"] = call.data[ATTR_VOLUME]
        try:
            result = await hub.async_call_and_play(
                call.data[ATTR_TARGET], audio, **kwargs
            )
        except ModemError as err:
            msg = f"Call-and-play failed: {err}"
            raise HomeAssistantError(msg) from err
        return {"answered": result.answered, "played": result.played}

    async def _handle_hang_up(_call: ServiceCall) -> None:
        hub = _first_hub(hass)
        try:
            await hub.async_hang_up()
        except ModemError as err:
            msg = f"Hang up failed: {err}"
            raise HomeAssistantError(msg) from err

    if not hass.services.has_service(DOMAIN, SERVICE_SEND_SMS):
        hass.services.async_register(
            DOMAIN, SERVICE_SEND_SMS, _handle_send_sms, schema=SEND_SMS_SCHEMA
        )
    if not hass.services.has_service(DOMAIN, SERVICE_CALL):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CALL,
            _handle_call,
            schema=CALL_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_CALL_AND_PLAY):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CALL_AND_PLAY,
            _handle_call_and_play,
            schema=CALL_AND_PLAY_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_HANG_UP):
        hass.services.async_register(
            DOMAIN, SERVICE_HANG_UP, _handle_hang_up, schema=HANG_UP_SCHEMA
        )
