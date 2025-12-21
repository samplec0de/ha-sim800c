#!/bin/bash
# ========================================
# RUN THIS SCRIPT ON THE HOST MACHINE
# (not inside the container!)
# ========================================

echo "🔧 Fixing /dev/ttyUSB0 permissions"
echo ""

# Check if device exists
if [ ! -e /dev/ttyUSB0 ]; then
    echo "❌ Device /dev/ttyUSB0 not found!"
    echo "Please connect your SIM800C module and try again."
    exit 1
fi

echo "✓ Device found"
echo "Current permissions:"
ls -l /dev/ttyUSB0
echo ""

# Temporary fix (until device is reconnected/system rebooted)
echo "📝 Applying temporary permissions..."
sudo chmod 666 /dev/ttyUSB0

# Permanent fix via udev
echo "📝 Creating permanent udev rule..."
echo 'KERNEL=="ttyUSB[0-9]*", MODE="0666"' | sudo tee /etc/udev/rules.d/99-usb-serial.rules > /dev/null
sudo udevadm control --reload-rules
sudo udevadm trigger

echo ""
echo "✅ Done! New permissions:"
ls -l /dev/ttyUSB0
echo ""
echo "🔄 Now restart Home Assistant in the container:"
echo "   pkill -f 'hass --config' && cd /workspaces/ha-sim800c && bash scripts/develop"

