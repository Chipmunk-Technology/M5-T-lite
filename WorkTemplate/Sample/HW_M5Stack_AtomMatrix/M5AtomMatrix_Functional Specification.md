# M5Stack ATOM Matrix v1.1 Functional Specification

## Purpose

The ATOM Matrix is a 24 mm programmable cube. Its value is a 5×5 colour LED
face, one button under that face, a six-axis motion sensor, an infrared
transmitter, 2.4 GHz Wi-Fi, and Bluetooth, in a device that is powered from
USB-C.

This document describes what software can make the board do. It avoids wiring
detail except where a wrong assumption would damage the LEDs or target the
wrong product.

## This Unit

Status as of 2026-09-24:

| Fact | Evidence |
|---|---|
| ESP32-PICO-D4, revision v1.1 | `DEVICE VERIFIED` (`flash-id`) |
| 4 MB flash, no PSRAM | `DEVICE VERIFIED` |
| MAC `c8:85:41:68:92:14` | `DEVICE VERIFIED` |
| USB serial `/dev/cu.usbserial-81524AF84F`, product name `M5stack` | `DEVICE VERIFIED` |
| Full 4 MB backup, SHA-256 checked | `DEVICE VERIFIED` |
| Running app prints `C008-B-V11` and `Atom Matrix Factory test` | `PARTIAL` (read from the image, not from a live serial log) |
| SKU C008-B-V11 is ATOM Matrix v1.1 with a BMI270 | `DOCUMENTED` (current M5Stack v1.1 page). Chip ID not read yet |
| LED patterns, button gestures, infrared output | `DOCUMENTED` as hardware. Not yet watched on this unit |

The earlier ATOM Matrix (SKU C008 / C008-B) uses an MPU6886. v1.1 uses a
BMI270 at the same I²C address. Software written for the MPU6886 register map
does not apply to this unit until an ID read says otherwise. M5Unified selects
the driver for the board it detects; the older M5Atom `MPU6886` examples do not.

The application currently in flash is specified separately in
`Factory M5AtomMatrix_App_Functional Specificaton.md`.

## Device Summary

- ESP32-PICO-D4, Xtensa LX6 dual-core up to 240 MHz, 520 KB SRAM, 4 MB flash
- 5×5 RGB LED matrix (25× WS2812C-2020) behind an acrylic window
- One programmable button under the matrix, plus a side reset control
- Six-axis IMU: 3-axis accelerometer and 3-axis gyroscope (v1.1: BMI270, I²C 0x68)
- Infrared transmitter
- 2.4 GHz Wi-Fi (802.11 b/g/n)
- Bluetooth 4.2 Classic and Bluetooth Low Energy
- USB-C through a USB-UART bridge (documented as FTDI) for power, upload, and serial
- One Grove port (power, plus two signal pins that firmware can use as GPIO, I²C, or UART)
- Pads that bring out extra GPIO
- Plastic case, about 24.0 × 24.0 × 13.9 mm, about 7.3 g
- Supply 5 V at up to 500 mA. v1.1 page lists a consumption figure of 5 V at 61.65 mA
- No internal battery, no speaker, no microphone, no display panel, no RFID, no real-time clock

## Programmable Features

### 5×5 Colour Matrix

Programs can light each of the 25 pixels in its own colour and change them
tens of times per second. Useful results are icons, one 5×5 character at a
time, a scrolling glyph, a level bar, a few status pixels, and short colour
animations.

The matrix cannot show a sentence, a photo, a menu of labels, or a chart with
axes. Information has to be colour, position, and motion.

Brightness is a hardware limit, not only a style choice. Official guidance for
FastLED is a brightness near 20 on a 0–255 scale. The M5Atom display helper
maps a 0–100 range and its default field is 40 on the 0–255 scale. Full white
on all 25 pixels runs hot and can damage the LEDs and the acrylic. Keep the
level at or below that default until a test on this unit sets a verified cap.

### Face Button

The front face is one button. Software can treat a press as click, double-click,
multi-click, or press-and-hold. The side control is reset, not a second
application button.

### Motion

Software can read acceleration and rotation, derive tilt against gravity, and
detect shakes or taps that the program defines. v1.1's BMI270 is the sensor
the product page names for this SKU. There is no magnetometer, so the board
does not provide a compass heading. Die temperature from the IMU is not an
air-temperature reading.

### Infrared Transmit

Software can emit infrared remote patterns (consumer protocols such as NEC are
implemented in software on the IR LED). The board has a transmitter. It does
not have an infrared receiver, so it cannot learn a code by listening.

### Wi-Fi

The device joins 2.4 GHz networks. Software can use HTTP, WebSocket, MQTT,
NTP, a small local web server, and over-the-air update logic when that logic
is written. There is no 5 GHz radio. Credentials and reconnection are the
application's job. Continuous Wi-Fi raises power use and heat.

**Wi-Fi scan is a default.** The ESP32-PICO-D4 lists nearby 2.4 GHz networks
the same way a Stick or a tablet does. Scan stays on for the ATOM Matrix.
The 5×5 face cannot show network names, so the phone asks the cube to scan
and the cube sends the list back.

`firmware/M5StackConnect/M5StackConnect.ino` publishes that scan on the Wi-Fi
setup service `a5c10000-7c3a-4b2e-9f10-6d0a4d13a001`, characteristic
`a5c10007-7c3a-4b2e-9f10-6d0a4d13a001` (write, read, and notify). The phone
writes the word `scan`. The cube replies on the same characteristic with

`{"networks":[{"ssid","rssi","secure"}]}`

