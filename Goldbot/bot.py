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
#  1. جلب البيانات
# ══════════════════════════════════════════════
def _fetch_history(symbol: str, period: str = "90d", max_retries: int = 4):
    for attempt in range(max_retries):
        try:
            df = yf.Ticker(symbol).history(period=period)
            if not df.empty:
                return df
            return None
        except Exception as e:
            wait = 2 ** attempt
            log.warning(f"[yfinance] {symbol} محاولة {attempt+1}/{max_retries}: {e} — انتظار {wait}s")
            time.sleep(wait)
    return None


def _last_close(df) -> float | None:
    return float(df['Close'].iloc[-1]) if df is not None and not df.empty else None


# ══════════════════════════════════════════════
#  2. المؤشرات الفنية الكاملة
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
    """Stochastic RSI — أدق من RSI العادي في تحديد نقاط التحول."""
    if len(closes) < rsi_period + stoch_period + k_smooth + d_smooth:
        return 50.0, 50.0
    rsi_series = []
    for i in range(len(closes) - rsi_period):
        rsi_series.append(calc_rsi(closes[i:i + rsi_period + 1]))
    rsi_arr = np.array(rsi_series)
    if len(rsi_arr) < stoch_period:
        return 50.0, 50.0
    stoch_k = []
    for i in range(len(rsi_arr) - stoch_period + 1):
        window = rsi_arr[i:i + stoch_period]
        mn, mx = window.min(), window.max()
        stoch_k.append(100.0 * (rsi_arr[i + stoch_period - 1] - mn) / (mx - mn + 1e-9))
    stoch_k = np.array(stoch_k)
    def sma(arr, n):
        return np.convolve(arr, np.ones(n)/n, mode='valid')
    k_smooth_arr = sma(stoch_k, k_smooth) if len(stoch_k) >= k_smooth else stoch_k
    d_smooth_arr = sma(k_smooth_arr, d_smooth) if len(k_smooth_arr) >= d_smooth else k_smooth_arr
    return round(float(k_smooth_arr[-1]), 2), round(float(d_smooth_arr[-1]), 2)


def calc_macd(closes: np.ndarray, fast=12, slow=26, signal=9):
    def ema(arr, n):
        k = 2 / (n + 1)
        res = [arr[0]]
        for v in arr[1:]:
            res.append(v * k + res[-1] * (1 - k))
        return np.array(res)
    if len(closes) < slow + signal:
        return 0.0, 0.0, 0.0
    macd_line   = ema(closes, fast) - ema(closes, slow)
    signal_line = ema(macd_line, signal)
    histogram   = macd_line - signal_line
    return round(float(macd_line[-1]), 4), round(float(signal_line[-1]), 4), round(float(histogram[-1]), 4)


def calc_bollinger(closes: np.ndarray, period: int = 20, std_dev: float = 2.0):
    if len(closes) < period:
        c = closes[-1]
        return c, c, c
    window = closes[-period:]
    mid, std = np.mean(window), np.std(window)
    return round(float(mid + std_dev * std), 2), round(float(mid), 2), round(float(mid - std_dev * std), 2)


def calc_ema(closes: np.ndarray, period: int) -> float:
    if len(closes) < period:
        return float(closes[-1])
    k = 2 / (period + 1)
    ema_val = closes[0]
    for v in closes[1:]:
        ema_val = v * k + ema_val * (1 - k)
    return round(float(ema_val), 2)


