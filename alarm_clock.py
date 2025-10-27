# ============================================================
# ESP32-S2 mini 多組鬧鐘系統 v2.6
# WiFi + NTP + Web + OLED + 長按切換模式 + Snooze + 5秒預聽
# CLOCK / SET_DATE / SET_TIME / SET_MUSIC / VIEW / RINGING
# 
# 操作規則：
#  長按A：CLOCK → SET_DATE → SET_TIME → SET_MUSIC → (長按A) 儲存鬧鐘 / (長按B) 取消鬧鐘
#  長按B：CLOCK → VIEW；在VIEW：
#           A = 上一個、B = 下一個、長按A = 開/關、雙擊B = 刪除、長按B = 返回主畫面
# ============================================================

# -------- 匯入必要模組 --------
import uasyncio as asyncio            # 非同步執行（可同時處理顯示、網頁、按鈕）
import ujson as json                  # JSON 檔案存取，用於保存鬧鐘資料
import network, ntptime, time         # WiFi 連線、NTP 校時、時間操作
from machine import I2C, Pin, PWM     # 硬體：I2C (OLED)、GPIO (按鈕)、PWM (蜂鳴器)
from ssd1306 import SSD1306_I2C       # OLED 顯示驅動
from bitmap_font_tool import set_font_path, draw_text  # 顯示中文字的工具
from DebounceButton import DebouncedButton              # 防彈跳按鈕類別

# -------- 設定字型路徑 --------
set_font_path('./lib/fonts/fusion_bdf.12')  # 請依實際字型路徑修改

# -------- 系統設定 --------
SSID = "WiFi SSID"               # WiFi SSID
PASSWORD = "WiFi 密碼"          # WiFi 密碼
ALARM_FILE = "alarm.txt"       # 鬧鐘資料檔案
TZ_OFFSET = 8 * 3600           # 台灣時區 (+8 小時)
SNOOZE_MIN = 5                 # 小睡時間（分鐘）
PREVIEW_SEC = 5                # 音樂預聽時間（秒）

