# SIM800C Integration v0.5.0 ☎️

Adds a persistent **last caller** sensor.

## ✨ What's New

- 📇 **`sensor.sim800c_last_caller`** — the number of the most recent incoming caller, kept even after the call ends. Unlike `binary_sensor.sim800c_incoming_call`'s `caller` attribute (which clears when the phone stops ringing), this survives, so a missed call's number stays available for automations and dashboards. Mirrors the existing `sensor.sim800c_last_sms`.

```yaml
automation:
  - alias: "Notify me about the last caller"
    triggers:
      - trigger: state
        entity_id: sensor.sim800c_last_caller
    actions:
      - action: notify.mobile_app_phone
        data:
          message: "Last call from {{ states('sensor.sim800c_last_caller') }}"
```

## 📦 Installation / Upgrade

### Via HACS (Recommended)
1. Update the "SIM800C" integration via HACS.
2. Restart Home Assistant.

### Manual
1. Copy `custom_components/sim800c` into your Home Assistant `custom_components` directory, overwriting the previous version.
2. Restart Home Assistant.

**Full changelog:** see [CHANGELOG.md](CHANGELOG.md).
