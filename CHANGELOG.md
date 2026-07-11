# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2026-07-11

### Added
- `sensor.sim800c_last_caller`: number of the most recent incoming caller, persisted after the call ends (unlike the binary sensor's `caller` attribute, which clears when the call is over) so a missed call's number stays available.

## [0.4.0] - 2026-07-11

### Added
- Incoming SMS monitoring: received messages are detected by a background poll of `AT+CMGL="REC UNREAD"`, serialized with calls and outgoing SMS through the existing transport lock.
- `sim800c_incoming_sms` event, fired with `{"sender", "text", "timestamp"}` for each received message.
- `sensor.sim800c_last_sms`: text of the most recently received SMS, with `sender`, `text` (full body), and `timestamp` attributes.
- Automatic decoding of both GSM 7-bit and UCS2 (Cyrillic/Unicode) message bodies; `AT+CSDH=1` is enabled during initialization so the message's data-coding scheme is available for correct decoding.
- Modem layer: `Modem.list_unread_sms()` (parses `AT+CMGL`) and `Modem.delete_sms()`; `encoding.from_ucs2_hex()`.
- Harness: `sms` (watch/parse received messages) and `cnum` (own number) subcommands in `scripts/modem_harness.py`.

### Changed
- After a received SMS is read and its event emitted, the message is deleted from the modem (`AT+CMGD`) to avoid duplicate events and prevent the SIM storage from filling up. Listing unread messages also marks them read, so no duplicate event fires even if a delete fails.

### Notes
- Long (multi-part) SMS are reported as separate messages/events, one per part; the integration does not reassemble concatenated SMS.

## [0.3.0] - 2026-07-11

### Added
- `sim800c.call` service: place a voice call with automatic hang-up after a configurable `ring_duration` (1–120s, default 30). Returns a response indicating whether the call was answered (`{"answered": bool, "state": "answered" | "no_answer" | "ended"}`). No audio is played — intended for ring alerts / missed-call notifications and answer detection.
- `sim800c.hang_up` service to end the current call.
- `binary_sensor.sim800c_incoming_call`: turns on while an incoming call rings, exposing the caller's number (via `+CLIP`) in its `caller` attribute.
- `sim800c_incoming_call` event, fired with `{"caller": "+7..."}` on the rising edge of each incoming call.
- `sensor.sim800c_call_state`: live call state (`idle` / `dialing` / `ringing` / `active` / `incoming`).
- Modem layer: `Modem.get_current_call()` (parses `AT+CLCC` into direction/state/caller number) and automatic `AT+CLIP=1` caller-ID enablement during initialization.
- Harness: `call` and `monitor` subcommands in `scripts/modem_harness.py` for testing calls against real hardware.

### Changed
- The modem hub now runs a background loop that polls `AT+CLCC` to detect incoming calls, serialized with SMS access through the existing transport lock.

## [0.2.0] - 2026-07-11

### Added
- UI-based setup via config flow (Settings → Devices & Services → Add Integration → SIM800C); the flow validates the device path, connects to the modem, and confirms network registration before creating the entry.
- `sim800c.send_sms` service with `target`, `message`, and `force_unicode` fields, replacing the `notify` platform.
- Serialized modem hub: all modem access (setup, service calls, diagnostics) is queued through a single hub, so no manual delays are needed between consecutive SMS sends.
- Token-based AT response parsing, eliminating false error logging that could occur with the previous substring-based parsing.
- Automatic GSM 7-bit / UCS2 encoding selection based on message content, with an optional `force_unicode` override.
- Diagnostic sensors: `sensor.sim800c_signal` (signal strength) and `sensor.sim800c_network` (registration state), polled periodically.

### Changed
- Configuration moved from YAML (`notify:` platform) to the Home Assistant UI config flow.

### Removed
- `notify.sms` service and the `notify` platform configuration (**BREAKING**: update automations/scripts to call `sim800c.send_sms` instead).
- Obsolete top-level test scripts `test_sms.py` and `test_sim800c.py`, superseded by `scripts/modem_harness.py`.

### Migration Notes
- Remove the `notify:` block referencing the `sim800c` platform from `configuration.yaml`.
- Add the integration via the UI (Settings → Devices & Services → Add Integration → SIM800C) using the same device path and baud rate.
- Update automations/scripts that called `notify.sms` to call `sim800c.send_sms` with `target` and `message` fields instead.

## [0.1.0] - 2024-12-22

### Added
- Initial release
- SMS sending via SIM800C GSM module
- UCS2 encoding support for Unicode characters (Cyrillic, Chinese, Arabic, etc.)
- YAML-based configuration (no GUI config flow)
- Automatic phone number formatting (adds + prefix if missing)
- Multiple recipients support
- Configurable baud rate (default 9600)
- Debug logging for troubleshooting
- USB device permissions fix script (`FIX_USB_ON_HOST.sh`)
- Module testing script (`test_sim800c.py`)
- Development environment with devcontainer support

### Features
- Send SMS notifications through Home Assistant's `notify` service
- Fast SMS delivery (~4-5 seconds)
- Error handling with detailed logging
- Compatible with Home Assistant OS, Container, and Core installations

### Tested On
- SIM800C modules with USB interface
- Home Assistant 2023.12.0+
- MegaFon network (Russia)

### Known Limitations
- SMS only (no voice call support yet)
- Requires phone number with + prefix (added automatically if missing)
- Serial device must be accessible to Home Assistant

[0.2.0]: https://github.com/samplec0de/ha-sim800c/releases/tag/v0.2.0
[0.1.0]: https://github.com/samplec0de/ha-sim800c/releases/tag/v0.1.0
