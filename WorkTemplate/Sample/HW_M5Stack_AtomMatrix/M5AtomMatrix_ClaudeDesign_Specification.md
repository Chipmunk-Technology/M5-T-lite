# M5Stack ATOM Matrix v1.1 Claude Design Specification

## Purpose

This is a design brief for interfaces and product concepts on the M5Stack
ATOM Matrix v1.1 (the connected unit, SKU C008-B-V11).

Design what the physical cube can show and how a person uses it. Do not put
source code, pin tables, or build steps in design output.

## Device Character

The ATOM Matrix is a tiny status cube, not a small phone. The whole product
face is 25 colour dots and one button. People understand it by colour,
position, blink, and motion of the cube itself.

It fits a remote, a beacon, a tilt control, or a pass/fail indicator. It does
not fit a page of text, a dashboard, or a multi-step form.

## Physical Display

- 5 columns by 5 rows
- Each pixel is one RGB LED
- The window is a small acrylic square on a 24 mm cube
- Pixels are large relative to the face, so a design is an icon, not a layout
- Brightness must stay modest. A design that needs all 25 pixels at full white
  is a hardware risk. Prefer a few lit pixels, or many pixels at a dim level.

There is no font size choice. A character is a 5×5 glyph, or a glyph that
scrolls across the face one column at a time. One glyph at a time is the
readable limit.

## Recommended Safe Areas

- Centre pixel: the main state (on, selected, alert)
- Middle 3×3: the icon
- Four corners: secondary status only if the icon does not need them
- Bottom row: connection or mode, when the upper 4 rows hold the icon
- One pixel of margin is often the whole margin. Do not draw a border and an
  icon; there is no room for both

## Core Interaction Model

### Press the face

The face is the button. Press is the confirmation.

- Single press: the primary action
- Double press: a second action, used sparingly
- Hold: a mode change or cancel

Every press needs an immediate pixel change. There is no click sound unless a
Grove buzzer is added, and that buzzer is an accessory.

### Tilt and shake

The cube knows tilt and sharp motion. Good uses:

- Tilt left or right to move a selection
- Face up or face down as a mode
- A shake as undo or wake

Show the result on the matrix in the same moment. Do not require a fine angle.
The sensor is not a compass, so do not design "point north."

### Infrared

The cube can send an infrared remote code. The person sees nothing leave the
cube, so the matrix must confirm "sent" with a short flash. The cube cannot
hear an incoming infrared signal.

### Connected status

Wi-Fi and Bluetooth are invisible. Spend one pixel, or one short colour, on
connection state. Suggested language, to be reused rather than restyled per
screen:

- Dim blue blink: Bluetooth waiting
- Solid blue: Bluetooth connected
- Green: Wi-Fi joined
- Red: failed or lost
- White flash: a momentary event (sent, confirmed)

Keep that language stable across the product.

## Visual Design Direction

Design in pixels, the way a 5×5 icon set is drawn.

- Use saturated colours at low brightness
- Use off-pixels as part of the icon
- Animate with one moving pixel or a 4-frame loop
- Do not depend on thin lines, anti-aliasing, or text labels
- Do not place two independent icons on the face at once

Colour is the label. If two states need the same shape, they need different
colours, not different words.

## Supported Device Functions

### Matrix

Icons, one glyph, a 5-step bar, a spinner, a flash. Not paragraphs, lists, or
photos.

### Button

One button. Primary, secondary, and hold. No keyboard.

### Motion

Tilt and shake as input. Orientation relative to gravity. No compass, no
"which way is north."

### Infrared

Outbound remote codes, with on-face confirmation. No inbound learning.

### Wi-Fi and Bluetooth

The cube can be a network device or a Bluetooth device (Low Energy, and
Classic when the product needs classic serial or a classic HID remote). The
face only reports state. Bluetooth on this chip is version 4.2. Wi-Fi is
2.4 GHz only. Configuration of passwords belongs on a phone or computer, not
on the 25 pixels.

Choosing a network is also a phone action. The phone asks the cube to scan
2.4 GHz networks and shows the names, signal, and whether each one asks for
a password. The face does not list SSIDs, does not show a picker, and does
not change its picture while the scan runs. Whatever the face was already
showing stays until some other command replaces it.

On the phone the control is one button, **Scan nearby networks**, in a
**Nearby networks** section. A row is the network name plus the signal number.
Tapping the row fills the name. The scan itself does not store names or
passwords.

### Power

The cube is plugged into USB-C. Designs that assume it lives in a pocket all
day need an external battery, which is not part of the product. When power is
removed, the face goes dark immediately. Nothing stays on the "screen."

### USB

USB is how the device is powered and programmed. It is not a user-facing
on-cube feature.

### Accessories

A Grove module can add a sensor, a buzzer, or a light. Design those only when
the concept includes the extra part. The stock cube has no speaker.

## Designable Product Concepts

- A one-button BLE trigger with three colours for idle, armed, and sent
- A tilt remote: lean to choose, press to confirm, four colours for four targets
- An infrared room remote: press sends the code, the centre pixel flashes white
- A join beacon: one pixel tells Wi-Fi or Bluetooth state, the 3×3 shows mode
- A pass/fail cube for a test jig: green face or red face, nothing else

## Patterns That Fit

### Single state

One colour across the 3×3, or one centre pixel. Label the meaning in the
product legend, not on the cube.

### Three-step choice

Three columns, one lit. Press accepts the lit column. Tilt moves it.

### Event flash

A short white or coloured flash over the current icon, then return. Use this
for send, success, and error. Errors should stay longer than successes.

### Connection pixel

Reserve the bottom-centre or bottom-corner pixel for radio state and do not
reuse it as part of the icon.

## Factory Firmware as a Design Reference

The app on this unit is a factory test named in the image as
`Atom Matrix Factory test`. What it draws on the LEDs was not recovered.
Do not treat a guessed animation as the current product UI. Serial behaviour
of that test is in the factory functional specification.

## Important Limitations

- 5×5 pixels, RGB, dim
- One button
- No speaker on the board
- No battery on the board
- No compass
- Infrared goes out only
- The face is blank when USB power is removed
- Text is one glyph at a time

## Design Deliverables Expected from Claude Design

- A pixel grid (5×5) for each state, with the colour of every lit pixel
- The press, double-press, hold, and tilt actions for that state
- The one-pixel radio language, used the same way in every state
- A note when a concept needs a Grove accessory or an external battery
- No mockups that show words on the cube unless each word is a sequence of
  5×5 glyphs

## Document Reference Locations

- This file: `M5AtomMatrix_ClaudeDesign_Specification.md`
- Human features: `M5AtomMatrix_Functional Specification.md`
- AI reference: `M5AtomMatrix_AI_Specification.md`
- Factory app: `Factory M5AtomMatrix_App_Functional Specificaton.md`

Official product page: https://docs.m5stack.com/en/core/Atom-Matrix_v1.1

Reference review date: 2026-09-24.