def calc_adx(df, period: int = 14):
    """ADX + DI+ + DI- لقياس قوة واتجاه الترند."""
    if df is None or len(df) < period * 2:
        return 20.0, 50.0, 50.0
    highs  = df['High'].values
    lows   = df['Low'].values
    closes = df['Close'].values
    tr_list, dm_plus, dm_minus = [], [], []
    for i in range(1, len(df)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        up   = highs[i] - highs[i-1]
        down = lows[i-1] - lows[i]
        tr_list.append(tr)
        dm_plus.append(up   if up > down and up > 0 else 0)
        dm_minus.append(down if down > up and down > 0 else 0)
    def wilder_smooth(arr, n):
        res = [sum(arr[:n])]
        for v in arr[n:]:
            res.append(res[-1] - res[-1]/n + v)
        return res
    atr_s  = wilder_smooth(tr_list, period)
    dip_s  = wilder_smooth(dm_plus,  period)
    dim_s  = wilder_smooth(dm_minus, period)
    di_plus  = [100 * dip_s[i] / (atr_s[i] + 1e-9) for i in range(len(atr_s))]
    di_minus = [100 * dim_s[i] / (atr_s[i] + 1e-9) for i in range(len(atr_s))]
    dx = [100 * abs(di_plus[i] - di_minus[i]) / (di_plus[i] + di_minus[i] + 1e-9) for i in range(len(atr_s))]
    adx_s = wilder_smooth(dx, period)
    return round(float(adx_s[-1]), 2), round(float(di_plus[-1]), 2), round(float(di_minus[-1]), 2)


def calc_cci(df, period: int = 20) -> float:
    """Commodity Channel Index — مفيد جداً للذهب والسلع."""
    if df is None or len(df) < period:
        return 0.0
    tp = (df['High'].values + df['Low'].values + df['Close'].values) / 3
    tp_window = tp[-period:]
    mean_tp   = np.mean(tp_window)
    mean_dev  = np.mean(np.abs(tp_window - mean_tp))
    cci = (tp[-1] - mean_tp) / (0.015 * mean_dev + 1e-9)
    return round(float(cci), 2)


def calc_williams_r(df, period: int = 14) -> float:
    """Williams %R — مؤكد ممتاز للتشبع الشرائي والبيعي."""
    if df is None or len(df) < period:
        return -50.0
    highs  = df['High'].values[-period:]
    lows   = df['Low'].values[-period:]
    close  = df['Close'].values[-1]
    hh, ll = np.max(highs), np.min(lows)
    wr = -100 * (hh - close) / (hh - ll + 1e-9)
    return round(float(wr), 2)


def calc_fibonacci(closes: np.ndarray, lookback: int = 30):
    if len(closes) < lookback:
        lookback = len(closes)
    window = closes[-lookback:]
    high, low = float(np.max(window)), float(np.min(window))
    diff = high - low
    return {
        "0.0%"  : round(high, 2),
        "23.6%" : round(high - 0.236 * diff, 2),
        "38.2%" : round(high - 0.382 * diff, 2),
        "50.0%" : round(high - 0.500 * diff, 2),
        "61.8%" : round(high - 0.618 * diff, 2),
        "78.6%" : round(high - 0.786 * diff, 2),
        "100%"  : round(low, 2),
    }


def calc_atr(df, period: int = 14) -> float:
    if df is None or len(df) < period + 1:
        return 0.0
    h, l, c = df['High'].values, df['Low'].values, df['Close'].values
    tr_list = [max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1])) for i in range(1, len(df))]
    return round(float(np.mean(tr_list[-period:])), 2)


def find_swing_levels(df, lookback: int = 20):
    """
    إيجاد أقرب Swing High و Swing Low حقيقيين من البيانات الفعلية.
    أدق بكثير من Pivot Points الكلاسيكية.
    """
    if df is None or len(df) < lookback:
        return None, None
    highs  = df['High'].values[-lookback:]
    lows   = df['Low'].values[-lookback:]
    swing_high = float(np.max(highs))
    swing_low  = float(np.min(lows))
    return round(swing_high, 2), round(swing_low, 2)


