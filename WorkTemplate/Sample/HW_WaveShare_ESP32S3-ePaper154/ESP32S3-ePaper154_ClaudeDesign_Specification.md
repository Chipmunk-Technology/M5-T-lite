# WaveShare ESP32-S3-ePaper-1.54 Claude Design Specification

## Purpose

This document is a design brief for Claude Design or another visual/UX system
creating interfaces for the WaveShare ESP32-S3-ePaper-1.54.

Use it to design screens, interaction flows, visual states, and product concepts
that are realistic for this physical device. It describes what the device can
support and the constraints that should shape the design.

This is not a programming specification. Do not include source code, software
APIs, build instructions, pin assignments, or implementation tables in design
output.

## Device Character

The board is a compact, low-power **e-paper information surface**. Its strongest
quality is a crisp, paper-like black-and-white display that holds its image with
no power. It is best for **glanceable, slowly-changing information**: a clock,
a sensor readout, a status panel, a badge.

It should feel like a smart label, a desk clock, or a status tag — not a phone or
a live dashboard. Design for "wake, show, sleep," not for continuous animated
interaction.

The board has buttons (PWR, BOOT), optional capacitive touch (touch variant
only), Wi-Fi, BLE, a temperature/humidity sensor, a real-time clock, an audio
codec with mic and speaker, micro-SD, and battery operation. It has **no rotary
dial and no RFID**.

## Physical Display

The display is:

- Rectangular (square), 200 × 200 pixels
- Black and white only (treat as two tones; no color)
- Bistable — the last image stays visible with the power off
- Slow to refresh: ~2 s full refresh (with flashing), ~0.3 s partial refresh
- Highly legible in reflected light, with a wide viewing angle
- Prone to **ghosting** after many partial refreshes

Design within these realities. Favor strong black-on-white contrast, clear
typography, and layouts that change a small region at a time.

## Core Interaction Model

This device is primarily a **display**, not a rich input surface. Plan the
interaction around its real inputs:

### Buttons

PWR and BOOT are the always-available physical inputs. Use them for a small
number of clear actions: wake, next page, confirm, or toggle a mode. Keep button
roles consistent across screens and label them on-screen when helpful.

### Touch (touch variant only)

On the touch variant, design large, well-spaced tap targets and simple gestures.
Because redraw is slow, a tap should update only the affected region with a
partial refresh, and the design must tolerate ~0.3 s feedback latency. Never rely
on touch for the non-touch variant.

### Connected control (Wi-Fi / BLE)

For richer control, the natural pattern is to drive the device from a phone or a
small web page over Wi-Fi/BLE, while the e-paper shows the resulting state. Design
the on-device screen as the **output**, and put complex controls in the companion
app or web UI.

### Time- and event-driven updates

Much of the experience is automatic: the RTC wakes the device, it reads a sensor
or fetches data, refreshes the screen, and sleeps. Design the **states** the
screen rests in, not a moment-to-moment interaction loop.

## Visual Design Direction

The interface should be:

- High contrast (pure black on white)
- Glanceable and legible at arm's length
- Calm and static — content that looks intentional when frozen for minutes
- Organized so only a small region changes between updates

Prefer:

- One dominant value or message per screen (large numerals or short text)
- Clear typographic hierarchy and generous spacing
- Bold icons, rules, and frames that render well in 1-bit
- Dithering or hatching, used sparingly, to suggest a mid-tone
- Static progress as discrete segments rather than smooth fills

Avoid:

- Color as meaning (there is none)
- Fine gray gradients, photographic detail, or thin hairlines
- Animation, smooth scrolling, spinners, or live tickers
- Dense tables and tiny text
- Designs that require frequent full-screen redraws

## Typography

Use short, plain text. Recommended hierarchy:

- Primary value or message: very large
- Title or label: medium
- Secondary status: small but still high-contrast

Limit line length and prefer a few short lines. Make units distinct but readable
(e.g. `22 °C`, `48 %`, `09:41`, `2026-06-28`). Use a bitmap-friendly or clean
sans typeface that stays crisp at 1-bit.

## Iconography and Tone

Use solid, high-contrast icons with clear silhouettes. Reserve outlines for
secondary meaning. Because there is no color, distinguish states with shape,
fill, position, frames, or a small text label — never by hue alone.

## Feedback and Sound

The board has an audio codec, microphone, and a speaker connector, so audible
feedback (a tone, a chime, an alert) is possible when a speaker is attached.
Keep it short and purposeful. Do not design around music or speech quality.
Visual confirmation should not depend on a speaker being present.

## Supported Device Functions (for design)

### Display

Designs may use full and partial refresh, 1-bit graphics, large type, icons,
frames, QR codes, and simple segmented charts. Plan a periodic full refresh to
clear ghosting and design that flash moment to look intentional.

### Buttons

Press, long press, and wake-from-sleep are available. Keep to a few consistent
actions and show them on screen.

### Touch (variant)

Large tap targets, simple taps and holds, region-level updates. Tolerate slow
feedback. Provide a non-touch path for the non-touch variant.

### Wi-Fi

2.4 GHz for weather, smart-home/MQTT, Home Assistant, API status, time sync, and
remote configuration. Design disconnected, connecting, connected, stale-data, and
error states. No 5 GHz.

### Bluetooth Low Energy

BLE for phone-controlled setup, sensor/status services, beacons, and provisioning
before Wi-Fi exists. Design discovery, pairing, connected, and disconnected
states. **BLE only** — no Bluetooth Classic audio or serial.

