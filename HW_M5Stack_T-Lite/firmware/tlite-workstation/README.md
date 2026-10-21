# T-Lite 熱記憶韌體

M5StickC Plus（或 Plus SE）加 MLX90640。量測與熱哨兵在裝置上。網頁句子由 `bridge/` 經 USB 送回來，小螢幕只重複那一句。

- 板子設定對齊官方 T-Lite：`board = m5stick-c`，`espressif32@6.12.0`
- 分割表抄自這台 2026-10-20 的全閃存備份，不是別塊板子的表
- 工作站序列速率 460800。讀閃存備份仍用 115200
- 不使用 Wi-Fi、藍牙、IMU、麥克風、紅外發射、Grove

```text
pio run -e tlite
```

上傳會覆蓋目前的應用程式。先確認 `backup/SHA256SUMS`。不要整片擦除。復原用備份目錄裡的全閃存映像。

2026-10-20 `pio run -e tlite` 已通過。應用程式約 782 KB，落在 3 MB 槽裡。小螢幕字型是 efontCN_14。還沒上傳。實機上的句子、溫度與蜂鳴都還沒有 `DEVICE VERIFIED`。
