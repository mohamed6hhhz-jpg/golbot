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
#  1. جلب البيانات — متعددة الإطارات الزمنية
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
    def wilder(arr, n):
        res = [sum(arr[:n])]
        for v in arr[n:]: res.append(res[-1] - res[-1]/n + v)
        return res
    atr_s  = wilder(tr_list, period)
    dip_s  = wilder(dm_plus,  period)
    dim_s  = wilder(dm_minus, period)
    di_p   = [100 * dip_s[i] / (atr_s[i] + 1e-9) for i in range(len(atr_s))]
    di_m   = [100 * dim_s[i] / (atr_s[i] + 1e-9) for i in range(len(atr_s))]
    dx     = [100 * abs(di_p[i]-di_m[i]) / (di_p[i]+di_m[i]+1e-9) for i in range(len(atr_s))]
    adx_s  = wilder(dx, period)
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
    """On-Balance Volume + اتجاهه."""
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
    obv_arr  = np.array(obv_series)
    trend    = "صعودي 🟢" if obv_arr[-1] > np.mean(obv_arr[-20:]) else "هبوطي 🔴"
    return round(float(obv_arr[-1]), 0), trend


def calc_relative_volume(df, period: int = 20) -> tuple:
    """نسبة حجم اليوم إلى متوسط الـ 20 يوم."""
    if df is None or len(df) < period + 1 or 'Volume' not in df.columns:
        return 1.0, "محايد"
    vols = df['Volume'].values.astype(float)
    if np.mean(vols[-period-1:-1]) == 0:
        return 1.0, "محايد"
    rel_vol = vols[-1] / np.mean(vols[-period-1:-1])
    if rel_vol > 1.5:
        label = f"عالي جداً ({rel_vol:.1f}x) — تحرك مؤسسي 🔥"
    elif rel_vol > 1.0:
        label = f"فوق المتوسط ({rel_vol:.1f}x) ⬆️"
    elif rel_vol > 0.5:
        label = f"دون المتوسط ({rel_vol:.1f}x) ⬇️"
    else:
        label = f"منخفض جداً ({rel_vol:.1f}x) — إشارات ضعيفة ⚠️"
    return round(rel_vol, 2), label


def calc_atr(df, period: int = 14) -> float:
    if df is None or len(df) < period + 1: return 0.0
    h, l, c = df['High'].values, df['Low'].values, df['Close'].values
    tr_list = [max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1])) for i in range(1, len(df))]
    return round(float(np.mean(tr_list[-period:])), 2)


def calc_atr_regime(df, period: int = 14) -> str:
    """هل التقلب ينفجر أم ينكمش؟"""
    if df is None or len(df) < period * 2 + 1:
        return "غير محدد"
    h, l, c = df['High'].values, df['Low'].values, df['Close'].values
    tr_list = [max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1])) for i in range(1, len(df))]
    atr_now = np.mean(tr_list[-period:])
    atr_old = np.mean(tr_list[-period*2:-period])
    if atr_now > atr_old * 1.25:
        return "تقلب متصاعد 🔥 — اختراق جارٍ أو وشيك"
    elif atr_now < atr_old * 0.80:
        return "تقلب منخفض جداً ⚡ — اختراق قريب (ضغط متراكم)"
    else:
        return "تقلب عادي ⚪"


def calc_fibonacci(closes: np.ndarray, lookback: int = 30):
    if len(closes) < lookback: lookback = len(closes)
    w = closes[-lookback:]
    high, low = float(np.max(w)), float(np.min(w))
    d = high - low
    return {"0.0%": round(high,2), "23.6%": round(high-0.236*d,2), "38.2%": round(high-0.382*d,2),
            "50.0%": round(high-0.500*d,2), "61.8%": round(high-0.618*d,2), "78.6%": round(high-0.786*d,2), "100%": round(low,2)}


def find_swing_levels(df, lookback: int = 20):
    if df is None or len(df) < lookback: return None, None
    return round(float(np.max(df['High'].values[-lookback:])), 2), \
           round(float(np.min(df['Low'].values[-lookback:])), 2)


