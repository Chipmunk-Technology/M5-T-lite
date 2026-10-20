# Factory ATOM Matrix App Functional Specification

## Purpose

This document describes the application that was on the connected M5Stack
ATOM Matrix **before any replacement firmware**. It focuses on what that
image is and what it does, and on its practical limits.

The paired programming contract is
`Factory M5AtomMatrix_App_Programming Specificaton (AI).md`. A change to the
described behaviour belongs in both files.

## Evidence Status

Status: `PARTIAL` (binary-derived, not yet run-traced)

How this was determined:

- The complete 4 MB flash was read without writing to the device
  (`backup/atom-matrix-full-flash-2026-09-24.bin`, SHA-256 OK).
- The bootloader at `0x1000` starts with `0xE9`. The partition table at
  `0x8000` starts with `0xAA50`.
- The app descriptor and the printable strings in `app0` were read from that
  image.
- **Not done:** a live serial log, and a look at the 5×5 LED matrix while
  this firmware is running. Anything about screen patterns, button actions,
  or the order of the tests is inferred and stays `PARTIAL` until those
  checks.

## Application Identity

| Field | Value |
|---|---|
| Title string in the image | `Atom Matrix Factory test` |
| Board string in the image | `C008-B-V11` |
| What that SKU is | ATOM Matrix **v1.1** on the current M5Stack product page |
| App descriptor project | `arduino-lib-builder` |
| App descriptor version | `esp-idf: v4.4.7 38eeba213a` |
| App descriptor build stamp | `Mar  5 2024` `12:36:24` |
| ESP-IDF string | `v4.4.7-dirty` |
| How it was built | PlatformIO, board package `m5stack-atom`, library **M5Unified** (and M5GFX), Arduino BLE library. Paths are under `C:/Users/EDY/.platformio/` |
| This unit | ESP32-PICO-D4 revision v1.1, 4 MB flash, MAC `c8:85:41:68:92:14` |

The descriptor project name and date are the **Arduino-ESP32 core** stamp
(IDF 4.4.7). They are not a separate name for the factory sketch. The sketch
identifies itself with the strings `Atom Matrix Factory test` and `C008-B-V11`.

This is a factory hardware test: it scans Wi-Fi, brings up the motion sensor,
and advertises a BLE server. It is not a finished product.

## Flash Layout

Verified from the backup:

| Partition | Type | Offset | Size | Notes |
|---|---|---|---|---|
| `nvs` | data/nvs | 0x009000 | 20 KB | contains data; not decoded |
| `otadata` | data/ota | 0x00E000 | 8 KB | present; only one app slot exists |
| `app0` | app/ota_0 | 0x010000 | 3072 KB | about 1.17 MB used, rest erased `0xFF` |
| `spiffs` | data/spiffs | 0x310000 | 896 KB | entirely erased; no files |
| `coredump` | data/coredump | 0x3F0000 | 64 KB | entirely erased |

There is no second OTA slot. Replacing the application overwrites `app0`.
The SPIFFS region is empty, so this firmware is not serving files from flash.

## What the Firmware Exercises

Recovered from strings and linked libraries. Quoted text is verbatim.

### Wi-Fi

Scanning is the default. The test does not wait for a button or a phone
before it scans. The image scans and prints a network table:

- `Scanning WiFi...`
- `No networks found.`
- `% d networks found`
- `ID | RSSI | CH | BSSID             | SSID`
- `%2d | %4d | %2d | %s | %s`

It looks for the SSID **`M5Stack-Production`**. Related strings:

- `Found matching SSID: %s, RSSI: %d, BSSID: %s`
- `Connecting to strongest AP: %d dBm on channel %d`
- `Target SSID not found in scan, trying default connection...`
- `IP: %s`
- `wifi ssid: %s`
- `password: %s`

The password string stored next to that SSID is **`m5stack1234`**. That is the
factory-floor credential inside this image, not a network this project should
join unless the goal is to reproduce the factory test.

Wi-Fi here is 2.4 GHz, which is all the ESP32-PICO-D4 provides.

### Motion sensor

- `Into IMU test`
- `IMU init OK`
- `IMU init failed`
- a three-value print format `%0.2f %0.2f %0.2f`

