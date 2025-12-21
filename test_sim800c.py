#!/usr/bin/env python3
"""Test SIM800C module and check network registration."""

import serial
import time

def send_command(ser, cmd, wait=1):
    """Send AT command and read response."""
    print(f"\n>>> {cmd}")
    ser.write(f"{cmd}\r\n".encode())
    time.sleep(wait)

    response = b""
    while ser.in_waiting > 0:
        response += ser.read(ser.in_waiting)
        time.sleep(0.1)

    resp_str = response.decode('utf-8', errors='ignore').strip()
    print(f"<<< {resp_str}")
    return resp_str

try:
    with serial.Serial('/dev/ttyUSB0', 9600, timeout=1) as ser:
        time.sleep(2)
        ser.flush()

        print("=" * 50)
        print("Testing SIM800C module")
        print("=" * 50)

        # Basic test
        send_command(ser, "AT")

        # Check SIM card
        send_command(ser, "AT+CPIN?")

        # Check network registration
        send_command(ser, "AT+CREG?")

        # Check signal strength
        send_command(ser, "AT+CSQ")

        # Check operator
        send_command(ser, "AT+COPS?")

        # SMS settings
        send_command(ser, "AT+CMGF=1")  # Text mode
        send_command(ser, "AT+CSCS?")   # Character set

        print("\n" + "=" * 50)
        print("✓ Test complete")
        print("=" * 50)

except Exception as e:
    print(f"❌ Error: {e}")