def get_round_numbers(price: float, step: int = 50) -> dict:
    """أقرب المستويات النفسية الكبيرة فوق وتحت السعر."""
    lower = (price // step) * step
    upper = lower + step
    return {
        "nearest_support"   : round(lower, 2),
        "nearest_resistance": round(upper, 2),
        "dist_to_support"   : round(price - lower, 2),
        "dist_to_resistance": round(upper - price, 2),
    }


def get_historical_context(df) -> dict:
    """تغير السعر على فترات 1، 7، 30 يوم + قمة وقاع 52 أسبوع."""
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
    ctx['high_52w'] = round(float(np.max(df['High'].values[-252:])), 2) if len(df) >= 252 else None
    ctx['low_52w']  = round(float(np.min(df['Low'].values[-252:])),  2) if len(df) >= 252 else None
    return ctx


# ══════════════════════════════════════════════
#  3. تحليل الإطار الزمني الواحد
# ══════════════════════════════════════════════
def analyze_timeframe(df, label: str) -> dict:
    """يحسب المؤشرات الأساسية لإطار زمني واحد ويعيد حكم صعودي/هبوطي/محايد."""
    if df is None or len(df) < 30:
        return {"label": label, "bias": "غير متاح", "rsi": 50, "ema_align": "غير متاح", "macd_hist": 0}
    closes = df['Close'].values
    rsi    = calc_rsi(closes)
    ema20  = calc_ema(closes, min(20, len(closes)//2))
    ema50  = calc_ema(closes, min(50, len(closes)//2))
    _, _, macd_hist = calc_macd(closes)
    adx, di_p, di_m = calc_adx(df)

    score = 0
    if rsi < 45:         score += 1
    elif rsi > 55:       score -= 1
    if macd_hist > 0:    score += 1
    elif macd_hist < 0:  score -= 1
    if ema20 > ema50:    score += 1
    elif ema20 < ema50:  score -= 1
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
    """هل الإطارات الزمنية الثلاثة متوافقة؟"""
    scores = [
        weekly.get("score", 0),
        daily.get("score", 0),
        hourly.get("score", 0)
    ]
    s = sum(scores)
    positives = sum(1 for x in scores if x > 0)
    negatives = sum(1 for x in scores if x < 0)

    if positives == 3:
        return "🔥 توافق تام صعودي (أسبوعي + يومي + ساعي)"
    elif negatives == 3:
        return "❄️ توافق تام هبوطي (أسبوعي + يومي + ساعي)"
    elif positives == 2:
        return "🟡 توافق جزئي صعودي (2/3 إطارات)"
    elif negatives == 2:
        return "🟠 توافق جزئي هبوطي (2/3 إطارات)"
    else:
        return "⚪ تعارض بين الإطارات الزمنية — حذر"


# ══════════════════════════════════════════════
#  4. نظام نقاط التوافق (Confluence Score)
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
    if adx > 25:
        scores['ADX']       = +1 if di_p > di_m else -1
    else:
        scores['ADX']       = 0
    scores['CCI (20)']      = +1 if d['cci'] < -100 else (-1 if d['cci'] > 100 else 0)
    scores['Williams %R']   = +1 if d['williams_r'] < -80 else (-1 if d['williams_r'] > -20 else 0)
    scores['OBV Trend']     = +1 if "صعودي" in d['obv_trend'] else (-1 if "هبوطي" in d['obv_trend'] else 0)
    tf_scores = [d['tf_weekly'].get('score',0), d['tf_daily'].get('score',0), d['tf_hourly'].get('score',0)]
    tf_avg    = sum(tf_scores) / 3
    scores['Multi-Timeframe'] = +1 if tf_avg > 0.5 else (-1 if tf_avg < -0.5 else 0)

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
#  5. نقاط الدخول الذكية
# ══════════════════════════════════════════════
def calc_smart_entries(d: dict, bias: str) -> dict:
    gold       = d['gold']
    atr        = d['atr']
    swing_high = d['swing_high']
    swing_low  = d['swing_low']
    s1, r1     = d['s1'], d['r1']
    s2, r2     = d['s2'], d['r2']
    rn         = d['round_numbers']

    # أقرب دعم: أعلى قيمة بين (Swing Low، S1، المستوى النفسي الأدنى)
    candidates_sup = [x for x in [swing_low, s1, rn['nearest_support']] if x and x < gold]
    nearest_sup    = max(candidates_sup) if candidates_sup else s1

    # أقرب مقاومة: أدنى قيمة بين (Swing High، R1، المستوى النفسي الأعلى)
    candidates_res = [x for x in [swing_high, r1, rn['nearest_resistance']] if x and x > gold]
    nearest_res    = min(candidates_res) if candidates_res else r1

    if bias == "bull":
        entry = round(nearest_sup, 2)
        sl    = round(min(swing_low or s2, s2) - 0.5 * atr, 2)
        risk  = max(round(entry - sl, 2), atr)           # R لا يقل عن ATR واحد
        tp1   = round(entry + 1.5 * risk, 2)
        tp2   = round(entry + 2.5 * risk, 2)
        return {"type": "شراء 📗", "entry": entry, "sl": sl,
                "tp1": tp1, "tp2": tp2, "risk": risk, "rr1": "1:1.5", "rr2": "1:2.5"}

    elif bias == "bear":
        entry = round(nearest_res, 2)
        sl    = round(max(swing_high or r2, r2) + 0.5 * atr, 2)
        risk  = max(round(sl - entry, 2), atr)
        tp1   = round(entry - 1.5 * risk, 2)
        tp2   = round(entry - 2.5 * risk, 2)
        return {"type": "بيع 📕", "entry": entry, "sl": sl,
                "tp1": tp1, "tp2": tp2, "risk": risk, "rr1": "1:1.5", "rr2": "1:2.5"}

    else:
        return {"type": "تذبذب — انتظر ⚪", "entry": gold,
                "sl": round(nearest_sup - atr, 2), "tp1": round(nearest_res, 2),
                "tp2": round(nearest_res + atr, 2), "risk": round(atr, 2),
                "rr1": "غير محدد", "rr2": "غير محدد"}


# ══════════════════════════════════════════════
#  6. جلب كل بيانات السوق
# ══════════════════════════════════════════════
def get_full_market_data() -> dict | None:
    log.info("📡 جلب البيانات — متعدد الإطارات الزمنية...")

    # ── الإطارات الزمنية للذهب ──
    gold_daily  = _fetch("GC=F", period="90d",  interval="1d"); time.sleep(0.8)
    gold_weekly = _fetch("GC=F", period="2y",   interval="1wk"); time.sleep(0.8)
    gold_hourly = _fetch("GC=F", period="30d",  interval="1h"); time.sleep(0.8)

    if gold_daily is None or gold_daily.empty:
        return None

    # ── الأسواق الأخرى ──
    silver_df = _fetch("SI=F",      period="60d"); time.sleep(0.7)
    oil_df    = _fetch("CL=F",      period="60d"); time.sleep(0.7)
    dxy_df    = _fetch("DX-Y.NYB",  period="60d"); time.sleep(0.7)
    tnx_df    = _fetch("^TNX",      period="60d"); time.sleep(0.7)
    tip_df    = _fetch("TIP",       period="60d"); time.sleep(0.7)  # TIPS ETF للعائد الحقيقي
    vix_df    = _fetch("^VIX",      period="60d"); time.sleep(0.7)
    sp500_df  = _fetch("^GSPC",     period="60d"); time.sleep(0.7)

    gold   = _last_close(gold_daily)
    silver = _last_close(silver_df)
    oil    = _last_close(oil_df)
    dxy    = _last_close(dxy_df)
    tnx    = _last_close(tnx_df)
    vix    = _last_close(vix_df)
    sp500  = _last_close(sp500_df)
    tip    = _last_close(tip_df)

    if not all([gold, dxy, tnx]):
        return None

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
    atr_regime                 = calc_atr_regime(gold_daily)
    fib                        = calc_fibonacci(closes)
    atr                        = calc_atr(gold_daily)
    swing_high, swing_low      = find_swing_levels(gold_daily, lookback=20)
    hist_ctx                   = get_historical_context(gold_daily)

    # ── العائد الحقيقي (Real Yield Proxy via TIP ETF) ──
    real_yield_signal = "غير متاح"
    real_yield_label  = "غير متاح"
    if tip_df is not None and not tip_df.empty and len(tip_df) >= 10:
        tip_closes  = tip_df['Close'].values
        tip_trend   = tip_closes[-1] - np.mean(tip_closes[-10:])
        if tip_trend > 0:
            real_yield_signal = "🟢 العائد الحقيقي ينخفض (TIP صاعد) — بيئة موات للذهب"
            real_yield_label  = "منخفض"
        else:
            real_yield_signal = "🔴 العائد الحقيقي يرتفع (TIP هابط) — ضغط على الذهب"
            real_yield_label  = "مرتفع"

    # ── المستويات النفسية (Round Numbers) ──
    round_numbers = get_round_numbers(gold, step=50)

    # ── Pivot Points ──
    ph, pl, pc = float(gold_daily['High'].iloc[-2]), float(gold_daily['Low'].iloc[-2]), float(gold_daily['Close'].iloc[-2])
    pivot = round((ph + pl + pc) / 3, 2)
    r1    = round(2*pivot - pl, 2);  r2 = round(pivot + (ph-pl), 2); r3 = round(ph + 2*(pivot-pl), 2)
    s1    = round(2*pivot - ph, 2);  s2 = round(pivot - (ph-pl), 2); s3 = round(pl - 2*(ph-pivot), 2)

    # ── التسميات النصية ──
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
    atr_reg     = calc_atr_regime(gold_daily)

    d = dict(
        gold=gold, silver=silver, oil=oil, dxy=dxy, tnx=tnx, vix=vix, sp500=sp500,
        rsi=rsi, rsi_label=rsi_label,
        stoch_k=stoch_k, stoch_d=stoch_d,
        macd=macd, macd_sig=macd_sig, macd_hist=macd_hist, macd_label=macd_label,
        bb_upper=bb_upper, bb_mid=bb_mid, bb_lower=bb_lower, bb_label=bb_label,
        ema20=ema20, ema50=ema50, ema200=ema200, ema_label=ema_label,
        adx=adx, di_plus=di_plus, di_minus=di_minus, adx_label=adx_label,
        cci=cci, cci_label=cci_label,
        williams_r=williams_r, wr_label=wr_label,
        obv_val=obv_val, obv_trend=obv_trend,
        rel_vol=rel_vol, rel_vol_label=rel_vol_label,
        atr=atr, atr_regime=atr_reg,
        fib=fib, swing_high=swing_high, swing_low=swing_low,
        pivot=pivot, r1=r1, r2=r2, r3=r3, s1=s1, s2=s2, s3=s3,
        round_numbers=round_numbers,
        hist_ctx=hist_ctx,
        real_yield_signal=real_yield_signal, real_yield_label=real_yield_label,
        tf_weekly=tf_weekly, tf_daily=tf_daily, tf_hourly=tf_hourly, tf_label=tf_label,
        gs_ratio=gs_ratio, dxy_bias=dxy_bias, bond_bias=bond_bias, gold_pressure=gold_pres,
        vix_label=vix_label,
    )

    d['confluence'] = calc_confluence(d)
    d['entries']    = calc_smart_entries(d, d['confluence']['bias'])
    return d


# ══════════════════════════════════════════════
#  7. توليد التقرير — Chain-of-Thought
# ══════════════════════════════════════════════
def generate_report(d: dict, is_alert: bool = False, price_diff: float = 0.0, is_morning: bool = False) -> str | None:
    client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
    if not client:
        return None

    date_now  = cairo_now().strftime("%Y-%m-%d %H:%M قاهرة")
    conf      = d['confluence']
    ent       = d['entries']
    ctx       = d['hist_ctx']
    rn        = d['round_numbers']
    fib_table = "\n".join([f"   {k:7s} ▸ {v}$" for k, v in d['fib'].items()])

    if is_morning:   header = "🌅 [نشرة الصباح — استراتيجية اليوم الكاملة]"
    elif is_alert:   header = f"🚨 [تنبيه سعري — تحرك حاد {'+' if price_diff>0 else ''}{price_diff:.2f}$]"
    else:            header = "📊 [نشرة التحليل الكمي الاستباقي للذهب]"

    # جدول نقاط التوافق
    score_lines = [f"   {'🟢' if v>0 else ('🔴' if v<0 else '⚪')} {name}"
                   for name, v in conf['scores'].items()]
    score_table = "\n".join(score_lines)

    # السياق التاريخي
    hist_lines = []
    if ctx.get('chg_1d')  is not None: hist_lines.append(f"   آخر 24 ساعة : {ctx['chg_1d']:+.2f}$ ({ctx['pct_1d']:+.2f}%)")
    if ctx.get('chg_7d')  is not None: hist_lines.append(f"   آخر 7 أيام  : {ctx['chg_7d']:+.2f}$ ({ctx['pct_7d']:+.2f}%)")
    if ctx.get('chg_30d') is not None: hist_lines.append(f"   آخر 30 يوم  : {ctx['chg_30d']:+.2f}$ ({ctx['pct_30d']:+.2f}%)")
    if ctx.get('high_52w'): hist_lines.append(f"   قمة 52 أسبوع: {ctx['high_52w']}$ | قاع 52 أسبوع: {ctx['low_52w']}$")
    hist_block = "\n".join(hist_lines)

    # ── بناء توجيه الاتجاه الإلزامي بناءً على الـ Confluence ──
    bias        = conf['bias']
    bias_ar     = {"bull": "صعودي", "bear": "هبوطي", "neutral": "متذبذب"}.get(bias, "متذبذب")
    sl_dir_note = (
        f"⚠️ هذه صفقة {ent['type']} — وقف الخسارة {ent['sl']}$ هو {'أدنى' if bias=='bull' else 'أعلى'} نقطة الدخول {ent['entry']}$ بفارق {ent['risk']}$."
    )

    # ── حد أدنى إلزامي لاحتمالية الاتجاه الغالب ──
    if bias == "bull":
        prob_note = f"الاتجاه الغالب صعودي — احتمالية سيناريو الصعود لا تقل بأي حال عن 50%."
    elif bias == "bear":
        prob_note = f"الاتجاه الغالب هبوطي — احتمالية سيناريو الهبوط لا تقل بأي حال عن 50%."
    else:
        prob_note = "السوق متذبذب — احتمالية التذبذب لا تقل عن 40%."

    system_prompt = f"""أنت محلل كمي أول في صندوق تحوط عالمي متخصص بالذهب — خبرة 20 عاماً.

[قواعد صارمة لا تُخالَف]
1. العربية الفصحى البسيطة فقط. لا كلمة إنجليزية واحدة في نص التقرير.
2. حكم السوق المحسوب من 10 مؤشرات هو: {conf['verdict']}
   هذا الحكم نهائي — تحليلك يبدأ منه ولا يناقضه.
3. {prob_note}
4. الأرقام في قسم "الصفقة المقترحة" محسوبة رياضياً وهي نهائية:
   - نقطة الدخول : {ent['entry']}$
   - وقف الخسارة : {ent['sl']}$  ← هو دائماً {'أدنى' if bias=='bull' else 'أعلى'} نقطة الدخول في صفقات {bias_ar}
   - الهدف الأول : {ent['tp1']}$
   - الهدف الثاني: {ent['tp2']}$
   استخدم هذه الأرقام حرفياً في "القرار العملي" — لا تعيد احتسابها ولا تبدّلها.
5. كل سيناريو يحمل احتمالية عددية (مجموعها 100% بالضبط).
6. لا تذكر أي إخلاء مسؤولية أو تحذير قانوني.
7. اختم حرفياً بـ: "القرار العملي:" في جملتين فقط."""

    user_prompt = f"""{header}
🕐 {date_now}

━━━━━━━━━━━━━━━━━━━━━━━━
🎯 حكم السوق: {conf['verdict']}
━━━━━━━━━━━━━━━━━━━━━━━━
{score_table}
المجموع: {conf['total']:+d} من ±{conf['n']} | ({conf['bullish']} شراء | {conf['bearish']} بيع | {conf['neutral']} محايد)

━━━━━━━━━━━━━━━━━━━━━━━━
🕐 توافق الإطارات الزمنية
━━━━━━━━━━━━━━━━━━━━━━━━
{d['tf_label']}
   📅 أسبوعي : {d['tf_weekly']['bias']} | RSI={d['tf_weekly']['rsi']} | EMA={d['tf_weekly']['ema_align']}
   📆 يومي   : {d['tf_daily']['bias']}  | RSI={d['tf_daily']['rsi']}  | EMA={d['tf_daily']['ema_align']}
   ⏱️ ساعي   : {d['tf_hourly'].get('bias','غير متاح')} | RSI={d['tf_hourly'].get('rsi','-')} | EMA={d['tf_hourly'].get('ema_align','غير متاح')}

━━━━━━━━━━━━━━━━━━━━━━━━
📈 حركة السعر التاريخية
━━━━━━━━━━━━━━━━━━━━━━━━
{hist_block}

━━━━━━━━━━━━━━━━━━━━━━━━
📡 بيانات السوق اللحظية
━━━━━━━━━━━━━━━━━━━━━━━━
🥇 ذهب  : {d['gold']:.2f}$
🥈 فضة  : {f"{d['silver']:.3f}$" if d['silver'] else 'غير متاح'} | نسبة ذهب/فضة: {f"{d['gs_ratio']}:1" if d['gs_ratio'] else '-'}
🛢️ نفط   : {f"{d['oil']:.2f}$" if d['oil'] else 'غير متاح'}
💵 DXY  : {d['dxy']:.2f} ({d['dxy_bias']})
📈 سندات 10Y: {d['tnx']:.2f}% ({d['bond_bias']})
😨 VIX  : {f"{d['vix']:.2f} — {d['vix_label']}" if d['vix'] else 'غير متاح'}
📊 S&P  : {f"{d['sp500']:.0f}" if d['sp500'] else 'غير متاح'}
💡 العائد الحقيقي: {d['real_yield_signal']}
⚖️ الضغط الكلي: {d['gold_pressure']}

━━━━━━━━━━━━━━━━━━━━━━━━
🧮 المؤشرات الفنية (10 مؤشرات)
━━━━━━━━━━━━━━━━━━━━━━━━
RSI (14)       : {d['rsi']} — {d['rsi_label']}
Stoch RSI      : K={d['stoch_k']} | D={d['stoch_d']}
MACD           : Hist={d['macd_hist']} — {d['macd_label']}
بولينجر        : سقف {d['bb_upper']}$ | وسط {d['bb_mid']}$ | قاع {d['bb_lower']}$ ({d['bb_label']})
EMA 20/50/200  : {d['ema20']} / {d['ema50']} / {d['ema200']} — {d['ema_label']}
ADX (14)       : {d['adx']} ({d['adx_label']}) | DI+={d['di_plus']} | DI-={d['di_minus']}
CCI (20)       : {d['cci']} — {d['cci_label']}
Williams %R    : {d['williams_r']} — {d['wr_label']}
OBV            : {d['obv_trend']}
حجم التداول   : {d['rel_vol_label']}
نظام التقلب    : {d['atr_regime']}
ATR (14)       : {d['atr']}$

━━━━━━━━━━━━━━━━━━━━━━━━
🔢 المستويات الرئيسية
━━━━━━━━━━━━━━━━━━━━━━━━
🟣 المستوى النفسي فوق السعر : {rn['nearest_resistance']}$ (بعيد {rn['dist_to_resistance']}$)
🟣 المستوى النفسي تحت السعر : {rn['nearest_support']}$ (بعيد {rn['dist_to_support']}$)
📍 Swing High (20 شمعة)     : {d['swing_high']}$
📍 Swing Low  (20 شمعة)     : {d['swing_low']}$
🔴 R3/R2/R1: {d['r3']}$ / {d['r2']}$ / {d['r1']}$
⚪ Pivot: {d['pivot']}$
🟢 S1/S2/S3: {d['s1']}$ / {d['s2']}$ / {d['s3']}$

━━━━━━━━━━━━━━━━━━━━━━━━
📐 فيبوناتشي (30 يوم)
━━━━━━━━━━━━━━━━━━━━━━━━
{fib_table}

━━━━━━━━━━━━━━━━━━━━━━━━
🎯 الصفقة المقترحة ({ent['type']})
━━━━━━━━━━━━━━━━━━━━━━━━
📍 دخول    : {ent['entry']}$
🛑 وقف خسارة: {ent['sl']}$   (تحت/فوق أقوى مستوى حقيقي)
🎯 هدف 1   : {ent['tp1']}$   (R:R = {ent['rr1']})
🏆 هدف 2   : {ent['tp2']}$   (R:R = {ent['rr2']})
📊 مخاطرة  : {ent['risk']}$ لكل أونصة

━━━━━━━━━━━━━━━━━━━━━━━━
📝 اكتب التقرير الآن — 4 خطوات متسلسلة
━━━━━━━━━━━━━━━━━━━━━━━━

**خلاصة التحليل:** [جملة واحدة — تبدأ حتماً بالاتجاه {bias_ar} بناءً على حكم السوق أعلاه]

**الخطوة 1 — قراءة الإطارات الزمنية**
حلل توافق الأسبوعي واليومي والساعي. استنتج المعنى في جملتين: هل الترند واضح أم متعارض؟ وما دلالته على الحركة القادمة؟

**الخطوة 2 — فك شفرة أبرز 3 مؤشرات**
اختر أقوى 3 مؤشرات تدعم الحكم {bias_ar}. اشرح كلاً منها بمثال حياتي بسيط لا يتجاوز جملتين.
ثم: هل حجم التداول يؤكد الحركة أم يُشكك فيها؟ وهل التقلب ينذر باختراق؟

**الخطوة 3 — السيناريوهات (المجموع 100% حتماً)**
[الاتجاه {bias_ar} هو السيناريو الأعلى احتمالاً — التزم بهذا]
📈 سيناريو الصعود (X%): الشرط + الهدف + العلامة التأكيدية
📉 سيناريو الهبوط (Y%): الشرط + الهدف + علامة التحذير
⚡ سيناريو التذبذب (Z%): النطاق + شرط الانكسار

**القرار العملي:** [جملتان فقط — تستخدم هذه الأرقام حرفياً: دخول {ent['entry']}$ | وقف {ent['sl']}$ | هدف {ent['tp1']}$ / {ent['tp2']}$]
"""

    for model_name in GROQ_MODELS:
        try:
            log.info(f"🤖 جاري الاتصال بـ Groq — {model_name}")
            resp = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                model=model_name,
                temperature=0.08,
                max_tokens=2400,
            )
            log.info(f"✅ نجح الاتصال: {model_name}")
            return resp.choices[0].message.content
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate_limit" in err_str.lower():
                log.warning(f"⚠️ [{model_name}] 429 — الانتقال للتالي...")
                time.sleep(2)
                continue
            log.error(f"❌ [{model_name}] {e}")
            break
    log.error("❌ جميع الموديلات فشلت.")
    return None


# ══════════════════════════════════════════════
#  8. إرسال تيليجرام
# ══════════════════════════════════════════════
CHUNK_SIZE = 3800


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
    try:
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.start(bot_token=TELEGRAM_BOT_TOKEN)
        await client.send_message(TELEGRAM_CHAT_ID, text)
        await client.disconnect()
        return True
    except Exception as e:
        log.warning(f"⚠️ [Telethon] {e}")
        return False


def _http_send(text: str) -> bool:
    url     = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": str(TELEGRAM_CHAT_ID), "text": text}
    for attempt in range(3):
        try:
            r = requests.post(url, json=payload, headers={"Connection": "close"}, timeout=(5, 20))
            r.raise_for_status()
            return True
        except Exception as e:
            log.warning(f"⚠️ [HTTP] {attempt+1}/3 — {e}")
            time.sleep(2 ** attempt)
    return False


def _send_single(text: str) -> bool:
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
                log.info("✅ [Telethon new loop] تم الإرسال.")
                return True
        except Exception as e:
            log.warning(f"⚠️ [Telethon loop] {e}")
    except Exception as e:
        log.warning(f"⚠️ [Telethon] {e}")
    return _http_send(text)


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
    log.info("🚀 Goldbot Pro+ بدأ — تحليل كمي متعدد الإطارات + Chain-of-Thought...")

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
                    f"📊 ذهب: {current_gold:.2f}$ | {conf['verdict']}\n"
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
                    "تعذّر جلب البيانات أو استنفدت الموديلات حدودها.\n"
                    "سيتم إعادة المحاولة تلقائياً."
                )
                all_models_notified = True

        time.sleep(60)
        minutes_counter += 1