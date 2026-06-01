import yfinance as yf
from groq import Groq
import requests
from datetime import datetime, timezone, timedelta
import time
import os
import logging
import numpy as np
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
    "mixtral-8x7b-32768",
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logging.getLogger('yfinance').setLevel(logging.CRITICAL)  # منع رسائل ياهو المزعجة
log = logging.getLogger(__name__)

GROQ_API_KEY       = os.environ.get("GROQ_API_KEY")
TELEGRAM_BOT_TOKEN = "8678714877:AAE2v6jeeYzsNFYj_83rXK32RJEA7fszQew"
TELEGRAM_CHAT_ID   = -1003775201576

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
    trend   = "صعودي 🟢" if obv_arr[-1] > np.mean(obv_arr[-20:]) else "هبوطي 🔴"
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
    if p2_hi > p1_hi * 1.001 and r2_hi < r1_hi * 0.985:
        return "⚠️ تباين هبوطي — السعر يصنع قمة أعلى وRSI أدنى ⚠️"
    # تباين صعودي: سعر قاع أدنى + RSI قاع أعلى
    if p2_lo < p1_lo * 0.999 and r2_lo > r1_lo * 1.015:
        return "💡 تباين صعودي — السعر يصنع قاعاً أدنى وRSI أعلى 💡"
    return "⚪ لا يوجد تباين واضح"


def calc_trade_confidence(d: dict, t: dict) -> tuple[str, str]:
    """درجة ثقة الصفقة 1-5 نجوم لكل صفقة منفصلة مع سبب التقييم"""
    score = 0
    reasons = []
    is_buy = t['is_buy']
    gold = d['gold']
    
    # 1. التوافق مع الترند العام
    trend_bias = d['confluence']['bias']
    if (is_buy and trend_bias == 'bull') or (not is_buy and trend_bias == 'bear'):
        score += 1
        reasons.append("مع الترند")
    else:
        reasons.append("عكس الترند")

    # 2. العائد للمخاطرة (R:R) للهدف الأول
    if t['rr1'] >= 2.5:
        score += 1
        reasons.append(f"عائد ضخم ({t['rr1']}x)")
    elif t['rr1'] >= 1.5:
        reasons.append(f"عائد جيد ({t['rr1']}x)")
    else:
        reasons.append("عائد ضعيف")

    # 3. نوع الصفقة (محافظ / عدواني)
    if "محافظ" in t['style']:
        score += 2
        reasons.append("مستوى آمن")
    elif "معتدل" in t['style']:
        score += 1
        reasons.append("مستوى متوسط")
    else:
        reasons.append("دخول خطر")

    # 4. البعد عن السعر الحالي (تجنب الضوضاء)
    dist = abs(t['entry'] - gold)
    atr = d.get('atr', 10)
    if dist >= atr * 0.4:
        score += 1
        reasons.append("نقطة دخول ممتازة")

    # تقييد النجوم بين 1 و 5
    score = max(1, min(5, score))
    stars  = "⭐" * score + "☆" * (5 - score)
    
    # تنسيق السبب النهائي بشكل مختصر وجميل
    final_reason = "، ".join(reasons[:3]) # نكتفي بأهم 3 أسباب حتى لا يطول السطر
    labels = {5:'ممتازة',4:'قوية',3:'جيدة',2:'ضعيفة',1:'خطرة'}
    return f"{stars} {labels.get(score,'')}", final_reason


