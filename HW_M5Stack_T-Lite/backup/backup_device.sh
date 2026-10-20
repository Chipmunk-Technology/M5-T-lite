#!/usr/bin/env bash
#
# Full-flash backup for the M5Stack T-Lite (ESP32-PICO-D4, documented 4 MB).
#
# Basic first step of Make Spec.md. Run BEFORE flashing or erasing.
# Reading flash does not erase the device.
#
# Usage:
#   ./backup_device.sh
#   ./backup_device.sh /dev/cu.usbserial-XXXX
#   FLASH_SIZE=4194304 ./backup_device.sh
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

if "$ESPTOOL" version 2>/dev/null | grep -q 'v5\.'; then
  CMD_FLASH_ID="flash-id"
  CMD_READ_FLASH="read-flash"
else
  CMD_FLASH_ID="flash_id"
  CMD_READ_FLASH="read_flash"
fi

PORT="${1:-}"
if [ -z "$PORT" ]; then
  for p in /dev/cu.usbserial* /dev/cu.wchusbserial* /dev/cu.SLAB_USBtoUART* /dev/cu.usbmodem*; do
    [ -e "$p" ] && PORT="$p" && break
  done
fi

if [ -z "$PORT" ] || [ ! -e "$PORT" ]; then
  echo "ERROR: No USB serial port found."
  echo "  - Plug the T-Lite into USB-C with a data cable (not charge-only)."
  echo "  - On macOS the port is usually /dev/cu.usbserial-XXXX."
  echo "  - If nothing appears, install the driver named in the StickC-Plus"
  echo "    docs (FTDI VCP). The device is often called \"M5Stack\" or \"USB Serial\"."
  echo "  - List candidates with:  ls /dev/cu.*"
  exit 1
fi
echo "Using port: $PORT"

STAMP="$(date +%Y-%m-%d)"
BIN="t-lite-full-flash-${STAMP}.bin"
INFO="t-lite-backup-info-${STAMP}.txt"

echo "== Reading chip id =="
$ESPTOOL --port "$PORT" "$CMD_FLASH_ID" | tee "$INFO"

SIZE="${FLASH_SIZE:-}"
if [ -z "$SIZE" ]; then
  DETECTED="$(grep -iEo 'Detected flash size: *[0-9]+MB' "$INFO" | grep -iEo '[0-9]+' | head -1 || true)"
  if [ -n "$DETECTED" ]; then
    SIZE=$((DETECTED * 1024 * 1024))
  else
    echo "Could not auto-detect flash size; defaulting to 4 MB (documented for T-Lite)."
    SIZE=$((4 * 1024 * 1024))
  fi
fi
echo "Backing up $SIZE bytes of flash to $BIN"

echo "== Reading flash (non-destructive) =="
# 115200 is the safe read rate used on the paired ATOM Matrix USB-UART.
# This T-Lite has not been measured. Do not raise the baud until a read succeeds.
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