### Sensors and Clock

SHTC3 temperature/humidity and PCF85063 RTC support readouts, trends, clocks,
alarms, countdowns, and scheduled wake. Make the last-updated time clear when data
can be stale.

### Audio

Short tones/alerts and basic recording/playback with a connected speaker; design
audio as optional reinforcement, not the main channel.

### Micro-SD

Images, fonts, logs, and configuration can come from SD. Design for a card being
absent or unreadable.

### Battery, Sleep, Power

Design for battery life: show battery and charging status, prefer "update then
sleep," and rely on the persistent image while asleep. Indicate when data on
screen may be old because the device has been sleeping.

The board runs untethered on a LiPo battery, but the *firmware* must hold the
battery power latch on or the device powers off the moment USB is unplugged (an
implementation requirement, not a design constraint — but it means "works on
battery" must be explicitly engineered, and a design can't assume the device
stays alive off-USB unless that's been built and verified).

**Battery life shapes the whole concept — ask for the target early.** A design
that stays connected and updates live lasts only **hours**; a design that sleeps
and wakes occasionally lasts **weeks to months**. These are different products,
so confirm the desired runtime up front and design the interaction to match
(e.g. an always-live remote vs. a wake-on-button frame that's reachable over
Bluetooth only briefly). Lean on the e-paper's zero-power image retention: a
glanceable frame can sleep almost all the time and still always show something.

## Designable Product Concepts

- Desk clock / calendar with alarms
- Room temperature & humidity monitor
- Weather or air-quality status panel (data over Wi-Fi)
- Smart-home / Home Assistant status display
- Meeting-room or desk-availability sign
- Name badge / status tag (bistable, near-zero idle power)
- Price, queue, CI, or KPI status board refreshed periodically
- BLE sensor with a companion-phone setup screen
- QR / ticket / boarding-style code display from SD or network
- Simple logger with an on-screen summary

## Recommended Screen Patterns

### Single Big Value

One large number or short message centered, a small label, and a last-updated
time. Update only the value region with partial refresh.

### Status Panel

One dominant status plus two or three small secondary fields (e.g. temperature,
humidity, time, battery). Refresh fields individually; full-refresh occasionally.

### Clock / Calendar

Large time, smaller date, optional next-alarm line. Partial-refresh the minute;
full-refresh on the hour to clear ghosting.

### Paged Information

A few static pages (clock, weather, sensor, info) advanced by a button or a tap.
Each page is a full-refresh; within a page, update regions partially.

### Connected Setup

Show clear connection state and instructions; put the actual controls in a
companion app or web page and reflect the result on the e-paper.

### Badge / Sign

A composed static layout meant to stay frozen for long periods. Optimize purely
for legibility and a clean single refresh.

## Important Limitations

- The screen is 200 × 200, **black and white**, and refreshes slowly.
- Frequent updates cause ghosting; periodic full refresh is required.
- No animation, video, smooth scrolling, or live tickers.
- No color — never encode meaning in hue.
- No rotary dial and no RFID on this board.
- Touch exists only on the touch variant.
- Audio is limited and optional; not a speaker-grade music device.
- Limited microcontroller memory and storage versus a phone.
- No built-in camera, GPS, cellular modem, or Ethernet.
- Bluetooth Classic is unavailable; Wi-Fi is 2.4 GHz only.
- Real sensing beyond temperature/humidity, and any actuation, needs external
  hardware.
- Battery life depends on refresh frequency, wireless/audio use, and sleep design.
- Installing different firmware normally replaces the current experience.

## Design Deliverables Expected from Claude Design

When asked to design an experience for this device, produce:

- The product purpose and primary user task
- Screen inventory
- Navigation flow (buttons, touch where present, companion app/web where used)
- Button, touch, and connected-control behavior
- Resting states: normal, updating, stale/old-data, connecting, connected,
  disconnected, low battery, error, and empty
- 1-bit, high-contrast layout that tolerates slow refresh and ghosting
- Typography hierarchy and icon direction
- Refresh strategy (which regions are partial, when a full refresh happens)
- Wi-Fi, BLE, sensor, time, battery, audio, or SD states when relevant
- Practical limitations and assumptions
- A clear handoff description of every screen and state

Do not produce code unless separately requested. Do not assume unsupported
sensors, color, fast refresh, or connectivity that the board lacks.

## Document Reference Locations

Local references:

- This Claude Design brief: `ESP32S3-ePaper154_ClaudeDesign_Specification.md`
- General device capability specification: `ESP32S3-ePaper154_Functional Specification.md`
- General AI capability reference: `ESP32S3-ePaper154_AI_Specification.md`
- Development findings: `ESP32S3-ePaper154_Development Log.log`
- Method: `Make Spec.md`
- Project instructions: `Project instruction.md`

Official product references (review dates 2026-06-28 / 2026-06-29):

- Product page: https://www.waveshare.net/shop/ESP32-S3-ePaper-1.54.htm
- Official documentation (all SKUs + V1/V2):
  https://docs.waveshare.net/ESP32-S3-ePaper-1.54/?variant=ESP32-S3-Touch-ePaper-1.54
- Wiki (V2, non-touch): https://www.waveshare.net/wiki/ESP32-S3-ePaper-1.54-V2

Note: the unit on hand is hardware version **V2**. The touch vs non-touch SKU is
not yet confirmed — design for both the **touch** and **non-touch** interaction
models until the variant is verified.
