# SIM800C Integration for Home Assistant

Home Assistant integration for SIM800C GSM module connected via USB/Serial.

Supports **SMS notifications** and **voice calls** (ring alerts / missed-call notifications).

## Features

- Send SMS messages via the `sim800c.send_sms` service
- Place voice calls via the `sim800c.call` service, with automatic hang-up and answered/no-answer reporting (no audio is played)
- Hang up an active call via the `sim800c.hang_up` service
- Detect incoming calls via `binary_sensor.sim800c_incoming_call` (with caller number) and the `sim800c_incoming_call` event
- Live call state via `sensor.sim800c_call_state` (`idle` / `dialing` / `ringing` / `active` / `incoming`)
- Full Unicode support (Cyrillic, Chinese, Arabic, etc.) with automatic GSM 7-bit / UCS2 encoding
- UI-based setup via config flow (no YAML editing required)
- Diagnostic sensors for signal strength and network registration
- Serialized modem access, so SMS sends and calls never race on the serial port
- Works with SIM800C GSM modules connected via USB or serial

## Installation

### Manual Installation

1. Copy the `custom_components/sim800c` directory to your Home Assistant's `custom_components` directory.
2. Restart Home Assistant.

### HACS Installation

1. Add this repository as a custom repository in HACS.
2. Search for "SIM800C" and install.
3. Restart Home Assistant.

## Configuration

Configuration is done entirely through the Home Assistant UI (config flow) — no YAML editing required.

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **SIM800C** and select it.
3. Enter your modem's **device path** (e.g. `/dev/ttyUSB0`) and **baud rate** (defaults to `9600`).
4. Home Assistant will connect to the modem and verify it is registered on the network before creating the entry.

### Finding Your Device Path

On Linux, your SIM800C module typically appears as `/dev/ttyUSB0` or `/dev/ttyUSB1`. You can find available serial devices by running:

```bash
ls -l /dev/ttyUSB*
```

Or use the "Hardware" tab in Settings > System > Hardware within Home Assistant to find the device path after connecting the module.

## Usage

### Sending SMS

Use the `sim800c.send_sms` service to send an SMS message:

```yaml
service: sim800c.send_sms
data:
  target: "+79990001122"
  message: "Hello from Home Assistant!"
```

`target` accepts either a single phone number or a list of numbers. The optional `force_unicode` field forces UCS2 encoding even when the message would otherwise fit GSM 7-bit encoding:

| Field | Required | Description |
| --- | --- | --- |
| `target` | Yes | Phone number(s) in international format (`+7...`). Accepts a single string or a list. |
| `message` | Yes | Message text. Cyrillic and other Unicode text is supported. |
| `force_unicode` | No | Always send as UCS2 even if the text fits GSM 7-bit. Defaults to `false`. |

### Multiple Recipients

You can send to multiple phone numbers:

```yaml
service: sim800c.send_sms
data:
  target:
    - "+79990001122"
    - "+79990003344"
  message: "Alert: Motion detected!"
```

### Example Automation

```yaml
automation:
  - alias: "Send SMS on alarm trigger"
    triggers:
      - trigger: state
        entity_id: alarm_control_panel.home
        to: "triggered"
    actions:
      - action: sim800c.send_sms
        data:
          target: "+79990001122"
          message: "⚠️ Alarm triggered at home!"
```

## Unicode Support

Messages are automatically encoded as GSM 7-bit when the text fits that character set, and UCS2 otherwise — so you can send messages in any language without any configuration, including:

- Cyrillic (Russian, Ukrainian, Bulgarian, etc.)
- Chinese
- Arabic
- Greek
- And more!

Example:

```yaml
service: sim800c.send_sms
data:
  target: "+79990001122"
  message: "Привет! Это сообщение на русском языке."
```

Set `force_unicode: true` if you need to force UCS2 encoding for a message that would otherwise be sent as GSM 7-bit.

## Voice Calls

The integration can place and observe voice calls. No audio is played or recorded — this is intended for **ring alerts** and **missed-call notifications**, plus knowing whether a call was answered.

### Placing a Call

Use the `sim800c.call` service:

```yaml
service: sim800c.call
data:
  target: "+79990001122"
  ring_duration: 30   # optional, seconds to ring before auto hang-up (1–120)
```

