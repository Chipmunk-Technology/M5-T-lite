# WaveShare ESP32-S3-ePaper-1.54 AI Specification

## Purpose

Use this file as the project's primary local knowledge source for discussing,
designing, and programming the WaveShare ESP32-S3-ePaper-1.54.

Focus on software behavior and useful product ideas. Do not burden the user with
pins, buses, or electrical detail unless they explicitly ask about hardware
expansion or low-level troubleshooting.

Do not search the internet for ordinary capability questions already answered
here. Search official sources only when current library details are required,
this file lacks the answer, or the user explicitly asks for online verification.

Hardware facts here are **DOCUMENTED** (official product page + datasheets,
review dates 2026-06-28 / 2026-06-29) unless a line is marked device-verified.
Promote a capability to device-verified only after testing the connected board
per `Make Spec.md`. The connected unit's identity (chip, version, MAC, flash) is
DEVICE VERIFIED — see "Local Device and Recovery" below.

## Device Summary

The WaveShare ESP32-S3-ePaper-1.54 is an ESP32-S3 board with:

- 1.54-inch e-paper display, 200 × 200, black/white, bistable
- ESP32-S3 dual-core LX7 @ 240 MHz; flash/PSRAM by version — **V1: 4 MB / 2 MB**,
  **V2: 8 MB / 8 MB**. *This unit is V2 (8 MB / 8 MB), confirmed by esptool.*
- 2.4 GHz Wi-Fi
- Bluetooth 5 Low Energy
- PWR and BOOT buttons
- Capacitive touch (FT6336) — **touch variant only**
- SHTC3 temperature/humidity sensor
- PCF85063 real-time clock
- ES8311 audio codec, on-board mic, speaker connector (MX1.25)
- Micro-SD slot (FAT32)
- USB-C (programming, serial, power)
- 3.7 V Li-battery connector with charge/discharge management
- Two 6-pin expansion headers (GPIO/UART/I²C)

This board has **no rotary encoder and no RFID**. Always confirm whether a unit
is the **touch** or **non-touch** variant before promising touch.

## Capability Knowledge

### E-Paper Display

Software can draw text, icons, shapes, images, QR codes, simple charts, and
status dashboards on a 200 × 200 black-and-white panel. Two refresh modes:

- Full refresh: clean image, ~2 s, visible flashing — use sparingly.
- Partial refresh: quick regional update, ~0.3 s — use for changing values.

Key facts:

- The display is **bistable**: it holds its image with no power. Ideal for
  "draw, then sleep" designs with near-zero idle power.
- Frequent partial refreshes cause **ghosting**; schedule a periodic full
  refresh to clear it.
- It is black/white only and slow. Do not propose animation, video, smooth
  scrolling, or fast interactive redraws.

Good uses: clocks, calendars, weather/sensor panels, status boards, name tags/
badges, QR display, dashboards that change seconds-to-minutes apart.

### Buttons

PWR and BOOT buttons. BOOT enters firmware download mode (hold BOOT, tap
RESET/PWR, release BOOT). Firmware can also read presses (short, long, wake-from-
sleep) as user input. There is no rotary encoder; navigation must use buttons,
touch (variant), or a remote/web interface.

### Touch (variant only)

On the touch variant, FT6336 over I²C reports position and release for taps,
holds, and simple gestures. Update small regions with partial refresh for
feedback; never full-redraw on every touch.

### Wi-Fi

Software can connect to 2.4 GHz networks; use HTTP, HTTPS, WebSocket, MQTT, NTP,
and custom TCP/UDP; call APIs or run a small local web server; integrate with
Home Assistant; send status and receive commands; download assets; and implement
OTA updates.

Limitations: no 5 GHz; credentials/auth/reconnection/services must be programmed;
continuous Wi-Fi raises power use; long network operations must not block a
refresh in progress.

### Bluetooth Low Energy

Software can advertise as a BLE peripheral; expose custom GATT services/
characteristics; scan and connect to BLE devices; send settings/status; receive
commands; act as a BLE HID device when implemented; broadcast beacons; provision
Wi-Fi credentials; and bridge BLE to Wi-Fi.

