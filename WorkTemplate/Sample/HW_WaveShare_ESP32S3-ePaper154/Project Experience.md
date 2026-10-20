# Project Experience — WaveShare ESP32-S3-ePaper-1.54

Solved problems, file locations, and working commands. **Read this before
re-deriving anything.** Mirrors the role of the M5Stack Dial project's
`Project Experience.md`. Newest-relevant facts first; keep entries concise and
command-accurate. Convert relative dates to absolute.

## Device facts (DEVICE VERIFIED 2026-06-29)

```yaml
device: WaveShare ESP32-S3-ePaper-1.54, hardware version V2
mcu: ESP32-S3-PICO-1 (LGA56), revision v0.2, 40 MHz crystal
flash: 8 MB (GigaDevice c8/4017, eFuse quad/QIO, 3.3 V)
psram: 8 MB (AP_3v3)   # the e-paper driver allocates its buffer in PSRAM
display: 1.54" e-paper, 200x200, black/white, bistable
mac: ac:27:6e:d2:07:28
usb: native USB-Serial/JTAG (baud ignored; runs at USB speed)
touch: YES - FT6336, DEVICE VERIFIED 2026-06-29 (tap toggled the ABC app)
sku_unconfirmed: battery vs -EN   # still confirm visually
```

V1 vs V2 matters: **V1 = 4 MB flash / 2 MB PSRAM, V2 = 8 MB / 8 MB**. This unit
is V2 (read via esptool). Don't assume 8 MB on an unread board.

## File locations

```text
Project instruction.md            # entry point / rules
Make Spec.md                      # check/test/specification method
Project Experience.md             # this file
NextSteps.md                      # current handoff state
ESP32S3-ePaper154_Development Log.log   # append-only technical log (detailed)

# Device specification set
ESP32S3-ePaper154_Functional Specification.md
ESP32S3-ePaper154_AI_Specification.md
ESP32S3-ePaper154_ClaudeDesign_Specification.md

# Factory (default) firmware, reverse-documented from the backup
Factory ESP32S3-ePaper154_App_Functional Specificaton.md
Factory ESP32S3-ePaper154_App_Programming Specificaton (AI).md

# Backup & recovery
backup/esp32s3-epaper154-full-flash-2026-06-29.bin   # 8 MB, factory image
backup/SHA256SUMS                                     # 1be2d533…28e9f
backup/backup_device.sh                               # non-destructive dumper
backup/README.md

# Custom firmware
firmware/ABC_Touch_Toggle/        # tap -> big ABC, tap -> back (Arduino-ESP32 3.x)

# Reference (untouched): the M5Stack Dial project this structure is modeled on
Sample/
```

## Working commands (verified on this machine, macOS arm64)

Backup / restore (esptool v4.11.0, `python3 -m pip install --user esptool`):

```sh
PORT=$(ls /dev/cu.usbmodem* | head -1)
python3 -m esptool --port "$PORT" flash_id                       # identify chip
python3 -m esptool --port "$PORT" --baud 921600 \
  read_flash 0 0x800000 backup/esp32s3-epaper154-full-flash-2026-06-29.bin
shasum -a 256 -c backup/SHA256SUMS                               # verify
# RESTORE (overwrites device):
python3 -m esptool --port "$PORT" --baud 921600 \
  write_flash 0 backup/esp32s3-epaper154-full-flash-2026-06-29.bin
```

Inspect a flash dump offline (no device needed):

```sh
# partition table is at offset 0x8000; app descriptor magic 0xABCD5432 at app+0x20
# strings + the python parser used on 2026-06-29 are in the Development Log.
```

Firmware build/flash (Arduino-ESP32 **3.x**, arduino-cli via `brew install arduino-cli`):

```sh
export PATH="/opt/homebrew/bin:$PATH"
arduino-cli core install esp32:esp32        # 3.x; large download (~minutes)
FQBN="esp32:esp32:esp32s3:PSRAM=opi,FlashSize=8M,USBMode=hwcdc,CDCOnBoot=cdc,PartitionScheme=default_8MB"
arduino-cli compile --fqbn "$FQBN" firmware/ABC_Touch_Toggle
arduino-cli upload  --fqbn "$FQBN" -p "$(ls /dev/cu.usbmodem* | head -1)" firmware/ABC_Touch_Toggle
```

## Solved problems

