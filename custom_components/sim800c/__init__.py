"""SIM800C integration for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant

from .const import CONF_BAUD_RATE, DEFAULT_BAUD_RATE, DOMAIN, LOGGER, PLATFORMS
from .hub import ModemHub
from .services import async_register_services

__version__ = "0.2.0"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hub = ModemHub(entry.data[CONF_DEVICE], entry.data.get(CONF_BAUD_RATE, DEFAULT_BAUD_RATE))
    await hub.async_start()
    await hub.async_update_diagnostics()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub
    async_register_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    LOGGER.info("SIM800C ready on %s", entry.data[CONF_DEVICE])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hub: ModemHub = hass.data[DOMAIN].pop(entry.entry_id)
        await hub.async_stop()
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "send_sms")
    return unloaded
