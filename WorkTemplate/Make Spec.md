# WaveShare ESP32-S3-ePaper-1.54 — Check, Test, and Specification Method

## Purpose

Use this document whenever researching, testing, or documenting a function of
the WaveShare ESP32-S3-ePaper-1.54.

The goal is to produce specifications based on clear evidence rather than
assumptions. A feature should move from documentation, to a buildable test, to a
flashed test, and finally to physical-device verification whenever feasible.

This method mirrors the project's reference method for the M5Stack Dial
(`Sample/`), adapted for an e-paper device with no rotary encoder, no RFID, and
a slow-refreshing reflective display.

## Basic First Step — Back Up the Device

**Before any other work, before any flash or erase, take a full-flash backup.**

The factory firmware is irreplaceable until it is captured. The procedure and
tooling live in `backup/`:

1. Read `backup/README.md`.
2. Plug the device into USB-C with a data cable.
3. Run `backup/backup_device.sh` (non-destructive full-flash read).
4. Confirm `backup/SHA256SUMS` records the new image.

Do not flash, erase, or modify the device until this backup exists and verifies.
If the device is not connected yet, stop at this step and ask for it to be
plugged in. (As of 2026-06-28 the device was not connected and the backup is
pending; tooling is installed and ready.)

## Basic Second Step — Characterize the Factory Firmware from the Backup

Immediately after the verified backup, and **before flashing anything**, analyse
the backup image itself (non-destructive — you only read the `.bin`) to document
the app that shipped on the device. This is how the paired `Factory …App…` specs
are produced. Do it once per new board, then keep the two files in sync.

Procedure (all offsets are for a standard ESP-IDF layout — adjust per board):

1. **Parse the partition table** at flash offset `0x8000` (32-byte entries, magic
   `0xAA50`). Record each partition's label, type/subtype, offset, and size. Note
   whether there are OTA slots and whether any FAT/SPIFFS/LittleFS data partition
   exists (if not, files live on the SD card). Note any large erased (`0xFF`)
   region left unused on the flash.
2. **Read the app descriptor** of each app partition: the ESP image starts with
   `0xE9`; the `esp_app_desc_t` (magic `0xABCD5432`) sits just after the 24-byte
   image header + 8-byte segment header. Extract **project name, version, build
   date/time, ESP-IDF version, and secure-version**.
3. **Scan strings/symbols** of the app region (`strings -n 5` on the extracted
   app partition) to identify which subsystems the firmware initializes — display
   / touch controller, IMU, RTC, audio codec(s) and mic path, SD/FATFS, GPIO
   expander, Wi-Fi, BLE **stack (Bluedroid vs NimBLE) and any RF/manufacturing
   test routines**, power/battery ADC, and the board's per-peripheral BSP
   component names. Recover any **on-screen instruction / menu / `_Test` label**
   strings verbatim — these reveal the real user interaction.
4. **Record the bus map** where the strings reveal it (e.g. which I²C port each
   device is on, QSPI for the panel), but take exact GPIO numbers and I²C
   addresses from the schematic/demo code, not guesses.
5. **Write the paired Factory specs** (create if absent, keeping them
   synchronized):
   - `Factory <Board>_App_Functional Specificaton.md` — human description of the
     factory app: identity table, flash layout, subsystems exercised, inferred
     user-visible behaviour, limitations.
   - `Factory <Board>_App_Programming Specificaton (AI).md` — a buildable
     reproduction contract: replication target, feature-sync IDs, toolchain
     (exact ESP-IDF version + key components/stacks), the partition CSV, the bus/
     peripheral map, per-feature behaviour, the interaction model from the
     recovered strings, limitations, and an acceptance checklist.
6. **Set the evidence status to `PARTIAL` (binary-derived, not run-traced).**
   Anything inferred from the binary (screen layout, wording, pass/fail visuals)
   stays `PARTIAL` until confirmed by a live serial boot log and physical
   observation, then promote to `DEVICE VERIFIED` in both files and the log.

Distinguish the two spec families: the `Factory …App…` files describe **the
firmware that shipped on this unit** (reverse-engineered from the backup); the
non-`Factory` capability specs describe **what the board can be programmed to do**
in general. Keep them separate.

## Required Reading

Before starting a test or changing a specification, read:

1. `Project instruction.md`
2. `ESP32S3-ePaper154_AI_Specification.md`
3. `ESP32S3-ePaper154_Functional Specification.md`
4. `ESP32S3-ePaper154_ClaudeDesign_Specification.md` for UI/UX or product-design work
5. Relevant earlier entries in `ESP32S3-ePaper154_Development Log.log`
6. `backup/README.md` before any firmware or recovery operation
7. `NextSteps.md` for the current handoff state

## Evidence Levels

Use these exact labels:

- `DOCUMENTED`: stated by an official specification, datasheet, library, or
  example, but not tested locally.