### Battery power-hold — device dies the instant USB is unplugged
On battery, firmware MUST assert the power-hold latch or the board cuts power the
moment USB is removed (board dead, e-paper can't even keep a static image). Call
`board_power.VBAT_POWER_ON();` (drives **GPIO17 HIGH**) as the **first line of
setup()**. While USB is connected the board is powered regardless, so the bug is
invisible on USB and only shows when you unplug. The factory firmware asserts
this; my early custom firmwares omitted it (regression). E-paper is bistable so a
fully-refreshed image normally persists with no power, but an abrupt power cut can
prevent a clean latch — the power-hold avoids the cut entirely on battery.

### Reading battery percentage (from the factory firmware's method)
Battery voltage is on **ADC1 channel 3 = GPIO4**, through an on-board **1:2
divider**. Recipe (WaveShare factory `port_adc.cpp`): read calibrated mV, then
`V = mV/1000 * 2`; percent maps **3.00 V = 0%** to **4.12 V = 100%** linearly.
Arduino one-liner: `analogReadMilliVolts(4)` (calibrated), average a few samples.
Used on the ePaper_BLE home screen ("BAT nn%"). BT/Wi-Fi status on that screen =
`deviceConnected` (a phone is connected) and `WiFi.status()==WL_CONNECTED`.

### USB connection is intermittent (marginal link)
Symptom: the board enumerated then dropped; `/dev/cu.usbmodem*` came and went; at
times only a `USB JTAG/serial debug unit` appeared `!matched` with no tty node.
Cause: marginal USB-C physical link (originally through a hub / Type-C AV adapter,
and charge-biased cables). Fix: a known-good **data** cable **directly** to the
Mac (no hub), kept still. Inspect with `ioreg -p IOUSB -l -w 0` (note:
`system_profiler SPUSBDataType` returned nothing in this sandbox). To force the
ROM serial, enter download mode: hold **BOOT**, tap **RESET/PWR**, release BOOT.

### Which hardware version? (V1 vs V2)
`esptool flash_id` reports `Embedded Flash 8MB / Embedded PSRAM 8MB` ⇒ **V2**.
Product-page "8 MB" claims are V2-specific; V1 is 4 MB / 2 MB.

### Reading what's on the device without a serial log
The factory firmware was identified entirely from the verified backup: parse the
partition table (0x8000), read the ESP-IDF app descriptor → project
`02_ePaper_1_54_Test`, board `S3_ePaper_1_54`, ESP-IDF v5.4.3, built Jan 4 2026.
String/symbol fingerprinting showed it exercises e-paper(LVGL), SHTC3, PCF85063,
ES8311 audio, SD (`/sdcard/sdcard.txt`), Wi-Fi, BLE(Bluedroid), ADC.

### Firmware framework choice (the important one)
WaveShare's FT6336 touch driver uses the **new** `driver/i2c_master.h` API
(ESP-IDF **5.2+**). The only local IDF toolchain is **v5.1.3** (too old). So
custom firmware uses **Arduino-ESP32 3.x** (ships the right I2C API; WaveShare's
documented path). Don't try to build the touch driver under IDF 5.1.3.

### Exact board pin map (from WaveShare's own examples)
```text
EPD:  DC=10 CS=11 SCK=12 MOSI=13 RST=9 BUSY=8 PWR=6   (SPI2_HOST)
I2C:  SDA=47 SCL=48   FT6336=0x38  RTC(PCF85063)=0x51  SHTC3=0x70
Touch: INT=21 RST=7
Buttons: BOOT=0  PWR=18
Power rails (board_power_bsp):
  EPD_PWR=GPIO6   active-LOW  (POWEER_EPD_ON -> 0)
  Audio_PWR=GPIO42 active-LOW (POWEER_Audio_ON -> 0)
  VBAT_PWR=GPIO17 active-HIGH (VBAT_POWER_ON -> 1) = BATTERY POWER-HOLD LATCH
```
Source: `waveshareteam/ESP32-S3-ePaper-1.54` examples `09_LVGL_V8_Test` and
`12_FT6336_Test`. Cloned during the 2026-06-29 session.

### e-paper drawing model
1bpp buffer, 200x200 = 5000 bytes; `pixel index = y*25 + (x>>3)`, `bit = 7-(x&7)`;
**WHITE sets** the bit, **BLACK clears** it. `EPD_Clear()` = white buffer;
`EPD_Display()` = full refresh (~2 s, ghost-free); `EPD_DisplayPart()` = partial
(~0.3 s, needs base image + `EPD_Init_Partial`). The driver buffer is allocated in
**PSRAM**, so the Arduino build **must** enable PSRAM (OPI) or it asserts at boot.

## Gotchas to remember

- Detect the serial port every time; the `usbmodem` name varies and the link is
  flaky. Keep the cable still during flashing.
- e-paper is bistable: the last screen stays visible unpowered — the image you see
  now is whatever the factory test left.
- BLE is BLE-only; Wi-Fi is 2.4 GHz only.
- Always keep `backup/…full-flash-2026-06-29.bin`; it is the only way back to
  factory firmware.

## Reference locations

- Method: `Make Spec.md`  · Rules: `Project instruction.md`  · Handoff: `NextSteps.md`
- Detailed evidence/commands per session: `ESP32S3-ePaper154_Development Log.log`
- Upstream demo source: https://github.com/waveshareteam/ESP32-S3-ePaper-1.54
- Product docs: https://docs.waveshare.net/ESP32-S3-ePaper-1.54/?variant=ESP32-S3-Touch-ePaper-1.54
- Wiki (V2): https://www.waveshare.net/wiki/ESP32-S3-ePaper-1.54-V2
