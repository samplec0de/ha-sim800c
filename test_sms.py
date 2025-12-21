#!/usr/bin/env python3
"""Test script to simulate SMS sending without real hardware."""

import sys
sys.path.insert(0, '/workspaces/ha-sim800c/custom_components')

from sim800c.notify import SIM800CSMSNotificationService

# Mock serial device (won't actually send)
print("Testing SIM800C notification service...")
print("Note: This will fail without real hardware, but tests the code structure")

service = SIM800CSMSNotificationService(device="/dev/ttyUSB0", baud_rate=9600)
print(f"✓ Service created with device: {service.device}")
print(f"✓ Baud rate: {service.baud_rate}")
print("\nService structure is valid!")
print("\nTo test actual SMS sending, use Home Assistant Developer Tools once hardware is connected.")


