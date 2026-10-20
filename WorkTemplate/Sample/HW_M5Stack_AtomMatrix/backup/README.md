# Flash Backup and Recovery — M5Stack ATOM Matrix

This folder holds a full-flash backup of the connected ATOM Matrix and the
tools to create and restore it. Read this before any firmware change.

Taking this backup is the first step of the Make Spec workflow
(`../../WorkTemplate/Make Spec.md`). Do it before flashing or erasing, so the
firmware currently on the board can be restored.

## Status

- Backup taken: **YES — 2026-09-24**, full 4 MB read, image checks out.
  - File: `atom-matrix-full-flash-2026-09-24.bin` (4,194,304 bytes)
  - SHA-256: `60987a9476bde5297ebd231649100452e1b0906d6460eb7c8fa959f88e041c57`
  - Device: ESP32-PICO-D4 revision v1.1, 4 MB flash, MAC `c8:85:41:68:92:14`
  - Port: `/dev/cu.usbserial-81524AF84F` (USB product `M5stack`, vendor `Hades2001`)
  - Bootloader magic `0xE9` at `0x1000`. Partition table magic `0xAA50` at `0x8000`.
- A read at 460800 baud failed with `Invalid head of packet`. The good image
  was read at **115200** baud. Use 115200 for restore as well.
- Direct USB-C worked. A hub in front of this cable did not enumerate.

Do not erase the flash. Flashing test firmware is safe only while this image
is kept.

## How to take the backup

1. Connect the ATOM Matrix with a USB-C **data** cable, directly if a hub
   has been unreliable.
2. Confirm a port exists:
   ```sh
   ls /dev/cu.*
   ```
   Expect an FTDI-style name such as `/dev/cu.usbserial-XXXX`. This board does
   not use the ESP32-S3 native USB port (`usbmodem`).
3. From this folder:
   ```sh
   ./backup_device.sh
   ```
4. Confirm the info file says **ESP32** (PICO-D4 class), not ESP32-S3, and
   that the flash size is **4 MB** unless `flash_id` reports otherwise.

Reading flash does not erase the device. It is safe to repeat.

## Verify

```sh
shasum -a 256 -c SHA256SUMS
```

## Restore (overwrites the device)

```sh
python3 -m esptool --port /dev/cu.usbserial-XXXX --baud 115200 \
  write-flash 0 atom-matrix-full-flash-<date>.bin
```

Confirm the port and the SHA-256 immediately before running.

## Notes

- Documented flash size is **4 MB**. Trust `flash_id` if it disagrees.
- The face button is the user button. It is not a download-mode button.
  Uploads normally use the USB-UART auto-reset. A small reset control is on
  the side of the case.
- If the port never appears, install the FTDI VCP driver. Official docs name
  the unrecognized device `M5Stack` or `USB Serial`.
- Do not modify eFuses.
- Do not copy Wi-Fi passwords out of a dump into shared files.

## Files

- `backup_device.sh` — one-command full-flash read.
- `atom-matrix-full-flash-<date>.bin` — created on the first successful run.
- `atom-matrix-backup-info-<date>.txt` — chip, MAC, flash size, port.
- `SHA256SUMS` — created on the first successful run.
