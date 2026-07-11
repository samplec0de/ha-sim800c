# SIM800C Integration v0.7.0 🎙️

Answer an incoming call, **record what the caller says, and transcribe it** with a local speech-to-text service — all on the SIM800C.

## ✨ What's New

- 🎙️ **`sim800c.answer_and_record`** — answers a **ringing incoming call**, records the caller for `record_seconds` (1–60, default 15), hangs up, saves the recording under `<config>/media/sim800c/`, and transcribes it via a local **Whisper-compatible** STT service (e.g. [GigaAM](https://github.com/salute-developers/GigaAM)). Returns `{"recorded", "transcript", "path"}`.
- 📝 **`sensor.sim800c_last_recording`** — transcript of the most recent recorded call (attributes: `caller`, `path`, `url`, `transcript`, `timestamp`).
- 📣 **`sim800c_call_recorded`** event with the same fields.

```yaml
automation:
  - alias: "Transcribe and notify on an incoming call"
    triggers:
      - trigger: event
        event_type: sim800c_incoming_call
    actions:
      - action: sim800c.answer_and_record
        data:
          record_seconds: 15
          stt_url: "http://192.168.1.10:9000/v1"   # your STT host's LAN IP
        response_variable: rec
      - action: notify.mobile_app_phone
        data:
          message: "Call from {{ rec.caller if rec.caller else 'unknown' }}: {{ rec.transcript }}"
```

Verified end-to-end on real hardware (SIM800 R14.18 → GigaAM v3): the caller's speech was recorded and transcribed correctly.

## ⚠️ Notes
- If the STT service is unreachable the recording is still saved and returned; only the transcript is `null` (a warning is logged).
- **STT URL on Home Assistant OS:** the default `http://127.0.0.1:9000/v1` points at the HA container itself. On HAOS, set your STT host's **LAN IP** via the `stt_url` field.
- The integration answers the call to record it (there is an audio path only once connected).

## 📦 Installation / Upgrade

### Via HACS (Recommended)
1. Update the "SIM800C" integration via HACS.
2. Restart Home Assistant.

### Manual
1. Copy `custom_components/sim800c` into your Home Assistant `custom_components` directory, overwriting the previous version.
2. Restart Home Assistant.

**Full changelog:** see [CHANGELOG.md](CHANGELOG.md).
