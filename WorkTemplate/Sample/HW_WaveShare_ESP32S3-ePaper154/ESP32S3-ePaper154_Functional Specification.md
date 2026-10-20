# WaveShare ESP32-S3-ePaper-1.54 Functional Specification

## Purpose

The WaveShare ESP32-S3-ePaper-1.54 is a small, battery-capable development board
built around an ESP32-S3. Its main value is the combination of a 1.54-inch
black-and-white electronic-paper display with Wi-Fi, Bluetooth Low Energy,
on-board sensors (temperature/humidity and a real-time clock), an audio codec
with microphone and speaker output, a micro-SD slot, and a lithium-battery power
path — all on one programmable board.

This document focuses on what software can make the device do. It avoids
low-level wiring and pin detail. Hardware facts here are **DOCUMENTED** from the
official product page and datasheets (review dates 2026-06-28 / 2026-06-29).
Programmable behavior will be promoted to device-verified as each feature is
tested on the connected board (see the Development Log).

> **This unit (DEVICE VERIFIED 2026-06-29):** ESP32-S3-PICO-1 (LGA56) rev v0.2,
> hardware version **V2** — 8 MB flash + 8 MB PSRAM — MAC `ac:27:6e:d2:07:28`,
> native USB-Serial/JTAG. A full-flash backup has been taken and verified.
>
> The product line also includes a **non-touch / touch** split and a battery /
> `-EN` no-battery split, plus an older **V1** (4 MB flash / 2 MB PSRAM). For
> this unit, V1-vs-V2 is settled (V2); whether it has capacitive touch (FT6336)
> and a battery still needs visual confirmation. Capacitive touch applies only to
> the touch variant.

## Device Summary

The board provides:

- 1.54-inch electronic-paper (e-paper) display, 200 × 200 pixels, black/white
- ESP32-S3 dual-core processor; flash/PSRAM depend on hardware version —
  **V1: 4 MB flash / 2 MB PSRAM**, **V2: 8 MB flash / 8 MB PSRAM**
  (*this unit is V2: 8 MB / 8 MB*)
- 2.4 GHz Wi-Fi
- Bluetooth 5 Low Energy
- PWR button and BOOT button
- Capacitive touch on the touch variant (FT6336)
- SHTC3 temperature and humidity sensor
- PCF85063 real-time clock
- ES8311 audio codec with on-board microphone and speaker connector
- Micro-SD card slot (FAT32)
- USB-C for programming, serial, and power
- 3.7 V lithium-battery connector with on-board charge/discharge management
- Two 6-pin expansion headers (2.54 mm) exposing GPIO, UART, and I²C

## Programmable Features

### Electronic-Paper Display

The 200 × 200 black-and-white e-paper screen holds its image with no power and is
highly readable in reflected light.

Programs can:

- Draw text, icons, shapes, images, QR codes, simple charts, and dashboards
- Use a **full refresh** for a clean image (about 2 seconds, with visible flashing)
- Use a **partial refresh** to update a region quickly (about 0.3 seconds)
- Keep the last image on screen with the power off (bistable display)

Display limitations:

- Black and white only (no color; effectively two levels). Grayscale, where a
  panel supports it, is limited and slow.
- Refresh is far slower than an LCD. It suits status, text, and occasional
  updates, not animation or video.
- Frequent partial refreshes cause **ghosting**; a periodic full refresh clears it.
- Best for content that changes seconds-to-minutes apart, not many times a second.

### Buttons

The board has a **PWR** button and a **BOOT** button.

- BOOT is primarily used to enter firmware download mode (hold BOOT, tap
  RESET/PWR, release BOOT).
- Both buttons can be read by firmware as user inputs (for example short press,
  long press, or wake-from-sleep), with the exact behavior defined in software.

There is no rotary encoder and no RFID reader on this board.

### Touch Screen (touch variant only)

On the touch variant, the FT6336 capacitive controller (over I²C) reports touch
position and release. Programs can implement taps, holds, and simple gestures on
top of the e-paper image. Because the display refreshes slowly, touch feedback
should update small regions with partial refresh rather than redrawing the whole
screen.

### Wi-Fi

The device connects to 2.4 GHz Wi-Fi networks.

Software can use Wi-Fi to:

- Call web APIs and send/receive HTTP/HTTPS requests
- Run a small local web server
- Publish and subscribe using MQTT
- Integrate with Home Assistant or custom smart-home systems
- Synchronize time from an NTP server (and set the on-board RTC)
- Download settings, images, or firmware updates
- Send sensor, status, or user data to another computer; receive commands
- Support over-the-air firmware updates when implemented