# ══════════════════════════════════════════════
#  3. نظام نقاط التوافق (Confluence Score)
# ══════════════════════════════════════════════
def calc_confluence(d: dict) -> dict:
    """
    كل مؤشر يعطي: +1 (شراء) أو -1 (بيع) أو 0 (محايد).
    المجموع يحدد الحكم الكلي للسوق.
    """
    gold = d['gold']
    scores = {}

    # RSI
    if d['rsi'] < 40:
        scores['RSI'] = +1
    elif d['rsi'] > 60:
        scores['RSI'] = -1
    else:
        scores['RSI'] = 0

    # Stochastic RSI
    stoch_k = d['stoch_k']
    if stoch_k < 20:
        scores['Stoch RSI'] = +1
    elif stoch_k > 80:
        scores['Stoch RSI'] = -1
    else:
        scores['Stoch RSI'] = 0

    # MACD
    scores['MACD'] = +1 if d['macd_hist'] > 0 else (-1 if d['macd_hist'] < 0 else 0)

    # EMA Alignment
    ema20, ema50, ema200 = d['ema20'], d['ema50'], d['ema200']
    if ema20 > ema50 > ema200:
        scores['EMA'] = +1
    elif ema20 < ema50 < ema200:
        scores['EMA'] = -1
    else:
        scores['EMA'] = 0

    # Bollinger Bands
    if gold < d['bb_lower'] * 1.003:
        scores['Bollinger'] = +1
    elif gold > d['bb_upper'] * 0.997:
        scores['Bollinger'] = -1
    else:
        scores['Bollinger'] = 0

    # ADX (فقط لو الترند قوي)
    adx, di_plus, di_minus = d['adx'], d['di_plus'], d['di_minus']
    if adx > 25:
        scores['ADX'] = +1 if di_plus > di_minus else -1
    else:
        scores['ADX'] = 0  # سوق تذبذبي — لا حكم

    # CCI
    cci = d['cci']
    if cci < -100:
        scores['CCI'] = +1
    elif cci > 100:
        scores['CCI'] = -1
    else:
        scores['CCI'] = 0

    # Williams %R
    wr = d['williams_r']
    if wr < -80:
        scores['Williams %R'] = +1
    elif wr > -20:
        scores['Williams %R'] = -1
    else:
        scores['Williams %R'] = 0

    total = sum(scores.values())
    bullish = sum(1 for v in scores.values() if v > 0)
    bearish = sum(1 for v in scores.values() if v < 0)
    neutral = sum(1 for v in scores.values() if v == 0)
    n       = len(scores)

    if total >= 4:
        verdict = f"🟢 صعودي قوي ({bullish}/{n} مؤشرات تدعم الشراء)"
        bias    = "bull"
    elif total >= 2:
        verdict = f"🟡 صعودي معتدل ({bullish}/{n} مؤشرات تدعم الشراء)"
        bias    = "bull"
    elif total <= -4:
        verdict = f"🔴 هبوطي قوي ({bearish}/{n} مؤشرات تدعم البيع)"
        bias    = "bear"
    elif total <= -2:
        verdict = f"🟠 هبوطي معتدل ({bearish}/{n} مؤشرات تدعم البيع)"
        bias    = "bear"
    else:
        verdict = f"⚪ متذبذب / غير محدد ({neutral}/{n} مؤشرات محايدة)"
        bias    = "neutral"

    return {
        "scores"  : scores,
        "total"   : total,
        "bullish" : bullish,
        "bearish" : bearish,
        "neutral" : neutral,
        "n"       : n,
        "verdict" : verdict,
        "bias"    : bias,
    }


