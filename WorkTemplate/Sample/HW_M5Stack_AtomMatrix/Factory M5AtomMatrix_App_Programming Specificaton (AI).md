# Factory ATOM Matrix App Programming Specification (AI)

## 1. Purpose and Required Result

This is the programming contract for recreating the application found on the
backed-up ATOM Matrix. The paired human document is
`Factory M5AtomMatrix_App_Functional Specificaton.md`. Both describe the same
behaviour. If a behaviour is added, removed, renamed, or corrected, update
both files together.

An implementation shall be a buildable Arduino firmware for board
`m5stack-atom` that reproduces the serial text, Wi-Fi target, IMU test, and
BLE server defined here. Pixel patterns, button gestures, and infrared output
are **out of contract** until a live observation adds them. Do not invent
those behaviours to make the demo look complete.

**Replication target**

- Product: M5Stack ATOM Matrix v1.1, SKU string `C008-B-V11`
- SoC: ESP32-PICO-D4, dual-core LX6, 4 MB flash, no PSRAM
- This unit: revision v1.1, MAC `c8:85:41:68:92:14`
- Face: 5×5 WS2812C matrix. Driver library is present (M5GFX). Drawn content
  is unknown.
- Motion: M5Unified IMU init. SKU page specifies BMI270 at I²C 0x68. Chip ID
  not yet read.
- Radios: 2.4 GHz Wi-Fi scan and join; BLE notify server
- Application title: `Atom Matrix Factory test`
- Toolchain evidence: PlatformIO, `framework-arduinoespressif32`, ESP-IDF
  **v4.4.7**, M5Unified, Arduino `BLEUUID` library (Bluedroid, not NimBLE)
- **Evidence status: `PARTIAL`**

"Same" means the same serial messages, the same Wi-Fi SSID, the same BLE
name, UUIDs, and notify payload. A byte-identical image would need the
original sketch, the same core build (`38eeba213a`, Mar 5 2024), and the same
compiler. The app descriptor project name `arduino-lib-builder` is the core's
default stamp; a reproduction does not need to forge that stamp.

## 2. Feature Synchronization IDs

| ID | Feature |
|---|---|
| DF-00 | Boot identity: `Atom Matrix Factory test` and `C008-B-V11` |
| DF-01 | Wi-Fi scan table and join of `M5Stack-Production` |
| DF-02 | IMU init and three-float print |
| DF-03 | BLE server `Atom-BLE-Test` with the Neil Kolban notify UUIDs |
| DF-04 | LED matrix — library linked, pixels not specified |
| DF-05 | Face button — hardware exists, factory action not recovered |
| DF-06 | Infrared — not recovered; do not add it |

## 3. Toolchain and Build Contract

Closest reproduction baseline:

- PlatformIO board `m5stack-atom` (Arduino-ESP32 for the original ESP32, not ESP32-S3)
- ESP-IDF **4.4.7** underneath that Arduino core (the descriptor version)
- Library: `M5Unified` (pulls M5GFX)
- BLE: Arduino `BLEDevice` / `BLEServer` / `BLECharacteristic`, not NimBLE-Arduino
- Serial monitor: **115200**
- Upload baud on this unit: **115200**. 460800 failed during the backup read.
- Flash size: 4 MB

Partition table recovered from the image (single OTA slot, empty SPIFFS):

~~~csv
# Name,     Type, SubType, Offset,   Size
nvs,        data, nvs,     0x9000,   0x5000,
otadata,    data, ota,     0xe000,   0x2000,
app0,       app,  ota_0,   0x10000,  0x300000,
spiffs,     data, spiffs,  0x310000, 0xE0000,
coredump,   data, coredump,0x3F0000, 0x10000,
~~~

The SPIFFS partition in the backup is erased (`0xFF`). A reproduction must not
require files from it.

Do not target `esp32s3`. Do not enable PSRAM.

## 4. Bus and Peripheral Map

Taken from the official v1.1 pin map (the SKU this image names). The factory
strings do not list GPIO numbers.

| Function | Connection |
|---|---|
| 25× WS2812C | GPIO27, data |
| Face button | GPIO39, active low, input-only |
| IR transmit | GPIO12 |
| IMU (BMI270 on the v1.1 page) | I²C address 0x68, SCL GPIO21, SDA GPIO25 |
| Grove PORT.CUSTOM | GND, 5V, GPIO26 (yellow), GPIO32 (white) |

M5Unified is the library this image actually links. Prefer `M5.begin()` and
`M5.Imu` over the older M5Atom `MPU6886` class, which matches the pre-v1.1 board.

GPIO12 is an ESP32 strapping pin (flash voltage). This unit's `flash_id`
reported "Flash voltage set by a strapping pin: 3.3V". Do not hold GPIO12
during reset.

## 5. Feature Behaviour Contract

### DF-00 — Identity

On startup, print:

