from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE

from custom_components.sim800c.const import CONF_BAUD_RATE, DOMAIN


async def test_user_flow_creates_entry(hass):
    with patch(
        "custom_components.sim800c.config_flow.ModemHub"
    ) as hub_cls:
        hub = hub_cls.return_value
        hub.async_start = AsyncMock()
        hub.async_update_diagnostics = AsyncMock()
        hub.registered = True
        hub.async_stop = AsyncMock()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: "/dev/ttyUSB0", CONF_BAUD_RATE: 9600},
        )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_DEVICE] == "/dev/ttyUSB0"


async def test_user_flow_errors_when_not_registered(hass):
    with patch(
        "custom_components.sim800c.config_flow.ModemHub"
    ) as hub_cls:
        hub = hub_cls.return_value
        hub.async_start = AsyncMock()
        hub.async_update_diagnostics = AsyncMock()
        hub.registered = False
        hub.async_stop = AsyncMock()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: "/dev/ttyUSB0", CONF_BAUD_RATE: 9600},
        )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "not_registered"