# ══════════════════════════════════════════════
#  4. حساب نقاط الدخول الدقيقة
# ══════════════════════════════════════════════
def calc_smart_entries(d: dict, bias: str) -> dict:
    """
    نقاط دخول ذكية مبنية على:
    - أقرب Swing Low/High فعلي (ليس Pivot مجرد حساب)
    - نسبة R:R مضمونة لا تقل عن 1:1.5
    - وقف الخسارة تحت/فوق أقوى مستوى حقيقي
    """
    gold       = d['gold']
    atr        = d['atr']
    swing_high = d['swing_high']
    swing_low  = d['swing_low']
    s1, r1     = d['s1'], d['r1']
    s2, r2     = d['s2'], d['r2']

    # نستخدم أقرب دعم/مقاومة حقيقي (Swing) مع Pivot كتأكيد
    nearest_support    = max(swing_low,  s1)  # الأعلى بين الاثنين = الأقرب للسعر
    nearest_resistance = min(swing_high, r1)  # الأدنى بين الاثنين = الأقرب للسعر

    if bias == "bull":
        # دخول شراء: عند أول دعم حقيقي تحت السعر
        entry = round(nearest_support, 2)
        # وقف الخسارة: تحت أدنى Swing Low + هامش نصف ATR
        sl    = round(min(swing_low, s2) - 0.5 * atr, 2)
        risk  = round(entry - sl, 2)
        tp1   = round(entry + 1.5 * risk, 2)
        tp2   = round(entry + 2.5 * risk, 2)
        return {"type": "شراء", "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2,
                "risk": risk, "rr1": "1:1.5", "rr2": "1:2.5"}

    elif bias == "bear":
        # دخول بيع: عند أول مقاومة حقيقية فوق السعر
        entry = round(nearest_resistance, 2)
        sl    = round(max(swing_high, r2) + 0.5 * atr, 2)
        risk  = round(sl - entry, 2)
        tp1   = round(entry - 1.5 * risk, 2)
        tp2   = round(entry - 2.5 * risk, 2)
        return {"type": "بيع", "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2,
                "risk": risk, "rr1": "1:1.5", "rr2": "1:2.5"}

    else:
        # سوق تذبذبي — نعطي كلا الاتجاهين مع تحذير
        return {"type": "تذبذب — لا صفقة مفضلة",
                "entry": gold, "sl": round(s2, 2), "tp1": round(r1, 2), "tp2": round(r2, 2),
                "risk": round(atr, 2), "rr1": "غير مؤكد", "rr2": "غير مؤكد"}


