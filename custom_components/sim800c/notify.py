"""Support for sending SMS messages via SIM800C module."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import homeassistant.helpers.config_validation as cv
import serial
import voluptuous as vol
from homeassistant.components.notify import (
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
)
from homeassistant.components.notify import (
    BaseNotificationService,
)
from homeassistant.const import CONF_DEVICE

from .const import CONF_BAUD_RATE, DEFAULT_BAUD_RATE, LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DEVICE): cv.string,
        vol.Optional(CONF_BAUD_RATE, default=DEFAULT_BAUD_RATE): cv.positive_int,
    }
)


def get_service(
    hass: HomeAssistant,  # noqa: ARG001
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,  # noqa: ARG001
) -> SIM800CSMSNotificationService | None:
    """Get the SIM800C SMS notification service."""
    device = config[CONF_DEVICE]
    baud_rate = config[CONF_BAUD_RATE]

    LOGGER.info("Setting up SIM800C SMS notification service on %s", device)

    return SIM800CSMSNotificationService(device, baud_rate)


class SIM800CSMSNotificationService(BaseNotificationService):
    """Implement the notification service for SIM800C SMS."""

    def __init__(self, device: str, baud_rate: int) -> None:
        """Initialize the service."""
        self.device = device
        self.baud_rate = baud_rate

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send an SMS message to a specified target."""
        targets = kwargs.get("target")

        if not targets:
            LOGGER.error("No target phone number specified")
            return

        if isinstance(targets, str):
            targets = [targets]

        if not message:
            LOGGER.error("Message is empty")
            return

        for target in targets:
            try:
                await self._send_sms(target, message)
                LOGGER.info("SMS sent successfully to %s", target)
            except (serial.SerialException, OSError, RuntimeError) as ex:
                LOGGER.error("Failed to send SMS to %s: %s", target, ex)

    async def _send_sms(self, phone_number: str, message: str) -> None:
        """Send SMS via SIM800C module."""
        await asyncio.to_thread(self._send_sms_sync, phone_number, message)

    def _send_sms_sync(self, phone_number: str, message: str) -> None:
        """Send SMS synchronously (runs in executor)."""
        try:
            with serial.Serial(self.device, self.baud_rate, timeout=0.5) as ser:
                # Wait for module to be ready
                asyncio.run(asyncio.sleep(2))
                ser.flush()

                # Configure module
                self._write_command(ser, "ATZ")
                self._write_command(ser, 'AT+CSCS="UCS2"')
                self._write_command(ser, "AT+CSMP=17,168,0,8")
                self._write_command(ser, "AT+CMGF=1")

                # Send SMS
                phone_ucs2 = self._convert_to_ucs2(phone_number)
                self._write_command(ser, f'AT+CMGS="{phone_ucs2}"')

                message_ucs2 = self._convert_to_ucs2(message)
                ser.write(f"{message_ucs2}\r\n".encode())
                ser.write(b"\x1a")  # Ctrl+Z
                asyncio.run(asyncio.sleep(2))

                # Read final response
                response = self._read_response(ser)

                if "OK" not in response and "+CMGS" not in response:
                    msg = f"SMS sending failed: {response}"
                    raise RuntimeError(msg)

        except serial.SerialException as ex:
            LOGGER.error("Could not open serial port %s: %s", self.device, ex)
            raise
        except OSError as ex:
            LOGGER.error("System error: %s", ex)
            raise

    def _write_command(self, ser: serial.Serial, command: str) -> None:
        """Send command to serial port."""
        LOGGER.debug("Sending: %s", command)
        ser.write(f"{command}\r\n".encode())
        asyncio.run(asyncio.sleep(0.3))

        response = self._read_response(ser)
        LOGGER.debug("Response: %s", response)

    def _read_response(self, ser: serial.Serial) -> str:
        """Read response from serial port."""
        response = b""
        retries = 0
        max_retries = 10

        while retries < max_retries:
            try:
                if ser.in_waiting > 0:
                    response += ser.read(ser.in_waiting)
                    asyncio.run(asyncio.sleep(0.1))
                else:
                    asyncio.run(asyncio.sleep(0.1))
                    if ser.in_waiting == 0:
                        break
                retries += 1
            except OSError:
                break

        return response.decode("utf-8", errors="ignore").strip()

    @staticmethod
    def _convert_to_ucs2(text: str) -> str:
        """Convert string to UCS2 hexadecimal representation."""
        return "".join(f"{ord(char):04x}" for char in text)