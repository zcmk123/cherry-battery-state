# Cherry Keyboard Battery Tray Tool

A Windows system tray tool that displays the battery level of Cherry wireless keyboards in real time. **No Cherry official software required** - reads HID data directly from the USB receiver (dongle).

## Features

- Resides in the system tray, showing real-time battery level
- Reads dongle data directly via HID protocol, no Cherry Utility needed
- Auto-detects device name (e.g., CHERRY MX 2.0S Dongle)
- 6-level battery icon visualization
- Low battery notification (<=20%)
- Sleep detection (icon dims when keyboard is idle)
- Configurable polling interval (5 / 10 / 20 / 30 / 60 seconds, default 30s)
- Persistent configuration, auto-restored on restart
- Red cross indicator when device is disconnected

## Supported Devices

Tested with:

- Cherry MX 2.0S (VID=0x046A, PID=0x01AC)

Theoretically supports all Cherry dongle-based keyboards, as long as the HID enumeration can find a vendor-specific interface with `usage_page=0xFF1C`.

## Download

### Option 1: Download the exe (Recommended)

Download `cherry_battery.exe` from the [Releases](../../releases) page. Double-click to run - no Python environment required.

A `config.json` file is generated next to the exe on first run to save settings.

### Option 2: Run from source

```bash
# Install dependencies
pip install hid pillow pystray

# You also need hidapi.dll - place it in the script directory or load via system PATH
# Download: https://github.com/libusb/hidapi/releases

# Run
python cherry_battery.py
```

> The script loads hidapi.dll from `E:\hidap\x64` by default. If your path differs, modify the `os.add_dll_directory()` call at the top of `cherry_battery.py`.

## Tray Menu

| Menu Item | Action |
|-----------|--------|
| Refresh | Manually query current battery level |
| Polling Interval | Switch auto-query frequency (5/10/20/30/60s) |
| Exit | Close the application |

## How It Works

1. Uses `hid.enumerate()` to find the Cherry dongle's vendor-specific interface (Col04, usage_page=0xFF1C)
2. Sends a battery query command `04 20 00 1A 06` (64-byte Output Report)
3. Reads the status message returned by the dongle; `byte[8]` is the battery percentage
4. A background thread polls at the configured interval and updates the tray icon and tooltip

The command sequence was obtained by reverse-engineering the Cherry Utility's HID communication using Frida. See [Development Notes](#development-notes).

## Will It Interfere with the Keyboard?

No. The tool only accesses the Col04 management interface, not the Col01 interface where keyboard input flows. Each query sends a single 64-byte command and receives one reply, taking <1ms. With 30-second polling, the impact on battery life and typing is negligible.

## Build from Source

```bash
pip install pyinstaller
python -m PyInstaller cherry_battery.spec --noconfirm
```

The output is in `dist/cherry_battery.exe`, bundled with hidapi.dll and 7 battery icon PNGs. The exe icon uses `logo.ico`.

## Project Structure

```
cherry-battery/
├── cherry_battery.py        # Main application
├── cherry_battery.spec      # PyInstaller config
├── logo.png / logo.ico      # App logo (exe icon)
├── icon_0.png ~ icon_6.png  # Battery icons (0=empty, 3=charging, 6=full)
└── README.md                # This file (English)
└── README.zh-CN.md          # Chinese documentation
```

## Development Notes

### Reverse-Engineering Cherry Utility

Cherry Utility communicates with the dongle via HID, but the protocol is not publicly documented. To eliminate the dependency on the official software, [Frida](https://frida.re/) was used for dynamic instrumentation:

1. Launch Cherry Utility in Frida spawn mode
2. Hook `WriteFile` and `ReadFile` APIs to log all HID I/O
3. Analyze captured packets to locate the battery query command

Key finding: Cherry Utility sends commands via **Output Report** (not Feature Report), so simply listening to Input Report only captures echoes and misses the actual commands. The battery query is a single command: `04 20 00 1A 06`.

### Why 30-Second Polling?

Cherry Utility queries battery every 5 seconds plus a heartbeat every 3 seconds - 10x more frequent than this tool. At 30-second intervals, the keyboard's wireless power consumption is dominated by keystroke transmission; the overhead of battery queries is unmeasurable. Adjust to 60 seconds via the tray menu if you want to be even more conservative.

## License

MIT License

## Acknowledgements

- [hidapi](https://github.com/libusb/hidapi) - Cross-platform HID communication library
- [pystray](https://github.com/moses-palmer/pystray) - Python system tray library
- [Pillow](https://python-pillow.org/) - Image processing library