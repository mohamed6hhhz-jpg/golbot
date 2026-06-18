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
    "mixtral-8x7b-32768",
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logging.getLogger('yfinance').setLevel(logging.CRITICAL)  # منع رسائل ياهو المزعجة
log = logging.getLogger(__name__)

GROQ_API_KEY        = os.environ.get("GROQ_API_KEY")
TWELVEDATA_API_KEY  = os.environ.get("TWELVEDATA_API_KEY", "a40631d26cb64ba99916a3162880aff3")
TELEGRAM_BOT_TOKEN  = "8783502825:AAEEgxaxzgiAxwl4oBp4zl73jmqwBtKCalc"
TARGET_CHATS = [-1002922209855, -1003775201576]

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
    return float(df['Close'].iloc[-1]) if df is not None and not df.empty else None

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
        return "غير محدد"
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
    atr_15m   = round(atr * (15/390) ** 0.5, 2)
    atr_1h    = round(atr * (60/390) ** 0.5, 2)
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

    # ── سكالبينج (15 دقيقة) ──
    sl_sc = 8.0
    t = dict(entry=round(s_n, 2), sl=round(s_n - sl_sc, 2), risk=sl_sc,
             t1=round(s_n + 15, 2), t2=round(s_n + 28, 2), t3=round(s_n + 45, 2),
             market='آجل (Futures)', tf='15د', typ='سكالبينج 🏹', dir='buy')
    if bias in ('bull', 'neutral') and _rr(15, sl_sc) >= MIN_RR:
        trades['scalp_buy'] = t
    t = dict(entry=round(r_n, 2), sl=round(r_n + sl_sc, 2), risk=sl_sc,
             t1=round(r_n - 15, 2), t2=round(r_n - 28, 2), t3=round(r_n - 45, 2),
             market='آجل (Futures)', tf='15د', typ='سكالبينج 🏹', dir='sell')
    if bias in ('bear', 'neutral') and _rr(15, sl_sc) >= MIN_RR:
        trades['scalp_sell'] = t

    # ── يومية ── (الدخول من Pivot فقط لو بين الدعم والمقاومة)
    sl_d = round(atr * 0.4, 2)
    # pivot قد يكون بعيداً عن السعر — نستخدمه فقط لو منطقي
    piv_valid = s_n < pivot < r_n
    buy_entry_d  = round(pivot if piv_valid else s_n, 2)
    sell_entry_d = round(pivot if piv_valid else r_n, 2)
    t = dict(entry=buy_entry_d, sl=round(buy_entry_d - sl_d, 2), risk=sl_d,
             t1=r_n, t2=r_f, t3=round(r_f + atr * 0.3, 2),
             market='فوري (Spot)', tf='1ي', typ='يومية 📅', dir='buy')
    if bias in ('bull', 'neutral') and _rr(r_n - buy_entry_d, sl_d) >= MIN_RR:
        trades['daily_buy'] = t
    t = dict(entry=sell_entry_d, sl=round(sell_entry_d + sl_d, 2), risk=sl_d,
             t1=s_n, t2=s_f, t3=round(s_f - atr * 0.3, 2),
             market='فوري (Spot)', tf='1ي', typ='يومية 📅', dir='sell')
    if bias in ('bear', 'neutral') and _rr(sell_entry_d - s_n, sl_d) >= MIN_RR:
        trades['daily_sell'] = t

    # ── أسبوعية ──
    sl_w_b = round(s_n - (pw_l - 5), 2) if pw_l else round(atr * 1.0, 2)
    sl_w_s = round((pw_h + 5) - r_n, 2) if pw_h else round(atr * 1.0, 2)
    t = dict(entry=round(s_n, 2), sl=round(pw_l - 5 if pw_l else s_n - atr, 2),
             risk=max(abs(sl_w_b), 10),
             t1=r_n, t2=r_f, t3=round(pw_h if pw_h else r_f + atr * 0.5, 2),
             market='آجل (Futures)', tf='1أ', typ='أسبوعية 📆', dir='buy')
    if bias in ('bull', 'neutral') and _rr(r_n - s_n, max(abs(sl_w_b), 10)) >= MIN_RR:
        trades['weekly_buy'] = t
    t = dict(entry=round(r_n, 2), sl=round(pw_h + 5 if pw_h else r_n + atr, 2),
             risk=max(abs(sl_w_s), 10),
             t1=s_n, t2=s_f, t3=round(pw_l if pw_l else s_f - atr * 0.5, 2),
             market='آجل (Futures)', tf='1أ', typ='أسبوعية 📆', dir='sell')
    if bias in ('bear', 'neutral') and _rr(r_n - s_n, max(abs(sl_w_s), 10)) >= MIN_RR:
        trades['weekly_sell'] = t

    # ── شهرية ──
    sl_m = round(atr * 1.5, 2)
    t = dict(entry=round(s_f, 2), sl=round(s_f - sl_m, 2), risk=sl_m,
             t1=r_n, t2=round((pm_h + r_n) / 2, 2) if pm_h else r_f,
             t3=round(pm_h, 2) if pm_h else round(r_f + atr * 0.5, 2),
             market='فوري (Spot)', tf='1ش', typ='شهرية 🗓️', dir='buy')
    if bias in ('bull', 'neutral') and _rr(r_n - s_f, sl_m) >= MIN_RR:
        trades['monthly_buy'] = t
    t = dict(entry=round(r_f, 2), sl=round(r_f + sl_m, 2), risk=sl_m,
             t1=s_n, t2=round((pm_l + s_n) / 2, 2) if pm_l else s_f,
             t3=round(pm_l, 2) if pm_l else round(s_f - atr * 0.5, 2),
             market='فوري (Spot)', tf='1ش', typ='شهرية 🗓️', dir='sell')
    if bias in ('bear', 'neutral') and _rr(r_f - s_n, sl_m) >= MIN_RR:
        trades['monthly_sell'] = t

    # ── سوينج ──
    sl_sw = round(atr * 0.35, 2)
    mid   = round((sw_h + sw_l) / 2, 2)
    t = dict(entry=round(sw_l, 2), sl=round(sw_l - sl_sw, 2), risk=sl_sw,
             t1=mid, t2=round(sw_h, 2), t3=round(sw_h + atr * 0.4, 2),
             market='آجل (Futures)', tf='أسابيع', typ='سوينج 🌊', dir='buy')
    if sw_l < gold and _rr(mid - sw_l, sl_sw) >= MIN_RR:
        trades['swing_buy'] = t
    t = dict(entry=round(sw_h, 2), sl=round(sw_h + sl_sw, 2), risk=sl_sw,
             t1=mid, t2=round(sw_l, 2), t3=round(sw_l - atr * 0.4, 2),
             market='آجل (Futures)', tf='أسابيع', typ='سوينج 🌊', dir='sell')
    if sw_h > gold and _rr(sw_h - mid, sl_sw) >= MIN_RR:
        trades['swing_sell'] = t

    # ── انعكاس (Counter-trend) ──
    has_div = '💡' in div or '⚠️' in div
    sl_rev  = round(atr * 0.28, 2)
    if (has_div or rsi < 38) and bias != 'bull':
        t = dict(entry=round(gold, 2), sl=round(gold - sl_rev, 2), risk=sl_rev,
                 t1=round(pivot, 2), t2=r_n, t3=r_f,
                 market='فوري (Spot)', tf='1-4س', typ='زيرو انعكاس 🔄', dir='buy')
        if _rr(pivot - gold, sl_rev) >= MIN_RR:
            trades['rev_buy'] = t
    if (has_div or rsi > 62) and bias != 'bear':
        t = dict(entry=round(gold, 2), sl=round(gold + sl_rev, 2), risk=sl_rev,
                 t1=round(pivot, 2), t2=s_n, t3=s_f,
                 market='فوري (Spot)', tf='1-4س', typ='زيرو انعكاس 🔄', dir='sell')
        if _rr(gold - pivot, sl_rev) >= MIN_RR:
            trades['rev_sell'] = t
    # ── صفقة كل 5 دقائق (5min scalp) ──
    atr_5m = round(atr * (5/390)**0.5, 2)
    sl_5m = max(round(atr_5m * 0.8, 2), 3.0)
    sc_15m = d.get('tf_15m', {}).get('score', 0)
    if sc_15m > 0:
        t5m = dict(entry=round(gold, 2), sl=round(gold - sl_5m, 2), risk=sl_5m,
                   t1=round(gold + atr_5m*1.5, 2), t2=round(gold + atr_5m*2.5, 2),
                   t3=round(gold + atr_5m*4.0, 2),
                   market='فوري (Spot)', tf='5د', typ='سكالبينج 5د ⚡', dir='buy')
        if _rr(atr_5m*1.5, sl_5m) >= 1.5: trades['scalp_5m_buy'] = t5m
    elif sc_15m < 0:
        t5m = dict(entry=round(gold, 2), sl=round(gold + sl_5m, 2), risk=sl_5m,
                   t1=round(gold - atr_5m*1.5, 2), t2=round(gold - atr_5m*2.5, 2),
                   t3=round(gold - atr_5m*4.0, 2),
                   market='فوري (Spot)', tf='5د', typ='سكالبينج 5د ⚡', dir='sell')
        if _rr(atr_5m*1.5, sl_5m) >= 1.5: trades['scalp_5m_sell'] = t5m

    # ── سوينج طويل الأمد (Long-Term Swing) ──
    pm_h_val = d.get('prev_mo_high') or round(sw_h + atr, 2)
    pm_l_val = d.get('prev_mo_low') or round(sw_l - atr, 2)
    sl_lt = round(atr * 2.0, 2)
    if bias in ('bull', 'neutral'):
        lt_entry = round(min(s_f, sw_l * 1.001), 2)
        t_lt = dict(entry=lt_entry, sl=round(lt_entry - sl_lt, 2), risk=sl_lt,
                    t1=round(sw_h, 2), t2=round(pm_h_val, 2), t3=round(pm_h_val + atr*0.5, 2),
                    market='آجل (Futures)', tf='شهور', typ='سوينج طويل 🌊⌚', dir='buy')
        if _rr(sw_h - lt_entry, sl_lt) >= 1.5: trades['long_swing_buy'] = t_lt
    if bias in ('bear', 'neutral'):
        lt_entry = round(max(r_f, sw_h * 0.999), 2)
        t_lt = dict(entry=lt_entry, sl=round(lt_entry + sl_lt, 2), risk=sl_lt,
                    t1=round(sw_l, 2), t2=round(pm_l_val, 2), t3=round(pm_l_val - atr*0.5, 2),
                    market='آجل (Futures)', tf='شهور', typ='سوينج طويل 🌊⌚', dir='sell')
        if _rr(lt_entry - sw_l, sl_lt) >= 1.5: trades['long_swing_sell'] = t_lt

    # ── سكالبينج ضيق جداً (Tight Scalp) ──
    sl_tight = max(round(atr * (10/390)**0.5, 2), 2.5)
    sc_1h = d.get('tf_hourly', {}).get('score', 0)
    if sc_1h > 0 and bias in ('bull', 'neutral'):
        t_ts = dict(entry=round(gold, 2), sl=round(gold - sl_tight, 2), risk=sl_tight,
                    t1=round(gold + sl_tight*2, 2), t2=round(gold + sl_tight*3.5, 2),
                    t3=round(gold + sl_tight*5, 2),
                    market='فوري (Spot)', tf='10د', typ='سكالب ضيق 🎯', dir='buy')
        if _rr(sl_tight*2, sl_tight) >= 1.5: trades['tight_scalp_buy'] = t_ts
    elif sc_1h < 0 and bias in ('bear', 'neutral'):
        t_ts = dict(entry=round(gold, 2), sl=round(gold + sl_tight, 2), risk=sl_tight,
                    t1=round(gold - sl_tight*2, 2), t2=round(gold - sl_tight*3.5, 2),
                    t3=round(gold - sl_tight*5, 2),
                    market='فوري (Spot)', tf='10د', typ='سكالب ضيق 🎯', dir='sell')
        if _rr(sl_tight*2, sl_tight) >= 1.5: trades['tight_scalp_sell'] = t_ts

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
                    market='فوري (Spot)', tf='<5د', typ='لوت عالي 💰', dir='buy')
        if _rr(12, sl_hl) >= 1.5: trades['high_lot_buy'] = t_hl
    if hl_entry_s:
        t_hl = dict(entry=hl_entry_s, sl=round(hl_entry_s + sl_hl, 2), risk=sl_hl,
                    t1=round(hl_entry_s - 12, 2), t2=round(hl_entry_s - 22, 2), t3=round(hl_entry_s - 35, 2),
                    market='فوري (Spot)', tf='<5د', typ='لوت عالي 💰', dir='sell')
        if _rr(12, sl_hl) >= 1.5: trades['high_lot_sell'] = t_hl

    # ── هدف الـ 15 دقيقة القادمة ──
    atr_15 = round(atr * (15/390)**0.5, 2)
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


