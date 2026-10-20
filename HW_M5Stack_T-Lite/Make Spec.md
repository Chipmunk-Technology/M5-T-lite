# M5Stack T-Lite — Check, Test, and Specification Method

## Purpose

研究、測試或寫下 T-Lite 的一項功能時，用這份文件。

目標是讓規格來自證據。一項功能的路徑是：文件，可編譯的測試，刷進裝置的測試，最後在實機上看到結果。做不到最後一步時，停在對應的證據等級，不往上標。

這份方法對齊 `../WorkTemplate/Make Spec.md`，改成這台熱像裝置與「熱記憶」工作站。

## Basic First Step — Back Up the Device

**在任何其他工作之前，在任何刷寫或抹除之前，做全閃存備份。**

出廠韌體在被讀下來之前無法復原。步驟在 `backup/`：

1. 讀 `backup/README.md`。
2. 用 USB-C 資料線接上裝置。
3. 執行 `backup/backup_device.sh`（只讀，不抹除）。
4. 確認 `backup/SHA256SUMS` 記了新映像。

備份不存在或核對失敗時，停止。裝置還沒接上時，停在這一步，請人接上。截至 2026-10-20，備份未做。

## Basic Second Step — Characterize the Factory Firmware from the Backup

備份核對之後、**刷任何東西之前**，只讀 `.bin`，寫出這台裝置出廠時的應用。每個新板子做一次。

ESP-IDF 常見配置（偏移以這顆板子的分割表為準，不先假設）：

1. 解析 `0x8000` 的分割表（32-byte 一筆，magic `0xAA50`）。記下名稱、類型、偏移、大小、有沒有 OTA、有沒有資料分割區。
2. 每個 app 分割區讀 `esp_app_desc_t`（映像以 `0xE9` 開頭，magic `0xABCD5432` 在 24-byte 檔頭加 8-byte 段頭之後）。取出專案名、版本、建置時間、ESP-IDF 版本、secure version。
3. 對 app 區做 `strings -n 5`，看它初始化了什麼：MLX90640、LCD、AXP192、蜂鳴器、Wi-Fi、EZData、本機網頁。畫面上的字串照原文留下。
4. GPIO 與 I²C 位址以原理圖或官方範例為準，不從字串猜測。
5. 寫成對的 Factory 規格（備份存在之後才建立）：
   - `Factory TLite_App_Functional Specificaton.md`
   - `Factory TLite_App_Programming Specificaton (AI).md`
6. 證據標成 `PARTIAL`（來自映像，不是開機日誌，也不是人眼看到的畫面）。串列開機日誌與實機觀察都對上之後，才在兩份檔與 Development Log 改成 `DEVICE VERIFIED`。

`Factory …` 描述**這台裝置裡那份韌體**。沒有 Factory 前綴的規格描述**這塊板子與熱記憶工作站可以被做成什麼**。兩套分開。

## Required Reading

1. `Project instruction.md`
2. `TLite_AI_Specification.md`
3. `TLite_Functional Specification.md`
4. 做介面時讀 `TLite_ClaudeDesign_Specification.md`
5. `TLite_Development Log.log` 裡相關的舊紀錄
6. 任何韌體動作之前讀 `backup/README.md`
7. `NextSteps.md`

## Evidence Levels

只用這些標籤：

- `DOCUMENTED`：官方規格、資料手冊、函式庫或範例寫了，本地還沒測。
- `BUILD VERIFIED`：測試韌體已對這塊板子編譯成功。
- `FLASH VERIFIED`：已上傳到目標裝置。
- `DEVICE VERIFIED`：在實機上看到預期行為，或由可靠的裝置輸出確認。
- `PARTIAL`：只過了一部分，或驗證中斷。
- `FAILED`：沒有得到預期結果。

原始碼、編譯成功、推測，都不能標成 `DEVICE VERIFIED`。

## End-to-End Workflow

### 1. Define the Function

先寫短的測試定義：

