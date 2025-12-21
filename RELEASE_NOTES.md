# SIM800C Integration v0.1.0 - First Release! 🎉

Send SMS notifications from Home Assistant using SIM800C GSM modules.

## ✨ Features

### Core Functionality
- 📱 **SMS Notifications** - Send SMS through Home Assistant's `notify` service
- 🌍 **Unicode Support** - Full support for Cyrillic, Chinese, Arabic, and other scripts via UCS2 encoding
- ⚡ **Fast Delivery** - Optimized to ~4-5 seconds per SMS
- 📞 **Smart Phone Formatting** - Automatically adds + prefix if missing
- 👥 **Multiple Recipients** - Send to multiple phone numbers at once

### Configuration
- 📝 **YAML-Based** - Simple configuration in `configuration.yaml`
- ⚙️ **Configurable Baud Rate** - Defaults to 9600, customizable
- 🔍 **Debug Logging** - Detailed logs for troubleshooting

### Developer Experience
- 🐳 **Dev Container** - Ready-to-use development environment
- 🛠️ **Helper Scripts** - USB permissions fix, module testing
- 📚 **Comprehensive Docs** - Installation, usage, and troubleshooting guides

## 📦 Installation

### Via HACS (Recommended)
1. Add custom repository: `https://github.com/samplec0de/ha-sim800c`
2. Install "SIM800C" integration
3. Restart Home Assistant

### Manual
1. Copy `custom_components/sim800c` to your HA config directory
2. Restart Home Assistant

## 🔧 Quick Start

Add to `configuration.yaml`:

```yaml
notify:
  - name: sms
    platform: sim800c
    device: /dev/ttyUSB0
    baud_rate: 9600  # Optional
```

Send SMS:

```yaml
service: notify.sms
data:
  target: "+1234567890"
  message: "Hello from Home Assistant! 🎉"
```

## 🐛 Known Issues & Limitations

- SMS only (voice calls planned for v0.2.0)
- Requires serial device access permissions (see docs)
- Phone number must start with + (added automatically if missing)

## 🧪 Tested On

- ✅ SIM800C modules with USB interface
- ✅ Home Assistant 2023.12.0+
- ✅ MegaFon network (Russia)
- ✅ Unicode messages (Cyrillic confirmed working)

## 📖 Documentation

Full documentation available in [README.md](README.md)

## 🙏 Acknowledgments

- Based on [integration_blueprint](https://github.com/ludeeus/integration_blueprint) by @ludeeus
- Inspired by [homeassistant-gsm-call](https://github.com/black-roland/homeassistant-gsm-call)

## 🔮 What's Next?

Planned for v0.2.0:
- Voice call support
- SMS delivery status
- Signal strength sensor
- Network operator sensor

---

**Enjoy your new SMS integration!** 📨

If you encounter any issues, please [open an issue](https://github.com/samplec0de/ha-sim800c/issues).
