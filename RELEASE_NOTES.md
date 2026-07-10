# SIM800C Integration v0.2.0 🎉

Config-flow setup, a proper `send_sms` service, and a rewritten modem layer that serializes all AT-command traffic through a single hub.

## ⚠️ Breaking Changes

- **The `notify` platform is gone.** Remove any `notify:` block referencing the `sim800c` platform from `configuration.yaml`.
- **`notify.sms` is replaced by `sim800c.send_sms`.** Update automations/scripts to call the new service (see below).

## ✨ What's New

### Config Flow Setup
- 🖱️ **UI Setup** - Add the integration from Settings → Devices & Services → Add Integration → SIM800C. No more YAML configuration.
- ✅ **Validated on Setup** - The config flow connects to the modem and confirms network registration before creating the entry.

### `sim800c.send_sms` Service
- 📱 Replaces `notify.sms` with fields `target`, `message`, and `force_unicode`.
- 👥 `target` accepts a single phone number or a list of numbers.
- 🌍 Messages are automatically encoded as GSM 7-bit or UCS2 based on content; set `force_unicode: true` to force UCS2.

```yaml
service: sim800c.send_sms
data:
  target: "+79990001122"
  message: "Hello from Home Assistant!"
```

### Serialized Modem Hub
- 🔒 All modem access (setup, service calls, diagnostics) is queued through a single hub, so consecutive SMS sends no longer need manual delays between them.
- 🧾 Token-based AT response parsing removes false error logging seen with the previous substring-based approach.

### Diagnostic Sensors
- 📶 `sensor.sim800c_signal` - Signal strength in dBm.
- 📡 `sensor.sim800c_network` - Network registration state (`registered` or `searching`).

## 📦 Installation / Upgrade

### Via HACS (Recommended)
1. Update the "SIM800C" integration via HACS.
2. Restart Home Assistant.
3. Remove the old `notify:` block for the `sim800c` platform from `configuration.yaml`, if present.
4. Add the integration via Settings → Devices & Services → Add Integration → SIM800C.

### Manual
1. Copy `custom_components/sim800c` to your HA config directory, overwriting the previous version.
2. Restart Home Assistant.
3. Remove the old `notify:` block for the `sim800c` platform from `configuration.yaml`, if present.
4. Add the integration via Settings → Devices & Services → Add Integration → SIM800C.

## 🔧 Quick Start

Add the integration via the UI, then send SMS:

```yaml
service: sim800c.send_sms
data:
  target: "+79990001122"
  message: "Hello from Home Assistant! 🎉"
```

## 🐛 Known Issues & Limitations

- SMS only (no voice call support).
- Requires serial device access permissions (see [README.md](README.md)).
- Phone number must be in international format (`+7...`).

## 📖 Documentation

Full documentation available in [README.md](README.md).

## 🙏 Acknowledgments

- Based on [integration_blueprint](https://github.com/ludeeus/integration_blueprint) by @ludeeus
- Inspired by [homeassistant-gsm-call](https://github.com/black-roland/homeassistant-gsm-call)

---

**Enjoy the rebuilt SIM800C integration!** 📨

If you encounter any issues, please [open an issue](https://github.com/samplec0de/ha-sim800c/issues).
