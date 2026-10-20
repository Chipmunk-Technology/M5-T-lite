# Project Instructions — M5Stack T-Lite 熱記憶

## What this project is

把 **M5Stack T-Lite**（SKU K126，M5StickC Plus + MLX90640-BAA）做成一套插上 USB 就能用的本機系統，名稱是**熱記憶**。

第一版只有三項：

1. **熱記憶**：記住一件資產的熱，用一句人話說出這次比上次差幾度。
2. **漏熱與隱藏水管**：在溫差夠大時，標出比周圍冷或熱的一段。
3. **熱哨兵**：全黑環境裡，暖物經過就讓裝置自己響一聲蜂鳴。

電腦上的網頁負責句子、數字與報告。裝置負責量測；熱哨兵的判斷在裝置上完成，拔掉電腦仍會響。

## Read before doing any work

1. This file.
2. `Make Spec.md` — 證據等級、備份優先、驗收。任何測試從這裡開始。
3. `TLite_AI_Specification.md` — 之後開發時要遵守的事實與禁令。
4. `TLite_Functional Specification.md` — 人能讀的行為。
5. `TLite_ClaudeDesign_Specification.md` — 介面。不含接腳與程式。
6. `TLite_Development Log.log` — 已做過的結論、失敗與修正。
7. `NextSteps.md` — 現在停在哪一步。
8. `backup/README.md` — 任何韌體或復原動作之前。

## The basic first step: back up the device

出廠韌體在被讀下來之前無法復原。**在任何刷寫、抹除或修改之前，用 `backup/backup_device.sh` 做全閃存備份**（見 `backup/README.md`）。

截至 2026-10-20，這台裝置**尚未接上**，備份**未做**。可以準備工具，不可以刷機。

## Core rules

- 每次都重新偵測 USB 序列埠，不沿用上一次的埠名。
- 用 `Make Spec.md` 的證據標籤。文獻、規格書、官方頁是 `DOCUMENTED`。沒有在這台裝置上看見的行為，不寫成 `DEVICE VERIFIED`。
- 熱圖是 32×24。可以放大顯示，像素仍是像素。不做超解析度，不把讀數寫成校準證書。
- 系統不輸出誠信、情緒、壓力或說謊，不做人臉辨識，不追蹤人。
- 熱哨兵是近距離提示，不是保全警報。
- Wi-Fi 是 2.4 GHz。第一版的使用路徑是 USB，不要求使用者為裝置配網。
- 藍牙在這顆 ESP32-PICO-D4 上是 4.2，含 Classic 與 Low Energy。第一版不使用藍牙。
- 一次只驗一項行為。
- 不把 Wi-Fi 密碼、API 金鑰或私鑰寫進共享檔案。
- 不改 eFuse，不做不可逆的安全設定。
- 規格之間要一致。發現錯了就改正，不把已知的錯留在文件裡。

## Where things live

- 方法：`Make Spec.md`
- 規格：`TLite_*.md`
- 實驗紀錄：`TLite_Development Log.log`
- 備份與復原：`backup/`
- 交接：`NextSteps.md`
- 方法範本（別台裝置，只供對照寫法）：`../WorkTemplate/`
