# Next Steps — WaveShare ESP32-S3-ePaper-1.54

Updated: 2026-06-29

## Current state

- **Battery power-hold fix coded, REFLASH PENDING:** `firmware/ePaper_BLE/` now
  calls `board_power.VBAT_POWER_ON()` (GPIO17) first in `setup()` so the board
  keeps running on battery when USB is unplugged (previously it died on unplug —
  see Development Log 2026-06-29). BUILD VERIFIED; needs the device back on USB to
  flash, then verify: unplug USB → stays running + screen retained. Also apply the
  same one-liner to `firmware/ABC_Touch_Toggle/`.
- Specification set and `Make Spec.md` method created.
- **Full-flash backup DONE and verified (2026-06-29):**
  `backup/esp32s3-epaper154-full-flash-2026-06-29.bin` (8 MB), SHA-256 checks OK.
- **Device identified (DEVICE VERIFIED):** ESP32-S3-PICO-1 (LGA56) rev v0.2,
  **V2** (8 MB flash / 8 MB PSRAM), MAC `ac:27:6e:d2:07:28`, USB-Serial/JTAG.
- Connection note: the USB-C link is physically marginal and flickered during
  setup. It works with a solid data cable plugged directly (no hub). Keep the
  cable still during any flashing. Port seen as `/dev/cu.usbmodem1101` (varies).

## Still to confirm (not derivable from the flash read)

- **Touch (FT6336)** vs **non-touch** — visual / I²C scan for 0x38 (FT6336).
- **Battery** vs **-EN** (no battery) — visual.
- Identify the pre-installed factory firmware behavior; log it.
- If a micro-SD card is inserted, copy its files off separately as a second backup.

## Recovery (now available)

The factory image can be restored if a flash goes wrong:
```sh
python3 -m esptool --port /dev/cu.usbmodemXXXX --baud 921600 \
  write_flash 0 backup/esp32s3-epaper154-full-flash-2026-06-29.bin
```
Confirm the port and the file's SHA-256 first. Flashing test firmware is now safe
as long as this backup is preserved.

## Then (first verification tests, per Make Spec.md)

- Minimal e-paper "hello" test: full refresh, then partial refresh of a region;
  confirm ~2 s / ~0.3 s timings → promote display facts to DEVICE VERIFIED.
- RTC (PCF85063) keep-time-across-reset and alarm wake.
- SHTC3 temperature/humidity readout.
- Wi-Fi connect + NTP time sync.
- BLE advertise + connect from a phone.
- (Touch variant) FT6336 tap/position test.

## Custom firmware — DONE (DEVICE VERIFIED 2026-06-29)

- **`firmware/ABC_Touch_Toggle/`** — tap e-paper → big "ABC"; tap again → back.
  Built (arduino-cli, esp32 core 3.3.10), flashed to /dev/cu.usbmodem11201,
  and **confirmed working on hardware** (user observed the tap-toggle).
- This also **confirmed the unit is the TOUCH (FT6336) variant**.
- The factory firmware was replaced; restore any time from
  `backup/esp32s3-epaper154-full-flash-2026-06-29.bin` (see backup/README.md).
- Build/flash steps and FQBN: `firmware/ABC_Touch_Toggle/README.md`.

## BLE app + firmware (2026-06-29)

- **`firmware/ePaper_BLE/`** — BLE GATT server (info + Wi-Fi + image upload) on
  top of the e-paper/touch/sensor app. BUILD + FLASH verified; advertises
  `ePaper-154`. Tap toggles home ↔ uploaded picture.
- **`ios/ePaperBLE.xcodeproj`** — SwiftUI + CoreBluetooth app (2 tabs: device info
  / photo upload). **BUILD VERIFIED** (compiles + runs in the iOS simulator).
  To use: open the .xcodeproj, set a signing Team, run on a real iPhone (BLE needs
  a physical device). Steps in `ios/README.md`.
- **Next to verify on hardware (user):** connect from the app or nRF Connect;
  read temp/humidity/time; set time; upload a photo and confirm it displays.
  Until verified live, BLE behavior is BUILD/FLASH-verified only.

## Proposed next feature (concept written, not built)

- **`Idea - periodic update.md`** — adaptive low-power mode: deep sleep, wake every
  ~30 min (RTC alarm) or on touch to advertise/check for the phone; sync ~every
  5 min while the phone is nearby, else sleep. Targets weeks of battery + optional
  per-wake history logging + iOS background auto-connect. Needs decisions: battery
  target, which screen data is phone-sourced vs onboard, intervals, history store.

## Still open / optional

- Confirm **battery vs -EN** SKU (visual only; not testable from firmware).
- Serial console didn't emit over native USB-Serial/JTAG with the pyserial
  capture (HWCDC quirk). If serial logs are wanted later, try `arduino-cli
  monitor` or the Arduino IDE Serial Monitor instead.
- Capture the factory firmware's own serial/screen behavior is now moot on this
  unit (overwritten); the backup preserves the image if needed.

## Reference docs (recorded 2026-06-29)

- Official documentation (all SKUs + V1/V2):
  https://docs.waveshare.net/ESP32-S3-ePaper-1.54/?variant=ESP32-S3-Touch-ePaper-1.54
- Wiki (V2, non-touch): https://www.waveshare.net/wiki/ESP32-S3-ePaper-1.54-V2
- Product page: https://www.waveshare.net/shop/ESP32-S3-ePaper-1.54.htm

## Notes

- Reference structure and example specs: `Sample/` (M5Stack Dial project).
- Keep DOCUMENTED vs verified facts distinct; update specs after each finding.
- Two hardware versions exist (V1 4 MB/2 MB, V2 8 MB/8 MB); do not assume 8 MB
  until confirmed on the device.