- 功能名稱
- 人看得到的目的
- 輸入（Button A、電源鍵、USB 帧、網頁操作、感測器讀數）
- 預期的畫面、蜂鳴、網頁句子或序列輸出
- 限制（32×24、視角、精度、電池）
- 需要什麼額外設備（資料線、接觸式溫度計、暗房、已知溫差的門窗）

一次只測一個主要行為。

### 2. Check Existing Local Knowledge

先搜本地檔。穩定的問題不要重複上網。API、函式庫版本或本地規格不完整時，才查現行官方來源。

### 3. Verify the Target Device

刷寫或讀取之前：

- 確認是 **T-Lite / StickC-Plus + MLX90640**，不是 ATOM、Dial 或 ESP32-S3 e-paper。
- 重新偵測序列埠。
- 用 `esptool flash-id` 確認目標是 ESP32、flash 大小與文件一致（文件為 4 MB）。
- 確認沒有別的程式占著埠。
- 確認全閃存備份存在且 SHA-256 通過。

進不了下載模式時：按住前方 Button A 不一定是下載鍵。StickC-Plus 的下載通常靠 USB-UART 自動重設。若自動重設失敗，查當時的 M5 文件再動作，不依別塊板子的 BOOT 手順硬套。

### 4. Establish Acceptance Criteria

可觀察的通過與失敗。

序列幀：

- 接上後數秒內開始送出完整幀。
- 一幀有 768 個溫度，加上感測器環境溫度、序號、時間。
- 拔線後網頁說已斷線，不繼續顯示舊幀當成即時。

溫度合理性：

- 對準已知接近室溫的高發射率表面（紙、塗裝牆），讀數落在接觸式溫度計的可說明範圍內。範圍用這次實測寫下來。
- 對準明顯更熱的物體（溫水容器外壁、開機中的電源），最高溫高於背景。
- 光亮金屬的畫面寫出不可靠，不給一個看起來很準的數字。

熱記憶：

- 握穩約兩秒後留下一幀，並能用名字存起來。
- 晃動時畫面說「請握穩」，該段不寫成記憶。
- 同一名字的下一次讀數，第一句是與上一筆的差。
- PDF 含材料、發射率、反射溫度、距離選項、裝置識別，以及「篩查用，非計量追溯」。

漏熱：

- 室內外溫差約 10°C 以上時，比周圍冷或熱的一段被標出，句子給出溫差。
- 溫差不夠時，第一句是「現在溫差不夠」，不標出一段假縫。
- 牆後管線的句子帶「可能」。

熱哨兵：

- 全黑房間，人用走、快走、近距離揮手各通過多次，記錄觸發率。
- 空房間接 USB 跑整夜，記錄誤報次數。整夜測試用 USB 供電，不靠 160 mAh 電池撐整夜。
- 有暖氣的房間、有陽光直射的房間各測一次。忽略區畫上之後，該區不再觸發。
- 電腦拔掉、裝置改接行動電源後，仍會因暖物經過響一聲。
- 同一個人站著不動時不連續響。
- 蜂鳴是短音。規格維持「提示」，不測成防盜警報。

這些場景在實測完成前都是 `DOCUMENTED`。

### 5. Create a Minimal Test

小的、可回復的韌體測試：一次一項、序列或小螢幕上看得到成功與失敗、不帶多餘的網路服務。

韌體放在有名字的子資料夾，並附短 README。不把真實密碼寫進原始碼。

### 6. Record the Environment

日期、框架與版本、板子、函式庫、編譯器、序列埠、建置指令、燒錄指令、韌體位置、外部設備。寫進 `TLite_Development Log.log`。

### 7. Build Before Flashing

先在本地編譯。記憶體、分割區、棄用 API 的警告當成發現。目標板、flash 大小或分割表不對就不刷。編譯成功只標 `BUILD VERIFIED`。

### 8. Flash Carefully

- 刷之前再確認一次埠。
- 先確認備份存在且核對通過。
- 關掉其他序列工具。
- 用破壞最小的上傳。
- 不整片擦除，除非這次測試必須且已寫進紀錄。
- 不改 eFuse。
- 記下是否覆蓋了目前韌體。
- 上傳成功只標 `FLASH VERIFIED`。