Wi-Fi behavior is not automatic: credentials, security, server addresses, and
application logic must be programmed. There is no 5 GHz Wi-Fi.

### Bluetooth Low Energy

The ESP32-S3 supports Bluetooth 5 Low Energy (BLE).

Software can make the board operate as:

- A BLE peripheral controlled by a phone or computer
- A BLE sensor/status server (temperature, humidity, time, battery)
- A BLE HID-style device when implemented
- A beacon or information broadcaster
- A client that scans for and connects to compatible BLE peripherals
- A configuration interface for Wi-Fi credentials or device settings
- A bridge between BLE input and Wi-Fi services

BLE services, characteristics, pairing, security, and companion software must be
designed for the application. **Bluetooth is BLE only**: no Bluetooth Classic
audio (A2DP) and no classic SPP serial.

### Temperature and Humidity Sensor (SHTC3)

The on-board SHTC3 sensor measures ambient temperature and relative humidity over
I²C. Programs can display readings, log them to SD, send them over Wi-Fi/BLE, or
trigger thresholds. It measures the board's surroundings; self-heating and
enclosure design affect accuracy.

### Real-Time Clock (PCF85063)

The on-board PCF85063 RTC keeps date and time and can run with low power.

Programs can:

- Display clocks, calendars, alarms, and countdowns
- Synchronize time over Wi-Fi (NTP) and store it in the RTC
- Trigger alarms and scheduled actions
- Wake the system from sleep at a set time or interval
- Timestamp readings and events

### Audio (ES8311 codec, microphone, speaker)

The board includes an ES8311 audio codec with an on-board microphone and a
2-pin (MX1.25) speaker connector.

Programs can capture audio from the microphone and play audio to a connected
speaker (for example tones, alerts, recorded clips, or simple sound playback),
subject to ESP32-S3 memory and processing limits. High-fidelity or long-form
audio is constrained by storage and RAM; use SD streaming where needed.

### Micro-SD Storage

A micro-SD slot (FAT32) provides removable storage for images, fonts, logs,
audio, configuration, or downloaded assets. SD contents are separate from the
device flash and must be backed up separately by copying files from the card.

### USB

USB-C can be used for:

- Uploading firmware
- Reading program logs and serial debugging
- Sending commands or data between the board and a computer
- Firmware-defined USB device behavior supported by the ESP32-S3

Installing new firmware replaces the application currently in flash. This project
keeps a complete flash backup in `backup/` for recovery.

### Battery, Sleep, and Wake

The board has a 3.7 V lithium-battery connector and on-board charge/discharge
management, so it can run untethered.

**Battery power-hold (important for untethered operation):** the board uses a
power-hold latch. To keep running on battery, the firmware must assert the
battery power-enable (`VBAT_POWER_ON`, GPIO17 high) — normally as the first thing
at boot. While USB is connected the board is powered regardless, so this only
matters when USB is unplugged: if the latch is not asserted, removing USB cuts
power instantly (the board dies and the e-paper may not even retain a static
image). DEVICE-VERIFIED behavior 2026-06-29: firmware that omits this dies on
unplug; the factory firmware asserts it and keeps running.

Software can reduce power by entering light or deep sleep and waking from a
timer, the RTC alarm, or a button. The e-paper display keeps its last *fully
refreshed* image with no power, which makes "show status, then sleep" designs
very efficient; an abrupt power cut mid-refresh can prevent a clean retained
image. Wi-Fi, BLE, audio, sensor polling, and frequent full refreshes increase
power use.

**Battery life is a design choice — decide it up front.** How long the device
runs on a charge depends almost entirely on the firmware, so the intended runtime
should be agreed before building battery firmware. On this board's small LiPo:

- **Always-on** (CPU never sleeps, BLE advertising continuously): only **~3–8
  hours**. An on-screen "BT off" usually means *no client connected* — the BLE
  radio may still be advertising and draining power.
- **Low-power "frame"** (deep sleep between updates, wake on a timer/touch/button,
  BLE only on demand): **weeks to months** per charge.
- **Middle ground** (slower advertising + light sleep): **~1–2 days**.

For a desk/wall display that shows status and occasionally updates, the low-power
frame approach is strongly preferred.

USB-powered sleep consumes more than battery-only sleep because of the USB power
path.

### Expansion

Two 6-pin headers (2.54 mm) expose GPIO, UART, and I²C. Programs can communicate
with compatible external sensors, buttons, displays, or modules when the correct
accessory and driver are used. High-current loads, motors, relays, or mains
switching require suitable external rated hardware.

## Types of Applications

### Standalone

