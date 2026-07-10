#!/usr/bin/env python3
"""
Standalone SIM800C harness — run on the machine with the modem attached.

Usage:
  python3 scripts/modem_harness.py --device /dev/ttyUSB0 status
  python3 scripts/modem_harness.py --device /dev/ttyUSB0 send +79990001122 "Тест"
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Import the modem package directly (as a top-level package) so this harness
# stays standalone: importing via `custom_components.sim800c.modem` would run
# `custom_components/sim800c/__init__.py`, which pulls in Home Assistant.
sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "custom_components" / "sim800c")
)

from modem import Modem, Transport


async def main() -> int:
    """Parse CLI args and run the requested modem command against real hardware."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="/dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=9600)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    send = sub.add_parser("send")
    send.add_argument("number")
    send.add_argument("text")
    args = parser.parse_args()

    transport = Transport(args.device, args.baud)
    await transport.connect()
    modem = Modem(transport)
    try:
        await modem.initialize()
        if args.cmd == "status":
            print("registered:", await modem.get_registration())
            print("signal dBm:", await modem.get_signal())
        elif args.cmd == "send":
            ref = await modem.send_sms(args.number, args.text)
            print("sent, +CMGS ref:", ref)
    finally:
        await transport.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
