"""Incoming-call binary sensor for SIM800C."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo

from .const import ATTR_CALLER, DOMAIN, SIGNAL_UPDATE

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .hub import ModemHub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SIM800C incoming-call binary sensor for a config entry."""
    hub: ModemHub = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([IncomingCallSensor(hub, entry.entry_id)])


class IncomingCallSensor(BinarySensorEntity):
    """On while an incoming call is ringing; caller number in attributes."""

    _attr_has_entity_name = True
    _attr_name = "Incoming call"
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    _attr_should_poll = False

    def __init__(self, hub: ModemHub, entry_id: str) -> None:
        """Bind the sensor to its owning modem hub and config entry."""
        self._hub = hub
        self._attr_unique_id = f"{entry_id}_incoming_call"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="SIM800C",
            manufacturer="SIMCom",
            model="SIM800C",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to modem call-state updates pushed by the hub."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE, self.async_write_ha_state
            )
        )

    @property
    def is_on(self) -> bool:
        """Return True while an incoming call is ringing."""
        return self._hub.incoming_call

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Expose the caller's number, when known."""
        return {ATTR_CALLER: self._hub.incoming_number}