M5Unified is linked, and that library selects the IMU driver. The board string
`C008-B-V11` is the v1.1 SKU, whose current product page specifies a **BMI270**
at I²C address 0x68. This image does not contain the text `BMI270` or
`MPU6886`. Treat the chip as BMI270 from the SKU, and confirm with a chip-ID
read before relying on it.

### Bluetooth Low Energy

- `ble server mode`
- `Starting BLE work!`
- advertised name **`Atom-BLE-Test`**
- service UUID `4fafc201-1fb5-459e-8fcc-c5c9c331914b`
- characteristic UUID `beb5483e-36e1-4688-b7f5-ea07361b26a8`
- notify text `Hello World says Neil`
- `Waiting a client connection to notify...`
- `start advertising`

Those UUIDs and the notify text are the stock Arduino ESP32 BLE notify
example. The stack in this image is the Arduino BLE library on the ESP32
Bluedroid controller. NimBLE is not what this image uses.

The chip also supports Bluetooth Classic. This factory app does not show
Classic profiles in its strings.

### LED matrix, button, infrared

M5GFX is linked, so a display driver for the 5×5 matrix is in the image.
No phrase was recovered that says what the matrix draws, how the face button
is used, or whether the infrared LED is driven. The public EasyLoader note
("scrolling text and key count") describes an older published factory demo.
It is **not** evidence for this image. Leave matrix, button, and IR behaviour
unknown until a serial log and the LEDs are watched.

## Inferred User-Visible Behaviour

Inferred from the string group, not from a trace:

- On boot the firmware prints `Atom Matrix Factory test` and `C008-B-V11`.
- It scans 2.4 GHz Wi-Fi, prints the scan table, and tries to join
  `M5Stack-Production`. If that SSID is absent it logs that it is trying a
  default connection, then prints an IP line when it has one.
- It runs an IMU init and prints either `IMU init OK` or `IMU init failed`,
  plus three decimal numbers.
- It starts a BLE server named `Atom-BLE-Test` and waits to notify
  `Hello World says Neil`.

What it is not: there is no recovered cloud, MQTT, or Home Assistant client,
no files in SPIFFS, and no second app slot.

## Limitations of the Factory Firmware

- It is a production test, not an end-user application.
- LED patterns, button actions, and infrared use are not in the recovered text.
- The test Wi-Fi network is a factory SSID. Away from that network the scan
  still runs and the "SSID not found" path is the expected one.
- BLE is a single notify characteristic with a fixed hello string.
- NVS contains data that was not decoded. SPIFFS and the coredump slot are blank.
- Installing another application replaces `app0`. The verified backup is the
  way back.

## How to Confirm the Remaining Details

1. Open the serial port at **115200** and reset the board. Do not flash.
2. Record the real order of the Wi-Fi, IMU, and BLE lines.
3. Watch the 5×5 matrix and press the face button. Write down what changes.
4. Optionally read the IMU chip ID at I²C 0x68.
5. Promote confirmed items to `DEVICE VERIFIED` in this file, the programming
   spec, and the development log.

## Recovery

- Image: `backup/atom-matrix-full-flash-2026-09-24.bin`
- Checksum: `backup/SHA256SUMS`
  (`60987a9476bde5297ebd231649100452e1b0906d6460eb7c8fa959f88e041c57`)
- Procedure: `backup/README.md` (use **115200** baud)

## Document Reference Locations

- This file: `Factory M5AtomMatrix_App_Functional Specificaton.md`
- Programming contract: `Factory M5AtomMatrix_App_Programming Specificaton (AI).md`
- Board capabilities: `M5AtomMatrix_Functional Specification.md`
- AI capability reference: `M5AtomMatrix_AI_Specification.md`
- Design constraints: `M5AtomMatrix_ClaudeDesign_Specification.md`
- Evidence log: `M5AtomMatrix_Development Log.log`
- Method: `../WorkTemplate/Make Spec.md`

Official references:

- ATOM Matrix v1.1 (SKU C008-B-V11): https://docs.m5stack.com/en/core/Atom-Matrix_v1.1
- ATOM Matrix (earlier page): https://docs.m5stack.com/en/core/ATOM%20Matrix
- Source markdown linked by the user: https://github.com/m5stack/m5-docs/blob/master/docs/en/core/atom_matrix.md

Evidence basis: factory image read 2026-09-24 from ESP32-PICO-D4
MAC `c8:85:41:68:92:14`. Review date: 2026-09-24.
