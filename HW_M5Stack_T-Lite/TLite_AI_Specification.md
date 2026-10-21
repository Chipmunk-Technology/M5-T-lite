# M5Stack T-Lite 熱記憶 — AI Specification

## Purpose

開發這份專案之前先讀本檔。穩定的事實以這裡為準。函式庫 API 可能已變、本檔沒有寫、或使用者要求對一下現況時，再查官方來源。

證據標籤的意思在 `Make Spec.md`。截至 2026-10-20，本檔的硬體句子是 `DOCUMENTED`。幀格式、門檻、蜂鳴節奏是**設計合約**，還沒有在裝置上跑過。不要把它們說成已測到的行為。

出廠映像已於 2026-10-20 讀下並寫入 `backup/SHA256SUMS`。覆蓋應用程式之前先核對那份雜湊。不要整片擦除，不要改 eFuse。

## Device Summary

這台已用 `flash-id` 讀到：ESP32-PICO-D4 revision v1.1，MAC `c8:85:41:68:87:70`，4 MB flash，FTDI `0403:6001` 在 COM5。其餘產品句子仍是 `DOCUMENTED`：

- SKU K126。M5StickC Plus 或 Plus SE，加 MLX90640-BAA HAT
- ESP32-PICO-D4，240 MHz，520 KB SRAM，文件 4 MB flash，無 PSRAM
- 熱像 32×24，FOV 110°×75°，目標 −40°C 至 300°C，感測器工作 −40°C 至 85°C
- NETD：資料手冊 0.1 K RMS @ 1 Hz。更快的刷新更吵
- 畫面精度只在感測器溫度穩定、物體填滿該像素 FOV 時成立。中間溫區約 ±1°C；極端更差；多年漂移資料手冊寫可再約 ±3°C
- LCD 135×240 ST7789v2
- USB-C 經 USB-UART。不能當原生 USB gadget，也不能靠 Web Serial 假設它是 CDC-ACM，除非埠已經出現且驅動正確
- 電池：T-Lite 頁 160 mAh @ 3.7 V；StickC-Plus 頁 120 mAh。不要寫死續航
- 官方韌體：`m5stack/M5StickC-Plus-TLite-FW`，PlatformIO `board = m5stick-c`，`espressif32@6.12.0`，版本字串在 2026-10-20 的 `platformio.ini` 為 0.0.15。它走 Wi-Fi AP 配網與區網 MJPEG。那不是第一版的使用路徑

Plus 與 Plus SE 官方韌體同一映像。Plus SE 沒有 IMU。不要讀 IMU 來判斷握穩。握穩用連續熱幀的差。

## Pins Worth Getting Right

來源是 StickC-Plus 文件的接腳表，`DOCUMENTED`，這台尚未點亮確認。HAT 占的是上方插座；側邊 Grove（G32 / G33）仍在，第一版不用。

| 功能 | GPIO | 注意 |
|---|---|---|
| 被動蜂鳴器 | G2 | 要自己產生音調。短音即可 |
| 紅外發射 | G9 | 第一版不用。不要拿來當按鍵 |
| 紅色 LED | G10 | 第一版不用它表達警報 |
| TFT MOSI / CLK / DC / RST / CS | G15 / G13 / G23 / G18 / G5 | ST7789v2 |
| Button A | G37 | 輸入。熱記憶裡等於「記住這一幀」 |
| 電源鍵 | G39 | 短按開機或重設，長按關機。不是第二個應用鍵 |
| 內部 I²C SCL / SDA | G22 / G21 | IMU、AXP192、RTC、以及 HAT 上的 MLX90640 走這條 |
| 麥克風 CLK / DATA | G0 / G34 | G0 是 strap。第一版不開麥克風 |
| Grove | G32、G33 | 第一版不接 |

MLX90640 的預設 I²C 位址是 0x33（Melexis）。連線後做一次掃描再依賴這個位址。不要在沒掃到時改別的位址去碰 AXP192（常見 0x34）或 BM8563。

G25 與 G36 在 StickC-Plus 上共用一個埠。第一版不要去設定它們。

## Pixel Geometry

半視角 55° 與 37.5°。橫向視野寬度 = `2 * d * tan(55°)` ≈ `2.856 * d`。一格橫向 ≈ `0.089 * d`（距離的 9%）。

用這個式子產生「再靠近」與報告上的那一行小字。不要另造一個像素尺寸。

## Radiometry

- 連線時讀一次 EEPROM 校正區塊，跟裝置記錄一起留在電腦。以後才重算得了。
- 每一幀在電腦保存：768 點、感測器環境溫度 Ta、Vdd、當時的材料與發射率、反射溫度、序號、裝置時間或電腦時間、子頁是否已經合成為完整幀。
- 溫度用 0.01°C 的整數存。不要只存上色後的 PNG。
- 材料起點（慣用值，不是這台的校正）：塑膠 0.95、塗裝金屬 0.92、電路板 0.95、水 0.96。光亮金屬不套一個假精度，句子固定為不可靠。
- 反射溫度預設等於當下的 Ta。進階才讓人改。
- 棋盤模式：暫存器刷新率是子頁率。完整幀率約為其一半。熱記憶的取樣目標是約 4 張完整幀每秒（暫存器 8 Hz 這一檔，待實測）。熱哨兵預設同一檔。人走得太快而漏抓時，才試 16 Hz 子頁，並把雜訊寫進 log。不要把 32 Hz 或 64 Hz 當工作模式。

## USB Frame Contract

