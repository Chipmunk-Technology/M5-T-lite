# ePaperBLE — iOS companion app

SwiftUI + Core Bluetooth app for the WaveShare ESP32-S3-ePaper-1.54 running the
`firmware/ePaper_BLE` firmware.

- **Device tab:** connect over BLE; see live temperature, humidity, and time;
  set the device clock to the phone's time; rename the BLE device; view/set
  Wi-Fi (SSID/password), scan, and connect.
- **Picture tab:** pick a photo → it's auto-converted to **200×200 1-bit
  (dithered)** and uploaded over BLE to replace the on-device picture. Tap the
  device screen to switch between the info home screen and your picture.

## Files (all in `ePaperBLE/`)

| File | Role |
|---|---|
| `ePaperBLEApp.swift` | App entry + `TabView` |
| `BLEManager.swift` | Core Bluetooth client (scan/connect/read/notify/write, chunked upload) |
| `ImageConverter.swift` | Resize → grayscale → Floyd–Steinberg dither → pack to the e-paper byte layout |
| `InfoTabView.swift` | Tab 1 UI |
| `ImageTabView.swift` | Tab 2 UI |

The UUIDs in `BLEManager.swift` must match `firmware/ePaper_BLE/ePaper_BLE.ino`.

## The Xcode project is already generated and verified

`ePaperBLE.xcodeproj` is included and **compiles cleanly** (verified with Xcode
26.5 / iOS SDK; it also launches in the iOS Simulator). The Bluetooth permission
string and Info.plist are set up via `project.yml` — nothing to wire by hand.

### Run it on your iPhone (needed for real Bluetooth)

1. **Open** `ios/ePaperBLE.xcodeproj` in Xcode (double-click it).
2. **Signing:** select the **ePaperBLE** target → **Signing & Capabilities** →
   check *Automatically manage signing* → pick your **Team** (a free Apple ID
   works for a 7-day install). If the bundle id `com.example.ePaperBLE` is taken,
   change it to something unique.
3. **Connect your iPhone** with a cable, select it as the run destination (top
   bar), and press **▶ Run**.
4. On the phone the first time: **Settings → General → VPN & Device Management →
   trust your developer profile**, then re-run. Allow **Bluetooth** when asked.

> The **iOS Simulator has no Bluetooth**, so it will show "Bluetooth unavailable".
> Use a real iPhone to connect to the device.

### Regenerating the project (only if you change `project.yml`)

```sh
cd ios && xcodegen generate     # brew install xcodegen
```

## Using it

- Open the app near the powered-on device; the **Device** tab auto-connects to
  `ePaper-154` (or whatever you renamed it).
- **Set time:** tap *Set device time to now* — fixes the clock without Wi-Fi.
- **Rename:** the device **reboots** to apply a new BLE name; it reconnects after
  a few seconds.
- **Wi-Fi:** enter SSID/password → *Connect*; the status line shows the IP on
  success.
- **Picture:** Picture tab → *Choose photo* → preview shows exactly what the
  e-paper will display → *Send to e-paper*. The device switches to the picture;
  tap the screen to toggle back to the info home screen.

## Test without writing code (optional)

Before building the app you can verify the firmware with a free BLE app
(**nRF Connect** or **LightBlue**): connect to `ePaper-154`, find service
`f0a00000-…`, read the temperature/humidity characteristics, and write
`yyyy-MM-dd HH:mm:ss` to the time characteristic `f0a00003-…`.

## Notes / limitations

- BLE is point-to-point; one phone connects at a time.
- Wi-Fi password is sent over the BLE link — fine for home use; for stronger
  security, a future version can add BLE pairing/bonding or Espressif's encrypted
  Wi-Fi provisioning.
- The e-paper is 1-bit black/white at 200×200, so photos become dithered line
  art — high-contrast images and logos work best.