| Field | Required | Description |
| --- | --- | --- |
| `target` | Yes | Phone number in international format (`+7...`). |
| `ring_duration` | No | Seconds to let the call ring before hanging up (1–120, default `30`). The call also ends early if the other party answers or hangs up. |

The service **returns a response** indicating whether the call was answered:

```yaml
# In a script/automation using response variables:
- action: sim800c.call
  data:
    target: "+79990001122"
  response_variable: call_result
- if: "{{ call_result.answered }}"
  then:
    - action: notify.mobile_app
      data:
        message: "They picked up!"
```

`call_result` looks like `{"answered": true, "state": "answered"}`. `state` is one of `answered`, `no_answer` (rang out and auto-hung-up), or `ended` (the remote hung up / rejected before answering).

### Hanging Up

```yaml
service: sim800c.hang_up
```

### Detecting Incoming Calls

When someone calls the SIM, two things happen:

- `binary_sensor.sim800c_incoming_call` turns **on** while the phone is ringing. Its `caller` attribute holds the caller's number (requires caller-ID / `+CLIP`, which the integration enables automatically).
- A `sim800c_incoming_call` **event** fires with `{"caller": "+7..."}`.

Example automation reacting to an incoming call:

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

Or trigger on the binary sensor state:

```yaml
    triggers:
      - trigger: state
        entity_id: binary_sensor.sim800c_incoming_call
        to: "on"
```

> **Note:** The integration does not answer incoming calls (there is no audio path); it only reports them. Incoming calls are detected by polling the modem every few seconds, so a very short ring may occasionally be missed.

## Automation Examples

All numbers below are placeholders — replace them with your own.

### Ring alert on an event (missed-call notification)

Call your phone (no audio, just make it ring) when something important happens, e.g. an alarm is triggered:

```yaml
automation:
  - alias: "Ring me when the alarm triggers"
    triggers:
      - trigger: state
        entity_id: alarm_control_panel.home
        to: "triggered"
    actions:
      - action: sim800c.call
        data:
          target: "+79990001122"
          ring_duration: 20
```

### Call, and fall back to SMS if unanswered

Use the service response to branch: if nobody picks up, send an SMS instead.

```yaml
automation:
  - alias: "Water leak: call, else SMS"
    triggers:
      - trigger: state
        entity_id: binary_sensor.water_leak
        to: "on"
    actions:
      - action: sim800c.call
        data:
          target: "+79990001122"
          ring_duration: 25
        response_variable: call_result
      - if:
          - condition: template
            value_template: "{{ not call_result.answered }}"
        then:
          - action: sim800c.send_sms
            data:
              target: "+79990001122"
              message: "⚠️ Water leak detected at home! (call went unanswered)"
```

### Retry the call until it is answered

Loop a few times, stopping as soon as the call is picked up.

```yaml
automation:
  - alias: "Insist until answered"
    triggers:
      - trigger: state
        entity_id: binary_sensor.freezer_door
        to: "on"
        for: "00:10:00"
    actions:
      - repeat:
          count: 3
          sequence:
            - action: sim800c.call
              data:
                target: "+79990001122"
                ring_duration: 25
              response_variable: call_result
            - if:
                - condition: template
                  value_template: "{{ call_result.answered }}"
              then:
                - stop: "Answered"
            - delay: "00:01:00"
```

### Notify on an incoming call (with caller ID)

```yaml
automation:
  - alias: "Notify on incoming call"
    triggers:
      - trigger: event
        event_type: sim800c_incoming_call
    actions:
      - action: notify.mobile_app_phone
        data:
          title: "📞 Incoming call"
          message: "From {{ trigger.event.data.caller or 'unknown number' }}"
```

### "Call to trigger" — act only on a specific caller

Turn an incoming call from a known number into an action (e.g. open the gate). The integration never answers, so the caller is not charged — it's a free trigger. Restrict it to trusted numbers.

```yaml
automation:
  - alias: "Open gate on call from a trusted number"
    triggers:
      - trigger: event
        event_type: sim800c_incoming_call
    conditions:
      - condition: template
        value_template: >-
          {{ trigger.event.data.caller in
             ['+79990001122', '+79990003344'] }}
    actions:
      - action: switch.turn_on
        target:
          entity_id: switch.gate_relay
```

### Log missed calls

