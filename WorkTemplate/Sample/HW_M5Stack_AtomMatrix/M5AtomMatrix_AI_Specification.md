# M5Stack ATOM Matrix v1.1 AI Specification

## Purpose

Use this file as the local knowledge source for the ATOM Matrix before searching
the web. Search official sources when a library API may have changed, when this
file lacks the fact, or when the user asks for a live check.

Focus on what software can do. Give pin numbers when they prevent damage, a
wrong chip target, or a failed flash. The factory image currently in flash is
specified in `Factory M5AtomMatrix_App_Programming Specificaton (AI).md`. Do not
replace that image unless the user asks.

## Device Summary

Connected unit, 2026-09-24:

- Product: ATOM Matrix **v1.1**, SKU string in the app image `C008-B-V11`
- SoC: ESP32-PICO-D4 revision v1.1, 240 MHz dual-core LX6, 520 KB SRAM, **4 MB**
  flash, **no PSRAM**
- MAC: `c8:85:41:68:92:14`
- USB: FTDI-style bridge, product `M5stack`, port was
  `/dev/cu.usbserial-81524AF84F` (detect every time)
- Face: 25× WS2812C on GPIO27
- Button: GPIO39, active low, input-only (no internal pull-up)
- IR LED: GPIO12 transmit
- IMU: I²C 0x68, SCL GPIO21, SDA GPIO25. v1.1 page says **BMI270**. Not yet
  confirmed with a chip-ID read. Do not assume MPU6886.
- Grove: GPIO26 and GPIO32, plus 5 V and GND
- Radios: 2.4 GHz Wi-Fi; Bluetooth 4.2 Classic **and** Low Energy
- Power: 5 V USB, up to 500 mA. No internal battery.
- Backup: `backup/atom-matrix-full-flash-2026-09-24.bin`, SHA-256 in
  `backup/SHA256SUMS`. Read and write this bridge at **115200**. 460800 failed.

Distinguish this board from ATOM Lite (no matrix), ATOM S3 (ESP32-S3 and a
small LCD), and the pre-v1.1 Matrix (MPU6886).

## Capability Knowledge

### Matrix

25 independent RGB pixels. Suitable for a glyph, a bar, status dots, and short
animations. Unsuitable for sentences, photos, or dense UI.

Brightness cap: official FastLED note says about **20**/255. M5Atom's
`LED_DisPlay` default field is **40**. Exceeding that, especially full white,
can overheat the face. Start at or below 40 and lower it if the case gets hot.

M5Unified draws the matrix through `M5.Display`. Call `M5.update()` in the loop.

Pixel index order in a given library is not yet confirmed on this unit. Verify
the first lit pixel against a one-pixel test before shipping a map.

### Button

`M5.BtnA` with M5Unified. GPIO39. Patterns (click, double-click, hold) are
software. The side button resets the chip.

### Motion

`M5.Imu` via M5Unified, which can select BMI270. Readings support tilt, shake,
and orientation relative to gravity. No magnetometer, so no compass. Do not use
the legacy `M5Atom` MPU6886 driver on this SKU unless a chip-ID read returns
the MPU6886 ID.

### Infrared

Transmit on GPIO12 only. Receiving needs an external module. GPIO12 is a
strapping pin; do not strap it at boot. This unit already reports 3.3 V flash
voltage from the strap.

### Wi-Fi

2.4 GHz 802.11 b/g/n only. HTTP, WebSocket, MQTT, NTP, and a small server are
possible when programmed. **Scanning nearby networks is the default**, same
as on the Stick and the tablet. The factory image scans at boot and looks for
SSID `M5Stack-Production`. Joining that SSID is factory-test behaviour, not a
network the board always joins.

Phone scan, in `firmware/M5StackConnect/M5StackConnect.ino`:

- Service `a5c10000-7c3a-4b2e-9f10-6d0a4d13a001`
- Characteristic `a5c10007-7c3a-4b2e-9f10-6d0a4d13a001`, read + write + notify
- Write UTF-8 `scan`. Do the scan from `loop()`, not inside the BLE callback
- Notify and store `{"networks":[{"ssid","rssi","secure"}]}`
- `secure` is false only for `WIFI_AUTH_OPEN`. No channel, BSSID, or password
- Skip empty SSIDs. Keep at most 6 networks. Stop adding once the JSON is
  over about 140 characters. Initial value `{"networks":[]}`
- If the radio was `WIFI_OFF` before the scan, put it back to `WIFI_OFF`
  afterwards so a cube with no saved network stays on Bluetooth
- Create the Wi-Fi service with **32 handles**:
  `createService(BLEUUID(WIFI_SVC), 32)`. The library default is 15. This
  service needs 17 (seven characteristics, notify descriptors on status and
  scan). At 15 the scan characteristic is never published, WS Connect sets
  `scanSupported` false, and the page shows “Scan unavailable on this
  firmware” while the other Wi-Fi characteristics still appear

### Bluetooth

State both modes. This chip is **not** BLE-only (that limit belongs to the
ESP32-S3 boards in this project). It is Bluetooth 4.2:

