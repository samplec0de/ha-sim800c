"""Tests for the sim800c.send_sms service."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_DEVICE
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sim800c.const import CONF_BAUD_RATE, DOMAIN
from custom_components.sim800c.hub import CallResult
from custom_components.sim800c.modem import ModemError


async def test_send_sms_service_calls_hub(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/ttyUSB0", CONF_BAUD_RATE: 9600},
        unique_id="/dev/ttyUSB0",
    )
    entry.add_to_hass(hass)

    with patch("custom_components.sim800c.ModemHub") as hub_cls:
        hub = hub_cls.return_value
        hub.async_start = AsyncMock()
        hub.async_stop = AsyncMock()
        hub.async_update_diagnostics = AsyncMock()
        hub.async_send_sms = AsyncMock()

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            DOMAIN,
            "send_sms",
            {"target": "+79990001122", "message": "Hello"},
            blocking=True,
        )

    hub.async_send_sms.assert_awaited_once_with(
        ["+79990001122"],
        "Hello",
        False,  # noqa: FBT003 — asserts the positional force_unicode arg of the real send_sms signature
    )


async def test_send_sms_service_wraps_modem_error(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/ttyUSB0", CONF_BAUD_RATE: 9600},
        unique_id="/dev/ttyUSB0",
    )
    entry.add_to_hass(hass)

    with patch("custom_components.sim800c.ModemHub") as hub_cls:
        hub = hub_cls.return_value
        hub.async_start = AsyncMock()
        hub.async_stop = AsyncMock()
        hub.async_update_diagnostics = AsyncMock()
        hub.async_send_sms = AsyncMock(side_effect=ModemError("boom"))

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                "send_sms",
                {"target": "+79990001122", "message": "Hello"},
                blocking=True,
            )


async def test_unload_entry_stops_hub_and_removes_service(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/ttyUSB0", CONF_BAUD_RATE: 9600},
        unique_id="/dev/ttyUSB0",
    )
    entry.add_to_hass(hass)

    with patch("custom_components.sim800c.ModemHub") as hub_cls:
        hub = hub_cls.return_value
        hub.async_start = AsyncMock()
        hub.async_stop = AsyncMock()
        hub.async_update_diagnostics = AsyncMock()
        hub.async_send_sms = AsyncMock()

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert hass.services.has_service(DOMAIN, "send_sms")
        assert hass.services.has_service(DOMAIN, "call")
        assert hass.services.has_service(DOMAIN, "hang_up")

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        hub.async_stop.assert_awaited_once()
        assert not hass.services.has_service(DOMAIN, "send_sms")
        assert not hass.services.has_service(DOMAIN, "call")
        assert not hass.services.has_service(DOMAIN, "hang_up")


async def _setup_with_mock_hub(hass) -> tuple:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/ttyUSB0", CONF_BAUD_RATE: 9600},
        unique_id="/dev/ttyUSB0",
    )
    entry.add_to_hass(hass)
    patcher = patch("custom_components.sim800c.ModemHub")
    hub_cls = patcher.start()
    hub = hub_cls.return_value
    hub.async_start = AsyncMock()
    hub.async_stop = AsyncMock()
    hub.async_update_diagnostics = AsyncMock()
    hub.async_send_sms = AsyncMock()
    hub.async_hang_up = AsyncMock()
    hub.async_call = AsyncMock(
        return_value=CallResult(answered=True, final_state="answered")
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return hub, patcher


async def test_call_service_returns_answered(hass):
    hub, patcher = await _setup_with_mock_hub(hass)
    try:
        response = await hass.services.async_call(
            DOMAIN,
            "call",
            {"target": "+79990001122", "ring_duration": 15},
            blocking=True,
            return_response=True,
        )
    finally:
        patcher.stop()

    hub.async_call.assert_awaited_once_with("+79990001122", ring_duration=15.0)
    assert response == {"answered": True, "state": "answered"}


async def test_call_service_uses_default_duration(hass):
    hub, patcher = await _setup_with_mock_hub(hass)
    try:
        await hass.services.async_call(
            DOMAIN, "call", {"target": "+79990001122"}, blocking=True
        )
    finally:
        patcher.stop()

    # No ring_duration passed → hub applies its own default.
    hub.async_call.assert_awaited_once_with("+79990001122")


async def test_hang_up_service_calls_hub(hass):
    hub, patcher = await _setup_with_mock_hub(hass)
    try:
        await hass.services.async_call(DOMAIN, "hang_up", {}, blocking=True)
    finally:
        patcher.stop()

    hub.async_hang_up.assert_awaited_once()


async def test_call_service_wraps_modem_error(hass):
    hub, patcher = await _setup_with_mock_hub(hass)
    hub.async_call = AsyncMock(side_effect=ModemError("boom"))
    try:
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN, "call", {"target": "+79990001122"}, blocking=True
            )
    finally:
        patcher.stop()