# -------- 音樂設定 --------
# 標準西洋音階頻率對照（C4為中央C）
NOTE_FREQS = {
    # === 第3八度 ===
    'C3': 131,     # Do
    'C#3': 139, 'Db3': 139,   # Do#
    'D3': 147,     # Re
    'D#3': 156, 'Eb3': 156,   # Re#
    'E3': 165,     # Mi
    'F3': 175,     # Fa
    'F#3': 185, 'Gb3': 185,   # Fa#
    'G3': 196,     # Sol
    'G#3': 208, 'Ab3': 208,   # Sol#
    'A3': 220,     # La
    'A#3': 233, 'Bb3': 233,   # La#
    'B3': 247,     # Si

    # === 第4八度（中央C區） ===
    'C4': 262,     # Do
    'C#4': 277, 'Db4': 277,   # Do#
    'D4': 294,     # Re
    'D#4': 311, 'Eb4': 311,   # Re#
    'E4': 330,     # Mi
    'F4': 349,     # Fa
    'F#4': 370, 'Gb4': 370,   # Fa#
    'G4': 392,     # Sol
    'G#4': 415, 'Ab4': 415,   # Sol#
    'A4': 440,     # La
    'A#4': 466, 'Bb4': 466,   # La#
    'B4': 494,     # Si

    # === 第5八度 ===
    'C5': 523,     # Do
    'C#5': 554, 'Db5': 554,   # Do#
    'D5': 587,     # Re
    'D#5': 622, 'Eb5': 622,   # Re#
    'E5': 659,     # Mi
    'F5': 698,     # Fa
    'F#5': 740, 'Gb5': 740,   # Fa#
    'G5': 784,     # Sol
    'G#5': 831, 'Ab5': 831,   # Sol#
    'A5': 880,     # La
    'A#5': 932, 'Bb5': 932,   # La#
    'B5': 988,     # Si

    # === 第6八度（高音區） ===
    'C6': 1047,    # Do
    'C#6': 1109, 'Db6': 1109, # Do#
    'D6': 1175,    # Re
    'D#6': 1245, 'Eb6': 1245, # Re#
    'E6': 1319,    # Mi
    'F6': 1397,    # Fa
    'F#6': 1480, 'Gb6': 1480, # Fa#
    'G6': 1568,    # Sol
    'G#6': 1661, 'Ab6': 1661, # Sol#
    'A6': 1760,    # La
    'A#6': 1865, 'Bb6': 1865, # La#
    'B6': 1976,    # Si

    # === 休止符 ===
    'REST': 0      # 休止符（無聲）
}
# 每首曲子是一串 (頻率, 持續時間)
MUSIC_NAME = ["生日快樂", "給愛麗絲", "小蜜蜂", "快樂頌"]
MELODY = {
    0: [('C4', 350), ('C4', 150), ('D4', 500), ('C4', 500), ('F4', 500), ('E4', 900), ('REST', 100),
    ('C4', 350), ('C4', 150), ('D4', 500), ('C4', 500), ('G4', 500), ('F4', 900), ('REST', 100),
    ('C4', 350), ('C4', 150), ('C5', 500), ('A4', 500), ('F4', 500), ('E4', 500), ('D4', 900), ('REST', 100),
    ('Bb4', 350), ('Bb4', 150), ('A4', 500), ('F4', 500), ('G4', 500), ('F4', 1000)], 
    1: [('E5', 200), ('D#5', 200), ('E5', 200), ('D#5', 200), ('E5', 200), ('B4', 200), ('D5', 200), ('C5', 200), ('A4', 400), ('REST', 100),
    ('C4', 150), ('E4', 150), ('A4', 150), ('B4', 400), ('REST', 100),
    ('E4', 150), ('Ab4', 150), ('B4', 150), ('C5', 400), ('REST', 100),
    ('E5', 200), ('D#5', 200), ('E5', 200), ('D#5', 200), ('E5', 200), ('B4', 200), ('D5', 200), ('C5', 200), ('A4', 400)], 
    2: [('G4',300),('E4',300),('E4',300),('F4',300),('D4',300),('D4',300),
    ('C4',300),('D4',300),('E4',300),('F4',300),('G4',300),('G4',300),('G4',450),
    ('G4',300),('E4',300),('E4',300),('F4',300),('D4',300),('D4',300),
    ('C4',300),('E4',300),('G4',300),('G4',300),('E4',450),
    ('D4',300),('D4',300),('D4',300),('D4',300),('D4',300),('E4',300),('F4',450),
    ('E4',300),('E4',300),('E4',300),('E4',300),('E4',300),('F4',300),('G4',450),
    ('G4',300),('E4',300),('E4',300),('F4',300),('D4',300),('D4',300),
    ('C4',300),('E4',300),('G4',300),('G4',300),('C4',450)],
    3: [('E4',200),('E4',200),('F4',200),('G4',200),
    ('G4',200),('F4',200),('E4',200),('D4',200),
    ('C4',200),('C4',200),('D4',200),('E4',200),
    ('E4',400),('D4',400),('D4',400),
    ('E4',200),('E4',200),('F4',200),('G4',200),
    ('G4',200),('F4',200),('E4',200),('D4',200),
    ('C4',200),('C4',200),('D4',200),('E4',200),
    ('D4',400),('C4',400),('C4',400),
    ('D4',200),('D4',200),('E4',200),('C4',200),
    ('D4',200),('E4',200),('F4',200),('E4',200),
    ('D4',200),('E4',200),('F4',200),('E4',200),
    ('D4',200),('G4',400),('G4',400),
    ('E4',200),('E4',200),('F4',200),('G4',200),
    ('G4',200),('F4',200),('E4',200),('D4',200),
    ('C4',200),('C4',200),('D4',200),('E4',200),
    ('D4',400),('C4',400),('C4',400)],
}