# ══════════════════════════════════════════════
#  5. جلب كل بيانات السوق دفعة واحدة
# ══════════════════════════════════════════════
def get_full_market_data():
    symbols = {"gold": "GC=F", "silver": "SI=F", "oil": "CL=F",
               "dxy": "DX-Y.NYB", "tnx": "^TNX", "vix": "^VIX", "sp500": "^GSPC"}
    dfs = {}
    for key, sym in symbols.items():
        dfs[key] = _fetch_history(sym, period="90d")
        time.sleep(0.7)

    gold_df = dfs.get("gold")
    if gold_df is None or gold_df.empty:
        return None

    closes = gold_df['Close'].values
    gold   = _last_close(dfs["gold"])
    silver = _last_close(dfs["silver"])
    oil    = _last_close(dfs["oil"])
    dxy    = _last_close(dfs["dxy"])
    tnx    = _last_close(dfs["tnx"])
    vix    = _last_close(dfs["vix"])
    sp500  = _last_close(dfs["sp500"])

    if not all([gold, dxy, tnx]):
        return None

    # ── المؤشرات الفنية ──
    rsi                        = calc_rsi(closes)
    stoch_k, stoch_d           = calc_stoch_rsi(closes)
    macd, macd_sig, macd_hist  = calc_macd(closes)
    bb_upper, bb_mid, bb_lower = calc_bollinger(closes)
    ema20  = calc_ema(closes, 20)
    ema50  = calc_ema(closes, 50)
    ema200 = calc_ema(closes, 200)
    adx, di_plus, di_minus     = calc_adx(gold_df)
    cci                        = calc_cci(gold_df)
    williams_r                 = calc_williams_r(gold_df)
    fib                        = calc_fibonacci(closes)
    atr                        = calc_atr(gold_df)
    swing_high, swing_low      = find_swing_levels(gold_df, lookback=20)

    # ── Pivot Points ──
    ph, pl, pc = float(gold_df['High'].iloc[-2]), float(gold_df['Low'].iloc[-2]), float(gold_df['Close'].iloc[-2])
    pivot = round((ph + pl + pc) / 3, 2)
    r1    = round(2 * pivot - pl, 2)
    r2    = round(pivot + (ph - pl), 2)
    r3    = round(ph + 2 * (pivot - pl), 2)
    s1    = round(2 * pivot - ph, 2)
    s2    = round(pivot - (ph - pl), 2)
    s3    = round(pl - 2 * (ph - pivot), 2)

    # ── تسميات نصية ──
    rsi_label  = "تشبع شراء 🔴" if rsi > 70 else ("تشبع بيع 🟢" if rsi < 30 else "محايد ⚪")
    macd_label = "زخم صعودي 🟢" if macd_hist > 0 else "زخم هبوطي 🔴"
    vix_label  = "خوف شديد 🟢" if (vix and vix > 25) else ("توتر ⚠️" if (vix and vix > 18) else "هدوء 🔴")
    bb_label   = "قريب من السقف" if gold > bb_upper * 0.997 else ("قريب من القاع" if gold < bb_lower * 1.003 else "داخل النطاق")
    ema_label  = "🟢 صعودي" if ema20 > ema50 > ema200 else ("🔴 هبوطي" if ema20 < ema50 < ema200 else "⚪ متقاطع")
    adx_label  = "ترند قوي" if adx > 25 else "تذبذب"
    cci_label  = "تشبع بيع 🟢" if cci < -100 else ("تشبع شراء 🔴" if cci > 100 else "محايد ⚪")
    wr_label   = "تشبع بيع 🟢" if williams_r < -80 else ("تشبع شراء 🔴" if williams_r > -20 else "محايد ⚪")
    gs_ratio   = round(gold / silver, 1) if silver else None
    dxy_bias   = "قوي" if dxy > 104 else ("محايد" if dxy > 101 else "ضعيف")
    bond_bias  = "مرتفعة" if tnx > 4.3 else ("معتدلة" if tnx > 3.8 else "منخفضة")
    gold_pressure = "ضغط هبوطي" if (dxy > 104 or tnx > 4.5) else "زخم صعودي"

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
        fib=fib, atr=atr,
        swing_high=swing_high, swing_low=swing_low,
        pivot=pivot, r1=r1, r2=r2, r3=r3, s1=s1, s2=s2, s3=s3,
        gs_ratio=gs_ratio, dxy_bias=dxy_bias, bond_bias=bond_bias,
        gold_pressure=gold_pressure,
    )

    # ── نظام التوافق ──
    confluence = calc_confluence(d)
    d['confluence'] = confluence

    # ── نقاط الدخول الذكية ──
    entries = calc_smart_entries(d, confluence['bias'])
    d['entries'] = entries

    return d


