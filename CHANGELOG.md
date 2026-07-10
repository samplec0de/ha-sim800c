# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
