# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.0] - 2026-07-11

### Added
- `sensor.sim800c_last_sms_sender`: the phone number of the most recent SMS sender as the sensor's state (mirroring `sensor.sim800c_last_caller` for calls), persisted until the next message. The sender is also still available as an attribute of `sensor.sim800c_last_sms`.

## [0.7.0] - 2026-07-11

### Added
- `sim800c.answer_and_record` service: answer a **ringing incoming call**, record what the caller says, hang up, then transcribe the recording via a local **Whisper-compatible** STT service (e.g. GigaAM). Returns `{"recorded": bool, "transcript": str | None, "path": str | None}`. Fields: optional `record_seconds` (1–60, default 15) and optional `stt_url` override. The recording is saved under `<config>/media/sim800c/rec_<epoch>.amr`; a STT failure still returns the recording (transcript `None`). Verified end-to-end on real hardware (SIM800 R14.18 → GigaAM v3).
- `sensor.sim800c_last_recording`: transcript of the most recent recorded call, with `caller`, `path`, `url`, `transcript`, and `timestamp` attributes.
- `sim800c_call_recorded` event, fired with `{"caller", "path", "url", "transcript", "timestamp"}`.
- Modem layer: `Modem.answer()` (`AT+CVHU=0` then `ATA`), `Modem.start_recording()` / `Modem.stop_recording()` (`AT+CREC=1,"<file>",0` / `AT+CREC=2`), `Modem.file_size()` (`AT+FSFLSIZE`), `Modem.read_file()` (chunked `AT+FSREAD` — the firmware caps a single read, so files are fetched in 4 KB chunks: mode 0, then mode 1 continue), and `Modem.delete_file()` (`AT+FSDEL`).
- New `stt.py` module (HA layer): a Whisper-compatible transcription client.
- Harness: `record` subcommand in `scripts/modem_harness.py` (answer, record N seconds, read the file, save `./rec.amr`).

### Notes
- Transcription requires a reachable Whisper-compatible STT service; set `stt_url` to its LAN IP on Home Assistant OS (the default `127.0.0.1` points at the HA container). Without STT the recording is still saved and returned.

## [0.6.0] - 2026-07-11

### Added
- `sim800c.call_and_play` service: place a voice call and play a pre-made **AMR-NB** audio clip into it so the **callee hears it**, then automatically hang up. The clip is uploaded to the modem, dialed out, and played into the call's uplink once the other party answers; the call is watched and auto-hung-up (using the optional `duration` clip length, or a 60s cap when unknown). Returns `{"answered": bool, "played": bool}`. Fields: `target`, `audio_file` (path to a local AMR-NB file under an allowlisted directory), optional `duration`, `ring_duration` (1–120s), and `volume` (0–100, default 90).
- Modem layer: `Modem.upload_audio()` (chunked `AT+FSCREATE`/`AT+FSWRITE`), `Modem.play_audio()` (`AT+CREC=4`), and `Modem.stop_audio()` (`AT+CREC=5`).

### Notes
- `call_and_play` requires an **AMR-NB (8 kHz mono)** file. Plain speech can be produced with any TTS engine and then converted to AMR-NB (e.g. with `ffmpeg` + an opencore-amr encoder). The other call services (`sim800c.call`, `sim800c.hang_up`) still play no audio.

## [0.5.0] - 2026-07-11

### Added
- `sensor.sim800c_last_caller`: number of the most recent incoming caller, persisted after the call ends (unlike the binary sensor's `caller` attribute, which clears when the call is over) so a missed call's number stays available.

## [0.4.0] - 2026-07-11

### Added
- Incoming SMS monitoring: received messages are detected by a background poll of `AT+CMGL="REC UNREAD"`, serialized with calls and outgoing SMS through the existing transport lock.
- `sim800c_incoming_sms` event, fired with `{"sender", "text", "timestamp"}` for each received message.
- `sensor.sim800c_last_sms`: text of the most recently received SMS, with `sender`, `text` (full body), and `timestamp` attributes.
- Automatic decoding of both GSM 7-bit and UCS2 (Cyrillic/Unicode) message bodies; `AT+CSDH=1` is enabled during initialization so the message's data-coding scheme is available for correct decoding.
- Modem layer: `Modem.list_unread_sms()` (parses `AT+CMGL`) and `Modem.delete_sms()`; `encoding.from_ucs2_hex()`.
- Harness: `sms` (watch/parse received messages) and `cnum` (own number) subcommands in `scripts/modem_harness.py`.

### Changed
- After a received SMS is read and its event emitted, the message is deleted from the modem (`AT+CMGD`) to avoid duplicate events and prevent the SIM storage from filling up. Listing unread messages also marks them read, so no duplicate event fires even if a delete fails.

### Notes
- Long (multi-part) SMS are reported as separate messages/events, one per part; the integration does not reassemble concatenated SMS.

## [0.3.0] - 2026-07-11

### Added
- `sim800c.call` service: place a voice call with automatic hang-up after a configurable `ring_duration` (1–120s, default 30). Returns a response indicating whether the call was answered (`{"answered": bool, "state": "answered" | "no_answer" | "ended"}`). No audio is played — intended for ring alerts / missed-call notifications and answer detection.
- `sim800c.hang_up` service to end the current call.
- `binary_sensor.sim800c_incoming_call`: turns on while an incoming call rings, exposing the caller's number (via `+CLIP`) in its `caller` attribute.
- `sim800c_incoming_call` event, fired with `{"caller": "+7..."}` on the rising edge of each incoming call.
- `sensor.sim800c_call_state`: live call state (`idle` / `dialing` / `ringing` / `active` / `incoming`).
- Modem layer: `Modem.get_current_call()` (parses `AT+CLCC` into direction/state/caller number) and automatic `AT+CLIP=1` caller-ID enablement during initialization.
- Harness: `call` and `monitor` subcommands in `scripts/modem_harness.py` for testing calls against real hardware.

### Changed
- The modem hub now runs a background loop that polls `AT+CLCC` to detect incoming calls, serialized with SMS access through the existing transport lock.

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