# ══════════════════════════════════════════════
#  6. توليد التقرير بالذكاء الاصطناعي
# ══════════════════════════════════════════════
def generate_report(d: dict, is_alert: bool = False, price_diff: float = 0.0, is_morning: bool = False) -> str | None:
    client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
    if not client:
        return None

    date_now   = cairo_now().strftime("%Y-%m-%d %H:%M قاهرة")
    conf       = d['confluence']
    ent        = d['entries']
    fib_table  = "\n".join([f"   {k:7s} ▸ {v}$" for k, v in d['fib'].items()])

    if is_morning:
        header = "🌅 [نشرة الصباح — استراتيجية جلسة اليوم الكاملة]"
    elif is_alert:
        header = f"🚨 [تنبيه سعري — حركة حادة {'+' if price_diff > 0 else ''}{price_diff:.2f}$ مرصودة الآن]"
    else:
        header = "📊 [نشرة التحليل الكمي الاستباقي للذهب]"

    # جدول نقاط التوافق
    score_lines = []
    for name, val in conf['scores'].items():
        icon = "🟢" if val > 0 else ("🔴" if val < 0 else "⚪")
        score_lines.append(f"   {icon} {name}")
    score_table = "\n".join(score_lines)

    system_prompt = """أنت محلل كمي كبير في صندوق تحوط عالمي متخصص في الذهب.
أسلوبك: حاسم، دقيق، لا مجال للتردد.
قواعد لا تُكسر:
- العربية الفصحى البسيطة فقط. لا إنجليزية في نص التقرير.
- ابنِ تحليلك بالكامل على "حكم السوق" المعطى لك. هو نتيجة 8 مؤشرات محسوبة فعلياً.
- أعطِ احتمالية عددية واضحة لكل سيناريو (يجب أن يكون مجموعها 100%).
- لا تذكر أي إخلاء مسؤولية أو تحذير قانوني في أي جزء من التقرير.
- كل تقرير ينتهي بجملة التوصية العملية مباشرة — بلا مقدمات."""

    user_prompt = f"""{header}
🕐 {date_now}

━━━━━━━━━━━━━━━━━━━━━━━━
🎯 حكم السوق الآن — {conf['verdict']}
━━━━━━━━━━━━━━━━━━━━━━━━
{score_table}

النتيجة الإجمالية: {conf['total']:+d} من أصل ±{conf['n']}
({conf['bullish']} شراء | {conf['bearish']} بيع | {conf['neutral']} محايد)

━━━━━━━━━━━━━━━━━━━━━━━━
📡 بيانات السوق اللحظية
━━━━━━━━━━━━━━━━━━━━━━━━
🥇 الذهب (XAU/USD)   : {d['gold']:.2f}$
🥈 الفضة (XAG/USD)   : {f"{d['silver']:.3f}$" if d['silver'] else 'غير متاح'}
🛢️ النفط (CL)         : {f"{d['oil']:.2f}$" if d['oil'] else 'غير متاح'}
💵 الدولار (DXY)      : {d['dxy']:.2f} — {d['dxy_bias']}
📈 سندات الخزانة 10Y  : {d['tnx']:.2f}% — {d['bond_bias']}
😨 مؤشر الخوف (VIX)  : {f"{d['vix']:.2f} — {d['vix_label']}" if d['vix'] else 'غير متاح'}
📊 S&P 500             : {f"{d['sp500']:.0f}" if d['sp500'] else 'غير متاح'}
🔄 نسبة ذهب/فضة       : {f"{d['gs_ratio']}:1" if d['gs_ratio'] else 'غير متاح'}
⚖️ الضغط الكلي        : {d['gold_pressure']}

━━━━━━━━━━━━━━━━━━━━━━━━
🧮 المؤشرات الفنية الكاملة (8 مؤشرات)
━━━━━━━━━━━━━━━━━━━━━━━━
📉 RSI (14)          : {d['rsi']} — {d['rsi_label']}
🎯 Stoch RSI         : K={d['stoch_k']} | D={d['stoch_d']}
📊 MACD              : {d['macd']} | إشارة: {d['macd_sig']} | Hist: {d['macd_hist']} — {d['macd_label']}
📐 بولينجر           : سقف {d['bb_upper']}$ | وسط {d['bb_mid']}$ | قاع {d['bb_lower']}$ ({d['bb_label']})
📈 EMA 20/50/200     : {d['ema20']} / {d['ema50']} / {d['ema200']} — {d['ema_label']}
💪 ADX (14)          : {d['adx']} ({d['adx_label']}) | DI+: {d['di_plus']} | DI-: {d['di_minus']}
🏭 CCI (20)          : {d['cci']} — {d['cci_label']}
🌡️ Williams %R       : {d['williams_r']} — {d['wr_label']}
📏 ATR (14)          : {d['atr']}$ — متوسط التقلب اليومي

━━━━━━━━━━━━━━━━━━━━━━━━
🎯 نقاط المحاور (Pivot Points)
━━━━━━━━━━━━━━━━━━━━━━━━
🔴 R3: {d['r3']}$ | 🟠 R2: {d['r2']}$ | 🟡 R1: {d['r1']}$
⚪ محور: {d['pivot']}$
🟢 S1: {d['s1']}$ | 🔵 S2: {d['s2']}$ | 🟣 S3: {d['s3']}$

📍 Swing High (20 شمعة): {d['swing_high']}$
📍 Swing Low  (20 شمعة): {d['swing_low']}$

━━━━━━━━━━━━━━━━━━━━━━━━
📐 فيبوناتشي (آخر 30 يوم)
━━━━━━━━━━━━━━━━━━━━━━━━
{fib_table}

━━━━━━━━━━━━━━━━━━━━━━━━
🎯 صفقة {ent['type']} المقترحة (محسوبة بدقة)
━━━━━━━━━━━━━━━━━━━━━━━━
📍 نقطة الدخول  : {ent['entry']}$
🛑 وقف الخسارة  : {ent['sl']}$  ← تحت/فوق أقوى مستوى فعلي
🎯 الهدف الأول  : {ent['tp1']}$  (نسبة المخاطرة {ent['rr1']})
🏆 الهدف الثاني : {ent['tp2']}$  (نسبة المخاطرة {ent['rr2']})
📊 حجم المخاطرة : {ent['risk']}$ لكل أونصة

━━━━━━━━━━━━━━━━━━━━━━━━
📝 التقرير الكامل — 4 أقسام
━━━━━━━━━━━━━━━━━━━━━━━━

**القسم الأول — قراءة المشهد الكلي**
اشرح المشهد العام (دولار + سندات + VIX + نفط) في فقرة واحدة مركزة. ركز على ما يؤثر على الذهب مباشرة الآن.

**القسم الثاني — تفسير حكم السوق**
اشرح لماذا وصلنا لهذا الحكم ({conf['verdict']}) بناءً على أبرز 3-4 مؤشرات متوافقة. اشرح كل مؤشر بمثال حياتي بسيط جداً.

**القسم الثالث — السيناريوهات بالاحتمالات**
بناءً على حكم السوق والأرقام أعلاه، اكتب 3 سيناريوهات مع احتمالية كل منها (المجموع 100%):
📈 سيناريو الصعود (X%): الشرط + الهدف + ما يجب مراقبته
📉 سيناريو الهبوط (Y%): الشرط + الهدف + علامات التحذير
⚡ سيناريو التذبذب (Z%): النطاق + متى ينكسر

**القسم الرابع — التوصية العملية**
جملتان فقط — مباشرة وعملية. ماذا يفعل المستثمر الآن بناءً على كل ما سبق؟
"""

    for model_name in GROQ_MODELS:
        try:
            log.info(f"🤖 جاري الاتصال بـ Groq — الموديل: {model_name}")
            resp = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                model=model_name,
                temperature=0.10,
                max_tokens=2200,
            )
            log.info(f"✅ نجح الاتصال مع الموديل: {model_name}")
            return resp.choices[0].message.content
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate_limit" in err_str.lower():
                log.warning(f"⚠️ [{model_name}] وصل للحد الأقصى — الانتقال للتالي...")
                time.sleep(2)
                continue
            else:
                log.error(f"❌ [{model_name}] خطأ: {e}")
                break
    log.error("❌ جميع الموديلات فشلت.")
    return None