def tf_gold_impact(score: int) -> str:
    if score >= 3:  return "↑↑ دعم صعودي قوي → الذهب مرشح للصعود"
    if score >= 1:  return "↑ دعم صعودي خفيف → ميل إيجابي للذهب"
    if score <= -3: return "↓↓ ضغط هبوطي قوي → الذهب مرشح للهبوط"
    if score <= -1: return "↓ ضغط هبوطي خفيف → ميل سلبي للذهب"
    return "↔ محايد — لا تأثير واضح على الذهب"


def _rsi_gold_impact(rsi: float) -> str:
    if rsi < 30:   return "🟢 تشبع بيع → الذهب مرشح لارتداد صعودًا"
    elif rsi > 70: return "🔴 تشبع شراء → الذهب مرشح لتصحيح هبوطًا"
    elif rsi < 45: return "🔴 ضغط هبوطي → الذهب تحت ضغط بائع"
    elif rsi > 55: return "🟢 دعم صعودي → الذهب يجد زخماً للأعلى"
    return "⚪ محايد → لا دعم ولا ضغط على الذهب"


def _macd_gold_impact(macd_hist: float) -> str:
    if macd_hist > 0.5:   return "🟢 زخم صعودي → يدفع الذهب للأعلى"
    elif macd_hist < -0.5: return "🔴 زخم هبوطي → يضغط الذهب للأسفل"
    return "⚪ زخم ضعيف → لا تأثير واضح على الذهب"