Critical limitation: **BLE only** — no Bluetooth Classic, no SPP serial, no A2DP
audio. A BLE feature needs a defined GATT service, a pairing/security design, and
compatible companion software.

### Temperature/Humidity (SHTC3)

Read ambient temperature and relative humidity over I²C; display, log to SD,
report over Wi-Fi/BLE, or threshold. It senses the board's surroundings;
self-heating and enclosure affect accuracy.

### Real-Time Clock (PCF85063)

Keep/display date and time; sync from NTP and store to the RTC; set alarms and
scheduled actions; wake from sleep on a timer or RTC alarm; timestamp events.

### Audio (ES8311 + mic + speaker connector)

Capture from the on-board microphone and play to a connected speaker — tones,
alerts, short recorded clips, or simple playback. Constrained by RAM/storage;
stream long audio from SD. Not a hi-fi system.

### Micro-SD

FAT32 removable storage for images, fonts, logs, audio, and configuration. SD
contents are separate from device flash; back them up by copying files.

### USB

Firmware upload, serial logs, debugging, computer communication, and ESP32-S3
firmware-defined USB behavior. Flashing replaces the application; preserve the
full-flash backup before experimental changes.

### Sleep and Battery

Light/deep sleep; wake from timer, RTC alarm, or button; power off. The bistable
display keeps its last fully-refreshed image while asleep. Battery life is
dominated by refresh frequency, Wi-Fi/BLE/audio activity, sensor polling, and
wake frequency.

**MANDATORY for battery operation — power-hold latch (DEVICE VERIFIED 2026-06-29):**
the board only stays powered from the battery if firmware asserts the battery
power-enable. Call `board_power.VBAT_POWER_ON()` (drives **GPIO17 HIGH**) as the
FIRST thing in `setup()`. Without it, the board runs fine on USB but **dies the
instant USB is unplugged** (no function, and the e-paper may not retain a static
image). Power-pin polarity: `EPD_PWR`(GPIO6) and `Audio_PWR`(GPIO42) are
active-LOW (`POWEER_*_ON` -> 0); `VBAT_PWR`(GPIO17) is active-HIGH
(`VBAT_POWER_ON` -> 1). Any firmware intended to run on battery MUST include the
VBAT_POWER_ON call — this was a real regression when omitted.

**Battery-life planning — ALWAYS ask before building battery firmware.** Power
mode is a fundamental architecture decision, not a tweak added later. Before
writing firmware that may run on battery, REMIND the user that battery life
depends entirely on the design and ASK how long they want the device to last on
a charge. Then recommend a mode. Reference numbers for this board (small ~200–500
mAh LiPo; confirm the actual cell):

| Mode | Battery life | Bluetooth / behavior |
|---|---|---|
| Always-on (CPU never sleeps, BLE advertising 24/7) | ~3–8 hours | Always connectable; live touch/updates. ~40–70 mA. |
| Low-power "frame" | weeks–months | Deep sleep (~10–50 µA) between updates; wake on timer/touch/button; BLE enabled only on demand (e.g. hold BOOT for a minute to set time / upload). |
| Middle ground | ~1–2 days | Slower BLE advertising interval + light sleep between touch polls. |

Key facts to tell the user:
- The e-paper holds its image with **zero power**, so "draw, then deep sleep" is
  the natural low-power pattern and wastes nothing while idle.
- A status like "BT: off" on screen usually means *not connected* — the BLE radio
  may still be advertising and drawing power. Truly cutting BLE power means
  stopping advertising / deinit, not just "no client connected".
- Deep sleep and "always reachable over BLE" are mutually exclusive; the radio
  cannot advertise while the chip is in deep sleep.

Factory recommendation for a desk/wall e-paper frame: low-power frame mode (sleep
most of the time, wake periodically and on a button) — weeks per charge.

### Expansion

Two 6-pin headers expose GPIO/UART/I²C for compatible external modules. Never
describe external sensors or actuators as built in. High-current/mains loads
require external rated hardware.