### 9. Observe the Physical Device

能同時看的就同時看：135×240 螢幕、Button A、蜂鳴、序列、網頁句子、溫度是否合理。

互動測多次，含邊緣：快步通過、人站著不動、暖氣開著、USB 拔除、低電量。代理人看不到、聽不到時，請使用者確認，或用可靠的序列與網頁輸出。不編造實機結果。

### 10. Diagnose Failures Systematically

分開階段：工具安裝、依賴、編譯、連線、燒錄、開機當機、按鍵、螢幕、蜂鳴、I²C 讀取 MLX90640、幀格式、網頁、電源。

一次只改一個變因。修完之後記下原因、改了什麼、為什麼有效、重測結果、這次修正是通用的還是只在這台環境。失敗紀錄留在 log 裡。

### 11. Classify the Result

全部通過才是 `DEVICE VERIFIED`。不完整是 `PARTIAL`。沒有做出來是 `FAILED`。其餘用 `DOCUMENTED`、`BUILD VERIFIED`、`FLASH VERIFIED`。寫下還剩什麼、下一個有用的測試是什麼。

### 12. Update the Specifications

- 技術證據追加到 `TLite_Development Log.log`。
- 穩定行為更新 `TLite_Functional Specification.md`。
- 穩定規則更新 `TLite_AI_Specification.md`。
- 改變設計可能或顯示限制時，更新 `TLite_ClaudeDesign_Specification.md`。
- 單次、不確定的觀察留在 log，重複出現再升進規格。
- 發現錯了就加更正。
- 規格底部保留文件參照位置。

## Development Log Entry Template

```text
================================================================================
YYYY-MM-DD HH:MM - Function or experiment name
Status: DOCUMENTED | BUILD VERIFIED | FLASH VERIFIED | DEVICE VERIFIED | PARTIAL | FAILED
================================================================================

Goal:
What should the device do?

Acceptance criteria:
- Observable pass condition 1
- Observable pass condition 2

Environment:
- Framework and version:
- Board/platform:
- Libraries:
- Firmware source:
- Serial port:
- Required equipment/software:

Commands:
- Build:
- Flash:
- Monitor/test:

Observed result:
What actually happened.

Failures/errors:
Exact messages or symptoms.

Diagnosis:
Likely or confirmed cause.

Solution:
Changes made and why.

Verification:
Retest result and evidence level.

Limitations/follow-up:
Anything unresolved or worth testing next.
```

## Specification Quality Checklist

- 寫的是 T-Lite（SKU K126，MLX90640-BAA，32×24，110°×75°）。
- 可程式行為與工作站行為分開寫，也寫在一起時標明哪一邊做。
- 板上就有的（蜂鳴器、按鈕、螢幕、電池）與要另接的（行動電源、接觸式溫度計）分開。
- Wi-Fi 寫成 2.4 GHz。藍牙寫成 4.2 Classic 與 BLE；第一版不用。
- 寫出解析度、視角、精度條件、刷新越快雜訊越大、玻璃擋住長波紅外。
- 限制寫在規格裡。
- `DOCUMENTED` 與本地實測不混在一起。
- 沒有密鑰。
- 備份與復原路徑是這份專案的 `backup/`。
- 規格底部有參照位置，引用的本地路徑都存在。
- Functional、AI、Claude Design 三份對能力與限制的說法一致。

## Key Reference Locations

- 專案規則：`Project instruction.md`
- 人讀規格：`TLite_Functional Specification.md`
- AI 規格：`TLite_AI_Specification.md`
- 介面規格：`TLite_ClaudeDesign_Specification.md`
- 實驗紀錄：`TLite_Development Log.log`
- 交接：`NextSteps.md`
- 備份：`backup/README.md`
- 備份腳本：`backup/backup_device.sh`
- 方法範本：`../WorkTemplate/Make Spec.md`
