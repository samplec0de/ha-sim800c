"""Diagnostic sensors for SIM800C."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .hub import ModemHub

SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub: ModemHub = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [SignalSensor(hub, entry.entry_id), NetworkSensor(hub, entry.entry_id)]
    )


class _BaseSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = True

    def __init__(self, hub: ModemHub, entry_id: str) -> None:
        self._hub = hub
        self._entry_id = entry_id

    async def async_update(self) -> None:
        await self._hub.async_update_diagnostics()


class SignalSensor(_BaseSensor):
    _attr_name = "Signal"
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hub: ModemHub, entry_id: str) -> None:
        super().__init__(hub, entry_id)
        self._attr_unique_id = f"{entry_id}_signal"

    @property
    def native_value(self) -> int | None:
        return self._hub.signal_dbm


class NetworkSensor(_BaseSensor):
    _attr_name = "Network"

    def __init__(self, hub: ModemHub, entry_id: str) -> None:
        super().__init__(hub, entry_id)
        self._attr_unique_id = f"{entry_id}_network"

    @property
    def native_value(self) -> str:
        return "registered" if self._hub.registered else "searching"