## Programming Platforms

- Arduino IDE: recommended default for straightforward custom firmware. Use
  ESP32-S3 board support and an e-paper library (GxEPD2 or WaveShare's driver),
  plus drivers for PCF85063, SHTC3, FT6336 (touch variant), and ES8311.
- PlatformIO: structured projects, dependency management, repeatable builds.
- ESP-IDF: maximum control for networking, BLE, USB, and production firmware.
- MicroPython: quick prototypes and scripting.

Always confirm the board target is **ESP32-S3** and the flash size before
flashing (this unit: 8 MB, QIO, 3.3 V). Detect the serial port each time — it
enumerates as a native USB-Serial/JTAG `usbmodem` port whose name varies, and
the physical USB-C link on this unit is marginal (keep the cable still).

## Recommended Software Architecture

For most applications (especially battery designs):

0. At boot, FIRST assert the battery power-hold: `board_power.VBAT_POWER_ON()`
   (GPIO17 high). Required or the device dies when USB is unplugged.
1. Wake (timer/RTC/button) → read inputs and sensors → fetch network data if due.
2. Compute the new screen state.
3. Update only changed regions with partial refresh; full-refresh periodically to
   clear ghosting.
4. Persist anything that must survive restart (to flash NVS or SD).
5. Keep Wi-Fi/BLE work time-limited and non-blocking.
6. Sleep as soon as the screen and pending I/O are done (the image persists).
7. Recover gracefully from Wi-Fi/BLE/server/SD errors.

## Suitable Application Ideas

- E-paper clock/calendar/countdown (RTC + display, mostly asleep)
- Room temperature/humidity monitor that wakes, shows, and sleeps
- Battery name badge / status tag (bistable image, near-zero idle power)
- Wi-Fi status panel (weather, smart home, CI, prices) refreshed periodically
- Home Assistant / MQTT status display
- BLE temperature/humidity sensor reporting to a phone
- SD-driven image/QR display
- Timestamped sensor logger to SD
- Audio alert / short voice-note recorder
- Wi-Fi/BLE provisioning device

## Limitation Checklist

Before promising a feature, check:

- Display is black/white, 200 × 200, slow (~2 s full, ~0.3 s partial), with
  ghosting — no animation/video/fast UI.
- Bluetooth is BLE only, not Classic.
- Wi-Fi is 2.4 GHz only.
- No rotary encoder, no RFID on this board.
- Touch only on the touch variant (FT6336).
- Battery operation requires asserting the power-hold (`VBAT_POWER_ON`, GPIO17)
  at boot, or the board dies when USB is unplugged.
- Audio is limited by RAM/storage; not hi-fi.
- Limited flash (V1 4 MB / V2 8 MB) + microcontroller RAM (V1 2 MB / V2 8 MB
  PSRAM) — no large media, complex web apps, or heavy on-device AI.
- No built-in camera, GPS, cellular modem, or Ethernet.
- SHTC3 (temp/humidity), PCF85063 (RTC), ES8311 (audio), micro-SD, and battery
  charging are on board; most other sensing/actuation needs accessories.
- Cloud, MQTT, Home Assistant, BLE, and OTA require firmware implementation.
- High-current/mains control requires external rated hardware.
- Flashing another application replaces the installed firmware.

## How the AI Should Respond

- Explain what can be programmed before implementation detail.
- **For any battery-capable build, proactively ask the user how long they want a
  charge to last and recommend a power mode** (see Battery-life planning above)
  before committing to an always-on design. Do not silently ship an always-on
  firmware that drains in hours when the user may expect days/weeks.
- Group ideas by display, buttons, touch (variant), Wi-Fi, BLE, sensors, RTC,
  audio, SD, and power when helpful.
- Label features as built in, software-defined, or accessory-required.
- Surface e-paper limits (refresh time, ghosting, B/W) early when they affect the
  idea — favor "update, then sleep" patterns.
- For Bluetooth requests, say "Bluetooth Low Energy"; reject Classic assumptions
  and offer a BLE alternative.
- Confirm the touch vs non-touch variant before relying on touch.
- Do not search online for facts already recorded here unless freshness or a gap
  requires it.
- When asked to build firmware: inspect the workspace and connected device,
  ensure the full-flash backup exists, implement the feature, compile, flash, and
  test when feasible.
- Prefer concise, outcome-oriented explanations for nontechnical users.

## Local Device and Recovery

```yaml
device: WaveShare ESP32-S3-ePaper-1.54  # V2 (DEVICE VERIFIED 2026-06-29)
mcu: ESP32-S3-PICO-1 (LGA56), revision v0.2, dual-core LX7 @ 240 MHz, 40 MHz xtal
hw_version: V2 (confirmed: 8 MB flash / 8 MB PSRAM)
flash_size: 8 MB (GigaDevice c8/4017; eFuse quad/QIO, 3.3 V)
psram: 8 MB (AP_3v3)
display: 1.54" e-paper, 200x200, black/white, bistable
variant: TOUCH (FT6336, DEVICE VERIFIED 2026-06-29); battery vs -EN not yet confirmed
connected: yes — port /dev/cu.usbmodem1101 (USB-Serial/JTAG; port name varies)
device_mac: ac:27:6e:d2:07:28
full_flash_backup: backup/esp32s3-epaper154-full-flash-2026-06-29.bin (8,388,608 B, VERIFIED)
backup_sha256: 1be2d5337dd6a58340a9426120c54bf0465424dbb80c0a3b5bbe43c3c5028e9f
backup_notes: backup/README.md
backup_script: backup/backup_device.sh
backup_checksum: backup/SHA256SUMS
human_reference: ESP32S3-ePaper154_Functional Specification.md
claude_design_reference: ESP32S3-ePaper154_ClaudeDesign_Specification.md
```

The serial port name can change after reconnecting; always detect it instead of
assuming the previous value.

A verified factory full-flash backup exists, so flashing test firmware is safe as
long as that image is preserved. Restore with:

```sh
python3 -m esptool --port /dev/cu.usbmodemXXXX --baud 921600 \
  write_flash 0 backup/esp32s3-epaper154-full-flash-2026-06-29.bin
```

Connection caveat (DEVICE VERIFIED): the USB-C link on this unit is physically
marginal and flickered during setup. Use a known-good data cable plugged directly
(no hub/AV-adapter), keep it still, and if the chip enumerates as a `!matched`
"USB JTAG/serial debug unit" with no `usbmodem` node, reseat until a node binds.
Still to confirm by inspection: touch (FT6336, I²C addr 0x38) vs non-touch, and
battery vs `-EN`.

## Document Reference Locations

Local references to read first:

- `ESP32S3-ePaper154_AI_Specification.md`
- `ESP32S3-ePaper154_Functional Specification.md`
- `ESP32S3-ePaper154_ClaudeDesign_Specification.md`
- `ESP32S3-ePaper154_Development Log.log`
- `Factory ESP32S3-ePaper154_App_Functional Specificaton.md` (factory firmware, human)
- `Factory ESP32S3-ePaper154_App_Programming Specificaton (AI).md` (factory firmware, AI)
- `Make Spec.md`
- `Project instruction.md`
- `backup/README.md`

Official references used to create this specification (review dates 2026-06-28 /
2026-06-29):

- Product page: https://www.waveshare.net/shop/ESP32-S3-ePaper-1.54.htm
- Official documentation (all SKUs + V1/V2; setup, pinout, demos, FAQ):
  https://docs.waveshare.net/ESP32-S3-ePaper-1.54/?variant=ESP32-S3-Touch-ePaper-1.54
- Wiki (V2, non-touch; schematic, demo code, datasheets, LVGL):
  https://www.waveshare.net/wiki/ESP32-S3-ePaper-1.54-V2
- WaveShare wiki: https://www.waveshare.net/wiki/
- ESP32-S3 datasheet (Wi-Fi/BLE): https://www.espressif.com/documentation/esp32-s3_datasheet_en.pdf
- ESP32-S3 BLE programming guide:
  https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/ble/overview.html