# -------- 全域狀態變數 --------
oled = None                      # OLED 顯示物件
speaker = None                   # 蜂鳴器物件 (PWM)
alarms = []                      # 鬧鐘清單
is_ringing = False               # 是否正在響鈴
MODE = "CLOCK"                   # 當前模式
cursor_idx = 0                   # 設定畫面游標位置
view_idx = 0                     # 檢視鬧鐘索引
setting = {"y":0,"M":0,"d":0,"h":0,"m":0,"music":0}  # 暫存設定中的鬧鐘
_preview_task = None             # 音樂預聽任務
_last_rung_key = None            # 防止同一分鐘重複觸發鬧鐘

# ============================================================
# 公用函式區
# ============================================================

def taiwan_time():
    """取得台灣時區的時間 tuple"""
    return time.localtime(time.time() + TZ_OFFSET)

def fmt_date(y,M,d): return f"{y:04d}/{M:02d}/{d:02d}"  # 日期格式化
def fmt_time(h,m):   return f"{h:02d}:{m:02d}"           # 時間格式化

def next_alarm():
    """找出下一筆有效的鬧鐘（依時間排序）"""
    now = taiwan_time()
    key = (now[0], now[1], now[2], now[3], now[4])
    # 篩選未過期的鬧鐘
    future = [a for a in alarms if a.get("enabled", True) and (a["y"],a["M"],a["d"],a["h"],a["m"]) > key]
    return sorted(future, key=lambda x:(x["y"],x["M"],x["d"],x["h"],x["m"]))[0] if future else None

# ======== 增減欄位值 ========
def inc_field(k):
    """欄位加一（自動循環）"""
    if k=="y": setting[k]+=1
    elif k=="M": setting[k]=(setting[k]%12)+1
    elif k=="d": setting[k]=(setting[k]%31)+1
    elif k=="h": setting[k]=(setting[k]+1)%24
    elif k=="m": setting[k]=(setting[k]+1)%60

def dec_field(k):
    """欄位減一（自動循環）"""
    if k=="y": setting[k]-=1
    elif k=="M": setting[k] = 12 if setting[k]==1 else setting[k]-1
    elif k=="d": setting[k] = 31 if setting[k]==1 else setting[k]-1
    elif k=="h": setting[k] = 23 if setting[k]==0 else setting[k]-1
    elif k=="m": setting[k] = 59 if setting[k]==0 else setting[k]-1

# ======== 鬧鐘資料存取 ========
def load_alarms():
    """從檔案載入鬧鐘資料；若無檔案則建立空白檔"""
    global alarms
    try:
        with open(ALARM_FILE,"r") as f:
            alarms = json.loads(f.read())
        for a in alarms:  # 保險起見補欄位
            a.setdefault("enabled", True)
            a.setdefault("music", 0)
    except:
        alarms = []
        with open(ALARM_FILE,"w") as f:
            f.write("[]")

def save_alarms():
    """將目前鬧鐘清單寫入檔案"""
    with open(ALARM_FILE,"w") as f:
        f.write(json.dumps(alarms))

def add_alarm(y,M,d,h,m,music):
    """新增一筆鬧鐘"""
    alarms.append({"y":y,"M":M,"d":d,"h":h,"m":m,"music":music,"enabled":True})
    save_alarms()

def switch_alarm(i):
    """切換鬧鐘開/關狀態"""
    if 0 <= i < len(alarms):
        alarms[i]["enabled"] = not alarms[i]["enabled"]
        save_alarms()
        return alarms[i]["enabled"]
    return None

def delete_alarm(i):
    """刪除指定索引的鬧鐘"""
    if 0 <= i < len(alarms):
        del alarms[i]
        save_alarms()
        return True
    return False

