"""Tests for the sim800c.send_sms service."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_DEVICE
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sim800c.const import CONF_BAUD_RATE, DOMAIN


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