def _obv_gold_impact(obv_trend: str) -> str:
    if 'صعودي' in obv_trend: return "🟢 تراكم مؤسسي → المؤسسات تشتري الذهب"
    elif 'هبوطي' in obv_trend: return "🔴 توزيع مؤسسي → المؤسسات تبيع الذهب"
    return "⚪ OBV غير محدد"


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
    """كشف التباين بين RSI والسعر — صعودي / هبوطي"""
    if df is None or len(df) < 35:
        return "⚪ لا يوجد تباين واضح"
    closes = df['Close'].values
    # نحسب RSI على آخر 30 شمعة
    rsi_vals = [calc_rsi(closes[max(0,i-20):i+1]) for i in range(len(closes)-30, len(closes))]
    prices   = closes[-30:]
    if len(rsi_vals) < 20:
        return "⚪ لا يوجد تباين واضح"
    mid = len(prices) // 2
    p1_hi, p2_hi = np.max(prices[:mid]),  np.max(prices[mid:])
    p1_lo, p2_lo = np.min(prices[:mid]),  np.min(prices[mid:])
    r1_hi, r2_hi = np.max(rsi_vals[:mid]), np.max(rsi_vals[mid:])
    r1_lo, r2_lo = np.min(rsi_vals[:mid]), np.min(rsi_vals[mid:])
    # تباين هبوطي: سعر قمة أعلى + RSI قمة أدنى
    if p2_hi > p1_hi and r2_hi < r1_hi * 0.99:
        return "⚠️ تباين هبوطي — السعر يصنع قمة أعلى وRSI أدنى ⚠️"
    # تباين صعودي: سعر قاع أدنى + RSI قاع أعلى
    if p2_lo < p1_lo and r2_lo > r1_lo * 1.01:
        return "💡 تباين صعودي — السعر يصنع قاعاً أدنى وRSI أعلى 💡"
    return "⚪ لا يوجد تباين في الوقت الحالي"


def calc_trade_confidence(d: dict, t: dict) -> tuple[int, str, str]:
    score   = 0
    reasons = []
    is_buy  = t.get('is_buy', t.get('dir', '') == 'buy')
    gold    = d['gold']
    entry   = t.get('entry', gold)
    bias    = d['confluence']['bias']

    # 1. Trend alignment (20 pts)
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

    pct = max(20, min(97, round(score)))
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
        'obv_muayad': 'OBV مؤيد 🏦',
        'qarib_min_daom': 'قريب من دعم قوي 📍',
        'qarib_min_muqawama': 'عند مقاومة قوية 📍',
        'tabayon_sauodi': 'تباين صعودي 💡',
        'tabayon_huboti': 'تباين هبوطي ⚠️',
        'stoch_tashabuo_bay': 'Stoch تشبع بيع',
        'stoch_tashabuo_shira': 'Stoch تشبع شراء',
    }

    def translate(r):
        for k, v in ar_map.items():
            if r.startswith(k.split('_')[0]):
                return ar_map.get(k, r)
        for k, v in ar_map.items():
            if k in r: return v
        return r

    arabic_reasons = []
    for r in reasons[:4]:
        matched = False
        for k, v in ar_map.items():
            if r == k or r.startswith(k):
                arabic_reasons.append(v); matched = True; break
        if not matched:
            arabic_reasons.append(r)

    reason_str = '، '.join(arabic_reasons) if arabic_reasons else 'لا توجد مؤشرات قوية'
    return pct, f'{emoji} {lbl}', reason_str


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
        buys  = [mb(gold,   TIGHT_SL, "فوري (Spot)",   "🔴 عدواني"),
                 mb(s_near, STD_SL,   "آجل (Futures)", "🟡 معتدل — دعم قريب"),
                 mb(s_far,  TIGHT_SL, "فوري (Spot)",   "🟢 محافظ — دعم بعيد")]
        sells = [ms(r_near, TIGHT_SL, "فوري (Spot)",   "🔴 عند مقاومة قريبة"),
                 ms(r_far,  STD_SL,   "آجل (Futures)", "🟡 عند مقاومة ثانية"),
                 ms(r_far2, TIGHT_SL, "فوري (Spot)",   "🟢 عند مقاومة بعيدة")]
    elif bias == "bear":
        sells = [ms(gold,   TIGHT_SL, "فوري (Spot)",   "🔴 عدواني"),
                 ms(r_near, STD_SL,   "آجل (Futures)", "🟡 معتدل — مقاومة قريبة"),
                 ms(r_far,  TIGHT_SL, "فوري (Spot)",   "🟢 محافظ — مقاومة بعيدة")]
        buys  = [mb(s_near, TIGHT_SL, "فوري (Spot)",   "🔴 عدواني — دعم قريب"),
                 mb(s_far,  STD_SL,   "آجل (Futures)", "🟡 معتدل — دعم ثاني"),
                 mb(s_far2, TIGHT_SL, "فوري (Spot)",   "🟢 محافظ — دعم بعيد")]
    else:  # neutral
        buys  = [mb(s_near, TIGHT_SL, "فوري (Spot)",   "🔴 دعم قريب — اختراق"),
                 mb(s_far,  STD_SL,   "آجل (Futures)", "🟡 معتدل — دعم ثاني"),
                 mb(s_far2, TIGHT_SL, "فوري (Spot)",   "🟢 محافظ — دعم بعيد")]
        sells = [ms(r_near, TIGHT_SL, "فوري (Spot)",   "🔴 مقاومة قريبة — اختراق"),
                 ms(r_far,  STD_SL,   "آجل (Futures)", "🟡 معتدل — مقاومة ثانية"),
                 ms(r_far2, TIGHT_SL, "فوري (Spot)",   "🟢 محافظ — مقاومة بعيدة")]

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
    def _fc(n_hours: float):
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
        return {"close": center, "high": high, "low": low, "quality": int(quality)}

    return {
        "1h"  : _fc(1),
        "4h"  : _fc(4),
        "1d"  : _fc(24),
        "1w"  : _fc(24 * 5),
        "1mo" : _fc(24 * 22),
    }


