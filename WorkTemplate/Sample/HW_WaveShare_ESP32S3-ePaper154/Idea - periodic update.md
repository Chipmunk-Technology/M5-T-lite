# Idea — Periodic Update (adaptive low-power BLE)

Status: **CONCEPT / not yet implemented.** A power-saving operating mode for the
WaveShare ESP32-S3-ePaper-1.54 (V2, touch). Goal: make a battery charge last
**weeks** instead of the few hours the current always-on firmware gives, while
still syncing with the iOS app when the phone is nearby.

## The idea (user's words, refined)

The e-paper should spend almost all its time in **deep sleep**. It periodically
**checks whether the iOS phone is nearby (connectable)**:

- **Every ~30 minutes**, or **on a screen/button press**, it wakes and checks.
- **If the phone is nearby** → enter an **active** mode that syncs roughly **every
  5 minutes** and refreshes the screen data.
- **Otherwise** → go back to deep sleep to save power.

## One BLE reality that shapes the design

In Bluetooth LE the **phone (central) connects to the device (peripheral)** — the
e-paper cannot reach out and connect to the phone. So the device does not *scan*
for the phone; instead it **advertises for a short window and sees whether the
phone connects**. Same outcome ("is my phone here and willing?"), inverted
mechanism.

## Operating flow

1. **Deep sleep** almost all the time (~10–50 µA on the ESP32-S3).
2. **Wake** from either:
   - the **PCF85063 RTC alarm** (e.g. every 30 min) — RTC keeps time while asleep
     and pulses its INT pin to wake the ESP32; or
   - a **screen touch / button** (GPIO deep-sleep wake; first touch just wakes it,
     the UI reacts a moment later).
3. **Advertise ~10–30 s** and wait for a connection.
4. **Phone connects?**
   - **Yes** (phone nearby) → phone pushes fresh data, screen redraws → switch to
     **active mode**: short sleeps, wake ~every 5 min to resync.
   - **No** (phone away) → optionally redraw from onboard sensors → deep sleep;
     after a few empty checks, relax back to the 30-min interval.
5. Remember the **"phone present"** state across sleeps in **RTC RAM**, so the
   device speeds up to 5-min while you're around and slows to 30-min when you
   leave.

## Power estimate (≈300 mAh LiPo; confirm actual cell)

| State | Behaviour | Battery life |
|---|---|---|
| Idle | 30-min check windows, deep sleep between | ~**3 weeks** |
| Active | 5-min syncs while phone is nearby | ~**3–4 days** (only while you're around) |
| (current always-on firmware, for comparison) | never sleeps, BLE advertises 24/7 | ~**3–8 hours** |

## The key design question — where does the screen data come from?

This decides how often the phone is actually needed:

- **From the phone** (weather, calendar, notifications, a photo) → the phone
  connection IS required to refresh; the scheme above applies as written.
- **From onboard sensors** (temperature, humidity, time) → the device can
  **sample and redraw itself on each wake** and barely needs the phone; the phone
  is only needed occasionally to set the clock, upload a photo, or pull history.

Most likely a **mix**: temp/humidity/time are onboard (update without the phone),
and the phone handles the occasional photo / time-set / history sync.

## iOS app side (needed for hands-off operation)

For the phone to connect during the device's short advertising windows **without
the user opening the app**:

- Enable the **`bluetooth-central` background mode**.
- Use a **held auto-connect** (a pending `connect()` with no timeout) so iOS links
  up whenever the device advertises and is in range.
- Add **state restoration** (a `CBCentralManager` restore identifier) so iOS can
  relaunch the app in the background when the device appears.

**Honest limits:** timing is iOS-controlled and best-effort (seconds, usually,
not "exactly every 5 min"); it does **not** work after a **force-quit** (swipe-up
kill) and is paused after a **phone reboot** until the app is opened once.

## Pairs naturally with on-device history logging

An every-N-minutes wake is the textbook spot to also **log a reading** (see the
history-buffer idea): on each wake, read SHTC3, append to a ring buffer
(RTC RAM for sleep-survival, or NVS for power-off survival, or micro-SD for long
logs), then redraw and sleep. This gives **both** long battery life **and** a
"past 12 hours, hourly" history at the same time.

## Hardware support (all present on this board)

- **Deep sleep wake on RTC alarm:** PCF85063 (I²C 0x51) INT → ESP32 wake pin.
- **Deep sleep wake on touch/button:** FT6336 INT (GPIO21) or PWR/BOOT buttons
  (GPIO18 / GPIO0) via GPIO wake.
- **Battery power-hold:** assert `VBAT_POWER_ON` (GPIO17) at every boot/wake or the
  board dies off-USB (see Development Log 2026-06-29).
- **State across sleep:** RTC slow memory survives deep sleep; NVS/SD survive
  power-off.
- **Image retention:** the e-paper holds its last fully-refreshed image at zero
  power, so the screen stays readable the entire time the chip is asleep.

## Open decisions before building

1. **Battery target / mode:** adopt this adaptive low-power mode (weeks idle) vs.
   keep always-connected (hours)?
2. **Data source:** which screen fields are phone-sourced vs. onboard sensors?
3. **Intervals:** confirm 30-min idle check and 5-min active sync (tunable).
4. **History:** also log readings on each wake? Where (RTC RAM / NVS / SD) and how
   long a window?
5. **iOS background auto-connect:** add it (needed for hands-off), accepting the
   iOS timing limits above?

## Status / next step

Concept only — no firmware written for this yet. The current `firmware/ePaper_BLE`
is always-on. When the decisions above are settled, implement: RTC-alarm + touch
wake, short advertise-and-check window, adaptive 5-/30-min schedule, deep sleep
between, optional per-wake logging, and the iOS background auto-connect.

Related docs: `ESP32S3-ePaper154_AI_Specification.md` (battery-life planning),
`ESP32S3-ePaper154_Functional Specification.md` (battery section),
`ESP32S3-ePaper154_Development Log.log` (power-hold + battery-drain findings),
`Project Experience.md` (battery reading + power-hold).
