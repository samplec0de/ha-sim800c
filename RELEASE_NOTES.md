# SIM800C Integration v0.8.0 📇

Adds a **Last SMS sender** sensor — the SMS counterpart to `Last caller`.

## ✨ What's New

- 📇 **`sensor.sim800c_last_sms_sender`** — the phone number of the most recent SMS sender as the sensor's **state** (mirroring `sensor.sim800c_last_caller` for calls), persisted until the next message arrives. The sender number is also still exposed as an attribute of `sensor.sim800c_last_sms`; this sensor just makes it directly usable as state in templates and automations.

```yaml
automation:
  - alias: "Notify who last texted"
    triggers:
      - trigger: state
        entity_id: sensor.sim800c_last_sms_sender
    actions:
      - action: notify.mobile_app_phone
        data:
          message: "New SMS from {{ states('sensor.sim800c_last_sms_sender') }}"
```

## 📦 Installation / Upgrade

### Via HACS (Recommended)
1. Update the "SIM800C" integration via HACS.
2. Restart Home Assistant.

### Manual
1. Copy `custom_components/sim800c` into your Home Assistant `custom_components` directory, overwriting the previous version.
2. Restart Home Assistant.

**Full changelog:** see [CHANGELOG.md](CHANGELOG.md).
