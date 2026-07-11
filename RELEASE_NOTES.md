# SIM800C Integration v0.6.0 🔊

Play a pre-made audio clip **into a voice call** so the person you call hears it.

## ✨ What's New

- 🔊 **`sim800c.call_and_play`** — place a call and play an **AMR-NB** audio clip into it, so the **callee hears your message**, then hang up automatically. Perfect for spoken alerts ("Water leak detected at home") to a phone that has no smart-home app.

```yaml
automation:
  - alias: "Voice-call alert on a water leak"
    triggers:
      - trigger: state
        entity_id: binary_sensor.water_leak
        to: "on"
    actions:
      - action: sim800c.call_and_play
        data:
          target: "+79990001122"
          audio_file: "/media/sim800c/alert.amr"
          duration: 5          # optional: known clip length in seconds
          ring_duration: 30     # optional: seconds to ring before giving up
          volume: 90            # optional: 0-100
        response_variable: result
      - if: "{{ not result.answered }}"
        then:
          - action: sim800c.send_sms
            data:
              target: "+79990001122"
              message: "⚠️ Water leak at home (call went unanswered)."
```

The service returns `{"answered": <bool>, "played": <bool>}`.

## 🎧 Audio format

The clip **must be AMR-NB (8 kHz, mono)** — the format the SIM800C plays natively.
Convert an existing WAV/MP3 with `ffmpeg` (built with an opencore-amr encoder):

```bash
ffmpeg -i input.wav -ar 8000 -ac 1 -c:a libopencore_amrnb -b:a 12.2k alert.amr
```

You can generate the source audio with any TTS engine first, then convert it.
Place the resulting `.amr` under a Home Assistant allowlisted directory (e.g.
`/media/`) so the service can read it.

## 📦 Installation / Upgrade

### Via HACS (Recommended)
1. Update the "SIM800C" integration via HACS.
2. Restart Home Assistant.

### Manual
1. Copy `custom_components/sim800c` into your Home Assistant `custom_components` directory, overwriting the previous version.
2. Restart Home Assistant.

**Full changelog:** see [CHANGELOG.md](CHANGELOG.md).