- E-paper clock, calendar, or countdown using the on-board RTC
- Room temperature/humidity display that updates every few minutes and sleeps
- Battery-powered status badge or name tag (bistable image, near-zero idle power)
- Image/QR display loaded from SD
- Simple data logger writing sensor readings to SD with timestamps
- Audio note recorder / alert beeper

### Connected

- Wi-Fi weather or smart-home status panel
- Home Assistant / MQTT status display
- Remote API status board (CI, prices, queues) refreshed periodically
- BLE sensor that reports temperature, humidity, and battery to a phone
- Wi-Fi/BLE provisioning and configuration device

### Combined Interaction Examples

- On wake from the RTC, read SHTC3, refresh the e-paper status, then sleep.
- Fetch data over Wi-Fi every N minutes, partial-refresh the changed numbers,
  full-refresh occasionally to clear ghosting, and sleep between updates.
- Record a short audio note, store it to SD, and show a confirmation on screen.
- (Touch variant) Tap a region to switch between clock, weather, and sensor
  pages, updating only that region.

## Programming Platforms

The board can be programmed with:

- Arduino IDE (ESP32-S3 board support; e-paper via GxEPD2 or WaveShare's driver)
- PlatformIO
- ESP-IDF
- MicroPython

Arduino is usually the simplest choice for custom firmware. ESP-IDF offers the
most control. The e-paper panel, RTC, sensor, touch controller, and audio codec
each need their respective driver library.

## Main Limitations

- The display is **black and white**, 200 × 200, and refreshes slowly
  (~2 s full, ~0.3 s partial); it is unsuitable for animation, video, or fast UI.
- Frequent partial refreshes cause ghosting that needs periodic full refresh.
- Bluetooth is **BLE only**; no Bluetooth Classic.
- Wi-Fi is **2.4 GHz only**, not 5 GHz.
- There is **no rotary encoder and no RFID** on this board.
- Touch exists **only on the touch variant** (FT6336).
- Audio is constrained by microcontroller memory and storage; not a hi-fi system.
- Limited flash (V1 4 MB / V2 8 MB) and microcontroller-scale RAM (V1 2 MB /
  V2 8 MB PSRAM) make large media, complex web apps, and heavy on-device AI
  unsuitable.
- No built-in camera, GPS, cellular modem, or Ethernet.
- Internet, cloud, Home Assistant, MQTT, BLE, and OTA behavior must be implemented.
- High-voltage, high-current, relay, and motor control need external hardware.
- Battery life depends heavily on refresh frequency, Wi-Fi/BLE/audio use, and
  sleep design.
- Installing new firmware replaces the current application unless a custom
  multi-app design is built.

## Local Recovery Information

- Backup tooling and procedure: `backup/README.md`, `backup/backup_device.sh`
- Full flash backup: `backup/esp32s3-epaper154-full-flash-2026-06-29.bin`
  (8,388,608 bytes, **taken and verified 2026-06-29**)
- Backup checksum: `backup/SHA256SUMS`
- This unit is confirmed **V2** (8 MB flash / 8 MB PSRAM), ESP32-S3-PICO-1,
  MAC `ac:27:6e:d2:07:28`. Touch/non-touch and battery/-EN still need visual
  confirmation.

## Document Reference Locations

Local documents:

- Human reference: `ESP32S3-ePaper154_Functional Specification.md`
- AI reference: `ESP32S3-ePaper154_AI_Specification.md`
- Claude Design reference: `ESP32S3-ePaper154_ClaudeDesign_Specification.md`
- Development history: `ESP32S3-ePaper154_Development Log.log`
- Factory firmware (human): `Factory ESP32S3-ePaper154_App_Functional Specificaton.md`
- Factory firmware (AI): `Factory ESP32S3-ePaper154_App_Programming Specificaton (AI).md`
- Method: `Make Spec.md`
- Project rules: `Project instruction.md`
- Firmware recovery: `backup/README.md`
- Reference example specs (M5Stack Dial): `Sample/`

Official references (review dates 2026-06-28 / 2026-06-29):

- Product page: https://www.waveshare.net/shop/ESP32-S3-ePaper-1.54.htm
- Official documentation (all SKUs + V1/V2):
  https://docs.waveshare.net/ESP32-S3-ePaper-1.54/?variant=ESP32-S3-Touch-ePaper-1.54
- Wiki (V2, non-touch): https://www.waveshare.net/wiki/ESP32-S3-ePaper-1.54-V2
- WaveShare wiki and resources: https://www.waveshare.net/wiki/
- ESP32-S3 datasheet: https://www.espressif.com/documentation/esp32-s3_datasheet_en.pdf
- ESP32-S3 BLE programming guide:
  https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/ble/overview.html