def calc_all_entries(d: dict, bias: str) -> dict:
    """
    3 صفقات شراء + 3 صفقات بيع مبنية على مستويات تقنية حقيقية.
    القاعدة: الصفقة المعتدلة (2) دائماً Futures بـ 38$ — الأخريان Spot بـ 15$.
    """
    gold   = d['gold']
    s1, r1 = d['s1'], d['r1']
    s2, r2 = d['s2'], d['r2']
    s3, r3 = d['s3'], d['r3']
    rn     = d['round_numbers']

    MIN_GAP = 8.0  # حد أدنى للفرق بين الأهداف

    def _buy_t(e):
        """أهداف الشراء: تصاعدية خالصة مع فجوات كافية"""
        raw  = sorted(set([x for x in [r1,r2,r3,rn['nearest_resistance']] if x and x > e]))
        # ازل المستويات القريبة جداً من بعضها
        pool = []
        for x in raw:
            if not pool or x - pool[-1] >= MIN_GAP:
                pool.append(x)
        t1 = pool[0] if len(pool)>0 else round(e+30,2)
        t2 = pool[1] if len(pool)>1 else round(t1+50,2)
        t3 = pool[2] if len(pool)>2 else round(t2+50,2)
        return t1, t2, t3

    def _sell_t(e):
        """أهداف البيع: تنازلية خالصة مع فجوات كافية"""
        raw  = sorted(set([x for x in [s1,s2,s3,rn['nearest_support']] if x and x < e]), reverse=True)
        # ازل المستويات القريبة جداً من بعضها
        pool = []
        for x in raw:
            if not pool or pool[-1] - x >= MIN_GAP:
                pool.append(x)
        t1 = pool[0] if len(pool)>0 else round(e-30,2)
        t2 = pool[1] if len(pool)>1 else round(t1-50,2)
        t3 = pool[2] if len(pool)>2 else round(t2-50,2)
        return t1, t2, t3

    def mb(entry, sl_d, mkt, style):
        e=round(entry,2); t1,t2,t3=_buy_t(e)
        rr1=round((t1-e)/sl_d,1); rr2=round((t2-e)/sl_d,1); rr3=round((t3-e)/sl_d,1)
        return {"dir":"شراء 📗","market":mkt,"style":style,"entry":e,
                "sl":round(e-sl_d,2),"risk":sl_d,"t1":t1,"t2":t2,"t3":t3,
                "rr1":rr1,"rr2":rr2,"rr3":rr3,"is_buy":True}

    def ms(entry, sl_d, mkt, style):
        e=round(entry,2); t1,t2,t3=_sell_t(e)
        rr1=round((e-t1)/sl_d,1); rr2=round((e-t2)/sl_d,1); rr3=round((e-t3)/sl_d,1)
        return {"dir":"بيع 📕","market":mkt,"style":style,"entry":e,
                "sl":round(e+sl_d,2),"risk":sl_d,"t1":t1,"t2":t2,"t3":t3,
                "rr1":rr1,"rr2":rr2,"rr3":rr3,"is_buy":False}

    if bias == "bull":
        buys  = [mb(gold, TIGHT_SL, "فوري (Spot)",   "🔴 عدواني"),
                 mb(s1,   STD_SL,   "آجل (Futures)", "🟡 معتدل — S1"),
                 mb(s2,   TIGHT_SL, "فوري (Spot)",   "🟢 محافظ — S2")]
        sells = [ms(r1,   TIGHT_SL, "فوري (Spot)",   "🔴 بيع R1"),
                 ms(r2,   STD_SL,   "آجل (Futures)", "🟡 بيع R2"),
                 ms(r3,   TIGHT_SL, "فوري (Spot)",   "🟢 بيع R3")]
    elif bias == "bear":
        sells = [ms(gold, TIGHT_SL, "فوري (Spot)",   "🔴 عدواني"),
                 ms(r1,   STD_SL,   "آجل (Futures)", "🟡 معتدل — R1"),
                 ms(r2,   TIGHT_SL, "فوري (Spot)",   "🟢 محافظ — R2")]
        buys  = [mb(s1,   TIGHT_SL, "فوري (Spot)",   "🔴 شراء S1"),
                 mb(s2,   STD_SL,   "آجل (Futures)", "🟡 شراء S2"),
                 mb(s3,   TIGHT_SL, "فوري (Spot)",   "🟢 شراء S3")]
    else:  # neutral
        buys  = [mb(rn['nearest_resistance'], TIGHT_SL, "فوري (Spot)",   "🔴 اختراق نفسي"),
                 mb(r1,   STD_SL,   "آجل (Futures)", "🟡 اختراق R1"),
                 mb(r2,   TIGHT_SL, "فوري (Spot)",   "🟢 اختراق R2")]
        sells = [ms(rn['nearest_support'],   TIGHT_SL, "فوري (Spot)",   "🔴 كسر نفسي"),
                 ms(s1,   STD_SL,   "آجل (Futures)", "🟡 كسر S1"),
                 ms(s2,   TIGHT_SL, "فوري (Spot)",   "🟢 كسر S2")]


    refs = {
        "above": round(min([x for x in [r1,rn['nearest_resistance']] if x and x>gold], default=r1), 2),
        "below": round(max([x for x in [s1,rn['nearest_support']]    if x and x<gold], default=s1), 2),
        "r1":r1,"r2":r2,"s1":s1,"s2":s2,
    }
    return {
        "bias":bias, "buys":buys, "sells":sells, "refs":refs,
        "momentum":  calc_momentum_signal(d),
        "trend":     calc_trend_signal(d),
        "liquidity": calc_liquidity_signal(d),
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
    # الفوري: نجرب 2m أولاً للحصول على سعر لايف — ثم fallback تدريجي
    gold_spot_df = _fetch("XAUUSD=X", period="1d",  interval="2m"); time.sleep(0.5)
    _sp, _       = _last_with_date(gold_spot_df)
    if not _sp:
        gold_spot_df = _fetch("XAUUSD=X", period="5d",  interval="1h"); time.sleep(0.5)
        _sp, _   = _last_with_date(gold_spot_df)
        
    gold_spot, spot_date = _sp, _
    
    # إذا فشل ياهو تماماً في الفوري (غالبًا بيعمل Block لـ HuggingFace)، نستخدم Binance PAXG (توكن الذهب الفعلي 1:1) كبديل فوري حقيقي 24/7
    if not gold_spot:
        try:
            resp = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=PAXGUSDT", timeout=5)
            if resp.status_code == 200:
                gold_spot = float(resp.json()['price'])
                spot_date = datetime.now().strftime("%d/%m %H:%M") + " (PAXG/Binance)"
        except Exception:
            pass

    if not gold_spot:
        # لو فشل حتى بينانس، نستخدم GC=F بدقائق صغيرة (أحدث سعر متاح)
        gold_spot_df = _fetch("GC=F",     period="2d",  interval="5m"); time.sleep(0.5)
        gold_spot, spot_date = _last_with_date(gold_spot_df)


    if gold_daily is None or gold_daily.empty:
        return None

    # ── الأسواق الأخرى ──
    silver_df = _fetch("SI=F",     period="60d"); time.sleep(0.6)
    oil_df    = _fetch("CL=F",     period="60d"); time.sleep(0.6)
    dxy_df    = _fetch("DX-Y.NYB", period="60d"); time.sleep(0.6)
    tnx_df    = _fetch("^TNX",     period="60d"); time.sleep(0.6)
    tip_df    = _fetch("TIP",      period="60d"); time.sleep(0.6)
    vix_df    = _fetch("^VIX",     period="60d"); time.sleep(0.6)
    sp500_df  = _fetch("^GSPC",    period="60d"); time.sleep(0.6)

    gold_futures, futures_date = _last_with_date(gold_daily)
    # لو الفوري مش متاح نستخدم الآجل كمرجع (فارقهم صغير)
    if not gold_spot:
        gold_spot  = gold_futures
        spot_date  = futures_date + " (آجل)"
    silver = _last_close(silver_df)
    oil    = _last_close(oil_df)
    dxy    = _last_close(dxy_df)
    tnx    = _last_close(tnx_df)
    vix    = _last_close(vix_df)
    sp500  = _last_close(sp500_df)

    if not all([gold_futures, dxy, tnx]):
        return None

    gold = gold_futures   # الأساس للحسابات هو الآجل

    # ── تحليل الإطارات الزمنية ──
    tf_weekly = analyze_timeframe(gold_weekly, "أسبوعي")
    tf_daily  = analyze_timeframe(gold_daily,  "يومي")
    tf_hourly = analyze_timeframe(gold_hourly, "ساعي")
    tf_label  = get_tf_confluence_label(tf_weekly, tf_daily, tf_hourly)

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
    round_numbers              = get_round_numbers(gold, step=50)

    # ── العائد الحقيقي (TIP ETF) ──
    real_yield_signal = "غير متاح"
    if tip_df is not None and not tip_df.empty and len(tip_df) >= 10:
        tip_closes = tip_df['Close'].values
        tip_trend  = tip_closes[-1] - np.mean(tip_closes[-10:])
        real_yield_signal = ("🟢 العائد الحقيقي ينخفض — بيئة موات للذهب"
                             if tip_trend > 0 else
                             "🔴 العائد الحقيقي يرتفع — ضغط على الذهب")

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
    gs_ratio    = round(gold / silver, 1) if silver else None
    contango    = round(gold_futures - gold_spot, 2) if gold_spot else None

    d = dict(
        gold=gold, gold_futures=gold_futures, gold_spot=gold_spot,
        futures_date=futures_date, spot_date=spot_date,
        contango=contango,
        silver=silver, oil=oil, dxy=dxy, tnx=tnx, vix=vix, sp500=sp500,
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
        tf_weekly=tf_weekly, tf_daily=tf_daily, tf_hourly=tf_hourly, tf_label=tf_label,
        gs_ratio=gs_ratio, dxy_bias=dxy_bias, bond_bias=bond_bias,
        gold_pressure=gold_pres, vix_label=vix_label,
    )

    d['confluence'] = calc_confluence(d)
    d['entries']    = calc_all_entries(d, d['confluence']['bias'])
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
    date_now = cairo_now().strftime("%Y-%m-%d %H:%M قاهرة")
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
        lines=[]
        for i,t in enumerate(trades):
            conf_str, reason = calc_trade_confidence(d, t)
            lines.append(
                f"   {nums[i]} [{t['style']}] {t['market']} | {conf_str}\n"
                f"      💡 السبب: {reason}\n"
                f"      دخول: {t['entry']}$ | وقف: {t['sl']}$ (خطر: {t['risk']}$)\n"
                f"      T1:{t['t1']}$(R:{t['rr1']}x) | T2:{t['t2']}$(R:{t['rr2']}x) | T3:{t['t3']}$(R:{t['rr3']}x)"
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

    fixed = f"""💰 {header}
🕐 {date_now}
━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 أسعار الذهب
   فوري  (XAU/USD) : {spot_label}
   آجل   (GC=F)    : {futures_label}{contango_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 ملخص السوق
   الزخم        : {ent['momentum']}
   الاتجاه العام : {ent['trend']}
   السيولة       : {ent['liquidity']}
━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 حكم السوق: {conf['verdict']}
{score_table}
   ∑ {conf['total']:+d}/±{conf['n']}  ▪ 🟢{conf['bullish']} 🔴{conf['bearish']} ⚪{conf['neutral']}
━━━━━━━━━━━━━━━━━━━━━━━━━━
🕐 الإطارات الزمنية: {d['tf_label']}
   📅 {d['tf_weekly']['bias']} | RSI={d['tf_weekly']['rsi']}
   📆 {d['tf_daily']['bias']}  | RSI={d['tf_daily']['rsi']}
   ⏱️ {d['tf_hourly'].get('bias','—')} | RSI={d['tf_hourly'].get('rsi','—')}
━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 حركة السعر: {hist_line}
━━━━━━━━━━━━━━━━━━━━━━━━━━
📡 الأسواق
   DXY:{d['dxy']:.1f}({d['dxy_bias']}) | 10Y:{d['tnx']:.2f}%({d['bond_bias']}) | VIX:{f"{d['vix']:.1f}" if d['vix'] else '—'}({d['vix_label'] if d['vix'] else '—'})
   🥈{f"{d['silver']:.2f}$" if d['silver'] else '—'} | 🛢️{f"{d['oil']:.1f}$" if d['oil'] else '—'} | 📊S&P:{f"{d['sp500']:.0f}" if d['sp500'] else '—'}
   {d['real_yield_signal']}
━━━━━━━━━━━━━━━━━━━━━━━━━━
🧮 المؤشرات
   RSI:{d['rsi']}({d['rsi_label'].split()[0]}) | StochK:{d['stoch_k']} | MACD:{d['macd_hist']}({d['macd_label'].split()[0]})
   BB:{d['bb_upper']}/{d['bb_mid']}/{d['bb_lower']}({d['bb_label'].split()[0]}) | EMA:{d['ema_label']}
   ADX:{d['adx']}(DI+{d['di_plus']}/DI-{d['di_minus']}) | CCI:{d['cci']} | W%R:{d['williams_r']}
   OBV:{d['obv_trend']} | حجم:{d['rel_vol_label'].split('—')[0].strip()} | ATR:{d['atr']}$
━━━━━━━━━━━━━━━━━━━━━━━━━━
🔢 المستويات
   🟣 مقاومة نفسية:{rn['nearest_resistance']}$(↑{rn['dist_to_resistance']}$) | دعم نفسي:{rn['nearest_support']}$(↓{rn['dist_to_support']}$)
   📍 High:{d['swing_high']}$ / Low:{d['swing_low']}$
   🔴 R1:{d['r1']}$ R2:{d['r2']}$ | Pivot:{d['pivot']}$ | 🟢 S1:{d['s1']}$ S2:{d['s2']}$
   🟠 {fib_line}
   📊 {range_line}
   🔍 التباين: {d['divergence']}
━━━━━━━━━━━━━━━━━━━━━━━━━━
{bias_section}
🛒 صفقات الشراء:
{buy_block}
━━
📉 صفقات البيع:
{sell_block}
   ↑ مراقبة: {refs['above']}$ | ↓ مراقبة: {refs['below']}$"""

    # ── تعليمات الـ AI ──
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
4. السيناريوهات الثلاثة مجموعها 100% ولا يجوز أن يكون أي واحد منهم 0% أو أقل من 10%
5. {prob_floor} — هذا حد أدنى للسيناريو الرئيسي، والباقيان لا يقل أي منهم عن 15%

بيانات السوق:
سعر الذهب = {gold:.2f}$ | RSI={d['rsi']} | ADX={d['adx']} | MACD={d['macd_hist']}
الزخم: {ent['momentum']} | الاتجاه: {ent['trend']} | السيولة: {ent['liquidity']}
حكم السوق: {conf['verdict']}

صفقات الشراء:
{_fmt_ai(ent['buys'])}
صفقات البيع:
{_fmt_ai(ent['sells'])}

اكتب هذه الأقسام فقط بالترتيب:

━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 التحليل الكمي
━━━━━━━━━━━━━━━━━━━━━━━━━━

**📌 خلاصة:** [جملة واحدة — {bias_ar} + الاحتمالية بالأرقام مثل 50%]

**🔍 الإطارات الزمنية:** [جملتان — بناءً على المعطى التالي: "{d['tf_label']}". اشرح هل هي متوافقة وماذا تعني للحركة القادمة؟]

**📉 السيناريوهات (100%):**
   📈 صعود (X%): كسر {refs['above']}$ → الهدف بالأرقام
   📉 هبوط (Y%): كسر {refs['below']}$ → الهدف بالأرقام
   ⚡ تذبذب (Z%): النطاق والشرط — [X+Y+Z=100، كل واحد ≥ 15%]"""

    return fixed, ai_instructions

def generate_report(d: dict, is_alert: bool = False, price_diff: float = 0.0, is_morning: bool = False) -> str | None:
    client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
    if not client:
        return None

    if is_morning:  header = "🌅 نشرة الصباح — استراتيجية اليوم"
    elif is_alert:  header = f"🚨 تنبيه — حركة {'+' if price_diff>0 else ''}{price_diff:.2f}$"
    else:           header = "📊 نشرة التحليل الكمي للذهب"

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
CHUNK_SIZE = 4090   # حد تيليجرام 4096 — نترك هامش 6 أحرف


def _split_message(text: str) -> list:
    if len(text) <= CHUNK_SIZE:
        return [text]
    chunks, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > CHUNK_SIZE:
            if current: chunks.append(current.strip())
            current = line
        else:
            current = (current + "\n" + line) if current else line
    if current: chunks.append(current.strip())
    return chunks


async def _telethon_send(text: str) -> bool:
    """MTProto بجلسة المستخدم الموجودة — يتجاوز حجب api.telegram.org تماماً"""
    if not SESSION_STRING:
        log.warning("⚠️ [Telethon] SESSION_STRING غير موجود.")
        return False
    try:
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        await client.start()   # جلسة موجودة — بدون ImportBotAuthorizationRequest
        await client.send_message(TELEGRAM_CHAT_ID, text)
        await client.disconnect()
        return True
    except Exception as e:
        log.warning(f"⚠️ [Telethon] {e}")
        return False


def _http_send(text: str) -> bool:
    """الإرسال عبر HTTP Bot API — الوسيلة الأساسية."""
    url     = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": str(TELEGRAM_CHAT_ID), "text": text}
    for attempt in range(4):
        try:
            r = requests.post(url, json=payload, headers={"Connection": "close"}, timeout=(10, 30))
            r.raise_for_status()
            return True
        except Exception as e:
            wait = 2 ** attempt
            log.warning(f"⚠️ [HTTP] {attempt+1}/4 — {e} — انتظار {wait}s")
            time.sleep(wait)
    return False


def _send_single(text: str) -> bool:
    """Telethon (MTProto) أولاً — يتجاوز الحجب. HTTP كاحتياطي أخير."""
    # المحاولة الأولى: Telethon بجلسة المستخدم عبر MTProto
    try:
        ok = asyncio.run(_telethon_send(text))
        if ok:
            log.info("✅ [Telethon] تم الإرسال.")
            return True
    except RuntimeError:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            ok = loop.run_until_complete(_telethon_send(text))
            loop.close()
            if ok:
                log.info("✅ [Telethon loop] تم الإرسال.")
                return True
        except Exception as e:
            log.warning(f"⚠️ [Telethon loop] {e}")
    except Exception as e:
        log.warning(f"⚠️ [Telethon] {e}")
    # الاحتياطي الأخير: HTTP Bot API
    log.warning("⚠️ [Telethon] فشل — جاري المحاولة عبر HTTP...")
    if _http_send(text):
        log.info("✅ [HTTP] تم الإرسال.")
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
            log.info(f"🛌 سوق مغلق ({day_names[weekday]} {hour_cairo:02d}:00 قاهرة). انتظار 30 دقيقة.")
            last_gold_price = None
            time.sleep(30 * 60)
            continue

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