這是韌體與 `bridge/protocol.py` 共用的設計合約，還沒在這台裝置上跑過。二進位、小端序。每一包結尾是 CRC-16/CCITT-FALSE（多項式 0x1021，初值 0xFFFF），範圍是 CRC 之前的全部位元組。工作站速率 460800。讀閃存備份仍用 115200。

裝置送出的完整幀，魔數 `TL01`，版本 1，標頭 36 位元組，接著 768 個 int16（0.01°C），再加 2 位元組 CRC。標頭欄位依序是：版本、旗標、標頭長度、序號、毫秒時間、Ta、Vdd（0.01 V）、發射率千分位、反射溫度、哨兵峰值溫差、觸發格數、靈敏度、電量百分比、工作模式、已安靜的分鐘、事件經過秒數。

旗標：完整幀、子頁、哨兵事件、Button A、守候已開啟、保存的舊事件。靈敏度 0 高、1 中、2 低。

另外兩種裝置封包：`TL0H` 帶 MAC 與 832 個 EEPROM 字；`TL0M` 帶守候開關、靈敏度、工作模式與 96 位元組忽略遮罩。

電腦送 `TL0C`：設定守候、遮罩、發射率、螢幕句子、工作模式、PING。

電腦是唯一的分析端，除了熱哨兵的判斷。裝置在沒有電腦時仍要自己響，事件先留在裝置，連上再送。

序列埠由本機橋接程式独占。網頁只連 `127.0.0.1`。不要讓網頁直接開序列埠當成第一版的唯一路徑。

## Thermal Sentry Rules

判斷在裝置上，否則拔線就失效。

- 每格一個緩慢更新的背景。人站進畫面時，不要在幾秒內把人學成背景。室溫漂移要跟得上。時間常數從 30 秒這個設計起點開始測，不把它寫成最佳值。
- 三檔只改門檻與連續幀數，網頁不露出度數，除非進階：
  - 高：比背景高 2.0°C，連續 2 張完整幀
  - 中：高 3.0°C，連續 3 張（預設）
  - 低：高 5.0°C，連續 3 張
- 觸發後安靜 10 秒。這段時間同一區不再響。
- 觸發那一區加快併入背景，避免人站著不動時安靜結束又響。
- 忽略區是 32×24 的遮罩，存在裝置上，沒有電腦也有效。
- 蜂鳴：G2 短音兩下，然後停。不做連續警報音。
- 事件紀錄：時間、峰值溫差、觸發格數、該幀 768 點。不存身份，不做追蹤。

AXP192 必須在 USB 拔除後維持電池供電，否則「接行動電源仍會響」不成立。這是實作時要測的開機條件，官方 StickC 類板子有過未保持電源的情況。不要假設 `M5.begin()` 已經做對。

內部電池不作為整夜守候的電源。整夜誤報測試用 USB。

## Leak Rules

- 操作員把距離留在「房間」或自訂。
- 與鄰近區域的差約 10°C 以上，才標出一段並給溫差。
- 差不到時，第一句只說「現在溫差不夠」。
- 管線句子帶「可能」。
- 不輸出能耗、不輸出熱損失瓦數。

## Prohibitions

- 備份的 SHA-256 尚未通過時，不刷寫、不抹除、不改 eFuse。
- 不輸出誠信、情緒、壓力、說謊。有人要求測謊時，拒絕該功能，並指出 Functional 規格裡的幾何與精度理由。不做成「僅供娛樂的測謊」。
- 不做人臉辨識，不用熱圖追蹤特定的人。
- 不把插值或模糊說成更高解析度。
- 不把篩查讀數寫成校準證書。
- 不把 Wi-Fi 密碼寫進原始碼。
- 不依賴 IMU、麥克風、紅外發射、Grove。
- 不把熱哨兵寫成保全或防盜系統。

## Workstation Shape

```text
T-Lite --USB frames--> local bridge --WebSocket--> browser at 127.0.0.1
                         |
                         +--> SQLite：資產、命名幀、哨兵事件、EEPROM 複本
```

第一版沒有組織伺服器。橋接與網頁可以是同一個本機程序。儲存的是命名過的熱記憶，不是一堆未命名截圖。

## Programming

```text
PlatformIO board:  m5stick-c
Chip target:       esp32
Framework pin:     espressif32 6.12.0 when matching official T-Lite firmware
Library start:     M5Unified
Upload baud:       1500000 is what official platformio.ini sets;
                   fall back through the StickC-Plus list if upload fails
Backup read baud:  115200 until this unit proves faster
```

官方 `platformio.ini` 使用 `huge_app.csv`。自製哨兵韌體若要取代官方映像，先從備份裡的分割表確認，不要套用別塊板子的 CSV。

## How the AI Should Respond

- 先區分 `DOCUMENTED` 與這台還沒有的實測。
- 問到測謊、情緒、人是誰：說明幾何與精度，不做該功能。
- 問到畫面怎麼排：依 `TLite_ClaudeDesign_Specification.md`，一句話、一個數字、一張誠實的熱圖。
- 要刷機：先看 `backup/SHA256SUMS` 在不在。不在就停。
- 不把官方區網 MJPEG 說成已經滿足「只接 USB」。那要先配 Wi-Fi。

## Document Reference Locations

- 本檔：`TLite_AI_Specification.md`
- 人讀規格：`TLite_Functional Specification.md`
- 介面：`TLite_ClaudeDesign_Specification.md`
- 方法：`Make Spec.md`
- 備份：`backup/README.md`
- 紀錄：`TLite_Development Log.log`

審查日：2026-10-20。
