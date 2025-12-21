# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.1.0]: https://github.com/samplec0de/ha-sim800c/releases/tag/v0.1.0
