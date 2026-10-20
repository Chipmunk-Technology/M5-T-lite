# Flash Backup and Recovery — M5Stack T-Lite

讀這份文件，再做任何韌體變更。全閃存備份是 `Make Spec.md` 的第一步。讀取不會抹除裝置。

## Status

- Backup taken: **NO — pending as of 2026-10-20.**
- 這台 T-Lite 當時沒有接在電腦上。沒有映像檔，沒有 SHA-256，沒有已核對的埠名。
- 在 `SHA256SUMS` 出現、而且 `shasum -a 256 -c SHA256SUMS` 通過之前，不刷寫、不抹除。

預期的硬體（全部是 `DOCUMENTED`，尚未在這台裝置上讀到）：

- 產品：T-Lite，SKU K126。M5StickC Plus（或 Plus SE）加上 MLX90640 HAT。
- SoC：ESP32-PICO-D4，文件寫 4 MB flash，無 PSRAM。以 `flash-id` 為準。
- USB：USB-C，經 USB-UART，不是 ESP32-S3 那種原生 USB。M5 文件要求安裝 FTDI VCP，未辨識時的名稱常是 `M5Stack` 或 `USB Serial`。實際橋接晶片等埠出現再記。
- 埠名每次重抓。常見形態是 `/dev/cu.usbserial-*` 或 `/dev/cu.wchusbserial-*`，不是 `/dev/cu.usbmodem*`。

## How to take the backup

1. 用 USB-C **資料線**直插電腦。集線器不穩時就不要經過集線器。
2. 確認埠存在：

   ```sh
   ls /dev/cu.*
   ```

3. 在這個資料夾執行：

   ```sh
   ./backup_device.sh
   ```

4. 確認 info 檔寫的是 **ESP32**（PICO-D4 這一類），不是 ESP32-S3，而且 flash 是 **4 MB**，除非 `flash-id` 報了別的大小。

讀取可以重做。它不擦除裝置。

## Verify

```sh
shasum -a 256 -c SHA256SUMS
```

## Restore (overwrites the device)

先確認埠名與 SHA-256。預設用 115200，因為同一類 M5 USB-UART 在較高讀取速率上出過 `Invalid head of packet`。這台 T-Lite 的可用速率尚未量到；上傳文件允許 115200、250000、500000、750000、1500000，那是上傳，不是讀取已驗證。

```sh
python3 -m esptool --port /dev/cu.usbserial-XXXX --baud 115200 \
  write-flash 0 t-lite-full-flash-<date>.bin
```

## Notes

- 側邊電源鍵長按關機，短按開機或重設。Button A 是前方的使用者鍵，不是下載模式鍵。一般上傳靠 USB-UART 自動重設。
- 若埠完全不出現，依 StickC-Plus 文件安裝 FTDI VCP。驅動要裝的晶片以系統看到的為準。
- 不改 eFuse。
- 不把 dump 裡的 Wi-Fi 密碼抄進共享檔案。
- 官方韌體倉庫是 `m5stack/M5StickC-Plus-TLite-FW`。在備份核對完成前，不用它覆蓋這台裝置。

## Files

- `backup_device.sh` — 一鍵全閃存讀取。
- `t-lite-full-flash-<date>.bin` — 第一次成功後才會出現。
- `t-lite-backup-info-<date>.txt` — 晶片、MAC、flash 大小、埠。
- `SHA256SUMS` — 第一次成功後才會出現。