# ══════════════════════════════════════════════
#  6. جلب كل بيانات السوق
# ══════════════════════════════════════════════
def get_full_market_data() -> dict | None:
    log.info("📡 جلب البيانات — فوري + آجل + متعدد الإطارات...")

    # ── الذهب: الآجل والفوري وإطارات متعددة ──
    gold_daily  = _fetch("GC=F",     period="90d", interval="1d");  time.sleep(0.7)
    gold_weekly = _fetch("GC=F",     period="2y",  interval="1wk"); time.sleep(0.7)
    gold_hourly = _fetch("GC=F",     period="30d", interval="1h");  time.sleep(0.7)
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

    # [11] 15m data for short-term trend
    gold_15m  = _fetch("GC=F",     period="5d",  interval="15m"); time.sleep(0.5)

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

    if not all([gold_futures, dxy, tnx]):
        return None

    gold = gold_futures   # الأساس للحسابات هو الآجل

    # [11] تحليل 4 إطارات زمنية: 15m, 1h, 4h, 1d
    import pandas as pd
    gold_4h = None
    if gold_hourly is not None and len(gold_hourly) >= 16:
        try:
            gold_4h = gold_hourly.resample('4h').agg(
                {'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}
            ).dropna()
        except Exception:
            gold_4h = None

    tf_15m    = analyze_timeframe(gold_15m,    "⋆ 15 دقيقة")
    tf_hourly = analyze_timeframe(gold_hourly, "⏱️ ساعي")
    tf_4h     = analyze_timeframe(gold_4h,     "⏰ 4 ساعات")
    tf_daily  = analyze_timeframe(gold_daily,  "📅 يومي")
    tf_weekly = analyze_timeframe(gold_weekly, "📆 أسبوعي")
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
    real_yield_val = round(tnx - inflation_est, 2) if tnx else None
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
            f"   🔢 الحساب: عائد اسمي(10Y) {tnx:.2f}% − تضخم {inflation_est}% = عائد حقيقي {ryv:+.2f}%\n"
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


    # ── [4] مستويات محسّنة: VWAP + سابق أسبوع/شهر + مناطق الطلب/عرض ──
    # VWAP (سعر مرجح بالحجم) من بيانات الساعي
    vwap = None
    if gold_hourly is not None and len(gold_hourly) > 0:
        try:
            h = gold_hourly.copy()
            h['tp']     = (h['High'] + h['Low'] + h['Close']) / 3
            h['tp_vol'] = h['tp'] * h['Volume']
            total_vol   = h['Volume'].sum()
            vwap = round(float(h['tp_vol'].sum() / total_vol), 2) if total_vol > 0 else None
        except Exception:
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

    # ثانياً: CBOE Equity PCR — بيانات رسمية 100% (متاح علناً)
    if gld_pcr is None:
        try:
            cboe_url = "https://cdn.cboe.com/api/global/us_indices/daily_prices/PCR-EQUITYVOL_Data.csv"
            cr = requests.get(cboe_url, timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
            if cr.status_code == 200:
                lines = cr.text.strip().split('\n')
                # آخر سطر بيانات
                last = [x.strip() for x in lines[-1].split(',')]
                if len(last) >= 2:
                    pcr_val = float(last[1])
                    if 0.2 < pcr_val < 5.0:
                        gld_pcr    = round(pcr_val, 2)
                        pcr_source = "CBOE Equity"
        except Exception:
            pass


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
        gold=gold, gold_futures=gold_futures, gold_spot=gold_spot,
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
        atr=atr, atr_regime=atr_reg, fib=fib, divergence=divergence,
        swing_high=swing_high, swing_low=swing_low,
        pivot=pivot, r1=r1, r2=r2, r3=r3, s1=s1, s2=s2, s3=s3,
        round_numbers=round_numbers, hist_ctx=hist_ctx,
        real_yield_signal=real_yield_signal,
        real_yield_brief=real_yield_brief,
        tf_weekly=tf_weekly, tf_daily=tf_daily, tf_hourly=tf_hourly,
        tf_4h=tf_4h, tf_15m=tf_15m, tf_label=tf_label,
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
    )

    d['confluence']      = calc_confluence(d)
    d['entries']         = calc_all_entries(d, d['confluence']['bias'])
    d['adv_trades']      = calc_advanced_trades(d, d['confluence']['bias'])
    d['price_pred']      = calc_price_prediction(d['gold'], d['atr'], d['tf_15m'], d['tf_hourly'])
    d['tf_forecasts']    = _calc_price_forecasts(d['gold'], d['atr'], d['confluence']['bias'], d)
    return d


# ══════════════════════════════════════════════
#  7. بناء هيكل التقرير الثابت + تحليل الـ AI
# ══════════════════════════════════════════════
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
        spot_label = f"غير متاح (آخر معلوم: راجع الآجل)"
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
    bias_section = {"bull":"🎯 صفقات الاتجاه الصعودي",
                    "bear":"🎯 صفقات الاتجاه الهبوطي",
                    "neutral":"⚡ صفقات الاختراق (سوق متذبذب)"}.get(ent['bias'],"🎯 الصفقات")

    def fmt_block(trades):
        lines = []
        for i, t in enumerate(trades):
            pct, lbl, reason = calc_trade_confidence(d, t)
            if pct >= 75:
                entry_rule = f"✅ ادخل بثقة — (فرصة قوية مدعومة بالترند والسيولة)"
            elif pct >= 60:
                entry_rule = f"⚠️ دخول بحذر (نصف عقد) — (مخاطرة متوسطة، يُفضل الانتظار لتأكيد الاتجاه)"
            elif pct >= 45:
                entry_rule = f"⛔ لا تدخل — (السوق متضارب والعائد لا يبرر المخاطرة الحالية)"
            else:
                entry_rule = f"❌ تجاهل الصفقة — (خطر عالي جداً وعكس تيار السوق)"
            
            lines.append(
                f"\n   ╭─────────────────────────────╮\n"
                f"   │ {nums[i]} {t['dir']}  ·  {t['style']}\n"
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
        return "\n".join(lines)

    buy_block  = fmt_block(ent['buys'])
    sell_block = fmt_block(ent['sells'])

    # مستويات فيبوناتشي الرئيسية
    fib = d['fib']
    fib_line = (f"فيبو: 78.6%={fib['78.6%']}$ | 61.8%={fib['61.8%']}$ | "
                f"50.0%={fib['50.0%']}$ | 38.2%={fib['38.2%']}$ | 23.6%={fib['23.6%']}$")
    # نطاق اليوم المتوقع من ATR
    exp_low  = round(gold - d['atr'] * 0.65, 2)
    exp_high = round(gold + d['atr'] * 0.65, 2)
    range_line = f"نطاق اليوم المتوقع (±0.65×ATR): {exp_low}$ ↔ {exp_high}$"

    fixed = f"""👑 📊 التقرير الكمي الشامل للذهب
🕐 {date_now}

━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 أسعار الذهب
   فوري  (XAU/USD) : {spot_label}
   آجل   (GC=F)    : {futures_label}{contango_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 ملخص السوق
   الزخم        : {ent['momentum']} {'→ تسارع بيع، الذهب عرضة للهبوط' if 'هابط' in ent['momentum'] else '→ تسارع شراء، الذهب في دعم' if 'صاعد' in ent['momentum'] else '→ حركة غير محددة'}
   الاتجاه العام : {ent['trend']} {'→ الاتجاه السائد للأسفل' if 'هبوطي' in ent['trend'] else '→ الاتجاه السائد للأعلى' if 'صعودي' in ent['trend'] else '→ الاتجاه غير محدد'}
   السيولة       : {ent['liquidity']} {'→ الحركات موثوقة ✅' if 'مرتفعة' in ent['liquidity'] else '→ انتبه: حركات وهمية محتملة ⚠️'}

━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 حكم السوق: {conf['verdict']}
{score_table}
   ∑ {conf['total']:+d}/±{conf['n']}  ▪ 🟢{conf['bullish']} 🔴{conf['bearish']} ⚪{conf['neutral']}

━━━━━━━━━━━━━━━━━━━━━━━━━━
🕐 الاتجاه العام (متعدد الإطارات): {d['tf_label']}
   ⚡ {d['tf_15m'].get('bias','—')} | RSI={d['tf_15m'].get('rsi','—')} | {tf_gold_impact(d['tf_15m'].get('score',0))} [15د]
   ⏱️ {d['tf_hourly'].get('bias','—')} | RSI={d['tf_hourly'].get('rsi','—')} | {tf_gold_impact(d['tf_hourly'].get('score',0))} [1س]
   ⏰ {d['tf_4h'].get('bias','—')} | RSI={d['tf_4h'].get('rsi','—')} | {tf_gold_impact(d['tf_4h'].get('score',0))} [4س]
   📅 {d['tf_daily'].get('bias','—')} | RSI={d['tf_daily'].get('rsi','—')} | {tf_gold_impact(d['tf_daily'].get('score',0))} [1ي]
   📆 {d['tf_weekly'].get('bias','—')} | RSI={d['tf_weekly'].get('rsi','—')} | {tf_gold_impact(d['tf_weekly'].get('score',0))} [أسبوعي]

━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 حركة السعر: {hist_line}

━━━━━━━━━━━━━━━━━━━━━━━━━━
📡 الأسواق
   DXY:{d['dxy']:.1f}({d['dxy_bias']}) {'→🟢دعم ذهب' if d['dxy']<101 else '→🔴ضغط' if d['dxy']>104 else '→⚪محايد'} | 2Y:{f"{d['twy']:.2f}%" if d['twy'] else '—'} | 10Y:{d['tnx']:.2f}% | 30Y:{f"{d['tty']:.2f}%" if d['tty'] else '—'} | Spread(10Y-2Y):{f"{d['yield_curve']:+.2f}%({d['yield_curve_label']})" if d['yield_curve'] is not None else '—'}
   VIX:{f"{d['vix']:.1f}" if d['vix'] else '—'}({d['vix_label'] if d['vix'] else '—'}) {'→🟢خوف=طلب ملاذء' if d['vix'] and d['vix']>25 else '→🔴هدوء=تراجع ملاذء' if d['vix'] else ''} | 🥈{f"{d['silver']:.2f}$" if d['silver'] else '—'} | 🛢️{f"{d['oil']:.1f}$" if d['oil'] else '—'} | 📊S&P:{f"{d['sp500']:.0f}" if d['sp500'] else '—'}
   🎯 نسبة P/C:{f"{d['gld_pcr']}({d['pcr_source']})" if d['gld_pcr'] else '—'} {'→تشاؤم (بيع سائد)' if d['gld_pcr'] and d['gld_pcr']>1.2 else '→تفاؤل (شراء سائد)' if d['gld_pcr'] and d['gld_pcr']<0.8 else '→توازن' if d['gld_pcr'] else ''}
   {d['real_yield_brief']}
{d['real_yield_signal']}

━━━━━━━━━━━━━━━━━━━━━━━━━━
🧮 المؤشرات وتأثيرها على الذهب
   RSI:{d['rsi']}({d['rsi_label'].split()[0]}) | {_rsi_gold_impact(d['rsi'])}
   MACD:{d['macd_hist']} | {_macd_gold_impact(d['macd_hist'])}
   StochK:{d['stoch_k']} | BB:{d['bb_label'].split()[0]}{d['ind_bb_i']} | EMA:{d['ema_label']}{d['ind_ema_i']}
   ADX:{d['adx']}(DI+{d['di_plus']}/DI-{d['di_minus']}) | {_adx_gold_impact(d['adx'],d['di_plus'],d['di_minus'])}
   OBV:{d['obv_trend']} | {_obv_gold_impact(d['obv_trend'])}
   CCI:{d['cci']}({d['cci_label'].split()[0]}) | W%R:{d['williams_r']} | ATR:{d['atr']}$

━━━━━━━━━━━━━━━━━━━━━━━━━━
🔢 المستويات
   🟣 مقاومة نفسية:{rn['nearest_resistance']}$(+{rn['dist_to_resistance']}$) | دعم نفسي:{rn['nearest_support']}$(-{rn['dist_to_support']}$)
   📍 Swing H:{d['swing_high']}$ / L:{d['swing_low']}$ | VWAP:{f"{d['vwap']}$" if d['vwap'] else '—'}
   📅 PrevWk H:{f"{d['prev_wk_high']}$" if d['prev_wk_high'] else '—'} / L:{f"{d['prev_wk_low']}$" if d['prev_wk_low'] else '—'} | PrevMo H:{f"{d['prev_mo_high']}$" if d['prev_mo_high'] else '—'} / L:{f"{d['prev_mo_low']}$" if d['prev_mo_low'] else '—'}
   🔴 R1:{d['r1']}$ R2:{d['r2']}$ | Pivot:{d['pivot']}$ | 🟢 S1:{d['s1']}$ S2:{d['s2']}$
   🟡 {fib_line}
   📊 {range_line}
   🔍 تباين:{d['divergence']} | طلب:{f"{d['sd_demand']}$" if d['sd_demand'] else '—'} | عرض:{f"{d['sd_supply']}$" if d['sd_supply'] else '—'}
━━━━━━━━━━━━━━━━━━━━━━━━━━
{bias_section}
🛒 صفقات الشراء:
{buy_block}
━━
📉 صفقات البيع:
{sell_block}
   ↑ مراقبة: {refs['above']}$ | ↓ مراقبة: {refs['below']}$"""

    # ── الجزء الثاني: توقعات + صفقات متقدمة ──
    adv  = d['adv_trades']
    pred = d['price_pred']

    def _fmt_adv(t: dict) -> str:
        arr   = "🛒" if t['dir'] == 'buy' else "📉"
        gain  = abs(t['t1'] - t['entry'])
        rr    = round(gain / t['risk'], 1) if t['risk'] > 0 else 0
        # add is_buy key for confidence calc
        t2 = dict(t); t2['is_buy'] = (t['dir'] == 'buy'); t2['rr1'] = rr
        pct, lbl, rsn = calc_trade_confidence(d, t2)
        if pct >= 75:   dec = "\u2705 \u0627\u062f\u062e\u0644 \u0628\u062b\u0642\u0629"
        elif pct >= 60: dec = "\u26a0\ufe0f \u062f\u062e\u0648\u0644 \u0628\u062d\u0630\u0631"
        elif pct >= 45: dec = "\u26d4 \u0644\u0627 \u062a\u062f\u062e\u0644"
        else:           dec = "\u274c \u062a\u062c\u0627\u0647\u0644"
        return (f"\n   \u256d\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u256e\n"
                f"   \u2502 {arr} {t['typ']} | {t['market']} | {t['tf']}\n"
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
        ('\U0001f6d2 \u0635\u0641\u0642\u0627\u062a \u0633\u0643\u0627\u0644\u0628\u064a\u0646\u062c \u0633\u0631\u064a\u0639',
         ['scalp_5m_buy','scalp_5m_sell','tight_scalp_buy','tight_scalp_sell','scalp_buy','scalp_sell']),
        ('\U0001f4c5 \u0635\u0641\u0642\u0627\u062a \u064a\u0648\u0645\u064a\u0629 \u0648\u0623\u0633\u0628\u0648\u0639\u064a\u0629',
         ['daily_buy','daily_sell','weekly_buy','weekly_sell']),
        ('\U0001f30a \u0633\u0648\u064a\u0646\u062c \u0637\u0648\u064a\u0644 \u0648\u0634\u0647\u0631\u064a',
         ['long_swing_buy','long_swing_sell','monthly_buy','monthly_sell','swing_buy','swing_sell']),
        ('\U0001f4b0 \u0644\u0648\u062a \u0639\u0627\u0644\u064a \u0648\u0627\u0646\u0639\u0643\u0627\u0633\u0627\u062a',
         ['high_lot_buy','high_lot_sell','rev_buy','rev_sell']),
    ]
    adv_blocks = []
    for grp_title, keys in order_groups:
        grp_lines = []
        for k in keys:
            if k in adv:
                grp_lines.append(_fmt_adv(adv[k]))
        if grp_lines:
            adv_blocks.append(f"\n{grp_title}:\n" + "\n".join(grp_lines))
    adv_lines = adv_blocks

    adv_block = "\n".join(adv_lines) if adv_lines else "   \u0644\u0627 \u062a\u0648\u062c\u062f \u0635\u0641\u0642\u0627\u062a \u0645\u062a\u0642\u062f\u0645\u0629 \u0645\u062a\u0627\u062d\u0629"

    part2 = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 توقعات السعر (إغلاق · قمة · قاع)
   📌 مبني على: ATR={d['atr']}$ × √زمن مُعدَّل بالاتجاه
   ─────────────────────────
   ⏱️ ساعة   │ إغلاق: {d['tf_forecasts']['1h']['close']}$  │  قمة: {d['tf_forecasts']['1h']['high']}$  │  قاع: {d['tf_forecasts']['1h']['low']}$  │ جودة:{d['tf_forecasts']['1h'].get('quality','—')}%
   ⏰ 4 ساعات│ إغلاق: {d['tf_forecasts']['4h']['close']}$  │  قمة: {d['tf_forecasts']['4h']['high']}$  │  قاع: {d['tf_forecasts']['4h']['low']}$  │ جودة:{d['tf_forecasts']['4h'].get('quality','—')}%
   📅 يوم    │ إغلاق: {d['tf_forecasts']['1d']['close']}$  │  قمة: {d['tf_forecasts']['1d']['high']}$  │  قاع: {d['tf_forecasts']['1d']['low']}$  │ جودة:{d['tf_forecasts']['1d'].get('quality','—')}%
   📆 أسبوع  │ إغلاق: {d['tf_forecasts']['1w']['close']}$  │  قمة: {d['tf_forecasts']['1w']['high']}$  │  قاع: {d['tf_forecasts']['1w']['low']}$  │ جودة:{d['tf_forecasts']['1w'].get('quality','—')}%
   🗓️ شهر    │ إغلاق: {d['tf_forecasts']['1mo']['close']}$ │  قمة: {d['tf_forecasts']['1mo']['high']}$ │  قاع: {d['tf_forecasts']['1mo']['low']}$ │ جودة:{d['tf_forecasts']['1mo'].get('quality','—')}%
━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 صفقات متقدمة (آجل وفوري)
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
فيبو: 78.6%={d['fib']['78.6%']}$ | 61.8%={d['fib']['61.8%']}$ | 50%={d['fib']['50.0%']}$
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
   📈 صعود (X%): كسر {refs['above']}$ → الهدف [رقم]$ — فوري (Spot) أو آجل (Futures)
   📉 هبوط (Y%): كسر {refs['below']}$ → الهدف [رقم]$ — فوري (Spot) أو آجل (Futures)
   ⚡ تذبذب (Z%): النطاق [رقم]$-[رقم]$ — فوري (Spot) أو آجل (Futures)"""

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

    # ── 5. الاتجاه العام ──
    ema50 = d.get('ema50', gold)
    ema200 = d.get('ema200', gold)
    
    ma50_state = 'أعلى' if gold > ema50 else 'أدنى'
    ma50_match = 'يتوافق' if (gold > ema50) == is_up else 'يتعارض'
    ma50_desc  = 'يدعم السعر بقوة' if (gold > ema50) == is_up else 'ما زال يُشير إلى ضعف السعر' if not is_up else 'ما زال يُشير إلى ضغط على السعر'
    ma50_text = f"متوسط 50 يوم:\nالسعر الحالي {ma50_state} من متوسط 50 يوم البالغ {ema50:,.2f} دولار. هذا يعني أن الزخم اليومي {ma50_match} مع الاتجاه المتوسط المدى، والذي {ma50_desc} على المدى المتوسط."

    ma200_state = 'أعلى' if gold > ema200 else 'أدنى'
    ma200_desc = 'يدعم السعر من الأسفل' if gold > ema200 else 'يضغط على السعر من الأعلى'
    ma_support = 'مدعوماً بشكل هيكلي' if (gold > ema50 and gold > ema200) == is_up else 'يواجه ضغطاً هيكلياً'
    ma200_text = f"متوسط 200 يوم:\nالسعر أيضاً {ma200_state} من متوسط 200 يوم البالغ {ema200:,.2f} دولار. الاتجاه العام على المدى البعيد ما زال {ma200_desc}، مما يعني أن {dir_str_noun_def} الحالي {ma_support} من كلا المتوسطين."

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
        else: hit_first = 'غير محدد ⚖️ (سوق عرضي بحت)'

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
        "   \u2570\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u256f",
        "",
        "   \u2139\ufe0f \u0647\u0630\u0627 \u0627\u0644\u062a\u0648\u0642\u0639 \u0645\u0628\u0646\u064a \u0639\u0644\u0649: ATR + ADX(\u0642\u0648\u0629 \u0627\u0644\u062a\u0631\u0646\u062f) + \u062a\u0648\u0627\u0641\u0642 \u0627\u0644\u0625\u0637\u0627\u0631\u0627\u062a + \u0641\u064a\u0628\u0648\u0646\u0627\u062a\u0634\u064a",
    ]
    return "\n".join(lines_out)


def generate_report(d: dict, is_alert: bool = False, price_diff: float = 0.0, is_morning: bool = False) -> str | None:
    client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
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
                    {"role": "system", "content": "أنت محلل ذهب كمي. اكتب فقط ما طُلب منك بالعربية الفصحى. لا تكتب أي شيء خارج الأقسام المطلوبة."},
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
                time.sleep(2)
                continue
            log.error(f"❌ [{model_name}] {e}")
            break

    log.error("❌ جميع الموديلات فشلت — إرسال الجزء الثابت فقط.")
    return fixed_block


# ══════════════════════════════════════════════
#  8. إرسال تيليجرام
# ══════════════════════════════════════════════
CHUNK_SIZE = 3800   # أقل من 4096 (حد تيليجرام بـ UTF-16) — هامش أمان للإيموجي

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

    for i, line in enumerate(lines):
        new_block = (current + "\n" + line) if current else line
        if _tg_len(new_block) > CHUNK_SIZE:
            if current:
                chunks.append(current.strip())
            current = line
        else:
            current = new_block

        # لو السطر التالي فاصل والجزء الحالي فوق 70% من الحد → اقطع هنا
        next_line = lines[i + 1] if i + 1 < len(lines) else ""
        if (next_line.startswith(SEPARATOR) and
                _tg_len(current) > CHUNK_SIZE * 0.70):
            chunks.append(current.strip())
            current = ""

    if current:
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


def _http_send(text: str) -> bool:
    """الإرسال عبر HTTP Bot API — الوسيلة الأساسية."""
    url     = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    headers = {
        "Connection": "close",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    success = True
    for chat in TARGET_CHATS:
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


async def _telethon_bot_send(text: str) -> bool:
    """MTProto باستخدام توكن البوت — يتجاوز حجب HTTP نهائياً ولا يتعارض مع جلسات المستخدم"""
    try:
        # استخدام ملف جلسة محلي بدلاً من الذاكرة لتجنب تسجيل الدخول بالتوكن في كل رسالة (يمنع الـ FloodWait)
        client = TelegramClient("goldbot_bot_session", API_ID, API_HASH)
        await client.start(bot_token=TELEGRAM_BOT_TOKEN)
        # جلب المحادثات للكاش عشان يقدر يتعرف على الـ ID بتاع القنوات البرايفت
        try:
            await client.get_dialogs()
        except Exception:
            pass
            
        for chat in TARGET_CHATS:
            try:
                await client.send_message(chat, text)
            except Exception as inner_e:
                log.warning(f"⚠️ [Telethon Bot] فشل الإرسال للجروب {chat}: {inner_e}")
                
        await client.disconnect()
        return True
    except Exception as e:
        log.warning(f"⚠️ [Telethon Bot] {e}")
        return False


def _send_single(text: str) -> bool:
    """إرسال عبر MTProto (Bot) أولاً للهروب من مشاكل Timeout، والـ HTTP كاحتياطي."""
    try:
        ok = asyncio.run(_telethon_bot_send(text))
        if ok:
            log.info("✅ [Telethon Bot] تم الإرسال بنجاح.")
            return True
    except RuntimeError:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            ok = loop.run_until_complete(_telethon_bot_send(text))
            loop.close()
            if ok:
                log.info("✅ [Telethon Bot] تم الإرسال بنجاح.")
                return True
        except Exception as e:
            log.warning(f"⚠️ [Telethon Bot loop] {e}")
    except Exception as e:
        log.warning(f"⚠️ [Telethon Bot] {e}")

    log.warning("⚠️ [Telethon Bot] فشل — جاري المحاولة عبر HTTP...")
    if _http_send(text):
        log.info("✅ [HTTP] تم الإرسال بنجاح.")
        return True
    log.error("❌ فشل الإرسال من جميع الوسائل.")
    return False


def send_to_telegram(message: str) -> bool:
    if not message:
        return False
    chunks = _split_message(message)
    log.info(f"📤 إرسال في {len(chunks)} جزء...")
    all_ok = True
    for i, chunk in enumerate(chunks, 1):
        prefix = f"[{i}/{len(chunks)}] " if len(chunks) > 1 else ""
        ok     = _send_single(prefix + chunk)
        log.info(f"✅ جزء {i}/{len(chunks)} وصل." if ok else f"❌ فشل جزء {i}/{len(chunks)}.")
        all_ok = all_ok and ok
        if i < len(chunks): time.sleep(1.5)
    return all_ok


# ══════════════════════════════════════════════
#  9. الحلقة الرئيسية
# ══════════════════════════════════════════════
def run_bot():
    log.info("🚀 Goldbot Pro+ v4 — Spot/Futures + هيكل ثابت + SL≤38$ + هدف مفتوح")

    last_gold_price      = None
    minutes_counter      = 0
    morning_sent_today   = False
    closing_sent_today   = False
    heartbeat_sent_today = False
    all_models_notified  = False
    last_report_date     = None
    consec_failures      = 0
    market_closed_notified = False   # يُبعت إشعار الإغلاق مرة واحدة فقط
    day_names = ["اثنين","ثلاثاء","أربعاء","خميس","جمعة","سبت","أحد"]

    while True:
        now_cairo  = cairo_now()
        today      = now_cairo.date()
        hour_cairo = now_cairo.hour
        weekday    = now_cairo.weekday()

        if last_report_date != today:
            morning_sent_today   = False
            closing_sent_today   = False
            heartbeat_sent_today = False
            all_models_notified  = False

        if not is_market_open():
            # — إرسال إشعار "سوق مغلق" مرة واحدة فقط لكل فترة إغلاق —
            if not market_closed_notified:
                now_c    = cairo_now()
                wday     = now_c.weekday()
                hr       = now_c.hour

                # تحديد السبب
                if wday == 5:                               # السبت
                    reason   = "عطلة نهاية الأسبوع (السبت)"
                    reopen   = "الاثنين 01:00 بتوقيت القاهرة"
                    details  = "أسواق الذهب والعملات والمعادن تغلق كل جمعة مساءً وتعود مطلع الأسبوع."
                elif wday == 6:                             # الأحد
                    reason   = "عطلة نهاية الأسبوع (الأحد)"
                    reopen   = "الاثنين 01:00 بتوقيت القاهرة"
                    details  = "أسواق الذهب والعملات والمعادن تغلق كل جمعة مساءً وتعود مطلع الأسبوع."
                elif wday == 0 and hr < MARKET_OPEN_HOUR:  # الاثنين قبل الفتح
                    reason   = "ما زلنا في ساعات الإغلاق (الاثنين قبل الفتح)"
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
            last_gold_price = None
            time.sleep(30 * 60)
            continue

        # السوق مفتوح — نعيد تهيئة الفلاج عشان الإغلاق الجاي يبعت إشعار تاني
        market_closed_notified = False

        data = get_full_market_data()

        if data and data["gold"]:
            consec_failures     = 0
            all_models_notified = False
            current_gold        = data["gold"]

            if last_gold_price is None and last_report_date != today:
                log.info("📊 إرسال التقرير الافتتاحي...")
                report = generate_report(data, is_alert=False)
                if report: send_to_telegram(report)
                last_gold_price  = current_gold
                last_report_date = today
                minutes_counter  = 0

            elif hour_cairo == HEARTBEAT_HOUR and not heartbeat_sent_today:
                conf = data['confluence']
                send_to_telegram(
                    f"💚 [Goldbot Heartbeat] البوت يعمل بشكل طبيعي ✔️\n"
                    f"💰 آجل: {data['gold_futures']:.2f}$"
                    + (f" | فوري: {data['gold_spot']:.2f}$" if data['gold_spot'] else "") + "\n"
                    f"🎯 {conf['verdict']}\n"
                    f"🕐 {now_cairo.strftime('%H:%M قاهرة')}"
                )
                heartbeat_sent_today = True

            elif hour_cairo == MORNING_HOUR_CAI and not morning_sent_today:
                log.info("🌅 إرسال تقرير الصباح...")
                report = generate_report(data, is_alert=False, is_morning=True)
                if report:
                    send_to_telegram(report)
                    morning_sent_today = True
                    last_gold_price    = current_gold
                    minutes_counter    = 0

            elif hour_cairo == CLOSING_HOUR_CAI and not closing_sent_today:
                log.info("🌙 إرسال ملخص الجلسة...")
                report = generate_report(data, is_alert=False)
                if report:
                    send_to_telegram("🌙 [ملخص جلسة اليوم — تقرير نهائي]\n" + report)
                    closing_sent_today = True
                    last_gold_price    = current_gold
                    minutes_counter    = 0

            else:
                price_diff = current_gold - (last_gold_price or current_gold)
                if abs(price_diff) >= ALERT_THRESHOLD:
                    log.info(f"🚨 تحرك حاد {price_diff:+.2f}$")
                    report = generate_report(data, is_alert=True, price_diff=price_diff)
                    if report:
                        send_to_telegram(report)
                        last_gold_price = current_gold
                        minutes_counter = 0
                elif minutes_counter >= ROUTINE_MINUTES:
                    log.info(f"⏰ مرت {ROUTINE_MINUTES} دقيقة — تقرير دوري...")
                    report = generate_report(data, is_alert=False)
                    if report:
                        send_to_telegram(report)
                        last_gold_price = current_gold
                        minutes_counter = 0
        else:
            consec_failures += 1
            log.warning(f"⚠️ فشل جلب البيانات مرة {consec_failures}.")
            if consec_failures >= 3 and not all_models_notified:
                send_to_telegram(
                    "🚨 تحذير — جولدبوت يواجه مشكلة!\n"
                    "تعذّر جلب البيانات. سيتم إعادة المحاولة تلقائياً."
                )
                all_models_notified = True

        time.sleep(60)
        minutes_counter += 1