- `BUILD VERIFIED`: the test firmware compiled successfully for this board.
- `FLASH VERIFIED`: the firmware uploaded successfully to the target device.
- `DEVICE VERIFIED`: the expected behavior was observed physically or confirmed
  through reliable device output.
- `PARTIAL`: only some acceptance checks passed or verification was interrupted.
- `FAILED`: the test did not produce the expected result.

Do not use `DEVICE VERIFIED` based only on source code, compilation, or
assumptions.

## End-to-End Workflow

### 1. Define the Function

Write a short test definition before implementation:

- Function name
- User-visible purpose
- Input or trigger (PWR button, BOOT button, touch where present, Wi-Fi, BLE,
  sensor reading, SD file, RTC alarm, etc.)
- Expected screen, sound, network, or device response
- Important limitations (especially e-paper refresh time and ghosting)
- Whether companion software, Wi-Fi credentials, a BLE client, a battery, a
  micro-SD card, the touch variant, or other equipment is required
- **Target battery life (if it may run on battery).** Power mode is an
  architecture decision, so REMIND/ASK the user how long they want a charge to
  last before building, and recommend a mode: always-on ≈ hours; low-power
  deep-sleep "frame" ≈ weeks–months; middle ground ≈ a day or two. Do not default
  to an always-on design that drains in hours when longer life is expected.
  (See the battery-life table in the AI/Functional specifications.)

Test one primary behavior at a time. Combined demonstrations should come after
the individual functions are understood.

### 2. Check Existing Local Knowledge

Search local files first:

- AI specification for capability and limitation facts
- Functional specification for human-readable behavior
- Development log for previous commands, failures, and fixes
- Existing firmware folders for reusable code

Do not repeat internet research when local files already answer a stable
question. Use current official sources when APIs, library versions, or behavior
may have changed, or when the local specification is incomplete.

### 3. Verify the Target Device

Before flashing or reading the device:

