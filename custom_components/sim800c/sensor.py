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
    ATTR_CALLER,
    ATTR_PATH,
    ATTR_SENDER,
    ATTR_TEXT,
    ATTR_TIMESTAMP,
    ATTR_TRANSCRIPT,
    ATTR_URL,
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
            LastSmsSenderSensor(hub, entry.entry_id),
            LastCallerSensor(hub, entry.entry_id),
            LastRecordingSensor(hub, entry.entry_id),
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


class LastCallerSensor(SensorEntity):
    """Number of the most recent incoming caller, persisted across calls."""

    _attr_has_entity_name = True
    _attr_name = "Last caller"
    _attr_should_poll = False
    _attr_icon = "mdi:phone-incoming"

    def __init__(self, hub: ModemHub, entry_id: str) -> None:
        """Bind the sensor to its owning modem hub and config entry."""
        self._hub = hub
        self._attr_unique_id = f"{entry_id}_last_caller"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="SIM800C",
            manufacturer="SIMCom",
            model="SIM800C",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates pushed by the hub when a call arrives."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE, self.async_write_ha_state
            )
        )

    @property
    def native_value(self) -> str | None:
        """Return the number of the last person who called."""
        return self._hub.last_caller


class LastSmsSenderSensor(SensorEntity):
    """Number of the most recent SMS sender, persisted across messages."""

    _attr_has_entity_name = True
    _attr_name = "Last SMS sender"
    _attr_should_poll = False
    _attr_icon = "mdi:message-arrow-left"

    def __init__(self, hub: ModemHub, entry_id: str) -> None:
        """Bind the sensor to its owning modem hub and config entry."""
        self._hub = hub
        self._attr_unique_id = f"{entry_id}_last_sms_sender"
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
        """Return the number of the last person who sent an SMS."""
        return self._hub.last_sms.sender if self._hub.last_sms else None


class LastRecordingSensor(SensorEntity):
    """Transcript of the most recent recorded call, with recording attributes."""

    _attr_has_entity_name = True
    _attr_name = "Last recording"
    _attr_should_poll = False
    _attr_icon = "mdi:microphone-message"

    def __init__(self, hub: ModemHub, entry_id: str) -> None:
        """Bind the sensor to its owning modem hub and config entry."""
        self._hub = hub
        self._attr_unique_id = f"{entry_id}_last_recording"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="SIM800C",
            manufacturer="SIMCom",
            model="SIM800C",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates pushed by the hub when a call is recorded."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE, self.async_write_ha_state
            )
        )

    @property
    def native_value(self) -> str | None:
        """Return the last recording's transcript (truncated to the state limit)."""
        recording = self._hub.last_recording
        if recording is None:
            return None
        transcript = recording.get(ATTR_TRANSCRIPT)
        if not isinstance(transcript, str):
            return None
        return transcript[:_STATE_MAX]

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        """Expose the caller, file path/url, full transcript, and timestamp."""
        recording = self._hub.last_recording
        if recording is None:
            return None
        return {
            ATTR_CALLER: recording.get(ATTR_CALLER),
            ATTR_PATH: recording.get(ATTR_PATH),
            ATTR_URL: recording.get(ATTR_URL),
            ATTR_TRANSCRIPT: recording.get(ATTR_TRANSCRIPT),
            ATTR_TIMESTAMP: recording.get(ATTR_TIMESTAMP),
        }
