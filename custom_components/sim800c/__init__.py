"""SIM800C integration for Home Assistant."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_DEVICE
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    ATTR_CALLER,
    ATTR_SENDER,
    ATTR_TEXT,
    ATTR_TIMESTAMP,
    CONF_BAUD_RATE,
    DEFAULT_BAUD_RATE,
    DOMAIN,
    EVENT_INCOMING_CALL,
    EVENT_INCOMING_SMS,
    LOGGER,
    PLATFORMS,
    SERVICE_ANSWER_AND_RECORD,
    SERVICE_CALL,
    SERVICE_CALL_AND_PLAY,
    SERVICE_HANG_UP,
    SERVICE_SEND_SMS,
    SIGNAL_UPDATE,
)
from .hub import ModemHub
from .modem import ModemError
from .services import async_register_services

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .modem import SmsMessage

__version__ = "0.8.0"

_SERVICES = (
    SERVICE_SEND_SMS,
    SERVICE_CALL,
    SERVICE_CALL_AND_PLAY,
    SERVICE_HANG_UP,
    SERVICE_ANSWER_AND_RECORD,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SIM800C from a config entry."""
    baud = entry.data.get(CONF_BAUD_RATE, DEFAULT_BAUD_RATE)

    def _on_state_change() -> None:
        async_dispatcher_send(hass, SIGNAL_UPDATE)

    def _on_incoming_call(caller: str | None) -> None:
        hass.bus.async_fire(EVENT_INCOMING_CALL, {ATTR_CALLER: caller})

    def _on_incoming_sms(message: SmsMessage) -> None:
        hass.bus.async_fire(
            EVENT_INCOMING_SMS,
            {
                ATTR_SENDER: message.sender,
                ATTR_TEXT: message.text,
                ATTR_TIMESTAMP: message.timestamp,
            },
        )

    hub = ModemHub(
        entry.data[CONF_DEVICE],
        baud,
        on_state_change=_on_state_change,
        on_incoming_call=_on_incoming_call,
        on_incoming_sms=_on_incoming_sms,
    )
    try:
        await hub.async_start()
        await hub.async_update_diagnostics()
    except (ModemError, OSError) as err:
        await hub.async_stop()
        raise ConfigEntryNotReady(str(err)) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub
    async_register_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    hub.start_monitoring()
    LOGGER.info("SIM800C ready on %s", entry.data[CONF_DEVICE])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a SIM800C config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hub: ModemHub = hass.data[DOMAIN].pop(entry.entry_id)
        await hub.async_stop()
        if not hass.data[DOMAIN]:
            for service in _SERVICES:
                hass.services.async_remove(DOMAIN, service)
    return unloaded