# ══════════════════════════════════════════════
#  7. إرسال تيليجرام — Telethon أولاً ثم HTTP
# ══════════════════════════════════════════════
CHUNK_SIZE = 3800


def _split_message(text: str) -> list:
    if len(text) <= CHUNK_SIZE:
        return [text]
    chunks, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > CHUNK_SIZE:
            if current:
                chunks.append(current.strip())
            current = line
        else:
            current = (current + "\n" + line) if current else line
    if current:
        chunks.append(current.strip())
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
    headers = {"Connection": "close"}
    for attempt in range(3):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=(5, 20))
            r.raise_for_status()
            return True
        except Exception as e:
            log.warning(f"⚠️ [HTTP] محاولة {attempt+1}/3 — {e}")
            time.sleep(2 ** attempt)
    return False


def _send_single(text: str) -> bool:
    try:
        ok = asyncio.run(_telethon_send(text))
        if ok:
            log.info("✅ [Telethon MTProto] تم الإرسال بنجاح.")
            return True
    except RuntimeError:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            ok = loop.run_until_complete(_telethon_send(text))
            loop.close()
            if ok:
                log.info("✅ [Telethon new loop] تم الإرسال بنجاح.")
                return True
        except Exception as e:
            log.warning(f"⚠️ [Telethon loop] {e}")
    except Exception as e:
        log.warning(f"⚠️ [Telethon] {e}")
    log.info("🔄 جاري المحاولة عبر HTTP API...")
    return _http_send(text)