```yaml
automation:
  - alias: "Log missed calls"
    triggers:
      - trigger: state
        entity_id: binary_sensor.sim800c_incoming_call
        to: "off"
    conditions:
      - condition: template
        value_template: "{{ trigger.from_state.attributes.caller is not none }}"
    actions:
      - action: logbook.log
        data:
          name: "SIM800C"
          message: "Missed call from {{ trigger.from_state.attributes.caller }}"
```

> **Tip:** the entity IDs above (`binary_sensor.sim800c_incoming_call`, etc.) may be prefixed with the modem's area — e.g. `binary_sensor.hallway_sim800c_incoming_call` — if you assigned the device to an area. Check **Settings → Devices & Services → SIM800C** for the exact IDs.

## Diagnostic Sensors

The integration exposes two diagnostic sensors per configured modem:

- `sensor.sim800c_signal` — signal strength in dBm.
- `sensor.sim800c_network` — network registration state (`registered` or `searching`).
- `sensor.sim800c_call_state` — current call state (`idle` / `dialing` / `ringing` / `active` / `incoming`), updated live.
- `binary_sensor.sim800c_incoming_call` — `on` while an incoming call is ringing, with the caller number in its `caller` attribute.

The signal and network sensors are polled periodically; the call-state and incoming-call sensors update as calls come and go. All can be used in automations or dashboards to monitor modem health and call activity.

## Troubleshooting

### Enable Debug Logging

Add to your `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.sim800c: debug
```

### Serial Device Permission Issues

If you get `Permission denied` errors when accessing `/dev/ttyUSB0`, use the provided fix script:

**Quick Fix:**

Run the `FIX_USB_ON_HOST.sh` script **on your host machine** (not in the container):

```bash
bash /path/to/ha-sim800c/FIX_USB_ON_HOST.sh
```

This script will:
- ✅ Check if the device exists
- ✅ Apply temporary permissions (chmod 666)
- ✅ Create a permanent udev rule for automatic permissions
- ✅ Show you the commands to restart Home Assistant

**Manual Fix:**

Alternatively, you can manually set permissions:

```bash
# On host machine
sudo chmod 666 /dev/ttyUSB0
```

### Permission Issues (Alternative Methods)

**For Home Assistant Core (manual installation only):**

If you get permission errors accessing the serial device, add the Home Assistant user to the `dialout` group:

```bash
sudo usermod -a -G dialout homeassistant
```

Then restart Home Assistant.

**For Home Assistant Container (Docker):**

Pass the serial device to the container and give it appropriate permissions:

```bash
docker run ... --device=/dev/ttyUSB0:/dev/ttyUSB0 --group-add dialout ...
```

Or use `--privileged` flag (less secure but simpler).

**For Home Assistant OS:** Serial devices should work automatically. If not, check Settings → System → Hardware for device visibility.

### Module Not Responding

1. Check that the SIM card is inserted and has network signal.
2. Verify the device path is correct.
3. Try a different baud rate (common values: 9600, 115200).
4. Check the SIM800C module has power (some modules need external power supply).

## Hardware Requirements

- SIM800C GSM module
- USB-to-Serial adapter (if not using built-in USB)
- Active SIM card with SMS capability
- Power supply for the module (some modules need 5V/2A external power)

## Tested On

- SIM800C modules with USB interface
- Home Assistant OS
- Home Assistant Container
- Home Assistant Core

## Development

Based on the [integration_blueprint](https://github.com/ludeeus/integration_blueprint) template.

### Development Environment

This project includes a devcontainer configuration for easy development in VSCode:

1. Open the project in VSCode with Dev Containers extension
2. The container will automatically mount `/dev/ttyUSB0`
3. If you get permission errors, run `FIX_USB_ON_HOST.sh` on your host machine
4. Start Home Assistant with: `bash scripts/develop`
5. Access at http://localhost:8123

### Testing Against Real Hardware

Use `scripts/modem_harness.py` to talk to a real SIM800C module outside of Home Assistant:

```bash
python3 scripts/modem_harness.py --device /dev/ttyUSB0 status
python3 scripts/modem_harness.py --device /dev/ttyUSB0 send +79990001122 "Тест"
```

`status` reports network registration and signal strength; `send` sends an SMS and prints the `+CMGS` reference.

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
