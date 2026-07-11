"""
Whisper-compatible STT client (GigaAM) for transcribing call recordings.

This lives in the HA integration layer (not under modem/), so importing aiohttp
and using Home Assistant's shared client session here is fine.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    from aiohttp import ClientSession

# OpenAI/Whisper-compatible transcription endpoint and model.
_TRANSCRIBE_PATH = "/audio/transcriptions"
_STT_MODEL = "whisper-1"
# The recording is AMR-NB; GigaAM ffmpeg-decodes it, so the raw .amr is fine.
_AUDIO_CONTENT_TYPE = "audio/amr"


class SttError(Exception):
    """The STT service failed to transcribe the recording."""


async def transcribe(
    session: ClientSession,
    base_url: str,
    audio: bytes,
    filename: str = "rec.amr",
) -> str:
    """
    Transcribe `audio` via a Whisper-compatible STT service and return its text.

    POSTs a multipart request (fields `file` and `model`) to
    `{base_url}/audio/transcriptions` and parses the `{"text": ...}` response.
    Raises SttError on a non-200 response, a transport error, or a missing text.
    """
    url = f"{base_url.rstrip('/')}{_TRANSCRIBE_PATH}"
    form = aiohttp.FormData()
    form.add_field("file", audio, filename=filename, content_type=_AUDIO_CONTENT_TYPE)
    form.add_field("model", _STT_MODEL)

    try:
        async with session.post(url, data=form) as resp:
            if resp.status != HTTPStatus.OK:
                body = await resp.text()
                msg = f"STT {url} returned HTTP {resp.status}: {body[:200]!r}"
                raise SttError(msg)
            payload = await resp.json()
    except aiohttp.ClientError as err:
        msg = f"STT request to {url} failed: {err}"
        raise SttError(msg) from err

    text = payload.get("text") if isinstance(payload, dict) else None
    if not isinstance(text, str):
        msg = f"STT response has no 'text' field: {payload!r}"
        raise SttError(msg)
    return text
