# 🕒 智慧鬧鐘系統（Smart Alarm Clock System）

## 📘 專案簡介
本專案設計一套可同時由「OLED 螢幕」與「手機網頁」操作的多組智慧鬧鐘系統。  
鬧鐘時間與音樂皆可透過 WiFi 網頁設定，並自動與 NTP 伺服器同步時間。  
當鬧鐘響起時，蜂鳴器播放指定旋律，同時網頁會出現「關閉 / 小睡 5 分鐘」控制選項。

---

## 🧩 系統架構
```text
使用者（手機 / 電腦）
   │
   │  Web 控制介面 (index.html)
   │
WiFi 通訊
   │
   ▼
ESP32-S2 mini
 ├── Web Server (uasyncio)
 ├── NTP 時間同步
 ├── 鬧鐘管理 (JSON 檔案)
 ├── OLED 顯示 (SSD1306)
 ├── 蜂鳴器 PWM 音樂播放
 └── 按鈕輸入 (短按 / 長按 / 雙擊)
```

---

## ⚙️ 軟硬體需求

### 🔧 硬體配置
| 元件名稱 | 功能 | 備註 |
|-----------|------|------|
| ESP32-S2 mini | 主控核心 | MicroPython 韌體 |
| OLED 128x64 (SSD1306) | 顯示時間 / 鬧鐘狀態 | I2C: SDA=Pin5, SCL=Pin7 |
| 蜂鳴器 | 音樂播放 | PWM: Pin6 |
| 按鈕 A / B | 鬧鐘設定控制 | GPIO34 / GPIO21 |
| 電源 | 5V USB | |

### 💻 軟體架構
| 檔案名稱 | 功能說明 |
|-----------|-----------|
| `alarm_clock.py` | 主程式，負責時間同步、鬧鐘檢查、OLED 顯示與 Web 控制 |
| `index.html` | 前端網頁介面，負責顯示時間、控制鬧鐘狀態 |
| `bitmap_font_tool.py` | OLED 中文字型繪圖模組 |
| `DebounceButton.py` | 防彈跳按鈕控制類別 |
| `alarm.txt` | 鬧鐘設定資料（JSON 格式） |

---

## 🧠 操作方式

### 🎮 OLED + 按鈕操作
| 模式 | 操作說明 |
|-------|-----------|
| 長按 A | 進入設定模式（日期 → 時間 → 音樂） |
| 長按 B | 檢視所有鬧鐘 |
| 雙擊 B | 刪除選取鬧鐘 |
| 鬧鐘響時 | 按 A → 小睡 5 分鐘；按 B → 停止響鈴 |

### 🌐 Web 控制
- 新增鬧鐘：選擇日期、時間、曲目 → 按下「新增鬧鐘」
- 關閉 / 小睡：鬧鐘響時網頁會彈出控制視窗

---

## 🚀 安裝與使用

### 1️⃣ 上傳程式至 ESP32
使用 [Thonny IDE](https://thonny.org/) 或 [ampy](https://github.com/scientifichackers/ampy)  
將以下檔案上傳至開發板：
```
alarm_clock.py
index.html
bitmap_font_tool.py
DebounceButton.py
```

### 2️⃣ 啟動系統
上電後自動：
- WiFi 連線（SSID、密碼於程式中設定）
- NTP 時間同步
- 啟動 Web Server（port 80）
- 顯示 IP 位址於 OLED

### 3️⃣ 開啟瀏覽器
輸入 OLED 顯示的 IP，如：
```
http://192.168.0.123
```
即可操作網頁介面。

---

## 📝 授權條款
本專案採用 **MIT License**  
可自由使用、修改與分發，但請保留原始作者資訊。

---

## ⭐ 特別感謝
- MicroPython 開發團隊  
- SSD1306 OLED 驅動程式  
- OpenAI ChatGPT 技術輔助  
