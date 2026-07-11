"""Service registration for SIM800C."""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from . import stt
from .const import (
    ATTR_AUDIO_FILE,
    ATTR_CALLER,
    ATTR_DURATION,
    ATTR_FORCE_UNICODE,
    ATTR_MESSAGE,
    ATTR_PATH,
    ATTR_RECORD_SECONDS,
    ATTR_RING_DURATION,
    ATTR_TARGET,
    ATTR_TIMESTAMP,
    ATTR_TRANSCRIPT,
    ATTR_URL,
    ATTR_VOLUME,
    CONF_STT_URL,
    DOMAIN,
    EVENT_CALL_RECORDED,
    LOGGER,
    SERVICE_ANSWER_AND_RECORD,
    SERVICE_CALL,
    SERVICE_CALL_AND_PLAY,
    SERVICE_HANG_UP,
    SERVICE_SEND_SMS,
    SIGNAL_UPDATE,
)
from .modem import ModemError

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse

    from .hub import ModemHub

# Default STT service base URL. NOTE: on Home Assistant OS this must point at the
# STT host's LAN IP (e.g. http://192.168.1.10:9000/v1), NOT localhost — the HAOS
# container's 127.0.0.1 is the HA container itself, not the STT service host.
DEFAULT_STT_URL = "http://127.0.0.1:9000/v1"
# Default seconds to record a caller before hanging up.
DEFAULT_RECORD_SECONDS = 15

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

ANSWER_AND_RECORD_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_RECORD_SECONDS, default=DEFAULT_RECORD_SECONDS): vol.All(
            vol.Coerce(float), vol.Range(min=1, max=60)
        ),
        vol.Optional(CONF_STT_URL): cv.string,
    }
)


def _save_recording(hass: HomeAssistant, data: bytes) -> tuple[str, str]:
    """Write `data` under <config>/media/sim800c and return (fs_path, media_url)."""
    media_dir = Path(hass.config.path("media", "sim800c"))
    media_dir.mkdir(parents=True, exist_ok=True)
    filename = f"rec_{int(time.time())}.amr"
    file_path = media_dir / filename
    file_path.write_bytes(data)
    # /media/local/... is how HA's media source surfaces <config>/media/*.
    return str(file_path), f"/media/local/sim800c/{filename}"


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


def async_register_services(hass: HomeAssistant) -> None:  # noqa: PLR0915 — one closure handler per service, registered together
    """Register the sim800c send_sms/call/call_and_play/hang_up/record services."""

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

    async def _handle_answer_and_record(call: ServiceCall) -> ServiceResponse:
        hub = _first_hub(hass)
        record_seconds = call.data[ATTR_RECORD_SECONDS]
        try:
            data = await hub.async_answer_and_record(record_seconds)
        except ModemError as err:
            msg = f"Answer-and-record failed: {err}"
            raise HomeAssistantError(msg) from err
        if data is None:
            return {"recorded": False, "transcript": None, "path": None}

        fs_path, media_url = await hass.async_add_executor_job(
            _save_recording, hass, data
        )

        # Transcribe via a Whisper-compatible STT service; a failure must not
        # lose the recording — we still return it with transcript = None.
        stt_url = call.data.get(CONF_STT_URL) or DEFAULT_STT_URL
        transcript: str | None = None
        try:
            transcript = await stt.transcribe(
                async_get_clientsession(hass), stt_url, data
            )
        except stt.SttError as err:
            LOGGER.warning("STT transcription failed: %s", err)

        recording: dict[str, object] = {
            ATTR_CALLER: hub.last_caller,
            ATTR_PATH: fs_path,
            ATTR_URL: media_url,
            ATTR_TRANSCRIPT: transcript,
            ATTR_TIMESTAMP: dt_util.utcnow().isoformat(),
        }
        hub.last_recording = recording
        hass.bus.async_fire(EVENT_CALL_RECORDED, recording)
        async_dispatcher_send(hass, SIGNAL_UPDATE)
        return {"recorded": True, "transcript": transcript, "path": fs_path}

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
    if not hass.services.has_service(DOMAIN, SERVICE_ANSWER_AND_RECORD):
        hass.services.async_register(
            DOMAIN,
            SERVICE_ANSWER_AND_RECORD,
            _handle_answer_and_record,
            schema=ANSWER_AND_RECORD_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )
