"""Support for sending SMS messages via SIM800C module."""

from __future__ import annotations

import asyncio
import time
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
        # Ensure phone number starts with + (required for international format)
        if not phone_number.startswith("+"):
            phone_number = f"+{phone_number}"
            LOGGER.debug("Added + prefix to phone number: %s", phone_number)

        try:
            with serial.Serial(self.device, self.baud_rate, timeout=0.5) as ser:
                # Wait for module to be ready
                # BUG FIX #1: Use time.sleep() in thread context, not asyncio.run()
                time.sleep(0.5)
                ser.flush()

                # Configure module
                self._write_command(ser, "ATZ")
                self._write_command(ser, 'AT+CSCS="UCS2"')
                self._write_command(ser, "AT+CSMP=17,168,0,8")
                self._write_command(ser, "AT+CMGF=1")

                # When AT+CSCS="UCS2" is set, ALL text data must be in UCS2
                # This includes both phone number AND message content
                phone_ucs2 = self._convert_to_ucs2(phone_number)

                # Send AT+CMGS command and wait for > prompt
                LOGGER.debug('Sending: AT+CMGS="%s"', phone_ucs2)
                ser.write(f'AT+CMGS="{phone_ucs2}"\r\n'.encode())
                time.sleep(0.3)

                # Wait for > prompt
                prompt_response = self._read_response(ser, timeout=1.0)
                LOGGER.debug("Prompt response: %s", prompt_response)

                if ">" not in prompt_response:
                    msg = f"Did not receive > prompt, got: {prompt_response}"
                    raise RuntimeError(msg)

                # Send message content in UCS2 format
                message_ucs2 = self._convert_to_ucs2(message)
                LOGGER.debug("Sending message (UCS2 length: %d)", len(message_ucs2))
                # In text mode (AT+CMGF=1) with AT+CSCS="UCS2",
                # the module expects the UCS2 hex string as ASCII text, NOT raw bytes.
                ser.write(message_ucs2.encode())
                ser.write(b"\x1a")  # Ctrl+Z

                # Wait longer for SMS to be sent
                LOGGER.debug("Waiting for SMS to be sent...")
                time.sleep(5)

                # Read final response with longer timeout
                response = self._read_response(ser, timeout=10.0)
                LOGGER.debug("Final response: %s", response)

                if "OK" not in response and "+CMGS" not in response:
                    msg = f"SMS sending failed: {response}"
                    raise RuntimeError(msg)

        except serial.SerialException as ex:
            LOGGER.error("Could not open serial port %s: %s", self.device, ex)
            raise
        except OSError as ex:
            LOGGER.error("System error: %s", ex)
            raise

    def _write_command(self, ser: serial.Serial, command: str) -> str:
        """Send command to serial port and return response."""
        LOGGER.debug("Sending: %s", command)
        ser.write(f"{command}\r\n".encode())
        time.sleep(0.2)

        response = self._read_response(ser, timeout=1.0)
        LOGGER.debug("Response: %s", response)
        return response

    def _read_response(self, ser: serial.Serial, timeout: float = 1.0) -> str:
        """Read response from serial port with timeout."""
        response = b""
        start_time = time.time()
        last_data_time = start_time

        while True:
            try:
                if ser.in_waiting > 0:
                    chunk = ser.read(ser.in_waiting)
                    response += chunk
                    last_data_time = time.time()
                    LOGGER.debug(
                        "Read chunk: %s", chunk.decode("utf-8", errors="ignore")
                    )
                    time.sleep(0.05)
                else:
                    # If no data for 0.5 seconds, break
                    if time.time() - last_data_time > 0.5:
                        break
                    # If total timeout exceeded, break
                    if time.time() - start_time > timeout:
                        LOGGER.debug("Timeout reached after %.2f seconds", timeout)
                        break
                    time.sleep(0.05)
            except OSError as ex:
                LOGGER.debug("OSError while reading: %s", ex)
                break

        result = response.decode("utf-8", errors="ignore").strip()
        LOGGER.debug("Total read: %d bytes, decoded: %s", len(response), result)
        return result

    @staticmethod
    def _convert_to_ucs2(text: str) -> str:
        """Convert string to UCS2 hexadecimal representation."""
        return "".join(f"{ord(char):04x}" for char in text)
