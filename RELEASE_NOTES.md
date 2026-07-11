# SIM800C Integration v0.4.0 📩

The integration can now **receive SMS**, not just send them. Incoming messages are surfaced as an event and a sensor, with automatic GSM/UCS2 (Cyrillic/Unicode) decoding.

## ✨ What's New

### Receiving SMS
- 📩 `sensor.sim800c_last_sms` — text of the most recently received SMS, with `sender`, `text` (full body), and `timestamp` attributes.
- 📣 `sim800c_incoming_sms` **event** — fired with `{"sender": "...", "text": "...", "timestamp": "..."}` for each received message.
- 🌍 Both GSM 7-bit and UCS2 (Cyrillic, emoji, …) bodies are decoded automatically.

```yaml
automation:
  - alias: "Forward incoming SMS to my phone"
    triggers:
      - trigger: event
        event_type: sim800c_incoming_sms
    actions:
      - action: notify.mobile_app_phone
        data:
          title: "📩 SMS from {{ trigger.event.data.sender }}"
          message: "{{ trigger.event.data.text }}"
```

## 🔧 Under the Hood
- Received messages are detected by a background poll of `AT+CMGL="REC UNREAD"`, serialized with calls and outgoing SMS through the existing transport lock. `AT+CSDH=1` is enabled at init so each message's data-coding scheme is available for correct decoding.

## ⚠️ Notes
- After a message is read and its event fires, it is **deleted from the modem** (`AT+CMGD`) to avoid duplicate events and keep the SIM's limited storage from filling up. Listing unread also marks messages read, so no duplicate fires even if a delete fails.
- Received SMS are detected by polling every few seconds (not instantly).
- Long (multi-part) messages are reported as **separate events**, one per part — the integration does not reassemble concatenated SMS.

## 📦 Installation / Upgrade

### Via HACS (Recommended)
1. Update the "SIM800C" integration via HACS.
2. Restart Home Assistant.

### Manual
1. Copy `custom_components/sim800c` into your Home Assistant `custom_components` directory, overwriting the previous version.
2. Restart Home Assistant.

**Full changelog:** see [CHANGELOG.md](CHANGELOG.md).
