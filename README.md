# SIM800C Integration for Home Assistant

Home Assistant integration for SIM800C GSM module connected via USB/Serial.

Currently supports **SMS notifications**.

## Features

- Send SMS messages using Home Assistant's `notify` service
- Full Unicode support (Cyrillic, Chinese, Arabic, etc.) via UCS2 encoding
- Simple YAML configuration
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

Add the following to your `configuration.yaml`:

```yaml
notify:
  - name: sms
    platform: sim800c
    device: /dev/ttyUSB0  # Your SIM800C device path
    baud_rate: 9600  # Optional, defaults to 9600
```

### Finding Your Device Path

On Linux, your SIM800C module typically appears as `/dev/ttyUSB0` or `/dev/ttyUSB1`. You can find available serial devices by running:

```bash
ls -l /dev/ttyUSB*
```

Or use the "Hardware" tab in Settings > System > Hardware within Home Assistant to find the device path after connecting the module.

## Usage

### Sending SMS

Use the `notify.sms` service to send an SMS message:

```yaml
service: notify.sms
data:
  target: "+1234567890"
  message: "Hello from Home Assistant!"
```

### Multiple Recipients

You can send to multiple phone numbers:

```yaml
service: notify.sms
data:
  target:
    - "+1234567890"
    - "+9876543210"
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
      - action: notify.sms
        data:
          target: "+1234567890"
          message: "⚠️ Alarm triggered at home!"
```

## Unicode Support

This integration uses UCS2 encoding, which means you can send messages in any language, including:

- Cyrillic (Russian, Ukrainian, Bulgarian, etc.)
- Chinese
- Arabic
- Greek
- And more!

Example:

```yaml
service: notify.sms
data:
  target: "+1234567890"
  message: "Привет! Это сообщение на русском языке."
```

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

### Testing SMS

Use the test script to verify your SIM800C module:

```bash
python3 test_sim800c.py
```

This will check:
- Module connectivity
- SIM card status
- Network registration
- Signal strength

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
