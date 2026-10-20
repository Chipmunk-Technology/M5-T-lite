#!/usr/bin/env bash
#
# Full-flash backup for the M5Stack ATOM Matrix (ESP32-PICO-D4, 4 MB flash).
#
# This is the basic first step of the Make Spec workflow. Run it BEFORE
# flashing, erasing, or otherwise modifying the device, so the firmware that
# is on the board today can always be restored.
#
# What it does:
#   1. Detects the USB serial port (FTDI bridge: usbserial / wch / SLAB).
#   2. Reads the chip ID, MAC, and flash size with esptool.
#   3. Dumps the ENTIRE flash to a timestamped .bin in this folder.
#   4. Records a SHA-256 checksum and a small info file.
#
# It never erases or writes the device. Reading flash is non-destructive.
#
# Usage:
#   ./backup_device.sh                      # auto-detect port and flash size
#   ./backup_device.sh /dev/cu.usbserial-XXXX
#   FLASH_SIZE=4194304 ./backup_device.sh   # force 4 MB if detection fails
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

ARDUINO_ESPTOOL="$HOME/Library/Arduino15/packages/esp32/tools/esptool_py/5.3.0/esptool"
if command -v esptool.py >/dev/null 2>&1; then
  ESPTOOL="esptool.py"
elif command -v esptool >/dev/null 2>&1; then
  ESPTOOL="esptool"
elif [ -x "$ARDUINO_ESPTOOL" ]; then
  ESPTOOL="$ARDUINO_ESPTOOL"
else
  ESPTOOL="python3 -m esptool"
fi
echo "Using esptool: $ESPTOOL"

# esptool v5 uses hyphenated commands; v4 uses underscores.
if "$ESPTOOL" version 2>/dev/null | grep -q 'v5\.'; then
  CMD_FLASH_ID="flash-id"
  CMD_READ_FLASH="read-flash"
else
  CMD_FLASH_ID="flash_id"
  CMD_READ_FLASH="read_flash"
fi

PORT="${1:-}"
if [ -z "$PORT" ]; then
  # ATOM Matrix uses a USB-UART bridge (documented as FTDI), not native USB.
  for p in /dev/cu.usbserial* /dev/cu.wchusbserial* /dev/cu.SLAB_USBtoUART* /dev/cu.usbmodem*; do
    [ -e "$p" ] && PORT="$p" && break
  done
fi

if [ -z "$PORT" ] || [ ! -e "$PORT" ]; then
  echo "ERROR: No USB serial port found."
  echo "  - Plug the ATOM Matrix into USB-C with a data cable (not charge-only)."
  echo "  - On macOS the port is usually /dev/cu.usbserial-XXXX (FTDI)."
  echo "  - If nothing appears, install the FTDI VCP driver. The device name"
  echo "    in system tools is often \"M5Stack\" or \"USB Serial\"."
  echo "  - List candidates with:  ls /dev/cu.*"
  exit 1
fi
echo "Using port: $PORT"

STAMP="$(date +%Y-%m-%d)"
BIN="atom-matrix-full-flash-${STAMP}.bin"
INFO="atom-matrix-backup-info-${STAMP}.txt"

echo "== Reading chip id =="
$ESPTOOL --port "$PORT" "$CMD_FLASH_ID" | tee "$INFO"

SIZE="${FLASH_SIZE:-}"
if [ -z "$SIZE" ]; then
  DETECTED="$(grep -iEo 'Detected flash size: *[0-9]+MB' "$INFO" | grep -iEo '[0-9]+' | head -1 || true)"
  if [ -n "$DETECTED" ]; then
    SIZE=$((DETECTED * 1024 * 1024))
  else
    echo "Could not auto-detect flash size; defaulting to 4 MB (documented for ATOM Matrix)."
    SIZE=$((4 * 1024 * 1024))
  fi
fi
echo "Backing up $SIZE bytes of flash to $BIN"

echo "== Reading flash (non-destructive) =="
# 115200: this unit's USB-UART (product "M5stack", vendor Hades2001)
# drops packets at 460800 ("Invalid head of packet").
$ESPTOOL --port "$PORT" --baud 115200 "$CMD_READ_FLASH" 0 "$SIZE" "$BIN"

echo "== Checksums =="
if command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "$BIN" | tee -a SHA256SUMS
else
  sha256sum "$BIN" | tee -a SHA256SUMS
fi

{
  echo ""
  echo "backup_file: $BIN"
  echo "flash_bytes: $SIZE"
  echo "port_used: $PORT"
  echo "date: $STAMP"
} >> "$INFO"

echo ""
echo "DONE. Backup written to: $HERE/$BIN"
echo "Verify later with:  shasum -a 256 -c SHA256SUMS"
echo "Restore (DANGER, overwrites device) with:"
echo "  $ESPTOOL --port $PORT --baud 115200 write-flash 0 $BIN"
