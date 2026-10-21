# Next Steps — M5Stack T-Lite 熱記憶

Updated: 2026-10-20

## Current state

- 全閃存備份已核對：`backup/t-lite-full-flash-2026-10-20.bin`。晶片是 ESP32-PICO-D4，MAC `c8:85:41:68:87:70`。
- 工作站原始碼在 `firmware/tlite-workstation/` 與 `bridge/`。網頁三個畫面與三項工作都在橋接程序裡。熱哨兵判斷在韌體裡。
- `pio run -e tlite` 已通過。還沒上傳。上傳會覆蓋出廠應用程式。
- 出廠應用的 Factory 規格還沒從映像寫出。

## Immediate next step

1. 編譯已通過（`BUILD VERIFIED`）。還沒上傳。要覆蓋出廠應用程式時，先再核對 `backup/SHA256SUMS`，不要整片擦除。
2. 接上後開 `python bridge/server.py`（不要加 `--demo`）。看網頁是否在數秒內收到 768 點，以及小螢幕是否重複那一句。
3. 熱哨兵的實機驗收仍見 `Make Spec.md`：全黑、USB 整夜、拔掉電腦仍會響。

## Recovery

映像在 `backup/`。覆蓋應用程式之後，整片還原用 README 裡的 `write-flash`，速率先用 115200。