def sync_time():
    """透過 NTP 自動校時（重試三次）"""
    for _ in range(3):
        try:
            ntptime.settime()
            print("[NTP] OK")
            return
        except:
            time.sleep(1)

# ============================================================
# OLED 顯示相關
# ============================================================

def oled_init():
    """初始化 OLED 顯示模組"""
    i2c = I2C(0, scl=Pin(7), sda=Pin(5))
    return SSD1306_I2C(128, 64, i2c)

def oled_write(lines):
    """在 OLED 上顯示多行文字"""
    oled.fill(0)
    for text, y in lines:
        draw_text(oled, text, 0, y)
    oled.show()

def hint(text, ms=800):
    """顯示提示文字（短暫訊息）"""
    oled_write([(text, 26)])

# ======== 各模式畫面 ========
def show_clock():
    """主畫面顯示台灣時間與下一次鬧鐘"""
    y,M,d,h,m,s,_,_ = taiwan_time()
    nxt = next_alarm()
    nxt_str = f"{nxt['M']:02d}/{nxt['d']:02d} {nxt['h']:02d}:{nxt['m']:02d}" if nxt else "無"
    oled_write([
        ("台灣時間", 0),
        (fmt_date(y,M,d), 16),
        (f"{fmt_time(h,m)}:{s:02d}", 32),
        (f"下次:{nxt_str}", 48)
    ])

