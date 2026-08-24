# SIM800C Integration v0.9.0 📶

Keeps the modem on the network by itself — and stops a slow SMS from wedging it.

## 🩺 The problem

A SIM800C that the network de-registers can settle into `AT+CREG?` state `0` — *not registered, not searching* — and stay there indefinitely. The signal sensor keeps reporting a healthy value, so nothing looks wrong until an SMS fails with "Modem is not registered on the network". `AT+COPS=0` answers `ERROR` in that state; only a radio power-cycle re-attaches the module. In the wild this went unnoticed for six days.

## ✨ What's New

- 📶 **Automatic registration recovery.** The background monitor re-reads registration every minute. If it stays down for **10 minutes**, the radio is cycled (`AT+CFUN=0` → `AT+CFUN=1`) and given up to 90s to re-attach; a successful cycle re-runs the modem initialization, since `AT+CFUN` resets SMS text mode and caller-ID reporting. Cycles are spaced at least **30 minutes** apart and are skipped while a call is in progress.
- 🔁 **`sim800c.send_sms` recovers too.** When the modem reports itself unregistered, the service now cycles the radio once and retries the message instead of failing immediately.
- ⏱️ `sensor.sim800c_network` updates once a minute (previously only on the 5-minute sensor poll).

## 🐛 Fixed

- **A slow SMS no longer wedges the modem.** The wait for `+CMGS` was 15s, while the network routinely needs 16–25s to accept a multi-part UCS2 (Cyrillic) message. On timeout the modem stayed in text-entry mode and swallowed every subsequent AT command — the retries, the call poll, everything — until it was power-cycled. The timeout is now 60s, and any failure inside the send transaction sends `ESC` to leave text-entry mode.

## 📦 Installation / Upgrade

### Via HACS (Recommended)
1. Update the "SIM800C" integration via HACS.
2. Restart Home Assistant.

### Manual
1. Copy `custom_components/sim800c` into your Home Assistant `custom_components` directory, overwriting the previous version.
2. Restart Home Assistant.

**Full changelog:** see [CHANGELOG.md](CHANGELOG.md).