def send_to_telegram(message: str) -> bool:
    if not message:
        return False
    chunks = _split_message(message)
    log.info(f"📤 إرسال في {len(chunks)} جزء...")
    all_ok = True
    for i, chunk in enumerate(chunks, 1):
        prefix = f"[{i}/{len(chunks)}] " if len(chunks) > 1 else ""
        ok = _send_single(prefix + chunk)
        log.info(f"✅ الجزء {i}/{len(chunks)} وصل." if ok else f"❌ فشل الجزء {i}/{len(chunks)}.")
        all_ok = all_ok and ok
        if i < len(chunks):
            time.sleep(1.5)
    return all_ok


# ══════════════════════════════════════════════
#  8. الحلقة الرئيسية — متكاملة ومحكمة
# ══════════════════════════════════════════════
def run_bot():
    log.info("🚀 Goldbot Pro بدأ العمل — نظام التحليل الكمي المتكامل (8 مؤشرات + Confluence)...")

    last_gold_price      = None
    minutes_counter      = 0
    morning_sent_today   = False
    closing_sent_today   = False
    heartbeat_sent_today = False
    all_models_notified  = False
    last_report_date     = None
    consec_failures      = 0
    day_names = ["اثنين", "ثلاثاء", "أربعاء", "خميس", "جمعة", "سبت", "أحد"]

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
                if report:
                    send_to_telegram(report)
                last_gold_price  = current_gold
                last_report_date = today
                minutes_counter  = 0

            elif hour_cairo == HEARTBEAT_HOUR and not heartbeat_sent_today:
                send_to_telegram(
                    f"💚 [Goldbot Heartbeat] البوت يعمل بشكل طبيعي ✔️\n"
                    f"📊 ذهب: {current_gold:.2f}$ | {data['confluence']['verdict']}\n"
                    f"🕐 {now_cairo.strftime('%H:%M قاهرة')}"
                )
                heartbeat_sent_today = True
                log.info("💚 Heartbeat تم إرساله.")

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
                    log.info(f"🚨 تحرك حاد {price_diff:+.2f}$ — إرسال تنبيه...")
                    report = generate_report(data, is_alert=True, price_diff=price_diff)
                    if report:
                        send_to_telegram(report)
                        last_gold_price = current_gold
                        minutes_counter = 0

                elif minutes_counter >= ROUTINE_MINUTES:
                    log.info(f"⏰ مرت {ROUTINE_MINUTES} دقيقة — إرسال التقرير الدوري...")
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
                    "تعذّر جلب البيانات أو استنفدت موديلات الذكاء الاصطناعي حدها اليومي.\n"
                    "سيتم إعادة المحاولة تلقائياً."
                )
                all_models_notified = True

        time.sleep(60)
        minutes_counter += 1


# Note: run_bot() is called by the root main.py orchestrator as a background thread.