# Project Instructions — WaveShare ESP32-S3-ePaper-1.54

## What this project is

Research, test, and document the programmable behavior of the **WaveShare
ESP32-S3-ePaper-1.54** so future work can rely on evidence instead of
assumptions. The structure mirrors the reference project for the M5Stack Dial
kept in `Sample/`.

## Read before doing any work

1. This file.
2. `Project Experience.md` — solved problems, file locations, working commands.
   Read this before re-deriving anything.
3. `Make Spec.md` — the check/test/specification method (start here for any test).
5. `ESP32S3-ePaper154_AI_Specification.md` — primary local knowledge source.
6. `ESP32S3-ePaper154_Functional Specification.md` — human-readable behavior.
7. `ESP32S3-ePaper154_ClaudeDesign_Specification.md` — for UI/UX or product design.
8. `ESP32S3-ePaper154_Development Log.log` — prior experiments, failures, fixes.
9. `NextSteps.md` — current handoff state.
10. `backup/README.md` — before any firmware or recovery operation.

## The basic first step: back up the device

The factory firmware is irreplaceable until captured. **Before any flash, erase,
or modification, take a full-flash backup** using `backup/backup_device.sh` (see
`backup/README.md`). As of 2026-06-28 the device was **not connected**, so the
backup is **pending** — the tooling (esptool) is installed and the script is
ready. Do not flash or erase until the backup exists and verifies.

## Core rules

- Detect the USB serial port every time; never assume the previous name.
- Distinguish DOCUMENTED facts from locally verified findings; use the evidence
  labels from `Make Spec.md`.
- Bluetooth is **BLE only** (no Bluetooth Classic). Wi-Fi is **2.4 GHz only**.
- Respect e-paper reality: slow full refresh (~2 s), fast partial refresh
  (~0.3 s), ghosting, and limited grayscale. Do not design as if it were an LCD.
- Note whether the unit is the **touch (FT6336)** or **non-touch** variant before
  relying on touch.
- Test one behavior at a time; show state on screen and/or serial.
- Never commit real Wi-Fi passwords, API keys, or private keys.
- Do not modify eFuses or irreversible security settings.
- Keep specifications in agreement; add corrections rather than leaving known
  false statements.

## Where things live

- Methodology: `Make Spec.md`
- Specifications: `ESP32S3-ePaper154_*.md`
- Experiment history: `ESP32S3-ePaper154_Development Log.log`
- Backup + recovery: `backup/`
- Reference example specs (M5Stack Dial): `Sample/`
- Handoff: `NextSteps.md`
