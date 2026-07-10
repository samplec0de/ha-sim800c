# SIM800C Integration v0.3.0 📞

Voice calls come to the SIM800C integration: place outgoing calls with automatic hang-up and answer detection, and get notified about incoming calls with caller ID. No audio is played — this is built for **ring alerts / missed-call notifications** and knowing whether a call was answered.

## ✨ What's New

### `sim800c.call` Service
- 📞 Places a voice call to `target` and **auto-hangs-up** after `ring_duration` seconds (1–120, default 30).
- ✅ **Returns whether the call was answered** as a service response (`{"answered": true, "state": "answered"}`). `state` is one of `answered`, `no_answer` (rang out), or `ended` (the remote hung up first).

```yaml
action: sim800c.call
data:
  target: "+79990001122"
  ring_duration: 30
response_variable: call_result
```

### `sim800c.hang_up` Service
- ☎️ Ends the current call.

### Incoming Call Detection
- 🔔 `binary_sensor.sim800c_incoming_call` — `on` while an incoming call is ringing, with the caller's number in its `caller` attribute (via `+CLIP`).
- 📣 `sim800c_incoming_call` **event** — fired with `{"caller": "+7..."}` on each incoming call, ready to trigger automations.

```yaml
automation:
  - alias: "Announce incoming call"
    triggers:
      - trigger: event
        event_type: sim800c_incoming_call
    actions:
      - action: notify.mobile_app
        data:
          message: "Incoming call from {{ trigger.event.data.caller }}"
```

### Live Call State Sensor
- 🔄 `sensor.sim800c_call_state` — current call state (`idle` / `dialing` / `ringing` / `active` / `incoming`), updated live.

## 🔧 Under the Hood
- Call progress is tracked via `AT+CLCC`; caller ID is enabled with `AT+CLIP=1`. A background loop polls for incoming calls, serialized with SMS through the existing transport lock so calls and SMS never race on the serial port.

## ⚠️ Notes
- The integration **does not answer** incoming calls (there is no audio path) — it only reports them.
- Incoming calls are detected by polling every few seconds, so a very short ring may occasionally be missed.

## 📦 Installation / Upgrade

### Via HACS (Recommended)
1. Update the "SIM800C" integration via HACS.
2. Restart Home Assistant.

### Manual
1. Copy `custom_components/sim800c` into your Home Assistant `custom_components` directory, overwriting the previous version.
2. Restart Home Assistant.

**Full changelog:** see [CHANGELOG.md](CHANGELOG.md).