def show_set_date():
    """設定日期畫面"""
    global cursor_idx
    labels = ["(年)","(月)","(日)"]
    parts = [f"{setting['y']:04d}", f"{setting['M']:02d}", f"{setting['d']:02d}"]
    disp = [p if i!=cursor_idx or (time.ticks_ms()//500)%2 else "  " for i,p in enumerate(parts)]
    oled_write([
        (f"設定日期{labels[cursor_idx]}", 0),
        (f"{disp[0]}/{disp[1]}/{disp[2]}", 20),
        ("A← B→ 雙A-1 雙B+1", 40),
        ("長按A下一步/長按B退出", 52),
    ])

def show_set_time():
    """設定時間畫面"""
    global cursor_idx
    labels = ["(時)","(分)"]
    parts = [f"{setting['h']:02d}", f"{setting['m']:02d}"]
    disp = [p if i!=cursor_idx or (time.ticks_ms()//500)%2 else "  " for i,p in enumerate(parts)]
    oled_write([
        (f"設定時間{labels[cursor_idx]}", 0),
        (f"{disp[0]}:{disp[1]}", 20),
        ("A← B→ 雙A-1 雙B+1", 40),
        ("長按A下一步/長按B退出", 52),
    ])

def show_set_music():
    """設定音樂畫面 (含預聽)"""
    name = MUSIC_NAME[setting["music"]]
    oled_write([
        ("選擇音樂", 0),
        (f"{name}", 22),
        ("A→ B←", 40),
        ("長按A儲存/長按B取消", 52),
    ])

def show_view_alarm():
    """查看鬧鐘清單畫面"""
    if not alarms:
        oled_write([("查看鬧鐘", 0), ("目前無設定", 22), ("長按B 返回", 46)])
        return
    i = max(0, min(view_idx, len(alarms)-1))
    a = alarms[i]
    st = "開啟" if a.get("enabled", True) else "關閉"
    oled_write([
        (f"鬧鐘 {i+1}/{len(alarms)}", 0),
        (f"{a['y']:04d}/{a['M']:02d}/{a['d']:02d}", 16),
        (f"{a['h']:02d}:{a['m']:02d} {MUSIC_NAME[a['music']]}", 32),
        ("A← B→/長按A開關", 48),
    ])
# ============================================================
# 蜂鳴器 / 音樂播放（改良版，可正常響起）
# ============================================================

def speaker_init(pin=6):
    """初始化蜂鳴器（PWM輸出）"""
    s = PWM(Pin(pin, Pin.OUT))
    s.duty(0)  # 初始不發聲
    s.freq(1000)
    return s

async def _play_melody_for(music_index, seconds):
    """
    播放指定音樂一段時間 (用於預聽)
    使用毫秒計時避免無聲或延遲問題
    """
    try:
        t0 = time.ticks_ms()
        melody = MELODY[music_index]
        while time.ticks_diff(time.ticks_ms(), t0) < seconds * 1000:
            for note, d in melody:
                if time.ticks_diff(time.ticks_ms(), t0) >= seconds * 1000:
                    break
                freq = NOTE_FREQS.get(note, 0)
                if freq > 0:
                    speaker.freq(freq)
                    speaker.duty(512)
                else:
                    speaker.duty(0)
                await asyncio.sleep_ms(int(d))
                speaker.duty(0)
                await asyncio.sleep_ms(40)
    finally:
        speaker.duty(0)  # 預聽結束靜音

async def ring_alarm(music_index):
    """
    鬧鐘響鈴主程序 (非同步)
    可正常連續播放整首音樂直到被停止
    """
    global is_ringing, MODE
    if is_ringing:
        return  # 已在響鈴，避免重入
    is_ringing = True
    MODE = "RINGING"

    melody = MELODY[music_index]
    oled_write([("鬧鐘響鈴中", 0), (MUSIC_NAME[music_index], 24), ("A 小睡5分  B 停止", 44)])

    try:
        while is_ringing:
            for note, d in melody:
                if not is_ringing:
                    break
                freq = NOTE_FREQS.get(note, 0)
                if freq > 0:
                    speaker.freq(freq)
                    speaker.duty(512)
                else:
                    speaker.duty(0)
                await asyncio.sleep_ms(int(d))
                speaker.duty(0)
                await asyncio.sleep_ms(40)
    finally:
        # 確保停止時靜音與返回主畫面
        speaker.duty(0)
        is_ringing = False
        MODE = "CLOCK"

def stop_ringing():
    """停止鬧鐘響鈴並返回主畫面"""
    global is_ringing
    is_ringing = False
    speaker.duty(0)
    hint("已停止", 700)
    # ⚡ 立即回主畫面
    global MODE
    MODE = "CLOCK"

def snooze_alarm():
    """小睡五分鐘，建立新的鬧鐘後返回主畫面"""
    global is_ringing
    y, M, d, h, m, s, _, _ = taiwan_time()
    m += SNOOZE_MIN
    if m >= 60:
        m -= 60
        h = (h + 1) % 24
    add_alarm(y, M, d, h, m, 0)
    is_ringing = False
    speaker.duty(0)
    hint("已小睡5分鐘", 700)
    # ⚡ 立即回主畫面
    global MODE
    MODE = "CLOCK"

# ============================================================
# 模式流程控制
# ============================================================

def enter_set_date():
    """進入設定日期模式"""
    global MODE, cursor_idx, setting
    y, M, d, h, m, s, _, _ = taiwan_time()
    setting = {"y": y, "M": M, "d": d, "h": h, "m": m, "music": 0}
    cursor_idx = 0
    MODE = "SET_DATE"
    show_set_date()

def enter_set_time():
    """進入設定時間模式"""
    global MODE, cursor_idx
    cursor_idx = 0
    MODE = "SET_TIME"
    show_set_time()

def enter_set_music():
    """進入選擇音樂模式（含預聽）"""
    global MODE, _preview_task
    MODE = "SET_MUSIC"
    show_set_music()
    # 啟動音樂預聽（5秒）
    if _preview_task is not None:
        _preview_task.cancel()
    _preview_task = asyncio.create_task(_play_melody_for(setting["music"], PREVIEW_SEC))

def save_alarm_and_back():
    """儲存鬧鐘後回主畫面"""
    add_alarm(setting["y"], setting["M"], setting["d"], setting["h"], setting["m"], setting["music"])
    hint("已儲存", 700)

def enter_view():
    """進入查看鬧鐘模式"""
    global MODE, view_idx
    view_idx = 0
    MODE = "VIEW"
    show_view_alarm()

# ============================================================
# 按鈕事件邏輯
# ============================================================

def on_btnA_click(_id, _pin):
    """
    A按鈕：短按
      - SET_DATE / SET_TIME：切換游標
      - SET_MUSIC：下一首音樂 (預聽)
      - VIEW：上一個鬧鐘
      - RINGING：小睡5分鐘
    """
    global MODE, cursor_idx, view_idx, _preview_task
    if MODE == "SET_DATE":
        cursor_idx = (cursor_idx - 1) % 3
        show_set_date()
    elif MODE == "SET_TIME":
        cursor_idx = (cursor_idx - 1) % 2
        show_set_time()
    elif MODE == "SET_MUSIC":
        setting["music"] = (setting["music"] + 1) % len(MUSIC_NAME)
        show_set_music()
        if _preview_task:
            _preview_task.cancel()
        _preview_task = asyncio.create_task(_play_melody_for(setting["music"], PREVIEW_SEC))
    elif MODE == "VIEW" and alarms:
        view_idx = (view_idx - 1) % len(alarms)
        show_view_alarm()
    elif MODE == "RINGING":
        snooze_alarm()

def on_btnA_long(_id, _pin):
    """
    A按鈕：長按
      - CLOCK → 進入 SET_DATE
      - SET_DATE → SET_TIME
      - SET_TIME → SET_MUSIC
      - SET_MUSIC → 儲存鬧鐘並返回主畫面
      - VIEW → 開/關鬧鐘
    """
    global MODE, _preview_task
    if MODE == "CLOCK":
        enter_set_date()
    elif MODE == "SET_DATE":
        enter_set_time()
    elif MODE == "SET_TIME":
        enter_set_music()
    elif MODE == "SET_MUSIC":
        if _preview_task:
            _preview_task.cancel()
        _preview_task = None
        save_alarm_and_back()
        MODE = "CLOCK"
    elif MODE == "VIEW" and alarms:
        en = switch_alarm(view_idx)
        hint("已開啟" if en else "已關閉", 700)
        show_view_alarm()

def on_btnA_double(_id, _pin):
    """A按鈕：雙擊 → 數值減1"""
    global MODE
    if MODE == "SET_DATE":
        k = ["y", "M", "d"][cursor_idx]
        dec_field(k)
        show_set_date()
    elif MODE == "SET_TIME":
        k = ["h", "m"][cursor_idx]
        dec_field(k)
        show_set_time()

def on_btnB_click(_id, _pin):
    """
    B按鈕：短按
      - SET_DATE / SET_TIME：游標右移
      - SET_MUSIC：上一首音樂 (預聽)
      - VIEW：下一個鬧鐘
      - RINGING：停止鬧鐘
    """
    global MODE, cursor_idx, view_idx, _preview_task
    if MODE == "SET_DATE":
        cursor_idx = (cursor_idx + 1) % 3
        show_set_date()
    elif MODE == "SET_TIME":
        cursor_idx = (cursor_idx + 1) % 2
        show_set_time()
    elif MODE == "SET_MUSIC":
        setting["music"] = (setting["music"] - 1) % len(MUSIC_NAME)
        show_set_music()
        if _preview_task:
            _preview_task.cancel()
        _preview_task = asyncio.create_task(_play_melody_for(setting["music"], PREVIEW_SEC))
    elif MODE == "VIEW" and alarms:
        view_idx = (view_idx + 1) % len(alarms)
        show_view_alarm()
    elif MODE == "RINGING":
        stop_ringing()

def on_btnB_long(_id, _pin):
    """
    B按鈕：長按
      - CLOCK → 進入 VIEW
      - SET_* → 返回主畫面
      - SET_MUSIC → 取消設定
      - VIEW → 返回主畫面
    """
    global MODE, _preview_task
    if MODE == "CLOCK":
        enter_view()
    elif MODE in ("SET_DATE", "SET_TIME"):
        MODE = "CLOCK"
    elif MODE == "SET_MUSIC":
        if _preview_task:
            _preview_task.cancel()
        _preview_task = None
        MODE = "CLOCK"
        hint("已取消", 600)
    elif MODE == "VIEW":
        MODE = "CLOCK"

def on_btnB_double(_id, _pin):
    """
    B按鈕：雙擊
      - SET_* → 數值加1
      - VIEW → 刪除目前鬧鐘
    """
    global MODE, view_idx
    if MODE == "SET_DATE":
        k = ["y", "M", "d"][cursor_idx]
        inc_field(k)
        show_set_date()
    elif MODE == "SET_TIME":
        k = ["h", "m"][cursor_idx]
        inc_field(k)
        show_set_time()
    elif MODE == "VIEW" and alarms:
        if delete_alarm(view_idx):
            hint("已刪除", 700)
            if view_idx >= len(alarms):
                view_idx = max(0, len(alarms) - 1)
            show_view_alarm()

# ============================================================
# Web 伺服器 (提供前端網頁控制) — 修正版
# ============================================================

async def handle_client(reader, writer):
    """處理每次 HTTP 請求"""
    req = (await reader.read(1024)).decode()
    try:
        if "/time" in req:
            # 回傳目前時間 JSON
            y, M, d, h, m, s, _, _ = taiwan_time()
            await writer.awrite(
                "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" +
                json.dumps({"y": y, "M": M, "d": d, "h": h, "m": m, "s": s})
            )

        elif "/alarms" in req:
            # 回傳所有鬧鐘資料 + 下次響鈴時間
            nxt = next_alarm()
            nxt_info = None
            if nxt:
                nxt_info = {
                    "y": nxt["y"], "M": nxt["M"], "d": nxt["d"],
                    "h": nxt["h"], "m": nxt["m"],
                    "music": MUSIC_NAME[nxt["music"]],
                    "enabled": nxt["enabled"]
                }
            data = {
                "alarms": alarms,
                "next_alarm": nxt_info
            }
            await writer.awrite("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" + json.dumps(data))

        elif "/add?" in req:
            # 新增鬧鐘 (從網址參數讀取)
            q = req.split("/add?")[1].split(" ")[0]
            kvs = {kv.split("=")[0]: kv.split("=")[1] for kv in q.split("&")}
            add_alarm(int(kvs["y"]), int(kvs["M"]), int(kvs["d"]),
                      int(kvs["h"]), int(kvs["m"]), int(kvs["music"]))
            await writer.awrite("HTTP/1.1 200 OK\r\n\r\n")

        elif "/switch" in req:
            # 切換開關
            idx = int(req.split("id=")[1].split(" ")[0])
            en = switch_alarm(idx)
            await writer.awrite("HTTP/1.1 200 OK\r\n\r\n" if en is not None else "HTTP/1.1 404 Not Found\r\n\r\n")

        elif "/delete" in req:
            # 刪除指定鬧鐘
            idx = int(req.split("id=")[1].split(" ")[0])
            ok = delete_alarm(idx)
            await writer.awrite("HTTP/1.1 200 OK\r\n\r\n" if ok else "HTTP/1.1 404 Not Found\r\n\r\n")

        elif "/next_alarm" in req:
            # 回傳下次響鈴的時間（給前端定期刷新使用）
            nxt = next_alarm()
            if nxt:
                nxt_data = {
                    "y": nxt["y"], "M": nxt["M"], "d": nxt["d"],
                    "h": nxt["h"], "m": nxt["m"],
                    "music": MUSIC_NAME[nxt["music"]],
                    "enabled": nxt["enabled"]
                }
            else:
                nxt_data = None
            await writer.awrite("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" + json.dumps(nxt_data))

        elif "/status" in req:
            # 回傳是否正在響鈴，供網頁偵測用
            await writer.awrite("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" +
                                json.dumps({"ringing": is_ringing}))
            
        elif "/stop" in req:
            stop_ringing()
            await writer.awrite("HTTP/1.1 200 OK\r\n\r\n")

        elif "/snooze" in req:
            snooze_alarm()
            await writer.awrite("HTTP/1.1 200 OK\r\n\r\n")

        else:
            # 傳送 index.html 網頁
            with open("web/index.html") as f:
                for line in f:
                    await writer.awrite(line)

        await writer.aclose()

    except Exception as e:
        print("[Web]", e)
        try:
            await writer.awrite("HTTP/1.1 500 Internal Server Error\r\n\r\n")
            await writer.aclose()
        except:
            pass

# ============================================================
# 背景任務：UI 更新與鬧鐘檢查
# ============================================================

async def ui_task():
    """持續更新 OLED 與鬧鐘觸發判斷"""
    global MODE, _last_rung_key
    while True:
        if MODE == "CLOCK":
            show_clock()
            # 每秒檢查是否觸發鬧鐘（改成允許時間誤差）
            y, M, d, h, m, s, _, _ = taiwan_time()
            key = (y, M, d, h, m)
            if key != _last_rung_key:  # 每分鐘僅檢查一次（避免重複觸發）
                now_ts = time.mktime((y, M, d, h, m, s, 0, 0))
                for a in alarms:
                    if not a.get("enabled", True):
                        continue

                    # 將鬧鐘時間轉為 timestamp（秒）
                    alarm_ts = time.mktime((a["y"], a["M"], a["d"], a["h"], a["m"], 0, 0, 0))

                    # 🔔 觸發條件：
                    #   1. 鬧鐘時間在現在之後（避免剛設定就觸發）
                    #   2. 鬧鐘時間與現在時間差小於 2 秒
                    if 0 <= (alarm_ts - now_ts) <= 1:
                        a["enabled"] = False
                        save_alarms()
                        _last_rung_key = key
                        asyncio.create_task(ring_alarm(a["music"]))
                        break
        elif MODE == "SET_DATE": show_set_date()
        elif MODE == "SET_TIME": show_set_time()
        elif MODE == "SET_MUSIC": show_set_music()
        elif MODE == "VIEW": show_view_alarm()
        await asyncio.sleep(0.5)

# ============================================================
# 主程式入口點
# ============================================================

async def main():
    """系統初始化與主迴圈"""
    global oled, speaker
    oled = oled_init()
    speaker = speaker_init()
    oled_write([("ESP32 鬧鐘系統 v2.6", 16), ("啟動中...", 36)])

    load_alarms()
    sync_time()

    # WiFi 連線
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    ip = "(無)"
    for _ in range(100):
        if wlan.isconnected():
            ip = wlan.ifconfig()[0]
            break
        await asyncio.sleep(0.2)
    oled_write([("IP 位址:", 16), (ip, 36)])

    # 啟動 Web 伺服器
    if ip != "(無)":
        await asyncio.start_server(handle_client, "0.0.0.0", 80)

    # 啟動背景 UI 任務
    asyncio.create_task(ui_task())

    # 初始化按鈕事件 (A=34, B=21)
    btnA = DebouncedButton(34, on_click=on_btnA_click, on_long=on_btnA_long, on_double=on_btnA_double)
    btnB = DebouncedButton(21, on_click=on_btnB_click, on_long=on_btnB_long, on_double=on_btnB_double)

    # 主循環：持續更新按鈕狀態
    while True:
        btnA.update()
        btnB.update()
        await asyncio.sleep_ms(20)

# ============================================================
# 啟動程式（含安全結尾）
# ============================================================
try:
    asyncio.run(main())
finally:
    try:
        speaker.duty(0)   # 結束時關閉蜂鳴器
    except:
        pass