- Confirm it is the **ESP32-S3-ePaper-1.54** (200×200 1.54" e-paper), and note
  whether it is the **touch (FT6336)** or **non-touch** variant.
- Detect the current USB serial port; never assume a previous suffix.
- Confirm the ESP32-S3 target and flash size (documented 8 MB) with
  `esptool flash_id`.
- Ensure no serial monitor or other process is locking the port.
- Confirm the flash backup exists and passes its SHA-256 before risky changes.

If the chip cannot be reached, enter download mode: hold **BOOT**, tap
**RESET/PWR**, release **BOOT**.

### 4. Establish Acceptance Criteria

Define observable pass/fail checks. Examples:

E-paper display:

- A full refresh draws the intended image within ~2 s.
- A partial refresh updates the target region within ~0.3 s.
- Text and graphics are legible under reflected light.
- Ghosting is cleared by a periodic full refresh.

Buttons:

- PWR and BOOT presses are detected as defined by firmware.
- Long/short press behavior matches the specification.

Touch (touch variant only):

- A visible target responds only when touched.
- Reported position matches the touched area.
- Release is detected.

Wi-Fi:

- Device connects to the intended 2.4 GHz network.
- Screen or serial output reports connection state.
- Required request is sent and a response received.
- Disconnection and reconnection behavior are checked.

Bluetooth Low Energy:

- Device advertises with the intended identity.
- A phone/computer can discover it.
- Pairing or connection works as designed.
- Characteristic reads, writes, notifications, or HID events work.
- No Bluetooth Classic behavior is expected.

Sensors / RTC / audio / SD:

- SHTC3 returns plausible temperature and humidity.
- PCF85063 keeps time across a reset and wakes on alarm.
- ES8311 records from the mic and plays to the speaker as designed.
- Micro-SD mounts (FAT32) and reads/writes the intended files.

Sleep/wake/battery:

- Device visibly enters the intended low-power state.
- It wakes from the specified source (timer, button, RTC).
- Battery-only behavior is tested separately from USB-powered behavior.

### 5. Create a Minimal Test

Prefer a small, reversible firmware test that:

- Exercises one feature
- Shows its state on the e-paper screen and/or serial log
- Provides an obvious success/failure indication
- Minimizes full-screen refreshes (use partial refresh; batch updates)
- Avoids unnecessary network services, peripherals, or abstractions
- Avoids long blocking delays in interactive paths

Store test firmware in a clearly named project subfolder. Include a short README
when the test needs credentials, companion software, the touch variant, a
battery, an SD card, or manual steps.

Never store real Wi-Fi passwords, API secrets, or private keys in shared source.
Use ignored local configuration or placeholders.

### 6. Record the Environment

Record: date; framework (Arduino, PlatformIO, ESP-IDF, MicroPython); board/
platform version; library versions (e.g. GxEPD2 or the WaveShare e-paper
driver); compiler/tool version; serial port; build command; flash command;
firmware source location; required external equipment or companion app.

This information belongs in `ESP32S3-ePaper154_Development Log.log`.

### 7. Build Before Flashing

- Compile locally first.
- Treat warnings about memory, partition size, deprecated APIs, or unsafe
  behavior as findings.
- Record binary size and memory use when the tool reports them.
- Do not flash if the build targets the wrong board, flash size, or partition
  layout.
- Mark successful compilation as `BUILD VERIFIED`, not device verification.

### 8. Flash Carefully

- Confirm the current port immediately before flashing.
- Confirm the full-flash backup exists and verifies first.
- Close other serial tools.
- Use the least destructive upload suitable for the test.
- Do not erase the entire flash unless required and documented.
- Do not modify eFuses or irreversible security settings.
- Record whether the current firmware was replaced.
- Mark a successful upload as `FLASH VERIFIED` until behavior is checked.

### 9. Observe the Physical Device

After flashing, check more than one source of evidence when possible: screen
output (full and partial refresh), button behavior, touch (variant), audio,
serial logs, Wi-Fi/BLE result, sensor values, SD access, and sleep/wake timing.

Repeat interactive tests several times, including edge cases (fast repeated
updates, ghosting after many partial refreshes, network loss, low battery). If
the agent cannot see or hear the result, ask the user or use reliable serial/
network evidence. Do not invent a physical result.

### 10. Diagnose Failures Systematically

Separate the failure stage: tool install → dependency resolution → compilation →
device connection/boot mode → flash/upload → startup/crash → input detection →
display/audio output → Wi-Fi/BLE/sensor protocol → power/sleep/wake.

Record the exact error or symptom. Change one variable at a time. Prefer the
smallest reproducing test. After a fix, record root cause, the change, why it
works, the retest result, and whether the fix is general or environment-
specific. Do not erase failed attempts from the log.

### 11. Classify the Result

Assign one status: `DEVICE VERIFIED` only when all required acceptance criteria
pass; `PARTIAL` when incomplete; `FAILED` when it did not work; otherwise
`DOCUMENTED`, `BUILD VERIFIED`, or `FLASH VERIFIED`. List remaining limitations
and the next useful test.

### 12. Update the Specifications

After meaningful findings:

- Append full technical evidence to `ESP32S3-ePaper154_Development Log.log`.
- Update `ESP32S3-ePaper154_Functional Specification.md` with stable behavior.
- Update `ESP32S3-ePaper154_AI_Specification.md` with stable rules.
- Update `ESP32S3-ePaper154_ClaudeDesign_Specification.md` when a finding
  changes design possibilities or display constraints.
- Keep uncertain or one-off observations in the development log until repeated.
- Add a correction instead of silently preserving a known false statement.
- Keep document reference locations at the bottom of specification files.

## Development Log Entry Template

```text
================================================================================
YYYY-MM-DD HH:MM - Function or experiment name
Status: DOCUMENTED | BUILD VERIFIED | FLASH VERIFIED | DEVICE VERIFIED | PARTIAL | FAILED
================================================================================

Goal:
What should the device do?

Acceptance criteria:
- Observable pass condition 1
- Observable pass condition 2

Environment:
- Framework and version:
- Board/platform:
- Libraries:
- Firmware source:
- Serial port:
- Required equipment/software:

Commands:
- Build:
- Flash:
- Monitor/test:

Observed result:
What actually happened on screen, buttons, touch, serial, network, BLE,
sensors, SD, audio, or power.

Failures/errors:
Exact messages or symptoms.

Diagnosis:
Likely or confirmed cause.

Solution:
Changes made and why.

Verification:
Retest result and evidence level.

Limitations/follow-up:
Anything unresolved or worth testing next.
```

## Specification Quality Checklist

Before calling a specification update complete, verify:

- It refers to the ESP32-S3-ePaper-1.54 (200×200 1.54" e-paper), and notes the
  touch vs non-touch variant where it matters.
- It focuses on programmable behavior.
- Built-in and accessory-required features are distinguished.
- Bluetooth is described as BLE only.
- Wi-Fi is described as 2.4 GHz only.
- E-paper refresh time, ghosting, and limited color/grayscale are stated.
- Limitations are included.
- Documented claims and locally verified findings are not confused.
- No secret credentials are included.
- Recovery and backup paths are correct.
- Reference locations remain at the bottom of the specification.
- Cross-references use current filenames and all referenced local paths exist.
- The human, AI, and Claude Design specifications agree on capabilities and
  limitations.

## Key Reference Locations

- Project rules: `Project instruction.md`
- Human feature specification: `ESP32S3-ePaper154_Functional Specification.md`
- AI knowledge specification: `ESP32S3-ePaper154_AI_Specification.md`
- Claude Design specification: `ESP32S3-ePaper154_ClaudeDesign_Specification.md`
- Experiment history: `ESP32S3-ePaper154_Development Log.log`
- Current handoff state: `NextSteps.md`
- Flash recovery information: `backup/README.md`
- Backup script: `backup/backup_device.sh`
- Reference method and example specs (M5Stack Dial): `Sample/`
