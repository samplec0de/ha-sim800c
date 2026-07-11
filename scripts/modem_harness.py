#!/usr/bin/env python3
"""
Standalone SIM800C harness — run on the machine with the modem attached.

Usage:
  python3 scripts/modem_harness.py --device /dev/ttyUSB0 status
  python3 scripts/modem_harness.py --device /dev/ttyUSB0 send +79990001122 "Тест"
  python3 scripts/modem_harness.py --device /dev/ttyUSB0 call +79990001122 --ring 20
  python3 scripts/modem_harness.py --device /dev/ttyUSB0 monitor --seconds 60
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

# Import the modem package directly (as a top-level package) so this harness
# stays standalone: importing via `custom_components.sim800c.modem` would run
# `custom_components/sim800c/__init__.py`, which pulls in Home Assistant.
sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "custom_components" / "sim800c")
)

from modem import CALL_STAT_ACTIVE, Modem, Transport


async def _run_call(modem: Modem, number: str, ring: float) -> None:
    """Dial `number`, print live call state, and hang up after `ring` seconds."""
    await modem.dial(number)
    print(f"dialing {number} ...")
    deadline = time.monotonic() + ring
    answered = False
    saw_call = False
    while time.monotonic() < deadline:
        await asyncio.sleep(1.0)
        call = await modem.get_current_call()
        if call is None:
            if saw_call:
                print("state: ended (remote hung up / rejected)")
                break
            continue
        saw_call = True
        print(f"state: dir={call.direction} stat={call.state} number={call.number}")
        if call.state == CALL_STAT_ACTIVE:
            answered = True
            print(">>> ANSWERED")
            break
    await modem.hangup()
    print("hung up. answered:", answered)


async def _run_monitor(modem: Modem, seconds: float) -> None:
    """Poll AT+CLCC for `seconds`, printing any incoming call it sees."""
    print(f"monitoring incoming calls for {seconds}s (CLIP enabled)...")
    deadline = time.monotonic() + seconds
    last: str | None = None
    while time.monotonic() < deadline:
        await asyncio.sleep(1.0)
        call = await modem.get_current_call()
        desc = (
            None
            if call is None
            else f"dir={call.direction} stat={call.state} number={call.number}"
        )
        if desc != last:
            print("clcc:", desc)
            last = desc


async def _run_sms_watch(modem: Modem, seconds: float, *, delete: bool) -> None:
    """Poll for unread SMS for `seconds`, printing (and optionally deleting) them."""
    print(f"watching for incoming SMS for {seconds}s (delete={delete})...")
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        await asyncio.sleep(2.0)
        for msg in await modem.list_unread_sms():
            print(f"SMS #{msg.index} from {msg.sender} at {msg.timestamp}:")
            print(f"    {msg.text!r}")
            if delete:
                await modem.delete_sms(msg.index)
                print(f"    (deleted #{msg.index})")


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
    call = sub.add_parser("call")
    call.add_argument("number")
    call.add_argument("--ring", type=float, default=20.0)
    monitor = sub.add_parser("monitor")
    monitor.add_argument("--seconds", type=float, default=60.0)
    sms = sub.add_parser("sms")
    sms.add_argument("--seconds", type=float, default=60.0)
    sms.add_argument("--delete", action="store_true")
    sub.add_parser("cnum")
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
        elif args.cmd == "call":
            await _run_call(modem, args.number, args.ring)
        elif args.cmd == "monitor":
            await _run_monitor(modem, args.seconds)
        elif args.cmd == "sms":
            await _run_sms_watch(modem, args.seconds, delete=args.delete)
        elif args.cmd == "cnum":
            # Own subscriber number, if provisioned on the SIM.
            print(await transport.execute("AT+CNUM"))
    finally:
        await transport.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