- Low Energy: advertising, GATT server or client, BLE HID if implemented
- Classic: SPP and classic HID if the firmware enables them

The factory image is a BLE notify server named `Atom-BLE-Test` using the
Arduino BLE library (Bluedroid). It does not demonstrate Classic.

There is no Bluetooth 5 2M PHY or coded PHY on this SoC.

### USB and flash

Upload and logs go through the UART bridge. The board cannot be a native USB
device. Always detect `/dev/cu.usbserial*`. Use 115200 on this unit. Preserve
the full-flash backup before any write. Partition layout of the current image
is in the factory programming spec (`app0` is a 3 MB ota_0 slot).

### Power

No internal battery. Sleep matters for heat and for an external 5 V pack, not
for a built-in cell. Do not design an always-on portable product without adding
power hardware.

### Accessories

Grove and the extra pads are optional. Never describe a buzzer, relay, sensor,
or battery as built in.

## Programming Platforms

```text
Arduino FQBN:  esp32:esp32:m5stack_atom
PlatformIO:    board = m5stack-atom
ESP-IDF:       idf.py set-target esp32
Library:       M5Unified
Serial:        115200
```

```yaml
matrix: M5.Display
button: M5.BtnA
imu: M5.Imu
refresh: M5.update()
```

## Recommended Software Architecture

1. `M5.begin()`, then `M5.update()` every loop.
2. Keep a small state (mode, colour, connection).
3. Redraw only pixels that changed. Cap brightness.
4. Do network work in short slices so the button and IMU stay responsive.
5. Store only settings that must survive reset (NVS).
6. If an external 5 V pack is added, dim the matrix and sleep when idle.

## Suitable Application Ideas

- One-button BLE remote or presence tag
- Tilt or shake control with colour feedback
- Infrared remote for a TV or air conditioner
- Wi-Fi status beacon (a few pixels for connected / error)
- Factory-style self test: IMU numbers on serial, matrix shows pass or fail
- Grove sensor node with the matrix as the indicator

## Limitation Checklist

- ESP32-PICO-D4, not ESP32-S3. Target `esp32` / `m5stack-atom`.
- Bluetooth 4.2 Classic and BLE. Not BLE-only, and not Bluetooth 5.
- Wi-Fi 2.4 GHz only.
- 5×5 RGB matrix. Brightness stays low.
- One face button. Side control is reset.
- BMI270 expected on this v1.1 unit. Confirm chip ID. No compass.
- IR transmit only. GPIO12 is a strap pin.
- 4 MB flash, no PSRAM, 520 KB SRAM.
- No battery, speaker, microphone, RTC, RFID, or pixel panel.
- USB-UART at 115200 on this unit. No native USB gadget mode.
- Factory app is still in flash. Back up before replacing it. The backup
  already exists; do not erase it.

## How the AI Should Respond

- Say what the cube can do before discussing pins.
- Call this board ATOM Matrix v1.1 when talking about the connected unit.
- Call Bluetooth by the mode in use. If the user says "Bluetooth" without a
  mode, BLE is the usual choice, and Classic is available when they need SPP
  or classic HID.
- Keep LED designs inside 25 pixels and a low brightness.
- Treat Grove modules and batteries as add-ons.
- Do not search for facts already stated here.
- Before any flash: confirm the port, confirm the backup SHA-256, build for
  ESP32 rather than ESP32-S3, upload at 115200.
- Do not describe factory LED or button behaviour beyond the factory specs.
  Those two were not recovered from the image.

## Local Device and Recovery

```yaml
device: M5Stack ATOM Matrix v1.1
sku_string_in_app: C008-B-V11
connected_chip: ESP32-PICO-D4 revision v1.1
device_mac: c8:85:41:68:92:14
flash_size: 4 MB
psram: none
last_port: /dev/cu.usbserial-81524AF84F
upload_baud: 115200
full_flash_backup: backup/atom-matrix-full-flash-2026-09-24.bin
backup_checksum: backup/SHA256SUMS
factory_human: Factory M5AtomMatrix_App_Functional Specificaton.md
factory_ai: Factory M5AtomMatrix_App_Programming Specificaton (AI).md
```

## Document Reference Locations

- This file: `M5AtomMatrix_AI_Specification.md`
- Human features: `M5AtomMatrix_Functional Specification.md`
- Design: `M5AtomMatrix_ClaudeDesign_Specification.md`
- Factory app: `Factory M5AtomMatrix_App_Functional Specificaton.md`
- Factory contract: `Factory M5AtomMatrix_App_Programming Specificaton (AI).md`
- Log: `M5AtomMatrix_Development Log.log`
- Backup: `backup/README.md`

Official:

- https://docs.m5stack.com/en/core/Atom-Matrix_v1.1
- https://docs.m5stack.com/en/core/ATOM%20Matrix
- https://github.com/m5stack/m5-docs/blob/master/docs/en/core/atom_matrix.md
- https://github.com/m5stack/M5Unified

Reference review date: 2026-09-24.
