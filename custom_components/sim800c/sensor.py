"""Diagnostic sensors for SIM800C."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, ClassVar

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, EntityCategory
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    ATTR_SENDER,
    ATTR_TEXT,
    ATTR_TIMESTAMP,
    CALL_STATE_ACTIVE,
    CALL_STATE_DIALING,
    CALL_STATE_IDLE,
    CALL_STATE_INCOMING,
    CALL_STATE_RINGING,
    DOMAIN,
    SIGNAL_UPDATE,
)

# HA state values are capped at 255 chars; keep the full body in an attribute.
_STATE_MAX = 255

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .hub import ModemHub

SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SIM800C diagnostic sensors for a config entry."""
    hub: ModemHub = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            SignalSensor(hub, entry.entry_id),
            NetworkSensor(hub, entry.entry_id),
            CallStateSensor(hub, entry.entry_id),
            LastSmsSensor(hub, entry.entry_id),
        ]
    )


class _BaseSensor(SensorEntity):
    """Shared behavior for SIM800C diagnostic sensors."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = True

    def __init__(self, hub: ModemHub, entry_id: str) -> None:
        """Bind the sensor to its owning modem hub and config entry."""
        self._hub = hub
        self._entry_id = entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="SIM800C",
            manufacturer="SIMCom",
            model="SIM800C",
        )

    async def async_update(self) -> None:
        """Refresh diagnostic state from the modem hub."""
        await self._hub.async_update_diagnostics()


class SignalSensor(_BaseSensor):
    """Signal strength diagnostic sensor, in dBm."""

    _attr_name = "Signal"
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hub: ModemHub, entry_id: str) -> None:
        """Bind the sensor to its owning modem hub and config entry."""
        super().__init__(hub, entry_id)
        self._attr_unique_id = f"{entry_id}_signal"

    @property
    def native_value(self) -> int | None:
        """Return the last known signal strength in dBm."""
        return self._hub.signal_dbm


class NetworkSensor(_BaseSensor):
    """Network registration diagnostic sensor."""

    _attr_name = "Network"

    def __init__(self, hub: ModemHub, entry_id: str) -> None:
        """Bind the sensor to its owning modem hub and config entry."""
        super().__init__(hub, entry_id)
        self._attr_unique_id = f"{entry_id}_network"

    @property
    def native_value(self) -> str:
        """Return the current registration state."""
        return "registered" if self._hub.registered else "searching"


class CallStateSensor(SensorEntity):
    """Current call state (idle/dialing/ringing/active/incoming), pushed live."""

    _attr_has_entity_name = True
    _attr_name = "Call state"
    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options: ClassVar[list[str]] = [
        CALL_STATE_IDLE,
        CALL_STATE_DIALING,
        CALL_STATE_RINGING,
        CALL_STATE_ACTIVE,
        CALL_STATE_INCOMING,
    ]

    def __init__(self, hub: ModemHub, entry_id: str) -> None:
        """Bind the sensor to its owning modem hub and config entry."""
        self._hub = hub
        self._attr_unique_id = f"{entry_id}_call_state"
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
    def native_value(self) -> str:
        """Return the current call state string."""
        return self._hub.call_state


class LastSmsSensor(SensorEntity):
    """Text of the most recently received SMS, with sender/time attributes."""

    _attr_has_entity_name = True
    _attr_name = "Last SMS"
    _attr_should_poll = False
    _attr_icon = "mdi:message-text"

    def __init__(self, hub: ModemHub, entry_id: str) -> None:
        """Bind the sensor to its owning modem hub and config entry."""
        self._hub = hub
        self._attr_unique_id = f"{entry_id}_last_sms"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="SIM800C",
            manufacturer="SIMCom",
            model="SIM800C",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates pushed by the hub when an SMS arrives."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE, self.async_write_ha_state
            )
        )

    @property
    def native_value(self) -> str | None:
        """Return the last SMS text (truncated to the HA state length limit)."""
        if self._hub.last_sms is None:
            return None
        return self._hub.last_sms.text[:_STATE_MAX]

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Expose the sender, full text, and timestamp of the last SMS."""
        sms = self._hub.last_sms
        if sms is None:
            return None
        return {
            ATTR_SENDER: sms.sender,
            ATTR_TEXT: sms.text,
            ATTR_TIMESTAMP: sms.timestamp,
        }