- `Atom Matrix Factory test`
- `C008-B-V11`

Serial rate 115200.

### DF-01 — Wi-Fi

**Default: scan is on.** This board scans 2.4 GHz networks the same way an
M5Stick or a tablet does. The factory image scans at startup, with no extra
command and no menu. A reproduction must scan. Leaving scan out is not a
valid ATOM Matrix default.

The replacement provisioning sketch
`firmware/M5StackConnect/M5StackConnect.ino` keeps that default. Scan is a
normal characteristic, not an option omitted on this product:

- Service `a5c10000-7c3a-4b2e-9f10-6d0a4d13a001`
- Scan characteristic `a5c10007-7c3a-4b2e-9f10-6d0a4d13a001` (write, read, notify)
- Write UTF-8 `scan`
- Result `{"networks":[{"ssid","rssi","secure"}]}`

The factory test below is a different caller of the same radio. It prints a
serial table and then tries `M5Stack-Production`. It does not replace the
default that scan itself is available.

Scan and print every network in this form:

```text
Scanning WiFi...
ID | RSSI | CH | BSSID             | SSID
----------------------------------------------
%2d | %4d | %2d | %s | %s
```

If the scan is empty, print `No networks found.` Otherwise print
`% d networks found` (the format string in the image has a space after `%`).

Search the results for SSID `M5Stack-Production`.

- If one or more matches exist, print
  `Found matching SSID: %s, RSSI: %d, BSSID: %s` and
  `Connecting to strongest AP: %d dBm on channel %d`, then join the strongest
  match.
- If none exist, print
  `Target SSID not found in scan, trying default connection...`
  and still attempt the same SSID.
- Password in the image: `m5stack1234`
- On success print `IP: %s`
- Also print `wifi ssid: %s` and `password: %s`

This credential is the factory test network inside the backed-up image. Do not
copy it into an unrelated sketch as if it were a user network.

### DF-02 — IMU

Print `Into IMU test`. Initialise the IMU through M5Unified.

- Success: `IMU init OK`
- Failure: `IMU init failed`
- Print three floating values with `%0.2f %0.2f %0.2f`

The image does not say whether those three numbers are acceleration, gyro, or
attitude. Keep the format. Label the physical meaning only after a serial trace
shows the values moving in a known way.

### DF-03 — BLE server

Print `ble server mode`, then `Starting BLE work!`.

- Device name: `Atom-BLE-Test`
- Service: `4fafc201-1fb5-459e-8fcc-c5c9c331914b`
- Characteristic: `beb5483e-36e1-4688-b7f5-ea07361b26a8` (read + notify)
- Notify payload: `Hello World says Neil`
- Print `Waiting a client connection to notify...`
- Print `start advertising` and advertise

Use the Arduino BLE library. A client that connects and subscribes should
receive that hello string. No pairing scheme was recovered; do not add one.

### DF-04 — LED matrix

Link a matrix driver (M5GFX via M5Unified, brightness kept low). Do not specify
a pixel pattern. Official guidance: FastLED brightness around 20 on a 0–255
scale; high brightness can damage the LEDs and the acrylic. M5Atom's own
display object defaults to brightness 40 on that scale. Stay at or below that
until a live test sets a verified level.

### DF-05 — Button

GPIO39 is the face button. This factory image has no recovered button message.
A reproduction of the **known** factory behaviour does not need a button action.
Add one only after the live device shows what the current firmware does.

### DF-06 — Infrared

Do not transmit IR in the reproduction. No IR string was recovered.

## 6. Acceptance Checklist

- [ ] Builds for `m5stack-atom` / ESP32 (not S3) and fits in the 3 MB `app0` slot
- [ ] Serial 115200 shows `Atom Matrix Factory test` and `C008-B-V11`
- [ ] Scan table header matches the recovered format string
- [ ] SSID sought is `M5Stack-Production`; missing-SSID line matches verbatim
- [ ] IMU prints `IMU init OK` or `IMU init failed` and one `%0.2f %0.2f %0.2f` line
- [ ] BLE advertises as `Atom-BLE-Test` with the two UUIDs above
- [ ] Notify value is `Hello World says Neil`
- [ ] No invented button, IR, or pixel story is presented as factory behaviour
- [ ] The full-flash backup still exists and its SHA-256 checks before this
      image is allowed to replace `app0`

## 7. Recovery

Restore the whole backup at 115200 baud. See `backup/README.md`.
SHA-256: `60987a9476bde5297ebd231649100452e1b0906d6460eb7c8fa959f88e041c57`

## Document Reference Locations

- This file: `Factory M5AtomMatrix_App_Programming Specificaton (AI).md`
- Human factory description: `Factory M5AtomMatrix_App_Functional Specificaton.md`
- Board capabilities: `M5AtomMatrix_AI_Specification.md`
- Log: `M5AtomMatrix_Development Log.log`

Review date: 2026-09-24.
