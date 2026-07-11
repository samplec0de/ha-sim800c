"""Tests for the Whisper-compatible STT client."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Self

import aiohttp
import pytest

from custom_components.sim800c import stt

if TYPE_CHECKING:
    from collections.abc import Iterator


class _FakeResponse:
    """Minimal async-context stand-in for aiohttp's response."""

    def __init__(self, status: int, payload: object = None, text: str = "") -> None:
        self.status = status
        self._payload = payload
        self._text = text

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return

    async def json(self) -> object:
        return self._payload

    async def text(self) -> str:
        return self._text


class _FakeSession:
    """Fake ClientSession recording the POST and returning a canned response."""

    def __init__(self, response: _FakeResponse | Exception) -> None:
        self._response = response
        self.url: str | None = None
        self.data: aiohttp.FormData | None = None

    def post(self, url: str, *, data: aiohttp.FormData) -> _FakeResponse:
        self.url = url
        self.data = data
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def _fields(data: aiohttp.FormData) -> Iterator[tuple[dict, dict, object]]:
    # aiohttp stores appended fields as (type_options, headers, value) tuples.
    return iter(data._fields)


async def test_transcribe_returns_text_and_builds_multipart():
    session = _FakeSession(_FakeResponse(HTTPStatus.OK, {"text": "привет мир"}))
    result = await stt.transcribe(session, "http://stt.local:9000/v1", b"AMRDATA")
    assert result == "привет мир"
    # Endpoint is base_url + /audio/transcriptions (no double slash).
    assert session.url == "http://stt.local:9000/v1/audio/transcriptions"
    names = [opts.get("name") for opts, _headers, _value in _fields(session.data)]
    assert "file" in names
    assert "model" in names


async def test_transcribe_trims_trailing_slash_on_base_url():
    session = _FakeSession(_FakeResponse(HTTPStatus.OK, {"text": "ok"}))
    await stt.transcribe(session, "http://stt.local:9000/v1/", b"DATA")
    assert session.url == "http://stt.local:9000/v1/audio/transcriptions"


async def test_transcribe_raises_on_non_200():
    session = _FakeSession(_FakeResponse(HTTPStatus.INTERNAL_SERVER_ERROR, text="boom"))
    with pytest.raises(stt.SttError):
        await stt.transcribe(session, "http://stt.local:9000/v1", b"DATA")


async def test_transcribe_raises_when_text_missing():
    session = _FakeSession(_FakeResponse(HTTPStatus.OK, {"unexpected": 1}))
    with pytest.raises(stt.SttError):
        await stt.transcribe(session, "http://stt.local:9000/v1", b"DATA")


async def test_transcribe_wraps_client_error():
    session = _FakeSession(aiohttp.ClientError("connection refused"))
    with pytest.raises(stt.SttError):
        await stt.transcribe(session, "http://stt.local:9000/v1", b"DATA")
