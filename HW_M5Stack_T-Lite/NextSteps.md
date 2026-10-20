# Next Steps — M5Stack T-Lite 熱記憶

Updated: 2026-10-20

## Current state

- 規格套件已寫：`Project instruction.md`、`Make Spec.md`、三份 `TLite_*.md`、Development Log。
- 內容是文獻與產品設計，證據等級 **`DOCUMENTED`**。沒有這台裝置的實測。
- **全閃存備份未做。** 裝置當時沒有接上。`backup/backup_device.sh` 已準備好，只讀、不抹除。
- 沒有 Factory 規格。出廠畫面與選單等備份做出來再寫，不先猜。
- 沒有應用程式、沒有韌體專案。第一版的三項（熱記憶、漏熱與隱藏水管、熱哨兵）停在規格。

## Immediate next step

1. 用 USB-C 資料線把 T-Lite 直插電腦。
2. 讀 `backup/README.md`，執行 `backup/backup_device.sh`。
3. `shasum -a 256 -c backup/SHA256SUMS` 通過之後，才從映像描述出廠韌體。
4. 在那之前不刷寫、不抹除。

## After the backup verifies

- 寫 `Factory TLite_App_Functional Specificaton.md` 與 `Factory TLite_App_Programming Specificaton (AI).md`，狀態先標 `PARTIAL`。
- 最小測試：USB 送出一幀 768 點，網頁顯示一句話與一張不放大造假的熱圖。通過後，幀格式才離開純設計。
- 熱哨兵的實機驗收見 `Make Spec.md`：全黑通過測試、USB 供電的整夜誤報、拔掉電腦仍會響。整夜不靠內部電池。

## Recovery

尚無映像可還原。備份完成前，不要覆蓋官方韌體。
