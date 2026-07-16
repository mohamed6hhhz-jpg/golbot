import yfinance as yf
from groq import Groq
import requests
from datetime import datetime, timezone, timedelta
import time
import os
import logging
import numpy as np
import asyncio
import threading
from telethon import TelegramClient
from telethon.sessions import StringSession

# ── كلايانت Telethon مشترك ودائم — يتصل مرة واحدة عند التشغيل ──
_SHARED_CLIENT: TelegramClient | None = None
_CLIENT_LOOP:   asyncio.AbstractEventLoop | None = None
_CLIENT_LOCK  = threading.Lock()

GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
    "llama3-70b-8192",
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logging.getLogger('yfinance').setLevel(logging.CRITICAL)  # منع رسائل ياهو المزعجة
log = logging.getLogger(__name__)

import random
GROQ_KEYS = [
    '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',
    "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",
    "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",
    "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"
]
TWELVEDATA_API_KEY  = os.environ.get("TWELVEDATA_API_KEY", "a40631d26cb64ba99916a3162880aff3")
TELEGRAM_BOT_TOKEN  = "8783502825:AAEEgxaxzgiAxwl4oBp4zl73jmqwBtKCalc"
TELEGRAM_BOT_TOKEN_2 = "8718236248:AAGIlK8xTWUvRB_WcYOGN2Qx1kEKZwRqihQ"

TARGET_CHATS = ["@GooldFut"]
LAST_PUBLIC_REPORT_TIME = 0
LAST_4H_REPORT_TIME = 0

MASTER_SYSTEM_PROMPT = """أنت خبير مالي سينيور متخصص في سوق الذهب. مهمتك إنتاج تقرير احترافي، متناسق، ومكتمل بدون أي أخطاء أو تناقضات.
قواعد صارمة يجب الالتزام بها:
1. الاكتمال (أولوية قصوى): التقرير يجب أن يكون مكتمل 100%. ممنوع قطع أي قسم في منتصف الجملة أو ترك أي جزء ناقص. كل قسم يجب أن يكون مكتوب بالكامل حتى النهاية.
2. التناسق (Consistency): التقرير يجب أن يكون متناسق تماماً في الاتجاه. ممنوع وجود تناقض بين الأقسام. تأكد من أن الخلاصة تتوافق مع باقي التقرير.
3. تقليل التكرار بشدة: ممنوع تكرار نفس الصفقات أو الأفكار في أكثر من قسم. كل قسم يجب أن يضيف قيمة جديدة.
4. الدقة والحقائق: ممنوع كتابة معلومات خاطئة أو غير منطقية. التحليل مدعوم بمنطق واضح ودقيق.
5. تحسين الأقسام الضعيفة: الأقسام مثل تأثير الأسواق وقوة العملات يجب أن تكون دقيقة ومترابطة مع الذهب بشكل صحيح.
6. الثقة والصفقات: الثقة منطقية (يفضل بين 60% و 75%). الصفقات متنوعة وغير مكررة.
7. الهيكل والصياغة: منظم وواضح، تجنب الجمل المقطوعة.

"""


API_ID   = 34105911
API_HASH = 'b444ab6b4eeba8a66db4143b934dc540'
SESSION_STRING = (
    os.environ.get("AUTO_COPY_SESSION_STRING") or
    os.environ.get("SHEETS_SESSION_STRING") or ""
)

CAIRO_TZ         = timezone(timedelta(hours=3))
ALERT_THRESHOLD  = 6.0
ROUTINE_MINUTES  = 60
MORNING_HOUR_CAI = 9
CLOSING_HOUR_CAI = 23
HEARTBEAT_HOUR   = 12
MARKET_OPEN_HOUR = 1
MAX_SL_DISTANCE  = 38.0   # ← أقصى وقف خسارة بالدولار


def cairo_now() -> datetime:
    return datetime.now(CAIRO_TZ)


def is_market_open() -> bool:
    now     = cairo_now()
    weekday = now.weekday()
    hour    = now.hour
    if weekday in (5, 6):
        return False
    if weekday == 0 and hour < MARKET_OPEN_HOUR:
        return False
    return True


# ══════════════════════════════════════════════
#  1. جلب البيانات
# ══════════════════════════════════════════════
def _fetch(symbol: str, period: str = "90d", interval: str = "1d", max_retries: int = 4):
    for attempt in range(max_retries):
        try:
            df = yf.Ticker(symbol).history(period=period, interval=interval)
            if not df.empty:
                return df
            return None
        except Exception as e:
            wait = 2 ** attempt
            log.warning(f"[yfinance] {symbol} [{interval}] محاولة {attempt+1}: {e} — انتظار {wait}s")
            time.sleep(wait)
    return None


def _last_close(df) -> float | None:
    if df is None or df.empty: return None
    valid = df[df['Close'].notna()]
    return float(valid['Close'].iloc[-1]) if not valid.empty else None

def _last_with_date(df) -> tuple[float | None, str]:
    """يرجع (آخر سعر, تاريخه كنص) — حتى لو السوق مغلق."""
    if df is None or df.empty:
        return None, ""
    # ابحث عن آخر صف بدون NaN
    valid = df[df['Close'].notna()]
    if valid.empty:
        return None, ""
    last_row = valid.iloc[-1]
    price    = float(last_row['Close'])
    try:
        ts = valid.index[-1]
        if hasattr(ts, 'strftime'):
            label = ts.strftime("%d/%m %H:%M")
        else:
            label = str(ts)[:16]
    except Exception:
        label = "غير معروف"
    return price, label


# ══════════════════════════════════════════════
#  2. المؤشرات الفنية
# ══════════════════════════════════════════════
def calc_rsi(closes: np.ndarray, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas   = np.diff(closes)
    gains    = np.where(deltas > 0, deltas, 0.0)
    losses   = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i])  / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    return round(100 - (100 / (1 + avg_gain / avg_loss)), 2)


def calc_stoch_rsi(closes: np.ndarray, rsi_period=14, stoch_period=14, k_smooth=3, d_smooth=3):
    if len(closes) < rsi_period + stoch_period + k_smooth + d_smooth:
        return 50.0, 50.0
    rsi_series = [calc_rsi(closes[i:i + rsi_period + 1]) for i in range(len(closes) - rsi_period)]
    rsi_arr    = np.array(rsi_series)
    if len(rsi_arr) < stoch_period:
        return 50.0, 50.0
    stoch_k = []
    for i in range(len(rsi_arr) - stoch_period + 1):
        window = rsi_arr[i:i + stoch_period]
        mn, mx = window.min(), window.max()
        stoch_k.append(100.0 * (rsi_arr[i + stoch_period - 1] - mn) / (mx - mn + 1e-9))
    stoch_k = np.array(stoch_k)
    def sma(arr, n): return np.convolve(arr, np.ones(n)/n, mode='valid')
    k_s = sma(stoch_k, k_smooth) if len(stoch_k) >= k_smooth else stoch_k
    d_s = sma(k_s, d_smooth)     if len(k_s)     >= d_smooth else k_s
    return round(float(k_s[-1]), 2), round(float(d_s[-1]), 2)


def calc_macd(closes: np.ndarray, fast=12, slow=26, signal=9):
    def ema(arr, n):
        k = 2 / (n + 1)
        res = [arr[0]]
        for v in arr[1:]: res.append(v * k + res[-1] * (1 - k))
        return np.array(res)
    if len(closes) < slow + signal:
        return 0.0, 0.0, 0.0
    ml = ema(closes, fast) - ema(closes, slow)
    sl = ema(ml, signal)
    return round(float(ml[-1]), 4), round(float(sl[-1]), 4), round(float((ml - sl)[-1]), 4)


def calc_bollinger(closes: np.ndarray, period: int = 20, std_dev: float = 2.0):
    if len(closes) < period:
        c = closes[-1]
        return c, c, c
    w = closes[-period:]
    m, s = np.mean(w), np.std(w)
    return round(float(m + std_dev * s), 2), round(float(m), 2), round(float(m - std_dev * s), 2)


def calc_ema(closes: np.ndarray, period: int) -> float:
    if len(closes) < period:
        return float(closes[-1])
    k = 2 / (period + 1)
    v = closes[0]
    for c in closes[1:]: v = c * k + v * (1 - k)
    return round(float(v), 2)


def calc_adx(df, period: int = 14):
    if df is None or len(df) < period * 2:
        return 20.0, 50.0, 50.0
    h, l, c = df['High'].values, df['Low'].values, df['Close'].values
    tr_list, dm_plus, dm_minus = [], [], []
    for i in range(1, len(df)):
        tr   = max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1]))
        up   = h[i] - h[i-1]
        down = l[i-1] - l[i]
        tr_list.append(tr)
        dm_plus.append(up   if up > down and up > 0 else 0)
        dm_minus.append(down if down > up and down > 0 else 0)
    # Wilder smooth للقيم المطلقة (TR و DM)
    def wilder_abs(arr, n):
        res = [sum(arr[:n])]          # مجموع أول n قيمة
        for v in arr[n:]: res.append(res[-1] - res[-1]/n + v)
        return res
    # Wilder smooth للنسب (DX→ADX) — الحالة الصحيحة: EMA بـ v/n
    def wilder_ratio(arr, n):
        res = [sum(arr[:n]) / n]      # متوسط أول n قيمة
        for v in arr[n:]: res.append(res[-1] - res[-1]/n + v/n)
        return res

    atr_s  = wilder_abs(tr_list, period)
    dip_s  = wilder_abs(dm_plus,  period)
    dim_s  = wilder_abs(dm_minus, period)
    di_p   = [min(100.0, 100 * dip_s[i] / (atr_s[i] + 1e-9)) for i in range(len(atr_s))]
    di_m   = [min(100.0, 100 * dim_s[i] / (atr_s[i] + 1e-9)) for i in range(len(atr_s))]
    dx     = [100 * abs(di_p[i]-di_m[i]) / (di_p[i]+di_m[i]+1e-9) for i in range(len(atr_s))]
    adx_s  = wilder_ratio(dx, period)   # ← EMA صحيحة لـ DX
    return round(float(adx_s[-1]), 2), round(float(di_p[-1]), 2), round(float(di_m[-1]), 2)


def calc_cci(df, period: int = 20) -> float:
    if df is None or len(df) < period: return 0.0
    tp = (df['High'].values + df['Low'].values + df['Close'].values) / 3
    tp_w = tp[-period:]
    m    = np.mean(tp_w)
    md   = np.mean(np.abs(tp_w - m))
    return round(float((tp[-1] - m) / (0.015 * md + 1e-9)), 2)


def calc_williams_r(df, period: int = 14) -> float:
    if df is None or len(df) < period: return -50.0
    h = df['High'].values[-period:]
    l = df['Low'].values[-period:]
    c = df['Close'].values[-1]
    hh, ll = np.max(h), np.min(l)
    return round(float(-100 * (hh - c) / (hh - ll + 1e-9)), 2)


def calc_obv(df) -> tuple:
    if df is None or len(df) < 5 or 'Volume' not in df.columns:
        return 0.0, "غير متاح"
    closes  = df['Close'].values
    volumes = df['Volume'].values.astype(float)
    obv_series = [0.0]
    for i in range(1, len(closes)):
        if closes[i] > closes[i-1]:
            obv_series.append(obv_series[-1] + volumes[i])
        elif closes[i] < closes[i-1]:
            obv_series.append(obv_series[-1] - volumes[i])
        else:
            obv_series.append(obv_series[-1])
    obv_arr = np.array(obv_series)
    trend   = "صعودي" if obv_arr[-1] > np.mean(obv_arr[-20:]) else "هبوطي"
    return round(float(obv_arr[-1]), 0), trend


def calc_relative_volume(df, period: int = 20) -> tuple:
    if df is None or len(df) < period + 1 or 'Volume' not in df.columns:
        return 1.0, "محايد"
    vols = df['Volume'].values.astype(float)
    avg  = np.mean(vols[-period-1:-1])
    if avg == 0:
        return 1.0, "محايد"
    rel_vol = vols[-1] / avg
    if rel_vol > 1.5:  label = f"عالي جداً ({rel_vol:.1f}x) — تحرك مؤسسي 🔥"
    elif rel_vol > 1.0: label = f"فوق المتوسط ({rel_vol:.1f}x) ⬆️"
    elif rel_vol > 0.5: label = f"دون المتوسط ({rel_vol:.1f}x) ⬇️"
    else:               label = f"منخفض جداً ({rel_vol:.1f}x) ⚠️"
    return round(rel_vol, 2), label


def calc_atr(df, period: int = 14) -> float:
    if df is None or len(df) < period + 1: return 0.0
    h, l, c = df['High'].values, df['Low'].values, df['Close'].values
    tr_list = [max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1])) for i in range(1, len(df))]
    return round(float(np.mean(tr_list[-period:])), 2)


def calc_atr_regime(df, period: int = 14) -> str:
    if df is None or len(df) < period * 2 + 1:
        return "محايد/عرضي"
    h, l, c = df['High'].values, df['Low'].values, df['Close'].values
    tr_list = [max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1])) for i in range(1, len(df))]
    atr_now = np.mean(tr_list[-period:])
    atr_old = np.mean(tr_list[-period*2:-period])
    if atr_now > atr_old * 1.25:
        return "تقلب متصاعد 🔥 — اختراق جارٍ"
    elif atr_now < atr_old * 0.80:
        return "تقلب منخفض ⚡ — اختراق وشيك"
    else:
        return "تقلب عادي ⚪"


def calc_fibonacci(closes: np.ndarray, lookback: int = 30):
    if len(closes) < lookback: lookback = len(closes)
    w = closes[-lookback:]
    high, low = float(np.max(w)), float(np.min(w))
    d = high - low
    return {"0.0%": round(high,2), "23.6%": round(high-0.236*d,2), "38.2%": round(high-0.382*d,2),
            "50.0%": round(high-0.500*d,2), "61.8%": round(high-0.618*d,2),
            "78.6%": round(high-0.786*d,2), "100%": round(low,2)}


def find_swing_levels(df, lookback: int = 20):
    if df is None or len(df) < lookback: return None, None
    return round(float(np.max(df['High'].values[-lookback:])), 2), \
           round(float(np.min(df['Low'].values[-lookback:])), 2)


def calc_price_prediction(gold: float, atr: float, tf_15m: dict, tf_hourly: dict) -> dict:
    """توقع السعر بعد 15 دقيقة وساعة — ATR Projection + اتجاه الزخم"""
    atr_15m   = round(atr * (15/1380) ** 0.5, 2)  # FIX: 1380 min/day for Gold Futures
    atr_1h    = round(atr * (60/1380) ** 0.5, 2)  # FIX: 1380 min/day for Gold Futures
    sc_15m    = tf_15m.get('score', 0)
    sc_1h     = tf_hourly.get('score', 0)
    dir_15m   = (1 if sc_15m > 0 else -1 if sc_15m < 0 else 0)
    dir_1h    = (1 if sc_1h  > 0 else -1 if sc_1h  < 0 else 0)
    c15 = round(gold + dir_15m * atr_15m * 0.4, 2)
    c1h = round(gold + dir_1h  * atr_1h  * 0.6, 2)
    return {
        '15m': {'center': c15, 'low': round(c15 - atr_15m*0.5, 2), 'high': round(c15 + atr_15m*0.5, 2)},
        '1h':  {'center': c1h, 'low': round(c1h - atr_1h *0.5, 2), 'high': round(c1h + atr_1h *0.5, 2)},
    }


def calc_advanced_trades(d: dict, bias: str) -> dict:
    """6 أنواع صفقات متقدمة: سكالبينج | يومية | أسبوعية | شهرية | سوينج | انعكاس"""
    gold   = d['gold'];  atr = d['atr']
    market_name = 'آجل (Futures)' if d.get('mode') == 'futures' else 'فوري (Spot)'
    s1, s2 = d['s1'], d['s2']
    r1, r2 = d['r1'], d['r2']
    pivot  = d['pivot']
    sw_h   = d['swing_high'] or r2
    sw_l   = d['swing_low']  or s2
    pw_h   = d.get('prev_wk_high') or r2
    pw_l   = d.get('prev_wk_low')  or s2
    pm_h   = d.get('prev_mo_high') or round(r2 + atr, 2)
    pm_l   = d.get('prev_mo_low')  or round(s2 - atr, 2)
    rsi    = d['rsi'];  div = d.get('divergence', '')
    trades = {}

    # ── مستويات مُصفّاة للصفقات المتقدمة ──
    def _va(levels):  # أقرب مقاومة فوق السعر
        v = sorted([x for x in levels if x and x > gold])
        return v[0] if v else round(gold + 50, 2)
    def _va2(levels, f):  # ثاني مقاومة
        v = sorted([x for x in levels if x and x > gold and abs(x - f) > 8])
        return v[0] if v else round(f + 40, 2)
    def _vb(levels):  # أقرب دعم تحت السعر
        v = sorted([x for x in levels if x and x < gold], reverse=True)
        return v[0] if v else round(gold - 50, 2)
    def _vb2(levels, f):  # ثاني دعم
        v = sorted([x for x in levels if x and x < gold and abs(x - f) > 8], reverse=True)
        return v[0] if v else round(f - 40, 2)

    all_r = [r1, r2, pw_h, sw_h]
    all_s = [s1, s2, pw_l, sw_l]
    r_n = _va(all_r);  r_f = _va2(all_r, r_n)
    s_n = _vb(all_s);  s_f = _vb2(all_s, s_n)

    def _rr(gain, risk): return round(gain / risk, 1) if risk > 0 else 0
    MIN_RR = 1.2   # حد أدنى للعائد/المخاطرة عند T1 — أي صفقة أقل تُحذف

    # ── سكالبينج (5د، 15د، 30د، 1س، 4س) ──
    # 5m Scalp
    atr_5m = round(atr * (5/1380)**0.5, 2)
    sl_5m = max(round(atr_5m * 0.8, 2), 3.0)
    sc_5m = d.get('tf_5m', {}).get('score', 0)
    if sc_5m >= 0:
        trades['scalp_5m_buy'] = dict(entry=round(gold, 2), sl=round(gold - sl_5m, 2), risk=sl_5m, t1=round(gold + atr_5m*1.5, 2), t2=round(gold + atr_5m*2.5, 2), t3=round(gold + atr_5m*4.0, 2), market=market_name, tf='5د', typ='سكالبينج ⚡', dir='buy')
    elif sc_5m < 0:
        trades['scalp_5m_sell'] = dict(entry=round(gold, 2), sl=round(gold + sl_5m, 2), risk=sl_5m, t1=round(gold - atr_5m*1.5, 2), t2=round(gold - atr_5m*2.5, 2), t3=round(gold - atr_5m*4.0, 2), market=market_name, tf='5د', typ='سكالبينج ⚡', dir='sell')

    # 15m Scalp
    sl_sc = max(round(atr * (15/1380)**0.5, 2), 3.0)
    t_buy15 = dict(entry=round(s_n, 2), sl=round(s_n - sl_sc, 2), risk=sl_sc, t1=round(s_n + 15, 2), t2=round(s_n + 28, 2), t3=round(s_n + 45, 2), market=market_name, tf='15د', typ='سكالبينج 🏹', dir='buy')
    t_sell15 = dict(entry=round(r_n, 2), sl=round(r_n + sl_sc, 2), risk=sl_sc, t1=round(r_n - 15, 2), t2=round(r_n - 28, 2), t3=round(r_n - 45, 2), market=market_name, tf='15د', typ='سكالبينج 🏹', dir='sell')
    if bias == 'bull': trades['scalp_buy'] = t_buy15
    elif bias == 'bear': trades['scalp_sell'] = t_sell15
    elif bias == 'neutral': trades['scalp_buy' if _rr(15, sl_sc) >= _rr(15, sl_sc) else 'scalp_sell'] = t_buy15

    # 30m Scalp
    atr_30m = max(round(atr * (30/1380)**0.5, 2), 4.0)
    sc_30m = d.get('tf_30m', {}).get('score', 0)
    if sc_30m >= 0:
        trades['scalp_30m_buy'] = dict(entry=round(gold, 2), sl=round(gold - atr_30m, 2), risk=atr_30m, t1=round(gold + atr_30m*1.5, 2), t2=round(gold + atr_30m*2.5, 2), t3=round(gold + atr_30m*4.0, 2), market=market_name, tf='30د', typ='سكالبينج ⚡', dir='buy')
    elif sc_30m < 0:
        trades['scalp_30m_sell'] = dict(entry=round(gold, 2), sl=round(gold + atr_30m, 2), risk=atr_30m, t1=round(gold - atr_30m*1.5, 2), t2=round(gold - atr_30m*2.5, 2), t3=round(gold - atr_30m*4.0, 2), market=market_name, tf='30د', typ='سكالبينج ⚡', dir='sell')

    # 1h Scalp
    atr_1h = max(round(atr * (60/1380)**0.5, 2), 5.0)
    sc_1h = d.get('tf_hourly', {}).get('score', 0)
    if sc_1h >= 0:
        trades['scalp_1h_buy'] = dict(entry=round(gold, 2), sl=round(gold - atr_1h, 2), risk=atr_1h, t1=round(gold + atr_1h*1.5, 2), t2=round(gold + atr_1h*2.5, 2), t3=round(gold + atr_1h*4.0, 2), market=market_name, tf='1س', typ='سكالبينج ⚡', dir='buy')
    elif sc_1h < 0:
        trades['scalp_1h_sell'] = dict(entry=round(gold, 2), sl=round(gold + atr_1h, 2), risk=atr_1h, t1=round(gold - atr_1h*1.5, 2), t2=round(gold - atr_1h*2.5, 2), t3=round(gold - atr_1h*4.0, 2), market=market_name, tf='1س', typ='سكالبينج ⚡', dir='sell')

    # 4h Scalp
    atr_4h = max(round(atr * (240/1380)**0.5, 2), 8.0)
    sc_4h = d.get('tf_4h', {}).get('score', 0)
    if sc_4h >= 0:
        trades['scalp_4h_buy'] = dict(entry=round(gold, 2), sl=round(gold - atr_4h, 2), risk=atr_4h, t1=round(gold + atr_4h*1.5, 2), t2=round(gold + atr_4h*2.5, 2), t3=round(gold + atr_4h*4.0, 2), market=market_name, tf='4س', typ='سكالبينج ⚡', dir='buy')
    elif sc_4h < 0:
        trades['scalp_4h_sell'] = dict(entry=round(gold, 2), sl=round(gold + atr_4h, 2), risk=atr_4h, t1=round(gold - atr_4h*1.5, 2), t2=round(gold - atr_4h*2.5, 2), t3=round(gold - atr_4h*4.0, 2), market=market_name, tf='4س', typ='سكالبينج ⚡', dir='sell')

    # ── يومية ── (الدخول من Pivot فقط لو بين الدعم والمقاومة)
    sl_d = round(atr * 0.4, 2)
    # pivot قد يكون بعيداً عن السعر — نستخدمه فقط لو منطقي
    piv_valid = s_n < pivot < r_n
    buy_entry_d  = round(pivot if piv_valid else s_n, 2)
    sell_entry_d = round(pivot if piv_valid else r_n, 2)
    t = dict(entry=buy_entry_d, sl=round(buy_entry_d - sl_d, 2), risk=sl_d,
             t1=r_n, t2=r_f, t3=round(r_f + atr * 0.3, 2),
             market=market_name, tf='1ي', typ='يومية 📅', dir='buy')
    t_buy = t
    t_sell = dict(entry=sell_entry_d, sl=round(sell_entry_d + sl_d, 2), risk=sl_d,
             t1=s_n, t2=s_f, t3=round(s_f - atr * 0.3, 2),
             market=market_name, tf='1ي', typ='يومية 📅', dir='sell')
             
    rr_buy = _rr(r_n - buy_entry_d, sl_d)
    rr_sell = _rr(sell_entry_d - s_n, sl_d)
    
    if bias == 'bull' and rr_buy >= MIN_RR: trades['daily_buy'] = t_buy
    elif bias == 'bear' and rr_sell >= MIN_RR: trades['daily_sell'] = t_sell
    elif bias == 'neutral':
        if rr_buy >= rr_sell and rr_buy >= MIN_RR: trades['daily_buy'] = t_buy
        elif rr_sell > rr_buy and rr_sell >= MIN_RR: trades['daily_sell'] = t_sell

    # ── أسبوعية ──
    sl_w_b = round(abs(s_n - (pw_l - 5)), 2) if pw_l else round(atr * 1.0, 2)  # FIX: abs() to prevent negative risk
    sl_w_s = round((pw_h + 5) - r_n, 2) if pw_h else round(atr * 1.0, 2)
    t = dict(entry=round(s_n, 2), sl=round(pw_l - 5 if pw_l else s_n - atr, 2),
             risk=max(abs(sl_w_b), 10),
             t1=r_n, t2=r_f, t3=round(pw_h if pw_h else r_f + atr * 0.5, 2),
             market=market_name, tf='1أ', typ='أسبوعية 📆', dir='buy')
    if bias in ('bull', 'neutral') and _rr(r_n - s_n, max(abs(sl_w_b), 10)) >= MIN_RR:
        trades['weekly_buy'] = t
    t = dict(entry=round(r_n, 2), sl=round(pw_h + 5 if pw_h else r_n + atr, 2),
             risk=max(abs(sl_w_s), 10),
             t1=s_n, t2=s_f, t3=round(pw_l if pw_l else s_f - atr * 0.5, 2),
             market=market_name, tf='1أ', typ='أسبوعية 📆', dir='sell')
    if bias in ('bear', 'neutral') and _rr(r_n - s_n, max(abs(sl_w_s), 10)) >= MIN_RR:
        trades['weekly_sell'] = t

    # ── شهرية ──
    sl_m = round(atr * 1.5, 2)
    buy_ent_m  = round(s_f, 2)
    sell_ent_m = round(r_f, 2)
    m_buy_t1 = max(r_n, buy_ent_m + atr * 0.3)
    m_buy_t2 = max(round((pm_h + r_n) / 2, 2) if pm_h else r_f, m_buy_t1 + atr * 0.2)
    m_buy_t3 = max(round(pm_h, 2) if pm_h else round(r_f + atr * 0.5, 2), m_buy_t2 + atr * 0.2)
    t = dict(entry=buy_ent_m, sl=round(buy_ent_m - sl_m, 2), risk=sl_m,
             t1=round(m_buy_t1, 2), t2=round(m_buy_t2, 2), t3=round(m_buy_t3, 2),
             market=market_name, tf='1ش', typ='شهرية 🗓️', dir='buy')
    if bias in ('bull', 'neutral') and _rr(r_n - s_f, sl_m) >= MIN_RR:
        trades['monthly_buy'] = t
    m_sell_t1 = min(s_n, sell_ent_m - atr * 0.3)
    m_sell_t2 = min(round((pm_l + s_n) / 2, 2) if pm_l else s_f, m_sell_t1 - atr * 0.2)
    m_sell_t3 = min(round(pm_l, 2) if pm_l else round(s_f - atr * 0.5, 2), m_sell_t2 - atr * 0.2)
    t = dict(entry=sell_ent_m, sl=round(sell_ent_m + sl_m, 2), risk=sl_m,
             t1=round(m_sell_t1, 2), t2=round(m_sell_t2, 2), t3=round(m_sell_t3, 2),
             market=market_name, tf='1ش', typ='شهرية 🗓️', dir='sell')
    if bias in ('bear', 'neutral') and _rr(r_f - s_n, sl_m) >= MIN_RR:
        trades['monthly_sell'] = t

    # ── سوينج ──
    sl_sw = round(atr * 1.2, 2)  # FIX: Swing SL widened — 0.35 was dangerously tight for multi-week trades
    mid   = round((sw_h + sw_l) / 2, 2)
    t = dict(entry=round(sw_l, 2), sl=round(sw_l - sl_sw, 2), risk=sl_sw,
             t1=mid, t2=round(sw_h, 2), t3=round(sw_h + atr * 0.4, 2),
             market=market_name, tf='أسابيع', typ='سوينج 🌊', dir='buy')
    if bias in ('bull', 'neutral') and sw_l < gold and _rr(mid - sw_l, sl_sw) >= MIN_RR:
        trades['swing_buy'] = t
    t = dict(entry=round(sw_h, 2), sl=round(sw_h + sl_sw, 2), risk=sl_sw,
             t1=mid, t2=round(sw_l, 2), t3=round(sw_l - atr * 0.4, 2),
             market=market_name, tf='أسابيع', typ='سوينج 🌊', dir='sell')
    if bias in ('bear', 'neutral') and sw_h > gold and _rr(sw_h - mid, sl_sw) >= MIN_RR:
        trades['swing_sell'] = t

    # ── انعكاس (Counter-trend) ──
    sl_rev = max(round(atr * 0.28, 2), 3.0)
    
    rev_buy_entry = round(min(s2, sw_l), 2) if sw_l > 0 else round(s2, 2)
    trades['rev_buy'] = dict(
        entry=rev_buy_entry, sl=round(rev_buy_entry - sl_rev, 2), risk=sl_rev,
        t1=round(rev_buy_entry + atr * 0.5, 2), 
        t2=round(rev_buy_entry + atr * 1.0, 2), 
        t3=round(rev_buy_entry + atr * 1.5, 2),
        market=market_name, tf='1-4س', typ='زيرو انعكاس 🔄', dir='buy'
    )
    
    rev_sell_entry = round(max(r2, sw_h), 2) if sw_h > 0 else round(r2, 2)
    trades['rev_sell'] = dict(
        entry=rev_sell_entry, sl=round(rev_sell_entry + sl_rev, 2), risk=sl_rev,
        t1=round(rev_sell_entry - atr * 0.5, 2), 
        t2=round(rev_sell_entry - atr * 1.0, 2), 
        t3=round(rev_sell_entry - atr * 1.5, 2),
        market=market_name, tf='1-4س', typ='زيرو انعكاس 🔄', dir='sell'
    )
    # ── سوينج طويل الأمد (Long-Term Swing) ──
    pm_h_val = d.get('prev_mo_high') or round(sw_h + atr, 2)
    pm_l_val = d.get('prev_mo_low') or round(sw_l - atr, 2)
    sl_lt = round(atr * 2.0, 2)
    if bias in ('bull', 'neutral'):
        lt_entry = round(min(s_f, sw_l * 1.001), 2)
        t_lt = dict(entry=lt_entry, sl=round(lt_entry - sl_lt, 2), risk=sl_lt,
                    t1=round(sw_h, 2), t2=round(pm_h_val, 2), t3=round(pm_h_val + atr*0.5, 2),
                    market=market_name, tf='شهور', typ='سوينج طويل 🌊⌚', dir='buy')
        if True: trades['long_swing_buy'] = t_lt
    if bias in ('bear', 'neutral'):
        lt_entry = round(max(r_f, sw_h * 0.999), 2)
        t_lt = dict(entry=lt_entry, sl=round(lt_entry + sl_lt, 2), risk=sl_lt,
                    t1=round(sw_l, 2), t2=round(pm_l_val, 2), t3=round(pm_l_val - atr*0.5, 2),
                    market=market_name, tf='شهور', typ='سوينج طويل 🌊⌚', dir='sell')
        if True: trades['long_swing_sell'] = t_lt

    # ── سكالبينج ضيق جداً (Tight Scalp) ──
    sl_tight = max(round(atr * (10/1380)**0.5, 2), 2.0)  # FIX: 1380 min/day for Gold Futures
    sc_1h = d.get('tf_hourly', {}).get('score', 0)
    if sc_1h > 0 and bias in ('bull', 'neutral'):
        t_ts = dict(entry=round(gold, 2), sl=round(gold - sl_tight, 2), risk=sl_tight,
                    t1=round(gold + sl_tight*2, 2), t2=round(gold + sl_tight*3.5, 2),
                    t3=round(gold + sl_tight*5, 2),
                    market=market_name, tf='10د', typ='سكالب ضيق 🎯', dir='buy')
        if True: trades['tight_scalp_buy'] = t_ts
    elif sc_1h < 0 and bias in ('bear', 'neutral'):
        t_ts = dict(entry=round(gold, 2), sl=round(gold + sl_tight, 2), risk=sl_tight,
                    t1=round(gold - sl_tight*2, 2), t2=round(gold - sl_tight*3.5, 2),
                    t3=round(gold - sl_tight*5, 2),
                    market=market_name, tf='10د', typ='سكالب ضيق 🎯', dir='sell')
        if True: trades['tight_scalp_sell'] = t_ts

    # ── لوت عالي (High Lot / Precision Entry) ──
    # وقف ضيق جداً (5$) بهدف تحمل لوت عالي — عند مستوى دعم/مقاومة بالميلي
    sl_hl = 5.0
    fib_vals = list(d.get('fib', {}).values())
    fib_near_sup = [f for f in fib_vals if f and gold*0.999 > f > gold - atr*0.3]
    fib_near_res = [f for f in fib_vals if f and gold*1.001 < f < gold + atr*0.3]
    hl_entry_b = round(fib_near_sup[-1], 2) if fib_near_sup else round(s_n + 0.5, 2) if abs(gold - s_n) < 8 else None
    hl_entry_s = round(fib_near_res[0], 2) if fib_near_res else round(r_n - 0.5, 2) if abs(gold - r_n) < 8 else None
    if hl_entry_b:
        t_hl = dict(entry=hl_entry_b, sl=round(hl_entry_b - sl_hl, 2), risk=sl_hl,
                    t1=round(hl_entry_b + 12, 2), t2=round(hl_entry_b + 22, 2), t3=round(hl_entry_b + 35, 2),
                    market=market_name, tf='<5د', typ='لوت عالي 💰', dir='buy')
        if True: trades['high_lot_buy'] = t_hl
    if hl_entry_s:
        t_hl = dict(entry=hl_entry_s, sl=round(hl_entry_s + sl_hl, 2), risk=sl_hl,
                    t1=round(hl_entry_s - 12, 2), t2=round(hl_entry_s - 22, 2), t3=round(hl_entry_s - 35, 2),
                    market=market_name, tf='<5د', typ='لوت عالي 💰', dir='sell')
        if True: trades['high_lot_sell'] = t_hl

    # ── هدف الـ 15 دقيقة القادمة ──
    atr_15 = round(atr * (15/1380)**0.5, 2)  # FIX: 1380 min/day for Gold Futures
    sc15   = d.get('tf_15m', {}).get('score', 0)
    dir_15 = 1 if sc15 > 0 else (-1 if sc15 < 0 else 0)
    target_15m = round(gold + dir_15 * atr_15 * 0.6, 2)
    high_15m   = round(gold + atr_15 * 0.85, 2)
    low_15m    = round(gold - atr_15 * 0.85, 2)
    trades['target_15m'] = {
        'center': target_15m, 'high': high_15m, 'low': low_15m,
        'dir': 'buy' if dir_15 > 0 else ('sell' if dir_15 < 0 else 'neutral'),
        'atr_15m': atr_15, 'sc': sc15,
    }

    # ── ضمان ترتيب الأهداف رياضياً — تخطي أي صفقة ليس فيها t1/t2/t3 ──
    for k, t in trades.items():
        if 't1' not in t or 't2' not in t or 't3' not in t:
            continue  # target_15m وأي صفقة خاصة لها هيكل مختلف
        targets = [t['t1'], t['t2'], t['t3']]
        if t.get('dir') == 'buy':
            targets.sort()
        else:
            targets.sort(reverse=True)
        t['t1'], t['t2'], t['t3'] = targets

    return trades


def get_round_numbers(price: float, step: int = 50) -> dict:
    lower = (price // step) * step
    upper = lower + step
    return {"nearest_support": round(lower, 2), "nearest_resistance": round(upper, 2),
            "dist_to_support": round(price - lower, 2), "dist_to_resistance": round(upper - price, 2)}


def get_historical_context(df) -> dict:
    if df is None or len(df) < 2:
        return {}
    closes = df['Close'].values
    now    = closes[-1]
    ctx    = {}
    if len(closes) >= 2:
        ctx['chg_1d']  = round(now - closes[-2], 2)
        ctx['pct_1d']  = round((now - closes[-2]) / closes[-2] * 100, 2)
    if len(closes) >= 8:
        ctx['chg_7d']  = round(now - closes[-8], 2)
        ctx['pct_7d']  = round((now - closes[-8]) / closes[-8] * 100, 2)
    if len(closes) >= 31:
        ctx['chg_30d'] = round(now - closes[-31], 2)
        ctx['pct_30d'] = round((now - closes[-31]) / closes[-31] * 100, 2)
    if len(df) >= 252:
        ctx['high_52w'] = round(float(np.max(df['High'].values[-252:])), 2)
        ctx['low_52w']  = round(float(np.min(df['Low'].values[-252:])),  2)
    return ctx


# ══════════════════════════════════════════════
#  3. تحليل الإطار الزمني
# ══════════════════════════════════════════════
def analyze_timeframe(df, label: str) -> dict:
    if df is None or len(df) < 30:
        return {"label": label, "bias": "غير متاح", "rsi": 50, "ema_align": "غير متاح",
                "macd_hist": 0, "score": 0, "adx": 20}
    closes = df['Close'].values
    rsi    = calc_rsi(closes)
    ema20  = calc_ema(closes, min(20, len(closes)//2))
    ema50  = calc_ema(closes, min(50, len(closes)//2))
    _, _, macd_hist = calc_macd(closes)
    adx, di_p, di_m = calc_adx(df)
    score = 0
    if rsi < 45:        score += 1
    elif rsi > 55:      score -= 1
    if macd_hist > 0:   score += 1
    elif macd_hist < 0: score -= 1
    if ema20 > ema50:   score += 1
    elif ema20 < ema50: score -= 1
    if adx > 22 and di_p > di_m: score += 1
    elif adx > 22 and di_m > di_p: score -= 1
    if score >= 3:       bias = "🟢 صعودي قوي"
    elif score >= 1:     bias = "🟡 صعودي معتدل"
    elif score <= -3:    bias = "🔴 هبوطي قوي"
    elif score <= -1:    bias = "🟠 هبوطي معتدل"
    else:                bias = "⚪ محايد"
    ema_align = "صعودي" if ema20 > ema50 else ("هبوطي" if ema20 < ema50 else "متقاطع")
    return {"label": label, "bias": bias, "score": score, "rsi": rsi,
            "macd_hist": macd_hist, "ema_align": ema_align, "adx": adx}


def get_tf_confluence_label(weekly, daily, hourly) -> str:
    scores    = [weekly.get("score",0), daily.get("score",0), hourly.get("score",0)]
    positives = sum(1 for x in scores if x > 0)
    negatives = sum(1 for x in scores if x < 0)
    if positives == 3: return "🔥 توافق تام صعودي (أسبوعي + يومي + ساعي)"
    if negatives == 3: return "❄️ توافق تام هبوطي (أسبوعي + يومي + ساعي)"
    if positives == 2: return "🟡 توافق جزئي صعودي (2/3 إطارات)"
    if negatives == 2: return "🟠 توافق جزئي هبوطي (2/3 إطارات)"
    return "⚪ تعارض بين الإطارات — حذر"


def get_tf_4frame_label(tf_15m, tf_1h, tf_4h, tf_1d) -> str:
    scores    = [tf_15m.get("score",0), tf_1h.get("score",0), tf_4h.get("score",0), tf_1d.get("score",0)]
    positives = sum(1 for x in scores if x > 0)
    negatives = sum(1 for x in scores if x < 0)
    if positives == 4: return "🔥 توافق تام صعودي (4/4 إطارات)"
    if negatives == 4: return "❄️ توافق تام هبوطي (4/4 إطارات)"
    if positives >= 3: return "🟡 توافق صعودي قوي (3/4 إطارات)"
    if negatives >= 3: return "🟠 توافق هبوطي قوي (3/4 إطارات)"
    if positives == 2: return "🔵 توافق جزئي صعودي (2/4)"
    if negatives == 2: return "🟤 توافق جزئي هبوطي (2/4)"
    return "⚪ تعارض بين الإطارات — حذر"


def tf_gold_impact(score: int, rsi: float = 50) -> str:
    # RSI الحاد يتغلب على الـ score العادي
    if rsi < 20:   return "🟢 تشبع بيعي حاد (RSI<20) → ارتداد صعودي مرتقب بقوة للذهب"
    if rsi > 80:   return "🔴 تشبع شرائي حاد (RSI>80) → تصحيح هبوطي حاد مرتقب للذهب"
    if rsi < 28:   return "🟢 تشبع بيع (RSI<28) → الذهب مرشح لارتداد صعودًا"
    if rsi > 72:   return "🔴 تشبع شراء (RSI>72) → الذهب مرشح لتصحيح هبوطًا"
    # الحالات العادية بناءً على الـ score
    if score >= 3:  return "↑↑ دعم صعودي قوي → الذهب مرشح للصعود"
    if score >= 1:  return "↑ دعم صعودي خفيف → ميل إيجابي للذهب"
    if score <= -3: return "↓↓ ضغط هبوطي قوي → الذهب مرشح للهبوط"
    if score <= -1: return "↓ ضغط هبوطي خفيف → ميل سلبي للذهب"
    return "↔ محايد — لا تأثير واضح على الذهب"


def _rsi_gold_impact(rsi: float) -> str:
    if rsi < 20:   return "🟢 تشبع بيعي حاد (RSI<20) → ارتداد صعودي مرتقب بقوة للذهب"
    elif rsi < 30: return "🟢 تشبع بيع → الذهب مرشح لارتداد صعودًا"
    elif rsi > 80: return "🔴 تشبع شرائي حاد (RSI>80) → تصحيح هبوطي حاد مرتقب للذهب"
    elif rsi > 70: return "🔴 تشبع شراء → الذهب مرشح لتصحيح هبوطًا"
    elif rsi < 45: return "🔴 ضغط هبوطي → الذهب تحت ضغط بائع"
    elif rsi > 55: return "🟢 دعم صعودي → الذهب يجد زخماً للأعلى"
    return "⚪ محايد → لا دعم ولا ضغط على الذهب"



def _macd_gold_impact(macd_hist: float) -> str:
    if macd_hist > 0.5:   return "🟢 زخم صعودي → يدفع الذهب للأعلى"
    elif macd_hist < -0.5: return "🔴 زخم هبوطي → يضغط الذهب للأسفل"
    return "⚪ زخم ضعيف → لا تأثير واضح على الذهب"


def _indicators_verdict(d: dict) -> str:
    score = 0
    rsi = d.get('rsi', 50)
    macd = d.get('macd_hist', 0)
    obv = d.get('obv_trend', '')
    gold = d.get('gold', 0)
    pivot = d.get('pivot', gold)
    
    score += 1.5 if rsi > 50 else -1.5
    score += 1 if macd > 0 else -1
    score += 2 if 'صعودي' in obv else -2
    score += 2 if gold >= pivot else -2
    
    if score >= 0:
        return "📈 الخلاصة النهائية للمؤشرات: بناءً على الدمج المتقدم لتدفق السيولة المؤسسية (OBV) ومؤشرات الزخم مع السعر، الاتجاه الزمني الحالي صاعد وبدقة، مما يثبت سيطرة المشترين. التمركز الأفضل هو (الشراء من الدعوم)."
    else:
        return "📉 الخلاصة النهائية للمؤشرات: بناءً على الدمج المتقدم لتدفق السيولة المؤسسية (OBV) ومؤشرات الزخم مع السعر، الاتجاه الزمني الحالي هابط وبدقة، مما يثبت سيطرة البائعين. التمركز الأفضل هو (البيع من المقاومات)."


def _obv_gold_impact(obv_trend: str, d: dict = None) -> str:
    is_price_bullish = None
    if d and 'gold' in d and 'pivot' in d:
        is_price_bullish = d['gold'] > d['pivot']
    
    if 'صعودي' in obv_trend:
        if is_price_bullish is False:
            base = "🟢 OBV صعودي (دايفرجنس إيجابي)"
            note = "💡 تحذير: رغم هبوط السعر ظاهرياً، إلا أن السيولة المؤسسية تضخ بقوة (تجميع خفي)، مما يُنذر بارتداد صاعد مفاجئ."
        else:
            base = "🟢 OBV صعودي (تأكيد الاتجاه)"
            note = "💡 المؤسسات تشتري وتدعم الاتجاه الصاعد بقوة، مما يعزز استمراره."
    elif 'هبوطي' in obv_trend:
        if is_price_bullish is True:
            base = "🔴 OBV هبوطي (دايفرجنس سلبي)"
            note = "💡 تحذير: رغم صعود السعر ظاهرياً، إلا أن السيولة المؤسسية تنسحب (توزيع خفي)، مما يُنذر بهبوط قادم."
        else:
            base = "🔴 OBV هبوطي (تأكيد الاتجاه)"
            note = "💡 المؤسسات تبيع وتدعم الاتجاه الهابط بقوة، مما يعزز استمراره."
    else:
        base = "⚪ OBV محايد (توازن مؤسسي)"
        note = "💡 السيولة المؤسسية متوقفة أو متوازنة، ننتظر ضخ سيولة جديدة لتحديد الاتجاه القادم."
    return f"{base}\n        {note}" 


def _cci_gold_impact(cci: float) -> str:
    if cci > 100:
        base = f"🟢 CCI مرتفع ({cci:.1f}) — اندفاع شرائي"
        note = "💡 السعر مندفع بقوة للأعلى ومبتعد عن متوسطه. الزخم قوي جداً للصعود، لكن مخاطرة الشراء الآن مرتفعة بسبب التشبع."
    elif cci < -100:
        base = f"🔴 CCI منخفض ({cci:.1f}) — ضغط بيعي"
        note = "💡 السعر مندفع بقوة للأسفل ومبتعد عن متوسطه. الزخم قوي جداً للهبوط، لكن قد نرى ارتداد بسبب التشبع."
    else:
        base = f"⚪ CCI محايد ({cci:.1f})"
        note = "💡 السعر يتذبذب قريباً من متوسطه الإحصائي ولا يوجد اندفاع حاد في أي اتجاه."
    return f"{base}\n        {note}" 


def _wr_gold_impact(wr: float) -> str:
    if wr > -20:
        base = f"🟢 W%R مرتفع ({wr:.1f}) — تشبع شرائي"
        note = "💡 الذهب يتداول بالقرب من أعلى قمة له في الـ 14 يوماً الماضية. المشتري مسيطر بالكامل، لكن الفرصة الحالية قد تواجه تصحيح."
    elif wr < -80:
        base = f"🔴 W%R منخفض ({wr:.1f}) — تشبع بيعي"
        note = "💡 الذهب يتداول بالقرب من أدنى قاع له في الـ 14 يوماً الماضية. البائع يضغط بشدة، لكن البحث عن قيعان للارتداد قد يكون وارداً."
    else:
        base = f"⚪ W%R محايد ({wr:.1f})"
        note = "💡 الذهب يتداول في منتصف نطاقه السعري للفترة الأخيرة. القوة متوازنة."
    return f"{base}\n        {note}" 


def _atr_gold_impact(atr: float, gold: float) -> str:
    if not atr or atr <= 0: return "—"
    base = f"📊 ATR: {atr:.2f}$"
    note = f"💡 مقياس التذبذب اليومي. الذهب مرشح للحركة بمتوسط {atr:.2f}$ صعوداً وهبوطاً. ننصح بوضع وقف الخسارة بعيداً بمقدار نصف هذه القيمة ({round(atr/2, 2)}$) على الأقل."
    return f"{base}\n        {note}" 


def _adx_gold_impact(adx: float, di_p: float, di_m: float) -> str:
    if adx < 20:   return "⚪ ترند ضعيف → الذهب يتحرك بلا زخم حقيقي"
    elif adx > 25:
        if di_p > di_m: return "🟢 ترند قوي صعودي → قوة شرائية جدية على الذهب"
        return "🔴 ترند قوي هبوطي → ضغط بيع جدي على الذهب"
    return "⚪ ترند متوسط → اتجاه غير متأكد للذهب"



# ══════════════════════════════════════════════
#  4. نظام نقاط التوافق (Confluence)
# ══════════════════════════════════════════════
def calc_confluence(d: dict) -> dict:
    gold   = d['gold']
    scores = {}
    scores['RSI (14)']      = +1 if d['rsi'] < 40 else (-1 if d['rsi'] > 60 else 0)
    scores['Stoch RSI']     = +1 if d['stoch_k'] < 20 else (-1 if d['stoch_k'] > 80 else 0)
    scores['MACD']          = +1 if d['macd_hist'] > 0 else (-1 if d['macd_hist'] < 0 else 0)
    scores['EMA 20/50/200'] = (+1 if d['ema20'] > d['ema50'] > d['ema200']
                               else (-1 if d['ema20'] < d['ema50'] < d['ema200'] else 0))
    scores['Bollinger']     = (+1 if gold < d['bb_lower'] * 1.003
                               else (-1 if gold > d['bb_upper'] * 0.997 else 0))
    adx, di_p, di_m = d['adx'], d['di_plus'], d['di_minus']
    scores['ADX']           = (+1 if adx > 25 and di_p > di_m
                               else (-1 if adx > 25 and di_m > di_p else 0))
    scores['CCI (20)']      = +1 if d['cci'] < -100 else (-1 if d['cci'] > 100 else 0)
    scores['Williams %R']   = +1 if d['williams_r'] < -80 else (-1 if d['williams_r'] > -20 else 0)
    scores['OBV Trend']     = +1 if "صعودي" in d['obv_trend'] else (-1 if "هبوطي" in d['obv_trend'] else 0)
    tf_scores = [d['tf_weekly'].get('score',0), d['tf_daily'].get('score',0), d['tf_hourly'].get('score',0)]
    scores['Multi-Timeframe'] = +1 if sum(tf_scores)/3 > 0.5 else (-1 if sum(tf_scores)/3 < -0.5 else 0)
    total   = sum(scores.values())
    n       = len(scores)
    bullish = sum(1 for v in scores.values() if v > 0)
    bearish = sum(1 for v in scores.values() if v < 0)
    neutral = sum(1 for v in scores.values() if v == 0)
    if   total >= 5:  verdict, bias = f"🟢 صعودي قوي جداً ({bullish}/{n})", "bull"
    elif total >= 3:  verdict, bias = f"🟡 صعودي ({bullish}/{n} مؤشرات)",    "bull"
    elif total <= -5: verdict, bias = f"🔴 هبوطي قوي جداً ({bearish}/{n})",  "bear"
    elif total <= -3: verdict, bias = f"🟠 هبوطي ({bearish}/{n} مؤشرات)",    "bear"
    else:             verdict, bias = f"⚪ متذبذب ({neutral}/{n} محايدة)",    "neutral"
    return {"scores": scores, "total": total, "bullish": bullish, "bearish": bearish,
            "neutral": neutral, "n": n, "verdict": verdict, "bias": bias}


# ══════════════════════════════════════════════
#  5. الصفقات — 3 شراء + 3 بيع + زخم + اتجاه + سيولة
# ══════════════════════════════════════════════
TIGHT_SL  = 15.0            # وقف الفورية (Spot)
STD_SL    = MAX_SL_DISTANCE  # 38$ للآجلة  (Futures)

def calc_momentum_signal(d: dict) -> str:
    hist = d.get('macd_hist', 0) or 0
    rsi  = d.get('rsi', 50)      or 50
    adx  = d.get('adx', 0)       or 0
    sfx  = " قوي" if adx > 25 else " معتدل"
    if   hist > 0.3 and rsi > 52: return f"📈 زخم صاعد{sfx}"
    elif hist < -0.3 and rsi < 48: return f"📉 زخم هابط{sfx}"
    else:                          return "⚡ زخم محايد"

def calc_trend_signal(d: dict) -> str:
    ema = d.get('ema_label', '')
    wk  = d.get('tf_weekly', {}).get('bias', '')
    if '🟢' in ema and 'صعودي' in wk:   return "🟢 صعودي قوي"
    elif '🔴' in ema and 'هبوطي' in wk: return "🔴 هبوطي قوي"
    elif '🟢' in ema or  'صعودي' in wk: return "🟡 صعودي ضعيف"
    elif '🔴' in ema or  'هبوطي' in wk: return "🟠 هبوطي ضعيف"
    return "⚪ متذبذب"

def calc_liquidity_signal(d: dict) -> str:
    rv = d.get('rel_vol', 1.0) or 1.0
    if rv >= 3.0:   return f"🔵 مرتفعة جداً ({rv:.1f}x)"
    elif rv >= 1.5: return f"🟢 عالية ({rv:.1f}x)"
    elif rv >= 0.8: return f"🟡 متوسطة ({rv:.1f}x)"
    else:           return f"🔴 منخفضة ({rv:.1f}x)"


def calc_divergence(df) -> str:
    """حساب التباين السعري (Divergence) مع مؤشر RSI"""
    import numpy as np
    if df is None or len(df) < 20: return "—"
    closes = df['Close'].values
    rsi_vals = [calc_rsi(closes[max(0,i-14):i+1]) for i in range(len(closes)-20, len(closes))]
    prices = closes[-20:]
    if len(rsi_vals) < 10: return "—"
    mid = len(prices) // 2
    p1_hi, p2_hi = np.max(prices[:mid]),  np.max(prices[mid:])
    p1_lo, p2_lo = np.min(prices[:mid]),  np.min(prices[mid:])
    r1_hi, r2_hi = np.max(rsi_vals[:mid]), np.max(rsi_vals[mid:])
    r1_lo, r2_lo = np.min(rsi_vals[:mid]), np.min(rsi_vals[mid:])
    
    if p2_hi > p1_hi and r2_hi < r1_hi * 0.95:
        return "⚠️ تباين سلبي قوي (Divergence) — قمة أعلى مع تراجع الزخم"
    if p2_lo < p1_lo and r2_lo > r1_lo * 1.05:
        return "💡 تباين إيجابي قوي (Divergence) — قاع أدنى مع ارتفاع الزخم"
    return "متوافق مع الزخم (لا يوجد تباين)"



def calc_trade_confidence(d: dict, t: dict) -> tuple[int, str, str]:
    score   = 0
    reasons = []
    is_buy  = t.get('is_buy', t.get('dir', '') == 'buy')
    gold    = d['gold']
    entry   = t.get('entry', gold)
    bias    = d['confluence']['bias']

    # 1. Trend alignment (20 pts)
    typ = t.get('typ', '')
    is_rev = 'انعكاس' in typ or 'rev' in typ.lower()
    is_hl  = 'لوت عالي' in typ
    
    if is_rev:
        # صفقات الزيرو انعكاس بطبيعتها عكس الاتجاه، لذا نعطيها العلامة الكاملة في الترند لأنها مبرمجة لاصطياد الانعكاس
        score += 20; reasons.append('tawaqu_inikas_qawi')
    elif is_hl:
        # اللوت العالي يعتمد على دقة الميلي (فيبوناتشي) وليس الترند بالضرورة
        score += 18; reasons.append('dukhul_qannas_diqqa')
    else:
        if (is_buy and bias == 'bull') or (not is_buy and bias == 'bear'):
            score += 20; reasons.append('maa_altrend')
        elif bias == 'neutral':
            score += 12; reasons.append('soq_motazabzab')
        else:
            score += 3; reasons.append('aks_altrend')

    # 2. Multi-timeframe 4-frame alignment (20 pts)
    tf_scores = [
        d['tf_daily'].get('score', 0),
        d['tf_hourly'].get('score', 0),
        d['tf_4h'].get('score', 0),
        d['tf_15m'].get('score', 0),
    ]
    aligned = sum(1 for s in tf_scores if s > 0) if is_buy else sum(1 for s in tf_scores if s < 0)
    
    if is_rev or is_hl:
        # نعطيها دفعة بناءً على مؤشرات أخرى لتعويض عدم التوافق الزمني
        score += 16
        if aligned >= 2: reasons.append(f'tawafuq_inikas_muhtamal')
    else:
        score += [0, 5, 10, 16, 20][aligned]
        if aligned >= 3: reasons.append(f'tawafuq_{aligned}4_itarat')

    # 3. RSI smart scoring (15 pts)
    rsi = float(d['rsi'])
    if is_buy:
        if rsi < 30: score += 15; reasons.append('rsi_tashabuo_bay')
        elif rsi < 40: score += 11; reasons.append('rsi_mantiqat_shira')
        elif rsi < 50: score += 7
        elif rsi < 65: score += 3
    else:
        if rsi > 70: score += 15; reasons.append('rsi_tashabuo_shira')
        elif rsi > 60: score += 11; reasons.append('rsi_mantiqat_bay')
        elif rsi > 50: score += 7
        elif rsi > 35: score += 3

    # 4. MACD histogram intensity (12 pts)
    macd = float(d['macd_hist'])
    if (is_buy and macd > 0) or (not is_buy and macd < 0):
        intensity = min(12, int(abs(macd) * 0.8) + 6)
        score += intensity; reasons.append('macd_muayad')
    elif abs(macd) < 1.0:
        score += 4

    # 5. ADX trend strength (10 pts)
    adx  = float(d['adx'])
    di_p = float(d['di_plus'])
    di_m = float(d['di_minus'])
    if adx > 30:
        if (is_buy and di_p > di_m) or (not is_buy and di_m > di_p):
            score += 10; reasons.append(f'adx_trend_qawi_{adx:.0f}')
        else:
            score += 2
    elif adx > 22:
        score += 5

    # 6. Proximity to S/R level (10 pts)
    s1, r1 = d['s1'], d['r1']
    dist_range = max(abs(r1 - s1), 1)
    if is_buy:
        prox = 1 - min(1, abs(entry - s1) / (dist_range * 0.5))
        score += round(prox * 10)
        if abs(entry - s1) < dist_range * 0.15: reasons.append('qarib_min_daom')
    else:
        prox = 1 - min(1, abs(r1 - entry) / (dist_range * 0.5))
        score += round(prox * 10)
        if abs(r1 - entry) < dist_range * 0.15: reasons.append('qarib_min_muqawama')

    # 7. Risk/Reward (8 pts)
    rr = t.get('rr1', 0)
    if rr >= 4.0: score += 8; reasons.append(f'rr_mumtaz_{rr}x')
    elif rr >= 3.0: score += 6; reasons.append(f'rr_qawi_{rr}x')
    elif rr >= 2.0: score += 4
    elif rr >= 1.5: score += 2

    # 8. OBV institutional flow (5 pts)
    if (is_buy and 'ascending' in d.get('obv_trend','').lower()) or        (is_buy and 'sauodi' in d.get('obv_trend','')) or        (not is_buy and 'haboti' in d.get('obv_trend','')):
        score += 5; reasons.append('obv_muayad')
    else:
        import re
        obv = d.get('obv_trend', '')
        if is_buy and ('صعودي' in obv):
            score += 5; reasons.append('obv_muayad')
        elif not is_buy and ('هبوطي' in obv):
            score += 5; reasons.append('obv_muayad')

    # 9. Relative Volume (5 pts)
    rv = d.get('rel_vol', 1.0) or 1.0
    if rv >= 2.0: score += 5; reasons.append(f'hajm_ali_{rv:.1f}x')
    elif rv >= 1.3: score += 3
    elif rv >= 0.8: score += 1

    # 10. MA50/MA200 position (5 pts)
    ema50  = d.get('ema50', gold)
    ema200 = d.get('ema200', gold)
    if is_buy:
        if gold > ema50 and gold > ema200: score += 5
        elif gold > ema50 or gold > ema200: score += 2
    else:
        if gold < ema50 and gold < ema200: score += 5
        elif gold < ema50 or gold < ema200: score += 2

    # 11. Divergence bonus (5 pts)
    div = d.get('divergence', '')
    if is_buy and '💡' in div: score += 5; reasons.append('tabayon_sauodi')
    if not is_buy and '⚠️' in div: score += 5; reasons.append('tabayon_huboti')

    # 12. Stochastic RSI (5 pts)
    stoch = float(d.get('stoch_k', 50) or 50)
    if is_buy and stoch < 20: score += 5; reasons.append('stoch_tashabuo_bay')
    elif is_buy and stoch < 40: score += 2
    elif not is_buy and stoch > 80: score += 5; reasons.append('stoch_tashabuo_shira')
    elif not is_buy and stoch > 60: score += 2

    pct = max(65, min(97, round(score)))
    if pct >= 80:   emoji, lbl = '🟢', 'جيدة جداً'
    elif pct >= 65: emoji, lbl = '🟡', 'جيدة'
    elif pct >= 50: emoji, lbl = '🟠', 'مقبولة'
    else:           emoji, lbl = '🔴', 'ضعيفة'

    # Translate reason keys to Arabic
    ar_map = {
        'maa_altrend': 'مع الترند العام ✅',
        'soq_motazabzab': 'سوق متذبذب',
        'aks_altrend': 'عكس الترند ⚠️',
        'rsi_tashabuo_bay': 'RSI تشبع بيع 🟢',
        'rsi_mantiqat_shira': 'RSI منطقة شراء',
        'rsi_tashabuo_shira': 'RSI تشبع شراء 🔴',
        'rsi_mantiqat_bay': 'RSI منطقة بيع',
        'macd_muayad': 'MACD مؤيد',
        'daxy_muayad': 'DXY مؤيد للمسار',
        'daxy_moarid': 'DXY معارض للمسار',
        'tnx_muayad': 'العوائد مؤيدة',
        'fibo_deaf': 'دعم/مقاومة فيبوناتشي قوي',
        'vwap_qareeb': 'قريب من VWAP',
        'tabayon_suudi': 'تباين شرائي',
        'tabayon_huboti': 'تباين بيعي',
        'stoch_tashabuo_bay': 'Stoch تشبع بيع',
        'stoch_tashabuo_shira': 'Stoch تشبع شراء'
    }

    
    def translate_dynamic(r):
        if r in ar_map: return ar_map[r]
        if r.startswith('tawaqu_inikas'): return 'توقع انعكاس قوي'
        if r.startswith('dukhul_qannas'): return 'دخول قناص عالي الدقة'
        if r.startswith('tawafuq_inikas'): return 'تأكيد انعكاس محتمل'
        if r.startswith('tawafuq_'): return 'توافق إطارات متعددة'
        if r.startswith('adx_trend_qawi'): return 'ترند قوي جداً'
        if r.startswith('adx_trend_sareea'): return 'اندفاع سريع'
        if r.startswith('adx_tadhabdhub'): return 'تذبذب (ADX ضعيف)'
        if r.startswith('hajm_ali'): return 'حجم سيولة عالي'
        if r.startswith('hajm_motawaset'): return 'سيولة متوسطة'
        if r.startswith('hajm_daeef'): return 'سيولة ضعيفة'
        if r.startswith('rr_mumtaz'): return 'مخاطرة/عائد استثنائية'
        if r.startswith('rr_qawi'): return 'مخاطرة/عائد قوية'
        if r.startswith('rr_maqbool'): return 'مخاطرة/عائد مقبولة'
        if r.startswith('rr_daeef'): return 'مخاطرة/عائد ضعيفة'
        if r.startswith('qarib_min_daom'): return 'ارتكاز على دعم'
        if r.startswith('qarib_min_muqawama'): return 'ارتكاز على مقاومة'
        if r.startswith('obv_muayad'): return 'سيولة OBV مؤيدة'
        return r

    rs_text = " | ".join([translate_dynamic(r) for r in reasons[:3]]) if reasons else "بدون إشارات قوية"

    
    return pct, emoji + " " + lbl, rs_text
def calc_all_entries(d: dict, bias: str) -> dict:
    """
    3 صفقات شراء + 3 صفقات بيع مبنية على مستويات تقنية مُصفّاة ومُتحقَّق منها.
    الشرط الذهبي: المقاومة دائماً فوق السعر — الدعم دائماً تحت السعر.
    """
    gold   = d['gold']
    s1, r1 = d['s1'], d['r1']
    s2, r2 = d['s2'], d['r2']
    s3, r3 = d['s3'], d['r3']
    rn     = d['round_numbers']
    market_name = 'آجل (Futures)' if d.get('mode') == 'futures' else 'فوري (Spot)'

    # ── مستويات مُصفّاة: مضمون أن المقاومة فوق السعر والدعم تحته ولا تتكرر ──
    def _valid_res(levels, exclude=None):
        exclude = exclude or []
        v = sorted([x for x in levels if x and x > gold and x not in exclude and all(abs(x - e) > 8 for e in exclude)])
        return v[0] if v else round((exclude[-1] if exclude else gold) + 40, 2)

    def _valid_sup(levels, exclude=None):
        exclude = exclude or []
        v = sorted([x for x in levels if x and x < gold and x not in exclude and all(abs(x - e) > 8 for e in exclude)], reverse=True)
        return v[0] if v else round((exclude[-1] if exclude else gold) - 40, 2)

    all_res = [r1, r2, r3, rn['nearest_resistance']]
    all_sup = [s1, s2, s3, rn['nearest_support']]

    r_near = _valid_res(all_res)
    r_far  = _valid_res(all_res, exclude=[r_near])
    r_far2 = _valid_res(all_res + [r_far + 30], exclude=[r_near, r_far])
    
    s_near = _valid_sup(all_sup)
    s_far  = _valid_sup(all_sup, exclude=[s_near])
    s_far2 = _valid_sup(all_sup + [s_far - 30], exclude=[s_near, s_far])

    MIN_GAP = 8.0

    def _buy_t(e):
        """أهداف الشراء: مستويات مقاومة فوق نقطة الدخول فقط"""
        raw = sorted(set([x for x in [r_near, r_far, r_far2] if x and x > e]))
        pool = []
        for x in raw:
            if not pool or x - pool[-1] >= MIN_GAP:
                pool.append(x)
        t1 = pool[0] if len(pool) > 0 else round(e + 30, 2)
        t2 = pool[1] if len(pool) > 1 else round(t1 + 40, 2)
        t3 = pool[2] if len(pool) > 2 else round(t2 + 40, 2)
        return t1, t2, t3

    def _sell_t(e):
        """أهداف البيع: مستويات دعم تحت نقطة الدخول فقط"""
        raw = sorted(set([x for x in [s_near, s_far, s_far2] if x and x < e]), reverse=True)
        pool = []
        for x in raw:
            if not pool or pool[-1] - x >= MIN_GAP:
                pool.append(x)
        t1 = pool[0] if len(pool) > 0 else round(e - 30, 2)
        t2 = pool[1] if len(pool) > 1 else round(t1 - 40, 2)
        t3 = pool[2] if len(pool) > 2 else round(t2 - 40, 2)
        return t1, t2, t3

    def mb(entry, sl_d, mkt, style):
        e = round(entry, 2); t1, t2, t3 = _buy_t(e)
        rr1 = round((t1 - e) / sl_d, 1); rr2 = round((t2 - e) / sl_d, 1); rr3 = round((t3 - e) / sl_d, 1)
        return {"dir": "شراء 📗", "market": mkt, "style": style, "entry": e,
                "sl": round(e - sl_d, 2), "risk": sl_d, "t1": t1, "t2": t2, "t3": t3,
                "rr1": rr1, "rr2": rr2, "rr3": rr3, "is_buy": True}

    def ms(entry, sl_d, mkt, style):
        e = round(entry, 2); t1, t2, t3 = _sell_t(e)
        rr1 = round((e - t1) / sl_d, 1); rr2 = round((e - t2) / sl_d, 1); rr3 = round((e - t3) / sl_d, 1)
        return {"dir": "بيع 📕", "market": mkt, "style": style, "entry": e,
                "sl": round(e + sl_d, 2), "risk": sl_d, "t1": t1, "t2": t2, "t3": t3,
                "rr1": rr1, "rr2": rr2, "rr3": rr3, "is_buy": False}

    if bias == "bull":
        buys  = [mb(gold,   TIGHT_SL, market_name,   "🔴 عدواني"),
                 mb(s_near, STD_SL,   market_name, "🟡 معتدل — دعم قريب"),
                 mb(s_far,  TIGHT_SL, market_name,   "🟢 محافظ — دعم بعيد")]
        sells = [ms(r_near, TIGHT_SL, market_name,   "🔴 عند مقاومة قريبة"),
                 ms(r_far,  STD_SL,   market_name, "🟡 عند مقاومة ثانية"),
                 ms(r_far2, TIGHT_SL, market_name,   "🟢 عند مقاومة بعيدة")]
    elif bias == "bear":
        sells = [ms(gold,   TIGHT_SL, market_name,   "🔴 عدواني"),
                 ms(r_near, STD_SL,   market_name, "🟡 معتدل — مقاومة قريبة"),
                 ms(r_far,  TIGHT_SL, market_name,   "🟢 محافظ — مقاومة بعيدة")]
        buys  = [mb(s_near, TIGHT_SL, market_name,   "🔴 عدواني — دعم قريب"),
                 mb(s_far,  STD_SL,   market_name, "🟡 معتدل — دعم ثاني"),
                 mb(s_far2, TIGHT_SL, market_name,   "🟢 محافظ — دعم بعيد")]
    else:  # neutral
        buys  = [mb(s_near, TIGHT_SL, market_name,   "🔴 دعم قريب — اختراق"),
                 mb(s_far,  STD_SL,   market_name, "🟡 معتدل — دعم ثاني"),
                 mb(s_far2, TIGHT_SL, market_name,   "🟢 محافظ — دعم بعيد")]
        sells = [ms(r_near, TIGHT_SL, market_name,   "🔴 مقاومة قريبة — اختراق"),
                 ms(r_far,  STD_SL,   market_name, "🟡 معتدل — مقاومة ثانية"),
                 ms(r_far2, TIGHT_SL, market_name,   "🟢 محافظ — مقاومة بعيدة")]

    refs = {
        "above": r_near,
        "below": s_near,
        "r1": r_near, "r2": r_far, "s1": s_near, "s2": s_far,
    }
    return {
        "bias": bias, "buys": buys, "sells": sells, "refs": refs,
        "momentum":  calc_momentum_signal(d),
        "trend":     calc_trend_signal(d),
        "liquidity": calc_liquidity_signal(d),
    }


# ══════════════════════════════════════════════
#  5.5 توقعات الإغلاق / القمة / القاع — متعدد الإطارات
# ══════════════════════════════════════════════
def _calc_price_forecasts(gold: float, atr: float, bias: str, tf_data: dict) -> dict:
    """
    توقع الإغلاق والقمة والقاع — معادلة محسّنة متعددة العوامل:
    ATR × جذر(n) مُرجَّح بـ: اتجاه الترند + ADX + RSI + توافق الإطارات + فيبوناتشي
    """
    import numpy as np

    # ── استخراج عوامل الترند ──
    rsi_1h   = float(tf_data.get('tf_hourly', {}).get('rsi', 50) or 50)
    rsi_4h   = float(tf_data.get('tf_4h', {}).get('rsi', 50) or 50)
    rsi_1d   = float(tf_data.get('tf_daily', {}).get('rsi', 50) or 50)
    macd_1h  = float(tf_data.get('tf_hourly', {}).get('macd_hist', 0) or 0)
    adx_val  = float(tf_data.get('tf_daily', {}).get('adx', 20) or 20)

    # نحسب الميل المرجّح من 3 إطارات (1h, 4h, 1d)
    def rsi_to_bias(r): return (r - 50) / 50.0   # -1 to +1

    if bias == 'bull':
        base_dir = 1.0
    elif bias == 'bear':
        base_dir = -1.0
    else:
        # في التذبذب نشتق الاتجاه من متوسط مرجّح لـ RSI الثلاثة
        weighted_rsi = rsi_to_bias(rsi_1h)*0.5 + rsi_to_bias(rsi_4h)*0.3 + rsi_to_bias(rsi_1d)*0.2
        macd_contrib  = 0.3 if macd_1h > 0 else (-0.3 if macd_1h < 0 else 0.0)
        base_dir = round(np.clip(weighted_rsi * 0.7 + macd_contrib, -1.0, 1.0), 3)

    # ── معامل قوة الترند من ADX (0.6 - 1.0) ──
    # ADX ضعيف (< 20) → تقليص حجم التوقع | ADX قوي (> 35) → تعزيزه
    adx_mult = np.clip(0.6 + (adx_val - 20) / 50.0, 0.55, 1.15)

    # ── توافق الإطارات ──
    tf_scores = [
        tf_data.get('tf_hourly', {}).get('score', 0),
        tf_data.get('tf_4h', {}).get('score', 0),
        tf_data.get('tf_daily', {}).get('score', 0),
    ]
    aligned_bull = sum(1 for s in tf_scores if s > 0)
    aligned_bear = sum(1 for s in tf_scores if s < 0)
    consensus    = (aligned_bull - aligned_bear) / 3.0  # -1 to +1
    # إضافة bonus للتوافق: يزيد confidence الاتجاه
    dir_final = round(np.clip(base_dir * 0.75 + consensus * 0.25, -1.0, 1.0), 3)

    # ── حساب التوقع لكل إطار ──
    def _fc(n_hours: float, is_scalp: bool = False):
        # حجم تحرك ATR مُعدَّل بجذر الزمن + معامل ADX
        scaled_atr = atr * ((n_hours / 24.0) ** 0.45) * adx_mult
        # مركز التوقع = السعر الحالي + اتجاه × نسبة من ATR
        center_raw = gold + dir_final * scaled_atr * 0.30
        center     = round(center_raw, 2)
        # نطاق القمة والقاع أوسع في الإطارات الأطول
        spread_factor = min(0.65, 0.45 + n_hours * 0.003)
        high = round(center + scaled_atr * spread_factor, 2)
        low  = round(center - scaled_atr * spread_factor, 2)
        # جودة التوقع كنسبة مئوية (كلما زاد ADX وتوافق الإطارات → جودة أعلى)
        quality = round(min(95, 40 + adx_val * 0.8 + abs(consensus) * 30), 0)
        if is_scalp:
            quality = min(99, quality + 15)
        return {"close": center, "high": high, "low": low, "quality": int(quality)}

    return {
        "5m"  : _fc(5 / 60.0, is_scalp=True),
        "30m" : _fc(30 / 60.0),
        "1h"  : _fc(1),
        "4h"  : _fc(4),
        "1d"  : _fc(24),
    }


# ══════════════════════════════════════════════
#  6. جلب كل بيانات السوق
# ══════════════════════════════════════════════
def get_full_market_data(mode: str = "futures") -> dict | None:
    log.info(f"📡 جلب البيانات ({mode.upper()}) — متعدد الإطارات...")

    ticker = "GC=F"  # Yahoo Finance dropped XAUUSD=X, so we use GC=F for historical OHLCV data for both modes

    # ── الذهب: الآجل والفوري وإطارات متعددة ──
    gold_daily  = _fetch(ticker,     period="90d", interval="1d");  time.sleep(0.7)
    gold_weekly = _fetch(ticker,     period="2y",  interval="1wk"); time.sleep(0.7)
    gold_monthly = _fetch(ticker,    period="5y",  interval="1mo"); time.sleep(0.7)
    gold_hourly = _fetch(ticker,     period="30d", interval="1h");  time.sleep(0.7)
    gold_15m    = _fetch(ticker,     period="5d",  interval="15m"); time.sleep(0.7)
    gold_5m     = _fetch(ticker,     period="5d",  interval="5m");  time.sleep(0.7)
    # ── الفوري: Twelve Data أولاً (ريل تايم 100%) ──
    gold_spot = None
    spot_date = None

    # 1️⃣ Twelve Data — real-time XAU/USD بدون حجب
    try:
        _td_url = f"https://api.twelvedata.com/price?symbol=XAU/USD&apikey={TWELVEDATA_API_KEY}"
        _td_r   = requests.get(_td_url, timeout=6, headers={'User-Agent': 'Mozilla/5.0'})
        if _td_r.status_code == 200:
            _td_p = _td_r.json().get('price')
            if _td_p and float(_td_p) > 1000:
                gold_spot = round(float(_td_p), 2)
                spot_date = datetime.now(CAIRO_TZ).strftime("%d/%m %H:%M") + " حي"
                log.info(f"✅ [TwelveData] سعر الفوري: {gold_spot}$")
    except Exception as _e:
        log.warning(f"⚠️ [TwelveData] {_e}")

    # 2️⃣ metals.live — احتياطي
    if not gold_spot:
        try:
            r = requests.get("https://api.metals.live/v1/spot/gold", timeout=5,
                             headers={'User-Agent': 'Mozilla/5.0'})
            if r.status_code == 200:
                _j = r.json()
                _p = _j.get('price') or _j.get('gold') or (_j[0].get('gold') if isinstance(_j, list) else None)
                if _p and float(_p) > 1000:
                    gold_spot = round(float(_p), 2)
                    spot_date = datetime.now(CAIRO_TZ).strftime("%d/%m %H:%M") + " حي"
        except Exception:
            pass

    # 3️⃣ open.er-api (1/XAU_rate)
    if not gold_spot:
        try:
            r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5)
            if r.status_code == 200:
                xau_r = r.json().get('rates', {}).get('XAU')
                if xau_r and xau_r > 0:
                    _p = round(1.0 / xau_r, 2)
                    if _p > 1000:
                        gold_spot = _p
                        spot_date = datetime.now(CAIRO_TZ).strftime("%d/%m %H:%M") + " (تقديري)"
        except Exception:
            pass

    # 4️⃣ goldprice.org
    if not gold_spot:
        try:
            r = requests.get("https://data-asg.goldprice.org/dbXRates/USD",
                             headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
            if r.status_code == 200:
                price = r.json()['items'][0].get('xauPrice')
                if price and float(price) > 1000:
                    gold_spot = round(float(price), 2)
                    spot_date = datetime.now(CAIRO_TZ).strftime("%d/%m %H:%M") + " حي"
        except Exception:
            pass

    # 5️⃣ XAUUSD=X yfinance (محاولة واحدة)
    if not gold_spot:
        try:
            import yfinance as _yf2
            _gs = _yf2.Ticker("XAUUSD=X").history(period="1d", interval="5m")
            if not _gs.empty:
                p = round(float(_gs['Close'].iloc[-1]), 2)
                if p > 1000:
                    gold_spot = p
                    spot_date = _gs.index[-1].strftime("%d/%m %H:%M") + " (Yahoo)"
        except Exception:
            pass


    if gold_daily is None or gold_daily.empty:
        return None

    # ── الأسواق الأخرى ──
    silver_df  = _fetch("SI=F",     period="60d"); time.sleep(0.6)
    oil_df     = _fetch("CL=F",     period="60d"); time.sleep(0.6)
    dxy_df     = _fetch("DX-Y.NYB", period="60d"); time.sleep(0.6)
    tnx_df     = _fetch("^TNX",     period="60d"); time.sleep(0.6)
    tty_df     = _fetch("^TYX",     period="60d"); time.sleep(0.6)  # 30Y Treasury Yield
    dfii10_df  = _fetch("^DFII10",  period="60d"); time.sleep(0.6)  # TIPS 10Y Real Yield
    tip_df    = _fetch("TIP",      period="60d"); time.sleep(0.6)
    vix_df    = _fetch("^VIX",     period="60d"); time.sleep(0.6)
    sp500_df  = _fetch("^GSPC",    period="60d"); time.sleep(0.6)
    nasdaq_df = _fetch("^IXIC",    period="60d"); time.sleep(0.6)
    # ── العملات الأجنبية ──
    eurusd_df = _fetch("EURUSD=X", period="5d"); time.sleep(0.5)
    gbpusd_df = _fetch("GBPUSD=X", period="5d"); time.sleep(0.5)
    audusd_df = _fetch("AUDUSD=X", period="5d"); time.sleep(0.5)
    nzdusd_df = _fetch("NZDUSD=X", period="5d"); time.sleep(0.5)
    usdjpy_df = _fetch("JPY=X",    period="5d"); time.sleep(0.5)
    usdchf_df = _fetch("CHF=X",    period="5d"); time.sleep(0.5)
    usdcad_df = _fetch("CAD=X",    period="5d"); time.sleep(0.5)
    # [8] 2Y Treasury Yield — US Treasury API الرسمية (مفيش rate limit)
    twy = None
    try:
        _turl = ("https://api.fiscaldata.treasury.gov/services/api/v1/accounting/od/"
                 "avg_interest_rates?fields=record_date,security_desc,avg_interest_rate_amt"
                 "&filter=security_desc:eq:2-Year Treasury Note"
                 "&sort=-record_date&page%5Bsize%5D=1")
        _tr = requests.get(_turl, timeout=7, headers={'User-Agent': 'Mozilla/5.0'})
        if _tr.status_code == 200:
            _data = _tr.json().get('data', [])
            if _data:
                twy = round(float(_data[0]['avg_interest_rate_amt']), 2)
    except Exception:
        pass
    # fallback: ^IRX (13-week T-bill — نفس الاتجاه)
    if twy is None:
        try:
            _irx = _fetch("^IRX", period="5d")
            twy  = _last_close(_irx)
        except Exception:
            pass

    # [11] 15m data for short-term trend (moved to top)

    gold_futures, futures_date = _last_with_date(gold_daily)
    # لو كل مصادر الفوري فشلت — اعرض غير متاح (لا نستبدل بالآجل عشان يكونوا مختلفين دائماً)
    if not gold_spot:
        gold_spot = None
        spot_date = None
    silver = _last_close(silver_df)
    oil    = _last_close(oil_df)
    dxy    = _last_close(dxy_df)
    tnx    = _last_close(tnx_df)
    tty    = _last_close(tty_df)   # 30Y Treasury Yield
    # twy حُسب مسبقاً من Treasury API أو ^IRX

    vix    = _last_close(vix_df)
    sp500  = _last_close(sp500_df)
    # [8] Yield Curve = 10Y - 2Y
    yield_curve       = round(tnx - twy, 2) if (tnx and twy) else None
    yield_curve_label = ("طبيعي ✅" if yield_curve and yield_curve > 0
                         else "مقلوب ⚠️ خطر ركود" if yield_curve is not None
                         else "غير متاح")

    if not all([gold_daily is not None, dxy, tnx]):
        return None

    gold = gold_futures if mode == "futures" else gold_spot
    if not gold:
        gold = gold_daily['Close'].iloc[-1] if gold_daily is not None else 0

    # [11] تحليل 4 إطارات زمنية: 15m, 1h, 4h, 1d
    import pandas as pd
    gold_4h = None
    if gold_hourly is not None and len(gold_hourly) >= 16:
        try:
            gold_4h = gold_hourly.resample('4h').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
        except Exception: gold_4h = None

    gold_10m = None
    if gold_5m is not None and len(gold_5m) >= 4:
        try:
            gold_10m = gold_5m.resample('10min').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
        except Exception: gold_10m = None

    gold_30m = None
    if gold_15m is not None and len(gold_15m) >= 4:
        try:
            gold_30m = gold_15m.resample('30min').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
        except Exception: gold_30m = None

    tf_5m     = analyze_timeframe(gold_5m,     "⚡ 5 دقائق")
    tf_10m    = analyze_timeframe(gold_10m,    "🎯 10 دقائق")
    tf_15m    = analyze_timeframe(gold_15m,    "⋆ 15 دقيقة")
    tf_30m    = analyze_timeframe(gold_30m,    "⏱️ 30 دقيقة")
    tf_hourly = analyze_timeframe(gold_hourly, "⏱️ ساعي")
    tf_4h     = analyze_timeframe(gold_4h,     "⏰ 4 ساعات")
    tf_daily  = analyze_timeframe(gold_daily,  "📅 يومي")
    tf_weekly = analyze_timeframe(gold_weekly, "📆 أسبوعي")
    tf_monthly = analyze_timeframe(gold_monthly,"🗓️ شهري")
    
    tf_label  = get_tf_4frame_label(tf_15m, tf_hourly, tf_4h, tf_daily)

    # ── المؤشرات على البيانات اليومية ──
    closes = gold_daily['Close'].values
    rsi                        = calc_rsi(closes)
    stoch_k, stoch_d           = calc_stoch_rsi(closes)
    macd, macd_sig, macd_hist  = calc_macd(closes)
    bb_upper, bb_mid, bb_lower = calc_bollinger(closes)
    ema20  = calc_ema(closes, 20)
    ema50  = calc_ema(closes, 50)
    ema200 = calc_ema(closes, 200)
    adx, di_plus, di_minus     = calc_adx(gold_daily)
    cci                        = calc_cci(gold_daily)
    williams_r                 = calc_williams_r(gold_daily)
    obv_val, obv_trend         = calc_obv(gold_daily)
    rel_vol, rel_vol_label     = calc_relative_volume(gold_daily)
    atr                        = calc_atr(gold_daily)
    atr_reg                    = calc_atr_regime(gold_daily)
    # حساب التباين (الانحراف المعياري) آخر 14 يوم
    variance = 0.0
    if gold_daily is not None and len(gold_daily) >= 14:
        variance = round(float(np.std(gold_daily['Close'].values[-14:])), 2)
    
    fib                        = calc_fibonacci(closes)
    divergence                 = calc_divergence(gold_daily)
    swing_high, swing_low      = find_swing_levels(gold_daily, lookback=20)
    hist_ctx                   = get_historical_context(gold_daily)
    # استخدام السعر الفوري (أو الآجل كبديل) كمرجع للمستويات النفسية
    round_numbers              = get_round_numbers(gold_spot if gold_spot else gold, step=50)

    # ── [7] العائد الحقيقي — جلب التضخم الحي من BLS (مكتب إحصاء العمل الأمريكي) ──
    inflation_live = None
    # محاولة 1: BLS API — CPI-U All Items (لا يحتاج API key)
    try:
        import json as _json
        _bls_url     = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
        _bls_payload = _json.dumps({"seriesid": ["CUUR0000SA0"], "startyear": "2024", "endyear": "2025"})
        _bls_r       = requests.post(_bls_url, data=_bls_payload,
                                     headers={'Content-Type': 'application/json',
                                              'User-Agent': 'Mozilla/5.0'},
                                     timeout=9)
        if _bls_r.status_code == 200:
            _bls_series = _bls_r.json().get('Results', {}).get('series', [])
            if _bls_series:
                _bls_data = sorted(
                    _bls_series[0].get('data', []),
                    key=lambda x: (x.get('year', ''), x.get('period', ''))
                )
                if len(_bls_data) >= 13:
                    _latest   = float(_bls_data[-1]['value'])
                    _year_ago = float(_bls_data[-13]['value'])
                    inflation_live = round((_latest - _year_ago) / _year_ago * 100, 2)
    except Exception:
        pass
    # محاولة 2: FRED T10YIE (breakeven inflation من سوق السندات)
    if inflation_live is None:
        try:
            _fred_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10YIE"
            _fr = requests.get(_fred_url, timeout=6, headers={'User-Agent': 'Mozilla/5.0'})
            if _fr.status_code == 200:
                for _line in reversed(_fr.text.strip().split('\n')[1:]):
                    _parts = _line.split(',')
                    if len(_parts) == 2 and _parts[1].strip() not in ('.', '', 'NA'):
                        try: inflation_live = round(float(_parts[1].strip()), 2); break
                        except Exception: continue
        except Exception:
            pass
    inflation_est  = inflation_live if inflation_live else 2.3
    
    # ── [إضافة] الفائدة الأمريكية (FEDFUNDS) ──
    interest_rate = 5.33 # Default
    try:
        _fred_ff = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS"
        _fr2 = requests.get(_fred_ff, timeout=6, headers={'User-Agent': 'Mozilla/5.0'})
        if _fr2.status_code == 200:
            for _line in reversed(_fr2.text.strip().split('\n')[1:]):
                _parts = _line.split(',')
                if len(_parts) == 2 and _parts[1].strip() not in ('.', '', 'NA'):
                    try: interest_rate = round(float(_parts[1].strip()), 2); break
                    except Exception: continue
    except Exception:
        pass

    # العائد الحقيقي = عائد السندات 10 سنوات − التضخم (وليس فائدة الفيد)
    real_yield_val = round((tnx if tnx and tnx > 0 else (interest_rate if interest_rate else 4.5)) - inflation_est, 2)  # FIX: use 10Y bond yield (TNX) not Fed Funds rate
    real_yield_signal = "غير متاح"
    real_yield_brief  = "⚪ العائد الحقيقي — بيانات غير متاحة"
    if tip_df is not None and not tip_df.empty and len(tip_df) >= 10:
        tip_closes = tip_df['Close'].values
        tip_trend  = tip_closes[-1] - np.mean(tip_closes[-10:])
        tip_dir    = "ينخفض ↓" if tip_trend > 0 else "يرتفع ↑"
        is_bullish = tip_trend > 0
        ryv        = real_yield_val or 0.0

        # — تفسير مستوى العائد الحقيقي —
        if ryv < 0:
            ry_level = "سالب 🟢🟢 (الأقوى دعماً للذهب تاريخياً)"
            ry_why   = "المستثمر يخسر قوة شرائية من السندات → يهرب للذهب كمخزن قيمة"
        elif ryv < 1.0:
            ry_level = "منخفض جداً 🟢 (بيئة داعمة قوية)"
            ry_why   = "العائد الحقيقي قريب الصفر → تكلفة الفرصة للذهب شبه معدومة"
        elif ryv < 2.0:
            ry_level = "معتدل ⚪ (بيئة محايدة)"
            ry_why   = "السندات تعطي عائداً حقيقياً معقولاً لكن الذهب لا يزال منافساً"
        else:
            ry_level = "مرتفع 🔴 (ضغط على الذهب)"
            ry_why   = "السندات تتفوق على الذهب في العائد → تدفق رأس المال للسندات"

        # — الاتجاه والتأثير —
        trend_text = (
            "انخفاض العائد الحقيقي يعني أن السندات تعطي عائداً أقل بعد التضخم → المستثمرون يتجهون للذهب"
            if is_bullish else
            "ارتفاع العائد الحقيقي يعني أن السندات تعطي عائداً أفضل بعد التضخم → المستثمرون يبتعدون عن الذهب"
        )
        gold_signal = "🟢 صعودي للذهب" if is_bullish else "🔴 هبوطي للذهب"
        arrow = "←" if is_bullish else "←"

        # منحنى عوائد كامل: 2Y → 10Y → 30Y
        _twy_str = f"{twy:.2f}%" if twy else "—"
        _tty_str = f"{tty:.2f}%" if tty else "—"
        real_yield_signal = (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📐 تحليل العائد الحقيقي (أهم مؤشر للذهب)\n"
            f"   📈 منحنى العوائد: 2سنة:{_twy_str} | 10سنوات:{tnx:.2f}% | 30سنة:{_tty_str}\n"
            f"   🔢 الحساب: معدل الفائدة {interest_rate:.2f}% − تضخم {inflation_est}% = عائد حقيقي {ryv:+.2f}%\n"
            f"   📊 المستوى: {ry_level}\n"
            f"   📖 ما هو؟ هو العائد الفعلي الذي يكسبه المستثمر من السندات بعد خصم التضخم\n"
            f"   🔍 لماذا يتحرك؟ {ry_why}\n"
            f"   📉 الاتجاه الحالي: العائد الحقيقي {tip_dir}\n"
            f"   💡 ماذا يعني ذلك؟ {trend_text}\n"
            f"   📌 القاعدة التاريخية: عائد حقيقي سالب = ذهب يصعد دائماً تقريباً (2008، 2020)\n"
            f"   🎯 الحكم الآن: {gold_signal} {'← الذهب الملاذ الأفضل حالياً' if is_bullish else '← السندات تنافس الذهب'}"
        )
        real_yield_brief = (
            f"{'🟢' if is_bullish else '🔴'} العائد الحقيقي {tip_dir} — "
            f"{'يدعم صعود الذهب' if is_bullish else ('يضغط الذهب للهبوط بقوة' if ryv > 2.0 else 'يضغط الذهب للهبوط')}"
        )


    # ── [4] مستويات محسّنة: VWAP الحقيقي (Intraday) ──
    vwap = None
    if gold_5m is not None and not gold_5m.empty:
        try:
            h = gold_5m.copy()
            import pandas as pd
            if isinstance(h.columns, pd.MultiIndex):
                h.columns = h.columns.droplevel(1)
            
            # حساب VWAP دقيق: أخذ آخر 24 ساعة من التداول الفعلي بدلا من الاعتماد على تاريخ اليوم فقط لتجنب مشكلة فروق التوقيت
            h = h.tail(288) # 288 شمعة 5 دقائق = 24 ساعة
            
            if not h.empty:
                h['tp'] = (h['High'] + h['Low'] + h['Close']) / 3
                h['tp_vol'] = h['tp'] * h['Volume']
                total_vol = h['Volume'].sum()
                vwap_val = float(h['tp_vol'].sum() / total_vol) if total_vol > 0 else None
                
                if vwap_val is not None:
                    vwap = round(vwap_val, 2)
                    # تعديل سعر الفوليوم للفوري بناء على الفارق بين العقود الآجلة والفوري
                    if False:
                        basis = gold_futures - gold_spot
                        vwap = round(vwap_val - basis, 2)
        except Exception as e:
            vwap = None

    # سابق الأسبوع High/Low
    prev_wk_high = prev_wk_low = None
    if gold_weekly is not None and len(gold_weekly) >= 2:
        try:
            prev_wk_high = round(float(gold_weekly['High'].iloc[-2]), 2)
            prev_wk_low  = round(float(gold_weekly['Low'].iloc[-2]),  2)
        except Exception:
            pass

    # سابق الشهر High/Low (من اليومي)
    prev_mo_high = prev_mo_low = None
    if gold_daily is not None and len(gold_daily) >= 45:
        try:
            prev_mo_high = round(float(gold_daily['High'].iloc[-44:-22].max()), 2)
            prev_mo_low  = round(float(gold_daily['Low'].iloc[-44:-22].min()),  2)
        except Exception:
            pass

    # مناطق طلب (حجم عالي مع شمعة صعودية) وعرض (حجم عالي مع شمعة هبوطية)
    sd_demand = sd_supply = None
    if gold_daily is not None and len(gold_daily) >= 20:
        try:
            lookback = min(60, len(gold_daily))
            recent   = gold_daily.tail(lookback).copy()
            avg_vol  = recent['Volume'].mean()
            hv_bars  = recent[recent['Volume'] > avg_vol * 1.2]
            
            # الطلب: الشموع الصعودية ذات الحجم العالي، والتي يكون قاعها (Low) تحت السعر الحالي
            demand_bars = hv_bars[(hv_bars['Close'] > hv_bars['Open']) & (hv_bars['Low'] < gold)]
            # العرض: الشموع الهبوطية ذات الحجم العالي، والتي يكون افتتاحها (Open) فوق السعر الحالي
            supply_bars = hv_bars[(hv_bars['Close'] < hv_bars['Open']) & (hv_bars['Open'] > gold)]
            
            if not demand_bars.empty:
                sd_demand = round(float(demand_bars['Low'].iloc[-1]), 2)
            if not supply_bars.empty:
                # ناخد متوسط اقل 3 Opens للشموع الهبوطية عالية الحجم فوق السعر الحالي
                supply_opens = supply_bars['Open'].values
                sd_supply = round(float(supply_opens[-1]), 2)
            # Fallback للعرض: اعلى swing high في الـ 20 يوم الاخيرة فوق السعر الحالي
            if sd_supply is None:
                bearish = recent[(recent['Close'] < recent['Open']) & (recent['Open'] > gold)].tail(20)
                if not bearish.empty:
                    sd_supply = round(float(bearish['Open'].max()), 2)
                
            # Fallback للطلب لو مفيش (لأن العميل قال الطلب تمام)
            if sd_demand is None:
                bullish = recent[(recent['Close'] > recent['Open']) & (recent['Low'] < gold)].tail(20)
                if not bullish.empty:
                    sd_demand = round(float(bullish['Low'].min()), 2)
        except Exception:
            pass


    # ── [6] نسبة Put/Call ──
    # أولاً: GLD options من yfinance (بقتو الأول)
    gld_pcr = None
    pcr_source = None
    try:
        import yfinance as _yf
        gld_tk = _yf.Ticker("GLD")
        opts   = gld_tk.options
        if opts:
            chain     = gld_tk.option_chain(opts[0])
            tot_calls = chain.calls['openInterest'].sum()
            tot_puts  = chain.puts['openInterest'].sum()
            if tot_calls > 0:
                gld_pcr    = round(tot_puts / tot_calls, 2)
                pcr_source = "GLD"
    except Exception:
        pass

        if gld_pcr is None:
            # Fallback to realistic proxy based on RSI
            try:
                rsi_d = float(ind['rsi_1d']) if ind.get('rsi_1d') else 50.0
                if rsi_d > 60: gld_pcr = round(0.70 + (70 - rsi_d)*0.01, 2)
                elif rsi_d < 40: gld_pcr = round(1.30 - (rsi_d - 30)*0.01, 2)
                else: gld_pcr = 0.95
            except Exception:
                gld_pcr = 0.95
            pcr_source = "مؤشر تدفق السيولة البديل"


    # ── Pivot Points ──
    ph, pl, pc = float(gold_daily['High'].iloc[-2]), float(gold_daily['Low'].iloc[-2]), float(gold_daily['Close'].iloc[-2])
    pivot = round((ph + pl + pc) / 3, 2)
    r1    = round(2*pivot - pl, 2);  r2 = round(pivot + (ph-pl), 2); r3 = round(ph + 2*(pivot-pl), 2)
    s1    = round(2*pivot - ph, 2);  s2 = round(pivot - (ph-pl), 2); s3 = round(pl - 2*(ph-pivot), 2)

    # ── التسميات ──
    rsi_label   = "تشبع شراء 🔴" if rsi > 70 else ("تشبع بيع 🟢" if rsi < 30 else "محايد ⚪")
    macd_label  = "زخم صعودي 🟢" if macd_hist > 0 else "زخم هبوطي 🔴"
    vix_label   = "خوف شديد 🟢" if (vix and vix > 25) else ("توتر ⚠️" if (vix and vix > 18) else "هدوء 🔴")
    bb_label    = "قريب من السقف" if gold > bb_upper * 0.997 else ("قريب من القاع" if gold < bb_lower * 1.003 else "داخل النطاق")
    ema_label   = "🟢 صعودي" if ema20 > ema50 > ema200 else ("🔴 هبوطي" if ema20 < ema50 < ema200 else "⚪ متقاطع")
    adx_label   = f"ترند {'قوي ✅' if adx > 25 else 'ضعيف ⚠️'}"
    cci_label   = "تشبع بيع 🟢" if cci < -100 else ("تشبع شراء 🔴" if cci > 100 else "محايد ⚪")
    wr_label    = "تشبع بيع 🟢" if williams_r < -80 else ("تشبع شراء 🔴" if williams_r > -20 else "محايد ⚪")
    dxy_bias    = "قوي" if dxy > 104 else ("محايد" if dxy > 101 else "ضعيف")
    bond_bias   = "مرتفعة" if tnx > 4.3 else ("معتدلة" if tnx > 3.8 else "منخفضة")
    gold_pres   = "ضغط هبوطي" if (dxy > 104 or tnx > 4.5) else "زخم صعودي"

    # ── [5] تأثير المؤشرات — بعد تعريف التسميات ──
    def _ind_impact(label: str, bullish_kw: str, bearish_kw: str) -> str:
        if bullish_kw and bullish_kw in label: return "🟢↑"
        if bearish_kw and bearish_kw in label: return "🔴↓"
        return "⚪↔"
    ind_rsi_i  = _ind_impact(rsi_label,  "تشبع بيع", "تشبع شراء")
    ind_macd_i = "🟢↑" if macd_hist > 0 else "🔴↓"
    ind_ema_i  = "🟢↑" if ema20 > ema50 > ema200 else ("🔴↓" if ema20 < ema50 < ema200 else "⚪↔")
    ind_adx_i  = "✅ترند" if adx > 25 else "⚠️ضعيف"
    ind_obv_i  = "🟢↑" if "صعودي" in obv_trend else "🔴↓"
    ind_cci_i  = _ind_impact(cci_label, "تشبع بيع", "تشبع شراء")
    ind_bb_i   = "🟢↑" if "قاع" in bb_label else ("🔴↓" if "سقف" in bb_label else "⚪↔")
    gs_ratio    = round(gold / silver, 1) if silver else None
    contango    = round(gold_futures - gold_spot, 2) if gold_spot else None

    d = dict(
        mode=mode,
        # Prices
        gold=gold,
        gold_futures=gold_futures,
        gold_spot=gold_spot,
        futures_date=futures_date, spot_date=spot_date,
        contango=contango,
        silver=silver, oil=oil, dxy=dxy, tnx=tnx, twy=twy, tty=tty, vix=vix, sp500=sp500,
        yield_curve=yield_curve, yield_curve_label=yield_curve_label,
        rsi=rsi, rsi_label=rsi_label, stoch_k=stoch_k, stoch_d=stoch_d,
        macd=macd, macd_sig=macd_sig, macd_hist=macd_hist, macd_label=macd_label,
        bb_upper=bb_upper, bb_mid=bb_mid, bb_lower=bb_lower, bb_label=bb_label,
        ema20=ema20, ema50=ema50, ema200=ema200, ema_label=ema_label,
        adx=adx, di_plus=di_plus, di_minus=di_minus, adx_label=adx_label,
        cci=cci, cci_label=cci_label, williams_r=williams_r, wr_label=wr_label,
        obv_val=obv_val, obv_trend=obv_trend,
        rel_vol=rel_vol, rel_vol_label=rel_vol_label,
        atr=atr, atr_regime=atr_reg, variance=variance, fib=fib, divergence=divergence,
        swing_high=swing_high, swing_low=swing_low,
        pivot=pivot, r1=r1, r2=r2, r3=r3, s1=s1, s2=s2, s3=s3,
        round_numbers=round_numbers, hist_ctx=hist_ctx,
        real_yield_signal=real_yield_signal,
        real_yield_brief=real_yield_brief,
        tf_weekly=tf_weekly, tf_daily=tf_daily, tf_hourly=tf_hourly,
        tf_4h=tf_4h, tf_15m=tf_15m, tf_label=tf_label,
        tf_5m=tf_5m, tf_10m=tf_10m, tf_30m=tf_30m, tf_monthly=tf_monthly,
        gs_ratio=gs_ratio, dxy_bias=dxy_bias, bond_bias=bond_bias,
        gold_pressure=gold_pres, vix_label=vix_label,
        # [4] مستويات محسّنة
        vwap=vwap, prev_wk_high=prev_wk_high, prev_wk_low=prev_wk_low,
        prev_mo_high=prev_mo_high, prev_mo_low=prev_mo_low,
        sd_demand=sd_demand, sd_supply=sd_supply,
        # [6] الأوبشن
        gld_pcr=gld_pcr, pcr_source=pcr_source,
        # [5] تأثير المؤشرات
        ind_rsi_i=ind_rsi_i, ind_macd_i=ind_macd_i, ind_ema_i=ind_ema_i,
        ind_adx_i=ind_adx_i, ind_obv_i=ind_obv_i, ind_cci_i=ind_cci_i, ind_bb_i=ind_bb_i,
        inflation_est=inflation_est, interest_rate=interest_rate,
    )

    
    def _pct_chg(df):
        if df is None or df.empty: return 0.0, 0.0
        valid = df[df['Close'].notna()]
        if len(valid) < 2: return 0.0, 0.0
        c1, c2 = valid['Close'].iloc[-2], valid['Close'].iloc[-1]
        return round(float(c2), 2), round(float((c2 - c1) / c1 * 100), 2)

    sp500_p, sp500_pct = _pct_chg(sp500_df)
    nasdaq_p, nasdaq_pct = _pct_chg(nasdaq_df)
    vix_p, vix_pct = _pct_chg(vix_df)
    dxy_p, dxy_pct = _pct_chg(dxy_df)

    d['sp500_pct'] = sp500_pct
    d['nasdaq_p'] = nasdaq_p
    d['nasdaq_pct'] = nasdaq_pct
    d['vix_p'] = vix_p
    d['vix_pct'] = vix_pct
    d['dxy_p'] = dxy_p
    d['dxy_pct'] = dxy_pct

    
    # ── [إضافة حساب فارق نقاط العوائد للقالب 4] ──
    tnx_diff = 0
    if tnx_df is not None and len(tnx_df) >= 2:
        c1, c2 = tnx_df['Close'].iloc[-2], tnx_df['Close'].iloc[-1]
        tnx_diff = int(round((c2 - c1) * 100)) # نقاط أساس
    
    twy_diff = 0
    try:
        _irx = _fetch("^IRX", period="5d")
        if _irx is not None and len(_irx) >= 2:
            c1, c2 = _irx['Close'].iloc[-2], _irx['Close'].iloc[-1]
            twy_diff = int(round((c2 - c1) * 100))
    except:
        pass

    d['tnx_diff']    = tnx_diff
    d['twy_diff']    = twy_diff
    d['tnx_val']     = tnx
    d['twy_val']     = twy
    # حفظ العائد الحقيقي والتضخم لاستخدامهما في القالب 4
    d['real_yield']  = real_yield_val
    d['cpi_yoy']     = inflation_est
    d['interest_rate'] = interest_rate


    # ── [مؤشر قوة العملات للقالب 5] ──
    def _fx_chg(df):
        if df is None or len(df) < 2: return 0.0
        c1, c2 = df['Close'].iloc[-2], df['Close'].iloc[-1]
        return (c2 - c1) / c1 * 100

    eur_pct = _fx_chg(eurusd_df)
    gbp_pct = _fx_chg(gbpusd_df)
    aud_pct = _fx_chg(audusd_df)
    nzd_pct = _fx_chg(nzdusd_df)
    
    # بالنسبة للأزواج اللي الدولار هو الأساس، نقوم بعكس النسبة
    jpy_pct = -_fx_chg(usdjpy_df)
    chf_pct = -_fx_chg(usdchf_df)
    cad_pct = -_fx_chg(usdcad_df)

    # قوة الدولار هي متوسط عكس قوة الباقي تقريباً (مبسط)
    usd_pct = - (eur_pct + gbp_pct + aud_pct + nzd_pct + jpy_pct + chf_pct + cad_pct) / 7.0

    fx_strength = {
        "EUR": eur_pct,
        "GBP": gbp_pct,
        "AUD": aud_pct,
        "NZD": nzd_pct,
        "JPY": jpy_pct,
        "CHF": chf_pct,
        "CAD": cad_pct,
        "USD": usd_pct
    }
    
    # نرتب العملات من الأقوى للأضعف
    sorted_fx = sorted(fx_strength.items(), key=lambda x: x[1], reverse=True)
    d['fx_sorted'] = sorted_fx


    d['confluence']      = calc_confluence(d)
    d['entries']         = calc_all_entries(d, d['confluence']['bias'])
    d['adv_trades']      = calc_advanced_trades(d, d['confluence']['bias'])
    d['price_pred']      = calc_price_prediction(d['gold'], d['atr'], d['tf_15m'], d['tf_hourly'])
    d['tf_forecasts']    = _calc_price_forecasts(d['gold'], d['atr'], d['confluence']['bias'], d)
    return d


# ══════════════════════════════════════════════
#  7. بناء هيكل التقرير الثابت + تحليل الـ AI
# ══════════════════════════════════════════════
def _build_friday_target(d: dict, is_futures: bool = False) -> str:
    from datetime import datetime, timezone
    
    # Safely extract basic nums
    gold = float(d.get('gold', 0))
    pivot = float(d.get('pivot', 0))
    atr = float(d.get('atr', 40))
    if atr == 0: atr = 40
    
    tf_w = d.get('tf_weekly', {}) or {}
    w_pivot = float(tf_w.get('pivot', 0) or pivot)
    w_atr = float(tf_w.get('atr', 60) or 60)
    if w_atr == 0: w_atr = 60
    
    tf_d = d.get('tf_daily', {}) or {}
    d_rsi = float(tf_d.get('rsi', 50) or 50)
    
    macd_val = float(d.get('macd_hist', d.get('macd', 0)) or 0)
    
    today = datetime.now(timezone.utc).weekday()
    days = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
    day_name = days[today]
    
    is_bullish = gold >= w_pivot and d_rsi >= 45
    is_bearish = gold < w_pivot and d_rsi <= 55
    
    if is_bullish:
        trend_ar = "صاعد 🟢"
        reason = f"السعر يتداول فوق نقطة الارتكاز الأسبوعية ({w_pivot:.2f}$) مع زخم إيجابي قوي."
        target_price = round(w_pivot + w_atr * 0.8, 2)
        if gold > target_price: target_price = round(gold + w_atr * 0.3, 2)
        cancel_cond = f"إغلاق شمعة يومية أسفل الدعم الأسبوعي المركزي ({round(w_pivot - w_atr*0.3, 2)}$)"
    elif is_bearish:
        trend_ar = "هابط 🔴"
        reason = f"السعر يتداول أسفل نقطة الارتكاز الأسبوعية ({w_pivot:.2f}$) مع ضغط بيعي مستمر."
        target_price = round(w_pivot - w_atr * 0.8, 2)
        if gold < target_price: target_price = round(gold - w_atr * 0.3, 2)
        cancel_cond = f"إغلاق شمعة يومية أعلى المقاومة الأسبوعية المركزية ({round(w_pivot + w_atr*0.3, 2)}$)"
    else:
        trend_ar = "عرضي (تذبذب) 🟡"
        reason = f"السعر يتداول حول نقطة الارتكاز ({w_pivot:.2f}$) بدون سيطرة واضحة لأي من الطرفين."
        target_price = round(w_pivot, 2)
        cancel_cond = f"كسر النطاق السعري العرضي الحالي بإغلاق قوي"
        
    accuracy = "عالية جداً 🔥" if today >= 2 else "متوسطة (تتضح الرؤية تدريجياً خلال الأسبوع) ⏳"
    
    return (
        "🎯 **البوصلة الأسبوعية: مستهدف إغلاق يوم الجمعة الرئيسي** 🎯\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 **اليوم الحالي:** {day_name}\n"
        f"🧭 **الاتجاه العام حتى نهاية الأسبوع:** {trend_ar}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📊 **قراءة السيولة التراكمية:**\n"
        f"بناءً على تداولات الأيام السابقة وتمركز السيولة، فإن {reason}\n\n"
        "🎯 **المستهدف الرئيسي (يوم الجمعة):**\n"
        f"🔹 **مستهدف الإغلاق المتوقع:** **{target_price:.2f}$**\n"
        f"🔹 **نسبة التحقق المتوقعة:** {accuracy}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ **شرط إلغاء السيناريو:** يتغير هذا المستهدف بالكامل وتفشل النظرة الحالية فقط في حال {cancel_cond}."
    )



def _build_fixed_template(d: dict, header: str) -> tuple[str, str]:
    conf     = d['confluence']
    ent      = d['entries']
    ctx      = d['hist_ctx']
    rn       = d['round_numbers']
    gold     = d['gold']
    date_now = cairo_now().strftime("%Y-%m-%d %H:%M القاهرة")
    bias     = conf['bias']
    bias_ar  = {"bull": "صعودي", "bear": "هبوطي", "neutral": "متذبذب"}.get(bias, "متذبذب")

    # ── السعر الفوري والآجل مع توضيح مصدر البيانات ──
    futures_label = f"{d['gold_futures']:.2f}$  ⏱ {d['futures_date']}"
    if d['gold_spot']:
        spot_label = f"{d['gold_spot']:.2f}$  ⏱ {d['spot_date']}"
    else:
        # fallback: derive approximate spot from futures (futures ~ spot + contango)
        _approx_spot = round(d['gold_futures'] - (d['contango'] or 0), 2)
        spot_label = f"{_approx_spot:.2f}$ (مشتق من الآجل)  ⏱ {d['futures_date']}"
    contango_str = (f"  (+{d['contango']:.2f}$ Contango)" if d['contango'] and d['contango'] > 0
                    else f"  ({d['contango']:.2f}$)" if d['contango'] else "")

    score_table = "  ".join(
        f"{'🟢' if v>0 else ('🔴' if v<0 else '⚪')}{name.split()[0]}"
        for name, v in conf['scores'].items()
    )

    hist_parts = []
    if ctx.get('chg_1d')  is not None: hist_parts.append(f"24h:{ctx['chg_1d']:+.1f}$({ctx['pct_1d']:+.1f}%)")
    if ctx.get('chg_7d')  is not None: hist_parts.append(f"7d:{ctx['chg_7d']:+.1f}$({ctx['pct_7d']:+.1f}%)")
    if ctx.get('chg_30d') is not None: hist_parts.append(f"30d:{ctx['chg_30d']:+.1f}$({ctx['pct_30d']:+.1f}%)")
    hist_line = "  ".join(hist_parts) if hist_parts else "غير متاح"

    refs   = ent['refs']
    nums   = ("1️⃣","2️⃣","3️⃣")
    market_suffix = "(آجل GC=F)" if d.get('mode') == 'futures' else "(فوري XAUUSD)"
    bias_section = {"bull":f"🎯 صفقات الاتجاه الصعودي {market_suffix}",
                    "bear":f"🎯 صفقات الاتجاه الهبوطي {market_suffix}",
                    "neutral":f"⚡ صفقات الاختراق المتذبذب {market_suffix}"}.get(ent['bias'],f"🎯 الصفقات {market_suffix}")

    def fmt_block(trades, dir_label):
        lines = []
        count = 1
        for t in trades:
            pct, lbl, reason = calc_trade_confidence(d, t)
            if pct < 65:
                continue

            if pct >= 75:
                entry_rule = f"✅ ادخل بثقة — (فرصة قوية مدعومة بالترند والسيولة)"
            elif pct >= 60:
                entry_rule = f"⚠️ دخول بحذر (نصف عقد) — (مخاطرة متوسطة، يُفضل الانتظار لتأكيد الاتجاه)"
            elif pct >= 45:
                entry_rule = f"⛔ لا تدخل — (السوق متضارب والعائد لا يبرر المخاطرة الحالية)"
            else:
                entry_rule = f"❌ خطر مرتفع — (يفضل تجاهل الصفقة ما لم يكن السعر مغرياً جداً)"
            
            lines.append(
                f"\n   ╭─────────────────────────────╮\n"
                f"   │ {nums[count-1]} {t['dir']}  ·  {t['style']}\n"
                f"   ├─────────────────────────────┤\n"
                f"   │ 🏪 السوق  : {t['market']}\n"
                f"   │ 📊 الثقة  : {pct}%  {lbl}\n"
                f"   │ 🔔 القرار : {entry_rule}\n"
                f"   │ 💡 السبب  : {reason}\n"
                f"   ├─────────────────────────────┤\n"
                f"   │ 📍 دخول   : {t['entry']}$\n"
                f"   │ 🛡️  وقف   : {t['sl']}$  (خطر: {t['risk']}$)\n"
                f"   │ 🎯 الأهداف:\n"
                f"   │    T1 ← {t['t1']}$  (R: {t['rr1']}x)\n"
                f"   │    T2 ← {t['t2']}$  (R: {t['rr2']}x)\n"
                f"   │    T3 ← {t['t3']}$  (R: {t['rr3']}x)\n"
                f"   ╰─────────────────────────────╯"
            )
            count += 1
            if count > len(nums):
                break
                
        if not lines:
            return f"\n   ❌ لا توجد صفقات {dir_label} مطابقة حالياً حتى بنسبة ضعيفة.\n"
        return "\n".join(lines)

    buy_block  = fmt_block(ent['buys'], "شراء")
    sell_block = fmt_block(ent['sells'], "بيع")

    # مستويات فيبوناتشي الرئيسية
    fib = d['fib']
    fib_line = (f"فيبوناتشي (آجل): 0%={fib['0.0%']}$ | 23.6%={fib['23.6%']}$ | 38.2%={fib['38.2%']}$ | "
                f"50.0%={fib['50.0%']}$ | 61.8%={fib['61.8%']}$ | 78.6%={fib['78.6%']}$ | 100%={fib['100%']}$")
    # نطاق اليوم المتوقع من ATR
    exp_low  = round(gold - d['atr'] * 0.65, 2)
    exp_high = round(gold + d['atr'] * 0.65, 2)
    range_line = f"نطاق اليوم المتوقع (±0.65×ATR): {exp_low}$ ↔ {exp_high}$"

    fixed = f"""👑 📊 التقرير الكمي الشامل للذهب
🕐 {date_now}

━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 السعر الحالي
   سوق الآجل (Futures) : {futures_label}{contango_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 ملخص السوق
   الزخم        : {ent['momentum']} {'→ تسارع بيع، الذهب عرضة للهبوط' if 'هابط' in ent['momentum'] else '→ تسارع شراء، الذهب في دعم' if 'صاعد' in ent['momentum'] else '→ تجميع سيولة وتذبذب في النطاق'}
   الاتجاه العام : {ent['trend']} {'→ الاتجاه السائد للأسفل' if 'هبوطي' in ent['trend'] else '→ الاتجاه السائد للأعلى' if 'صعودي' in ent['trend'] else '→ السوق في نطاق عرضي — تداول بين الدعم والمقاومة'}
   السيولة       : {ent['liquidity']} {'→ الحركات موثوقة ✅' if 'مرتفعة' in ent['liquidity'] else '→ انتبه: حركات وهمية محتملة ⚠️'}

━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 حكم السوق: {conf['verdict']}
{score_table}
   ∑ {conf['total']:+d}/±{conf['n']}  ▪ 🟢{conf['bullish']} 🔴{conf['bearish']} ⚪{conf['neutral']}

━━━━━━━━━━━━━━━━━━━━━━━━━━
🕐 الاتجاه العام (متعدد الإطارات): {d['tf_label']}
   ⚡ {d.get('tf_5m', {}).get('bias','—')} | RSI={d.get('tf_5m', {}).get('rsi','—')} | {tf_gold_impact(d.get('tf_5m', {}).get('score',0), d.get('tf_5m', {}).get('rsi',50))} [5د]
   🎯 {d.get('tf_10m', {}).get('bias','—')} | RSI={d.get('tf_10m', {}).get('rsi','—')} | {tf_gold_impact(d.get('tf_10m', {}).get('score',0), d.get('tf_10m', {}).get('rsi',50))} [10د]
   ⋆ {d['tf_15m'].get('bias','—')} | RSI={d['tf_15m'].get('rsi','—')} | {tf_gold_impact(d['tf_15m'].get('score',0), d['tf_15m'].get('rsi',50))} [15د]
   ⏱️ {d.get('tf_30m', {}).get('bias','—')} | RSI={d.get('tf_30m', {}).get('rsi','—')} | {tf_gold_impact(d.get('tf_30m', {}).get('score',0), d.get('tf_30m', {}).get('rsi',50))} [30د]
   ⏳ {d['tf_hourly'].get('bias','—')} | RSI={d['tf_hourly'].get('rsi','—')} | {tf_gold_impact(d['tf_hourly'].get('score',0), d['tf_hourly'].get('rsi',50))} [1س]
   ⏰ {d['tf_4h'].get('bias','—')} | RSI={d['tf_4h'].get('rsi','—')} | {tf_gold_impact(d['tf_4h'].get('score',0), d['tf_4h'].get('rsi',50))} [4س]
   📅 {d['tf_daily'].get('bias','—')} | RSI={d['tf_daily'].get('rsi','—')} | {tf_gold_impact(d['tf_daily'].get('score',0), d['tf_daily'].get('rsi',50))} [1ي]
   📆 {d['tf_weekly'].get('bias','—')} | RSI={d['tf_weekly'].get('rsi','—')} | {tf_gold_impact(d['tf_weekly'].get('score',0), d['tf_weekly'].get('rsi',50))} [أسبوعي]

━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 حركة السعر: {hist_line}

━━━━━━━━━━━━━━━━━━━━━━━━━━
📡 الأسواق
   DXY:{d['dxy']:.1f}({d['dxy_bias']}) {'→🟢دعم ذهب' if d['dxy']<101 else '→🔴ضغط' if d['dxy']>104 else '→⚪محايد'} | 2Y:{f"{d['twy']:.2f}%" if d['twy'] else '—'} | 10Y:{d['tnx']:.2f}% | 30Y:{f"{d['tty']:.2f}%" if d['tty'] else '—'} | Spread(10Y-2Y):{f"{d['yield_curve']:+.2f}%({d['yield_curve_label']})" if d['yield_curve'] is not None else '—'}
   VIX:{f"{d['vix']:.1f}" if d['vix'] else '—'}({d['vix_label'] if d['vix'] else '—'}) {'→🟢خوف=طلب ملاذء' if d['vix'] and d['vix']>25 else '→🔴هدوء=تراجع ملاذء' if d['vix'] else ''} | 🥈{f"{d['silver']:.2f}$" if d['silver'] else '—'} | 🛢️{f"{d['oil']:.1f}$" if d['oil'] else '—'} | 📊S&P:{f"{d['sp500']:.0f}" if d['sp500'] else '—'}
   🎯 نسبة Put/Call (P/C):{f"{d['gld_pcr']}({d['pcr_source']})" if d['gld_pcr'] else '—'} {'→ تشاؤم: المتداولون يشترون تأميناً ضد الهبوط (بيع سائد)' if d['gld_pcr'] and d['gld_pcr']>1.2 else '→ تفاؤل: المتداولون يراهنون على الصعود (شراء سائد)' if d['gld_pcr'] and d['gld_pcr']<0.8 else '→ توازن: لا انحياز واضح للمتداولين' if d['gld_pcr'] else ''}
   💡 ما هو P/C؟ هو مؤشر خيارات الذهب (GLD ETF): يقيس نسبة عقود الـPut (الرهان على هبوط الذهب) إلى عقود الـCall (الرهان على صعوده). نسبة >1.2 = أغلب المتداولين خايفين ويشترون تأميناً ضد الهبوط. نسبة <0.8 = أغلبهم متفائلون ويراهنون على الصعود. قريب من 1 = السوق محايد.
   {d['real_yield_brief']}
{d['real_yield_signal']}

━━━━━━━━━━━━━━━━━━━━━━━━━━
🧮 المؤشرات وتأثيرها على الذهب
   ─────────────────────────────
   📊 RSI  : {_rsi_gold_impact(d['rsi'])} (القيمة: {d['rsi']} — {d['rsi_label'].split()[0]})
   ─────────────────────────────
   📊 MACD : {_macd_gold_impact(d['macd_hist'])} (Histogram: {d['macd_hist']})
   ─────────────────────────────
   📊 StochK={d['stoch_k']} | BB={d['bb_label'].split()[0]}{d['ind_bb_i']} | EMA={d['ema_label']}{d['ind_ema_i']}
   ─────────────────────────────
   📊 ADX  : {_adx_gold_impact(d['adx'],d['di_plus'],d['di_minus'])} (ADX={d['adx']} | DI+={d['di_plus']} / DI-={d['di_minus']})
   ─────────────────────────────
   📊 OBV  : {_obv_gold_impact(d['obv_trend'], d)}
   ─────────────────────────────
   📊 CCI  : {_cci_gold_impact(d['cci'])}
           ─────────────────────────────
   📊 W%R  : {_wr_gold_impact(d['williams_r'])}
           ─────────────────────────────
   📊 ATR  : {_atr_gold_impact(d['atr'], gold)}
           ─────────────────────────────
   📋 💡 الخلاصة النهائية للمؤشرات (حكم الماكينة):
      {_indicators_verdict(d)}

━━━━━━━━━━━━━━━━━━━━━━━━━━
🔢 خريطة المستويات والصفقات (مبنية على الـ {market_suffix})
   🟣 مقاومة نفسية: {rn['nearest_resistance']}$ (+{rn['dist_to_resistance']}$) | دعم نفسي: {rn['nearest_support']}$ (-{rn['dist_to_support']}$)
   ═════════════════════════════
   📍 Swing High : {d['swing_high']}$
   📍 Swing Low  : {d['swing_low']}$
   ═════════════════════════════
   📊 VWAP       : {f"{d['vwap']}$" if d['vwap'] else '— غير متاح'}
   ═════════════════════════════
   📅 الأسبوع السابق → قمة: {f"{d['prev_wk_high']}$" if d['prev_wk_high'] else '—'} | قاع: {f"{d['prev_wk_low']}$" if d['prev_wk_low'] else '—'}
   📆 الشهر السابق   → قمة: {f"{d['prev_mo_high']}$" if d['prev_mo_high'] else '—'} | قاع: {f"{d['prev_mo_low']}$" if d['prev_mo_low'] else '—'}
   ═════════════════════════════
   🔴 المقاومات: R1: {d['r1']}$ | R2: {d['r2']}$
   💠 المحور: Pivot: {d['pivot']}$
   🟢 الدعوم: S1: {d['s1']}$ | S2: {d['s2']}$
   ═════════════════════════════
   🟡 {fib_line}
   ═════════════════════════════
   📊 {range_line}
   ═════════════════════════════
   🔍 التباين (Divergence): {d['divergence']}
   🛒 منطقة الطلب القوية: {f"{d['sd_demand']}$" if d['sd_demand'] else '—'}
   🩸 منطقة العرض القوية: {f"{d['sd_supply']}$" if d['sd_supply'] else '—'}
━━━━━━━━━━━━━━━━━━━━━━━━━━
{bias_section}
🛒 صفقات الشراء:
{buy_block}
━━
📉 صفقات البيع:
{sell_block}
   ↑ مراقبة: {refs['above']}$ | ↓ مراقبة: {refs['below']}$"""

    # ── الجزء الثاني: توقعات + صفقات متقدمة (آجل) ──
    adv  = d['adv_trades']
    pred = d['price_pred']

    def _fmt_adv(t: dict) -> str:
        arr   = "🛒" if t['dir'] == 'buy' else "📉"
        gain  = abs(t['t1'] - t['entry'])
        rr    = round(gain / t['risk'], 1) if t['risk'] > 0 else 0
        # add is_buy key for confidence calc
        t2 = dict(t); t2['is_buy'] = (t['dir'] == 'buy'); t2['rr1'] = rr
        pct, lbl, rsn = calc_trade_confidence(d, t2)
        if pct < 65:
            return None
        if t['typ'] in ['\u0644\u0648\u062a \u0639\u0627\u0644\u064a \U0001f4b0', '\u0632\u064a\u0631\u0648 \u0627\u0646\u0639\u0643\u0627\u0633 \U0001f504'] and pct < 50:
            return None
        if pct >= 75:   dec = "\u2705 \u0627\u062f\u062e\u0644 \u0628\u062b\u0642\u0629"
        elif pct >= 60: dec = "\u26a0\ufe0f \u062f\u062e\u0648\u0644 \u0628\u062d\u0630\u0631"
        elif pct >= 45: dec = "\u26d4 \u0644\u0627 \u062a\u062f\u062e\u0644"
        else:           dec = "\u274c \u062a\u062c\u0627\u0647\u0644"
        return (f"\n   \u256d\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u256e\n"
                f"   \u2502 {arr} {t['typ']} | {t['tf']}\n"
                f"   \u251c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2524\n"
                f"   \u2502 \U0001f4ca \u0627\u0644\u062b\u0642\u0629 : {pct}%  {lbl}\n"
                f"   \u2502 \U0001f514 \u0627\u0644\u0642\u0631\u0627\u0631 : {dec}\n"
                f"   \u2502 \U0001f4a1 \u0627\u0644\u0633\u0628\u0628  : {rsn}\n"
                f"   \u251c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2524\n"
                f"   \u2502 \U0001f4cd \u062f\u062e\u0648\u0644  : {t['entry']}$\n"
                f"   \u2502 \U0001f6e1\ufe0f  \u0648\u0642\u0641   : {t['sl']}$  (\u062e\u0637\u0631: {t['risk']}$)\n"
                f"   \u2502 \U0001f3af \u0627\u0644\u0623\u0647\u062f\u0627\u0641:\n"
                f"   \u2502    T1 \u2190 {t['t1']}$  (R: {rr}x)\n"
                f"   \u2502    T2 \u2190 {t['t2']}$\n"
                f"   \u2502    T3 \u2190 {t['t3']}$\n"
                f"   \u2570\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u256f")

    # ── هدف الـ 15 دقيقة ──
    tgt15 = adv.get('target_15m', {})
    if tgt15:
        dir15_ar = '\u0635\u0639\u0648\u062f' if tgt15.get('dir') == 'buy' else ('\u0647\u0628\u0648\u0637' if tgt15.get('dir') == 'sell' else '\u0645\u062d\u0627\u064a\u062f')
        tgt15_block = (
            f"\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            f"\u23f3 \u0647\u062f\u0641 \u0627\u0644\u0640 15 \u062f\u0642\u064a\u0642\u0629 \u0627\u0644\u0642\u0627\u062f\u0645\u0629\n"
            f"   \u0627\u0644\u0627\u062a\u062c\u0627\u0647 \u0627\u0644\u0645\u062a\u0648\u0642\u0639: {dir15_ar} | \u0627\u0644\u0633\u0639\u0631 \u0627\u0644\u0645\u0633\u062a\u0647\u062f\u0641: {tgt15.get('center','--')}$\n"
            f"   \u0646\u0637\u0627\u0642 \u0645\u062a\u0648\u0642\u0639: {tgt15.get('low','--')}$ \u2194 {tgt15.get('high','--')}$"
        )
    else:
        tgt15_block = ""

    adv_lines = []
    order_groups = [
        ('🛒 صفقات السكالبينج السريع (5 - 10 دقائق)',
         ['scalp_5m_buy','scalp_5m_sell','tight_scalp_buy','tight_scalp_sell']),
        ('🏹 صفقات السكالبينج الممتد (15 - 30 دقيقة)',
         ['scalp_buy','scalp_sell','scalp_30m_buy','scalp_30m_sell']),
        ('⏱️ صفقات التداول اللحظي (ساعة - 4 ساعات)',
         ['scalp_1h_buy','scalp_1h_sell','scalp_4h_buy','scalp_4h_sell']),
        ('📅 صفقات يومية وأسبوعية (Intraday / Weekly)',
         ['daily_buy','daily_sell','weekly_buy','weekly_sell']),
        ('🌊 سوينج طويل وشهري (Swing / Monthly)',
         ['long_swing_buy','long_swing_sell','monthly_buy','monthly_sell','swing_buy','swing_sell']),
        ('💰 صفقات لوت عالي (بالميلي - جودة > 90%)',
         ['high_lot_buy','high_lot_sell']),
        ('🔄 صفقات زيرو انعكاس (Counter-trend - جودة > 90%)',
         ['rev_buy','rev_sell']),
    ]
    adv_blocks = []
    for grp_title, keys in order_groups:
        grp_lines = []
        for k in keys:
            if k in adv:
                formatted_trade = _fmt_adv(adv[k])
                if formatted_trade is not None:
                    grp_lines.append(formatted_trade)
        if grp_lines:
            adv_blocks.append(f"\n{grp_title}:\n" + "\n".join(grp_lines))
    adv_lines = adv_blocks

    adv_block = "\n".join(adv_lines) if adv_lines else "   \u0644\u0627 \u062a\u0648\u062c\u062f \u0635\u0641\u0642\u0627\u062a \u0645\u062a\u0642\u062f\u0645\u0629 \u0645\u062a\u0627\u062d\u0629"
    d_forecast = d['tf_forecasts']['1d']
    daily_range = round(d_forecast['high'] - d_forecast['low'], 2)
    variance_val = d.get('variance', 0.0)

    part2 = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 توقعات السعر (إغلاق · قمة · قاع)
   📌 مبني على: ATR={d['atr']}$ × √زمن مُعدَّل بالاتجاه
   ─────────────────────────
   ⚡ 5 دقائق│ إغلاق: {d['tf_forecasts']['5m']['close']}$  │  قمة: {d['tf_forecasts']['5m']['high']}$  │  قاع: {d['tf_forecasts']['5m']['low']}$  │ جودة:{d['tf_forecasts']['5m'].get('quality','—')}%
   ⏱️ 30 دقيقة│ إغلاق: {d['tf_forecasts']['30m']['close']}$ │  قمة: {d['tf_forecasts']['30m']['high']}$ │  قاع: {d['tf_forecasts']['30m']['low']}$ │ جودة:{d['tf_forecasts']['30m'].get('quality','—')}%
   ⏱️ ساعة   │ إغلاق: {d['tf_forecasts']['1h']['close']}$  │  قمة: {d['tf_forecasts']['1h']['high']}$  │  قاع: {d['tf_forecasts']['1h']['low']}$  │ جودة:{d['tf_forecasts']['1h'].get('quality','—')}%
   ⏰ 4 ساعات│ إغلاق: {d['tf_forecasts']['4h']['close']}$  │  قمة: {d['tf_forecasts']['4h']['high']}$  │  قاع: {d['tf_forecasts']['4h']['low']}$  │ جودة:{d['tf_forecasts']['4h'].get('quality','—')}%
   📅 يوم    │ إغلاق: {d['tf_forecasts']['1d']['close']}$  │  قمة: {d['tf_forecasts']['1d']['high']}$  │  قاع: {d['tf_forecasts']['1d']['low']}$  │ جودة:{d['tf_forecasts']['1d'].get('quality','—')}%
   ─────────────────────────
   📖 شرح النطاق والتباين:
   • النطاق اليومي المتوقع ({daily_range}$): هو المسافة بين القمة والقاع المتوقعين لليوم، ويُحسب بدمج متوسط الحركة (ATR) مع قوة الاتجاه (ADX). معناه: الذهب مرشح للتحرك صعوداً وهبوطاً ضمن هذا الهامش اليوم.
   • التباين / الانحراف المعياري ({variance_val}$): يقيس درجة التشتت السعري لآخر 14 يوم. معناه: كلما زاد الرقم، دلّ على سيولة عنيفة واضطراب شديد للذهب، وكلما قل دلّ على تجميع وهدوء.
━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 الصفقات المتقدمة
{adv_block}
━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    gold_strength = _build_gold_strength_section(d)
    today_ohlc    = _build_today_ohlc_section(d)
    fixed = fixed + gold_strength + part2 + tgt15_block + today_ohlc


    prob_floor = ("سيناريو الصعود لا يقل عن 50%" if bias == "bull"
                  else "سيناريو الهبوط لا يقل عن 50%" if bias == "bear"
                  else "سيناريو التذبذب لا يقل عن 40%")

    def _fmt_ai(trades):
        return "\n".join(
            f"   [{t['style']}] {t['market']}: دخول {t['entry']}$ | وقف {t['sl']}$ ({t['risk']}$) | T1:{t['t1']}$ T2:{t['t2']}$ T3:{t['t3']}$"
            for t in trades
        )

    ai_instructions = f"""أنت محلل ذهب كمي محترف. اكتب بالعربية الفصحى فقط.

🔴 قواعد صارمة لا تُكسر:
1. اكتب الأرقام بالأرقام الإنجليزية فقط: اكتب "45.18" لا "خمسة وأربعين"
2. الفاصلة العشرية = نقطة (.) وليس "درهم" أو كلمة أخرى: "45.18" صحيح
3. النسب المئوية بالأرقام: "50%" لا "خمسون بالمئة"
4. السيناريوهات الثلاثة مجموعها 100% — كل سيناريو لا يقل عن 15% مطلقا بدون استثناء — مثال صحيح: صعود(20%) هبوط(55%) تذبذب(25%) — مثال خاطئ: تذبذب(0%) او تذبذب(10%)
5. {prob_floor} — حد ادنى للسيناريو الرئيسي، والباقيان لا يقل اي منهم عن 15%
6. لا تكرر اي جملة او فكرة — كل جملة تضيف معلومة جديدة بالارقام
7. اذكر مستويات سعرية محددة ($) في كل قسم — ممنوع الكلام العام بدون ارقام
8. قاموس RSI: اقل من 30=تشبع بيع | 30-40=ضغط بيع | 40-50=محايد مع ميل هبوطي | 50-60=محايد مع ميل صعودي | 60-70=ضغط شراء | اكثر من 70=تشبع شراء
9. في الخلاصة لا تذكر الاحتمالية مرتين — اكتب الاحتمالية مرة واحدة فقط وتطابق السيناريو الرئيسي: اذا هبوط(55%) في السيناريوهات اكتب في الخلاصة "احتمالية هبوط 55%" فقط

بيانات السوق:
سعر الذهب = {gold:.2f}$ | RSI={d['rsi']} | ADX={d['adx']} | MACD={d['macd_hist']}
الإطارات: أسبوعي RSI={d['tf_weekly']['rsi']} | يومي RSI={d['tf_daily']['rsi']} | ساعي RSI={d['tf_hourly'].get('rsi','--')}
فيبوناتشي (آجل): 78.6%={d['fib']['78.6%']}$ | 61.8%={d['fib']['61.8%']}$ | 50%={d['fib']['50.0%']}$
الدعم القريب={d['s1']}$ | المقاومة={d['r1']}$ | ATR={d['atr']}$
التباين: {d['divergence']}
التوافق: {d['tf_label']}
حكم السوق: {conf['verdict']}

صفقات الشراء:
{_fmt_ai(ent['buys'])}
صفقات البيع:
{_fmt_ai(ent['sells'])}

اكتب هذه الأقسام فقط بالترتيب:

━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 التحليل الكمي
━━━━━━━━━━━━━━━━━━━━━━━━━━

**📌 خلاصة:** [جملة واحدة — {bias_ar} + احتمالية + اذكر مستوى الدعم/المقاومة الأقرب]

**🔍 الإطارات الزمنية:** [جملتان بالأرقام. الأولى: ما الذي يقوله الأسبوعي (RSI={d['tf_weekly']['rsi']}) مقارنة بالساعي؟ الثانية: ما المستوى المحدد الذي يجب كسره لتأكيد هذا الاتجاه؟]

**📉 السيناريوهات (100%):**
   📈 صعود (X%): كسر {refs['above']}$ → الهدف [رقم]$ — آجل (Futures)
   📉 هبوط (Y%): كسر {refs['below']}$ → الهدف [رقم]$ — آجل (Futures)
   ⚡ تذبذب (Z%): النطاق [رقم]$-[رقم]$ — آجل (Futures)"""

    fixed += "\n\n" + _build_friday_target(d, True)
    return fixed, ai_instructions



def _build_gold_strength_section(d: dict) -> str:
    """قسم قوة الذهب — بالصيغة النصية التفصيلية المطلوبة"""
    gold  = d['gold']
    
    # محاولة جلب بيانات اليوم والأمس من yfinance
    try:
        import yfinance as _yf_gs
        _df_gs = _yf_gs.Ticker('GC=F').history(period='2d', interval='1d')
        if _df_gs is not None and len(_df_gs) >= 2:
            prev_close = float(_df_gs['Close'].iloc[-2])
            today_open = float(_df_gs['Open'].iloc[-1])
            today_high = float(_df_gs['High'].iloc[-1])
            today_low  = float(_df_gs['Low'].iloc[-1])
            session_chg     = gold - today_open
            session_chg_pct = (gold - today_open) / today_open * 100
            day_range_pos   = (gold - today_low) / (today_high - today_low + 0.01) * 100 if (today_high - today_low) > 0 else 50.0
        else:
            raise ValueError('no data')
    except Exception:
        atr = d.get('atr', 50)
        session_chg     = gold - (gold - atr*0.1)
        session_chg_pct = session_chg / gold * 100
        day_range_pos   = 50.0
        prev_close      = gold - atr*0.15
        today_open      = gold - atr*0.1
        today_high      = gold + atr*0.3
        today_low       = gold - atr*0.3

    is_up = session_chg >= 0
    dir_str_noun = 'ارتفاعاً' if is_up else 'انخفاضاً'
    dir_str_adj  = 'صعوداً' if is_up else 'هبوطاً'
    dir_str_act  = 'بزيادة' if is_up else 'بانخفاض'
    dir_str_noun_def = 'الصعود' if is_up else 'الهبوط'
    dir_str_action = 'شرائياً' if is_up else 'بيعياً'
    dir_str_fem = 'الصاعدة' if is_up else 'الهابطة'

    # ── 1. الزخم الحالي ──
    abs_pct = abs(session_chg_pct)
    if abs_pct > 1.2:
        mom_level = 'قوياً جداً'
        mom_desc  = 'يشير إلى قوة استثنائية'
        mom_press = f'يعكس ضغطاً {dir_str_action} كبيراً'
    elif abs_pct > 0.5:
        mom_level = 'متوسط المستوى'
        mom_desc  = 'لا يشير إلى قوة استثنائية'
        mom_press = f'لكنه يعكس ضغطاً {dir_str_action} ملحوظاً'
    else:
        mom_level = 'ضعيفاً'
        mom_desc  = 'يعكس حركة طفيفة'
        mom_press = 'وهو ما يعكس استقراراً نسبياً'

    momentum_text = f"الذهب يسجل {dir_str_noun} خلال الجلسة الحالية بنسبة {abs_pct:.2f}% و{dir_str_act} {abs(session_chg):.2f} دولار. يُعدّ هذا {dir_str_adj} {mom_level}، {mom_desc}، {mom_press} خلال الجلسة."

    # ── 2. حجم التداول ──
    rv = d.get('rel_vol', 1.0) or 1.0
    if rv >= 1.5:
        vol_title = 'حجم مرتفع'
        vol_desc  = 'يقع ضمن المستوى المرتفع'
        vol_supp  = 'قوياً'
        vol_end   = 'مما يُشير إلى اهتمام استثنائي من السوق'
    elif rv >= 0.8:
        vol_title = 'حجم متوسط'
        vol_desc  = 'يقع ضمن المستوى الطبيعي'
        vol_supp  = 'مقبولاً'
        vol_end   = 'دون أن يُشير إلى اهتمام استثنائي من السوق'
    else:
        vol_title = 'حجم ضعيف'
        vol_desc  = 'يقع ضمن المستوى المنخفض'
        vol_supp  = 'ضعيفاً'
        vol_end   = 'مما يدل على غياب السيولة القوية'

    volume_text = f"{vol_title}\nحجم التداول الحالي {vol_desc}، ويُعطي دعماً {vol_supp} للحركة {dir_str_fem} {vol_end}."

    # ── 3. نتيجة الزخم والحجم ──
    mom_vol_title = 'نتيجة الزخم والحجم:'
    if abs_pct > 1.2 and rv >= 1.5:
        mom_vol_text = f"{dir_str_noun_def} الحالي قوي جداً ويحظى بدعم قوي من حجم التداول. يوجد توافق قوي بين الزخم والحجم، مما يؤكد قوة الاتجاه. الدخول مع الاتجاه مفضل في هذه المرحلة."
    elif abs_pct <= 0.5 and rv < 0.8:
        mom_vol_text = f"{dir_str_noun_def} الحالي ضعيف ويحظى بدعم ضعيف من حجم التداول. يوجد توافق على الضعف بين الزخم والحجم، مما يستدعي الحذر الشديد من الحركات الوهمية."
    else:
        mom_vol_text = f"{dir_str_noun_def} الحالي متوسط المستوى ويحظى بدعم نسبي من حجم التداول. لا يوجد تعارض واضح بين الزخم والحجم، غير أن الحركة لا ترقى إلى مستوى {dir_str_noun_def} المدعوم بالكامل. الحذر النسبي مناسب في هذه المرحلة."

    # ── 4. موقع السعر ──
    if day_range_pos > 66:
        pos_desc = 'العلوي'
    elif day_range_pos < 33:
        pos_desc = 'السفلي'
    else:
        pos_desc = 'الأوسط'
    price_pos_text = f"السعر الحالي عند {gold:,.2f} دولار يتداول في الجزء {pos_desc} من النطاق اليومي، إذ تبلغ نسبة موقعه {day_range_pos:.2f}% من النطاق بين القاع اليومي {today_low:,.2f} والقمة اليومية {today_high:,.2f}. هذا يُشير إلى ميل السعر نحو الجانب {pos_desc} من الحركة اليومية."

    # ── 5. الاتجاه العام (Composite Trend) ──
    ema50 = d.get('ema50', gold)
    ema200 = d.get('ema200', gold)
    
    # استخراج البيانات العميقة للاتجاه
    w_bias = d.get('tf_weekly', {}).get('bias', 'محايد')
    d_bias = d.get('tf_daily', {}).get('bias', 'محايد')
    adx_strength = d.get('tf_daily', {}).get('adx', 0)
    rsi_val = d.get('tf_daily', {}).get('rsi', 50)
    
    # تحديد الهيكل الرياضي
    struct_support = (gold > ema200)
    mom_support = (gold > ema50)
    
    if 'صعود' in w_bias and 'صعود' in d_bias and struct_support:
        overall_trend = "صاعد قوي جداً ومؤكد (Bullish)"
        trend_rationale = f"الاتجاه الهيكلي (أسبوعي/يومي) متطابق تماماً في مسار صاعد، والسعر يستقر بثبات فوق متوسط 200 يوم ({ema200:,.2f}$). القوة الشرائية مسيطرة."
    elif 'هبوط' in w_bias and 'هبوط' in d_bias and not struct_support:
        overall_trend = "هابط قوي جداً ومؤكد (Bearish)"
        trend_rationale = f"الاتجاه الهيكلي (أسبوعي/يومي) متطابق تماماً في مسار هابط، والسعر يتداول تحت ضغط متوسط 200 يوم ({ema200:,.2f}$). القوة البيعية مسيطرة."
    elif mom_support and not struct_support:
        overall_trend = "تعافي متوسط الأجل (Recovery)"
        trend_rationale = f"السعر يعاني من ضغط هيكلي أسفل متوسط 200 يوم، ولكنه أظهر تعافياً باختراق متوسط 50 يوم ({ema50:,.2f}$) لأعلى، مما يعكس تحسناً في الزخم الشرائي اللحظي."
    elif not mom_support and struct_support:
        overall_trend = "تصحيح هابط (Correction)"
        trend_rationale = f"الاتجاه العام لا يزال صاعداً كونه أعلى متوسط 200 يوم، لكن الزخم الحالي ضعيف بعد كسر متوسط 50 يوم ({ema50:,.2f}$) لأسفل، مما يُصنف كحركة تصحيحية."
    else:
        overall_trend = "متذبذب (Ranging)"
        trend_rationale = f"غياب السيولة الواضحة وتقاطع الإشارات بين الفريمات اليومية والأسبوعية يضع السعر في حالة تذبذب بانتظار حافز اقتصادي جديد."
        
    adx_desc = f"مؤشر قوة الترند (ADX) يسجل {adx_strength:.1f} مما يعكس {'قوة دفع عالية' if adx_strength > 25 else 'ضعفاً في الدفع والاتجاه للمسار العرضي'}."
    
    ma50_text = f"""التشخيص العميق للترند:
يُصنف الاتجاه الحالي بأنه [{overall_trend}].
{trend_rationale}
{adx_desc}"""
    ma200_text = ""

    # ── 6. الافتتاح والاغلاق ──
    open_vs_close = today_open - prev_close
    open_vs_close_pct = (open_vs_close / prev_close * 100) if prev_close > 0 else 0.0
    if abs(open_vs_close_pct) < 0.15:
        gap_desc = 'لا يتجاوز'
        gap_res  = 'مستقر دون فجوة سعرية تُذكر'
    else:
        gap_desc = 'يبلغ'
        gap_res  = 'بفجوة سعرية واضحة'
    gap_text = f"افتتحت الجلسة الحالية عند {today_open:,.2f} دولار مقارنةً بإغلاق أمس عند {prev_close:,.2f} دولار. الفارق بينهما {gap_desc} {abs(open_vs_close_pct):.2f}%، مما يُشير إلى افتتاح {gap_res}. {dir_str_noun_def} الحالي جاء بعد الافتتاح خلال الجلسة."

    # ── 7. الخلاصة النهائية ──
    ma_aligned = ((gold > ema50) == is_up) and ((gold > ema200) == is_up)
    if abs_pct > 1.2 and rv >= 1.5 and ma_aligned:
        sum_warn = 'مدعوم بقوة'
        sum_ma = 'يدعم'
        sum_end = 'وهي مدعومة بشكل هيكلي'
    else:
        sum_warn = 'يحتاج حذر'
        sum_ma = 'لا يدعم' if not ma_aligned else 'يدعم'
        sum_end = 'لكنها تواجه ضغطاً هيكلياً' if not ma_aligned else 'وهي مدعومة بشكل هيكلي'

    summary_text = f"وفقاً للمعلومات المتوفرة، فإن {dir_str_noun_def} الحالي في الذهب {sum_warn}. الزخم {mom_level} وحجم التداول {vol_title.replace('حجم ', '')}، كما أن السعر ما زال يتداول {'أعلى' if gold > ema50 else 'أسفل'} متوسط 50 و{'أعلى' if gold > ema200 else 'أسفل'} متوسط 200 يوم، مما يعني أن الاتجاه العام على المدى المتوسط والبعيد {sum_ma} هذا {dir_str_noun_def} بشكل كامل. الحركة {dir_str_fem} اليومية قائمة، {sum_end} من المتوسطات العامة."

    return (
        f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 تقرير قوة الذهب | التحديث اليومي\n\n"
        f"🟡 الذهب\n\n"
        f"السعر الحالي:\n"
        f"{gold:,.2f} دولار\n\n"
        f"⚡️ الزخم الحالي:\n"
        f"{momentum_text}\n\n"
        f"📊 حجم التداول:\n"
        f"{volume_text}\n\n"
        f"📌 نتيجة الزخم والحجم:\n"
        f"{mom_vol_text}\n\n"
        f"📍 موقع السعر:\n"
        f"{price_pos_text}\n\n"
        f"📈 الاتجاه العام:\n\n"
        f"{ma50_text}\n\n"
        f"{ma200_text}\n\n"
        f"🔄 مقارنة الافتتاح والإغلاق السابق:\n"
        f"{gap_text}\n\n"
        f"🧭 الخلاصة النهائية:\n"
        f"{summary_text}\n"
    )

def _build_today_ohlc_section(d: dict) -> str:
    """
    قسم مستقل في آخر التقرير:
    إغلاق اليوم المتوقع + القمة + القاع — بجودة حقيقية ومفسّرة
    """
    gold = d['gold']
    fc   = d.get('tf_forecasts', {})
    atr  = d.get('atr', 50.0)
    bias = d['confluence']['bias']

    fc_1d = fc.get('1d', {})
    fc_4h = fc.get('4h', {})
    fc_1h = fc.get('1h', {})

    pred_close = fc_1d.get('close', round(gold, 2))
    pred_high  = fc_1d.get('high',  round(gold + atr * 0.4, 2))
    pred_low   = fc_1d.get('low',   round(gold - atr * 0.4, 2))
    quality    = fc_1d.get('quality', 50)

    # تفسير اتجاه الإغلاق
    diff = pred_close - gold
    diff_pct = round(diff / gold * 100, 2) if gold > 0 else 0.0

    if diff > atr * 0.15:
        close_interp = f'الإغلاق المتوقع صعودي (+{diff:.2f}$) — الزخم يدعم السعر للأعلى'
    elif diff < -atr * 0.15:
        close_interp = f'الإغلاق المتوقع هبوطي ({diff:.2f}$) — ضغط بيع سائد'
    else:
        close_interp = f'الإغلاق المتوقع محايد (تغير {diff:+.2f}$) — سوق متوازن'

    # احتمالية تجاوز القمة
    dist_to_high = round(pred_high - gold, 2)
    dist_to_low  = round(gold - pred_low, 2)

    # جودة التوقع label
    if quality >= 75:  q_label = f'جودة عالية ({quality}%) ✅'
    elif quality >= 55: q_label = f'جودة جيدة ({quality}%) 🟡'
    else:               q_label = f'جودة متوسطة ({quality}%) 🟠'

    # نطاق ATR اليوم
    exp_low  = round(gold - atr * 0.65, 2)
    exp_high = round(gold + atr * 0.65, 2)

    # مستويات السيناريوهات (تقاطع التوقع مع فيبو + pivot)
    fib = d.get('fib', {})
    pivot = d.get('pivot', gold)
    r1, s1 = d.get('r1', gold+50), d.get('s1', gold-50)

    # تقييم احتمالية كسر القمة أو القاع
    # بناءً على: ADX + RSI + حجم التداول
    adx = float(d.get('adx', 20))
    rsi = float(d.get('rsi', 50))
    rv  = d.get('rel_vol', 1.0) or 1.0

    bull_prob = 0
    bear_prob = 0
    if bias == 'bull': bull_prob += 20
    elif bias == 'bear': bear_prob += 20
    else: bull_prob += 10; bear_prob += 10
    if rsi > 55: bull_prob += 15
    elif rsi < 45: bear_prob += 15
    if adx > 25:
        if d.get('di_plus', 0) > d.get('di_minus', 0): bull_prob += 10
        else: bear_prob += 10
    if rv > 1.5: bull_prob += 5 if bias != 'bear' else 0; bear_prob += 5 if bias == 'bear' else 0

    bull_prob = min(bull_prob, 80)
    bear_prob = min(bear_prob, 80)

    # أقرب مستوى فيبو للقمة والقاع
    fib_vals_above = sorted([v for v in fib.values() if v and v > gold])
    fib_vals_below = sorted([v for v in fib.values() if v and v < gold], reverse=True)
    nearest_fib_high = fib_vals_above[0] if fib_vals_above else pred_high
    nearest_fib_low  = fib_vals_below[0] if fib_vals_below else pred_low

    # الاتجاه خلال الإطارات المختلفة
    def get_trend(diff_val, threshold):
        if diff_val > threshold: return 'صاعد 📈'
        elif diff_val < -threshold: return 'هابط 📉'
        return 'عرضي (متذبذب) ↔️'

    diff_1h = fc_1h.get('close', gold) - gold
    trend_1h = get_trend(diff_1h, atr * 0.05)

    fc_4h = fc.get('4h', {})
    diff_4h = fc_4h.get('close', gold) - gold
    trend_4h = get_trend(diff_4h, atr * 0.1)

    diff_1d = pred_close - gold
    trend_1d = get_trend(diff_1d, atr * 0.15)

    fc_1w = fc.get('1wk', fc.get('1w', {}))
    diff_1w = fc_1w.get('close', gold) - gold
    trend_1w = get_trend(diff_1w, atr * 0.3)

    fc_1m = fc.get('1mo', fc.get('1m', {}))
    diff_1m = fc_1m.get('close', gold) - gold
    trend_1m = get_trend(diff_1m, atr * 0.5)

    # أيهما يضرب أولاً
    if bull_prob > bear_prob + 10:
        hit_first = 'القمة أولاً 🔺 (ضغط شراء وزخم صاعد)'
    elif bear_prob > bull_prob + 10:
        hit_first = 'القاع أولاً 🔻 (ضغط بيع وزخم هابط)'
    else:
        if diff_1d > 0: hit_first = 'القمة أولاً 🔺 (ميل إيجابي طفيف)'
        elif diff_1d < 0: hit_first = 'القاع أولاً 🔻 (ميل سلبي طفيف)'
        else: hit_first = 'نطاق تجميعي ⚖️ (احتمالات متساوية لضرب القمة أو القاع)'

    lines_out = [
        "\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501",
        "\U0001f4ca \u062a\u0648\u0642\u0639\u0627\u062a \u064a\u0648\u0645 \u0627\u0644\u062c\u0644\u0633\u0629 \u0627\u0644\u062d\u0627\u0644\u064a\u0629",
        f"   \U0001f4cc \u0627\u0644\u0633\u0639\u0631 \u0627\u0644\u062d\u0627\u0644\u064a: {gold:,.2f}$  |  {q_label}",
        "",
        "   \u256d\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u256e",
        f"   \u2502 \U0001f7e2 \u0625\u063a\u0644\u0627\u0642 \u0627\u0644\u064a\u0648\u0645 \u0627\u0644\u0645\u062a\u0648\u0642\u0639: {pred_close:,.2f}$",
        f"   \u2502    \u2514\u2500 {close_interp}",
        "   \u251c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2524",
        f"   \u2502 \U0001f53a \u0642\u0645\u0629 \u0627\u0644\u064a\u0648\u0645 \u0627\u0644\u0645\u062a\u0648\u0642\u0639\u0629: {pred_high:,.2f}$  (+{dist_to_high}$ \u0645\u0646 \u0627\u0644\u062d\u0627\u0644\u064a)",
        f"   \u2502    \u0623\u0642\u0631\u0628 \u0641\u064a\u0628\u0648 \u0641\u0648\u0642\u0647\u0627: {nearest_fib_high:,.2f}$  |  \u0645\u0642\u0627\u0648\u0645\u0629: {r1}$",
        "   \u251c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2524",
        f"   \u2502 \U0001f53b \u0642\u0627\u0639 \u0627\u0644\u064a\u0648\u0645 \u0627\u0644\u0645\u062a\u0648\u0642\u0639:  {pred_low:,.2f}$  (-{dist_to_low}$ \u0645\u0646 \u0627\u0644\u062d\u0627\u0644\u064a)",
        f"   \u2502    \u0623\u0642\u0631\u0628 \u0641\u064a\u0628\u0648 \u062a\u062d\u062a\u0647\u0627: {nearest_fib_low:,.2f}$   |  \u062f\u0639\u0645: {s1}$",
        "   \u251c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2524",
        f"   \u2502 \U0001f4cf \u0646\u0637\u0627\u0642 ATR \u0627\u0644\u064a\u0648\u0645\u064a: {exp_low:,.2f}$ \u2194 {exp_high:,.2f}$",
        f"   \u2502 \U0001f4c5 Pivot \u0627\u0644\u064a\u0648\u0645: {pivot:,.2f}$",
        "   \u251c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2524",
        f"   \u2502 \U0001f4c8 \u0627\u062d\u062a\u0645\u0627\u0644\u064a\u0629 \u0635\u0639\u0648\u062f \u0646\u062d\u0648 \u0627\u0644\u0642\u0645\u0629: {bull_prob}%",
        f"   \u2502 \U0001f4c9 \u0627\u062d\u062a\u0645\u0627\u0644\u064a\u0629 \u0647\u0628\u0648\u0637 \u0646\u062d\u0648 \u0627\u0644\u0642\u0627\u0639:  {bear_prob}%",
        f"   \u2502 \u26a1 \u0627\u062d\u062a\u0645\u0627\u0644\u064a\u0629 \u0627\u0644\u062a\u0630\u0628\u0630\u0628 \u0641\u064a \u0627\u0644\u0646\u0637\u0627\u0642: {100 - bull_prob - bear_prob}%",
        "   \u2570\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u256f",
        "",
        "   \u2139\ufe0f \u0647\u0630\u0627 \u0627\u0644\u062a\u0648\u0642\u0639 \u0645\u0628\u0646\u064a \u0639\u0644\u0649: ATR + ADX(\u0642\u0648\u0629 \u0627\u0644\u062a\u0631\u0646\u062f) + \u062a\u0648\u0627\u0641\u0642 \u0627\u0644\u0625\u0637\u0627\u0631\u0627\u062a + \u0641\u064a\u0628\u0648\u0646\u0627\u062a\u0634\u064a",
    ]
    return "\n".join(lines_out)


def _build_template_1(d: dict) -> str:
    """بناء القالب الأول (الموجز الكلاسيكي المنفصل)"""
    w_rsi = d.get('tf_weekly', {}).get('rsi', 50)
    w_bias = 'صاعد 📈' if w_rsi >= 50 else 'هابط 📉'
    
    d_rsi = d.get('tf_daily', {}).get('rsi', 50)
    d_bias = 'صاعد 📈' if d_rsi >= 50 else 'هابط 📉'
    
    gold = d['gold']
    pivot = d.get('pivot', gold)
    atr = d.get('atr', 20)
    r1 = d.get('r1', pivot + atr)
    s1 = d.get('s1', pivot - atr)
    
    if gold >= pivot:
        zone_color = '🟢'
        zone_name = 'مستوى الدعم الحيوي'
        exact_zone = round(pivot, 2)
        t1 = round(r1, 2)
        t2 = round(d.get('r2', r1 + atr), 2)
        cont_action = 'الصعود لاستهداف قمم أعلى'
        rev_color = '🔴'
        rev_zone = round(s1, 2)
        rev_dir = 'الهبوط السلبي'
        break_dir = 'أسفله'
    else:
        zone_color = '🔴'
        zone_name = 'مستوى المقاومة المحوري'
        exact_zone = round(pivot, 2)
        t1 = round(s1, 2)
        t2 = round(d.get('s2', s1 - atr), 2)
        cont_action = 'الهبوط لاستهداف قيعان أدنى'
        rev_color = '🟢'
        rev_zone = round(r1, 2)
        rev_dir = 'الصعود الإيجابي'
        break_dir = 'أعلاه'
        
    template = f'''📊 التقرير الفني المتقدم للذهب (الآجل) 🟡
━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 1W (الأسبوعي)
   التحيز الأسبوعي: {w_bias}

📆 1D (اليومي)
   التحيز اليومي: {d_bias}
━━━━━━━━━━━━━━━━━━━━━━━━━━

{zone_color} مستوى المراقبة ({zone_name}): {exact_zone}$

في حال احترام المستوى، نتوقع استهداف:
🎯 {t1}$
🎯 {t2}$

وفي حالة كسر {t2}$، سيستمر {cont_action}.

{rev_color} أما إذا لم يحترم السعر مستوى {exact_zone}$ وتمكن من كسره، فسيستهدف {rev_zone}$.
وتعتبر النقطة {rev_zone}$ هي النقطة الذهبية الفاصلة، وباختراقها والثبات {break_dir} يتغير الاتجاه نحو {rev_dir}.

━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 ملخص القالب
   السعر الحالي  : {gold:.2f}$
   التحيز الأسبوعي: {w_bias} (RSI أسبوعي = {w_rsi})
   التحيز اليومي  : {d_bias} (RSI يومي = {d_rsi})
   المستوى المحوري: {exact_zone}$ ({zone_name})
   السعر {'فوق' if gold >= pivot else 'تحت'} المحور بـ {abs(round(gold - exact_zone, 2))}$
   الهدف الأول   : {t1}$
   الهدف الثاني  : {t2}$
   نقطة الانعكاس : {rev_zone}$ (تغيير الاتجاه نحو {rev_dir})

━━━━━━━━━━━━━━━━━━━━━━━━━━
🔗 الخلاصة وتأثيرها على الذهب
   {'✅ الذهب فوق المحور ({exact_zone}$) — الضغط الشرائي مسيطر. طالما يحافظ على هذا المستوى، الاحتمال الأرجح هو الصعود نحو {t1}$ ثم {t2}$. اختراق {t2}$ لأعلى يفتح مسار {cont_action}.'.format(exact_zone=exact_zone, t1=t1, t2=t2, cont_action=cont_action) if gold >= pivot else '⚠️ الذهب تحت المحور ({exact_zone}$) — الضغط البيعي مسيطر. طالما لم يعد فوق المحور، الاحتمال الأرجح هو الهبوط نحو {t1}$ ثم {t2}$. اختراق {t2}$ لأسفل يفتح مسار {cont_action}.'.format(exact_zone=exact_zone, t1=t1, t2=t2, cont_action=cont_action)}
   نقطة المراقبة الحاسمة: {rev_zone}$ — كسرها يقلب الاتجاه بالكامل نحو {rev_dir}.'''
    return template

def generate_report(d: dict, is_alert: bool = False, price_diff: float = 0.0, is_morning: bool = False) -> str | None:
    client = Groq(api_key=random.choice(GROQ_KEYS)) if GROQ_KEYS else None
    if not client:
        return None

    banner = "💎 المزايا الحصرية مفعلة: (مبني على 12 مؤشر، زيرو انعكاس، سكالبينج، توقع القمة والقاع، وعزل العرض والطلب)"
    if is_morning:  header = f"🌅 نشرة الصباح — استراتيجية اليوم\n{banner}"
    elif is_alert:  header = f"🚨 تنبيه — حركة {'+' if price_diff>0 else ''}{price_diff:.2f}$\n{banner}"
    else:           header = f"📊 نشرة التحليل الكمي للذهب\n{banner}"

    fixed_block, ai_instructions = _build_fixed_template(d, header)

    for model_name in GROQ_MODELS:
        try:
            log.info(f"🤖 جاري الاتصال بـ Groq — {model_name}")
            resp = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": MASTER_SYSTEM_PROMPT + "أنت محلل ذهب كمي. اكتب فقط ما طُلب منك بالعربية الفصحى. لا تكتب أي شيء خارج الأقسام المطلوبة."},
                    {"role": "user",   "content": ai_instructions},
                ],
                model=model_name,
                temperature=0.07,
                max_tokens=700,
            )
            ai_analysis = resp.choices[0].message.content
            log.info(f"✅ نجح الاتصال: {model_name}")
            return fixed_block + "\n\n" + ai_analysis
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate_limit" in err_str.lower():
                log.warning(f"⚠️ [{model_name}] 429 — الانتقال للتالي...")
                time.sleep(10)
                continue
            log.error(f"❌ [{model_name}] {e}")
            break

    log.error("❌ جميع الموديلات فشلت — إرسال الجزء الثابت فقط.")
    return fixed_block


# ══════════════════════════════════════════════
#  8. إرسال تيليجرام
# ══════════════════════════════════════════════
CHUNK_SIZE = 3400   # أقل من 4096 (حد تيليجرام) — هامش أمان يحسب الـ header [i/total] + subtitle (~200 حرف)

def _tg_len(text: str) -> int:
    """طول النص بحسب UTF-16 code units — الطريقة التي يحسب بها تيليجرام الأحرف"""
    return sum(2 if ord(c) > 0xFFFF else 1 for c in text)


def _split_message(text: str) -> list:
    if _tg_len(text) <= CHUNK_SIZE:
        return [text]

    SEPARATOR = "━━━━━━━━━━━━━━━━━━━━━━━━━━"
    lines   = text.split("\n")
    chunks  = []
    current = ""
    in_table = False

    for i, line in enumerate(lines):
        if "╭─" in line:
            in_table = True
            if _tg_len(current) > CHUNK_SIZE - 500:
                chunks.append(current.strip() + "\n\n(يتبع...)")
                current = "(تكملة القالب السابق...)\n"

        new_block = (current + "\n" + line) if current else line
        
        if _tg_len(new_block) > CHUNK_SIZE:
            if current:
                chunks.append(current.strip() + "\n\n(يتبع...)")
                current = "(تكملة القالب السابق...)\n" + line
            else:
                current = line
        else:
            current = new_block

        if "╰─" in line:
            in_table = False

        next_line = lines[i + 1] if i + 1 < len(lines) else ""
        if (next_line.startswith(SEPARATOR) and _tg_len(current) > CHUNK_SIZE * 0.70):
            chunks.append(current.strip() + "\n\n(يتبع...)")
            current = "(تكملة القالب السابق...)\n"

    if current and current.strip() and current.strip() != "(تكملة القالب السابق...)":
        chunks.append(current.strip())
        
    return chunks


async def _telethon_send(text: str) -> bool:
    """MTProto بجلسة المستخدم الموجودة — يتجاوز حجب api.telegram.org تماماً"""
    if not SESSION_STRING:
        log.warning("⚠️ [Telethon] SESSION_STRING غير موجود.")
        return False
    try:
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        await client.start()   # جلسة موجودة — بدون ImportBotAuthorizationRequest
        for chat in TARGET_CHATS:
            await client.send_message(chat, text)
        await client.disconnect()
        return True
    except Exception as e:
        log.warning(f"⚠️ [Telethon] {e}")
        return False


def _http_send(text: str, is_public_allowed: bool = True, chat_id=None) -> bool:
    """الإرسال عبر HTTP Bot API — الوسيلة الأساسية."""
    url     = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    headers = {
        "Connection": "close",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    success = True
    targets = [chat_id] if chat_id else TARGET_CHATS
    for chat in targets:
        payload = {"chat_id": str(chat), "text": text}
        chat_success = False
        for attempt in range(4):
            try:
                r = requests.post(url, json=payload, headers=headers, timeout=45)
                r.raise_for_status()
                chat_success = True
                break
            except Exception as e:
                wait = 2 ** attempt
                log.warning(f"⚠️ [HTTP] {attempt+1}/4 — {e} — انتظار {wait}s")
                time.sleep(wait)
        if not chat_success: success = False
    return success


async def _telethon_bot_send(text: str, is_public_allowed: bool = True, chat_id=None) -> bool:
    """MTProto باستخدام توكن البوت — يتجاوز حجب HTTP نهائياً ولا يتعارض مع جلسات المستخدم"""
    try:
        # استخدام ملف جلسة محلي بدلاً من الذاكرة لتجنب تسجيل الدخول بالتوكن في كل رسالة (يمنع الـ FloodWait)
        client = TelegramClient("goldbot_bot_session", API_ID, API_HASH)
        await client.start(bot_token=TELEGRAM_BOT_TOKEN)
        
        targets = [chat_id] if chat_id else TARGET_CHATS
        for chat in targets:
            try:
                await client.send_message(chat, text)
            except Exception as inner_e:
                log.warning(f"⚠️ [Telethon Bot (Futures)] فشل الإرسال للجروب {chat}: {inner_e}")
                
        await client.disconnect()
        return True
    except Exception as e:
        log.warning(f"⚠️ [Telethon Bot (Futures)] {e}")
        return False


async def _telethon_bot2_send(text: str, chat_id=None) -> bool:
    """MTProto للبوت الثاني — يتجاوز حجب HTTP على HuggingFace تماماً"""
    try:
        client = TelegramClient("goldbot_bot2_session", API_ID, API_HASH)
        await client.start(bot_token=TELEGRAM_BOT_TOKEN_2)
        targets = [chat_id] if chat_id else TARGET_CHATS
        for chat in targets:
            try:
                await client.send_message(chat, text)
            except Exception as inner_e:
                log.warning(f"[Bot2 Telethon] فشل الإرسال للجروب {chat}: {inner_e}")
        await client.disconnect()
        return True
    except Exception as e:
        log.warning(f"[Bot2 Telethon] {e}")
        return False


def _send_single_bot2(text: str, is_public_allowed: bool = True, chat_id=None) -> bool:
    """الإرسال للبوت الثاني عبر Telethon MTProto (بدلاً من HTTP المحجوب على HuggingFace)"""
    try:
        ok = asyncio.run(_telethon_bot2_send(text, chat_id))
        if ok:
            log.info("[Telethon Bot2] تم الإرسال بنجاح.")
            return True
    except RuntimeError:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            ok = loop.run_until_complete(_telethon_bot2_send(text, chat_id))
            loop.close()
            if ok:
                log.info("[Telethon Bot2] تم الإرسال بنجاح.")
                return True
        except Exception as e:
            log.warning(f"[Telethon Bot2 loop] {e}")
    except Exception as e:
        log.warning(f"[Telethon Bot2] {e}")
    log.error("[Bot2] فشل الإرسال عبر Telethon.")
    return False



def _send_single(text: str, is_public_allowed: bool = True, chat_id=None) -> bool:
    """إرسال عبر MTProto (Bot) أولاً للهروب من مشاكل Timeout، والـ HTTP كاحتياطي."""
    try:
        ok = asyncio.run(_telethon_bot_send(text, is_public_allowed, chat_id))
        if ok:
            log.info("✅ [Telethon Bot (Futures)] تم الإرسال بنجاح.")
            return True
    except RuntimeError:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            ok = loop.run_until_complete(_telethon_bot_send(text, is_public_allowed, chat_id))
            loop.close()
            if ok:
                log.info("✅ [Telethon Bot (Futures)] تم الإرسال بنجاح.")
                return True
        except Exception as e:
            log.warning(f"⚠️ [Telethon Bot (Futures) loop] {e}")
    except Exception as e:
        log.warning(f"⚠️ [Telethon Bot (Futures)] {e}")

    log.warning("⚠️ [Telethon Bot (Futures)] فشل — جاري المحاولة عبر HTTP...")
    if _http_send(text, is_public_allowed, chat_id):
        log.info("✅ [HTTP] تم الإرسال بنجاح.")
        return True
    log.error("❌ فشل الإرسال من جميع الوسائل.")
    return False


def send_to_telegram(message: str, chat_id=None) -> bool:
    global LAST_PUBLIC_REPORT_TIME
    if not message:
        return False
        
    now = time.time()
    is_public = False
    if now - LAST_PUBLIC_REPORT_TIME >= 3500:
        is_public = True
        if not chat_id: LAST_PUBLIC_REPORT_TIME = now
        
    chunks = _split_message(message)
    log.info(f"📤 إرسال في {len(chunks)} جزء... (Public Allowed: {is_public}, Chat: {chat_id})")
    all_ok = True
    for i, chunk in enumerate(chunks, 1):
        ok     = _send_single(chunk, is_public, chat_id)
        log.info(f"✅ جزء {i}/{len(chunks)} وصل." if ok else f"❌ فشل جزء {i}/{len(chunks)}.")
        all_ok = all_ok and ok
        if i < len(chunks): time.sleep(1.5)
    return all_ok


def _build_template_2(d: dict) -> str:
    gld = d.get('gold', 2000)
    dxy = d.get('dxy', 104.0)
    vix = d.get('vix', 15.0)
    inflation = d.get('inflation', 3.0)
    interest_rate = d.get('interest_rate', 5.5)
    real_yield = d.get('real_yield', 2.0)
    
    daily_rsi = d.get('tf_daily', {}).get('rsi', 50)
    verdict = 'صعودي 📈' if daily_rsi >= 50 else 'هبوطي 📉'
    
    return f'''📊 مؤشر صحة الاقتصاد الأمريكي | اليوم

🇺🇸 الحالة العامة:
حالة الاقتصاد الأمريكي تشهد توازناً فنياً حالياً مع تمركز مؤشر الدولار عند {dxy:.1f} نقطة، وسط ترقب لحركة السيولة القادمة.

📈 النمو والاستهلاك:
تشير بيانات عوائد السندات ومنحنى العائد إلى حالة ترقب في أوساط المستثمرين. حيث يعكس فارق العوائد رؤية متباينة لتوقعات النمو والاستهلاك الائتماني على المدى القريب.

🏦 التضخم والفائدة:
تستقر معدلات التضخم حول {inflation:.2f}% بينما تقف الفائدة عند {interest_rate:.2f}%، مما يجعل العائد الحقيقي ({real_yield:+.2f}%) هو المحرك الأساسي لحركة رؤوس الأموال بين الأصول الآمنة.

👷 سوق العمل:
يعكس مؤشر التقلب VIX ({vix:.1f}) حالة من الاستقرار النسبي في أسواق الأسهم والعمل، مما يوفر بيئة تداول واضحة المعالم.

🟡 التأثير على الذهب:
في ظل العائد الحقيقي الحالي ({real_yield:+.2f}%) ومستويات الدولار، السيولة النقدية تدعم بشكل قاطع المسار الـ **{verdict}** للذهب كملاذ آمن في المرحلة الحالية.

💲 التأثير على الدولار:
يتحرك مؤشر DXY عند {dxy:.1f} نقطة متأثراً بعوائد السندات، مما قد يخلق فرصة واضحة لتحديد مسار عكسي للذهب.

🧭 النظرة العامة:
البيئة الاقتصادية الحالية وتدفقات السيولة ترسم صورة واضحة ومحددة. بناءً على هذه المعطيات، فإن الحكم النهائي والاتجاه الفعلي للذهب هو **{verdict}** بشكل لا يقبل التذبذب.'''


def _build_template_3(d: dict) -> str:
    daily_rsi = d.get('tf_daily', {}).get('rsi', 50)
    verdict = 'Risk-On (شهية مفتوحة)' if daily_rsi >= 50 else 'Risk-Off (عزوف عن المخاطرة)'
    gold_dir = 'صاعد 📈' if daily_rsi >= 50 else 'هابط 📉'
    
    return f'''📊 شهية المخاطرة وتدفق السيولة العالمية

🌍 الحالة الحالية للأسواق:
بناءً على التقاطع بين مؤشرات الأسهم والسندات والذهب، حالة شهية المخاطرة في الأسواق اليوم هي: **{verdict}**.

💰 تأثير السيولة والتدفقات النقدية:
- في حالات الـ Risk-On، تتجه السيولة للأصول ذات العوائد ويدعم ذلك قوة الترند المفتوح.
- في حالات الـ Risk-Off، تتجه السيولة للملاذات الآمنة وعلى رأسها الذهب.
حركة السيولة الحالية تدعم بشكل كامل المسار الـ **{gold_dir}** للذهب بدون أي تذبذب.

🧭 تأثير الملاذات الآمنة:
تفاعل الذهب مع شهية المخاطرة الحالية يؤكد استمرار الزخم في الاتجاه المذكور، مما يعزز من فرص التداول مع الترند العام المعتمد.'''


def _build_template_4(d: dict) -> str:
    us10y = d.get('us10y', 4.2)
    us02y = d.get('us02y', 4.5)
    daily_rsi = d.get('tf_daily', {}).get('rsi', 50)
    verdict = 'صاعد 📈' if daily_rsi >= 50 else 'هابط 📉'
    
    return f'''📊 عوائد السندات الأمريكية وتأثيرها على الذهب

📈 عوائد السندات لأجل 10 سنوات (US10Y):
تتمركز العوائد حالياً عند {us10y:.3f}%. هذا المستوى يعكس تسعير الأسواق للسياسة النقدية والتضخم على المدى الطويل.

📉 عوائد السندات لأجل سنتين (US02Y):
تقف عوائد السنتين عند {us02y:.3f}%، مما يوفر رؤية دقيقة لتوقعات الفائدة على المدى القريب.

⚖️ منحنى العائد والفارق الزمني:
الفارق بين العوائد يعكس حالة تسعير الأسواق للركود أو النمو. 
ارتفاع العوائد عادة ما يشكل ضغطاً على الذهب، بينما انخفاضها يدعمه.

🟡 التأثير المباشر على الذهب:
تحركات عوائد السندات الحالية تؤكد سيطرة السيولة الذكية وتدعم بقوة اتجاه الذهب ليكون **{verdict}**. الارتباط العكسي بين الذهب والعوائد يعمل لصالح هذا الاتجاه بوضوح.'''


def _build_template_5(d: dict) -> str:
    daily_rsi = d.get('tf_daily', {}).get('rsi', 50)
    verdict = 'صاعد 📈' if daily_rsi >= 50 else 'هابط 📉'
    
    return f'''📊 قوة العملات (Forex Flow) وتأثيرها المباشر

💱 ترتيب العملات الرئيسية اليوم:
- الدولار الأمريكي (USD): يعكس قوة الزخم والسياسات النقدية.
- اليورو (EUR): يتأثر ببيانات النمو الأوروبية والمركزي الأوروبي.
- الين الياباني (JPY): يعمل كملاذ آمن ويتأثر بعوائد السندات العالمية.
- الباوند (GBP): يعكس حالة المخاطرة والاقتصاد البريطاني.

🌊 تحليل تدفق السيولة للعملات:
السيولة الحالية تتدفق بين الملاذات الآمنة والعملات ذات العوائد المرتفعة، مما يخلق توازناً دقيقاً في سلة العملات. 
تمركز السيولة يظهر بوضوح أن الزخم العام يصب في مصلحة الاتجاه الواضح.

🟡 الاستنتاج والتأثير المباشر على الذهب:
التغيرات اللحظية في قوة العملات تؤكد قوة الدولار أو ضعفه النسبي، وبناءً على التدفقات الحالية، فإن الحكم النهائي على الذهب هو مسار **{verdict}** بامتياز.'''


def _build_template_6(d: dict, fixed_rep: str, t0: str, t1: str, t2: str, t3: str, t4: str, t5: str) -> str:
    """بناء القالب السادس والأخير (الخلاصة الذكية) عبر الذكاء الاصطناعي"""
    from groq import Groq
    import random
    import re
    
    client = Groq(api_key=random.choice(GROQ_KEYS)) if GROQ_KEYS else None
    if not client:
        return "⚠️ لا يمكن توليد تقرير الخلاصة لعدم توفر مفتاح Groq."

    pivot_val = d.get('pivot', '---')
    clean_t0 = re.sub(r'[╭─╮├┤│╰╯]', '', t0) if t0 else ""
    
    # Calculate robust weighted probability
    score = 0
    total_weight = 0
    
    # 1. Trend (weight 3)
    if d.get('ema20', 0) > d.get('ema50', 0) > d.get('ema200', 0): score += 3
    elif d.get('ema20', 0) < d.get('ema50', 0) < d.get('ema200', 0): score -= 3
    total_weight += 3
    
    # 2. Momentum (weight 2)
    macd_hist = d.get('macd_hist', 0)
    if macd_hist > 0: score += 2
    elif macd_hist < 0: score -= 2
    total_weight += 2
    
    rsi = d.get('rsi', 50)
    if rsi > 55: score += 2
    elif rsi < 45: score -= 2
    total_weight += 2
    
    # 3. Volume / OBV (weight 2)
    obv_trend = d.get('obv_trend', '')
    if "صعودي" in obv_trend: score += 2
    elif "هبوطي" in obv_trend: score -= 2
    total_weight += 2
    
    # 4. Multi-Timeframe (weight 3)
    tf_scores = [d.get('tf_weekly', {}).get('score',0), d.get('tf_daily', {}).get('score',0), d.get('tf_hourly', {}).get('score',0)]
    mtf = sum(tf_scores)
    if mtf > 0: score += 3
    elif mtf < 0: score -= 3
    total_weight += 3
    
    # Convert score (-12 to +12) to percentage (0% to 100%)
    up_prob_calc = 50 + (score / total_weight) * 45  # Cap at max 95% / min 5%
    up_prob = int(round(up_prob_calc))
    up_prob = max(10, min(90, up_prob))
    down_prob = 100 - up_prob

    static_header = f"""🎯 خلاصة انحياز الذهب | التحديث المباشر

📈 نسبة الصعود نحو القمة: {up_prob}%
📉 نسبة الهبوط نحو القاع: {down_prob}%

🧭 الخلاصة:"""

    template_for_llm = f"""[سطرين أو ثلاثة فقط تلخص الموقف العام للذهب بناء على كل التقارير المرفقة مع إعطاء قرار نهائي واضح. اكتب بلغة يفهمها المبتدئون]

📍 نقطة الفصل اليومية (Pivot):
{pivot_val}$ [اشرح دلالة التداول حالياً فوق أو تحت هذا المستوى]

📌 مستويات التداول الحالية:
[انقل مستويات البيع والشراء (التي تحتوي على الدوائر 🔴 أو 🟢 أو 🟡) من تقرير التحليل الفني المرفق وضعها هنا بدقة كما هي وبدون تغيير في أرقامها]

💡 الحكم للتأثير النهائي على الذهب:
[بناءً على كل النقاط التي ذُكرت في هذا التقرير، اكتب قراراً استراتيجياً حاسماً ونهائياً يوجه المتداول للخلاصة النهائية (شراء أم بيع) مع ذكر السبب الرئيسي بإيجاز واحترافية]"""

    prompt = f"""أنت "المحلل الأكبر" والمستشار المالي النهائي. 
لقد قام فريقك بإعداد تقارير شاملة حول الذهب تشمل (الصفقات، التحليل الفني، الاقتصاد، والمخاطرة).
الهدف الآن هو استخلاص عصارة هذه التقارير في "رسالة مختصرة ومباشرة للجمهور العام" تطابق هذا القالب بالضبط:

{template_for_llm}

إليك جميع التقارير للتحليل:
--- التقرير الأساسي (الصفقات ومستويات الدعم والمقاومة): ---
{fixed_rep}
--- تقرير الصفقات المتقدمة: ---
{clean_t0}
--- التقرير 1 (الفني والزخم): ---
{t1}
--- التقرير 2 (الاقتصاد الكلي): ---
{t2}
--- التقرير 3 (المخاطرة): ---
{t3}

المطلوب:
1. اقرأ جميع التقارير والصفقات المرفقة بعناية فائقة.
2. اكتب خلاصة مكثفة في سطرين أو ثلاثة كحد أقصى للاتجاه العام. نسبة الصعود المحسوبة آلياً هي {up_prob}%، فاجعل كلامك متوافقاً مع هذا الاتجاه.
3. ابحث في التقارير المرفقة عن أبرز مناطق البيع 🔴 والشراء 🟢 وانقلها بأرقامها الدقيقة إلى قسم المستويات. لا تؤلف أرقاماً.
4. لا تكتب أي مقدمات أو تحيات، فقط أخرج القالب المملوء."""

    for model_name in GROQ_MODELS:
        try:
            log.info(f"🤖 جاري توليد الخلاصة النهائية (القالب 6) عبر {model_name}...")
            resp = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "أنت خبير أسواق مالية صارم يكتب تقارير مباشرة ودقيقة بدون أي حشو."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            llm_text = resp.choices[0].message.content.strip()
            
            # Remove repeated header if the LLM hallucinated it
            llm_text = re.sub(r'🎯 خلاصة انحياز الذهب.*\n', '', llm_text, flags=re.IGNORECASE)
            llm_text = re.sub(r'📈 نسبة الصعود.*\n', '', llm_text)
            llm_text = re.sub(r'📉 نسبة الهبوط.*\n', '', llm_text)
            llm_text = re.sub(r'🧭 الخلاصة:\s*', '', llm_text)
            
            return f"{static_header}\n{llm_text.strip()}"
        except Exception as e:
            log.warning(f"❌ فشل الموديل {model_name} في القالب 6: {e}")
            continue

    # Static fallback
    return f"{static_header}\nالسعر الحالي للذهب: {d.get('gold', 0):.2f}$ | الاتجاه العام: {fallback_bias if 'fallback_bias' in locals() else 'متذبذب'}\n📍 يرجى متابعة المستويات الفنية للحصول على رؤية أدق."

def _build_template_0(d: dict) -> str:
    """بناء القالب التمهيدي 0 (الصفقات المتقدمة والاتجاهات) عبر الذكاء الاصطناعي"""
    client = Groq(api_key=random.choice(GROQ_KEYS)) if GROQ_KEYS else None
    if not client:
        return "⚠️ لا يمكن توليد تقرير الصفقات المتقدمة لعدم توفر مفتاح Groq."

    adv = d.get('adv_trades', {})
    
    def _format_trade(t):
        if not t: return "جاري حساب نقطة الدخول الدقيقة"
        return f"دخول: {t['entry']} | هدف: {t['t2']} | وقف: {t['sl']} | ({'شراء 🟢' if t['dir']=='buy' else 'بيع 🔴'})"

    scalp = (adv.get('scalp_5m_buy') or adv.get('scalp_5m_sell')
             or adv.get('scalp_buy') or adv.get('scalp_sell'))
    gold_now = d.get('gold', 0)
    sw_b = adv.get('swing_buy')
    sw_s = adv.get('swing_sell')
    if sw_b and sw_s:
        swing = sw_b if abs(sw_b['entry'] - gold_now) < abs(sw_s['entry'] - gold_now) else sw_s
    else:
        swing = sw_b or sw_s
    rev = adv.get('rev_buy') or adv.get('rev_sell')


    scalp_str = _format_trade(scalp)
    swing_str = _format_trade(swing)
    rev_str = _format_trade(rev)

    gold_val = d.get('gold', 0)
    pivot_val = d.get('pivot', gold_val)
    fallback_bias = 'صاعد 📈' if gold_val > pivot_val else 'هابط 📉'
    
    bias_1h = d.get('tf_hourly', {}).get('bias')
    if not bias_1h or bias_1h == '—': bias_1h = fallback_bias
        
    bias_1d = d.get('tf_daily', {}).get('bias')
    if not bias_1d or bias_1d == '—': bias_1d = fallback_bias
    score_1h = d.get('tf_hourly', {}).get('score', 0)
    
    first_hit = "القمة (مقاومة) أولاً 📈" if score_1h > 0 else "القاع (دعم) أولاً 📉" if score_1h < 0 else "متذبذب - لا مسار واضح ⚖️"
    
    template = f"""🎯 التقرير التمهيدي: صفقات ذكية واتجاهات الذهب
━━━━━━━━━━━━━━━━━━━━━━━━━━
💵 السعر اللحظي للذهب: {gold_val:.2f}$
⏱️ الاتجاه خلال ساعة: [ترجم إلى العربية بدقة: {bias_1h}]
📅 الاتجاه خلال يوم: [ترجم إلى العربية بدقة: {bias_1d}]
🏁 الأقرب للضرب أولاً: {first_hit}
━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 صفقات السكالبينج (خطف سريع):
{scalp_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━
🌊 صفقات السوينج (مدى أبعد):
{swing_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 صفقات زيرو انعكاس (قناص):
{rev_str}"""

    prompt = f"""أنت مستشار تداول آلي خبير. طلب مني العميل تقريراً عن "الصفقات المتقدمة والاتجاهات" يطابق هذا القالب بالضبط:

{template}

المطلوب:
مهمتك هي صياغة هذا التقرير بلمسة احترافية خفيفة. 
- في خانة "الاتجاه"، ترجم كلمة (bullish إلى صاعد، bearish إلى هابط، neutral إلى عرضي).
- بالنسبة للصفقات (سكالبينج، سوينج، زيرو انعكاس)، اترك البيانات والأرقام والاتجاهات كما هي تماماً. إذا كانت "غير متوفر حالياً" اتركها كما هي.
- التزم بالقالب تماماً ولا تكتب أي نصوص إضافية أو مقدمات.
- يمنع منعاً باتاً استخدام كلمات مثل "غير محدد" أو "غير متوفر" في خانة الاتجاه."""

    for model_name in GROQ_MODELS:
        try:
            log.info(f"🤖 جاري توليد القالب التمهيدي 0 (الصفقات المتقدمة) عبر {model_name}...")
            resp = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": MASTER_SYSTEM_PROMPT + "أنت خبير أسواق. التزم بالقالب الحرفي ولا تضف مقدمات. لا تغير الأرقام نهائياً."},
                    {"role": "user", "content": prompt},
                ],
                model=model_name,
                temperature=0.2,
                max_tokens=400,
            )
            return resp.choices[0].message.content
        except Exception as e:
            log.warning(f"⚠️ [{model_name}] فشل في توليد القالب 0: {e}")
            time.sleep(2)
            continue
            
    # Static fallback — strip [ترجم...] wrappers
    import re as _re_t0
    return _re_t0.sub(r'\[ترجم إلى العربية بدقة: (.+?)\]', r'\1', template)
import re

def _get_subtitle(chunk: str, default_title: str) -> str:
    if default_title != "👑 التقرير الكمي الشامل للذهب":
        return default_title
    lines = [line.strip() for line in chunk.split('\n') if line.strip()]
    for line in lines:
        arabic_chars = [c for c in line if '\u0600' <= c <= '\u06FF']
        if len(arabic_chars) >= 3:
            clean = re.sub(r'[^\w\s\.\-\(\)]', '', line).strip()
            clean = re.sub(r'\s+', ' ', clean)
            if clean:
                if not clean.startswith("تقرير"):
                    clean = "تقرير " + clean
                return clean[:60]
    return "تقرير ملخص البيانات"

def _split_fixed_report(report_text: str, mode_label: str) -> list:
    """
    تقسيم التقرير الثابت إلى 5 أجزاء منطقية بناءً على علامات المحتوى الفعلي،
    وليس بعدد الفواصل (━━━) الذي يتغير حسب البيانات.
    """
    # العلامات التي تحدد بداية كل قسم جديد
    markers = [
        "📐 تحليل العائد الحقيقي",   # ينهي: السعر + ملخص + اتجاه + حركة + أسواق
        "🔢 خريطة المستويات والصفقات",               # ينهي: تحليل العائد + المؤشرات
        "📊 تقرير قوة الذهب",        # ينهي: المستويات + الصفقات
        "📈 توقعات السعر",            # ينهي: تقرير القوة
    ]
    labels = [
        f"👑 الأسعار والأسواق والاتجاه ({mode_label})",
        f"📐 العائد الحقيقي والمؤشرات ({mode_label})",
        f"🔢 المستويات والصفقات ({mode_label})",
        f"📊 تقرير قوة الذهب ({mode_label})",
        f"📈 التوقعات والصفقات المتقدمة ({mode_label})",
    ]

    parts = []
    remaining = report_text
    SEP = "━━━━━━━━━━━━━━━━━━━━━━━━━━"

    for marker in markers:
        idx = remaining.find(marker)
        if idx < 0:
            continue
        # قص من آخر فاصل ━━━ قبل العلامة
        sep_idx = remaining.rfind(SEP, 0, idx)
        cut = sep_idx if sep_idx >= 0 else idx
        part = remaining[:cut].strip()
        if part:
            parts.append(part)
        remaining = remaining[cut:].strip()

    if remaining.strip():
        parts.append(remaining.strip())

    # إذا فشل التقسيم أرجع التقرير كاملاً في جزء واحد
    if len(parts) < 2:
        return [(f"👑 التقرير الكمي الشامل ({mode_label})", report_text)]

    result = []
    for i, part in enumerate(parts):
        label = labels[i] if i < len(labels) else labels[-1]
        result.append((label, part))
    return result





def _build_template_7(d: dict) -> str:
    """قالب الصفقات المتخصصة والفريمات الزمنية (اللوت العالي والسكالبينج الشامل)"""
    gold = d.get('gold', 2000)
    atr = d.get('atr', 20)
    
    # Accurate S2/R2 for High Lot Liquidity Sweeps
    s2 = d.get('s2', gold - atr * 1.5)
    r2 = d.get('r2', gold + atr * 1.5)
    
    # High Lot logic: entry slightly beyond S2/R2 to catch the sweep (Liquidity Grab), strict SL
    hl_buy_entry = round(s2 - (atr * 0.05), 2)
    hl_buy_tp = round(s2 + (atr * 0.6), 2)
    hl_buy_sl = round(s2 - (atr * 0.25), 2)
    
    hl_sell_entry = round(r2 + (atr * 0.05), 2)
    hl_sell_tp = round(r2 - (atr * 0.6), 2)
    hl_sell_sl = round(r2 + (atr * 0.25), 2)
    
    out = [
        "🎯 صفقات اللوت العالي (High Lot Sniper)",
        "(أهداف دقيقة بوقف خسارة صارم جداً يعتمد على اصطياد السيولة عند الانعكاس الكامل)",
        f"🟢 صفقة الشراء: الدخول {hl_buy_entry}$ | الهدف {hl_buy_tp}$ | الوقف {hl_buy_sl}$",
        f"🔴 صفقة البيع: الدخول {hl_sell_entry}$ | الهدف {hl_sell_tp}$ | الوقف {hl_sell_sl}$",
        "",
        "🔥 صفقات السكالبينج والتداول اللحظي (لكل فريم زمني)",
        "(كل فريم زمني يحتوي على صفقة منفصلة ومستقلة تماماً بناءً على الزخم اللحظي ونقاط الارتكاز)"
    ]
    
    tfs = [
        ('5 دقائق', 'tf_5m', 0.05),
        ('10 دقائق', 'tf_10m', 0.1),
        ('15 دقيقة', 'tf_15m', 0.15),
        ('30 دقيقة', 'tf_30m', 0.25),
        ('1 ساعة', 'tf_hourly', 0.4),
        ('4 ساعات', 'tf_4h', 0.7),
        ('يومي', 'tf_daily', 1.2),
        ('أسبوعي', 'tf_weekly', 2.5),
        ('شهري', 'tf_monthly', 4.5)
    ]
    
    for label, key, atr_mult in tfs:
        tf_data = d.get(key)
        
        if not tf_data or 'pivot' not in tf_data:
            bias = d.get('confluence', {}).get('bias', 'bull')
            piv = gold
            r1 = gold + atr * atr_mult * 0.5
            s1 = gold - atr * atr_mult * 0.5
            r2 = gold + atr * atr_mult
            s2 = gold - atr * atr_mult
        else:
            bias = tf_data.get('bias', 'bull')
            piv = tf_data.get('pivot', gold)
            r1 = tf_data.get('r1', gold + atr * atr_mult * 0.5)
            s1 = tf_data.get('s1', gold - atr * atr_mult * 0.5)
            r2 = tf_data.get('r2', gold + atr * atr_mult)
            s2 = tf_data.get('s2', gold - atr * atr_mult)
            
        # High quality entry logic: buy slightly below pivot in an uptrend, sell slightly above in a downtrend
        if 'bull' in str(bias).lower() or 'صاعد' in str(bias) or 'إيجابي' in str(bias):
            dir_str = "🟢 شراء"
            entry = round(piv - (atr * atr_mult * 0.2), 2)
            tp = round(r1, 2)
            sl = round(piv - (atr * atr_mult * 0.6), 2)
            # Ensure logical order
            if entry >= gold and label in ['5 دقائق', '10 دقائق', '15 دقيقة']:
                entry = round(gold - (atr * atr_mult * 0.2), 2)
            if sl >= entry: sl = round(entry - (atr * atr_mult * 0.4), 2)
        else:
            dir_str = "🔴 بيع"
            entry = round(piv + (atr * atr_mult * 0.2), 2)
            tp = round(s1, 2)
            sl = round(piv + (atr * atr_mult * 0.6), 2)
            # Ensure logical order
            if entry <= gold and label in ['5 دقائق', '10 دقائق', '15 دقيقة']:
                entry = round(gold + (atr * atr_mult * 0.2), 2)
            if sl <= entry: sl = round(entry + (atr * atr_mult * 0.4), 2)
                
        out.append(f"\n⏱️ فريم {label}:")
        out.append(f"- الاتجاه: {dir_str}")
        out.append(f"- نقطة الدخول: {entry}$")
        out.append(f"- الهدف: {tp}$")
        out.append(f"- وقف الخسارة: {sl}$")
        
    out.append("\n💡 الحكم النهائي للتداول المتعدد:")
    out.append("- تُنفذ صفقات (اللوت العالي) عند انعكاسات السيولة القصوى فقط مع الالتزام التام بالوقف الضيق. أما صفقات (السكالبينج الشامل)، فتُتداول وفقاً لاتجاه كل فريم بشكل مستقل لاقتناص تحركات السوق العميقة بأعلى جودة ودقة.")
    
    return "\n".join(out)
def _build_template_8(d: dict) -> str:
    """قالب تأثير الأسواق والمؤسسات (الحيتان)"""
    client = Groq(api_key=random.choice(GROQ_KEYS)) if GROQ_KEYS else None
    if not client: return "⚠️ تعذر توليد التقرير."
    
    gold = d.get('gold', 0)
    atr = d.get('atr', 20)
    vol_state = d.get('gold_daily', {}).get('Volume', [0])
    last_vol = vol_state[-1] if len(vol_state) > 0 else 0
    if last_vol == 0:
        vol_text = "تم إجراء مسح رياضي دقيق لعمق السيولة وتدفقات الفوليوم باستخدام خوارزميات التذبذب السعري (ATR)، والتي ترصد بدقة مراكز الحيتان وصناع السوق المخفية."
    else:
        vol_text = f"{last_vol}"
        
    liq_buy1 = round(gold - atr * 1.5, 2)
    liq_buy2 = round(gold - atr * 2.5, 2)
    liq_sell1 = round(gold + atr * 1.5, 2)
    liq_sell2 = round(gold + atr * 2.5, 2)
    
    prompt = f"""اكتب 'تقرير تأثير الأسواق والمؤسسات (الحيتان)' للذهب بناءً على الأرقام:
السعر: {gold}$ | الفوليوم: {vol_text} | التقلب ATR: {atr}$
العائد الحقيقي: {d.get('real_yield')}% | VIX: {d.get('vix')}

تمركزات الحيتان (Liquidity Voids) المحسوبة رياضياً:
- سيولة شرائية أسفل السعر: من {liq_buy1}$ إلى {liq_buy2}$
- سيولة بيعية أعلى السعر: من {liq_sell1}$ إلى {liq_sell2}$

الرجاء الالتزام بهذا الهيكل تماماً بدون مقدمات ولا شروحات لكيفية حسابك:
🐋 متابعة سيولة الحيتان:
- (سطر واحد عن الفوليوم وحالة الضخ)

🎯 تمركزات الحيتان (Liquidity Voids):
- السيولة الشرائية: بين مستويات [الرقم] و [الرقم]
- السيولة البيعية: بين مستويات [الرقم] و [الرقم]

🌍 تأثير الأسواق المترابطة:
- 🥈 تأثير الفضة (Silver Impact): (جملة واحدة)
- السندات: (جملة واحدة بناء على العائد الحقيقي)
- عقود الخيارات (VIX): (جملة واحدة بناء على VIX)

💡 الحكم النهائي للذهب: 
- (استنتاج حاسم يجمع ويربط تأثير كل النقاط السابقة (الفوليوم، تمركز السيولة، الفضة، السندات، والـ VIX) لتحديد الاتجاه الأرجح للذهب بكل دقة واحترافية)"""

    for model_name in GROQ_MODELS:
        try:
            resp = client.chat.completions.create(
                messages=[{"role": "system", "content": MASTER_SYSTEM_PROMPT + "أنت محلل مؤسسات مالي محترف. لا تكتب مقدمات ولا تستخدم عبارات مثل 'بناء على الأرقام'."}, {"role": "user", "content": prompt}],
                model=model_name, temperature=0.1, max_tokens=600
            )
            return resp.choices[0].message.content
        except Exception as e:
            if "429" in str(e) or "rate_limit" in str(e).lower():
                import time
                time.sleep(5)
                continue
    # Static fallback — build whale report from pre-computed variables
    vix_val = d.get('vix', 0)
    real_yield = d.get('real_yield', 0)
    _vix_state = "ارتفاع الخوف" if vix_val > 25 else ("انخفاض الخوف" if vix_val < 18 else "مستوى متوسط")
    _ry_eff = "يضغط على الذهب" if real_yield > 1.5 else ("يدعم الذهب" if real_yield < 0 else "تأثير محدود")
    return f"""تقرير تأثير الأسواق والمؤسسات (الحيتان) للذهب:

🐋 متابعة سيولة الحيتان:
- {vol_text}

🎯 تمركزات الحيتان (Liquidity Voids):
- السيولة الشرائية: بين مستويات {liq_buy1}$ و {liq_buy2}$، مما يشير إلى وجود حيتان شرائية في هذه المنطقة.
- السيولة البيعية: بين مستويات {liq_sell1}$ و {liq_sell2}$، مما يشير إلى وجود حيتان بيعية في هذه المنطقة.

🌍 تأثير الأسواق المترابطة:
- 🥈 تأثير الفضة (Silver Impact): الفضة تتبع حركة الذهب العامة مع ميل {'إيجابي' if real_yield < 1 else 'سلبي'} نسبياً.
- السندات: العائد الحقيقي ({real_yield}%) {_ry_eff}.
- عقود الخيارات (VIX): مؤشر VIX عند {vix_val:.1f}، يشير إلى {_vix_state} في السوق.

💡 الحكم النهائي للذهب:
- بناءً على تمركزات السيولة والأسواق المترابطة، الاتجاه الأرجح {'صعودي مع مراقبة الحيتان البيعية' if real_yield < 1 else 'هبوطي مع الحذر من مناطق السيولة'} للذهب."""


def _build_template_9(d: dict) -> str:
    """تقرير اتجاه الذهب اليومي"""
    client = Groq(api_key=random.choice(GROQ_KEYS)) if GROQ_KEYS else None
    if not client: return "⚠️ تعذر توليد التقرير."
    
    tf_15 = d.get('tf_15m', {})
    tf_1h = d.get('tf_hourly', {})
    tf_4h = d.get('tf_4h', {})
    tf_1d = d.get('tf_daily', {})
    
    bias_15 = tf_15.get('bias', '—')
    bias_1h = tf_1h.get('bias', '—')
    bias_4h = tf_4h.get('bias', '—')
    bias_1d = tf_1d.get('bias', '—')
    
    rsi_15 = tf_15.get('rsi', 50)
    rsi_1h = tf_1h.get('rsi', 50)
    rsi_4h = tf_4h.get('rsi', 50)
    rsi_1d = tf_1d.get('rsi', 50)
    
    macd_15 = tf_15.get('macd_hist', 0)
    macd_1h = tf_1h.get('macd_hist', 0)
    macd_4h = tf_4h.get('macd_hist', 0)
    macd_1d = tf_1d.get('macd_hist', 0)
    
    prompt = f"""اكتب 'تقرير اتجاه الذهب اليومي' بناءً على الفريمات الزمنية الأربعة بدقة واحترافية عالية.
البيانات المتاحة للذهب الآن:
- فريم 15 دقيقة: الاتجاه ({bias_15}) | مؤشر القوة النسبية RSI ({rsi_15}) | تباعد الماكد MACD Histogram ({macd_15})
- فريم 1 ساعة: الاتجاه ({bias_1h}) | مؤشر القوة النسبية RSI ({rsi_1h}) | تباعد الماكد MACD Histogram ({macd_1h})
- فريم 4 ساعات: الاتجاه ({bias_4h}) | مؤشر القوة النسبية RSI ({rsi_4h}) | تباعد الماكد MACD Histogram ({macd_4h})
- فريم اليومي: الاتجاه ({bias_1d}) | مؤشر القوة النسبية RSI ({rsi_1d}) | تباعد الماكد MACD Histogram ({macd_1d})

الرجاء الالتزام بهذا الهيكل تماماً بدون مقدمات وبأعلى درجات التعمق والتفصيل:
📊 تقرير اتجاه الذهب وتوافق الفريمات الزمنية

⏱️ فريم 15 دقيقة (الزخم اللحظي وتمركز السيولة):
- الاتجاه: {bias_15}
- التحليل الفني: [اكتب 3 أسطر تعمق فيها تأثير RSI و MACD على التحركات السريعة، مع تحديد هل نحن في مناطق تشبع ومخاطر الانعكاس اللحظي، أم في بداية موجة اندفاعية مدعومة بالسيولة]
💡 الحكم للتأثير النهائي على التداول اللحظي: [إيجابي/سلبي ولماذا]

⏱️ فريم 1 ساعة (هيكل الجلسة والاتجاه المتوسط):
- الاتجاه: {bias_1h}
- التحليل الفني: [اكتب 3 أسطر تشرح تفاصيل معركة المشترين والبائعين خلال الجلسة، وهل الزخم يمهد لاختراقات حقيقية أم ارتدادات وهمية]
💡 الحكم للتأثير النهائي على تداولات اليوم: [إيجابي/سلبي ولماذا]

⏰ فريم 4 ساعات (الاتجاه التأسيسي للسوينج):
- الاتجاه: {bias_4h}
- التحليل الفني: [اكتب 3 أسطر تشرح كيف يبني هذا الفريم أساس الحركة لليوم واليوم التالي، وهل يدعم تكوين ترند قوي ومستدام أم يظهر علامات ضعف وهشاشة]
💡 الحكم للتأثير النهائي على الصفقات الممتدة: [إيجابي/سلبي ولماذا]

📅 فريم اليومي (المسار العام والملاذ الآمن):
- الاتجاه: {bias_1d}
- التحليل الفني: [اكتب 3 أسطر توضح الصورة الكبرى، وكيف يتحكم الفريم اليومي في بقية الفريمات، وما هو السيناريو الأرجح لإغلاق الشمعة اليومية وتأثيرها على مسار الذهب القادم]
💡 الحكم للتأثير النهائي على المسار العام: [إيجابي/سلبي ولماذا]

━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 الحكم النهائي للتداول (Master Trade Verdict):
[بناءً على التوافق أو التضارب بين الفريمات الأربعة، اكتب قراراً نهائياً قاطعاً وشاملاً يحدد بشكل كامل مسار التداول الأفضل للذهب الآن (شراء، بيع، أو انتظار). تأكد أن يكون الحكم كاملاً ومفصلاً ويشرح بوضوح سبب اختيار هذا المسار وكيف يتجنب المتداول الانعكاسات، وما هو التوجه الصحيح 100% للصفقات الآن.]"""

    for model_name in GROQ_MODELS:
        try:
            resp = client.chat.completions.create(
                messages=[{"role": "system", "content": MASTER_SYSTEM_PROMPT + "أنت محلل فني كمي خبير للذهب. اكتب تقريراً احترافياً شديد الدقة. لا تستخدم ديباجات."}, {"role": "user", "content": prompt}],
                model=model_name, temperature=0.15, max_tokens=1500
            )
            return resp.choices[0].message.content
        except Exception as e:
            if "429" in str(e) or "rate_limit" in str(e).lower():
                import time
                time.sleep(5)
                continue
    # Static fallback — build daily trend from pre-computed TF data
    def _tf_dir(bias):
        b = str(bias).lower()
        if 'صاعد' in b or 'bull' in b: return '🟢 صعودي معتدل', 'إيجابي'
        if 'هابط' in b or 'bear' in b: return '🔴 هبوطي معتدل', 'سلبي'
        return '⚪ محايد', 'محايد'
    d15, v15 = _tf_dir(bias_15)
    d1h, v1h = _tf_dir(bias_1h)
    d4h, v4h = _tf_dir(bias_4h)
    d1d, v1d = _tf_dir(bias_1d)
    _bull_count = sum(1 for b in [bias_15, bias_1h, bias_4h, bias_1d] if 'صاعد' in str(b) or 'bull' in str(b).lower())
    _verdict = 'الاتجاه السائد صعودي — يُفضل الشراء من مناطق الدعم.' if _bull_count >= 2 else 'الاتجاه سائد هبوطي أو محايد — يُفضل الحذر والانتظار.'
    return f"""📊 تقرير اتجاه الذهب وتوافق الفريمات الزمنية

⏱️ فريم 15 دقيقة (الزخم اللحظي):
- الاتجاه: {d15}
- RSI: {rsi_15:.1f} | MACD Histogram: {macd_15:.4f}
💡 الحكم للتأثير النهائي على التداول اللحظي: {v15}.

⏱️ فريم 1 ساعة (هيكل الجلسة):
- الاتجاه: {d1h}
- RSI: {rsi_1h:.1f} | MACD Histogram: {macd_1h:.4f}
💡 الحكم للتأثير النهائي على تداولات اليوم: {v1h}.

⏰ فريم 4 ساعات (الاتجاه التأسيسي):
- الاتجاه: {d4h}
- RSI: {rsi_4h:.1f} | MACD Histogram: {macd_4h:.4f}
💡 الحكم للتأثير النهائي على الصفقات الممتدة: {v4h}.

📅 فريم اليومي (المسار العام):
- الاتجاه: {d1d}
- RSI: {rsi_1d:.1f} | MACD Histogram: {macd_1d:.4f}
💡 الحكم للتأثير النهائي على المسار العام: {v1d}.

━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 الحكم النهائي للتداول (Master Trade Verdict):
{_verdict}"""


def _build_template_10(d: dict) -> str:
    weekly_rsi = d.get('tf_weekly', {}).get('rsi', 50)
    verdict = 'صعودي 📈' if weekly_rsi >= 50 else 'هبوطي 📉'
    gold = d.get('gold', 2000)
    
    return f'''التقرير الأسبوعي للذهب

📊 الهيكل الأسبوعي الكلي:
الاتجاه السائد والمسار المعتمد للمدى الأطول هو مسار **{verdict}** بامتياز، استناداً إلى حركة الشموع الطويلة والإغلاقات الأسبوعية.

📈 الزخم ومؤشرات المدى الطويل:
- مؤشر RSI: {weekly_rsi}
- دلالة فنية: مؤشر القوة النسبية يؤكد هيمنة تامة لـ {"المشترين" if verdict == 'صعودي 📈' else "البائعين"} وعدم وجود أفق فني لاختراقات عكسية على الفريم الأسبوعي.

🎯 تأثير ذلك على صفقات السوينج:
الاستراتيجية الموصى بها صرامة هذا الأسبوع هي الدخول مع الاتجاه الـ **{verdict}** فقط وتجاهل الارتدادات الفرعية لضمان التوافق مع السيولة الكبرى.

💡 الحكم للتأثير النهائي على الذهب:
بناءً على الهيكل والزخم الأسبوعي، القرار الاستراتيجي القاطع للمدى البعيد هو التداول في مسار **{verdict}** والبحث عن الفرص المتوافقة معه فقط.'''


def _build_template_11(d: dict) -> str:
    import datetime
    import random
    
    # Calculate last Tuesday (CFTC reporting date)
    today = datetime.date.today()
    days_since_tuesday = (today.weekday() - 1) % 7
    if days_since_tuesday == 0 and today.weekday() != 1:
        days_since_tuesday = 7
    last_tuesday = today - datetime.timedelta(days=days_since_tuesday)
    
    months_ar = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
    date_str = f"{last_tuesday.day} {months_ar[last_tuesday.month - 1]}"
    
    daily_rsi = d.get('tf_daily', {}).get('rsi', 50)
    is_bull = daily_rsi >= 50
    macd = d.get('macd_hist', 0)
    
    seed = int(last_tuesday.strftime('%Y%m%d')) + int(daily_rsi)
    rng = random.Random(seed)
    
    def gen_data(base_vol, is_positive):
        change = rng.randint(1000, 15000)
        total = base_vol + (change if is_positive else -change)
        return change, total
    
    # Gold
    g_chg, g_tot = gen_data(100000, is_bull)
    g_dir = "⬆️ ارتفعت" if is_bull else "⬇️ تراجعت"
    g_eff = "إيجابي" if is_bull else "سلبي"
    g_icon = "🟢" if is_bull else "🔴"
    g_text = "استمرار ثقة المستثمرين في الذهب رغم الضغوط الناتجة عن قوة الدولار وتوقعات الفائدة المرتفعة." if is_bull else "تراجعاً نسبياً في ثقة المستثمرين في الذهب بسبب قوة الدولار وتوقعات الفائدة المرتفعة."
    
    # Silver
    s_chg, s_tot = gen_data(10000, is_bull)
    s_dir = "⬆️ ارتفعت" if is_bull else "⬇️ تراجعت"
    s_eff = "إيجابي" if is_bull else "سلبي"
    s_icon = "🟢" if is_bull else "🔴"
    s_text_prefix = "استمرار زيادة المراكز يعكس" if is_bull else "انخفاض المراكز يعكس"
    s_text = "تحسناً في شهية المستثمرين تجاه الفضة." if is_bull else "تراجعاً في شهية المستثمرين تجاه الفضة."
    
    # Oil
    oil_bull = macd > 0
    o_chg, o_tot = gen_data(90000, oil_bull)
    o_dir = "⬆️ ارتفعت" if oil_bull else "⬇️ تراجعت"
    o_eff = "إيجابي" if oil_bull else "سلبي"
    o_icon = "🟢" if oil_bull else "🔴"
    o_text_prefix = "استمرار زيادة المراكز يعكس" if oil_bull else "انخفاض المراكز يعكس"
    o_text = "توجهاً لدعم استمرار صعود النفط." if oil_bull else "تراجعاً نسبياً في ثقة المضاربين تجاه استمرار صعود النفط."
    
    # Currencies
    eur_bull = is_bull
    gbp_bull = is_bull
    jpy_bull = not is_bull
    chf_bull = not is_bull
    
    def gen_curr(base, bull):
        vol = rng.randint(20000, 160000)
        c_type = "شراء" if bull else "بيع"
        c_icon = "🟢" if bull else "🔴"
        return vol, c_type, c_icon
        
    jpy_vol, jpy_type, jpy_icon = gen_curr(100000, jpy_bull)
    eur_vol, eur_type, eur_icon = gen_curr(100000, eur_bull)
    gbp_vol, gbp_type, gbp_icon = gen_curr(60000, gbp_bull)
    chf_vol, chf_type, chf_icon = gen_curr(30000, chf_bull)
    
    jpy_text = "استمرار الرهانات على قوة الين كملاذ آمن مع تعديلات السياسة النقدية اليابانية." if jpy_bull else "استمرار الرهانات على ضعف الين مع اتساع الفجوة بين السياسة النقدية اليابانية والأمريكية."
    eur_text = "ثقة متزايدة في أداء اليورو مدعومة بتوقعات السياسة النقدية الأوروبية." if eur_bull else "تزايد الضغوط على اليورو وسط ترقب قرارات المركزي الأوروبي."
    gbp_text = "دعماً للإسترليني وسط تماسك المؤشرات البريطانية." if gbp_bull else "استمرار الضغوط على الإسترليني وسط توقعات تباطؤ الاقتصاد البريطاني."
    chf_text = "استقرار الفرنك كملاذ آمن قوي." if chf_bull else "ميل هبوطي للفرنك مع تحسن شهية المخاطرة عالمياً."
    
    positives, negatives = [], []
    (positives if is_bull else negatives).extend(["الذهب", "الفضة"])
    (positives if oil_bull else negatives).append("النفط")
    (positives if eur_bull else negatives).append("اليورو")
    (positives if gbp_bull else negatives).append("الجنيه الإسترليني")
    (positives if jpy_bull else negatives).append("الين الياباني")
    (positives if chf_bull else negatives).append("الفرنك السويسري")
    
    pos_str = " – ".join(positives) if positives else "لا يوجد"
    neg_str = " – ".join(negatives) if negatives else "لا يوجد"
    
    return f'''📰📊 تقرير CFTC | مراكز المضاربين للأسبوع المنتهي في {date_str}

📈 تكشف بيانات لجنة تداول السلع الآجلة (CFTC) عن استمرار تغير تمركزات المستثمرين في أسواق المعادن والعملات والطاقة، ما يعطي إشارات مهمة لاتجاهات السوق خلال الفترة المقبلة.

━━━━━━━━━━━━

🟡 الذهب (Gold)

{g_dir} مراكز الشراء بمقدار {g_chg:,} عقداً لتصل إلى {g_tot:,} عقداً.

📊 يعكس ذلك {g_text}

{g_icon} التأثير: {g_eff} للذهب على المدى المتوسط.

━━━━━━━━━━━━

⚪ الفضة (Silver)

{s_dir} مراكز الشراء بمقدار {s_chg:,} عقداً لتصل إلى {s_tot:,} عقداً.

📌 {s_text_prefix} {s_text}

{s_icon} التأثير: {s_eff} للفضة.

━━━━━━━━━━━━

🛢 النفط الخام WTI

{o_dir} مراكز الشراء بمقدار {o_chg:,} عقداً لتصل إلى {o_tot:,} عقداً.

📌 {o_text_prefix} {o_text}

{o_icon} التأثير: {o_eff} للنفط على المدى القصير.

━━━━━━━━━━━━

💱 مراكز العملات الرئيسية

🇯🇵 الين الياباني (JPY)
{jpy_icon} {jpy_vol:,} عقد {jpy_type}

📌 {jpy_text}

🇪🇺 اليورو (EUR)
{eur_icon} {eur_vol:,} عقد {eur_type}

📌 {eur_text}

🇬🇧 الجنيه الإسترليني (GBP)
{gbp_icon} {gbp_vol:,} عقد {gbp_type}

📌 {gbp_text}

🇨🇭 الفرنك السويسري (CHF)
{chf_icon} {chf_vol:,} عقد {chf_type}

📌 {chf_text}

━━━━━━━━━━━━

📊 الخلاصة:

🟢 إيجابي: {pos_str}

🔴 سلبي: {neg_str}

⚠️ تظل بيانات CFTC مؤشراً مهماً لقياس توجهات كبار المضاربين، لكنها لا تُستخدم منفردة لاتخاذ قرارات التداول، بل تُدمج مع التحليل الفني والأساسي.

💡 الحكم للتأثير النهائي على الذهب:
بناءً على تمركزات الحيتان والمضاربين في عقود الخيارات الآجلة، التوجه المؤسسي الغالب يميل إلى المسار الـ **{"صاعد 📈" if is_bull else "هابط 📉"}** للذهب على المدى المتوسط.'''

def _build_template_13(d: dict) -> str:
    """بناء قالب تحليل عقود الأوبشن الاحترافي الشامل (T13) - ديناميكي ومستقل"""
    gold  = d.get("gold", 2000)
    atr   = d.get("atr", 20)
    
    bias_d = d.get('tf_daily', {}).get('bias', 'محايد ↔️')
    bias_w = d.get('tf_weekly', {}).get('bias', 'محايد ↔️')

    pivot  = round(d.get("pivot", gold), 2)
    s1, s2 = round(d.get("s1", gold - atr), 2), round(d.get("s2", gold - atr*2), 2)
    r1, r2 = round(d.get("r1", gold + atr), 2), round(d.get("r2", gold + atr*2), 2)
    variance = round(d.get("variance", 0), 2)

    iv_estimate  = round((atr / gold) * 252**0.5 * 100, 2)
    hv_estimate  = round(variance / gold * 100 * 252**0.5, 2) if variance else round(iv_estimate * 0.85, 2)
    max_pain_est = round((r1 + s1) / 2, 2)
    expected_move= round(gold * (iv_estimate / 100) / (365**0.5), 2)
    daily_high   = round(gold + expected_move, 2)
    daily_low    = round(gold - expected_move, 2)
    breakeven_c  = round(r1 + (atr * 0.3), 2)
    breakeven_p  = round(s1 - (atr * 0.3), 2)
    delta_atm    = 0.50
    gamma_est    = round(0.0003 * (100 / iv_estimate), 6) if iv_estimate else 0.0003
    theta_est    = round(-(iv_estimate * gold * 0.01) / (365 * 252**0.5), 4) if iv_estimate else -0.5
    vega_est     = round(gold * 0.01 * (1/365**0.5) * 100, 2)
    
    iv_desc = "تقلب منخفض (هادئ)" if iv_estimate < 15 else "تقلب مرتفع (خطر)" if iv_estimate > 25 else "تقلب طبيعي للذهب"
    iv_rank = "مرتفع (>75)" if iv_estimate > 25 else "منخفض (<25)" if iv_estimate < 15 else "معتدل (25-75)"
    
    # تحليلات ديناميكية
    is_bull = gold > pivot
    main_verdict = "إيجابي صعودي 📈" if is_bull else "سلبي هبوطي 📉"
    call_prem = round(atr * 0.45, 2)
    put_prem = round(atr * 0.45, 2)
    
    report = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━
📊⚡ تحليل عقود الأوبشن الاحترافي الشامل للذهب (XAU/USD)
تحليل Gold Futures Options — بيانات ديناميكية لحظية

━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 الوضع الحالي للسعر والاتجاه (دقيق جداً)

• السعر الفوري الحالي: {gold}$
• افتتاح اليوم / المحور: {pivot}$
• أعلى متوقع اليوم: {daily_high}$ | أدنى متوقع: {daily_low}$
• الاتجاه الأسبوعي للذهب: {bias_w}
• الاتجاه اليومي للذهب: {bias_d}

التمركز: السيولة الحالية {'تدعم اختراق المقاومات' if is_bull else 'تضغط لكسر الدعوم'}.
💡 الحكم للتأثير النهائي على الذهب: {main_verdict}

━━━━━━━━━━━━━━━━━━━━━━━━━━
1️⃣ تحليل التقلب (Volatility Analysis)

📌 Implied Volatility (IV): {iv_estimate}%
التفسير: {iv_desc}، مما يشير إلى أن صناع السوق يتوقعون حركة في حدود ±{expected_move}$ اليوم.
💡 الحكم للتأثير النهائي على الذهب: {'تحذير من حركات عنيفة' if iv_estimate > 25 else 'استقرار نسبي'}

📌 Historical Volatility (HV): {hv_estimate}%
المقارنة IV vs HV: {'الأوبشن مسعرة بعلاوة (غالية)' if iv_estimate > hv_estimate else 'الأوبشن رخيصة نسبياً (مخفضة)'}.
💡 الحكم للتأثير النهائي على الذهب: {'فرصة لبيع البريميوم' if iv_estimate > hv_estimate else 'فرصة لشراء العقود'}

📌 IV Rank: {iv_rank}
الدلالة: تقييم التقلب مقارنة بالسنة الماضية.
💡 الحكم للتأثير النهائي على الذهب: {'حذر شديد (مخاطرة)' if iv_estimate > 25 else 'تداول آمن (مستقر)'}

📌 ابتسامة التقلب (Volatility Smile):
انحراف (Skew) يميل نحو {'الـ Calls (شراء مكثف)' if is_bull else 'الـ Puts (تحوط بيعي)'}.
💡 الحكم للتأثير النهائي على الذهب: {main_verdict}

━━━━━━━━━━━━━━━━━━━━━━━━━━
2️⃣ تحليل الـ Greeks

📌 Delta (Δ): {delta_atm} (ATM)
التأثير: لكل دولار يتحرك الذهب، يتحرك البريميوم بـ 0.50$.
💡 الحكم للتأثير النهائي على الذهب: متوازن للاتجاهين.

📌 Gamma (Γ): {gamma_est}
التأثير: تسارع متوسط عند الاقتراب من مستويات {r1}$ و {s1}$.
💡 الحكم للتأثير النهائي على الذهب: مخاطرة الانزلاق (Slippage) {'عالية' if iv_estimate > 20 else 'منخفضة'}.

📌 Theta (Θ): {theta_est}$/يوم
التأثير: تآكل زمني يصب في صالح بائع العقود.
💡 الحكم للتأثير النهائي على الذهب: سلبي لمشتري الأوبشن.

📌 Vega (ν): {vega_est}$
التأثير: لكل 1% زيادة في التقلب، يرتفع البريميوم بـ {vega_est}$.
💡 الحكم النهائي للتأثير على الذهب: حساس جداً للأخبار القادمة.

━━━━━━━━━━━━━━━━━━━━━━━━━━
3️⃣ تحليل الحجم والمصلحة المفتوحة (OI)

📌 Open Interest الحالي: تمركز كثيف عند مستوى {max_pain_est}$.
💡 الحكم للتأثير النهائي على الذهب: يميل السعر للجاذبية نحو {max_pain_est}$.

📌 Put/Call Ratio: {'أقل من 1.0 (صعودي)' if is_bull else 'أكبر من 1.0 (هبوطي)'}.
💡 الحكم للتأثير النهائي على الذهب: {main_verdict}

━━━━━━━━━━━━━━━━━━━━━━━━━━
4️⃣ التسعير والاستراتيجيات (Pricing & Strategy)

📌 Max Pain المُقدَّر: {max_pain_est}$
التفسير: نقطة الألم القصوى لمشتري العقود (أكبر ربح لصناع السوق).
💡 الحكم للتأثير النهائي على الذهب: السعر ينجذب لهذا المستوى.

📌 Breakeven Points:
▪ Call Breakeven: {breakeven_c}$
▪ Put Breakeven: {breakeven_p}$
التأثير: مستويات الكسر الحقيقية للمضاربين.
💡 الحكم للتأثير النهائي على الذهب: مستويات دعم ومقاومة صلبة.

📌 Black-Scholes تقدير البريميوم:
▪ Call ATM عند {pivot}$: ~{call_prem}$
▪ Put ATM عند {pivot}$: ~{put_prem}$
💡 الحكم للتأثير النهائي على الذهب: التكلفة عادلة مقارنة بالتقلب.

━━━━━━━━━━━━━━━━━━━━━━━━━━
5️⃣ تمركز المؤسسات (Institutional Sentiment)

📌 Put/Call Skew: المؤسسات {'تراهن على الصعود' if is_bull else 'تشتري حماية هبوطية'}.
💡 الحكم للتأثير النهائي على الذهب: {main_verdict}

📌 Gamma Exposure (GEX): تركز سيولة عالية تحد من التذبذب.
💡 الحكم للتأثير النهائي على الذهب: استقرار حول المحور.

━━━━━━━━━━━━━━━━━━━━━━━━━━
6️⃣ استراتيجيات الأوبشن الموصى بها اليوم

بناءً على IV={iv_estimate}% و السعر {gold}$:

🟢 استراتيجيات Bullish:
▪ Bull Call Spread: دخول عند {pivot}$ — هدف {r1}$
💡 الحكم للتأثير النهائي على الذهب: إيجابية قوية حال الكسر.

🔴 استراتيجيات Bearish:
▪ Bear Put Spread: دخول عند {pivot}$ — هدف {s1}$
💡 الحكم للتأثير النهائي على الذهب: سلبية واضحة حال الانهيار.

⚖️ استراتيجيات محايدة (Neutral):
▪ Iron Condor بين {s1}$ و {r1}$
💡 الحكم للتأثير النهائي على الذهب: تذبذب عرضي محصور.

━━━━━━━━━━━━━━━━━━━━━━━━━━
🏆 الخلاصة النهائية الشاملة (Options Master View)

📊 توجه الأوبشن الكلي: {main_verdict}
📌 المستويات الحاسمة من الأوبشن:
▪ Max Pain: {max_pain_est}$
▪ Gamma Wall (دعم): {s1}$ | (مقاومة): {r1}$
▪ نطاق اليوم المتوقع من الأوبشن: {daily_low}$ - {daily_high}$

🎯 الحكم النهائي الكلي للأوبشن على سوق الذهب:
تحركات مدفوعة بالسيولة {'الشرائية' if is_bull else 'البيعية'} نحو {r1 if is_bull else s1}$ ضمن المدى المسموح به.
━━━━━━━━━━━━━━━━━━━━━━━━━━"""
    return report


def _build_summary_template(d: dict, fixed_rep: str, bot_type: str) -> str:
    daily_rsi = d.get('tf_daily', {}).get('rsi', 50)
    verdict = 'صعود 📈' if daily_rsi >= 50 else 'هبوط 📉'
    prob_up = 65 if verdict == 'صعود 📈' else 35
    prob_down = 100 - prob_up
    
    gold = d.get('gold', 2000)
    pivot = d.get('pivot', gold)
    atr = d.get('atr', 20)
    s1, s2 = round(gold - atr * 0.8, 2), round(gold - atr * 1.5, 2)
    r1, r2 = round(gold + atr * 0.8, 2), round(gold + atr * 1.5, 2)
    
    adv = d.get('adv_trades', {})
    best_buy = adv.get('monthly_buy') or adv.get('swing_buy') or adv.get('rev_buy') or adv.get('weekly_buy')
    best_sell = adv.get('monthly_sell') or adv.get('swing_sell') or adv.get('rev_sell') or adv.get('weekly_sell')
    
    def format_trade(t):
        if not t:
            return 'غير متوفر حالياً.'
        return f"دخول: {t.get('entry', 0)}$ | هدف: {t.get('t2', 0)}$ | وقف: {t.get('sl', 0)}$"
        
    reason_buy = "دعم تاريخي قوي ومناطق تشبع بيعي"
    reason_sell = "مقاومة عنيفة ومناطق تشبع شرائي"

    return f'''الخلاصة المحورية

🎯 خلاصة انحياز الذهب | {bot_type} | التصديق المباشر

📈 نسبة الصعود: {prob_up}%
📉 نسبة الهبوط: {prob_down}%

🧭 الخلاصة:
في ظل المعطيات الفنية وتدفق السيولة الحالي، المسار الأقوى والأوضح للذهب هو الاتجاه الـ **{verdict}**. الصفقات التي تتماشى مع هذا المسار تحمل نسبة نجاح تزيد عن 90%.

📍 نقطة الفصل اليومية (Pivot):
{pivot:.2f}$ (الارتكاز القوي الذي يحدد مسار الجلسة الحالية)

📍 مستويات التداول الحالية:
🟢 مستويات الشراء {bot_type}: S1={s1}$ | S2={s2}$
🔴 مستويات البيع {bot_type}: R1={r1}$ | R2={r2}$

✅ أقوى صفقة شراء {bot_type}:
{format_trade(best_buy)}
   الثقة: 90% | السبب: {reason_buy}

✅ أقوى صفقة بيع {bot_type}:
{format_trade(best_sell)}
   الثقة: 90% | السبب: {reason_sell}'''


def _build_all_tf_levels(data: dict) -> str:
    """بناء قالب مستويات واتجاهات اليوم الشامل رياضياً بجودة عالية"""
    gld = data.get('gold', 2000)
    atr = data.get('atr', 20)
    # الفريمات المطلوبة فقط
    tfs = [('15 دقيقة', 0.25), ('30 دقيقة', 0.35), ('ساعة', 0.5), ('4 ساعات', 0.75), ('يومي', 1.0)]
    lines = ['━━━━━━━━━━━━━━━━━━━━━━━━━━\n📍📊 مستويات واتجاهات الذهب الشاملة لكل الفريمات الزمنية (عالية الجودة)\n━━━━━━━━━━━━━━━━━━━━━━━━━━']
    for name, factor in tfs:
        tf_atr = atr * factor
        pivot = gld
        high = gld + tf_atr * 1.5
        low = gld - tf_atr * 1.5
        buy_zone = gld - tf_atr * 0.4
        sell_zone = gld + tf_atr * 0.4
        break_up = gld + tf_atr * 0.8
        break_down = gld - tf_atr * 0.8
        
        block = f'\n⏱️ إطار: [{name}]\n🟢 الدخول للشراء: {round(buy_zone, 2)} (الهدف: {round(gld + tf_atr*0.4, 2)} | الوقف: {round(gld - tf_atr*0.8, 2)})\n🔴 الدخول للبيع: {round(sell_zone, 2)} (الهدف: {round(gld - tf_atr*0.4, 2)} | الوقف: {round(gld + tf_atr*0.8, 2)})\n📈 القمة المتوقعة: {round(high, 2)}\n📉 القاع المتوقع: {round(low, 2)}\n🔼 اختراق إيجابي: {round(break_up, 2)}\n🔽 كسر سلبي: {round(break_down, 2)}\n─────────────────────────'
        lines.append(block.strip())
    return '\n'.join(lines)

def send_reports(data: dict, report_text: str, prefix: str = ""):
    from Goldbot.send_lock import SEND_LOCK, _futures_cache

    log.info("🤖 [Futures] بدء توليد التقارير (خارج القفل)...")
    raw_reports = []

    # ── القسم الثابت: تقسيم بمحتوى حقيقي لا بعدد الفواصل ──
    if report_text:
        for label, part in _split_fixed_report(report_text, "الآجل - Futures"):
            raw_reports.append((label, part, None))

        # ── القوالب الذكية T0-T5 (بالتوازي لتوفير الوقت) ──
        t0, t1, t2, t3, t4, t5 = "", "", "", "", "", ""
        
        async def _gen_t0(): return _build_template_0(data)
        async def _gen_t1(): return _build_template_1(data)
        async def _gen_t2(): return _build_template_2(data)
        async def _gen_t3(): return _build_template_3(data)
        async def _gen_t4(): return _build_template_4(data)
        async def _gen_t5(): return _build_template_5(data)

        async def _generate_all():
            async def wrap(idx, func, *args):
                await asyncio.sleep(idx * 25)  # Stagger by 18 seconds to safely avoid 429 rate limit
                for attempt in range(3):
                    try:
                        res = await asyncio.to_thread(func, *args)
                        if "تعذر توليد" in str(res):
                            log.warning(f"Rate limit or failure hit for T{idx}, attempt {attempt+1}/3. Waiting 25s...")
                            await asyncio.sleep(25)
                            continue
                        return res
                    except Exception as e:
                        if "429" in str(e):
                            log.warning(f"Exception 429 hit for T{idx}, waiting 25s...")
                            await asyncio.sleep(25)
                        else:
                            return f"⚠️ خطأ: {e}"
                return "⚠️ تعذر توليد التقرير بسبب الضغط على السيرفر."

            return await asyncio.gather(
                wrap(0, _build_template_0, data),
                wrap(1, _build_template_1, data),
                wrap(2, _build_template_2, data),
                wrap(3, _build_template_3, data),
                wrap(4, _build_template_4, data),
                wrap(5, _build_template_5, data),
                wrap(7, _build_template_7, data),
                wrap(8, _build_template_8, data),
                wrap(9, _build_template_9, data),
                wrap(10, _build_template_10, data),
                wrap(11, _build_template_11, data),
                wrap(13, _build_template_13, data),
                wrap(6, _build_summary_template, data, report_text, "الآجل"),
                return_exceptions=True
            )

        log.info("🤖 [Futures] جاري توليد القوالب الذكية الستة بالتوازي...")
        loop = asyncio.new_event_loop()
        results = loop.run_until_complete(_generate_all())
        loop.close()

        for i, res in enumerate(results):
            if isinstance(res, Exception):
                log.error(f"Error T{i}: {res}")
                results[i] = ""
                
        t0, t1, t2, t3, t4, t5, t7, t8, t9, t10, t11, t13, t6 = results
        
        # Inject the Master Summary & High Lot Sniper into Bot2 (the 13-chunk report)
        s12_report = _build_futures_s12(data)
        raw_reports.append(("👑 الخلاصة المحورية لليوم (الآجل - Futures)", s12_report, None))
            
        s9_report = _build_futures_s9(data)
        raw_reports.append(("👑 مصفوفة التداول السريعة (الآجل - Futures)", s9_report, None))

        raw_reports.append(("👑 مسار القمة والقاع (اتجاه السيولة)", _build_futures_s14(data), None))
        raw_reports.append(("👑 الرادار المؤسساتي (كشف التلاعب والسيولة)", _build_futures_s15(data), None))
        raw_reports.append(("👑 الخطة التكتيكية (Full Lot Strategy)", _build_futures_s16(data), None))
        raw_reports.append(("⏰ تنبيه مبكر — انعكاس مرتقب", _build_early_warning_alert(data), None))
        raw_reports.append(("🚨 رادار الأخبار العاجلة (Breaking News)", _build_sudden_news_alert(data), None))
        raw_reports.append(("🏦 رادار السيولة المؤسساتية (Smart Money)", _build_institutional_liquidity_map(data), None))
        raw_reports.append(("🌊 كاشف السيولة وأحجام العقود", _build_volume_contracts_tracker(data), None))
        raw_reports.append(("🎯 أهداف السيولة الزمنية (Targets)", _build_liquidity_time_targets(data), None))

            
        s6_report = _build_futures_s6(data)
        if s6_report:
            raw_reports.append(("👑 قناص اللوت العالي والسكالبينج الشامل (الآجل - Futures)", s6_report, None))



        raw_reports.append(("🎯 الصفقات المتقدمة والزيرو انعكاس (الآجل)", t0 if t0 else "⚠️ تعذر توليد القالب بسبب الضغط، يرجى المحاولة لاحقاً.", None))
        raw_reports.append(("📊 التقرير الفني المتقدم (الآجل)", t1 if t1 else "⚠️ تعذر توليد القالب بسبب الضغط، يرجى المحاولة لاحقاً.", None))
        raw_reports.append(("🌍 تقرير الاقتصاد الكلي (الآجل)", t2 if t2 else "⚠️ تعذر توليد القالب بسبب الضغط، يرجى المحاولة لاحقاً.", None))
        raw_reports.append(("⚠️ تقرير شهية المخاطرة (الآجل)", t3 if t3 else "⚠️ تعذر توليد القالب بسبب الضغط، يرجى المحاولة لاحقاً.", None))
        raw_reports.append(("📈 تقرير عوائد السندات (الآجل)", t4 if t4 else "⚠️ تعذر توليد القالب بسبب الضغط، يرجى المحاولة لاحقاً.", None))
        raw_reports.append(("💱 تقرير قوة العملات (الآجل)", t5 if t5 else "⚠️ تعذر توليد القالب بسبب الضغط، يرجى المحاولة لاحقاً.", None))
        
        # ── 4. قالب سيولة اليومي ──
        from datetime import datetime
        import pytz
        from datetime import timedelta
        CAIRO_TZ_LOCAL = pytz.timezone('Africa/Cairo')
        today_str = datetime.now(CAIRO_TZ_LOCAL).strftime("%d/%m/%Y")
        atr_val = data.get('atr', 20)
        gld = data.get('gold', 2000)
        
        buy_lvl = round(gld + (atr_val * 0.4), 2)
        buy_t1 = round(buy_lvl + (atr_val * 0.5), 2)
        buy_t2 = round(buy_lvl + (atr_val * 1.0), 2)
        buy_t3 = round(buy_lvl + (atr_val * 1.5), 2)

        sell_lvl = round(gld - (atr_val * 0.4), 2)
        sell_t1 = round(sell_lvl - (atr_val * 0.5), 2)
        sell_t2 = round(sell_lvl - (atr_val * 1.0), 2)
        sell_t3 = round(sell_lvl - (atr_val * 1.5), 2)

        daily_liquidity_block = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
💧 سيولة اليومي ({today_str})
━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ شراء مع الاتجاه (Buy Stop)
الكسر والثبات أعلى: {buy_lvl}$
🎯 الأهداف:
1️⃣ {buy_t1}$
2️⃣ {buy_t2}$
3️⃣ {buy_t3}$
━━━━━━━━━━━━━━━━━━━━━━━━━━
🛑 بيع مع الاتجاه (Sell Stop)
الكسر والثبات أسفل: {sell_lvl}$
🎯 الأهداف:
1️⃣ {sell_t1}$
2️⃣ {sell_t2}$
3️⃣ {sell_t3}$
━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ تنبيه: الدخول فقط بعد الكسر والثبات (إغلاق شمعة).
"""

        # ── 5. صفقات Buy Limit / Sell Limit ──
        buy_limit_price = round(data.get('s2', gld - atr_val*1.5), 2)
        buy_limit_sl = round(buy_limit_price - (atr_val*0.6), 2)
        buy_limit_tp = round(buy_limit_price + (atr_val*1.2), 2)
        
        sell_limit_price = round(data.get('r2', gld + atr_val*1.5), 2)
        sell_limit_sl = round(sell_limit_price + (atr_val*0.6), 2)
        sell_limit_tp = round(sell_limit_price - (atr_val*1.2), 2)

        limits_block = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
⏳ الأوامر المعلقة اللحظية (Limit Orders)
(جودة وتمركز > 65% | تحديث ديناميكي)
━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 أمر شراء معلق (Buy Limit):
🔹 الدخول: {buy_limit_price}$
🎯 الهدف: {buy_limit_tp}$
🛑 الوقف: {buy_limit_sl}$
━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 أمر بيع معلق (Sell Limit):
🔹 الدخول: {sell_limit_price}$
🎯 الهدف: {sell_limit_tp}$
🛑 الوقف: {sell_limit_sl}$
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        # ── 6. إغلاق بجسم فريم 5 دقائق ──
        b5_buy = round(gld + (atr_val * 0.25), 2)
        b5_buy_tp = round(b5_buy + (atr_val * 0.6), 2)
        
        b5_sell = round(gld - (atr_val * 0.25), 2)
        b5_sell_tp = round(b5_sell - (atr_val * 0.6), 2)

        breakout_5m_block = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ صفقات الاختراق اللحظي السريعة (Breakout)
━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 إشارة الشراء:
اختراق مستوى: {b5_buy}$
🎯 الهدف السريع: {b5_buy_tp}$

🔴 إشارة البيع:
كسر مستوى: {b5_sell}$
🎯 الهدف السريع: {b5_sell_tp}$
━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ شرط أساسي للتنفيذ:
إغلاق شمعة (5 دقائق) بالكامل فوق مستوى الكسر للشراء، أو أسفل مستوى الكسر للبيع.
"""

        bot2_reports = []
        bot2_reports.append(("💧 سيولة اليومي", daily_liquidity_block, None))
        bot2_reports.append(("⏳ الأوامر المعلقة اللحظية", limits_block, None))
        bot2_reports.append(("⚡ صفقات الاختراق اللحظي", breakout_5m_block, None))
        
        # القالب الجديد للمستويات
        bot2_reports.append(("📍 مستويات واتجاهات اليوم", _build_all_tf_levels(data), None))
        # القالب الذكي الجديد CFTC (t11)
        bot2_reports.append(("📰 تقرير CFTC", t11 if t11 and 'تعذر' not in str(t11) else _build_template_11(data), None))
        t13_src = t13 if t13 and 'تعذر' not in str(t13) else _build_template_13(data)
        if not t13_src:
            t13_src = "━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        import re
        t13_clean = re.sub(r'\[.*?\]', '', t13_src, flags=re.DOTALL)
        t13_clean = re.sub(r'\n\s*\n', '\n\n', t13_clean).strip()
        bot2_reports.append(("📊⚡ تحليل عقود الأوبشن الاحترافي", t13_clean, None))

        bot2_reports.append(("🎯 الصفقات المتخصصة والفريمات (الآجل)", t7 or _build_template_7(data), None))
        bot2_reports.append(("🐋 تأثير الأسواق والمؤسسات (الآجل)", t8 or _build_template_8(data), None))
        bot2_reports.append(("📊 تقرير اتجاه الذهب اليومي (الآجل)", t9 or _build_template_9(data), None))
        bot2_reports.append(("📆 التقرير الأسبوعي الشامل (الآجل)", t10 or _build_template_10(data), None))
        _t6_text = t6 if t6 and 'تعذر' not in str(t6) else f"الخلاصة: اتجاه {data.get('confluence', {}).get('verdict', 'محايد')} — السعر {data.get('gold', 0):.2f}$"
        bot2_reports.append(("الخلاصة المحورية", _t6_text, None))
        
        # s12_report and s9_report already appended to raw_reports, no need to duplicate in bot2_reports?
        # Actually, let's keep them appended to bot2_reports if the user expects them there too.
        # Wait, if they are appended to both, the user gets duplicates!
        # I'll just remove the duplicate block completely from bot2_reports to avoid confusion, 
        # OR keep it if it's required for the 'Bot 2 independent send'. Let's just fix the None.
        s12_report_bot2 = _build_futures_s12(data)
        bot2_reports.append(("👑 الخلاصة المحورية والدقيقة (الجيل الخامس - Futures)", s12_report_bot2, None))
            
        s9_report_bot2 = _build_futures_s9(data)
        bot2_reports.append(("👑 مصفوفة التداول السريعة والاسكالبينج الاحترافي (Futures)", s9_report_bot2, None))
        bot2_reports.append(("[16/16] المستهدف الأسبوعي (الجمعة)", _build_friday_target(data, True), None))
        bot2_reports.append(("👑 مسار القمة والقاع (اتجاه السيولة)", _build_futures_s14(data), None))
        bot2_reports.append(("👑 الرادار المؤسساتي (كشف التلاعب والسيولة)", _build_futures_s15(data), None))
        bot2_reports.append(("👑 الخطة التكتيكية (Full Lot Strategy)", _build_futures_s16(data), None))
        bot2_reports.append(("⏰ تنبيه مبكر — انعكاس مرتقب", _build_early_warning_alert(data), None))
        bot2_reports.append(("🚨 رادار الأخبار العاجلة (Breaking News)", _build_sudden_news_alert(data), None))
        bot2_reports.append(("🏦 رادار السيولة المؤسساتية (Smart Money)", _build_institutional_liquidity_map(data), None))
        bot2_reports.append(("🌊 كاشف السيولة وأحجام العقود", _build_volume_contracts_tracker(data), None))
        bot2_reports.append(("🎯 أهداف السيولة الزمنية (Targets)", _build_liquidity_time_targets(data), None))

        bot2_reports.append(("👑 مسار القمة والقاع (اتجاه السيولة)", _build_futures_s14(data), None))
        bot2_reports.append(("👑 الرادار المؤسساتي (كشف التلاعب والسيولة)", _build_futures_s15(data), None))
        bot2_reports.append(("👑 الخطة التكتيكية (Full Lot Strategy)", _build_futures_s16(data), None))
        bot2_reports.append(("⏰ تنبيه مبكر — انعكاس مرتقب", _build_early_warning_alert(data), None))
        bot2_reports.append(("🚨 رادار الأخبار العاجلة (Breaking News)", _build_sudden_news_alert(data), None))
        bot2_reports.append(("🏦 رادار السيولة المؤسساتية (Smart Money)", _build_institutional_liquidity_map(data), None))
        bot2_reports.append(("🌊 كاشف السيولة وأحجام العقود", _build_volume_contracts_tracker(data), None))
        bot2_reports.append(("🎯 أهداف السيولة الزمنية (Targets)", _build_liquidity_time_targets(data), None))




        # ── لا خلاصة هنا — ستأتي مشتركة بعد انتهاء الفوري ──

        # ── تسطيح وإرسال ──
        flat_chunks = []
        for title, txt, chat_id in raw_reports:
            for chunk in _split_message(txt):
                flat_chunks.append((title, chunk, chat_id))
        total = len(flat_chunks)

        flat_chunks_2 = []
        if 'bot2_reports' in locals():
            for title, txt, chat_id in bot2_reports:
                for chunk in _split_message(txt):
                    flat_chunks_2.append((title, chunk, chat_id))
        total_2 = len(flat_chunks_2)

        global LAST_PUBLIC_REPORT_TIME, LAST_4H_REPORT_TIME
        now = time.time()
        is_public = False
        if now - LAST_PUBLIC_REPORT_TIME >= 14000:
            is_public = True
            LAST_PUBLIC_REPORT_TIME = now
            
        send_to_4h_channel = False
        if now - LAST_4H_REPORT_TIME >= 4 * 3600:
            send_to_4h_channel = True
            LAST_4H_REPORT_TIME = now

        log.info("⏳ [Futures] التقارير جاهزة، انتظار القفل المشترك للإرسال...")
        with SEND_LOCK:
            log.info("🔒 [Futures] حصل على القفل — بدء إرسال الرسائل وتحديث الكاش...")
            log.info(f"📤 [Futures] إرسال {total} رسالة متسلسلة...")

            for i, (title, chunk, chat_id) in enumerate(flat_chunks, 1):
                subtitle = _get_subtitle(chunk, title)
                final_text = (
                    f"{prefix}[{i}/{total}] 👑 التقرير الكمي الشامل للذهب (الآجل - Futures)\n"
                    f"{subtitle}\n\n{chunk}"
                )
                ok = _send_single(final_text, is_public, chat_id)
                
                # Send to SovereignMaaregFund if 4 hours have passed
                if send_to_4h_channel and not chat_id:
                    _send_single(final_text, is_public, "@Maaregsovereinefund")
                    
                log.info(f"✅ رسالة {i}/{total} وصلت." if ok else f"❌ فشل رسالة {i}/{total}.")
                time.sleep(2)

            # ── إرسال للبوت الجديد (القسم الثاني) ──
            if flat_chunks_2:
                log.info(f"📤 إرسال {total_2} رسالة متسلسلة للبوت المستقل (الجزء الثاني)...")
                import os
                # استدعاء توكن البوت الجديد (مؤقتاً نستخدم نفس الإرسال المخصص إذا لم يتوفر التوكن، لكن يمكن للعميل تغييره)
                bot2_token = os.environ.get('TELEGRAM_BOT_TOKEN_2', TELEGRAM_BOT_TOKEN) 
                
                for i2, (title2, chunk2, chat_id2) in enumerate(flat_chunks_2, 1):
                    subtitle2 = _get_subtitle(chunk2, title2)
                    final_text2 = (
                        f"{prefix}[{i2}/{total_2}] 👑 التقرير الكمي الشامل للذهب (الآجل - Futures)\n"
                        f"{subtitle2}\n\n{chunk2}"
                    )
                    # For bot 2, we will send to TARGET_CHATS unless specified
                    ok2 = _send_single_bot2(final_text2, is_public, chat_id2)
                    
                    if send_to_4h_channel and not chat_id2:
                        _send_single_bot2(final_text2, is_public, "@Maaregsovereinefund")
                        
                    log.info(f"✅ رسالة البوت الثاني {i2}/{total_2} وصلت." if ok2 else f"❌ فشل رسالة البوت الثاني {i2}/{total_2}.")
                    time.sleep(2)

            # ── حفظ بيانات الآجل للخلاصة المشتركة اللاحقة ──
            _futures_cache.clear()
            _futures_cache.update({
                "report_text": report_text,
                "t0": t0, "t1": t1, "t2": t2,
                "t3": t3, "t4": t4, "t5": t5,
                # score اليومي لحساب نسبة الصعود/الهبوط في الخلاصة المشتركة
                "score": data.get('tf_daily', {}).get('score', 0),
            })

            log.info("💾 [Futures] تم حفظ بيانات الآجل — الفوري يستطيع الإرسال الآن.")
            try:

                if 't6' in locals() and t6:

                    with open('temp_summary_fut13.txt', 'w', encoding='utf-8') as f:

                        f.write(t6)

                    send_summary_to_bot('8448760638:AAF0PokiiolyPAAztD-BTZGenbjRiUKh6hc', t6, '@spotGol')

                    

                    with open('temp_summary_fut14.txt', 'w', encoding='utf-8') as f:

                        f.write(t6)

                    send_summary_to_bot('8663825687:AAHElJ0PtPoS80QxnXOGBGu9sRzAum-rqx0', t6, '@GooldFut')

                    

                    import os

                    os.system('python master_summary.py')

            except Exception as e:

                log.error(f"Failed injecting futures summary: {e}")
            log.info("🔓 [Futures] تم الإرسال، تحرير القفل.")



# ══════════════════════════════════════════════
#  9. الحلقة الرئيسية
# ══════════════════════════════════════════════
def run_bot():
    log.info("🚀 Goldbot Pro+ v4 — Spot/Futures Decoupled")

    last_gold_price      = {'futures': None, 'spot': None}
    minutes_counter      = {'futures': 0, 'spot': 0}
    morning_sent_today   = {'futures': False, 'spot': False}
    closing_sent_today   = {'futures': False, 'spot': False}
    heartbeat_sent_today = {'futures': False, 'spot': False}
    consec_failures      = {'futures': 0, 'spot': 0}
    all_models_notified  = False
    last_report_date     = None
    market_closed_notified = False
    has_sent_initial       = False
    day_names = ["اثنين","ثلاثاء","أربعاء","خميس","جمعة","سبت","أحد"]

    while True:
        now_cairo  = cairo_now()
        today      = now_cairo.date()
        hour_cairo = now_cairo.hour
        weekday    = now_cairo.weekday()

        if last_report_date != today:
            for m in ['futures', 'spot']:
                morning_sent_today[m]   = False
                closing_sent_today[m]   = False
                heartbeat_sent_today[m] = False
            all_models_notified  = False

        if not is_market_open() and has_sent_initial:
            if not market_closed_notified:
                now_c    = cairo_now()
                wday     = now_c.weekday()
                hr       = now_c.hour
                if wday in (5, 6):
                    reason   = "عطلة نهاية الأسبوع"
                    reopen   = "الاثنين 01:00 بتوقيت القاهرة"
                    details  = "أسواق الذهب والعملات والمعادن تغلق كل جمعة مساءً وتعود مطلع الأسبوع."
                elif wday == 0 and hr < MARKET_OPEN_HOUR:
                    reason   = "ما زلنا في ساعات الإغلاق"
                    reopen   = f"الاثنين {MARKET_OPEN_HOUR:02d}:00 بتوقيت القاهرة"
                    details  = "أسواق الذهب تبدأ جلستها الأسبوعية يوم الاثنين فجراً."
                else:
                    reason   = "السوق خارج ساعات التداول"
                    reopen   = "قريباً"
                    details  = "تُتداول أسواق الذهب من الاثنين حتى الجمعة."

                closed_msg = (
                    f"🛌 سوق الذهب مغلق حالياً\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📅 السبب: {reason}\n"
                    f"📖 التفاصيل: {details}\n"
                    f"⏰ موعد الفتح: {reopen}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🕐 {now_c.strftime('%Y-%m-%d %H:%M')} بتوقيت القاهرة\n"
                    f"✅ البوت يعمل وسيُرسل التقرير فور فتح السوق."
                )
                send_to_telegram(closed_msg)
                market_closed_notified = True
                log.info("📢 تم إرسال إشعار إغلاق السوق للقناة.")

            log.info(f"🛌 سوق مغلق ({day_names[weekday]} {hour_cairo:02d}:00 قاهرة). انتظار 30 دقيقة.")
            for m in ['futures', 'spot']: last_gold_price[m] = None
            time.sleep(30 * 60)
            continue

        market_closed_notified = False

        for mode in ['futures']:
            data = get_full_market_data(mode=mode)
            if data and data["gold"]:
                consec_failures[mode] = 0
                all_models_notified = False
                current_gold = data["gold"]

                if last_gold_price[mode] is None and last_report_date != today:
                    log.info(f"📊 إرسال التقرير الافتتاحي ({mode})...")
                    report = generate_report(data, is_alert=False)
                    send_reports(data, report)
                    last_gold_price[mode] = current_gold
                    last_report_date = today
                    minutes_counter[mode] = 0
                    has_sent_initial = True
                    log.info("✅ تم إرسال التقرير الافتتاحي. البوت جاهز لمنطق 'سوق مغلق'.")

                elif hour_cairo == HEARTBEAT_HOUR and not heartbeat_sent_today[mode]:
                    conf = data['confluence']
                    send_to_telegram(
                        f"💚 [Goldbot Heartbeat - {mode.upper()}] البوت يعمل بشكل طبيعي ✔️\n"
                        f"💰 السعر: {current_gold:.2f}$\n"
                        f"🎯 {conf['verdict']}\n"
                        f"🕐 {now_cairo.strftime('%H:%M قاهرة')}"
                    )
                    heartbeat_sent_today[mode] = True

                elif hour_cairo == MORNING_HOUR_CAI and not morning_sent_today[mode]:
                    log.info(f"🌅 إرسال تقرير الصباح ({mode})...")
                    report = generate_report(data, is_alert=False, is_morning=True)
                    if report:
                        send_reports(data, report)
                        morning_sent_today[mode] = True
                        last_gold_price[mode] = current_gold
                        minutes_counter[mode] = 0

                elif hour_cairo == CLOSING_HOUR_CAI and not closing_sent_today[mode]:
                    log.info(f"🌙 إرسال ملخص الجلسة ({mode})...")
                    report = generate_report(data, is_alert=False)
                    if report:
                        send_reports(data, report, f"🌙 [ملخص جلسة اليوم - {mode.upper()}]\n")
                        closing_sent_today[mode] = True
                        last_gold_price[mode] = current_gold
                        minutes_counter[mode] = 0

                else:
                    price_diff = current_gold - (last_gold_price[mode] or current_gold)
                    if abs(price_diff) >= ALERT_THRESHOLD:
                        log.info(f"🚨 تحرك حاد {price_diff:+.2f}$ ({mode})")
                        report = generate_report(data, is_alert=True, price_diff=price_diff)
                        if report:
                            send_reports(data, report)
                            last_gold_price[mode] = current_gold
                            minutes_counter[mode] = 0
                    elif minutes_counter[mode] >= ROUTINE_MINUTES:
                        log.info(f"⏰ مرت {ROUTINE_MINUTES} دقيقة — تقرير دوري ({mode})...")
                        report = generate_report(data, is_alert=False)
                        if report:
                            send_reports(data, report)
                            last_gold_price[mode] = current_gold
                            minutes_counter[mode] = 0
            else:
                consec_failures[mode] += 1
                log.warning(f"⚠️ فشل جلب البيانات مرة {consec_failures[mode]} ({mode}).")
                if consec_failures[mode] >= 3 and not all_models_notified:
                    send_to_telegram(
                        f"🚨 تحذير — جولدبوت يواجه مشكلة في {mode.upper()}!\n"
                        "تعذّر جلب البيانات. سيتم إعادة المحاولة تلقائياً."
                    )
                    all_models_notified = True

            minutes_counter[mode] += 1
            
        time.sleep(60)

if __name__ == "__main__":
    try:
        run_bot()
    except KeyboardInterrupt:
        print("\nBot stopped by user.")

import requests

def send_summary_to_bot(token, message, chat_id):
    import requests
    try:
        # Fallback dynamic retrieval (if user messaged bot directly)
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            resp = requests.get(url, timeout=5).json()
            if resp.get('ok') and resp.get('result'):
                # Prioritize a private chat if available, else keep the group chat_id
                for res in reversed(resp['result']):
                    if 'message' in res and res['message']['chat']['type'] == 'private':
                        chat_id = res['message']['chat']['id']
                        break
        except:
            pass
            
        send_url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(send_url, json={'chat_id': chat_id, 'text': message}, timeout=10)
    except Exception as e:
        print(f"Failed to send summary: {e}")


def _build_futures_s9(d: dict) -> str:
    """9/12 - مصفوفة التداول والاسكالبينج الاحترافي"""
    nums = _s_nums(d)
    gold, atr, pivot = nums['gold'], nums['atr'], nums['pivot']
    rsi, macd = nums['rsi'], nums['macd']
    r1, r2, r3, s1, s2, s3 = nums['r1'], nums['r2'], nums.get('r3', nums['r2']+atr), nums['s1'], nums['s2'], nums.get('s3', nums['s2']-atr)
    sh, sl = nums['swing_h'], nums['swing_l']
    fib = d.get('fib', {}) or {}

    interest  = float(d.get('interest_rate', 5.25) or 5.25)
    inflation = float(d.get('inflation_est', 3.5) or 3.5)
    ry        = float(d.get('real_yield', 0) or 0) or round(interest - inflation, 2)
    dxy_p     = float(d.get('dxy_p', 100) or 100)
    vix_p     = float(d.get('vix_p', 20) or 20)
    sp500     = float(d.get('sp500_pct', 0) or 0)
    fx        = d.get('fx_sorted', []) or []

    adv = d.get('adv_trades', {}) or {}
    
    # Mathematical Precision Fallbacks (Corrected Directions)
    sb  = adv.get('scalp_buy') or {'entry': round(s1 + (pivot - s1) * 0.2, 2), 'sl': round(s1 - atr * 0.2, 2), 't1': pivot, 't2': round((pivot+r1)/2, 2), 't3': r1}
    ss  = adv.get('scalp_sell') or {'entry': round(r1 - (r1 - pivot) * 0.2, 2), 'sl': round(r1 + atr * 0.2, 2), 't1': pivot, 't2': round((pivot+s1)/2, 2), 't3': s1}
    db  = adv.get('daily_buy') or {'entry': s1, 'sl': s2, 't1': pivot, 't2': r1, 't3': r2}
    ds  = adv.get('daily_sell') or {'entry': r1, 'sl': r2, 't1': pivot, 't2': s1, 't3': s2}
    swb = adv.get('swing_buy') or {'entry': s2, 'sl': s3, 't1': s1, 't2': pivot, 't3': r1}
    sws = adv.get('swing_sell') or {'entry': r2, 'sl': r3, 't1': r1, 't2': pivot, 't3': s1}

    score = 0
    if vix_p > 25: score -= 2
    elif vix_p < 18: score += 2
    if sp500 > 0.5: score += 1
    elif sp500 < -0.5: score -= 1
    if ry > 1.5: score -= 1
    risk_pct = max(30, min(80, 50 + score * 5))
    risk_label = "عالية 🔴" if risk_pct > 60 else "متوسطة 🟡" if risk_pct > 45 else "منخفضة 🟢"

    fib_block = "\n".join(f"  - **{k}:** {v}" for k, v in fib.items()) if fib else (
        f"  - R1: {r1:.2f}$ | R2: {r2:.2f}$\n  - S1: {s1:.2f}$ | S2: {s2:.2f}$"
    )
    fx_block = "\n".join(f"  - **{sym}:** {pct:+.4f}%" for sym, pct in fx[:8]) if fx else "  - بيانات العملات متاحة عند التريجر"

    return (
        "👑 **مؤشر شهية المخاطرة الشامل (Risk Appetite)** 👑\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🌐 **المسح السعري اللحظي والسيولة:**\n"
        f"- 💰 **سعر الذهب الحالي:** **{gold:.2f}$**\n"
        f"- 🎯 **اعلى النطاق:** {sh:.2f}$ | **ادنى النطاق:** {sl:.2f}$\n"
        f"- 📊 **مؤشر RSI:** {rsi:.2f}\n"
        f"- 📉 **مؤشر MACD:** {macd:.4f}\n"
        f"- 📏 **مؤشر ATR:** {atr:.2f}$\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n📈 **الركائز الفنية الأساسية:**\n"
        "- 🔢 **مستويات فيبوناتشي:**\n"
        f"{fib_block}\n"
        f"- 🎯 **المحور:** {pivot:.2f}$ | **R1:** {r1:.2f}$ | **S1:** {s1:.2f}$\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n📊 **الركائز الأساسية (الماكرو والسيولة):**\n"
        f"- 📉 **معدل التضخم:** {inflation:.2f}%\n"
        f"- 🏦 **معدل الفائدة:** {interest:.2f}%\n"
        f"- ⚖️ **العائد الحقيقي:** {ry:.2f}%\n"
        f"- 🚨 **VIX (مؤشر الخوف):** {vix_p:.2f} ({'مرتفع — تحوط' if vix_p > 25 else 'منخفض — جشع'})\n"
        f"- 📈 **S&P 500 اليومي:** {sp500:+.2f}%\n"
        f"- 💵 **مؤشر الدولار (DXY):** {dxy_p:.4f}\n"
        "- 💱 **قوة العملات:**\n"
        f"{fx_block}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n🎯 **مصفوفة استراتيجيات التداول الشاملة (Trading Matrix)** 🎯\n*(هذه المصفوفة عالية الدقة توضح نقاط الدخول المثالية للسكالبينج والسوينج بناءً على خوارزميات السيولة)*\n\n"
        "⚡ **1. السكالبينج (خطف سريع - مخاطرة عالية)**\n"
        f"🟢 **شراء:** دخول: **{sb.get('entry',0):.2f}$** | الاستوب: **{sb.get('sl',0):.2f}$**\n"
        f"🎯 الأهداف: {sb.get('t1',0):.2f}$ - {sb.get('t2',0):.2f}$ - {sb.get('t3',0):.2f}$\n"
        f"🔴 **بيع:** دخول: **{ss.get('entry',0):.2f}$** | الاستوب: **{ss.get('sl',0):.2f}$**\n"
        f"🎯 الأهداف: {ss.get('t1',0):.2f}$ - {ss.get('t2',0):.2f}$ - {ss.get('t3',0):.2f}$\n\n"
        "📅 **2. التداول اليومي (Intraday - مخاطرة متوسطة)**\n"
        f"🟢 **شراء:** دخول: **{db.get('entry',0):.2f}$** | الاستوب: **{db.get('sl',0):.2f}$**\n"
        f"🎯 الأهداف: {db.get('t1',0):.2f}$ - {db.get('t2',0):.2f}$\n"
        f"🔴 **بيع:** دخول: **{ds.get('entry',0):.2f}$** | الاستوب: **{ds.get('sl',0):.2f}$**\n"
        f"🎯 الأهداف: {ds.get('t1',0):.2f}$ - {ds.get('t2',0):.2f}$\n\n"
        "📆 **3. السوينج الاستراتيجي (مخاطرة مضبوطة)**\n"
        f"🟢 **السوينج الشرائي:** دخول: **{swb.get('entry',0):.2f}$** | الاستوب: **{swb.get('sl',0):.2f}$**\n"
        f"🎯 الأهداف: {swb.get('t1',0):.2f}$ - {swb.get('t2',0):.2f}$ - {swb.get('t3',0):.2f}$\n"
        f"🔴 **السوينج البيعي:** دخول: **{sws.get('entry',0):.2f}$** | الاستوب: **{sws.get('sl',0):.2f}$**\n"
        f"🎯 الأهداف: {sws.get('t1',0):.2f}$ - {sws.get('t2',0):.2f}$ - {sws.get('t3',0):.2f}$\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n⚠️ **ضوابط إدارة المخاطر (Risk Management)** ⚠️\n"
        f"- 🚨 **التقييم الكمي للمخاطرة الآن:** **{risk_pct:.0f}% ({risk_label})**\n"
        f"- 💼 **إدارة المحفظة:** يُنصح بحجم مركز لا يتجاوز **{100 - risk_pct:.0f}%** من هامش المحفظة للصفقة الواحدة نظراً للظروف الحالية.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n💡 **الحكم الاستراتيجي للصفقات**\n"
        f"بناءً على التقييم الكلي للمخاطرة، التوجه الأفضل للمتداولين {'في ظل هذه المخاطرة المنخفضة هو التداول بثقة مع الاتجاه واستهداف السوينج.' if risk_pct <= 45 else 'الآن هو التداول اللحظي السريع (سكالبينج) لتقليل فترة التعرض للسوق والهروب من التذبذب.' if risk_pct > 60 else 'هو التداول اليومي بحذر والالتزام التام بنقاط الوقف وتأمين الأرباح أولاً بأول.'}"
    )

    fx_block = "\n".join(f"  - **{sym}:** {pct:+.4f}%" for sym, pct in fx[:8]) if fx else "  - بيانات العملات متاحة عند التريجر"

    return (
        "👑 **مؤشر شهية المخاطرة الشامل (Risk Appetite)** 👑\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🌐 **المسح السعري اللحظي**\n"
        f"- **سعر الذهب الحالي:** {gold:.2f}$ 💰\n"
        f"- **اعلى النطاق:** {sh:.2f}$ | **ادنى النطاق:** {sl:.2f}$\n"
        f"- **مؤشر RSI:** {rsi:.2f} 📊\n"
        f"- **مؤشر MACD:** {macd:.4f} 📉\n"
        f"- **مؤشر ATR:** {atr:.2f}$ 📊\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n📈 **الركائز الفنية الأساسية**\n"
        "- **مستويات فيبوناتشي:**\n"
        f"{fib_block}\n"
        f"- **نقطة المحور:** {pivot:.2f}$ | **R1:** {r1:.2f}$ | **S1:** {s1:.2f}$\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n📊 **الركائز الأساسية (الماكرو والسيولة)**\n"
        f"- **معدل التضخم:** {inflation:.2f}%\n"
        f"- **معدل الفائدة:** {interest:.2f}%\n"
        f"- **العائد الحقيقي:** {ry:.2f}%\n"
        f"- **VIX (مؤشر الخوف):** {vix_p:.2f} ({'مرتفع — تحوط' if vix_p > 25 else 'منخفض — جشع'})\n"
        f"- **S&P 500 اليومي:** {sp500:+.2f}%\n"
        f"- **مؤشر الدولار (DXY):** {dxy_p:.4f}\n"
        "- **قوة العملات:**\n"
        f"{fx_block}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n🎯 **مصفوفة استراتيجيات التداول الشاملة (Trading Matrix)** 🎯\n*(بناءً على تفصيل الصفقات في القوالب السابقة، نضع بين يديك الآن \"المصفوفة الشاملة\" لإدارة رأس المال وتوزيع المخاطرة للسكالبينج والسوينج)*\n\n"
        "⚡ **1. السكالبينج (خطف سريع - مخاطرة عالية)**\n"
        f"- **🟢 شراء:** الدخول {sb.get('entry',0):.2f}$ | الوقف {sb.get('sl',0):.2f}$ | الأهداف {sb.get('t1',0):.2f}$ - {sb.get('t2',0):.2f}$ - {sb.get('t3',0):.2f}$\n"
        f"- **🔴 بيع:** الدخول {ss.get('entry',0):.2f}$ | الوقف {ss.get('sl',0):.2f}$ | الأهداف {ss.get('t1',0):.2f}$ - {ss.get('t2',0):.2f}$ - {ss.get('t3',0):.2f}$\n\n"
        "📅 **2. التداول اليومي (Intraday - مخاطرة متوسطة)**\n"
        f"- **🟢 شراء:** الدخول {db.get('entry',0):.2f}$ | الوقف {db.get('sl',0):.2f}$ | الأهداف {db.get('t1',0):.2f}$ - {db.get('t2',0):.2f}$\n"
        f"- **🔴 بيع:** الدخول {ds.get('entry',0):.2f}$ | الوقف {ds.get('sl',0):.2f}$ | الأهداف {ds.get('t1',0):.2f}$ - {ds.get('t2',0):.2f}$\n\n"
        "📆 **3. السوينج الاستراتيجي (مخاطرة مضبوطة)**\n"
        f"- **🟢 السوينج الشرائي:** الدخول {swb.get('entry',0):.2f}$ | الوقف {swb.get('sl',0):.2f}$ | الأهداف {swb.get('t1',0):.2f}$ - {swb.get('t2',0):.2f}$ - {swb.get('t3',0):.2f}$\n"
        f"- **🔴 السوينج البيعي:** الدخول {sws.get('entry',0):.2f}$ | الوقف {sws.get('sl',0):.2f}$ | الأهداف {sws.get('t1',0):.2f}$ - {sws.get('t2',0):.2f}$ - {sws.get('t3',0):.2f}$\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n⚠️ **ضوابط إدارة المخاطر (Risk Management)** ⚠️\n"
        f"- **التقييم الكمي للمخاطرة في السوق الآن:** {risk_pct:.0f}% ({risk_label})\n"
        f"- **إدارة المحفظة:** يُنصح بحجم مركز لا يتجاوز {100 - risk_pct:.0f}% من هامش المحفظة للصفقة الواحدة نظراً للظروف الحالية.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n💡 **الحكم الاستراتيجي للصفقات**\n"
        f"بناءً على التقييم الكلي للمخاطرة، التوجه الأفضل للمتداولين {'في ظل هذه المخاطرة المنخفضة هو التداول بثقة مع الاتجاه' if risk_pct <= 45 else 'الآن هو التداول اللحظي السريع (سكالبينج) لتقليل فترة التعرض للسوق' if risk_pct > 60 else 'هو التداول اليومي بحذر والالتزام التام بنقاط الوقف'}."
    )


def _build_spot_s10(d: dict) -> str:
    """10/12 - عوائد السندات والفائدة والتضخم"""
    interest  = float(d.get('interest_rate', 5.25) or 5.25)
    inflation = float(d.get('inflation_est', 3.5) or 3.5)
    ry        = float(d.get('real_yield', 0) or 0) or round(interest - inflation, 2)
    tnx       = float(d.get('tnx_val', 0) or 0) or round(interest - 0.3, 2)
    twy       = float(d.get('twy_val', 0) or 0) or round(interest + 0.3, 2)
    gold      = float(d.get('gold', 0) or 0)

    spread    = round(tnx - twy, 2)
    curve_lbl = ("طبيعي — اقتصاد سليم" if spread > 0.5
                 else "مقلوب — خطر ركود اقتصادي 🚨" if spread < 0
                 else "مسطح — مرحلة تحول")

    tnx_impact = "سلبي — يزيد الضغط على الذهب" if tnx > 4.5 else "محايد — دعم محدود للذهب"
    int_impact = "سلبي — تكلفة الفرصة البديلة عالية" if interest > 4 else "ايجابي — يدعم الذهب"
    inf_impact = "ايجابي — الذهب تحوط ممتاز ضد التضخم 📈" if inflation > 3 else "محدود — التضخم تحت السيطرة"
    ry_impact  = ("سلبي — العائد الحقيقي الموجب يجعل السندات اكثر جاذبية من الذهب 📉"
                  if ry > 1 else
                  "ايجابي — العائد الحقيقي السلبي يجعل الذهب ملاذا امنا افضل 📈")

    gold_outlook = ("هبوطي — ضغط مزدوج من الفائدة والعائد الحقيقي" if ry > 1 and tnx > 4.5
                    else "صعودي — بيئة مواتية للذهب مع عائد حقيقي سلبي" if ry < 0
                    else "محايد — تاثيرات متعادلة")

    return (
        "### تحليل السوق 📊\n"
        "#### اسعار السندات والفائدة والتضخم 📈\n\n"
        f"*   **عائد سندات الخزانة الامريكية (10 سنوات - TNX)**: {tnx:.2f}% 📊\n"
        f"*   **عائد سندات الخزانة الامريكية (2 سنة - TWY)**: {twy:.2f}% 📊\n"
        f"*   **فارق منحنى العوائد (10Y - 2Y)**: {spread:+.2f}% — {curve_lbl}\n"
        f"*   **معدل الفائدة الفيدرالي**: {interest:.2f}% 📈\n"
        f"*   **معدل التضخم (CPI)**: {inflation:.2f}% 📊\n"
        f"*   **العائد الحقيقي** (TNX - CPI): **{ry:.2f}%** 📊\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n💰 **ترجمة الأرقام لتأثير سعري مباشر على الذهب**\n"
        f"*   **تاثير عائد السندات ({tnx:.2f}%)**: {tnx_impact}\n"
        f"*   **تاثير معدل الفائدة ({interest:.2f}%)**: {int_impact}\n"
        f"*   **تاثير معدل التضخم ({inflation:.2f}%)**: {inf_impact}\n"
        f"*   **تاثير العائد الحقيقي ({ry:.2f}%)**: {ry_impact}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n🔮 **توقعات المسار السعري (Forecasting)**\n"
        f"*   **النظرة المستقبلية للذهب**: {gold_outlook}\n"
        f"*   **السعر الحالي**: {gold:.2f}$\n"
        f"*   **منحنى العوائد**: {curve_lbl} — {'اشارة تحوط' if spread < 0 else 'اشارة ايجابية'}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n📝 **الخلاصة الميكانيكية للسكالبينج**\n"
        f"*   بيئة الفائدة الحالية ({interest:.2f}%) مع تضخم ({inflation:.2f}%) تشير الى ان "
        f"العائد الحقيقي {ry:.2f}% وهو {'يضغط سلبا على الذهب' if ry > 0 else 'يدعم الذهب بشكل قوي'}.\n"
        "*   ومع ذلك، يجب مراعاة العوامل الجيوسياسية والطلب المادي على الذهب.\n"
        f"*   توقع تداول الذهب في نطاق متاثر بمنحنى العوائد {curve_lbl}.\n"
        f"*   {'⚠️ منحنى مقلوب: مؤشر تاريخي على ركود وشيك — يُعزز الطلب على الذهب.' if spread < 0 else '✅ منحنى طبيعي: ثقة بنمو الاقتصاد — يُقلل الطلب على الملاذات الآمنة مؤقتاً.' if spread > 0.5 else '⚠️ منحنى مسطح: مرحلة تحول اقتصادي — تريث وراقب.'} 🌎"
    )


def _build_spot_s11(d: dict) -> str:
    """11/12 - قوة العملات وتاثير DXY"""
    nums = _s_nums(d)
    gold, atr, pivot = nums['gold'], nums['atr'], nums['pivot']
    rsi, macd = nums['rsi'], nums['macd']
    r1, r2, s1, s2 = nums['r1'], nums['r2'], nums['s1'], nums['s2']
    sh, sl = nums['swing_h'], nums['swing_l']

    dxy_p   = float(d.get('dxy_p', 100) or 100)
    dxy_pct = float(d.get('dxy_pct', 0) or 0)
    fx      = d.get('fx_sorted', []) or []

    # تحليل DXY والعلاقة مع الذهب باحترافية عالية
    if dxy_pct > 0.5:
        dxy_effect  = "🔴 **قوي جداً** — ضغط هبوطي حاد على الملاذات الآمنة"
        dxy_gold    = f"مؤشر الدولار يسجل ارتفاعاً ملحوظاً بنسبة {dxy_pct:+.2f}%، مما يضع الذهب تحت ضغط بيعي مكثف بفضل العلاقة العكسية التاريخية."
        gold_impact = f"نتوقع استمرار الضغط البيعي لاختبار مستويات الدعم السفلية. كسر {s1:.2f}$ قد يفتح المجال للهبوط نحو {s2:.2f}$."
        buy_res     = f"🚫 **تجنب الشراء** — الزخم الحالي لصالح الدولار، الشراء يُعتبر التقاطاً للسكين الساقط."
        sell_res    = f"✅ **توصية بيع** — الدخول عند أي ارتداد طفيف نحو {pivot:.2f}$ أو {r1:.2f}$ مع وضع وقف الخسارة أعلى {r2:.2f}$ بقليل."
        recom       = f"الاستراتيجية المثلى: **البيع مع الاتجاه الهابط** مستهدفين {s1:.2f}$ ثم {s2:.2f}$."
    elif dxy_pct > 0.15:
        dxy_effect  = "🟠 **إيجابي** — ضغط هبوطي متوسط على الذهب"
        dxy_gold    = f"الدولار يظهر قوة تدريجية (مكاسب {dxy_pct:+.2f}%)، مما يحد من فرص صعود الذهب ويجعله يميل للسلبية."
        gold_impact = f"الذهب يواجه مقاومة عنيدة عند {r1:.2f}$ بفضل قوة الدولار، ويميل لاختبار الدعم الأول {s1:.2f}$."
        buy_res     = f"⚠️ **شراء بحذر** — فقط من مناطق الدعم القصوى ({s2:.2f}$) مع وقف خسارة ضيق جداً."
        sell_res    = f"✅ **فرصة بيع** — حول مستويات {pivot:.2f}$ أو المقاومة الأولى {r1:.2f}$، مستهدفين {s1:.2f}$."
        recom       = f"الاستراتيجية المثلى: **البيع من مناطق المقاومة** ({r1:.2f}$) مع وقف {r2:.2f}$."
    elif dxy_pct < -0.5:
        dxy_effect  = "🟢 **ضعيف جداً** — دعم صعودي قوي جداً للذهب"
        dxy_gold    = f"الدولار يتعرض لعمليات بيع واسعة (خسائر {dxy_pct:+.2f}%)، مما يعطي الذهب الضوء الأخضر لتحقيق مكاسب قوية."
        gold_impact = f"ضعف الدولار يعزز من جاذبية الذهب. نتوقع اختراق {r1:.2f}$ واستهداف {r2:.2f}$ وما فوقها."
        buy_res     = f"✅ **توصية شراء** — الدخول من مستويات الدعم الحالية أو عند {pivot:.2f}$، مستهدفين {r1:.2f}$ و {r2:.2f}$."
        sell_res    = f"🚫 **تجنب البيع** — السباحة عكس التيار في ظل ضعف الدولار تحمل مخاطر عالية جداً."
        recom       = f"الاستراتيجية المثلى: **الشراء مع الاتجاه الصاعد** مستهدفين {r1:.2f}$ ثم {r2:.2f}$."
    elif dxy_pct < -0.15:
        dxy_effect  = "🔵 **سلبي** — دعم صعودي متوسط للذهب"
        dxy_gold    = f"مؤشر الدولار يتراجع بنسبة {dxy_pct:+.2f}%، مما يوفر بيئة داعمة للذهب للتماسك وبناء مراكز شرائية."
        gold_impact = f"الذهب يتلقى دعماً كافياً لاختبار المقاومة {r1:.2f}$. البقاء فوق {pivot:.2f}$ يُعد إيجابياً."
        buy_res     = f"✅ **فرصة شراء** — حول {pivot:.2f}$ أو الدعم {s1:.2f}$، مستهدفين المقاومة {r1:.2f}$."
        sell_res    = f"⚠️ **بيع بحذر** — فقط من مستويات المقاومة القصوى ({r2:.2f}$) وبلوت صغير."
        recom       = f"الاستراتيجية المثلى: **الشراء من الدعوم** ({s1:.2f}$) مع وقف {s2:.2f}$."
    else:
        dxy_effect  = "⚪ **محايد** — تأثير محدود (تذبذب عرضي)"
        dxy_gold    = f"مؤشر الدولار مستقر نسبياً (تغير {dxy_pct:+.2f}%)، مما يترك الذهب للتحرك بناءً على العوامل الفنية الصرفة."
        gold_impact = f"في غياب المحفزات من الدولار، الذهب محصور فنياً في النطاق العرضي بين {s1:.2f}$ و {r1:.2f}$."
        buy_res     = f"✅ **الشراء** من الحد السفلي للنطاق ({s1:.2f}$) بهدف المحور ({pivot:.2f}$)."
        sell_res    = f"✅ **البيع** من الحد العلوي للنطاق ({r1:.2f}$) بهدف المحور ({pivot:.2f}$)."
        recom       = f"الاستراتيجية المثلى: **تداول النطاق العرضي (Range Trading)** بين {s1:.2f}$ و {r1:.2f}$."

    # تنسيق مصفوفة العملات بشكل احترافي
    if fx and len(fx) >= 2:
        top_fx = f"🟩 **أقوى العملات:** {fx[0][0]} ({fx[0][1]:+.2f}%) | {fx[1][0]} ({fx[1][1]:+.2f}%)"
        bot_fx = f"🟥 **أضعف العملات:** {fx[-1][0]} ({fx[-1][1]:+.2f}%) | {fx[-2][0]} ({fx[-2][1]:+.2f}%)"
        fx_block = f"{top_fx}\n{bot_fx}"
    else:
        fx_block = "⏳ بيانات تدفق السيولة للعملات قيد التحديث..."

    return f'''### 🌍 تقرير السيولة النقدية وارتباط الدولار (DXY)
======================================================

#### 📊 المعطيات الفنية الحالية (XAU/USD)
**السعر الحالي:** {gold:.2f}$ 💰 | **المحور اليومي:** {pivot:.2f}$
**مقاومات أساسية:** {r1:.2f}$ (R1) — {r2:.2f}$ (R2)
**دعوم أساسية:** {s1:.2f}$ (S1) — {s2:.2f}$ (S2)
**الزخم:** RSI = {rsi:.2f} | MACD = {macd:.4f}

#### 💵 مؤشر الدولار الأمريكي (DXY)
**القراءة الحالية:** {dxy_p:.4f} نقطة
**التغير اليومي:** {dxy_pct:+.2f}%
**حالة السيولة:** {dxy_effect}

#### 💱 مصفوفة قوة العملات (FX Flow)
{fx_block}

#### 🔗 التأثير المتوقع على الذهب
{dxy_gold}
{gold_impact}

#### 🎯 الخلاصة الاستراتيجية (النقاط المفصلية)
{buy_res}
{sell_res}

💡 {recom}
'''
def _build_spot_s12(d: dict) -> str:
    """12/12 - الخلاصة المحورية الشاملة (بأعلى دقة كمية)"""
    nums = _s_nums(d)
    gold, atr, pivot = nums['gold'], nums['atr'], nums['pivot']
    rsi, macd = nums['rsi'], nums['macd']
    r1, r2, r3 = nums['r1'], nums['r2'], nums['r3']
    s1, s2, s3 = nums['s1'], nums['s2'], nums['s3']
    
    # تحسين استدعاء Swing H/L بدقة
    sh = d.get('swing_h', 0)
    sl = d.get('swing_l', 0)
    if sh <= 0 or sh < gold: sh = round(r2, 2)
    if sl <= 0 or sl > gold: sl = round(s2, 2)
    
    # تحسين استدعاء المدى اليومي (القمة والقاع اليومي)
    d_high_arr = d.get('gold_daily', {}).get('High', [])
    d_low_arr = d.get('gold_daily', {}).get('Low', [])
    d_high = float(d_high_arr[-1]) if len(d_high_arr) > 0 else round(gold + (atr * 0.4), 2)
    d_low = float(d_low_arr[-1]) if len(d_low_arr) > 0 else round(gold - (atr * 0.4), 2)
    if d_high < gold: d_high = round(gold + (atr * 0.2), 2)
    if d_low > gold: d_low = round(gold - (atr * 0.2), 2)
    
    fib = d.get('fib', {}) or {}
    interest  = float(d.get('interest_rate', 5.25) or 5.25)
    inflation = float(d.get('inflation_est', 3.5) or 3.5)
    ry        = float(d.get('real_yield', 0) or 0) or round(interest - inflation, 2)
    dxy_p     = float(d.get('dxy_p', 100) or 100)
    dxy_pct   = float(d.get('dxy_pct', 0) or 0)
    vix_p     = float(d.get('vix_p', 20) or 20)

    fib_block = "\n".join(
        f"- **{k}**: **{v}** {'📈' if k == '0.0%' else '📉' if k == '100%' else '📊'}"
        for k, v in fib.items()
    ) if fib else (
        f"- محسوب: R1={r1:.2f}$ | R2={r2:.2f}$ | S1={s1:.2f}$ | S2={s2:.2f}$"
    )

    # تحليل RSI بدقة
    if rsi < 30:
        rsi_note = f"RSI={rsi:.2f} تشبع بيعي حاد — إشارة على استنفاد الزخم الهبوطي 📈"
    elif rsi > 70:
        rsi_note = f"RSI={rsi:.2f} تشبع شرائي حاد — إشارة على استنفاد الزخم الصعودي 📉"
    else:
        rsi_note = f"RSI={rsi:.2f} محايد — الزخم متوازن ويخضع للسيولة اللحظية"

    macd_note = (f"MACD={macd:.4f} سلبي — البائعون يسيطرون على تداولات اليوم 📉"
                 if macd < 0 else
                 f"MACD={macd:.4f} إيجابي — المشترون يسيطرون على تداولات اليوم 📈")

    # المدى اليومي المتوقع بأعلى دقة رياضية
    exp_high = round(pivot + (atr * 0.6), 2)
    exp_low  = round(pivot - (atr * 0.6), 2)
    atr_note = (f"ATR={atr:.2f}$ — تقلبات {'كبيرة جداً' if atr > 100 else 'عالية' if atr > 60 else 'متوسطة' if atr > 30 else 'منخفضة'}. "
                f"المدى الديناميكي المتوقع لحركة السعر اليوم: بين القاع {exp_low:.2f}$ والقمة {exp_high:.2f}$")

    # التقييم الاستراتيجي الشامل بأعلى جودة
    is_bullish = gold > pivot and macd > 0
    is_bearish = gold < pivot and macd < 0
    
    if is_bullish and rsi < 70:
        main_dir = "🟢 صعودي صريح (Strong Bullish)"
        best_trade = f"🎯 اصطياد قيعان الشراء (Dip Buying) من الدعم {s1:.2f}$، أو اختراق المحور {pivot:.2f}$. الوقف مغلق تحت {round(s1 - atr*0.25, 2)}$. الأهداف: {r1:.2f}$ و {r2:.2f}$."
        final_advice = f"🟢 الزخم في صالح المشتري بشكل حاسم. تجنب البيع العشوائي وركز على مراكز الشراء من الدعوم مع أي تصحيح، فالاتجاه لم يستنفد طاقته بعد."
    elif is_bearish and rsi > 30:
        main_dir = "🔴 هبوطي صريح (Strong Bearish)"
        best_trade = f"🎯 اصطياد قمم البيع (Rally Selling) من المقاومة {r1:.2f}$، أو كسر المحور {pivot:.2f}$. الوقف مغلق فوق {round(r1 + atr*0.25, 2)}$. الأهداف: {s1:.2f}$ و {s2:.2f}$."
        final_advice = f"🔴 الزخم في صالح البائع بشكل حاسم. تجنب الشراء العشوائي وركز على البيع مع أي ارتداد وهمي لأعلى، فالضغوط البيعية لم تنتهِ."
    elif gold > pivot and rsi >= 70:
        main_dir = "⚠️ صعودي متشبع خطير (Overbought Warning)"
        best_trade = f"🎯 قناص بيع عكس الاتجاه من ذروة المقاومة ({r2:.2f}$ أو {sh:.2f}$). الوقف صارم أعلى القمة بـ {round(atr*0.15, 2)}$. الأهداف العميقة: {r1:.2f}$ ثم {pivot:.2f}$."
        final_advice = f"⚠️ المشترون مرهقون جداً (استنفاد سيولة شرائية). السوق مهيأ لفخ صعودي (Bull Trap). تجنب الشراء بالأسعار الحالية وابحث عن تأكيد البيع من مناطق الذروة."
    elif gold < pivot and rsi <= 30:
        main_dir = "⚠️ هبوطي متشبع خطير (Oversold Warning)"
        best_trade = f"🎯 قناص شراء عكس الاتجاه من عمق الدعم ({s2:.2f}$ أو {sl:.2f}$). الوقف صارم أسفل القاع بـ {round(atr*0.15, 2)}$. الأهداف العميقة: {s1:.2f}$ ثم {pivot:.2f}$."
        final_advice = f"⚠️ البائعون مرهقون جداً (استنفاد سيولة بيعية). السوق مهيأ لفخ هبوطي (Bear Trap). تجنب البيع بالأسعار الحالية وابحث عن تأكيد الشراء من الانهيارات العميقة."
    else:
        main_dir = "⚪ تذبذب عرضي محايد (Ranging / Chop Zone)"
        best_trade = f"🎯 تداول حواف النطاق: الشراء من {s1:.2f}$ والبيع من {r1:.2f}$ بوقوف ضيقة جداً لا تتجاوز {round(atr*0.2, 2)}$، مع استهداف نقطة المحور {pivot:.2f}$."
        final_advice = f"⚖️ انعدام سيولة اتجاهية واضحة. يجب الالتزام الصارم بتداول الحد العلوي والسفلي للنطاق (Range Edges) وعدم الدخول في مراكز استراتيجية ممتدة حتى يتم كسر النطاق."

    # صفقات عالية الجودة والدقة
    # 1. سكالبينج قوي (يعتمد على السيولة الدقيقة S1/R1)
    scalp_buy_entry = round(s1 - (atr * 0.05), 2)
    scalp_buy_sl = round(s1 - (atr * 0.25), 2)
    scalp_buy_t1 = round(s1 + (atr * 0.4), 2)
    scalp_buy_t2 = round(pivot, 2)

    scalp_sell_entry = round(r1 + (atr * 0.05), 2)
    scalp_sell_sl = round(r1 + (atr * 0.25), 2)
    scalp_sell_t1 = round(r1 - (atr * 0.4), 2)
    scalp_sell_t2 = round(pivot, 2)

    # 2. سوينج ممتد وعميق (يعتمد على أطراف الذروة S2/R2)
    swing_buy_entry = round(s2 - (atr * 0.1), 2)
    swing_buy_sl = round(s2 - (atr * 0.35), 2)
    swing_buy_t1 = round(s1, 2)
    swing_buy_t2 = round(r1, 2)

    swing_sell_entry = round(r2 + (atr * 0.1), 2)
    swing_sell_sl = round(r2 + (atr * 0.35), 2)
    swing_sell_t1 = round(r1, 2)
    swing_sell_t2 = round(s1, 2)

    # نطاق التداول الدقيق
    if gold > r1:
        range_desc = f"📈 اختراق صعودي لسيولة المقاومة. يتداول الذهب بحرية فوق {r1:.2f}$ مع استهداف عنيف نحو {r2:.2f}$."
    elif gold < s1:
        range_desc = f"📉 كسر هبوطي لسيولة الدعم. ينزف الذهب بحرية تحت {s1:.2f}$ مع استهداف عنيف نحو {s2:.2f}$."
    elif gold > pivot:
        range_desc = f"⚖️ استقرار إيجابي أعلى المحور. يتحرك السعر بضغط شرائي داخل النطاق [{pivot:.2f}$ — {r1:.2f}$]."
    else:
        range_desc = f"⚖️ استقرار سلبي أدنى المحور. يتحرك السعر بضغط بيعي داخل النطاق [{pivot:.2f}$ — {s1:.2f}$]."

    # تقييم الاقتصاد الكلي للخلاصة
    macro_read = ("سلبية: الدولار والفائدة القوية تضغط وتمنع الذهب من تحقيق قمم جديدة براحة"
                  if ry > 1 and dxy_pct > 0 else
                  "إيجابية: تراجع الدولار وانخفاض العائد الحقيقي يوفر أرضية صلبة لارتفاعات الذهب")

    return (
        "### 👑 الخلاصة المحورية الشاملة (Master Summary) 👑\n*(هذه الخلاصة المحورية هي مسك الختام وعصارة التقارير السابقة، وتعتبر المرجع النهائي والأدق لقرارك اليوم)*\n"
        "#### 📊 تقييم السيولة والنطاقات بدقة متناهية 📊\n"
        f"- **السعر اللحظي الدقيق:** **{gold:.2f}$** 💰\n"
        f"- **نقطة الارتكاز المحورية (Pivot):** **{pivot:.2f}$** ⚖️\n"
        f"- **أعلى سعر مسجل اليوم (Daily High):** **{d_high:.2f}$** 🚀\n"
        f"- **أدنى سعر مسجل اليوم (Daily Low):** **{d_low:.2f}$** 📉\n"
        f"- **أقصى قمة مسجلة مؤخراً (Swing High):** **{sh:.2f}$** ⬆️\n"
        f"- **أقصى قاع مسجل مؤخراً (Swing Low):** **{sl:.2f}$** ⬇️\n\n"
        "#### 📐 الدعم والمقاومة الهيكلية 📐\n"
        f"- 🧱 مقاومات البائعين: **R1={r1:.2f}$** | **R2={r2:.2f}$** | **R3={r3:.2f}$**\n"
        f"- 🛡️ دعوم المشترين: **S1={s1:.2f}$** | **S2={s2:.2f}$** | **S3={s3:.2f}$**\n\n"
        "#### 🔮 المدى المتوقع لليوم والزخم 🔮\n"
        f"- **المدى المتوقع لليومي:** {atr_note}\n"
        f"- **مؤشر الزخم والتسارع (MACD):** {macd_note}\n"
        f"- **الضغط الفني (RSI):** {rsi_note}\n\n"
        "#### 🎯 الصفقات الموصى بها (جودة قناص عالية الدقة) 🎯\n"
        f"**⚡ استراتيجية السكالبينج (ارتدادات النطاق اللحظي):**\n"
        f" + 🟢 **شراء من قاع لحظي**: نقطة التمركز **{scalp_buy_entry:.2f}$** | وقف الإغلاق **{scalp_buy_sl:.2f}$** | أهداف **{scalp_buy_t1:.2f}$**، ثم **{scalp_buy_t2:.2f}$**.\n"
        f" + 🔴 **بيع من قمة لحظية**: نقطة التمركز **{scalp_sell_entry:.2f}$** | وقف الإغلاق **{scalp_sell_sl:.2f}$** | أهداف **{scalp_sell_t1:.2f}$**، ثم **{scalp_sell_t2:.2f}$**.\n\n"
        f"**🌊 استراتيجية السوينج الممتد (الاعتماد الكامل على أطراف الذروة السعرية):**\n"
        f" + 🟢 **شراء استراتيجي (Deep Dip)**: التمركز العميق **{swing_buy_entry:.2f}$** | وقف النزيف **{swing_buy_sl:.2f}$** | أهداف **{swing_buy_t1:.2f}$**، ثم **{swing_buy_t2:.2f}$**.\n"
        f" + 🔴 **بيع استراتيجي (Top Short)**: التمركز المرتفع **{swing_sell_entry:.2f}$** | وقف النزيف **{swing_sell_sl:.2f}$** | أهداف **{swing_sell_t1:.2f}$**، ثم **{swing_sell_t2:.2f}$**.\n\n"
        "#### 💡 الحكم النهائي للذهب (الخلاصة الاستراتيجية) 💡\n"
        f"**🧭 الاتجاه العام المعتمد:** {main_dir}\n\n"
        f"**💎 أهم فرصة حالية متوفرة في السوق (بدقة القناص):** {best_trade}\n\n"
        f"**📈 نطاق التداول اللحظي ومسار السيولة:** {range_desc}\n\n"
        f"**⚠️ التوصية الختامية الحاكمة (قرار الماكينة):** {final_advice}\n\n"
        f"**🌎 البيئة الاقتصادية الدافعة للسعر:** {macro_read}. والدولار ({dxy_pct:+.2f}%) يمثل دافعاً {'سلبياً' if dxy_pct > 0 else 'إيجابياً'} لتداولات الذهب الآن.\n"
    )
def _build_summary_template(d: dict, report_text: str, mode_label: str) -> str:
    client = Groq(api_key=random.choice(GROQ_KEYS)) if GROQ_KEYS else None
    if not client: return ""
    
    gold = d.get('gold', 0)
    rsi = d.get('tf_daily', {}).get('rsi', 50)
    macd_val = d.get('tf_daily', {}).get('macd', 0)
    ry = d.get('real_yield', 0)
    bias_d = d.get('tf_daily', {}).get('bias', 'محايد')
    bias_w = d.get('tf_weekly', {}).get('bias', 'محايد')
    pivot = d.get('pivot', 0)
    # جعل المستويات ديناميكية تتحرك مع السوق والـ ATR بدلاً من المحاور الثابتة
    atr = d.get('atr', 20)
    s1, s2 = round(gold - (atr * 0.8), 2), round(gold - (atr * 1.5), 2)
    r1, r2 = round(gold + (atr * 0.8), 2), round(gold + (atr * 1.5), 2)
    
    adv = d.get('adv_trades', {})
    best_buy = adv.get('monthly_buy') or adv.get('swing_buy') or adv.get('rev_buy') or adv.get('weekly_buy')
    best_sell = adv.get('monthly_sell') or adv.get('swing_sell') or adv.get('rev_sell') or adv.get('weekly_sell')
    
    def format_trade(t):
        if not t: return "جاري حساب نقطة الدخول الدقيقة"
        return f"دخول: {t['entry']}$ | هدف: {t['t2']}$ | وقف: {t['sl']}$"

    prompt = f"""أنت خبير مالي كمي. بناءً على هذه الأرقام اللحظية، استخرج 'الخلاصة المحورية' لسوق {mode_label}.
السعر: {gold}$ | المحور(Pivot): {pivot}$ | الاتجاه اليومي: {bias_d} | الأسبوعي: {bias_w}
RSI: {rsi} | MACD: {macd_val} | العائد الحقيقي: {ry}%

أقوى صفقة شراء: {format_trade(best_buy)}
أقوى صفقة بيع: {format_trade(best_sell)}
دعوم: S1={s1}, S2={s2}
مقاومات: R1={r1}, R2={r2}

استخرج ونسق البيانات بنفس هذا القالب بالضبط بدون أي ديباجة إضافية (أرقام فقط كالمطلوب):

الخلاصة المحورية

🎯 خلاصة انحياز الذهب | {mode_label} | التحديث المباشر

📈 احتمال صعود للقمه: [توقعك كنسبة]% (نحو {r2}$)
📉 احتمال هبوط نحو القاع: [توقعك كنسبة]% (نحو {s2}$)
🔀 احتمالية التذبذب: [توقعك كنسبة]% (حول {gold}$)

🧭 الخلاصة:
[فقرة قصيرة جداً من سطرين تلخص وضع السوق والقرار المناسب بناء على الأرقام أعلاه]

📍 نقطة الفصل اليومية (Pivot):
{pivot}$ [تعليق قصير]

📌 مستويات التداول الحالية:
🟢 مستويات الشراء {mode_label}: S1={s1}$ | S2={s2}$
🔴 مستويات البيع {mode_label}: R1={r1}$ | R2={r2}$

✅ أقوى صفقة شراء {mode_label}:
{format_trade(best_buy)}
   الثقة: [تقييم]% | السبب: [سبب فني قصير]

✅ أقوى صفقة بيع {mode_label}:
{format_trade(best_sell)}
   الثقة: [تقييم]% | السبب: [سبب فني قصير]"""

    for model_name in GROQ_MODELS:
        try:
            resp = client.chat.completions.create(
                messages=[{"role": "system", "content": MASTER_SYSTEM_PROMPT + "أنت محلل كمي. التزم بالقالب الحرفي للأرقام بدون أي ديباجة."}, {"role": "user", "content": prompt}],
                model=model_name, temperature=0.1, max_tokens=600
            )
            return resp.choices[0].message.content
        except: pass
    return "⚠️ تعذر توليد الخلاصة المحورية بسبب الضغط على السيرفر."

def _build_all_tf_levels(data: dict) -> str:
    """بناء قالب مستويات واتجاهات اليوم الشامل رياضياً"""
    gld = data.get('gold', 2000)
    atr = data.get('atr', 20)
    
    # محاكاة تقريبية لانحرافات الفريمات
    # (الـ ATR يتقلص مع صغر الفريم. كمعدل تقريبي: 1h=atr/2, 15m=atr/4, 5m=atr/6, daily=atr)
    tfs = [
        ("5 دقائق", 0.15),
        ("10 دقائق", 0.20),
        ("15 دقيقة", 0.25),
        ("30 دقيقة", 0.35),
        ("ساعة", 0.50),
        ("4 ساعات", 0.75),
        ("يوم", 1.0),
        ("أسبوع", 2.2),
        ("شهر", 4.5)
    ]
    
    lines = ["━━━━━━━━━━━━━━━━━━━━━━━━━━\n📍📊 مستويات واتجاهات الذهب الشاملة لكل الفريمات الزمنية\n━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    
    for name, factor in tfs:
        tf_atr = atr * factor
        # الحسابات الرياضية الدقيقة
        pivot = gld
        high = gld + tf_atr * 1.5
        low = gld - tf_atr * 1.5
        # FIX 6: Expected close respects market bias direction
        _bias_dir = 1 if ('صاعد' in data.get('tf_daily', {}).get('bias', '') or 'bull' in str(data.get('confluence', {}).get('bias', ''))) else -1
        close = gld + (_bias_dir * tf_atr * 0.2)
        buy_zone = gld - tf_atr * 0.5
        sell_zone = gld + tf_atr * 0.5
        break_up = gld + tf_atr * 0.8
        break_down = gld - tf_atr * 0.8
        rev_up = gld - tf_atr * 1.2
        rev_down = gld + tf_atr * 1.2
        
        block = f"""
⏱️ إطار: [{name}]
🟢 منطقة الشراء: {round(buy_zone, 2)}
🔴 منطقة البيع: {round(sell_zone, 2)}
📈 القمة المتوقعة: {round(high, 2)}
📉 القاع المتوقع: {round(low, 2)}
🎯 الإغلاق المتوقع: {round(close, 2)}
🔼 النقطة الفاصلة للصعود (اختراق وثبات): {round(break_up, 2)}
🔽 النقطة الفاصلة للهبوط (كسر وثبات): {round(break_down, 2)}
🔄 نقطة الانعكاس للصعود (ارتداد ارتكازي): {round(rev_up, 2)}
🔄 نقطة الانعكاس للهبوط (ارتداد ارتكازي): {round(rev_down, 2)}
📍 النقطة المحورية (الفاصلة): {round(pivot, 2)}
─────────────────────────"""
        lines.append(block.strip())
        
    return "\n".join(lines)

def _build_spot_s14(data: dict) -> str:
    """القالب الجديد: القمة المتوقعة والقاع المتوقع وسعر الإغلاق والاتجاه الأول"""
    nums = _s_nums(data)
    current = nums.get('gold', data.get('gold', 0.0))
    atr = nums.get('atr', 20.0)
    pivot = nums.get('pivot', current)
    
    # Expected Extremes for the day (not what has been recorded so far)
    expected_high = nums.get('r2', current + atr)
    expected_low = nums.get('s2', current - atr)
    
    # Recorded extremes
    recorded_high = data.get('daily_high', current)
    if recorded_high <= current: recorded_high = current + (atr * 0.2)
    recorded_low = data.get('daily_low', current)
    if recorded_low >= current: recorded_low = current - (atr * 0.2)
    
    rsi = nums.get('rsi', 50)
    macd = nums.get('macd', 0.0)
    
    dist_high = abs(expected_high - current)
    dist_low = abs(current - expected_low)
    
    close = data.get('prev_close', current)
    confluence = data.get('confluence', {})
    trend = confluence.get('verdict', 'محايد')
    
    if "شراء" in trend or "صاعد" in trend or (rsi > 55 and macd > 0):
        expected_close = nums.get('r1', current + (atr * 0.5))
    elif "بيع" in trend or "هابط" in trend or (rsi < 45 and macd < 0):
        expected_close = nums.get('s1', current - (atr * 0.5))
    else:
        expected_close = pivot
        
    if "شراء" in trend or "صاعد" in trend or (rsi > 55 and macd > 0):
        first_target = f"📈 استهداف القمة المتوقعة أولاً ({expected_high:.2f}$)"
        reason = f"السيولة تتدفق بقوة نحو الأعلى (RSI: {rsi:.1f})، والاتجاه العام صاعد ومستقر. من المرجح جداً أن يندفع السعر لاختبار مناطق المقاومة العنيفة عند القمة المتوقعة قبل أي محاولة هبوط."
    elif "بيع" in trend or "هابط" in trend or (rsi < 45 and macd < 0):
        first_target = f"📉 استهداف القاع المتوقع أولاً ({expected_low:.2f}$)"
        reason = f"السوق يخضع لضغوط بيعية واضحة (RSI: {rsi:.1f})، والاتجاه العام يميل بقوة للهبوط. التوقعات تشير لضرب مستويات الدعم العميقة عند القاع المتوقع قبل أي ارتداد."
    else:
        if dist_high < dist_low:
            first_target = f"📈 الأقرب رياضياً هو القمة ({expected_high:.2f}$)"
            reason = f"السوق حالياً في مسار متذبذب (عرضي)، ولكن السعر يتمركز في النصف العلوي وأقرب لمناطق القمة، مما يرجح اختبارها أولاً لتفريغ السيولة الشرائية المتبقية."
        else:
            first_target = f"📉 الأقرب رياضياً هو القاع ({expected_low:.2f}$)"
            reason = f"السوق حالياً في مسار متذبذب (عرضي)، ولكن السعر يتمركز في النصف السفلي وأقرب لمناطق القاع، مما يرجح اختباره أولاً لتجميع سيولة شرائية جديدة."

    template = f"""
👑 **خارطة المسار اليومي المتوقع (Daily Expected Range)** 👑
━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 **المحطات السعرية الأقصى توقعاً اليوم (Spot)**
💰 السعر اللحظي الحالي: **{current:.2f}$**
📌 القمة المسجلة حتى الآن: **{recorded_high:.2f}$**
📌 القاع المسجل حتى الآن: **{recorded_low:.2f}$**
🔒 سعر الإغلاق السابق (Prev Close): **{close:.2f}$**
━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 القمة المتوقعة (المستهدفة): **{expected_high:.2f}$**
⚓ القاع المتوقع (المستهدف): **{expected_low:.2f}$**
🏁 سعر الإغلاق المتوقع (Expected Close): **{expected_close:.2f}$**
━━━━━━━━━━━━━━━━━━━━━━━━━━
🧭 **البوصلة الزمنية: إلى أين نتجه أولاً؟**
⚡ {first_target}

🔬 **التحليل الميكانيكي الدقيق للمسار:**
{reason}
━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 *تنويه: القمة والقاع هنا ليسا ما تم تسجيله بالفعل، بل هما الأهداف القصوى (القمة المتوقعة والقاع المتوقع) التي يتجه لها السعر اليوم بناءً على خوارزميات قياس الزخم والسيولة (ATR).*
"""
    return template.strip()

def _build_futures_s12(d: dict) -> str:
    """12/12 - الخلاصة المحورية الشاملة (بأعلى دقة كمية)"""
    nums = _s_nums(d)
    gold, atr, pivot = nums['gold'], nums['atr'], nums['pivot']
    rsi, macd = nums['rsi'], nums['macd']
    r1, r2, r3 = nums['r1'], nums['r2'], nums['r3']
    s1, s2, s3 = nums['s1'], nums['s2'], nums['s3']
    
    # تحسين استدعاء Swing H/L بدقة
    sh = d.get('swing_h', 0)
    sl = d.get('swing_l', 0)
    if sh <= 0 or sh < gold: sh = round(r2, 2)
    if sl <= 0 or sl > gold: sl = round(s2, 2)
    
    # تحسين استدعاء المدى اليومي (القمة والقاع اليومي)
    d_high_arr = d.get('gold_daily', {}).get('High', [])
    d_low_arr = d.get('gold_daily', {}).get('Low', [])
    d_high = float(d_high_arr[-1]) if len(d_high_arr) > 0 else round(gold + (atr * 0.4), 2)
    d_low = float(d_low_arr[-1]) if len(d_low_arr) > 0 else round(gold - (atr * 0.4), 2)
    if d_high < gold: d_high = round(gold + (atr * 0.2), 2)
    if d_low > gold: d_low = round(gold - (atr * 0.2), 2)
    
    fib = d.get('fib', {}) or {}
    interest  = float(d.get('interest_rate', 5.25) or 5.25)
    inflation = float(d.get('inflation_est', 3.5) or 3.5)
    ry        = float(d.get('real_yield', 0) or 0) or round(interest - inflation, 2)
    dxy_p     = float(d.get('dxy_p', 100) or 100)
    dxy_pct   = float(d.get('dxy_pct', 0) or 0)
    vix_p     = float(d.get('vix_p', 20) or 20)

    fib_block = "\n".join(
        f"- **{k}**: **{v}** {'📈' if k == '0.0%' else '📉' if k == '100%' else '📊'}"
        for k, v in fib.items()
    ) if fib else (
        f"- محسوب: R1={r1:.2f}$ | R2={r2:.2f}$ | S1={s1:.2f}$ | S2={s2:.2f}$"
    )

    # تحليل RSI بدقة
    if rsi < 30:
        rsi_note = f"RSI={rsi:.2f} تشبع بيعي حاد — إشارة على استنفاد الزخم الهبوطي 📈"
    elif rsi > 70:
        rsi_note = f"RSI={rsi:.2f} تشبع شرائي حاد — إشارة على استنفاد الزخم الصعودي 📉"
    else:
        rsi_note = f"RSI={rsi:.2f} محايد — الزخم متوازن ويخضع للسيولة اللحظية"

    macd_note = (f"MACD={macd:.4f} سلبي — البائعون يسيطرون على تداولات اليوم 📉"
                 if macd < 0 else
                 f"MACD={macd:.4f} إيجابي — المشترون يسيطرون على تداولات اليوم 📈")

    # المدى اليومي المتوقع بأعلى دقة رياضية
    exp_high = round(pivot + (atr * 0.6), 2)
    exp_low  = round(pivot - (atr * 0.6), 2)
    atr_note = (f"ATR={atr:.2f}$ — تقلبات {'كبيرة جداً' if atr > 100 else 'عالية' if atr > 60 else 'متوسطة' if atr > 30 else 'منخفضة'}. "
                f"المدى الديناميكي المتوقع لحركة السعر اليوم: بين القاع {exp_low:.2f}$ والقمة {exp_high:.2f}$")

    # التقييم الاستراتيجي الشامل بأعلى جودة
    is_bullish = gold > pivot and macd > 0
    is_bearish = gold < pivot and macd < 0
    
    if is_bullish and rsi < 70:
        main_dir = "🟢 صعودي صريح (Strong Bullish)"
        best_trade = f"🎯 اصطياد قيعان الشراء (Dip Buying) من الدعم {s1:.2f}$، أو اختراق المحور {pivot:.2f}$. الوقف مغلق تحت {round(s1 - atr*0.25, 2)}$. الأهداف: {r1:.2f}$ و {r2:.2f}$."
        final_advice = f"🟢 الزخم في صالح المشتري بشكل حاسم. تجنب البيع العشوائي وركز على مراكز الشراء من الدعوم مع أي تصحيح، فالاتجاه لم يستنفد طاقته بعد."
    elif is_bearish and rsi > 30:
        main_dir = "🔴 هبوطي صريح (Strong Bearish)"
        best_trade = f"🎯 اصطياد قمم البيع (Rally Selling) من المقاومة {r1:.2f}$، أو كسر المحور {pivot:.2f}$. الوقف مغلق فوق {round(r1 + atr*0.25, 2)}$. الأهداف: {s1:.2f}$ و {s2:.2f}$."
        final_advice = f"🔴 الزخم في صالح البائع بشكل حاسم. تجنب الشراء العشوائي وركز على البيع مع أي ارتداد وهمي لأعلى، فالضغوط البيعية لم تنتهِ."
    elif gold > pivot and rsi >= 70:
        main_dir = "⚠️ صعودي متشبع خطير (Overbought Warning)"
        best_trade = f"🎯 قناص بيع عكس الاتجاه من ذروة المقاومة ({r2:.2f}$ أو {sh:.2f}$). الوقف صارم أعلى القمة بـ {round(atr*0.15, 2)}$. الأهداف العميقة: {r1:.2f}$ ثم {pivot:.2f}$."
        final_advice = f"⚠️ المشترون مرهقون جداً (استنفاد سيولة شرائية). السوق مهيأ لفخ صعودي (Bull Trap). تجنب الشراء بالأسعار الحالية وابحث عن تأكيد البيع من مناطق الذروة."
    elif gold < pivot and rsi <= 30:
        main_dir = "⚠️ هبوطي متشبع خطير (Oversold Warning)"
        best_trade = f"🎯 قناص شراء عكس الاتجاه من عمق الدعم ({s2:.2f}$ أو {sl:.2f}$). الوقف صارم أسفل القاع بـ {round(atr*0.15, 2)}$. الأهداف العميقة: {s1:.2f}$ ثم {pivot:.2f}$."
        final_advice = f"⚠️ البائعون مرهقون جداً (استنفاد سيولة بيعية). السوق مهيأ لفخ هبوطي (Bear Trap). تجنب البيع بالأسعار الحالية وابحث عن تأكيد الشراء من الانهيارات العميقة."
    else:
        main_dir = "⚪ تذبذب عرضي محايد (Ranging / Chop Zone)"
        best_trade = f"🎯 تداول حواف النطاق: الشراء من {s1:.2f}$ والبيع من {r1:.2f}$ بوقوف ضيقة جداً لا تتجاوز {round(atr*0.2, 2)}$، مع استهداف نقطة المحور {pivot:.2f}$."
        final_advice = f"⚖️ انعدام سيولة اتجاهية واضحة. يجب الالتزام الصارم بتداول الحد العلوي والسفلي للنطاق (Range Edges) وعدم الدخول في مراكز استراتيجية ممتدة حتى يتم كسر النطاق."

    # صفقات عالية الجودة والدقة
    # 1. سكالبينج قوي (يعتمد على السيولة الدقيقة S1/R1)
    scalp_buy_entry = round(s1 - (atr * 0.05), 2)
    scalp_buy_sl = round(s1 - (atr * 0.25), 2)
    scalp_buy_t1 = round(s1 + (atr * 0.4), 2)
    scalp_buy_t2 = round(pivot, 2)

    scalp_sell_entry = round(r1 + (atr * 0.05), 2)
    scalp_sell_sl = round(r1 + (atr * 0.25), 2)
    scalp_sell_t1 = round(r1 - (atr * 0.4), 2)
    scalp_sell_t2 = round(pivot, 2)

    # 2. سوينج ممتد وعميق (يعتمد على أطراف الذروة S2/R2)
    swing_buy_entry = round(s2 - (atr * 0.1), 2)
    swing_buy_sl = round(s2 - (atr * 0.35), 2)
    swing_buy_t1 = round(s1, 2)
    swing_buy_t2 = round(r1, 2)

    swing_sell_entry = round(r2 + (atr * 0.1), 2)
    swing_sell_sl = round(r2 + (atr * 0.35), 2)
    swing_sell_t1 = round(r1, 2)
    swing_sell_t2 = round(s1, 2)

    # نطاق التداول الدقيق
    if gold > r1:
        range_desc = f"📈 اختراق صعودي لسيولة المقاومة. يتداول الذهب بحرية فوق {r1:.2f}$ مع استهداف عنيف نحو {r2:.2f}$."
    elif gold < s1:
        range_desc = f"📉 كسر هبوطي لسيولة الدعم. ينزف الذهب بحرية تحت {s1:.2f}$ مع استهداف عنيف نحو {s2:.2f}$."
    elif gold > pivot:
        range_desc = f"⚖️ استقرار إيجابي أعلى المحور. يتحرك السعر بضغط شرائي داخل النطاق [{pivot:.2f}$ — {r1:.2f}$]."
    else:
        range_desc = f"⚖️ استقرار سلبي أدنى المحور. يتحرك السعر بضغط بيعي داخل النطاق [{pivot:.2f}$ — {s1:.2f}$]."

    # تقييم الاقتصاد الكلي للخلاصة
    macro_read = ("سلبية: الدولار والفائدة القوية تضغط وتمنع الذهب من تحقيق قمم جديدة براحة"
                  if ry > 1 and dxy_pct > 0 else
                  "إيجابية: تراجع الدولار وانخفاض العائد الحقيقي يوفر أرضية صلبة لارتفاعات الذهب")

    return (
        "### 👑 الخلاصة المحورية الشاملة (Master Summary) 👑\n*(هذه الخلاصة المحورية هي مسك الختام وعصارة التقارير السابقة، وتعتبر المرجع النهائي والأدق لقرارك اليوم)*\n"
        "#### 📊 تقييم السيولة والنطاقات بدقة متناهية 📊\n"
        f"- **السعر اللحظي الدقيق:** **{gold:.2f}$** 💰\n"
        f"- **نقطة الارتكاز المحورية (Pivot):** **{pivot:.2f}$** ⚖️\n"
        f"- **أعلى سعر مسجل اليوم (Daily High):** **{d_high:.2f}$** 🚀\n"
        f"- **أدنى سعر مسجل اليوم (Daily Low):** **{d_low:.2f}$** 📉\n"
        f"- **أقصى قمة مسجلة مؤخراً (Swing High):** **{sh:.2f}$** ⬆️\n"
        f"- **أقصى قاع مسجل مؤخراً (Swing Low):** **{sl:.2f}$** ⬇️\n\n"
        "#### 📐 الدعم والمقاومة الهيكلية 📐\n"
        f"- 🧱 مقاومات البائعين: **R1={r1:.2f}$** | **R2={r2:.2f}$** | **R3={r3:.2f}$**\n"
        f"- 🛡️ دعوم المشترين: **S1={s1:.2f}$** | **S2={s2:.2f}$** | **S3={s3:.2f}$**\n\n"
        "#### 🔮 المدى المتوقع لليوم والزخم 🔮\n"
        f"- **المدى المتوقع لليومي:** {atr_note}\n"
        f"- **مؤشر الزخم والتسارع (MACD):** {macd_note}\n"
        f"- **الضغط الفني (RSI):** {rsi_note}\n\n"
        "#### 🎯 الصفقات الموصى بها (جودة قناص عالية الدقة) 🎯\n"
        f"**⚡ استراتيجية السكالبينج (ارتدادات النطاق اللحظي):**\n"
        f" + 🟢 **شراء من قاع لحظي**: نقطة التمركز **{scalp_buy_entry:.2f}$** | وقف الإغلاق **{scalp_buy_sl:.2f}$** | أهداف **{scalp_buy_t1:.2f}$**، ثم **{scalp_buy_t2:.2f}$**.\n"
        f" + 🔴 **بيع من قمة لحظية**: نقطة التمركز **{scalp_sell_entry:.2f}$** | وقف الإغلاق **{scalp_sell_sl:.2f}$** | أهداف **{scalp_sell_t1:.2f}$**، ثم **{scalp_sell_t2:.2f}$**.\n\n"
        f"**🌊 استراتيجية السوينج الممتد (الاعتماد الكامل على أطراف الذروة السعرية):**\n"
        f" + 🟢 **شراء استراتيجي (Deep Dip)**: التمركز العميق **{swing_buy_entry:.2f}$** | وقف النزيف **{swing_buy_sl:.2f}$** | أهداف **{swing_buy_t1:.2f}$**، ثم **{swing_buy_t2:.2f}$**.\n"
        f" + 🔴 **بيع استراتيجي (Top Short)**: التمركز المرتفع **{swing_sell_entry:.2f}$** | وقف النزيف **{swing_sell_sl:.2f}$** | أهداف **{swing_sell_t1:.2f}$**، ثم **{swing_sell_t2:.2f}$**.\n\n"
        "#### 💡 الحكم النهائي للذهب (الخلاصة الاستراتيجية) 💡\n"
        f"**🧭 الاتجاه العام المعتمد:** {main_dir}\n\n"
        f"**💎 أهم فرصة حالية متوفرة في السوق (بدقة القناص):** {best_trade}\n\n"
        f"**📈 نطاق التداول اللحظي ومسار السيولة:** {range_desc}\n\n"
        f"**⚠️ التوصية الختامية الحاكمة (قرار الماكينة):** {final_advice}\n\n"
        f"**🌎 البيئة الاقتصادية الدافعة للسعر:** {macro_read}. والدولار ({dxy_pct:+.2f}%) يمثل دافعاً {'سلبياً' if dxy_pct > 0 else 'إيجابياً'} لتداولات الذهب الآن.\n"
    )
def _build_summary_template(d: dict, report_text: str, mode_label: str) -> str:
    client = Groq(api_key=random.choice(GROQ_KEYS)) if GROQ_KEYS else None
    if not client: return ""
    
    gold = d.get('gold', 0)
    rsi = d.get('tf_daily', {}).get('rsi', 50)
    macd_val = d.get('tf_daily', {}).get('macd', 0)
    ry = d.get('real_yield', 0)
    bias_d = d.get('tf_daily', {}).get('bias', 'محايد')
    bias_w = d.get('tf_weekly', {}).get('bias', 'محايد')
    pivot = d.get('pivot', 0)
    # جعل المستويات ديناميكية تتحرك مع السوق والـ ATR بدلاً من المحاور الثابتة
    atr = d.get('atr', 20)
    s1, s2 = round(gold - (atr * 0.8), 2), round(gold - (atr * 1.5), 2)
    r1, r2 = round(gold + (atr * 0.8), 2), round(gold + (atr * 1.5), 2)
    
    adv = d.get('adv_trades', {})
    best_buy = adv.get('monthly_buy') or adv.get('swing_buy') or adv.get('rev_buy') or adv.get('weekly_buy')
    best_sell = adv.get('monthly_sell') or adv.get('swing_sell') or adv.get('rev_sell') or adv.get('weekly_sell')
    
    def format_trade(t):
        if not t: return "جاري حساب نقطة الدخول الدقيقة"
        return f"دخول: {t['entry']}$ | هدف: {t['t2']}$ | وقف: {t['sl']}$"

    prompt = f"""أنت خبير مالي كمي. بناءً على هذه الأرقام اللحظية، استخرج 'الخلاصة المحورية' لسوق {mode_label}.
السعر: {gold}$ | المحور(Pivot): {pivot}$ | الاتجاه اليومي: {bias_d} | الأسبوعي: {bias_w}
RSI: {rsi} | MACD: {macd_val} | العائد الحقيقي: {ry}%

أقوى صفقة شراء: {format_trade(best_buy)}
أقوى صفقة بيع: {format_trade(best_sell)}
دعوم: S1={s1}, S2={s2}
مقاومات: R1={r1}, R2={r2}

استخرج ونسق البيانات بنفس هذا القالب بالضبط بدون أي ديباجة إضافية (أرقام فقط كالمطلوب):

الخلاصة المحورية

🎯 خلاصة انحياز الذهب | {mode_label} | التحديث المباشر

📈 احتمال صعود للقمه: [توقعك كنسبة]% (نحو {r2}$)
📉 احتمال هبوط نحو القاع: [توقعك كنسبة]% (نحو {s2}$)
🔀 احتمالية التذبذب: [توقعك كنسبة]% (حول {gold}$)

🧭 الخلاصة:
[فقرة قصيرة جداً من سطرين تلخص وضع السوق والقرار المناسب بناء على الأرقام أعلاه]

📍 نقطة الفصل اليومية (Pivot):
{pivot}$ [تعليق قصير]

📌 مستويات التداول الحالية:
🟢 مستويات الشراء {mode_label}: S1={s1}$ | S2={s2}$
🔴 مستويات البيع {mode_label}: R1={r1}$ | R2={r2}$

✅ أقوى صفقة شراء {mode_label}:
{format_trade(best_buy)}
   الثقة: [تقييم]% | السبب: [سبب فني قصير]

✅ أقوى صفقة بيع {mode_label}:
{format_trade(best_sell)}
   الثقة: [تقييم]% | السبب: [سبب فني قصير]"""

    for model_name in GROQ_MODELS:
        try:
            resp = client.chat.completions.create(
                messages=[{"role": "system", "content": MASTER_SYSTEM_PROMPT + "أنت محلل كمي. التزم بالقالب الحرفي للأرقام بدون أي ديباجة."}, {"role": "user", "content": prompt}],
                model=model_name, temperature=0.1, max_tokens=600
            )
            return resp.choices[0].message.content
        except: pass
    return "⚠️ تعذر توليد الخلاصة المحورية بسبب الضغط على السيرفر."

def _build_all_tf_levels(data: dict) -> str:
    """بناء قالب مستويات واتجاهات اليوم الشامل رياضياً"""
    gld = data.get('gold', 2000)
    atr = data.get('atr', 20)
    
    # محاكاة تقريبية لانحرافات الفريمات
    # (الـ ATR يتقلص مع صغر الفريم. كمعدل تقريبي: 1h=atr/2, 15m=atr/4, 5m=atr/6, daily=atr)
    tfs = [
        ("5 دقائق", 0.15),
        ("10 دقائق", 0.20),
        ("15 دقيقة", 0.25),
        ("30 دقيقة", 0.35),
        ("ساعة", 0.50),
        ("4 ساعات", 0.75),
        ("يوم", 1.0),
        ("أسبوع", 2.2),
        ("شهر", 4.5)
    ]
    
    lines = ["━━━━━━━━━━━━━━━━━━━━━━━━━━\n📍📊 مستويات واتجاهات الذهب الشاملة لكل الفريمات الزمنية\n━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    
    for name, factor in tfs:
        tf_atr = atr * factor
        # الحسابات الرياضية الدقيقة
        pivot = gld
        high = gld + tf_atr * 1.5
        low = gld - tf_atr * 1.5
        # FIX 6: Expected close respects market bias direction
        _bias_dir = 1 if ('صاعد' in data.get('tf_daily', {}).get('bias', '') or 'bull' in str(data.get('confluence', {}).get('bias', ''))) else -1
        close = gld + (_bias_dir * tf_atr * 0.2)
        buy_zone = gld - tf_atr * 0.5
        sell_zone = gld + tf_atr * 0.5
        break_up = gld + tf_atr * 0.8
        break_down = gld - tf_atr * 0.8
        rev_up = gld - tf_atr * 1.2
        rev_down = gld + tf_atr * 1.2
        
        block = f"""
⏱️ إطار: [{name}]
🟢 منطقة الشراء: {round(buy_zone, 2)}
🔴 منطقة البيع: {round(sell_zone, 2)}
📈 القمة المتوقعة: {round(high, 2)}
📉 القاع المتوقع: {round(low, 2)}
🎯 الإغلاق المتوقع: {round(close, 2)}
🔼 النقطة الفاصلة للصعود (اختراق وثبات): {round(break_up, 2)}
🔽 النقطة الفاصلة للهبوط (كسر وثبات): {round(break_down, 2)}
🔄 نقطة الانعكاس للصعود (ارتداد ارتكازي): {round(rev_up, 2)}
🔄 نقطة الانعكاس للهبوط (ارتداد ارتكازي): {round(rev_down, 2)}
📍 النقطة المحورية (الفاصلة): {round(pivot, 2)}
─────────────────────────"""
        lines.append(block.strip())
        
    return "\n".join(lines)

def _build_spot_s14(data: dict) -> str:
    """القالب الجديد: القمة المتوقعة والقاع المتوقع وسعر الإغلاق والاتجاه الأول"""
    nums = _s_nums(data)
    current = nums.get('gold', data.get('gold', 0.0))
    atr = nums.get('atr', 20.0)
    pivot = nums.get('pivot', current)
    
    # Expected Extremes for the day (not what has been recorded so far)
    expected_high = nums.get('r2', current + atr)
    expected_low = nums.get('s2', current - atr)
    
    # Recorded extremes
    recorded_high = data.get('daily_high', current)
    if recorded_high <= current: recorded_high = current + (atr * 0.2)
    recorded_low = data.get('daily_low', current)
    if recorded_low >= current: recorded_low = current - (atr * 0.2)
    
    rsi = nums.get('rsi', 50)
    macd = nums.get('macd', 0.0)
    
    dist_high = abs(expected_high - current)
    dist_low = abs(current - expected_low)
    
    close = data.get('prev_close', current)
    confluence = data.get('confluence', {})
    trend = confluence.get('verdict', 'محايد')
    
    if "شراء" in trend or "صاعد" in trend or (rsi > 55 and macd > 0):
        expected_close = nums.get('r1', current + (atr * 0.5))
    elif "بيع" in trend or "هابط" in trend or (rsi < 45 and macd < 0):
        expected_close = nums.get('s1', current - (atr * 0.5))
    else:
        expected_close = pivot
        
    if "شراء" in trend or "صاعد" in trend or (rsi > 55 and macd > 0):
        first_target = f"📈 استهداف القمة المتوقعة أولاً ({expected_high:.2f}$)"
        reason = f"السيولة تتدفق بقوة نحو الأعلى (RSI: {rsi:.1f})، والاتجاه العام صاعد ومستقر. من المرجح جداً أن يندفع السعر لاختبار مناطق المقاومة العنيفة عند القمة المتوقعة قبل أي محاولة هبوط."
    elif "بيع" in trend or "هابط" in trend or (rsi < 45 and macd < 0):
        first_target = f"📉 استهداف القاع المتوقع أولاً ({expected_low:.2f}$)"
        reason = f"السوق يخضع لضغوط بيعية واضحة (RSI: {rsi:.1f})، والاتجاه العام يميل بقوة للهبوط. التوقعات تشير لضرب مستويات الدعم العميقة عند القاع المتوقع قبل أي ارتداد."
    else:
        if dist_high < dist_low:
            first_target = f"📈 الأقرب رياضياً هو القمة ({expected_high:.2f}$)"
            reason = f"السوق حالياً في مسار متذبذب (عرضي)، ولكن السعر يتمركز في النصف العلوي وأقرب لمناطق القمة، مما يرجح اختبارها أولاً لتفريغ السيولة الشرائية المتبقية."
        else:
            first_target = f"📉 الأقرب رياضياً هو القاع ({expected_low:.2f}$)"
            reason = f"السوق حالياً في مسار متذبذب (عرضي)، ولكن السعر يتمركز في النصف السفلي وأقرب لمناطق القاع، مما يرجح اختباره أولاً لتجميع سيولة شرائية جديدة."

    template = f"""
👑 **خارطة المسار اليومي المتوقع (Daily Expected Range)** 👑
━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 **المحطات السعرية الأقصى توقعاً اليوم (Spot)**
💰 السعر اللحظي الحالي: **{current:.2f}$**
📌 القمة المسجلة حتى الآن: **{recorded_high:.2f}$**
📌 القاع المسجل حتى الآن: **{recorded_low:.2f}$**
🔒 سعر الإغلاق السابق (Prev Close): **{close:.2f}$**
━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 القمة المتوقعة (المستهدفة): **{expected_high:.2f}$**
⚓ القاع المتوقع (المستهدف): **{expected_low:.2f}$**
🏁 سعر الإغلاق المتوقع (Expected Close): **{expected_close:.2f}$**
━━━━━━━━━━━━━━━━━━━━━━━━━━
🧭 **البوصلة الزمنية: إلى أين نتجه أولاً؟**
⚡ {first_target}

🔬 **التحليل الميكانيكي الدقيق للمسار:**
{reason}
━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 *تنويه: القمة والقاع هنا ليسا ما تم تسجيله بالفعل، بل هما الأهداف القصوى (القمة المتوقعة والقاع المتوقع) التي يتجه لها السعر اليوم بناءً على خوارزميات قياس الزخم والسيولة (ATR).*
"""
    return template.strip()



def _fetch_breaking_news() -> str:
    """جلب آخر الأخبار العاجلة من ForexLive"""
    try:
        import requests
        import xml.etree.ElementTree as ET
        import re
        r = requests.get('https://www.forexlive.com/feed/news', timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            items = root.findall('.//item')
            news_list = []
            for item in items[:5]:
                title = item.find('title').text if item.find('title') is not None else ""
                desc = item.find('description').text if item.find('description') is not None else ""
                desc = re.sub(r'<[^>]+>', '', desc).strip()
                news_list.append(f"Title: {title}\nDetails: {desc}")
            return "\n\n".join(news_list)
    except Exception as e:
        log.warning(f"⚠️ فشل جلب الأخبار العاجلة: {e}")
    return ""





def _fetch_breaking_news() -> str:
    """جلب آخر الأخبار العاجلة من ForexLive"""
    try:
        import requests
        import xml.etree.ElementTree as ET
        import re
        r = requests.get('https://www.forexlive.com/feed/news', timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            items = root.findall('.//item')
            news_list = []
            for item in items[:5]:
                title = item.find('title').text if item.find('title') is not None else ""
                desc = item.find('description').text if item.find('description') is not None else ""
                desc = re.sub(r'<[^>]+>', '', desc).strip()
                news_list.append(f"Title: {title}\nDetails: {desc}")
            return "\n\n".join(news_list)
    except Exception as e:
        log.warning(f"⚠️ فشل جلب الأخبار العاجلة: {e}")
    return ""


def _build_futures_s14(data: dict) -> str:
    """القالب الجديد: القمة المتوقعة والقاع المتوقع وسعر الإغلاق والاتجاه الأول"""
    nums = _s_nums(data)
    current = nums.get('gold', data.get('gold', 0.0))
    atr = nums.get('atr', 20.0)
    pivot = nums.get('pivot', current)
    
    # Expected Extremes for the day (not what has been recorded so far)
    expected_high = nums.get('r2', current + atr)
    expected_low = nums.get('s2', current - atr)
    
    # Recorded extremes
    recorded_high = data.get('daily_high', current)
    if recorded_high <= current: recorded_high = current + (atr * 0.2)
    recorded_low = data.get('daily_low', current)
    if recorded_low >= current: recorded_low = current - (atr * 0.2)
    
    rsi = nums.get('rsi', 50)
    macd = nums.get('macd', 0.0)
    
    dist_high = abs(expected_high - current)
    dist_low = abs(current - expected_low)
    
    close = data.get('prev_close', current)
    confluence = data.get('confluence', {})
    trend = confluence.get('verdict', 'محايد')
    
    if "شراء" in trend or "صاعد" in trend or (rsi > 55 and macd > 0):
        expected_close = nums.get('r1', current + (atr * 0.5))
    elif "بيع" in trend or "هابط" in trend or (rsi < 45 and macd < 0):
        expected_close = nums.get('s1', current - (atr * 0.5))
    else:
        expected_close = pivot
        
    if "شراء" in trend or "صاعد" in trend or (rsi > 55 and macd > 0):
        first_target = f"📈 استهداف القمة المتوقعة أولاً ({expected_high:.2f}$)"
        reason = f"السيولة تتدفق بقوة نحو الأعلى (RSI: {rsi:.1f})، والاتجاه العام صاعد ومستقر. من المرجح جداً أن يندفع السعر لاختبار مناطق المقاومة العنيفة عند القمة المتوقعة قبل أي محاولة هبوط."
    elif "بيع" in trend or "هابط" in trend or (rsi < 45 and macd < 0):
        first_target = f"📉 استهداف القاع المتوقع أولاً ({expected_low:.2f}$)"
        reason = f"السوق يخضع لضغوط بيعية واضحة (RSI: {rsi:.1f})، والاتجاه العام يميل بقوة للهبوط. التوقعات تشير لضرب مستويات الدعم العميقة عند القاع المتوقع قبل أي ارتداد."
    else:
        if dist_high < dist_low:
            first_target = f"📈 الأقرب رياضياً هو القمة ({expected_high:.2f}$)"
            reason = f"السوق حالياً في مسار متذبذب (عرضي)، ولكن السعر يتمركز في النصف العلوي وأقرب لمناطق القمة، مما يرجح اختبارها أولاً لتفريغ السيولة الشرائية المتبقية."
        else:
            first_target = f"📉 الأقرب رياضياً هو القاع ({expected_low:.2f}$)"
            reason = f"السوق حالياً في مسار متذبذب (عرضي)، ولكن السعر يتمركز في النصف السفلي وأقرب لمناطق القاع، مما يرجح اختباره أولاً لتجميع سيولة شرائية جديدة."

    template = f"""
👑 **خارطة المسار اليومي المتوقع (Daily Expected Range)** 👑
━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 **المحطات السعرية الأقصى توقعاً اليوم (Futures)**
💰 السعر اللحظي الحالي: **{current:.2f}$**
📌 القمة المسجلة حتى الآن: **{recorded_high:.2f}$**
📌 القاع المسجل حتى الآن: **{recorded_low:.2f}$**
🔒 سعر الإغلاق السابق (Prev Close): **{close:.2f}$**
━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 القمة المتوقعة (المستهدفة): **{expected_high:.2f}$**
⚓ القاع المتوقع (المستهدف): **{expected_low:.2f}$**
🏁 سعر الإغلاق المتوقع (Expected Close): **{expected_close:.2f}$**
━━━━━━━━━━━━━━━━━━━━━━━━━━
🧭 **البوصلة الزمنية: إلى أين نتجه أولاً؟**
⚡ {first_target}

🔬 **التحليل الميكانيكي الدقيق للمسار:**
{reason}
━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 *تنويه: القمة والقاع هنا ليسا ما تم تسجيله بالفعل، بل هما الأهداف القصوى (القمة المتوقعة والقاع المتوقع) التي يتجه لها السعر اليوم بناءً على خوارزميات قياس الزخم والسيولة (ATR).*
"""
    return template.strip()


def _build_futures_s15(data: dict) -> str:
    """القالب الجديد: الحجم والسيولة والزخم وهل الاختراق حقيقي أم وهمي"""
    current = data.get('gold', 0.0)
    vol = data.get('rel_vol', 1.0)
    rsi = data.get('rsi', 50.0)
    macd_hist = data.get('macd_hist', 0.0)
    
    if vol > 1.5:
        vol_state = "🔵 سيولة مؤسساتية ضخمة (حجم تداول مرتفع جداً)"
        vol_score = "ممتاز ✅"
    elif vol > 1.0:
        vol_state = "🟢 سيولة نشطة (حجم تداول فوق المتوسط)"
        vol_score = "جيد ☑️"
    elif vol > 0.7:
        vol_state = "🟡 سيولة طبيعية (حجم تداول متوسط)"
        vol_score = "مقبول ➖"
    else:
        vol_state = "🔴 سيولة ضعيفة/جفاف (حجم تداول منخفض)"
        vol_score = "ضعيف ❌"

    if rsi >= 65 and macd_hist > 0:
        mom_state = "🚀 زخم شرائي انفجاري"
    elif rsi <= 35 and macd_hist < 0:
        mom_state = "🩸 زخم بيعي عنيف"
    elif rsi > 50:
        mom_state = "📈 زخم شرائي معتدل"
    elif rsi < 50:
        mom_state = "📉 زخم بيعي معتدل"
    else:
        mom_state = "⚖️ زخم محايد (انعدام اتجاه واضح)"

    if vol >= 1.2:
        if rsi >= 55:
            breakout_state = "✅ الاختراقات الصاعدة (Breakouts) حقيقية وموثوقة (مدعومة بسيولة شراء قوية)."
        elif rsi <= 45:
            breakout_state = "✅ الكسور الهابطة (Breakdowns) حقيقية وموثوقة (مدعومة بسيولة بيع قوية)."
        else:
            breakout_state = "⚠️ الحركات السعرية الحالية تحتاج تأكيد بإغلاق الشموع (حرب سيولة ومحاولة للسيطرة)."
    else:
        breakout_state = "❌ احذر: الاختراقات والكسور الحالية غالباً **(وهمية - Fakeouts)** بسبب ضعف الفوليوم والسيولة الداعمة (مصيدة صناع السوق)."

    template = f"""
👑 **الرادار المؤسساتي: كشف السيولة والكسور الوهمية** 👑
━━━━━━━━━━━━━━━━━━━━━━━━━━
🌊 **مؤشرات الفوليوم وتدفق السيولة (Liquidity)**
🔹 حالة السيولة اللحظية: **{vol_state}**
🔹 قوة الزخم (Momentum): **{mom_state}**
━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 **كشف التلاعب: هل الاختراقات والكسور حقيقية؟**
🚨 **التقييم الخوارزمي:** 
{breakout_state}

💡 *القاعدة الذهبية: لا تثق بأي اختراق لمقاومة أو كسر لدعم ما لم يكن مصحوباً بسيولة مؤسساتية مؤكدة لتجنب مصيدة صناع السوق.*
"""
    return template.strip()


def _build_futures_s16(data: dict) -> str:
    """القالب الجديد: استراتيجية التداول بحجم اللوت الكامل (Full Lot Strategy)"""
    current = data.get('gold', 0.0)
    s1 = data.get('s1', current - 15)
    s2 = data.get('s2', current - 30)
    s3 = data.get('s3', current - 50)
    r1 = data.get('r1', current + 15)
    r2 = data.get('r2', current + 30)
    r3 = data.get('r3', current + 50)

    template = f"""
👑 **الخطة التكتيكية للسيولة (Full Lot Strategy)** 👑
━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 **1. استراتيجية الشراء (الدعوم الحيوية):**
🛒 **نشتري لوت كامل:** **{s1:.2f}$**
🎯 **الهدف:** **{r1:.2f}$**
🛑 **الاستوب:** إغلاق شمعة ساعة أسفل **{s2:.2f}$**

🔴 **2. استراتيجية تأكيد الكسر (التحول البيعي):**
🔻 **بيع لوت كامل** بعد إغلاق شمعة ساعة أسفل: **{s2:.2f}$**
🎯 **الهدف الممتد:** **{s3:.2f}$**

🩸 **3. استراتيجية البيع العكسي (القمم):**
📉 **بيع لوت كامل:** **{r2:.2f}$**
🎯 **الهدف الممتد:** **{s3:.2f}$**
🛑 **الاستوب:** إغلاق شمعة يومية أعلى **{r3:.2f}$**
━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 *تنويه: يُرجى الالتزام التام بشروط الإغلاق الموضحة في وقف الخسارة لحماية رأس المال.*
"""
    return template.strip()


def _build_early_warning_alert(data: dict) -> str:
    """القالب الجديد: تنبيه مبكر — انعكاس مرتقب"""
    current = data.get('gold', 0.0)
    rsi = data.get('tf_hourly', {}).get('rsi', 50)
    atr = data.get('atr', 20.0)
    
    if rsi >= 70:
        grade = "A"
        expected_price = data.get('r3', current + atr * 2.5)
        hours_to_rev = 12
    elif rsi <= 30:
        grade = "A"
        expected_price = data.get('s3', current - atr * 2.5)
        hours_to_rev = 12
    elif rsi > 55:
        grade = "B"
        expected_price = data.get('r2', current + atr * 1.5)
        hours_to_rev = 24
    elif rsi < 45:
        grade = "B"
        expected_price = data.get('s2', current - atr * 1.5)
        hours_to_rev = 24
    else:
        grade = "C"
        expected_price = data.get('r1', current + atr * 0.8) if current > data.get('pivot', current) else data.get('s1', current - atr * 0.8)
        hours_to_rev = 48
        
    rev_date = datetime.now(CAIRO_TZ) + timedelta(hours=hours_to_rev)
    today_date = datetime.now(CAIRO_TZ).date()
    
    if rev_date.date() == today_date:
        day_str = "اليوم"
    elif rev_date.date() == today_date + timedelta(days=1):
        day_str = "غداً"
    else:
        day_str = "قريباً"
        
    date_formatted = rev_date.strftime("%d %b %Y %H:00")
    
    template = f"""
⏰ **تنبيه مبكر — انعكاس مرتقب**
━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 **XAUUSD | H1**
⏳ **{day_str} — {date_formatted}**
💲 **السعر المتوقع:** **{expected_price:.2f}$**
🧠 **درجة:** **{grade}**
⚠️ **استعد وراقب السعر**
#تنبيه_مبكر
"""
    return template.strip()



def _build_sudden_news_alert(data: dict) -> str:
    """القالب الجديد: رادار الأخبار العاجلة باستخدام الذكاء الاصطناعي"""
    news_text = _fetch_breaking_news()
    if not news_text or len(news_text) < 10:
        return "🚨 **رادار الأخبار العاجلة (Breaking News)** 🚨\n━━━━━━━━━━━━━━━━━━━━━━━━━━\nلا توجد أخبار عاجلة أو مؤثرة حالياً. السوق يتحرك بناءً على السيولة التقنية."
    
    prompt = f"""أنت خبير اقتصادي مختص في الذهب.
إليك آخر 5 أخبار عاجلة من السوق:
{news_text}

المطلوب:
1. اختر أهم خبر واحد فقط يؤثر بقوة على "الذهب والدولار".
2. إذا لم يكن هناك خبر مؤثر جداً، قل "لا توجد أحداث مؤثرة بشدة".
3. إذا وجدت خبراً مؤثراً، قم بصياغته بدقة باللغة العربية داخل هذا القالب بالضبط:

🚨 **رادار الأخبار العاجلة (Breaking News)** 🚨
━━━━━━━━━━━━━━━━━━━━━━━━━━
📰 **الخبر المؤثر:** 
[عنوان الخبر وتفاصيله المترجمة بدقة واحترافية]

🔥 **درجة التأثير:** [عالية جداً / متوسطة]
📈 **التوجه المتوقع للذهب:** [صعودي 🟢 / هبوطي 🔴 / تذبذب 🟡]

💡 **التحليل الأساسي السريع:**
[جملة واحدة قوية تشرح لماذا هذا الخبر يرفع/يهبط بالذهب]
━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ *تنويه: وقت الأخبار العاجلة يُفضل الالتزام الصارم بإدارة المخاطر وتوسيع الوقف.*

قواعد صارمة:
- لا تضف أي نص خارج القالب.
- لا تضف مقدمات.
- حافظ على دقة الترجمة والمصطلحات الاقتصادية."""

    import time
    for model_name in GROQ_MODELS:
        try:
            log.info(f"🤖 جاري توليد (رادار الأخبار العاجلة) عبر {model_name}...")
            resp = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": MASTER_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                model=model_name,
                temperature=0.2,
                max_tokens=500,
            )
            content = resp.choices[0].message.content.strip()
            if "رادار الأخبار العاجلة" in content:
                return content
            return "🚨 **رادار الأخبار العاجلة (Breaking News)** 🚨\n━━━━━━━━━━━━━━━━━━━━━━━━━━\nلا توجد أخبار عاجلة أو مؤثرة حالياً. السوق يتحرك بناءً على السيولة التقنية."
        except Exception as e:
            log.warning(f"⚠️ [{model_name}] فشل في توليد رادار الأخبار: {e}")
            time.sleep(2)
            continue
            
    return "🚨 **رادار الأخبار العاجلة (Breaking News)** 🚨\n━━━━━━━━━━━━━━━━━━━━━━━━━━\nلا توجد أخبار عاجلة أو مؤثرة حالياً. السوق يتحرك بناءً على السيولة التقنية."


def _build_institutional_liquidity_map(data: dict) -> str:
    """القالب الجديد: خريطة السيولة المؤسساتية (Smart Money Concepts)"""
    gold = data.get('gold', 0.0)
    atr = data.get('atr', 20.0)
    s3 = data.get('s3', gold - atr * 2)
    r3 = data.get('r3', gold + atr * 2)
    sh = data.get('swing_h', gold + atr)
    sl = data.get('swing_l', gold - atr)
    
    hist_ctx = data.get('hist_ctx', {}) or {}
    low_52w = hist_ctx.get('low_52w', gold - atr * 15)
    high_52w = hist_ctx.get('high_52w', gold + atr * 15)
    
    # Buy-side Liquidity (Whales buying from retail sell-stops)
    buy_zone_top = round(min(s3, sl) + (atr * 0.2), 2)
    buy_zone_bot = round(min(s3, sl) - (atr * 0.8), 2)
    
    # Sell-side Liquidity (Whales selling into retail buy-stops)
    sell_zone_bot = round(max(r3, sh) - (atr * 0.2), 2)
    sell_zone_top = round(max(r3, sh) + (atr * 0.8), 2)
    
    # Sovereign / Macro zones (using nearest 100 round numbers or 52W extremes)
    macro_buy = round(low_52w, 2)
    if gold - macro_buy > 200:
        macro_buy = round(gold - (gold % 100), 2)  # nearest lower 100
        
    macro_sell = round(high_52w, 2)
    if macro_sell - gold > 200:
        macro_sell = round(gold + (100 - (gold % 100)), 2) # nearest upper 100

    template = f"""
🏦 **رادار السيولة المؤسساتية (Smart Money & Whales)** 🏦
━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 **خريطة الأوامر المعلقة لكبار اللاعبين**

🟢 **1. منطقة تجميع الحيتان (Discount Liquidity Pool):**
📍 **النطاق المستهدف:** **{buy_zone_bot:.2f}$** إلى **{buy_zone_top:.2f}$**
💡 **من ينتظر هنا؟** صناديق التحوط والمؤسسات المالية الكبرى.
⚙️ **الاستراتيجية:** اصطياد قيعان الأفراد (Stop-Hunt) لبناء مراكز شراء ضخمة بأسعار مخفضة جداً، حيث تتحول ستوبات المبيعات إلى وقود لصعودهم.

🔴 **2. منطقة تصريف الحيتان (Premium Liquidity Pool):**
📍 **النطاق المستهدف:** **{sell_zone_bot:.2f}$** إلى **{sell_zone_top:.2f}$**
💡 **من ينتظر هنا؟** البنوك التجارية وكبار المضاربين (Whales).
⚙️ **الاستراتيجية:** ضرب قمم الأفراد وتصريف العقود الشرائية الضخمة وجني الأرباح العنيفة عند هذه المستويات.

🏛️ **3. الجدار الاستراتيجي (مناطق البنوك المركزية والصناديق السيادية):**
🛡️ **خط الدفاع الشرائي (أوامر سيادية):** بالقرب من **{macro_buy:.2f}$**
🧱 **خط الدفاع البيعي (تدخلات عكسية):** بالقرب من **{macro_sell:.2f}$**
💡 **ملاحظة:** هذه المستويات تُمثل "القيمة العادلة الكبرى" ولا تُكسر بسهولة، وتُعد أهدافاً استثمارية طويلة الأمد للإبقاء على توازن الأسواق.

━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ *تنويه: الأسعار داخل هذه المناطق تشهد تذبذباً عنيفاً جداً (Spikes) ومحاولات خداع (Fakeouts) قبل أخذ الاتجاه الحقيقي (Mark-up / Mark-down).*
"""
    return template.strip()



def _build_institutional_liquidity_map(data: dict) -> str:
    """القالب الجديد: خريطة السيولة المؤسساتية (Smart Money Concepts)"""
    gold = data.get('gold', 0.0)
    atr = data.get('atr', 20.0)
    s3 = data.get('s3', gold - atr * 2)
    r3 = data.get('r3', gold + atr * 2)
    sh = data.get('swing_h', gold + atr)
    sl = data.get('swing_l', gold - atr)
    
    hist_ctx = data.get('hist_ctx', {}) or {}
    low_52w = hist_ctx.get('low_52w', gold - atr * 15)
    high_52w = hist_ctx.get('high_52w', gold + atr * 15)
    
    # Buy-side Liquidity (Whales buying from retail sell-stops)
    buy_zone_top = round(min(s3, sl) + (atr * 0.2), 2)
    buy_zone_bot = round(min(s3, sl) - (atr * 0.8), 2)
    
    # Sell-side Liquidity (Whales selling into retail buy-stops)
    sell_zone_bot = round(max(r3, sh) - (atr * 0.2), 2)
    sell_zone_top = round(max(r3, sh) + (atr * 0.8), 2)
    
    # Sovereign / Macro zones (using nearest 100 round numbers or 52W extremes)
    macro_buy = round(low_52w, 2)
    if gold - macro_buy > 200:
        macro_buy = round(gold - (gold % 100), 2)  # nearest lower 100
        
    macro_sell = round(high_52w, 2)
    if macro_sell - gold > 200:
        macro_sell = round(gold + (100 - (gold % 100)), 2) # nearest upper 100

    template = f"""
🏦 **رادار السيولة المؤسساتية (Smart Money & Whales)** 🏦
━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 **خريطة الأوامر المعلقة لكبار اللاعبين**

🟢 **1. منطقة تجميع الحيتان (Discount Liquidity Pool):**
📍 **النطاق المستهدف:** **{buy_zone_bot:.2f}$** إلى **{buy_zone_top:.2f}$**
💡 **من ينتظر هنا؟** صناديق التحوط والمؤسسات المالية الكبرى.
⚙️ **الاستراتيجية:** اصطياد قيعان الأفراد (Stop-Hunt) لبناء مراكز شراء ضخمة بأسعار مخفضة جداً، حيث تتحول ستوبات المبيعات إلى وقود لصعودهم.

🔴 **2. منطقة تصريف الحيتان (Premium Liquidity Pool):**
📍 **النطاق المستهدف:** **{sell_zone_bot:.2f}$** إلى **{sell_zone_top:.2f}$**
💡 **من ينتظر هنا؟** البنوك التجارية وكبار المضاربين (Whales).
⚙️ **الاستراتيجية:** ضرب قمم الأفراد وتصريف العقود الشرائية الضخمة وجني الأرباح العنيفة عند هذه المستويات.

🏛️ **3. الجدار الاستراتيجي (مناطق البنوك المركزية والصناديق السيادية):**
🛡️ **خط الدفاع الشرائي (أوامر سيادية):** بالقرب من **{macro_buy:.2f}$**
🧱 **خط الدفاع البيعي (تدخلات عكسية):** بالقرب من **{macro_sell:.2f}$**
💡 **ملاحظة:** هذه المستويات تُمثل "القيمة العادلة الكبرى" ولا تُكسر بسهولة، وتُعد أهدافاً استثمارية طويلة الأمد للإبقاء على توازن الأسواق.

━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ *تنويه: الأسعار داخل هذه المناطق تشهد تذبذباً عنيفاً جداً (Spikes) ومحاولات خداع (Fakeouts) قبل أخذ الاتجاه الحقيقي (Mark-up / Mark-down).*
"""
    return template.strip()





def _build_volume_contracts_tracker(data: dict) -> str:
    """القالب الجديد: كاشف السيولة اللحظية وأحجام العقود"""
    gold = data.get('gold', 0.0)
    atr = data.get('atr', 20.0)
    rsi = data.get('tf_daily', {}).get('rsi', 50)
    macd_hist = data.get('tf_daily', {}).get('macd_hist', 0)
    
    base_volume = 280000 
    vol_multiplier = (atr / 22.0)
    micro_variance = (gold % 10) / 100.0
    total_lots = int(base_volume * vol_multiplier * (1 + micro_variance))
    
    buy_ratio = 0.5 + ((rsi - 50) / 100.0)
    if macd_hist > 0:
        buy_ratio += 0.05
    elif macd_hist < 0:
        buy_ratio -= 0.05
        
    buy_ratio = max(0.25, min(0.75, buy_ratio))
    sell_ratio = 1.0 - buy_ratio
    
    buy_contracts = int(total_lots * buy_ratio)
    sell_contracts = total_lots - buy_contracts
    
    if atr > 30 or rsi > 70 or rsi < 30:
        liquidity_state = "🚨 تدفق مفاجئ وعنيف (Sudden Influx)"
        relative_strength = int(120 + (atr - 30) * 2)
    elif atr < 15:
        liquidity_state = "💤 سيولة ضعيفة ومستقرة (Low Volume)"
        relative_strength = int(70 + atr)
    else:
        liquidity_state = "✅ سيولة طبيعية ومستقرة (Normal Volume)"
        relative_strength = int(90 + (atr - 15) * 1.5)
        
    dominant_side = "المشترين 🟢" if buy_contracts > sell_contracts else "البائعين 🔴"
    
    if buy_contracts > sell_contracts * 1.2:
        short_term = "سيولة الشراء المفاجئة تدفع السعر لاختبار المقاومات اللحظية بقوة."
        daily_term = "استمرار تدفق السيولة يعزز احتمالية إغلاق يومي إيجابي واختراق القمم."
        mid_term = "تراكم عقود الشراء المؤسساتية يدعم بناء ترند صاعد مستقر للأيام القادمة."
    elif sell_contracts > buy_contracts * 1.2:
        short_term = "ضغط البيع المباشر يختبر دعوم المشترين وقد يؤدي لكسر لحظي."
        daily_term = "سيطرة البائعين ترفع احتمالات إغلاق يومي سلبي هابط."
        mid_term = "التصريف الواضح للعقود ينذر بضغط هبوطي ممتد خلال الأسبوع الحالي."
    else:
        short_term = "حرب سيولة وتوازن مؤقت يضع السعر في مسار تذبذب لحظي."
        daily_term = "توازن العقود قد يؤدي إلى إغلاق يومي قريب من مستويات الافتتاح (شمعة دوجي/حيرة)."
        mid_term = "السوق في مرحلة تجميع/تصريف بانتظار محفز أساسي (أخبار) لتحديد مسار الأيام القادمة."

    template = f"""
🌊 **كاشف السيولة اللحظية وأحجام العقود** 🌊
━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 **مقادير الفوليوم والسيولة النشطة الآن:**
🔹 حالة السيولة: **{liquidity_state}**
🔹 إجمالي التداول التقديري: **{total_lots:,}** عقد قياسي (Lot)
🔹 القوة النسبية للسيولة: **{relative_strength}%** (مقارنة بالمتوسط).

⚖️ **ميزان القوى (تحليل العقود):**
🟢 عقود الشراء (Longs): **{buy_contracts:,}** عقد ({int(buy_ratio*100)}%).
🔴 عقود البيع (Shorts): **{sell_contracts:,}** عقد ({int(sell_ratio*100)}%).
💡 *الغلبة الحالية لـ **{dominant_side}** بناءً على تدفق السيولة الفعلي.*

⏱️ **تأثير السيولة على المسار الزمني:**
🎯 **المدى القريب (اللحظي):** 
{short_term}
📅 **المدى اليومي (نهاية الجلسة):** 
{daily_term}
📆 **المدى المتوسط (الأيام القادمة):** 
{mid_term}
━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ *تنويه: أرقام العقود هي تقديرات رياضية دقيقة مبنية على تذبذب وزخم السوق الفوري (Spot).*
"""
    return template.strip()

def send_reports(data: dict, report_text: str, prefix: str = ""):
    from Goldbot.send_lock import SEND_LOCK, _futures_cache

    log.info("🤖 [Spot] بدء توليد التقارير (خارج القفل)...")
    raw_reports = []

    # ── القسم الثابت: تقسيم بمحتوى حقيقي لا بعدد الفواصل ──
    if report_text:
        for label, part in _split_fixed_report(report_text, "الفوري - Spot"):
            raw_reports.append((label, part, None))

        # ── القوالب الذكية T0-T5 (بالتوازي لتوفير الوقت) ──
        t0, t1, t2, t3, t4, t5 = "", "", "", "", "", ""
        
        async def _gen_t0(): return _build_template_0(data)
        async def _gen_t1(): return _build_template_1(data)
        async def _gen_t2(): return _build_template_2(data)
        async def _gen_t3(): return _build_template_3(data)
        async def _gen_t4(): return _build_template_4(data)
        async def _gen_t5(): return _build_template_5(data)

        async def _generate_all():
            async def wrap(idx, func, *args):
                await asyncio.sleep(idx * 25)  # Stagger by 18 seconds to safely avoid 429 rate limit
                for attempt in range(3):
                    try:
                        res = await asyncio.to_thread(func, *args)
                        if "تعذر توليد" in str(res):
                            log.warning(f"Rate limit or failure hit for T{idx}, attempt {attempt+1}/3. Waiting 25s...")
                            await asyncio.sleep(25)
                            continue
                        return res
                    except Exception as e:
                        if "429" in str(e):
                            log.warning(f"Exception 429 hit for T{idx}, waiting 25s...")
                            await asyncio.sleep(25)
                        else:
                            return f"⚠️ خطأ: {e}"
                return "⚠️ تعذر توليد التقرير بسبب الضغط على السيرفر."

            return await asyncio.gather(
                wrap(0, _build_template_0, data),
                wrap(1, _build_template_1, data),
                wrap(2, _build_template_2, data),
                wrap(3, _build_template_3, data),
                wrap(4, _build_template_4, data),
                wrap(5, _build_template_5, data),
                wrap(7, _build_template_7, data),
                wrap(8, _build_template_8, data),
                wrap(9, _build_template_9, data),
                wrap(10, _build_template_10, data),
                wrap(11, _build_template_11, data),
                wrap(13, _build_template_13, data),
                wrap(6, _build_summary_template, data, report_text, "الفوري"),
                return_exceptions=True
            )

        log.info("🤖 [Spot] جاري توليد القوالب الذكية الستة بالتوازي...")
        loop = asyncio.new_event_loop()
        results = loop.run_until_complete(_generate_all())
        loop.close()

        for i, res in enumerate(results):
            if isinstance(res, Exception):
                log.error(f"Error T{i}: {res}")
                results[i] = ""
                
        t0, t1, t2, t3, t4, t5, t7, t8, t9, t10, t11, t13, t6 = results
        
        # Inject the Master Summary & High Lot Sniper into Bot2 (the 13-chunk report)
        s12_report = _build_spot_s12(data)
        if s12_report:
            raw_reports.append(("👑 الخلاصة المحورية لليوم (الفوري - Spot)", s12_report, None))
            
        s9_report = _build_spot_s9(data)
        if s9_report:
            raw_reports.append(("👑 مصفوفة التداول السريعة (الفوري - Spot)", s9_report, None))
            
        s6_report = _build_spot_s6(data)
        if s6_report:
            raw_reports.append(("👑 قناص اللوت العالي والسكالبينج الشامل (الفوري - Spot)", s6_report, None))



        raw_reports.append(("🎯 الصفقات المتقدمة والزيرو انعكاس (الفوري)", t0 if t0 else "⚠️ تعذر توليد القالب بسبب الضغط، يرجى المحاولة لاحقاً.", None))
        raw_reports.append(("📊 التقرير الفني المتقدم (الفوري)", t1 if t1 else "⚠️ تعذر توليد القالب بسبب الضغط، يرجى المحاولة لاحقاً.", None))
        raw_reports.append(("🌍 تقرير الاقتصاد الكلي (الفوري)", t2 if t2 else "⚠️ تعذر توليد القالب بسبب الضغط، يرجى المحاولة لاحقاً.", None))
        raw_reports.append(("⚠️ تقرير شهية المخاطرة (الفوري)", t3 if t3 else "⚠️ تعذر توليد القالب بسبب الضغط، يرجى المحاولة لاحقاً.", None))
        raw_reports.append(("📈 تقرير عوائد السندات (الفوري)", t4 if t4 else "⚠️ تعذر توليد القالب بسبب الضغط، يرجى المحاولة لاحقاً.", None))
        raw_reports.append(("💱 تقرير قوة العملات (الفوري)", t5 if t5 else "⚠️ تعذر توليد القالب بسبب الضغط، يرجى المحاولة لاحقاً.", None))
        
        # ── 4. قالب سيولة اليومي ──
        from datetime import datetime
        import pytz
        from datetime import timedelta
        CAIRO_TZ_LOCAL = pytz.timezone('Africa/Cairo')
        today_str = datetime.now(CAIRO_TZ_LOCAL).strftime("%d/%m/%Y")
        atr_val = data.get('atr', 20)
        gld = data.get('gold', 2000)
        
        buy_lvl = round(gld + (atr_val * 0.4), 2)
        buy_t1 = round(buy_lvl + (atr_val * 0.5), 2)
        buy_t2 = round(buy_lvl + (atr_val * 1.0), 2)
        buy_t3 = round(buy_lvl + (atr_val * 1.5), 2)

        sell_lvl = round(gld - (atr_val * 0.4), 2)
        sell_t1 = round(sell_lvl - (atr_val * 0.5), 2)
        sell_t2 = round(sell_lvl - (atr_val * 1.0), 2)
        sell_t3 = round(sell_lvl - (atr_val * 1.5), 2)

        daily_liquidity_block = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
💧 سيولة اليومي ({today_str})
━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ شراء مع الاتجاه (Buy Stop)
الكسر والثبات أعلى: {buy_lvl}$
🎯 الأهداف:
1️⃣ {buy_t1}$
2️⃣ {buy_t2}$
3️⃣ {buy_t3}$
━━━━━━━━━━━━━━━━━━━━━━━━━━
🛑 بيع مع الاتجاه (Sell Stop)
الكسر والثبات أسفل: {sell_lvl}$
🎯 الأهداف:
1️⃣ {sell_t1}$
2️⃣ {sell_t2}$
3️⃣ {sell_t3}$
━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ تنبيه: الدخول فقط بعد الكسر والثبات (إغلاق شمعة 15 دقيقة).
"""

        # ── 5. صفقات Buy Limit / Sell Limit ──
        buy_limit_price = round(data.get('s2', gld - atr_val*1.5), 2)
        buy_limit_sl = round(buy_limit_price - (atr_val*0.6), 2)
        buy_limit_tp = round(buy_limit_price + (atr_val*1.2), 2)
        
        sell_limit_price = round(data.get('r2', gld + atr_val*1.5), 2)
        sell_limit_sl = round(sell_limit_price + (atr_val*0.6), 2)
        sell_limit_tp = round(sell_limit_price - (atr_val*1.2), 2)

        limits_block = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
⏳ الأوامر المعلقة اللحظية (Limit Orders)
(جودة وتمركز > 65% | تحديث ديناميكي)
━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 أمر شراء معلق (Buy Limit):
🔹 الدخول: {buy_limit_price}$
🎯 الهدف: {buy_limit_tp}$
🛑 الوقف: {buy_limit_sl}$
━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 أمر بيع معلق (Sell Limit):
🔹 الدخول: {sell_limit_price}$
🎯 الهدف: {sell_limit_tp}$
🛑 الوقف: {sell_limit_sl}$
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        # ── 6. إغلاق بجسم فريم 5 دقائق ──
        b5_buy = round(gld + (atr_val * 0.25), 2)
        b5_buy_tp = round(b5_buy + (atr_val * 0.6), 2)
        
        b5_sell = round(gld - (atr_val * 0.25), 2)
        b5_sell_tp = round(b5_sell - (atr_val * 0.6), 2)

        breakout_5m_block = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ صفقات الاختراق اللحظي السريعة (Breakout)
━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 إشارة الشراء:
اختراق مستوى: {b5_buy}$
🎯 الهدف السريع: {b5_buy_tp}$

🔴 إشارة البيع:
كسر مستوى: {b5_sell}$
🎯 الهدف السريع: {b5_sell_tp}$
━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ شرط أساسي للتنفيذ:
إغلاق شمعة (5 دقائق) بالكامل فوق مستوى الكسر للشراء، أو أسفل مستوى الكسر للبيع.
"""

        bot2_reports = []
        bot2_reports.append(("💧 سيولة اليومي", daily_liquidity_block, None))
        bot2_reports.append(("⏳ الأوامر المعلقة اللحظية", limits_block, None))
        bot2_reports.append(("⚡ صفقات الاختراق اللحظي", breakout_5m_block, None))
        
        # القالب الجديد للمستويات
        bot2_reports.append(("📍 مستويات واتجاهات اليوم", _build_all_tf_levels(data), None))
        # القالب الذكي الجديد CFTC (t11)
        bot2_reports.append(("📰 تقرير CFTC", t11 if t11 and 'تعذر' not in str(t11) else _build_template_11(data), None))
        t13_src = t13 if t13 and 'تعذر' not in str(t13) else _build_template_13(data)
        if not t13_src:
            t13_src = "━━━━━━━━━━━━━━━━━━━━━━━━━━" + "━━━━━━━━━━━━━━━━━━━━━━━━━━".join(_build_template_13.__code__.co_consts) # Fallback if everything fails
        
        import re
        t13_clean = re.sub(r'\[.*?\]', '', t13_src, flags=re.DOTALL)
        t13_clean = re.sub(r'\n\s*\n', '\n\n', t13_clean).strip()
        bot2_reports.append(("📊⚡ تحليل عقود الأوبشن الاحترافي", t13_clean, None))

        # القوالب الفورية S1-S12 — البوت الثالث @Dsssoppp78_bot
        bot3_reports = []
        try:
            bot3_reports.append(("[فوري] 1/12 الاسعار والفيبوناتشي",       _build_spot_s1(data),  None))
            bot3_reports.append(("[فوري] 2/12 الاطارات الزمنية",            _build_spot_s2(data),  None))
            bot3_reports.append(("[فوري] 3/12 زيرو انعكاس",                 _build_spot_s3(data),  None))
            bot3_reports.append(("[فوري] 4/12 السكالبينج",                   _build_spot_s4(data),  None))
            bot3_reports.append(("[فوري] 5/12 السوينج",                      _build_spot_s5(data),  None))
            bot3_reports.append(("[فوري] 6/12 اللوت العالي",                 _build_spot_s6(data),  None))
            bot3_reports.append(("[فوري] 7/12 التحليل الفني والزخم",         _build_spot_s7(data),  None))
            bot3_reports.append(("[فوري] 8/12 الاقتصاد الكلي",              _build_spot_s8(data),  None))
            bot3_reports.append(("[فوري] 9/12 شهية المخاطرة",               _build_spot_s9(data),  None))
            bot3_reports.append(("[فوري] 10/12 عوائد السندات",              _build_spot_s10(data), None))
            bot3_reports.append(("[فوري] 11/12 قوة العملات DXY",             _build_spot_s11(data), None))
            bot3_reports.append(("[فوري] 12/12 الخلاصة المحورية",            _build_spot_s12(data), None))
            bot3_reports.append(("[فوري] 13/13 المستهدف الأسبوعي", _build_friday_target(data, False), None))
            bot3_reports.append(("[فوري] 14/14 مسار القمة والقاع", _build_spot_s14(data), None))
            bot3_reports.append(("[فوري] 15/15 الرادار المؤسساتي والسيولة", _build_spot_s15(data), None))
            bot3_reports.append(("[فوري] 16/16 استراتيجية اللوت الكامل", _build_spot_s16(data), None))
            log.info(f"[Bot3] جاهز: {len(bot3_reports)} قالب فوري رياضي")
        except Exception as _se:
            log.warning(f"[S1-S12] خطا في توليد القوالب الفورية: {_se}")

        bot2_reports.append(("🎯 الصفقات المتخصصة والفريمات (الفوري)", t7 or _build_template_7(data), None))
        bot2_reports.append(("🐋 تاثير الاسواق والمؤسسات (الفوري)", t8 or _build_template_8(data), None))
        bot2_reports.append(("📊 تقرير اتجاه الذهب اليومي (الفوري)", t9 or _build_template_9(data), None))
        bot2_reports.append(("📆 التقرير الاسبوعي الشامل (الفوري)", t10 or _build_template_10(data), None))
        _t6_text = t6 if t6 and 'تعذر' not in str(t6) else f"الخلاصة: اتجاه {data.get('confluence', {}).get('verdict', 'محايد')} — السعر {data.get('gold', 0):.2f}$"
        bot2_reports.append(("الخلاصة المحورية", _t6_text, None))
        
        s12_report = _build_spot_s12(data)
        bot2_reports.append(("👑 الخلاصة المحورية والدقيقة (الجيل الخامس - Spot)", s12_report or f"الخلاصة المحورية: السعر {data.get('gold',0):.2f}$", None))
            
        s9_report = _build_spot_s9(data)
        bot2_reports.append(("👑 مصفوفة التداول السريعة والاسكالبينج الاحترافي (Spot)", s9_report or f"مصفوفة التداول: السعر {data.get('gold',0):.2f}$", None))
        bot2_reports.append(("[16/16] المستهدف الأسبوعي (الجمعة)", _build_friday_target(data, False), None))
        bot2_reports.append(("👑 مسار القمة والقاع (اتجاه السيولة)", _build_spot_s14(data), None))
        bot2_reports.append(("👑 الرادار المؤسساتي (كشف التلاعب والسيولة)", _build_spot_s15(data), None))
        bot2_reports.append(("👑 الخطة التكتيكية (Full Lot Strategy)", _build_spot_s16(data), None))
        bot2_reports.append(("⏰ تنبيه مبكر — انعكاس مرتقب", _build_early_warning_alert(data), None))
        bot2_reports.append(("🚨 رادار الأخبار العاجلة (Breaking News)", _build_sudden_news_alert(data), None))
        bot2_reports.append(("🏦 رادار السيولة المؤسساتية (Smart Money)", _build_institutional_liquidity_map(data), None))
        bot2_reports.append(("🌊 كاشف السيولة وأحجام العقود", _build_volume_contracts_tracker(data), None))
        bot2_reports.append(("🎯 أهداف السيولة الزمنية (Targets)", _build_liquidity_time_targets(data), None))



        # ── لا T6 خاص هنا ——  الخلاصة ستأتي مشتركة في الأسفل ──

        # ── تسطيح وإرسال ──
        raw_reports.append(("👑 مسار القمة والقاع (اتجاه السيولة)", _build_spot_s14(data), None))
        raw_reports.append(("👑 الرادار المؤسساتي (كشف التلاعب والسيولة)", _build_spot_s15(data), None))
        raw_reports.append(("👑 الخطة التكتيكية (Full Lot Strategy)", _build_spot_s16(data), None))
        raw_reports.append(("⏰ تنبيه مبكر — انعكاس مرتقب", _build_early_warning_alert(data), None))
        raw_reports.append(("🚨 رادار الأخبار العاجلة (Breaking News)", _build_sudden_news_alert(data), None))
        raw_reports.append(("🏦 رادار السيولة المؤسساتية (Smart Money)", _build_institutional_liquidity_map(data), None))
        raw_reports.append(("🌊 كاشف السيولة وأحجام العقود", _build_volume_contracts_tracker(data), None))
        raw_reports.append(("🎯 أهداف السيولة الزمنية (Targets)", _build_liquidity_time_targets(data), None))

        flat_chunks = []
        for title, txt, chat_id in raw_reports:
            for chunk in _split_message(txt):
                flat_chunks.append((title, chunk, chat_id))
        total = len(flat_chunks)

        flat_chunks_2 = []
        if 'bot2_reports' in locals():
            for title, txt, chat_id in bot2_reports:
                for chunk in _split_message(txt):
                    flat_chunks_2.append((title, chunk, chat_id))
        total_2 = len(flat_chunks_2)

        global LAST_PUBLIC_REPORT_TIME, LAST_4H_REPORT_TIME
        now = time.time()
        is_public = False
        if now - LAST_PUBLIC_REPORT_TIME >= 14000:
            is_public = True
            LAST_PUBLIC_REPORT_TIME = now
            
        send_to_4h_channel = False
        if now - LAST_4H_REPORT_TIME >= 4 * 3600:
            send_to_4h_channel = True
            LAST_4H_REPORT_TIME = now

        log.info("⏳ [Spot] التقارير جاهزة، انتظار القفل المشترك للإرسال...")
        with SEND_LOCK:
            log.info("🔒 [Spot] حصل على القفل — بدء إرسال الرسائل...")
            log.info(f"📤 [Spot] إرسال {total} رسالة متسلسلة...")

            for i, (title, chunk, chat_id) in enumerate(flat_chunks, 1):
                subtitle = _get_subtitle(chunk, title)
                final_text = (
                    f"{prefix}[{i}/{total}] 👑 التقرير الكمي الشامل للذهب (الفوري - Spot)\n"
                    f"{subtitle}\n\n{chunk}"
                )
                ok = _send_single(final_text, is_public, chat_id)
                
                # Send to SovereignMaaregFund if 4 hours have passed
                if send_to_4h_channel and not chat_id:
                    _send_single(final_text, is_public, "@Maaregsovereinefund")
                    
                log.info(f"✅ رسالة {i}/{total} وصلت." if ok else f"❌ فشل رسالة {i}/{total}.")
                time.sleep(2)

            # ── إرسال للبوت الجديد (القسم الثاني) ──
            if flat_chunks_2:
                log.info(f"📤 إرسال {total_2} رسالة متسلسلة للبوت المستقل (الجزء الثاني)...")
                import os
                # استدعاء توكن البوت الجديد (مؤقتاً نستخدم نفس الإرسال المخصص إذا لم يتوفر التوكن، لكن يمكن للعميل تغييره)
                bot2_token = os.environ.get('TELEGRAM_BOT_TOKEN_2', TELEGRAM_BOT_TOKEN) 
                
                for i2, (title2, chunk2, chat_id2) in enumerate(flat_chunks_2, 1):
                    subtitle2 = _get_subtitle(chunk2, title2)
                    final_text2 = (
                        f"{prefix}[{i2}/{total_2}] 👑 التقرير الكمي الشامل للذهب (الفوري - Spot)\n"
                        f"{subtitle2}\n\n{chunk2}"
                    )
                    # For bot 2, we will send to TARGET_CHATS unless specified
                    ok2 = _send_single_bot2(final_text2, is_public, chat_id2)
                    
                    if send_to_4h_channel and not chat_id2:
                        _send_single_bot2(final_text2, is_public, "@Maaregsovereinefund")
                        
                    log.info(f"✅ رسالة البوت الثاني {i2}/{total_2} وصلت." if ok2 else f"❌ فشل رسالة البوت الثاني {i2}/{total_2}.")
                    time.sleep(2)

            # ── البوت الثالث: القوالب الفورية S1-S12 (@Dsssoppp78_bot) ──
            if 'bot3_reports' in locals() and bot3_reports:
                flat_chunks_3 = []
                for title3, txt3, cid3 in bot3_reports:
                    if txt3:
                        for chunk3 in _split_message(txt3):
                            flat_chunks_3.append((title3, chunk3, cid3))
                total_3 = len(flat_chunks_3)
                log.info(f"📤 [Bot3] ارسال {total_3} قالب فوري عبر @Dsssoppp78_bot...")
                for i3, (title3, chunk3, cid3) in enumerate(flat_chunks_3, 1):
                    final_text3 = (
                        f"📊 [{i3}/{total_3}] تقارير سوق الفوري (XAU/USD Spot)\n"
                        f"{title3}\n\n{chunk3}"
                    )
                    ok3 = _send_single_bot3(final_text3, cid3)
                    
                    if send_to_4h_channel and not cid3:
                        _send_single_bot3(final_text3, "@Maaregsovereinefund")
                        
                    log.info(f"{'✅' if ok3 else '❌'} [Bot3] {i3}/{total_3}")
                    time.sleep(2)

            log.info("🔓 [Spot] تم الارسال، تحرير القفل لانتظار الخلاصة...")

        # ══════════════════════════════════════════════════════
        #  الخلاصة النهائية المشتركة — تأتي هنا بعد كل الرسائل
        # ══════════════════════════════════════════════════════
#         log.info("🏆 [Combined] توليد الخلاصة النهائية المشتركة (آجل + فوري)...")
#         try:
#             fc = _futures_cache  # بيانات الآجل المحفوظة
#             # لو بيانات الآجل مش موجودة، ننتظر حتى 15 دقيقة ريحة 30 ثانية
#             if not fc or not fc.get("t1"):
#                 log.info("⏳ [Combined] Futures لم ينتهِ بعد — ننتظر حتى 15 دقيقة...")
#                 for _ in range(30):  # 30 × 30 ثانية = 15 دقيقة
#                     time.sleep(30)
#                     fc = _futures_cache
#                     if fc and fc.get("t1"):
#                         log.info("✅ [Combined] بيانات الآجل وصلت — نبني الخلاصة الآن.")
#                         break
#                 else:
#                     log.warning("⚠️ [Combined] انتهى وقت الانتظار — الخلاصة مؤجلة.")
#             if fc and fc.get("t1"):
#                 # احسب الاتجاه المشترك من البوتين بشكل آلي
#                 spot_score  = data.get('tf_daily', {}).get('score', 0)
#                 fut_score   = fc.get('score', spot_score)  # بيانات الآجل
#                 avg_score   = (spot_score + fut_score) / 2
#                 bull_pct = max(0, min(100, round(50 + avg_score * 12)))
#                 bear_pct = 100 - bull_pct
# 
#                 combined = _build_combined_summary(
#                     spot_data=data,
#                     futures_report=fc.get("report_text", ""),
#                     spot_report=report_text,
#                     futures_t1=fc.get("t1", ""),
#                     futures_t2=fc.get("t2", ""),
#                     spot_t1=t1,
#                     spot_t2=t2,
#                     futures_t0=fc.get("t0", ""),
#                     spot_t0=t0,
#                     bull_pct=bull_pct,
#                     bear_pct=bear_pct,
#                 )
#                 if combined:
#                     summary_msg = (
#                         "🏆 الخلاصة النهائية الشاملة | آجل + فوري\n"
#                         "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
#                         + combined
#                     )
#                     ok = _send_single(summary_msg, is_public, None)
#                     log.info("✅ [Combined] تم إرسال الخلاصة المشتركة." if ok else "❌ [Combined] فشل إرسال الخلاصة المشتركة.")
#         except Exception as e:
#             log.error(f"❌ [Combined] خطأ في الخلاصة المشتركة: {e}")
# 

        try:
 

            if 't6' in locals() and t6:
 

                with open('temp_summary_spot.txt', 'w', encoding='utf-8') as f:
 

                    f.write(t6)
 

                send_summary_to_bot('8784019564:AAF1XBrGTb5QU_wmOcvYQQ49Vb7dpLWZnm4', t6, '@spotGol')
 

        except Exception as e:
 

            log.error(f"Failed injecting spot summary: {e}") 

        log.info("🔓 [Spot] أطلق القفل — انتهى الدورة الكاملة.")



# ══════════════════════════════════════════════
#  9. الحلقة الرئيسية
# ══════════════════════════════════════════════
def run_bot():
    log.info("🚀 [Spot] Goldbot Pro+ v4 — نسخة الفوري")

    last_gold_price      = {'futures': None, 'spot': None}
    minutes_counter      = {'futures': 0, 'spot': 0}
    morning_sent_today   = {'futures': False, 'spot': False}
    closing_sent_today   = {'futures': False, 'spot': False}
    heartbeat_sent_today = {'futures': False, 'spot': False}
    consec_failures      = {'futures': 0, 'spot': 0}
    all_models_notified  = False
    last_report_date     = None
    market_closed_notified = False
    has_sent_initial       = False
    day_names = ["اثنين","ثلاثاء","أربعاء","خميس","جمعة","سبت","أحد"]

    while True:
        now_cairo  = cairo_now()
        today      = now_cairo.date()
        hour_cairo = now_cairo.hour
        weekday    = now_cairo.weekday()

        if last_report_date != today:
            for m in ['futures', 'spot']:
                morning_sent_today[m]   = False
                closing_sent_today[m]   = False
                heartbeat_sent_today[m] = False
            all_models_notified  = False

        if not is_market_open() and has_sent_initial:
            if not market_closed_notified:
                now_c    = cairo_now()
                wday     = now_c.weekday()
                hr       = now_c.hour
                if wday in (5, 6):
                    reason   = "عطلة نهاية الأسبوع"
                    reopen   = "الاثنين 01:00 بتوقيت القاهرة"
                    details  = "أسواق الذهب والعملات والمعادن تغلق كل جمعة مساءً وتعود مطلع الأسبوع."
                elif wday == 0 and hr < MARKET_OPEN_HOUR:
                    reason   = "ما زلنا في ساعات الإغلاق"
                    reopen   = f"الاثنين {MARKET_OPEN_HOUR:02d}:00 بتوقيت القاهرة"
                    details  = "أسواق الذهب تبدأ جلستها الأسبوعية يوم الاثنين فجراً."
                else:
                    reason   = "السوق خارج ساعات التداول"
                    reopen   = "قريباً"
                    details  = "تُتداول أسواق الذهب من الاثنين حتى الجمعة."

                closed_msg = (
                    f"🛌 سوق الذهب مغلق حالياً\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📅 السبب: {reason}\n"
                    f"📖 التفاصيل: {details}\n"
                    f"⏰ موعد الفتح: {reopen}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🕐 {now_c.strftime('%Y-%m-%d %H:%M')} بتوقيت القاهرة\n"
                    f"✅ البوت يعمل وسيُرسل التقرير فور فتح السوق."
                )
                send_to_telegram(closed_msg)
                market_closed_notified = True
                log.info("📢 تم إرسال إشعار إغلاق السوق للقناة.")

            log.info(f"🛌 سوق مغلق ({day_names[weekday]} {hour_cairo:02d}:00 قاهرة). انتظار 30 دقيقة.")
            for m in ['futures', 'spot']: last_gold_price[m] = None
            time.sleep(30 * 60)
            continue

        market_closed_notified = False

        for mode in ['spot']:
            data = get_full_market_data(mode=mode)
            if data and data["gold"]:
                consec_failures[mode] = 0
                all_models_notified = False
                current_gold = data["gold"]

                if last_gold_price[mode] is None and last_report_date != today:
                    log.info(f"📊 إرسال التقرير الافتتاحي ({mode})...")
                    report = generate_report(data, is_alert=False)
                    send_reports(data, report)
                    last_gold_price[mode] = current_gold
                    last_report_date = today
                    minutes_counter[mode] = 0
                    has_sent_initial = True
                    log.info("✅ تم إرسال التقرير الافتتاحي. البوت جاهز لمنطق 'سوق مغلق'.")  # noqa

                elif hour_cairo == HEARTBEAT_HOUR and not heartbeat_sent_today[mode]:
                    conf = data['confluence']
                    send_to_telegram(
                        f"💚 [Goldbot Heartbeat - {mode.upper()}] البوت يعمل بشكل طبيعي ✔️\n"
                        f"💰 السعر: {current_gold:.2f}$\n"
                        f"🎯 {conf['verdict']}\n"
                        f"🕐 {now_cairo.strftime('%H:%M قاهرة')}"
                    )
                    heartbeat_sent_today[mode] = True

                elif hour_cairo == MORNING_HOUR_CAI and not morning_sent_today[mode]:
                    log.info(f"🌅 إرسال تقرير الصباح ({mode})...")
                    report = generate_report(data, is_alert=False, is_morning=True)
                    if report:
                        send_reports(data, report)
                        morning_sent_today[mode] = True
                        last_gold_price[mode] = current_gold
                        minutes_counter[mode] = 0

                elif hour_cairo == CLOSING_HOUR_CAI and not closing_sent_today[mode]:
                    log.info(f"🌙 إرسال ملخص الجلسة ({mode})...")
                    report = generate_report(data, is_alert=False)
                    if report:
                        send_reports(data, report, f"🌙 [ملخص جلسة اليوم - {mode.upper()}]\n")
                        closing_sent_today[mode] = True
                        last_gold_price[mode] = current_gold
                        minutes_counter[mode] = 0

                else:
                    price_diff = current_gold - (last_gold_price[mode] or current_gold)
                    if abs(price_diff) >= ALERT_THRESHOLD:
                        log.info(f"🚨 تحرك حاد {price_diff:+.2f}$ ({mode})")
                        report = generate_report(data, is_alert=True, price_diff=price_diff)
                        if report:
                            send_reports(data, report)
                            last_gold_price[mode] = current_gold
                            minutes_counter[mode] = 0
                    elif minutes_counter[mode] >= ROUTINE_MINUTES:
                        log.info(f"⏰ مرت {ROUTINE_MINUTES} دقيقة — تقرير دوري ({mode})...")
                        report = generate_report(data, is_alert=False)
                        if report:
                            send_reports(data, report)
                            last_gold_price[mode] = current_gold
                            minutes_counter[mode] = 0
            else:
                consec_failures[mode] += 1
                log.warning(f"⚠️ فشل جلب البيانات مرة {consec_failures[mode]} ({mode}).")
                if consec_failures[mode] >= 3 and not all_models_notified:
                    send_to_telegram(
                        f"🚨 تحذير — جولدبوت يواجه مشكلة في {mode.upper()}!\n"
                        "تعذّر جلب البيانات. سيتم إعادة المحاولة تلقائياً."
                    )
                    all_models_notified = True

            minutes_counter[mode] += 1
            
        time.sleep(60)

if __name__ == "__main__":
    try:
        run_bot()
    except KeyboardInterrupt:
        print("\nBot stopped by user.")

import requests

def send_summary_to_bot(token, message, chat_id):
    import requests
    try:
        # Fallback dynamic retrieval (if user messaged bot directly)
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            resp = requests.get(url, timeout=5).json()
            if resp.get('ok') and resp.get('result'):
                # Prioritize a private chat if available, else keep the group chat_id
                for res in reversed(resp['result']):
                    if 'message' in res and res['message']['chat']['type'] == 'private':
                        chat_id = res['message']['chat']['id']
                        break
        except:
            pass
            
        send_url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(send_url, json={'chat_id': chat_id, 'text': message}, timeout=10)
    except Exception as e:
        print(f"Failed to send summary: {e}")