`ssid` is the name, `rssi` is the signal in dBm, and `secure` is true when
the network asks for a password. The list does not include the channel, the
BSSID, or any password. Empty names are skipped. At most six networks are
returned, and the JSON stops near 140 characters so it fits in one Bluetooth
value. Before a scan, the value is `{"networks":[]}`.

WS Connect shows a **Nearby networks** section and a **Scan nearby networks**
button only when that characteristic is present. The button sits under
**Send networks over Bluetooth** and above **IP address**. Tapping a row fills
the Wi-Fi name. The phone waits up to 12 seconds, then reads the
characteristic if the notify is not valid JSON. If the characteristic is
missing, the button is hidden and the page says “Scan unavailable on this
firmware. Type the network name.”

That characteristic is the seventh on the Wi-Fi service. The Arduino BLE
library gives a new service 15 handles, which is not enough for seven
characteristics when two of them notify. The sketch must create this service
with 32 handles. With the default of 15, scan is missing, the other Wi-Fi
fields still appear, and the phone hides the button.

The factory test image also scans at startup and prints a serial table while
looking for `M5Stack-Production`. That is DF-01 in the factory programming
contract. It is not the phone scan.

After a sketch update that adds the scan characteristic, an iPhone can keep
the previous service list. Disconnect, and if the unavailable line remains,
toggle Bluetooth on the phone and connect again.

### Bluetooth

The ESP32-PICO-D4 provides Bluetooth 4.2 Classic and Bluetooth Low Energy.

Software can:

- Advertise as a BLE peripheral, or scan and connect as a central
- Expose custom GATT services
- Act as a BLE HID device when that profile is implemented
- Use Bluetooth Classic profiles that the firmware implements, including
  classic serial (SPP) and classic HID

The factory image on this unit uses BLE only. Classic support is a chip
capability, present when the firmware enables it. This is Bluetooth 4.2, not
Bluetooth 5: 2M PHY and coded PHY are not part of this chip.

### USB

USB-C supplies power and a serial port for logs and upload. The port name on
this Mac was `/dev/cu.usbserial-81524AF84F` and will change. This SoC has no
native USB device controller, so the board cannot become a USB keyboard or
USB disk. The bridge on this unit failed a flash read at 460800 baud and
succeeded at 115200.

Flashing replaces `app0`. The 2026-09-24 full-flash backup is the recovery image.

### Power and Sleep

The cube runs while USB power is present. It has no internal cell, so unplugging
USB turns it off unless an external 5 V source is wired in. ESP32 deep sleep is
available to cut current and LED heat on an external supply. The face button
and a timer are the wake sources to plan for. There is no battery-life target
on the stock board because there is no battery.

### Expansion

The Grove port and the extra pads can host sensors, a buzzer, a relay, or
other modules. Those parts are accessories. They are not on the board.

## Types of Applications

Fitting uses are a status beacon, a one-button remote, a tilt or shake control,
an infrared remote, a BLE presence tag, and a small Wi-Fi sensor node. The
5×5 face is feedback, not a control panel.

Poor fits are anything that needs readable paragraphs, audio, a clock that
survives power loss, or operation away from a 5 V cable without an added supply.

## Programming Platforms

- Arduino IDE and PlatformIO, board `m5stack-atom` / `esp32:esp32:m5stack_atom`
- ESP-IDF, target `esp32`
- UIFlow 1 and UIFlow 2
- M5Unified is the library the official v1.1 PlatformIO snippet uses, and it is
  the library linked in this unit's factory image

Arduino objects when using M5Unified:

| Function | Object |
|---|---|
| Matrix | `M5.Display` |
| Button | `M5.BtnA` |
| Motion | `M5.Imu` |
| Refresh inputs | `M5.update()` |

Interactive sketches should call `M5.update()` often and avoid long blocking
delays. Keep LED brightness low.

## Main Limitations

- 25 RGB pixels. No text layout beyond a single glyph or a scroll of glyphs.
- One application button.
- Bluetooth 4.2, Classic and Low Energy. Not Bluetooth 5.
- Wi-Fi is 2.4 GHz only.
- Infrared transmit only.
- Motion is accel and gyro. No compass.
- IMU on this SKU is the v1.1 BMI270. Confirm the chip ID before using MPU6886 code.
- 4 MB flash and 520 KB SRAM. No PSRAM.
- No battery, speaker, microphone, RTC, RFID, camera, or pixel display.
- High LED brightness can damage the face.
- USB serial on this unit should be used at 115200.
- Only one application image is the running program. The backup restores the
  factory test.

## Local Recovery

- Image: `backup/atom-matrix-full-flash-2026-09-24.bin`
- Checksum: `backup/SHA256SUMS`
- Steps: `backup/README.md`

## Document Reference Locations

- This file: `M5AtomMatrix_Functional Specification.md`
- AI reference: `M5AtomMatrix_AI_Specification.md`
- Design reference: `M5AtomMatrix_ClaudeDesign_Specification.md`
- Factory app: `Factory M5AtomMatrix_App_Functional Specificaton.md`
- Factory programming contract: `Factory M5AtomMatrix_App_Programming Specificaton (AI).md`
- Log: `M5AtomMatrix_Development Log.log`
- Handoff: `NextSteps.md`

Official references:

- v1.1 product page (SKU C008-B-V11): https://docs.m5stack.com/en/core/Atom-Matrix_v1.1
- Product page: https://docs.m5stack.com/en/core/ATOM%20Matrix
- Docs source: https://github.com/m5stack/m5-docs/blob/master/docs/en/core/atom_matrix.md
- M5Unified: https://github.com/m5stack/M5Unified
- ESP32-PICO-D4 datasheet (linked from the M5Stack page)

Reference review date: 2026-09-24.
