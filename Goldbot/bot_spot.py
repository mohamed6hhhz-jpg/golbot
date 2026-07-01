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
TELEGRAM_BOT_TOKEN   = "8135586080:AAFS1ZI2XcsPrnjtTvAPlXxlTMrSO_Lu3Qc"
TELEGRAM_BOT_TOKEN_2 = "8718236248:AAGIlK8xTWUvRB_WcYOGN2Qx1kEKZwRqihQ"
TELEGRAM_BOT_TOKEN_3 = "8696806326:AAEDKqSNoHAaMEHD8oqjaLm4oSci_3KOUWA"  # @Dsssoppp78_bot — القوالب الفورية S1-S12

TARGET_CHATS = ["@spotGol"]
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

    # ── سكالبينج (15 دقيقة) ──
    sl_sc = 8.0
    t = dict(entry=round(s_n, 2), sl=round(s_n - sl_sc, 2), risk=sl_sc,
             t1=round(s_n + 15, 2), t2=round(s_n + 28, 2), t3=round(s_n + 45, 2),
             market=market_name, tf='15د', typ='سكالبينج 🏹', dir='buy')
    if bias in ('bull', 'neutral') and _rr(15, sl_sc) >= MIN_RR:
        trades['scalp_buy'] = t
    t = dict(entry=round(r_n, 2), sl=round(r_n + sl_sc, 2), risk=sl_sc,
             t1=round(r_n - 15, 2), t2=round(r_n - 28, 2), t3=round(r_n - 45, 2),
             market=market_name, tf='15د', typ='سكالبينج 🏹', dir='sell')
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
             market=market_name, tf='1ي', typ='يومية 📅', dir='buy')
    if bias in ('bull', 'neutral') and _rr(r_n - buy_entry_d, sl_d) >= MIN_RR:
        trades['daily_buy'] = t
    t = dict(entry=sell_entry_d, sl=round(sell_entry_d + sl_d, 2), risk=sl_d,
             t1=s_n, t2=s_f, t3=round(s_f - atr * 0.3, 2),
             market=market_name, tf='1ي', typ='يومية 📅', dir='sell')
    if bias in ('bear', 'neutral') and _rr(sell_entry_d - s_n, sl_d) >= MIN_RR:
        trades['daily_sell'] = t

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
    # تأكيد: أهداف الشراء فوق الدخول دائماً
    m_buy_t1 = max(r_n, buy_ent_m + atr * 0.3)
    m_buy_t2 = max(round((pm_h + r_n) / 2, 2) if pm_h else r_f, m_buy_t1 + atr * 0.2)
    m_buy_t3 = max(round(pm_h, 2) if pm_h else round(r_f + atr * 0.5, 2), m_buy_t2 + atr * 0.2)
    t = dict(entry=buy_ent_m, sl=round(buy_ent_m - sl_m, 2), risk=sl_m,
             t1=round(m_buy_t1, 2), t2=round(m_buy_t2, 2), t3=round(m_buy_t3, 2),
             market=market_name, tf='1ش', typ='شهرية 🗓️', dir='buy')
    if bias in ('bull', 'neutral') and _rr(r_n - s_f, sl_m) >= MIN_RR:
        trades['monthly_buy'] = t
    # تأكيد: أهداف البيع تحت الدخول دائماً
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
    sl_rev  = round(atr * 0.28, 2)
    if rsi <= 50:
        t = dict(entry=round(gold, 2), sl=round(gold - sl_rev, 2), risk=sl_rev,
                 t1=round(gold + atr*0.4, 2), t2=round(gold + atr*0.8, 2), t3=round(gold + atr*1.5, 2),
                 market=market_name, tf='1-4س', typ='زيرو انعكاس 🔄', dir='buy')
        trades['rev_buy'] = t
    else:
        t = dict(entry=round(gold, 2), sl=round(gold + sl_rev, 2), risk=sl_rev,
                 t1=round(gold - atr*0.4, 2), t2=round(gold - atr*0.8, 2), t3=round(gold - atr*1.5, 2),
                 market=market_name, tf='1-4س', typ='زيرو انعكاس 🔄', dir='sell')
        trades['rev_sell'] = t
    # ── صفقة كل 5 دقائق (5min scalp) ──
    atr_5m = round(atr * (5/1380)**0.5, 2)  # FIX: 1380 min/day for Gold Futures (23h session)
    sl_5m = max(round(atr_5m * 0.8, 2), 3.0)
    sc_15m = d.get('tf_15m', {}).get('score', 0)
    if sc_15m > 0:
        t5m = dict(entry=round(gold, 2), sl=round(gold - sl_5m, 2), risk=sl_5m,
                   t1=round(gold + atr_5m*1.5, 2), t2=round(gold + atr_5m*2.5, 2),
                   t3=round(gold + atr_5m*4.0, 2),
                   market=market_name, tf='5د', typ='سكالبينج 5د ⚡', dir='buy')
        if True: trades['scalp_5m_buy'] = t5m
    else:
        t5m = dict(entry=round(gold, 2), sl=round(gold + sl_5m, 2), risk=sl_5m,
                   t1=round(gold - atr_5m*1.5, 2), t2=round(gold - atr_5m*2.5, 2),
                   t3=round(gold - atr_5m*4.0, 2),
                   market=market_name, tf='5د', typ='سكالبينج 5د ⚡', dir='sell')
        if True: trades['scalp_5m_sell'] = t5m

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

    rs_text = " | ".join([ar_map.get(r, r) for r in reasons[:3]]) if reasons else "بدون إشارات قوية"
    
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

        if gld_pcr is None:
            # Fallback to realistic proxy based on RSI
            try:
                rsi_d = float(ind['rsi_1d']) if ind.get('rsi_1d') else 50.0
                if rsi_d > 60: gld_pcr = round(0.70 + (70 - rsi_d)*0.01, 2)
                elif rsi_d < 40: gld_pcr = round(1.30 - (rsi_d - 30)*0.01, 2)
                else: gld_pcr = 0.95
            except Exception:
                gld_pcr = 0.95
            pcr_source = "Proxy"


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
    fib_line = (f"فيبوناتشي (فوري): 78.6%={fib['78.6%']}$ | 61.8%={fib['61.8%']}$ | "
                f"50.0%={fib['50.0%']}$ | 38.2%={fib['38.2%']}$ | 23.6%={fib['23.6%']}$")
    # نطاق اليوم المتوقع من ATR
    exp_low  = round(gold - d['atr'] * 0.65, 2)
    exp_high = round(gold + d['atr'] * 0.65, 2)
    range_line = f"نطاق اليوم المتوقع (±0.65×ATR): {exp_low}$ ↔ {exp_high}$"

    fixed = f"""👑 📊 التقرير الكمي الشامل للذهب
🕐 {date_now}

━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 السعر الحالي
   سوق الفوري (Spot) : {spot_label}

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
🔢 المستويات (مبنية على الـ {market_suffix})
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
        if t['typ'] in ['\u0644\u0648\u062a \u0639\u0627\u0644\u064a \U0001f4b0', '\u0632\u064a\u0631\u0648 \u0627\u0646\u0639\u0643\u0627\u0633 \U0001f504'] and pct < 90:
            return None
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
         ['scalp_5m_buy','scalp_5m_sell','tight_scalp_buy','tight_scalp_sell']),
        ('\U0001f4c5 \u0635\u0641\u0642\u0627\u062a \u064a\u0648\u0645\u064a\u0629 \u0648\u0623\u0633\u0628\u0648\u0639\u064a\u0629',
         ['daily_buy','daily_sell','weekly_buy','weekly_sell']),
        ('\U0001f30a \u0633\u0648\u064a\u0646\u062c \u0637\u0648\u064a\u0644 \u0648\u0634\u0647\u0631\u064a',
         ['long_swing_buy','long_swing_sell','monthly_buy','monthly_sell','swing_buy','swing_sell']),
        ('\U0001f4b0 \u0635\u0641\u0642\u0627\u062a \u0644\u0648\u062a \u0639\u0627\u0644\u064a (\u0628\u0627\u0644\u0645\u064a\u0644\u064a - \u062c\u0648\u062f\u0629 > 90%)',
         ['high_lot_buy','high_lot_sell']),
        ('\U0001f504 \u0635\u0641\u0642\u0627\u062a \u0632\u064a\u0631\u0648 \u0627\u0646\u0639\u0643\u0627\u0633 (Counter-trend - \u062c\u0648\u062f\u0629 > 90%)',
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
   ⏱️ ساعة   │ إغلاق: {d['tf_forecasts']['1h']['close']}$  │  قمة: {d['tf_forecasts']['1h']['high']}$  │  قاع: {d['tf_forecasts']['1h']['low']}$  │ جودة:{d['tf_forecasts']['1h'].get('quality','—')}%
   ⏰ 4 ساعات│ إغلاق: {d['tf_forecasts']['4h']['close']}$  │  قمة: {d['tf_forecasts']['4h']['high']}$  │  قاع: {d['tf_forecasts']['4h']['low']}$  │ جودة:{d['tf_forecasts']['4h'].get('quality','—')}%
   📅 يوم    │ إغلاق: {d['tf_forecasts']['1d']['close']}$  │  قمة: {d['tf_forecasts']['1d']['high']}$  │  قاع: {d['tf_forecasts']['1d']['low']}$  │ جودة:{d['tf_forecasts']['1d'].get('quality','—')}%
   📆 أسبوع  │ إغلاق: {d['tf_forecasts']['1w']['close']}$  │  قمة: {d['tf_forecasts']['1w']['high']}$  │  قاع: {d['tf_forecasts']['1w']['low']}$  │ جودة:{d['tf_forecasts']['1w'].get('quality','—')}%
   🗓️ شهر    │ إغلاق: {d['tf_forecasts']['1mo']['close']}$ │  قمة: {d['tf_forecasts']['1mo']['high']}$ │  قاع: {d['tf_forecasts']['1mo']['low']}$ │ جودة:{d['tf_forecasts']['1mo'].get('quality','—')}%
   ─────────────────────────
   📖 شرح النطاق والتباين:
   • النطاق اليومي المتوقع ({daily_range}$): هو المسافة بين القمة والقاع المتوقعين لليوم، ويُحسب بدمج متوسط الحركة (ATR) مع قوة الاتجاه (ADX). معناه: الذهب مرشح للتحرك صعوداً وهبوطاً ضمن هذا الهامش اليوم.
   • التباين / الانحراف المعياري ({variance_val}$): يقيس درجة التشتت السعري لآخر 14 يوم. معناه: كلما زاد الرقم، دلّ على سيولة عنيفة واضطراب شديد للذهب، وكلما قل دلّ على تجميع وهدوء.
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
فيبوناتشي (فوري): 78.6%={d['fib']['78.6%']}$ | 61.8%={d['fib']['61.8%']}$ | 50%={d['fib']['50.0%']}$
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


def _build_template_1(d: dict) -> str:
    """بناء القالب الأول (الموجز الكلاسيكي المنفصل)"""
    w_bias = d['tf_weekly'].get('bias', 'متذبذب')
    w_icon = '📈' if 'صاعد' in w_bias else ('📉' if 'هابط' in w_bias else '↔️')
    
    d_bias = d['tf_daily'].get('bias', 'متذبذب')
    d_icon = '📈' if 'صاعد' in d_bias else ('📉' if 'هابط' in d_bias else '↔️')
    
    gold = d['gold']
    vwap = d.get('vwap') or gold
    rsi_1h = d['tf_hourly'].get('rsi', 50) if d.get('tf_hourly') else 50
    score_4h = d['tf_4h'].get('score', 0) if d.get('tf_4h') else 0
    
    context_lines = []
    if gold < vwap:
        context_lines.append("الإغلاق تم أسفل مناطق دعم مكسورة تحولت إلى مقاومات.")
    else:
        context_lines.append("الإغلاق تم أعلى مقاومات مخترقة تحولت إلى دعوم.")
        
    if score_4h < -2 and rsi_1h < 40:
        context_lines.append("يوجد زخم بيعي مسيطر وقناة سعرية هابطة على فريم الساعة.")
    elif score_4h > 2 and rsi_1h > 60:
        context_lines.append("توجد قناة سعرية صاعدة متكونة على فريم الساعة بزخم شرائي قوي.")
    else:
        context_lines.append("السعر يتداول في نطاق عرضي تجميعي على المدى القصير.")
        
    context_text = "\n".join(context_lines)
    
    main_bias = d['confluence']['bias']
    atr = d.get('atr', 20)
    
    if main_bias == 'bear' or main_bias == 'neutral':
        # نفضل البيع
        zone_color = "🔴"
        zone_name = "مستوى البيع"
        # المقاومات
        r1, r2 = d.get('r1', gold+10), d.get('r2', gold+20)
        exact_zone = round(r1, 2)
        t1 = round(d.get('s1', gold-10), 2)
        t2 = round(d.get('s2', gold-20), 2)
        cont_action = "الهبوط لمستويات أقل"
        rev_color = "🟢"
        rev_zone = round(d.get('swing_high') or (r2 + atr), 2)
        rev_dir = "الصعود"
        break_dir = "أعلاه"
    else:
        # الشراء
        zone_color = "🟢"
        zone_name = "مستوى الشراء"
        s1, s2 = d.get('s1', gold-10), d.get('s2', gold-20)
        exact_zone = round(s1, 2)
        t1 = round(d.get('r1', gold+10), 2)
        t2 = round(d.get('r2', gold+20), 2)
        cont_action = "الصعود لمستويات أعلى"
        rev_color = "🔴"
        rev_zone = round(d.get('swing_low') or (s2 - atr), 2)
        rev_dir = "الهبوط"
        break_dir = "أسفله"
    
    # القالب كما طلبه العميل بالحرف
    template = f"""تحليل الذهب 🟡

1W (الأسبوعي)
التحيز الأسبوعي: {w_bias} {w_icon}

1D (اليومي)
التحيز اليومي: {d_bias} {d_icon}

4H - 1H
{context_text}

{zone_color} {zone_name}: {exact_zone}

في حال احترام المستوى، نتوقع استهداف:
{t1}
{t2}

وفي حالة كسر {t2}، سيستمر {cont_action}.

{rev_color} أما إذا لم يحترم السعر مستوى {exact_zone} وتمكن من اختراقه، فسيستهدف {rev_zone}.
وتعتبر نقطة {rev_zone} هي النقطة الذهبية الفاصلة بين الصعود والهبوط، وباختراقها والثبات {break_dir} يمكننا القول إن السعر بدأ يغير اتجاهه ويميل إلى {rev_dir}."""
    
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
                log.warning(f"⚠️ [Telethon Bot (Spot)] فشل الإرسال للجروب {chat}: {inner_e}")
                
        await client.disconnect()
        return True
    except Exception as e:
        log.warning(f"⚠️ [Telethon Bot (Spot)] {e}")
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
    """الإرسال للبوت الثاني عبر Telethon MTProto"""
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


async def _telethon_bot3_send(text: str, chat_id=None) -> bool:
    """MTProto للبوت الثالث @Dsssoppp78_bot — خاص بالقوالب الفورية S1-S12"""
    try:
        client = TelegramClient("goldbot_bot3_session", API_ID, API_HASH)
        await client.start(bot_token=TELEGRAM_BOT_TOKEN_3)
        targets = [chat_id] if chat_id else TARGET_CHATS
        for chat in targets:
            try:
                await client.send_message(chat, text)
            except Exception as inner_e:
                log.warning(f"[Bot3 Telethon] فشل الارسال للجروب {chat}: {inner_e}")
        await client.disconnect()
        return True
    except Exception as e:
        log.warning(f"[Bot3 Telethon] {e}")
        return False


def _send_single_bot3(text: str, chat_id=None) -> bool:
    """الارسال للبوت الثالث @Dsssoppp78_bot عبر Telethon MTProto"""
    try:
        ok = asyncio.run(_telethon_bot3_send(text, chat_id))
        if ok:
            log.info("[Telethon Bot3] تم الارسال بنجاح.")
            return True
    except RuntimeError:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            ok = loop.run_until_complete(_telethon_bot3_send(text, chat_id))
            loop.close()
            if ok:
                log.info("[Telethon Bot3] تم الارسال بنجاح.")
                return True
        except Exception as e:
            log.warning(f"[Telethon Bot3 loop] {e}")
    except Exception as e:
        log.warning(f"[Telethon Bot3] {e}")
    log.error("[Bot3] فشل الارسال عبر Telethon.")
    return False



def _send_single(text: str, is_public_allowed: bool = True, chat_id=None) -> bool:
    """إرسال عبر MTProto (Bot) أولاً للهروب من مشاكل Timeout، والـ HTTP كاحتياطي."""
    try:
        ok = asyncio.run(_telethon_bot_send(text, is_public_allowed, chat_id))
        if ok:
            log.info("✅ [Telethon Bot (Spot)] تم الإرسال بنجاح.")
            return True
    except RuntimeError:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            ok = loop.run_until_complete(_telethon_bot_send(text, is_public_allowed, chat_id))
            loop.close()
            if ok:
                log.info("✅ [Telethon Bot (Spot)] تم الإرسال بنجاح.")
                return True
        except Exception as e:
            log.warning(f"⚠️ [Telethon Bot (Spot) loop] {e}")
    except Exception as e:
        log.warning(f"⚠️ [Telethon Bot (Spot)] {e}")

    log.warning("⚠️ [Telethon Bot (Spot)] فشل — جاري المحاولة عبر HTTP...")
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
    """بناء القالب الثاني (مؤشر صحة الاقتصاد الأمريكي) عبر الذكاء الاصطناعي"""
    client = Groq(api_key=random.choice(GROQ_KEYS)) if GROQ_KEYS else None
    if not client:
        return "⚠️ لا يمكن توليد تقرير الاقتصاد الكلي لعدم توفر مفتاح Groq."

    dxy        = d.get('dxy', 0)
    dxy_pct    = d.get('dxy_pct', 0.0)
    tnx        = d.get('tnx', 0)
    twy        = d.get('twy', 0)
    vix        = d.get('vix', 0)
    vix_pct    = d.get('vix_pct', 0.0)
    sp500_pct  = d.get('sp500_pct', 0.0)
    nasdaq_pct = d.get('nasdaq_pct', 0.0)
    inflation  = d.get('cpi_yoy', 2.5)
    interest_rate = d.get('interest_rate', 5.5)
    real_yield = d.get('real_yield', round(interest_rate - inflation, 2))
    yield_curve = round(tnx - twy, 2) if tnx and twy else 0

    # تحديد حالة البيئة الاقتصادية بشكل آلي لإعطاء الـ AI سياقاً محدداً
    dxy_bias   = "قوي" if dxy > 104 else ("ضعيف" if dxy < 101 else "محايد")
    ry_bias    = "مرتفع ↑ (ضغط على الذهب)" if real_yield > 1.5 else ("متوسط" if real_yield > 0 else "سالب ↓ (دعم للذهب)")
    vix_state  = "مرتفع (خوف)" if vix > 25 else ("منخفض (هدوء)" if vix < 18 else "متوسط")
    eq_state   = "أسهم ترتفع (Risk-On)" if sp500_pct > 0.3 else ("أسهم تهبط (Risk-Off)" if sp500_pct < -0.3 else "أسهم مستقرة")
    yc_state   = "منحنى مقلوب (مخاوف ركود)" if yield_curve < -0.1 else ("منحنى طبيعي" if yield_curve > 0.1 else "منحنى شبه مسطح")

    prompt = f"""أنت خبير اقتصادي كمي متخصص. اكتب تقرير صحة الاقتصاد الأمريكي بالعربية ملتزماً بهذا القالب حرفياً:

📊 مؤشر صحة الاقتصاد الأمريكي | اليوم

🇺🇸 الحالة العامة:
[جملة واحدة دقيقة تصف الحالة الاقتصادية بناءً على: {eq_state}، DXY={dxy:.1f}({dxy_bias})]

📈 النمو والاستهلاك:
[تحليل 2 جملة: منحنى العوائد ({yc_state}، فارق {yield_curve:+.2f}%) وتأثيره على الائتمان والنمو]

🏦 التضخم والفائدة:
[تحليل 2 جملة: التضخم {inflation:.2f}%، معدل الفائدة={interest_rate:.2f}%، العائد الحقيقي={real_yield:+.2f}% ({ry_bias})]

👷 سوق العمل:
[جملة واحدة عن دلالة الأسواق الحالية على سوق العمل: VIX={vix:.1f}({vix_state})، أسهم {sp500_pct:+.2f}%]

🟡 التأثير على الذهب:
[جملتان محددتان: كيف يؤثر العائد الحقيقي {real_yield:+.2f}% والدولار {dxy:.1f} على الذهب الآن مع حكم صعودي أو هبوطي]

💲 التأثير على الدولار:
[جملة واحدة: DXY عند {dxy:.1f}({dxy_pct:+.2f}%) واتجاهه بناءً على العوائد والأسهم]

🧭 النظرة العامة:
[خلاصة في جملتين: الصورة الكاملة للبيئة الاقتصادية وتأثيرها على الذهب اليوم]

القاعدة: لا تكتب مقدمة. لا تضف نصاً خارج القالب. كل أرقام في القالب يجب أن تكون من البيانات المعطاة فقط."""

    for model_name in GROQ_MODELS:
        try:
            log.info(f"🤖 جاري توليد القالب الثاني (الاقتصاد الكلي) عبر {model_name}...")
            resp = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": MASTER_SYSTEM_PROMPT + "أنت خبير اقتصادي كمي. اكتب تحليلاً مالياً دقيقاً محدداً. استخدم فقط الأرقام المعطاة. لا تكتب خارج القالب."},
                    {"role": "user", "content": prompt},
                ],
                model=model_name,
                temperature=0.15,
                max_tokens=900,
            )
            return resp.choices[0].message.content
        except Exception as e:
            log.warning(f"⚠️ [{model_name}] فشل في توليد القالب الثاني: {e}")
            time.sleep(10)
            continue

    return "⚠️ تعذر توليد تقرير الاقتصاد الكلي بسبب ضغط على سيرفرات الذكاء الاصطناعي."



def _build_template_3(d: dict) -> str:
    """بناء القالب الثالث (تقرير شهية المخاطرة) عبر الذكاء الاصطناعي"""
    client = Groq(api_key=random.choice(GROQ_KEYS)) if GROQ_KEYS else None
    if not client:
        return "⚠️ لا يمكن توليد تقرير المخاطرة لعدم توفر مفتاح Groq."

    sp500_pct = d.get('sp500_pct', 0.0)
    nasdaq_pct = d.get('nasdaq_pct', 0.0)
    nasdaq_p = d.get('nasdaq_p', 0.0)
    vix_pct = d.get('vix_pct', 0.0)
    vix_p = d.get('vix_p', 0.0)
    dxy_pct = d.get('dxy_pct', 0.0)
    dxy_p = d.get('dxy_p', 0.0)

    # 1. حساب درجة المخاطرة رياضياً
    score = 5 # محايد كبداية
    
    # الأسهم
    if sp500_pct > 0.5 and nasdaq_pct > 0.5: score += 2
    elif sp500_pct > 0 and nasdaq_pct > 0: score += 1
    elif sp500_pct < -0.5 and nasdaq_pct < -0.5: score -= 2
    elif sp500_pct < 0 and nasdaq_pct < 0: score -= 1
        
    # مؤشر الخوف VIX
    if vix_pct < -2: score += 2
    elif vix_pct < 0: score += 1
    elif vix_pct > 2: score -= 2
    elif vix_pct > 0: score -= 1
        
    # الدولار
    if dxy_pct < -0.2: score += 1
    elif dxy_pct > 0.2: score -= 1
        
    # تحديد الحالة
    score = max(1, min(10, score)) # حصر بين 1 و 10
    if score >= 7:
        state = "🟢 Risk-On قوي"
    elif score >= 6:
        state = "🟢 Risk-On ضعيف"
    elif score <= 4:
        state = "🔴 Risk-Off قوي"
    else:
        state = "🟡 Risk-Neutral (متذبذب/حذر)"

    sign_sp = "+" if sp500_pct > 0 else ""
    sign_nq = "+" if nasdaq_pct > 0 else ""
    sign_vx = "+" if vix_pct > 0 else ""
    sign_dx = "+" if dxy_pct > 0 else ""

    template = f"""🌎 تقرير شهية المخاطرة
يقيس هذا التقرير هل المستثمرون يتجهون نحو المخاطرة أم يبحثون عن الأمان والملاذات.

الحالة:
{state}
القوة: {score}/10

📊 الأسواق:
S&P500: {sign_sp}{sp500_pct}%
Nasdaq: {sign_nq}{nasdaq_pct}%
VIX: {vix_p} ({sign_vx}{vix_pct}%)
DXY: {dxy_p} ({sign_dx}{dxy_pct}%)

📈 القراءة:
[اكتب القراءة بناء على الحالة والأرقام]

🟡 الذهب:
الانحياز الحالي:
[اكتب تأثير الحالة الحالية على الملاذات الآمنة والذهب]

💵 الدولار:
الانحياز الحالي:
[اكتب تأثير الحالة الحالية على الدولار]

الخلاصة:
[اكتب خلاصة تدفق السيولة]

ℹ️ شرح سريع

🟢 Risk-On = المستثمرون أكثر تقبلاً للمخاطر ويميلون للأصول عالية المخاطرة.
🔴 Risk-Off = ارتفاع الحذر والخوف في الأسواق وزيادة الطلب على الملاذات الآمنة مثل الذهب والدولار."""

    prompt = f"""أنت خبير مالي محترف. طلب مني العميل تقرير عن 'شهية المخاطرة' يطابق هذا القالب بالضبط:

{template}

المطلوب:
لقد قمت أنا بحساب الأرقام وتحديد الحالة (Risk-On / Risk-Off) كما هي ظاهرة في القالب.
مهمتك هي ملء الفراغات بين الأقواس المربعة [...] بناءً على الحالة والأرقام الموجودة.
إذا كانت الحالة Risk-On قوي، اشرح كيف يقل الطلب على الملاذات وتتدفق السيولة للأسهم.
إذا كانت الحالة Risk-Off، اشرح العكس (الخوف يدفع للذهب).
لا تكتب أي مقدمات أو خواتيم أو نصوص إضافية خارج القالب الموضح."""

    for model_name in GROQ_MODELS:
        try:
            log.info(f"🤖 جاري توليد القالب الثالث (شهية المخاطرة) عبر {model_name}...")
            resp = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": MASTER_SYSTEM_PROMPT + "أنت خبير أسواق مالية. التزم بالقالب حرفياً ولا تضف شيئاً خارجه."},
                    {"role": "user", "content": prompt},
                ],
                model=model_name,
                temperature=0.2,
                max_tokens=700,
            )
            return resp.choices[0].message.content
        except Exception as e:
            log.warning(f"⚠️ [{model_name}] فشل في توليد القالب الثالث: {e}")
            time.sleep(10)
            continue
            
    return "⚠️ تعذر توليد تقرير المخاطرة بسبب ضغط على سيرفرات الذكاء الاصطناعي."

def _build_template_4(d: dict) -> str:
    """بناء القالب الرابع (تقرير عوائد السندات الأمريكية) عبر الذكاء الاصطناعي"""
    client = Groq(api_key=random.choice(GROQ_KEYS)) if GROQ_KEYS else None
    if not client:
        return "⚠️ لا يمكن توليد تقرير عوائد السندات لعدم توفر مفتاح Groq."

    tnx = d.get('tnx_val', 0.0) or 0.0
    twy = d.get('twy_val', 0.0) or 0.0
    tty = d.get('tty', 0.0) or 0.0        # 30Y yield
    tnx_diff = d.get('tnx_diff', 0)
    twy_diff = d.get('twy_diff', 0)

    diff_val = round(tnx - twy, 2)
    diff_30_10 = round(tty - tnx, 2) if tty else None

    if diff_val < -0.1:
        curve_state = "مقلوب (Inverted)"
    elif diff_val > 0.1:
        curve_state = "طبيعي (Normal)"
    else:
        curve_state = "شبه مسطح (Flat)"

    tnx_dir = "ارتفع" if tnx_diff > 0 else "انخفض" if tnx_diff < 0 else "استقر"
    twy_dir = "ارتفع" if twy_diff > 0 else "انخفض" if twy_diff < 0 else "استقر"
    tty_str = f"{tty:.2f}%" if tty else "—"
    diff_30_10_str = f"{diff_30_10:+.2f}%" if diff_30_10 is not None else "—"

    real_yield = d.get('real_yield', 0.0)
    cpi = d.get('cpi_yoy', 0.0)

    template = f"""📊 تقرير عوائد السندات الأمريكية | التحديث اليومي

🇺🇸 عائد 10 سنوات:
{tnx:.2f}%

الحركة:
{tnx_dir} بمقدار {abs(tnx_diff)} نقطة أساس. [اكتب تحليلاً قصيراً جداً لهذه الحركة]

🇺🇸 عائد 30 سنة:
{tty_str}

التحليل:
عائد 30 سنة عند {tty_str}، الفارق مع 10 سنوات {diff_30_10_str}. [اكتب ماذا يعني هذا الفارق عن توقعات النمو بعيدة المدى]

🇺🇸 عائد سنتين:
{twy:.2f}%

التوقعات:
{twy_dir} بمقدار {abs(twy_diff)} نقطة أساس. [اكتب ماذا يشير ذلك بخصوص الفائدة]

📈 منحنى العوائد الكامل (2Y → 10Y → 30Y):
{curve_state} | 2Y:{twy:.2f}% | 10Y:{tnx:.2f}% | 30Y:{tty_str}

الفارق بين العشر سنوات والسنتين عند {diff_val} نقطة، [اكتب ماذا يعكس ذلك تجاه آفاق النمو]

⚖️ العائد الحقيقي (Real Yield):
العائد الحقيقي يبلغ {real_yield:.2f}% (10Y {tnx:.2f}% مطروحاً منها التضخم {cpi:.1f}%). [اكتب كيف يؤثر هذا العائد الحقيقي الإيجابي/السلبي على جاذبية الذهب]

🟡 تأثير الذهب:
[تأثير العوائد الحالية والمعدل الحقيقي على الذهب]

💵 تأثير الدولار:
[تأثير العوائد الحالية على الدولار]

🧭 الخلاصة:
[خلاصة حركة العوائد الثلاثة (2Y/10Y/30Y) وتأثيرها العام]"""

    prompt = f"""أنت محلل أسواق سندات محترف. طلب مني العميل تقرير عن 'عوائد السندات الأمريكية' يطابق هذا القالب بالضبط:

{template}

المطلوب:
لقد قمت أنا بحساب أرقام العوائد وفارق النقاط الأساسية (Basis Points) والمنحنى.
مهمتك هي استبدال الأقواس المربعة [...] بتحليل مالي دقيق واحترافي بناءً على الأرقام الحالية.
إذا كانت العوائد ترتفع بقوة، اذكر أن ذلك يشكل ضغطاً على الذهب ويدعم الدولار. وإذا انخفضت، اذكر العكس.
إذا كان المنحنى مقلوباً، اذكر أنه يعكس مخاوف ركود.
اترك جميع الأرقام والنسب المئوية كما هي تماماً. التزم بالقالب تماماً ولا تكتب أي نصوص إضافية أو مقدمات."""

    for model_name in GROQ_MODELS:
        try:
            log.info(f"🤖 جاري توليد القالب الرابع (عوائد السندات) عبر {model_name}...")
            resp = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": MASTER_SYSTEM_PROMPT + "أنت خبير أسواق مالية. التزم بالقالب حرفياً ولا تضف شيئاً خارجه. لا تغير الأرقام."},
                    {"role": "user", "content": prompt},
                ],
                model=model_name,
                temperature=0.2,
                max_tokens=750,
            )
            return resp.choices[0].message.content
        except Exception as e:
            log.warning(f"⚠️ [{model_name}] فشل في توليد القالب الرابع: {e}")
            time.sleep(10)
            continue

    return "⚠️ تعذر توليد تقرير السندات بسبب ضغط على سيرفرات الذكاء الاصطناعي."




def _build_template_5(d: dict) -> str:
    """بناء القالب الخامس (تقرير قوة العملات) عبر الذكاء الاصطناعي"""
    client = Groq(api_key=random.choice(GROQ_KEYS)) if GROQ_KEYS else None
    if not client:
        return "⚠️ لا يمكن توليد تقرير قوة العملات لعدم توفر مفتاح Groq."

    fx_sorted = d.get('fx_sorted', [])
    if not fx_sorted or len(fx_sorted) < 6:
        return "⚠️ بيانات العملات غير متوفرة."

    top_3 = fx_sorted[:3]
    bottom_3 = fx_sorted[-3:] # أضعف 3
    bottom_3.reverse() # نعكسهم عشان نجيب الأضعف خالص الأول

    template = f"""📊 تقرير قوة العملات | تحديث يومي
🟢 أقوى العملات:
🥇 {top_3[0][0]} | القوة: {top_3[0][1]:+.4f}%
السبب: [سبب قوة هذه العملة بناء على حركتها أمام الدولار]
🥈 {top_3[1][0]} | القوة: {top_3[1][1]:+.4f}%
السبب: [سبب قوة هذه العملة]
🥉 {top_3[2][0]} | القوة: {top_3[2][1]:+.4f}%
السبب: [سبب قوة هذه العملة]
🔴 أضعف العملات:
1️⃣ {bottom_3[0][0]} | القوة: {bottom_3[0][1]:+.4f}%
السبب: [سبب ضعف هذه العملة أمام الدولار]
2️⃣ {bottom_3[1][0]} | القوة: {bottom_3[1][1]:+.4f}%
السبب: [سبب ضعف هذه العملة]
3️⃣ {bottom_3[2][0]} | القوة: {bottom_3[2][1]:+.4f}%
السبب: [سبب ضعف هذه العملة]
⚡️ الزخم:
[اكتب وصفاً لحالة الزخم وحركة الأسواق الحالية بناء على هذه الأرقام]
💵 تأثير هذه العملات على مؤشر الدولار (DXY):
[اشرح كيف يؤثر صعود العملات القوية أعلاه وهبوط الضعيفة على سلة الدولار DXY اليوم]
🟡 التأثير على الذهب (XAU):
[استنتج حركة الذهب المتوقعة بناءً على أداء الدولار والعملات المنافسة]
🧭 الخلاصة:
[خلاصة لهيمنة عملات معينة وضعف أخرى]"""

    prompt = f"""أنت محلل أسواق عملات (Forex) محترف. طلب مني العميل تقرير عن 'قوة العملات' يطابق هذا القالب بالضبط:

{template}

المطلوب:
لقد قمت أنا بحساب ترتيب العملات وقوتها المئوية اليوم كما يظهر في القالب أعلاه.
مهمتك هي ملء الفراغات بين الأقواس المربعة [...] بأسباب احترافية جداً وواقعية بناءً على الأرقام المعطاة.
على سبيل المثال: إذا كانت قوة EUR موجبة، فالسبب هو "أداء قوي وارتفاع ملحوظ بفضل تدفق السيولة".
في الزخم والخلاصة: اذكر من يهيمن ومن يعاني اليوم بناء على الترتيب الموجود.
التزم بالقالب الموضح تماماً ولا تقم بإضافة مقدمات أو تغيير تنسيق الأسطر."""

    for model_name in GROQ_MODELS:
        try:
            log.info(f"🤖 جاري توليد القالب الخامس (قوة العملات) عبر {model_name}...")
            resp = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": MASTER_SYSTEM_PROMPT + "أنت خبير أسواق عملات (Forex). التزم بالقالب حرفياً ولا تضف شيئاً خارجه."},
                    {"role": "user", "content": prompt},
                ],
                model=model_name,
                temperature=0.2,
                max_tokens=650,
            )
            return resp.choices[0].message.content
        except Exception as e:
            log.warning(f"⚠️ [{model_name}] فشل في توليد القالب الخامس: {e}")
            time.sleep(10)
            continue
            
    return "⚠️ تعذر توليد تقرير قوة العملات بسبب ضغط على سيرفرات الذكاء الاصطناعي."

def _build_template_6(d: dict, fixed_rep: str, t0: str, t1: str, t2: str, t3: str, t4: str, t5: str) -> str:
    """بناء القالب السادس والأخير (الخلاصة الذكية) عبر الذكاء الاصطناعي"""
    client = Groq(api_key=random.choice(GROQ_KEYS)) if GROQ_KEYS else None
    if not client:
        return "⚠️ لا يمكن توليد تقرير الخلاصة لعدم توفر مفتاح Groq."

    pivot_val = d.get('pivot', '---')

    import re
    clean_t0 = re.sub(r'[╭─╮├┤│╰╯]', '', t0) if t0 else ""
    
    template = f"""🎯 خلاصة انحياز الذهب | التحديث المباشر

📈 نسبة الصعود: [النسبة المئوية]%
📉 نسبة الهبوط: [النسبة المئوية]%

🧭 الخلاصة:
[سطرين أو ثلاثة فقط تلخص الموقف العام للذهب بناء على كل التقارير المرفقة مع إعطاء قرار نهائي واضح. اكتب بلغة يفهمها المبتدئون]

📍 نقطة الفصل اليومية (Pivot):
{pivot_val}$ [اشرح دلالة التداول حالياً فوق أو تحت هذا المستوى]

📌 مستويات التداول الحالية:
[انقل مستويات البيع والشراء (التي تحتوي على الدوائر 🔴 أو 🟢 أو 🟡) من تقرير التحليل الفني المرفق وضعها هنا بدقة كما هي وبدون تغيير في أرقامها]"""

    prompt = f"""أنت "المحلل الأكبر" والمستشار المالي النهائي. 
لقد قام فريقك بإعداد تقارير شاملة حول الذهب تشمل (الصفقات الأساسية، الصفقات المتقدمة، التحليل الفني، الاقتصاد، المخاطرة، العوائد، والعملات).
الهدف الآن هو استخلاص عصارة هذه التقارير في "رسالة مختصرة ومباشرة للجمهور العام" تطابق هذا القالب بالضبط:

{template}

إليك جميع التقارير للتحليل:
--- التقرير الأساسي (الصفقات ومستويات الدعم والمقاومة): ---
{fixed_rep}
--- تقرير الصفقات المتقدمة (زيرو انعكاس ولوت عالي): ---
{clean_t0}
--- التقرير 1 (الفني والزخم): ---
{t1}
--- التقرير 2 (الاقتصاد الكلي): ---
{t2}
--- التقرير 3 (المخاطرة): ---
{t3}
--- التقرير 4 (العوائد): ---
{t4}
--- التقرير 5 (العملات): ---
{t5}

المطلوب:
1. اقرأ جميع التقارير والصفقات المرفقة بعناية فائقة.
2. استنتج رقمين دقيقين لنسبة الصعود والهبوط (مجموعهما 100%).
3. اكتب خلاصة مكثفة في سطرين أو ثلاثة كحد أقصى للاتجاه العام.
4. ابحث في التقارير المرفقة (خاصة التقرير الأساسي وتقرير الصفقات المتقدمة والفني) عن أبرز مناطق البيع 🔴 والشراء 🟢 وانقلها بأرقامها الدقيقة إلى قسم المستويات. لا تؤلف أرقاماً.
5. لا تكتب أي مقدمات أو تحيات، فقط أخرج القالب المملوء."""

    for model_name in GROQ_MODELS:
        try:
            log.info(f"🤖 جاري توليد الخلاصة النهائية (القالب 6) عبر {model_name}...")
            resp = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": MASTER_SYSTEM_PROMPT + "أنت المحلل المالي الأكبر. اصدر حكماً نهائياً قصيراً ودقيقاً للجمهور والتزم بالقالب الحرفي."},
                    {"role": "user", "content": prompt},
                ],
                model=model_name,
                temperature=0.3,
                max_tokens=600,
            )
            return resp.choices[0].message.content
        except Exception as e:
            log.warning(f"⚠️ [{model_name}] فشل في توليد الخلاصة: {e}")
            time.sleep(10)
            continue
            
    return "⚠️ تعذر توليد الخلاصة النهائية."


def _build_combined_summary(
    spot_data: dict,
    futures_report: str,
    spot_report: str,
    futures_t1: str,
    futures_t2: str,
    spot_t1: str,
    spot_t2: str,
    futures_t0: str,
    spot_t0: str,
    bull_pct: int = 50,
    bear_pct: int = 50,
) -> str:
    """
    الخلاصة النهائية المشتركة — تصدر مرة واحدة فقط بعد انتهاء
    كلا البوتين (الآجل والفوري)، وتجمع القرار النهائي من السوقين.
    """
    client = Groq(api_key=random.choice(GROQ_KEYS)) if GROQ_KEYS else None
    if not client:
        return "⚠️ لا يمكن توليد الخلاصة المشتركة لعدم توفر مفتاح Groq."

    import re
    def clean(t): return re.sub(r'[╭─╮├┤│╰╯]', '', t) if t else ""

    pivot_spot    = spot_data.get('pivot', '---')
    gold_spot     = spot_data.get('gold', 0)

    # تحديد الاتجاه الكلي بناءً على النسب المحسوبة
    if bull_pct >= 60:
        direction_label = "صعودي 📈"
    elif bear_pct >= 60:
        direction_label = "هبوطي 📉"
    else:
        direction_label = "متذبذب ⚖️"

    prompt = f"""أنت المحلل الأكبر. لقد انتهى فريقك للتو من إعداد تقارير شاملة لسوقَي الذهب:
① سوق الآجل (Futures/GC=F)
② سوق الفوري (Spot/XAUUSD)

السعر الفوري الحالي: {gold_spot:,.2f}$
نقطة الفصل اليومية (Pivot): {pivot_spot}$
الاتجاه المحسوب رياضياً: {direction_label} (صعود {bull_pct}% / هبوط {bear_pct}%)

── ملخص التحليل الفني للآجل ──
{clean(futures_t1)[:600]}

── ملخص التحليل الفني للفوري ──
{clean(spot_t1)[:600]}

── أبرز صفقات الآجل ──
{clean(futures_t0)[:400]}

── أبرز صفقات الفوري ──
{clean(spot_t0)[:400]}

المطلوب منك: اكتب خلاصة نهائية واحدة تتبع هذا القالب بالضبط (لا تضف أي مقدمة):

🏆 الخلاصة النهائية | آجل + فوري

📈 نسبة الصعود: {bull_pct}%
📉 نسبة الهبوط: {bear_pct}%

🧭 القرار النهائي (3-4 أسطر):
[اكتب حكماً واضحاً ومختصراً يجمع بين السوقين ويخبر القارئ ماذا يفعل الآن بناءً على الاتجاه {direction_label}]

📍 نقطة الفصل اليومية:
{pivot_spot}$ — [اشرح دلالة التداول حالياً فوق أو تحت هذا المستوى بجملة واحدة]

📌 أقوى صفقة الآن:
[انقل أفضل صفقة موصى بها (آجل أو فوري أيهما أقوى) بالأرقام الدقيقة كما هي]

قاعدة مهمة: لا تغير نسبة الصعود ({bull_pct}%) ولا نسبة الهبوط ({bear_pct}%) — هذه أرقام محسوبة رياضياً."""

    for model_name in GROQ_MODELS:
        try:
            log.info(f"🤖 [Combined] توليد الخلاصة المشتركة عبر {model_name}...")
            resp = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": MASTER_SYSTEM_PROMPT + "أنت المحلل المالي الأكبر. أصدر خلاصة نهائية موجزة ودقيقة تجمع بين سوقي الآجل والفوري. التزم بالقالب حرفياً. لا تغير النسب المئوية المعطاة."},
                    {"role": "user", "content": prompt},
                ],
                model=model_name,
                temperature=0.2,
                max_tokens=700,
            )
            return resp.choices[0].message.content
        except Exception as e:
            log.warning(f"⚠️ [{model_name}] فشل الخلاصة المشتركة: {e}")
            time.sleep(2)
            continue

    return "⚠️ تعذر توليد الخلاصة النهائية المشتركة."



def _build_template_0(d: dict) -> str:
    """بناء القالب التمهيدي 0 (الصفقات المتقدمة والاتجاهات) عبر الذكاء الاصطناعي"""
    client = Groq(api_key=random.choice(GROQ_KEYS)) if GROQ_KEYS else None
    if not client:
        return "⚠️ لا يمكن توليد تقرير الصفقات المتقدمة لعدم توفر مفتاح Groq."

    adv = d.get('adv_trades', {})
    
    def _format_trade(t):
        if not t: return "غير متوفر حالياً"
        return f"دخول: {t['entry']} | هدف: {t['t2']} | وقف: {t['sl']} | ({'شراء 🟢' if t['dir']=='buy' else 'بيع 🔴'})"

    # أولوية للسكالب اللحظي (5م) لأنه أقرب للسعر الحالي
    scalp = (adv.get('scalp_5m_buy') or adv.get('scalp_5m_sell')
             or adv.get('scalp_buy') or adv.get('scalp_sell'))
    # أقرب سوينج — نختار اللي دخوله أقرب للسعر الحالي
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

    bias_1h = d.get('tf_hourly', {}).get('bias', '—')
    bias_1d = d.get('tf_daily', {}).get('bias', '—')
    score_1h = d.get('tf_hourly', {}).get('score', 0)
    
    first_hit = "القمة (مقاومة) أولاً 📈" if score_1h > 0 else "القاع (دعم) أولاً 📉" if score_1h < 0 else "متذبذب - لا مسار واضح ⚖️"
    
    template = f"""🎯 التقرير التمهيدي: صفقات ذكية واتجاهات الذهب

⏱️ الاتجاه خلال ساعة: [ترجم إلى العربية بدقة: {bias_1h}]
📅 الاتجاه خلال يوم: [ترجم إلى العربية بدقة: {bias_1d}]
🏁 الأقرب للضرب أولاً: {first_hit}

🔥 صفقات السكالبينج (خطف سريع):
{scalp_str}

🌊 صفقات السوينج (مدى أبعد):
{swing_str}

🎯 صفقات زيرو انعكاس (قناص):
{rev_str}"""

    prompt = f"""أنت مستشار تداول آلي خبير. طلب مني العميل تقريراً عن "الصفقات المتقدمة والاتجاهات" يطابق هذا القالب بالضبط:

{template}

المطلوب:
مهمتك هي صياغة هذا التقرير بلمسة احترافية خفيفة. 
- في خانة "الاتجاه"، ترجم كلمة (bullish إلى صاعد، bearish إلى هابط، neutral إلى عرضي).
- بالنسبة للصفقات (سكالبينج، سوينج، زيرو انعكاس)، اترك البيانات والأرقام والاتجاهات كما هي تماماً. إذا كانت "غير متوفر حالياً" اتركها كما هي.
- التزم بالقالب تماماً ولا تكتب أي نصوص إضافية أو مقدمات."""

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
            
    return "⚠️ تعذر توليد تقرير الصفقات المتقدمة."

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
    markers = [
        "📐 تحليل العائد الحقيقي",
        "🔢 المستويات",
        "📊 تقرير قوة الذهب",
        "📈 توقعات السعر",
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
        sep_idx = remaining.rfind(SEP, 0, idx)
        cut = sep_idx if sep_idx >= 0 else idx
        part = remaining[:cut].strip()
        if part:
            parts.append(part)
        remaining = remaining[cut:].strip()

    if remaining.strip():
        parts.append(remaining.strip())

    if len(parts) < 2:
        return [(f"👑 التقرير الكمي الشامل ({mode_label})", report_text)]

    result = []
    for i, part in enumerate(parts):
        label = labels[i] if i < len(labels) else labels[-1]
        result.append((label, part))
    return result





def _build_template_7(d: dict) -> str:
    """قالب الصفقات المتخصصة والفريمات الزمنية (اللوت العالي وزيرو انعكاس)"""
    client = Groq(api_key=random.choice(GROQ_KEYS)) if GROQ_KEYS else None
    if not client: return "⚠️ تعذر توليد التقرير."
    
    adv = d.get('adv_trades', {})
    def _t(k):
        v = adv.get(k)
        return f"{v['entry']}$ | هدف: {v['t2']}$ | وقف: {v['sl']}$ | ({'شراء 🟢' if v['dir']=='buy' else 'بيع 🔴'})" if v else "غير متوفر"

    gold = d.get('gold', 0)
    prompt = f"""اكتب 'مصفوفة الصفقات المتخصصة للذهب' بناءً على البيانات التالية حصراً.
استخدم لغة الأرقام فقط ولا تكتب أي مقدمات أو شروحات (مثل: استخدمت بيانات كذا أو استنتجت كذا).

البيانات المتاحة:
السكالبينج: {_t('scalp_5m_buy')} أو {_t('scalp_5m_sell')}
السوينج: {_t('swing_buy')} أو {_t('swing_sell')}
زيرو انعكاس: {_t('rev_buy')} أو {_t('rev_sell')}

المطلوب إخراج القالب بهذا الشكل الحرفي (بدون تغيير العناوين):

🎯 صفقات اللوت العالي (High Lot)
(صفقة سكالبينج مستنتجة سريعة الأهداف بوقف ضيق، جودة > 90%. الفريم: 5 دقائق)
- دخول: [الرقم]
- هدف: [الرقم]
- وقف: [الرقم]
- الاتجاه: [شراء/بيع]

🎯 صفقات زيرو انعكاس (القناص)
(صفقة من بيانات زيرو انعكاس، دقة > 90%. الفريم: 1-4 ساعات)
- دخول: [الرقم]
- هدف: [الرقم]
- وقف: [الرقم]
- الاتجاه: [شراء/بيع]

🌊 صفقات السوينج (مدى أبعد)
(صفقة من بيانات السوينج. الفريم: يومي وأسبوعي)
- دخول: [الرقم]
- هدف: [الرقم]
- وقف: [الرقم]
- الاتجاه: [شراء/بيع]

⚡ مصفوفة السكالبينج
(صفقة من بيانات السكالبينج. الفريمات: 5د، 10د، 15د، 30د)
- دخول: [الرقم]
- هدف: [الرقم]
- وقف: [الرقم]
- الاتجاه: [شراء/بيع]

تحذير: أنت خبير كمي فائق الدقة. استنبط أرقام الصفقات بعبقرية وموثوقية عالية جداً بناءً على السياق. لا تضف أي نص خارج الأقواس. استبدل الأقواس بالأرقام فقط. (أجبر النظام على استخراج أفضل فرصة متاحة بناءً على أقرب مستوى ارتداد، يمنع منعاً باتاً كتابة "لا توجد فرصة")."""
    
    for model_name in GROQ_MODELS:
        try:
            resp = client.chat.completions.create(
                messages=[{"role": "system", "content": MASTER_SYSTEM_PROMPT + "أنت روبوت صفقات. نفذ القالب بالأرقام فقط بدون رغي نهائياً."}, {"role": "user", "content": prompt}],
                model=model_name, temperature=0.05, max_tokens=600
            )
            return resp.choices[0].message.content
        except: pass
    return "⚠️ تعذر توليد قالب الصفقات المتخصصة."

def _build_template_8(d: dict) -> str:
    """قالب تأثير الأسواق والمؤسسات (الحيتان)"""
    client = Groq(api_key=random.choice(GROQ_KEYS)) if GROQ_KEYS else None
    if not client: return "⚠️ تعذر توليد التقرير."
    
    gold = d.get('gold', 0)
    atr = d.get('atr', 20)
    vol_state = d.get('gold_daily', {}).get('Volume', [0])
    last_vol = vol_state[-1] if len(vol_state) > 0 else 0
    if last_vol == 0:
        vol_text = "البيانات الكمية غير مكتملة المصدر، يتم الاعتماد على زخم السيولة السعرية (ATR Proxy)."
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
- عقود الخيارات (VIX): (جملة واحدة بناء على VIX)"""

    for model_name in GROQ_MODELS:
        try:
            resp = client.chat.completions.create(
                messages=[{"role": "system", "content": MASTER_SYSTEM_PROMPT + "أنت محلل مؤسسات مالي محترف. لا تكتب مقدمات ولا تستخدم عبارات مثل 'بناء على الأرقام'."}, {"role": "user", "content": prompt}],
                model=model_name, temperature=0.1, max_tokens=600
            )
            return resp.choices[0].message.content
        except: pass
    return "⚠️ تعذر توليد قالب الحيتان."

def _build_template_9(d: dict) -> str:
    """تقرير اتجاه الذهب اليومي (قالب رياضي ثابت)"""
    tf_15 = d.get('tf_15m', {}).get('bias', '—')
    tf_1h = d.get('tf_hourly', {}).get('bias', '—')
    tf_4h = d.get('tf_4h', {}).get('bias', '—')
    tf_1d = d.get('tf_daily', {}).get('bias', '—')
    
    return f"""📊 تقرير اتجاه الذهب اليومي

الترند الحالي:
⋆ 15 دقيقة: {tf_15}
⏱️ 1 ساعة: {tf_1h}
⏰ 4 ساعات: {tf_4h}
📅 يومي: {tf_1d}

الخلاصة: 
(الاتجاه مبني رياضياً على توافق الإطارات الزمنية ولا يعكس بالضرورة الانعكاسات اللحظية المفاجئة)."""

def _build_template_10(d: dict) -> str:
    """التقرير الأسبوعي الشامل"""
    client = Groq(api_key=random.choice(GROQ_KEYS)) if GROQ_KEYS else None
    if not client: return "⚠️ تعذر توليد التقرير."
    
    w_bias = d.get('tf_weekly', {}).get('bias', '—')
    w_rsi = d.get('tf_weekly', {}).get('rsi', 50)
    
    prompt = f"""اكتب 'التقرير الأسبوعي للذهب'.
المعطيات: الاتجاه الأسبوعي ({w_bias}) | مؤشر RSI ({w_rsi}) | السعر ({d.get('gold')}$)

يجب أن تكون الجودة احترافية جداً، والقرارات حاسمة، والتحليل الفني عميق ومدروس بدقة متناهية. المطلوب إخراج التقرير جافاً بدون "بغبغة" لتعليماتي. لا تكتب "يبدو أن السوق..." أو "بناءً على...". اعطني النتيجة مباشرة كنص عادي (Plain Text). يمنع استخدام أي أكواد برمجية (مثل Java أو Python) أو تنسيقات Markdown معقدة:

📅 الهيكل الأسبوعي الكلي:
- (تحليل مباشر للاتجاه العام في سطر واحد)

📊 الزخم ومؤشرات المدى الطويل:
- مؤشر RSI: {w_rsi}
- (دلالة هذا المؤشر فنياً في سطر واحد)

🎯 تأثير ذلك على صفقات السوينج:
- (استراتيجية السوينج الموصى بها هذا الأسبوع في سطر واحد)"""

    for model_name in GROQ_MODELS:
        try:
            resp = client.chat.completions.create(
                messages=[{"role": "system", "content": MASTER_SYSTEM_PROMPT + "أنت خبير أسواق كمي. التزم بالأوامر حرفياً بدون أي إطالة أو تكرار للتعليمات."}, {"role": "user", "content": prompt}],
                model=model_name, temperature=0.1, max_tokens=500
            )
            return resp.choices[0].message.content
        except: pass
    return "⚠️ تعذر توليد التقرير الأسبوعي."


def _build_template_11(d: dict) -> str:
    """بناء قالب تقرير CFTC لمراكز المضاربين"""
    client = Groq(api_key=random.choice(GROQ_KEYS)) if GROQ_KEYS else None
    if not client: return ""
    
    gold_price = d.get('gold', 0)
    w_bias = d.get('tf_weekly', {}).get('bias', 'محايد')
    
    prompt = f"""أنت خبير كمي كبير ومستشار صناديق تحوط.
بناءً على أحدث بيانات متاحة لديك عن تقرير التزام المتداولين (CFTC) للذهب والفضة والنفط والعملات (الين، اليورو، الباوند، الفرنك).
علماً أن الذهب يتداول الآن عند {gold_price}$ واتجاهه الأسبوعي التقني: {w_bias}.

المطلوب:
توليد تقرير CFTC احترافي وحديث بالأرقام التقديرية الذكية جداً أو الحقيقية (بناء على معرفتك الأخيرة بالسوق)، والتزام العرض بنفس هذا الهيكل الحرفي تماماً:

📰📊 تقرير CFTC | مراكز المضاربين للأسبوع المنتهي في [تاريخ آخر جمعة]
📈 تكشف بيانات لجنة تداول السلع الآجلة (CFTC) عن استمرار تغير تمركزات المستثمرين في أسواق المعادن والعملات والطاقة، ما يعطي إشارات مهمة لاتجاهات السوق خلال الفترة المقبلة.
━━━━━━━━━━━━
🟡 الذهب (Gold)
[⬆️ أو ⬇️] [ارتفعت/تراجعت] مراكز الشراء بمقدار [رقم] عقداً لتصل إلى [رقم] عقداً.
📊 [تحليل قصير جداً لثقة المستثمرين بناءً على حركات الفائدة أو الدولار].
[🟢 التأثير: إيجابي/سلبي] للذهب على المدى [القصير/المتوسط].
━━━━━━━━━━━━
⚪ الفضة (Silver)
[⬆️ أو ⬇️] [ارتفعت/تراجعت] مراكز الشراء بمقدار [رقم] عقداً لتصل إلى [رقم] عقداً.
📌 [استنتاج لشهية المستثمرين].
[🟢 التأثير: إيجابي/سلبي] للفضة.
━━━━━━━━━━━━
🛢 النفط الخام WTI
[⬆️ أو ⬇️] [ارتفعت/تراجعت] مراكز الشراء بمقدار [رقم] عقداً لتصل إلى [رقم] عقداً.
📌 [استنتاج تجاه أسعار الطاقة].
[🔴 التأثير: سلبي/إيجابي] للنفط.
━━━━━━━━━━━━
💱 مراكز العملات الرئيسية
🇯🇵 الين الياباني (JPY)
[🔴/🟢] [رقم] عقد [بيع/شراء]
📌 [استنتاج عن السياسة النقدية].
🇪🇺 اليورو (EUR)
[🔴/🟢] [رقم] عقد [بيع/شراء]
📌 [استنتاج].
🇬🇧 الجنيه الإسترليني (GBP)
[🔴/🟢] [رقم] عقد [بيع/شراء]
📌 [استنتاج].
🇨🇭 الفرنك السويسري (CHF)
[🔴/🟢] [رقم] عقد [بيع/شراء]
📌 [استنتاج].
━━━━━━━━━━━━
📊 الخلاصة:
🟢 إيجابي:
- [الاسم]
🔴 سلبي:
- [الاسم]

تحذير: لا تغير الهيكل أبداً.
"""
    for model_name in GROQ_MODELS:
        try:
            resp = client.chat.completions.create(
                messages=[{"role": "system", "content": MASTER_SYSTEM_PROMPT + "أنت محلل بيانات CFTC احترافي جداً."}],
                model=model_name, temperature=0.15, max_tokens=1000
            )
            return resp.choices[0].message.content
        except: pass
    return ""

def _build_template_12(d: dict) -> str:
    """بناء قالب تقرير المشتقات وصناديق الذهب (العناصر المفقودة)"""
    client = Groq(api_key=random.choice(GROQ_KEYS)) if GROQ_KEYS else None
    if not client: return ""
    
    gold_price = d.get('gold', 0)
    w_bias = d.get('tf_weekly', {}).get('bias', 'محايد')
    
    prompt = f"""أنت محلل مشتقات مالية وصناديق (ETFs) في وول ستريت.
الذهب الآن يتداول عند {gold_price}$ والاتجاه الأسبوعي التقني هو: {w_bias}.

المطلوب إخراج هذا القالب الحرفي، وتعبئة البيانات بالاستنتاج التحليلي الدقيق والحديث المتوفر لديك كخبير للوضع الحالي للأسواق:

🏦📊 تقرير صناديق الاستثمار وسوق المشتقات (Derivatives & ETFs)
يقيس هذا التقرير تأثير العقود الورقية والفيزيكال وأسهم المناجم وسوق الأوبشن على مسار الذهب.
━━━━━━━━━━━━
1️⃣ صندوق الذهب (GLD ETF)
📌 حجم التدفقات النقدية: [تحليل مختصر لوضع صندوق GLD وهل يتم الشراء أم التسييل].
🟢 التأثير على الذهب: [إيجابي/سلبي]

2️⃣ أسهم منتجي الذهب (GDX) ومنتجي الفضة (SIL)
📌 أداء المناجم: [تقييم أداء GDX و SIL كمؤشر استباقي للذهب].
🟢 التأثير: [إيجابي/سلبي]

3️⃣ سوق عقود الخيارات (Options Market)
📌 تمركزات الأوبشن: [استنتاج لأماكن تمركز عقود الـ Call والـ Put للذهب].
📌 عقود خيارات النفط: [ارتباط وتأثير خيارات النفط الحالية على تضخم الذهب].

4️⃣ تأثير العقود الآجلة مقابل العقود الفورية والفيزيكال
📌 الرافعة المالية (Leverage): [حالة الرافعة المالية الحالية للمضاربين وخطر التسييل].
📌 العقود الورقية (Paper) vs الفيزيكال (Physical): [تحليل سريع للفجوة بين الطلب الفعلي والورقي للذهب].

━━━━━━━━━━━━
📊 الخلاصة للصناديق والمشتقات:
[استنتاج نهائي من سطرين يوضح هل المشتقات تدعم صعود الذهب أم هبوطه]

تحذير: التزم بالهيكل أعلاه حرفياً دون أي إطالة.
"""
    for model_name in GROQ_MODELS:
        try:
            resp = client.chat.completions.create(
                messages=[{"role": "system", "content": MASTER_SYSTEM_PROMPT + "أنت محلل صناديق ومستشار مشتقات مالي حاد الذكاء."}],
                model=model_name, temperature=0.15, max_tokens=1000
            )
            return resp.choices[0].message.content
        except: pass
    return ""

def _build_template_13(d: dict) -> str:
    """بناء قالب تحليل عقود الأوبشن الاحترافي الشامل (T13)"""
    client = Groq(api_key=random.choice(GROQ_KEYS)) if GROQ_KEYS else None
    if not client: return ""

    gold  = d.get("gold", 2000)
    atr   = d.get("atr", 20)
    rsi_d = d.get("tf_daily", {}).get("rsi", 50)
    bias_w = d.get("tf_weekly", {}).get("bias", "محايد")
    bias_d = d.get("tf_daily", {}).get("bias", "محايد")
    pivot  = round(d.get("pivot", gold), 2)
    s1, s2 = round(d.get("s1", gold - atr), 2), round(d.get("s2", gold - atr*2), 2)
    r1, r2 = round(d.get("r1", gold + atr), 2), round(d.get("r2", gold + atr*2), 2)
    variance = round(d.get("variance", 0), 2)

    # حساب مستويات رياضية دقيقة لتوجيه الذكاء الاصطناعي
    iv_estimate  = round((atr / gold) * 252**0.5 * 100, 2)       # FIX: 252 trading days (not 365 calendar days)
    hv_estimate  = round(variance / gold * 100 * 252**0.5, 2) if variance else round(iv_estimate * 0.85, 2)
    max_pain_est = round((r1 + s1) / 2, 2)                        # تقدير Max Pain رياضياً
    expected_move= round(gold * (iv_estimate / 100) / (365**0.5), 2)  # حركة يومية متوقعة
    daily_high   = round(gold + expected_move, 2)
    daily_low    = round(gold - expected_move, 2)
    breakeven_c  = round(r1 + (atr * 0.3), 2)
    breakeven_p  = round(s1 - (atr * 0.3), 2)
    delta_atm    = 0.50  # دلتا عند ATM دائماً ~0.5
    gamma_est    = round(0.0003 * (100 / iv_estimate), 6) if iv_estimate else 0.0003
    theta_est    = round(-(iv_estimate * gold * 0.01) / (365 * 252**0.5), 4) if iv_estimate else -0.5
    vega_est     = round(gold * 0.01 * (1/365**0.5) * 100, 2)
    iv_rank      = "مرتفع (>75)" if iv_estimate > 25 else ("معتدل (25-75)" if iv_estimate > 15 else "منخفض (<25)")

    prompt = f"""أنت كبير محللي المشتقات المالية في مكتب تداول مؤسساتي متخصص بالذهب. 
بناءً على البيانات الحية التالية قم بإنشاء تقرير عقود الأوبشن الاحترافي الشامل بأعلى دقة ممكنة:

── بيانات السوق اللحظية ──
السعر الحالي: {gold}$
اتجاه اليومي: {bias_d} | الأسبوعي: {bias_w}
RSI اليومي: {rsi_d}
الـ ATR اليومي: {atr}$
المحور (Pivot): {pivot}$
دعم1={s1}$ | دعم2={s2}$
مقاومة1={r1}$ | مقاومة2={r2}$
IV المُقدَّر: {iv_estimate}%
HV المُقدَّر: {hv_estimate}%
Max Pain المُقدَّر: {max_pain_est}$
الحركة اليومية المتوقعة: ±{expected_move}$
الـ Gamma المقدَّر: {gamma_est}
الـ Theta المقدَّر: {theta_est}$/يوم
الـ Vega المقدَّر: {vega_est}$
IV Rank: {iv_rank}
Breakeven Call: {breakeven_c}$ | Breakeven Put: {breakeven_p}$
القمة المتوقعة اليوم: {daily_high}$ | القاع: {daily_low}$

المطلوب: اكتب التقرير الكامل أدناه بدون أي اختصار أو قطع، مع تعبئة كل الأقواس المربعة [] بتحليل حقيقي ودقيق بناءً على البيانات أعلاه.
اكتب أرقاماً صريحة في كل مكان ممكن. لا تكتب ديباجات ولا مقدمات قبل القالب:

━━━━━━━━━━━━━━━━━━━━━━━━━━
📊⚡ تحليل عقود الأوبشن الاحترافي الشامل للذهب (XAU/USD)
تحليل Gold Futures Options — بيانات ديناميكية لحظية

━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 الوضع الحالي للسعر

- السعر الفوري الحالي: {gold}$
- افتتاح اليوم / المحور: {pivot}$
- أعلى متوقع اليوم: {daily_high}$ | أدنى متوقع: {daily_low}$
- الاتجاه اليومي: {bias_d} | الأسبوعي: {bias_w}

[سطران تحليل موجز لحالة الذهب اليوم وأسباب الحركة]

━━━━━━━━━━━━━━━━━━━━━━━━━━
1️⃣ تحليل التقلب (Volatility Analysis)

📌 Implied Volatility (IV): {iv_estimate}%
التفسير: [شرح ما تعنيه هذه النسبة للسوق الآن]
التأثير على الذهب: [إيجابي/سلبي/محايد ولماذا]

📌 Historical Volatility (HV): {hv_estimate}%
المقارنة IV vs HV: [هل الأوبشن مُبالَغ فيها؟ استراتيجية مناسبة؟]

📌 IV Rank: {iv_rank}
الدلالة: [ماذا يعني هذا الرانك للمتداولين الآن]

📌 Volatility Term Structure:
[وصف شكل منحنى التقلب: Contango/Backwardation وتأثيره]

📌 Volatility Skew:
[هل يوجد Put Skew أم Call Skew وماذا يعني]

📌 Volatility Smile:
[وصف شكل الابتسامة وما يكشفه عن مخاوف السوق]

الحكم النهائي على التقلب: [جملة واحدة حاسمة]

━━━━━━━━━━━━━━━━━━━━━━━━━━
2️⃣ تحليل الـ Greeks

📌 Delta (Δ): {delta_atm} (ATM)
التأثير: [لكل دولار يتحرك الذهب، ماذا يحدث لقيمة الأوبشن]

📌 Gamma (Γ): {gamma_est}
التأثير: [كيف تتسارع حساسية الأوبشن عند الاقتراب من السترايك]

📌 Theta (Θ): {theta_est}$/يوم
التأثير: [الوقت يسرق من البائع أم المشتري؟ ومن يستفيد الآن]

📌 Vega (ν): {vega_est}$
التأثير: [لكل 1% تغيُّر في IV، ماذا يحدث للبريميوم]

📌 Rho (ρ):
التأثير: [حساسية الأوبشن لتغيرات سعر الفائدة الفيدرالية]

📌 Greeks Profile Across Strikes:
[كيف تتوزع الـ Greeks على مستويات السترايكات المختلفة من {s2}$ إلى {r2}$]

الحكم النهائي على الـ Greeks: [استنتاج حاسم]

━━━━━━━━━━━━━━━━━━━━━━━━━━
3️⃣ تحليل الحجم والمصلحة المفتوحة (OI)

📌 Open Interest الحالي: [تقدير توزيع الـ OI بين Calls وPuts]
📌 Option Volume: [حجم التداول اليوم وما يكشفه عن نوايا السوق]
📌 Put/Call Ratio: [تقدير النسبة ودلالتها Bullish أم Bearish]
📌 Premium Put/Call Ratio: [هل الكولز أم البوتس تدفع بريميوم أعلى]
📌 Open Interest Profile:
[أين تتمركز أكبر كميات OI — عند أي سترايكات — وتأثير ذلك]

الحكم النهائي: [توجه المؤسسات Bullish أم Bearish حسب الـ OI]

━━━━━━━━━━━━━━━━━━━━━━━━━━
4️⃣ التسعير والاستراتيجيات (Pricing & Strategy)

📌 Max Pain المُقدَّر: {max_pain_est}$
التفسير: [لماذا يميل السعر نحو هذا المستوى عند انتهاء الصلاحية]

📌 Breakeven Points:
▪ Call Breakeven: {breakeven_c}$
▪ Put Breakeven: {breakeven_p}$
التأثير: [ماذا يعني هذا للمضارب الذي يريد شراء Calls أو Puts الآن]

📌 Black-Scholes تقدير البريميوم:
▪ Call ATM عند {r1}$: [تقدير البريميوم]
▪ Put ATM عند {s1}$: [تقدير البريميوم]

📌 Payoff Analysis:
[تحليل الربح/الخسارة المتوقع لكل استراتيجية في السيناريوهات المختلفة]

الحكم النهائي: [توصية التسعير]

━━━━━━━━━━━━━━━━━━━━━━━━━━
5️⃣ تمركز المؤسسات (Institutional Sentiment)

📌 Put/Call Skew: [هل المؤسسات تشتري حماية أم ترهن على الصعود]
📌 Dealer Positioning: [هل الـ Dealers يحتاجون لشراء أم بيع لتغطية Gamma]
📌 Gamma Exposure (GEX): [حساب GEX التقديري وتأثيره على تثبيت السعر]
📌 Delta Exposure (DEX): [صافي الانكشاف الدلتوي للمؤسسات]
📌 COT Report (CFTC): [تمركزات المضاربين المؤسساتيين في الذهب]

الحكم النهائي على تمركزات المؤسسات: [Bullish أم Bearish أم Neutral]

━━━━━━━━━━━━━━━━━━━━━━━━━━
6️⃣ استراتيجيات الأوبشن الموصى بها اليوم

بناءً على IV={iv_estimate}% و السعر {gold}$:

🟢 استراتيجيات Bullish:
▪ Bull Call Spread: دخول عند {s1}$ — هدف {r1}$
▪ Covered Call: [متى تستخدمها الآن]
▪ Protective Put: [مستوى الحماية الأمثل]

🔴 استراتيجيات Bearish:
▪ Bear Put Spread: دخول عند {r1}$ — هدف {s1}$
▪ [استراتيجية أخرى مناسبة]

⚖️ استراتيجيات محايدة (Neutral):
▪ Straddle عند {max_pain_est}$: [تحليل الربحية]
▪ Strangle بين {s1}$ و{r1}$: [متى يربح]
▪ Iron Condor بين {s2}$-{s1}$ و{r1}$-{r2}$: [تفاصيل]
▪ Butterfly عند {max_pain_est}$: [شرح مختصر]
▪ Calendar Spread: [متى يكون مفيداً في الوضع الحالي]

🛡️ التحوط بالعقود الآجلة (Hedging):
[كيف تستخدم العقود الآجلة لتغطية مركز الأوبشن الحالي]

الحكم النهائي على الاستراتيجيات: [الاستراتيجية الأمثل لهذا اليوم ولماذا]

━━━━━━━━━━━━━━━━━━━━━━━━━━
7️⃣ الأدوات المتقدمة

📌 IV Rank: {iv_rank} — [هل الآن وقت الشراء أم البيع للأوبشن]
📌 IV Percentile: [موضع IV الحالي مقارنة بآخر سنة]
📌 Delta Neutral Analysis: [كيف تبني مركزاً محايداً الآن]
📌 Theta Scalping: [هل يربح بائع الأوبشن منها الآن؟]
📌 Arbitrage Opportunities: [هل توجد فرص تحكيم بين الفوري والآجل]
📌 Option Settlement: [تفاصيل التسوية والانتهاء القادم]

━━━━━━━━━━━━━━━━━━━━━━━━━━
🏆 الخلاصة النهائية الشاملة (Options Master View)

📊 توجه الأوبشن الكلي: [Bullish / Bearish / Neutral + نسبة الثقة %]
📌 المستويات الحاسمة من الأوبشن:
▪ Max Pain: {max_pain_est}$ — [تأثيره على حركة السعر قبل الانتهاء]
▪ Gamma Wall (دعم): {s1}$ | (مقاومة): {r1}$
▪ نطاق اليوم المتوقع من الأوبشن: {daily_low}$ - {daily_high}$

🎯 الحكم النهائي للتداول:
[فقرة من 3-4 أسطر تجمع كل ما سبق في قرار استراتيجي واحد واضح للمتداول المؤسساتي: ماذا يفعل الآن؟ أين يدخل؟ أين يخرج؟ وما هي المخاطر الرئيسية؟]

تحذير صارم: لا تختصر أي قسم، لا تحذف أي عنوان، لا تضف ديباجات، اعمل بتحليل عميق ومدروس لكل نقطة."""

    for model_name in GROQ_MODELS:
        try:
            resp = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": MASTER_SYSTEM_PROMPT + "أنت كبير محللي المشتقات في مكتب تداول مؤسساتي. التزم بالهيكل حرفياً وبأعلى جودة كمية ممكنة."},
                    {"role": "user", "content": prompt}
                ],
                model=model_name,
                temperature=0.12,
                max_tokens=3000
            )
            return resp.choices[0].message.content
        except Exception as e:
            if "429" in str(e) or "rate_limit" in str(e).lower():
                log.warning(f"⚠️ [T13] {model_name} — 429, انتقال للتالي...")
                time.sleep(15)
                continue
            log.error(f"❌ [T13] {model_name}: {e}")
    return ""


# ══════════════════════════════════════════════════
#  قوالب الفوري الخاصة S1-S12 — رياضية 100% — صفر AI
# ══════════════════════════════════════════════════

def _s_nums(d):
    """مساعد: يرجع كل الارقام الاساسية مع ضمان عدم وجود اصفار او None"""
    gold  = float(d.get('gold', 0) or 0)
    atr   = float(d.get('atr', 0) or 0) or 50.0
    pivot = float(d.get('pivot', 0) or 0) or gold
    rsi   = float(d.get('rsi', 50) or 50)
    macd  = float(d.get('macd', 0) or 0)
    r1 = float(d.get('r1', 0) or 0) or round(pivot + atr * 0.9, 2)
    r2 = float(d.get('r2', 0) or 0) or round(pivot + atr * 1.8, 2)
    r3 = float(d.get('r3', 0) or 0) or round(pivot + atr * 2.7, 2)
    s1 = float(d.get('s1', 0) or 0) or round(pivot - atr * 0.9, 2)
    s2 = float(d.get('s2', 0) or 0) or round(pivot - atr * 1.8, 2)
    s3 = float(d.get('s3', 0) or 0) or round(pivot - atr * 2.7, 2)
    swing_h = float(d.get('swing_high', 0) or 0) or r2
    swing_l = float(d.get('swing_low',  0) or 0) or s2
    return dict(gold=gold, atr=atr, pivot=pivot, rsi=rsi, macd=macd,
                r1=r1, r2=r2, r3=r3, s1=s1, s2=s2, s3=s3,
                swing_h=swing_h, swing_l=swing_l)


def _s_trades(d, n):
    """مساعد: يرجع الصفقات من adv_trades او يحسبها رياضيا"""
    adv  = d.get('adv_trades', {}) or {}
    nums = _s_nums(d)
    g, a, pv = nums['gold'], nums['atr'], nums['pivot']
    r1, r2 = nums['r1'], nums['r2']
    s1, s2 = nums['s1'], nums['s2']
    sh, sl = nums['swing_h'], nums['swing_l']

    if n == 'scalp_buy':
        t = adv.get('scalp_buy')
        if not t:
            ent = round(s1 + (pv - s1) * 0.25, 2)
            slv = round(ent - a * 0.4, 2)
            t = {'entry': ent, 'sl': slv, 'risk': round(ent - slv, 2),
                 't1': round(ent + a * 0.45, 2), 't2': round(pv, 2), 't3': round(r1, 2)}
    elif n == 'scalp_sell':
        t = adv.get('scalp_sell')
        if not t:
            ent = round(r1 - (r1 - pv) * 0.25, 2)
            slv = round(ent + a * 0.4, 2)
            t = {'entry': ent, 'sl': slv, 'risk': round(slv - ent, 2),
                 't1': round(ent - a * 0.45, 2), 't2': round(pv, 2), 't3': round(s1, 2)}
    elif n == 'swing_buy':
        t = adv.get('swing_buy') or adv.get('long_swing_buy')
        if not t:
            ent = round(s2, 2)
            slv = round(s2 - a * 0.5, 2)
            t = {'entry': ent, 'sl': slv, 'risk': round(ent - slv, 2),
                 't1': round(s1, 2), 't2': round(pv, 2), 't3': round(r1, 2)}
    elif n == 'swing_sell':
        t = adv.get('swing_sell') or adv.get('long_swing_sell')
        if not t:
            ent = round(r2, 2)
            slv = round(r2 + a * 0.5, 2)
            t = {'entry': ent, 'sl': slv, 'risk': round(slv - ent, 2),
                 't1': round(r1, 2), 't2': round(pv, 2), 't3': round(s1, 2)}
    elif n == 'rev_buy':
        t = adv.get('rev_buy')
        if not t:
            ent = round(sl + a * 0.3, 2)
            slv = round(sl - a * 0.2, 2)
            t = {'entry': ent, 'sl': slv, 'risk': round(ent - slv, 2),
                 't1': round(ent + a * 0.5, 2), 't2': round(pv, 2), 't3': round(r1, 2)}
    elif n == 'rev_sell':
        t = adv.get('rev_sell')
        if not t:
            ent = round(sh - a * 0.3, 2)
            slv = round(sh + a * 0.2, 2)
            t = {'entry': ent, 'sl': slv, 'risk': round(slv - ent, 2),
                 't1': round(ent - a * 0.5, 2), 't2': round(pv, 2), 't3': round(s1, 2)}
    elif n == 'high_lot_buy':
        t = adv.get('high_lot_buy')
        if not t:
            fib   = d.get('fib', {}) or {}
            ent   = float(fib.get('61.8%', 0) or 0) or s2
            slv   = round(ent - a * 0.25, 2)
            t = {'entry': round(ent, 2), 'sl': slv, 'risk': round(ent - slv, 2),
                 't1': round(fib.get('50.0%', pv) or pv, 2),
                 't2': round(fib.get('38.2%', r1) or r1, 2),
                 't3': round(fib.get('23.6%', r2) or r2, 2)}
    elif n == 'high_lot_sell':
        t = adv.get('high_lot_sell')
        if not t:
            fib   = d.get('fib', {}) or {}
            ent   = float(fib.get('23.6%', 0) or 0) or r2
            slv   = round(ent + a * 0.25, 2)
            t = {'entry': round(ent, 2), 'sl': slv, 'risk': round(slv - ent, 2),
                 't1': round(fib.get('38.2%', r1) or r1, 2),
                 't2': round(fib.get('50.0%', pv) or pv, 2),
                 't3': round(fib.get('61.8%', s1) or s1, 2)}
    else:
        t = {}
    return t or {}


def _build_spot_s1(d: dict) -> str:
    """1/12 - ملخص السوق والفيبوناتشي"""
    nums   = _s_nums(d)
    gold, atr, pivot = nums['gold'], nums['atr'], nums['pivot']
    rsi, macd = nums['rsi'], nums['macd']
    r1, r2, s1, s2 = nums['r1'], nums['r2'], nums['s1'], nums['s2']
    sh, sl = nums['swing_h'], nums['swing_l']
    fib = d.get('fib', {}) or {}
    ctx = d.get('hist_ctx', {}) or {}

    f50  = float(fib.get('50.0%', 0) or 0) or pivot
    f618 = float(fib.get('61.8%', 0) or 0) or s1
    f382 = float(fib.get('38.2%', 0) or 0) or r1

    if gold < f618:
        pos_note = f"الاسعار تقع تحت مستوى 61.8% من فيبوناتشي ({f618:.2f}$)، مما يشير الى تصحيح عميق."
    elif gold < f50:
        pos_note = f"الاسعار تقع تحت مستوى 50.0% من فيبوناتشي ({f50:.2f}$)، مما يشير الى طور تصحيح."
    elif gold < f382:
        pos_note = f"الاسعار اقتربت من مستوى 38.2% ({f382:.2f}$)، مما يشير الى استمرار الزخم الصعودي."
    else:
        pos_note = f"الاسعار فوق مستوى 38.2% ({f382:.2f}$)، مما يشير الى زخم صعودي قوي."

    if rsi < 30:
        rsi_note = f"مؤشر RSI عند {rsi:.2f} يشير الى تشبع بيعي حاد — فرصة ارتداد صعودي محتملة. 💡"
        recom = f"يمكن النظر في فرصة شراء عند {s1:.2f}$ مع وقف اسفل {s2:.2f}$. ⏰"
    elif rsi > 70:
        rsi_note = f"مؤشر RSI عند {rsi:.2f} يشير الى تشبع شرائي — احتمالية انعكاس هبوطي. 💡"
        recom = f"يمكن النظر في فرصة بيع عند {r1:.2f}$ مع وقف فوق {r2:.2f}$. ⏰"
    else:
        rsi_note = f"مؤشر RSI عند {rsi:.2f} في المنطقة المحايدة — انتظار كسر واضح للاتجاه. 💡"
        recom = f"انتظار تاكيد الاتجاه: كسر {r1:.2f}$ صعودا، او كسر {s1:.2f}$ هبوطا. ⏰"

    macd_note = f"MACD عند {macd:.4f} {'سلبي — ضغط بيعي' if macd < 0 else 'ايجابي — زخم صعودي'}."

    fib_lines = "\n".join(
        f"* {k}: **{v}** {'🔝' if k in ('0.0%', '100%') else '🔜'}"
        for k, v in fib.items()
    ) if fib else f"* محسوب من ATR: دعم {s1:.2f}$ | مقاومة {r1:.2f}$"

    chg1d = ctx.get('chg_1d', 0) or 0
    pct1d = ctx.get('pct_1d', 0) or 0
    chg7d = ctx.get('chg_7d', 0) or 0
    pct7d = ctx.get('pct_7d', 0) or 0

    return (
        "### ملخص السوق 📊\n"
        f"السعر الحالي: **{gold:.2f}** 💰\n"
        f"مؤشر RSI: **{rsi:.2f}** 📈\n"
        f"مؤشر MACD: **{macd:.4f}** 📉\n"
        f"مؤشر ATR: **{atr:.2f}** 📊\n"
        f"التغير اليومي: {chg1d:+.2f}$ ({pct1d:+.2f}%) | اسبوعي: {chg7d:+.2f}$ ({pct7d:+.2f}%)\n"
        f"اعلى النطاق اليومي: **{sh:.2f}$** | ادنى النطاق: **{sl:.2f}$**\n\n"
        "### مستويات فيبوناتشي 📐\n"
        f"{fib_lines}\n\n"
        "### الدعم والمقاومة 📍\n"
        f"* مقاومة 1 (R1): **{r1:.2f}$** | مقاومة 2 (R2): **{r2:.2f}$**\n"
        f"* دعم 1 (S1): **{s1:.2f}$** | دعم 2 (S2): **{s2:.2f}$**\n"
        f"* نقطة المحور: **{pivot:.2f}$**\n\n"
        "### تحليل السوق 📊\n"
        f"{pos_note} {rsi_note} {macd_note}\n\n"
        "### التوصيات 📝\n"
        f"{recom}\n\n"
        "### ملاحظات 📝\n"
        "* هذا التقرير خاص بسوق الفوري (Spot - XAU/USD).\n"
        "* يجب الحذر عند اتخاذ اي اجراء في السوق وادارة المخاطر بشكل صارم. 🚨"
    )


def _build_spot_s2(d: dict) -> str:
    """2/12 - تحليل الاطارات الزمنية"""
    nums = _s_nums(d)
    gold, atr, pivot = nums['gold'], nums['atr'], nums['pivot']
    rsi, macd = nums['rsi'], nums['macd']
    r1, r2, s1, s2 = nums['r1'], nums['r2'], nums['s1'], nums['s2']

    tf15 = d.get('tf_15m', {}) or {}
    tf_d = d.get('tf_daily', {}) or {}
    tf_w = d.get('tf_weekly', {}) or {}
    tf_m = d.get('tf_monthly', {}) or {}

    def bias_ar(tf):
        if not tf: return "محايد 🤔"
        b = str(tf.get('bias', ''))
        if 'صعودي' in b or 'bull' in b.lower(): return "صعودي ⬆️"
        if 'هبوطي' in b or 'bear' in b.lower(): return "هبوطي ⬇️"
        return "محايد 🤔"

    def tf_rsi(tf): return float(tf.get('rsi', rsi) or rsi) if tf else rsi

    rng_low  = round(pivot - atr * 0.5, 2)
    rng_high = round(pivot + atr * 0.5, 2)

    piv_d  = float(tf_d.get('pivot', 0) or 0) or pivot
    piv_w  = float(tf_w.get('pivot', 0) or 0) or round(pivot + atr * 0.5, 2)
    piv_mo = float(tf_m.get('pivot', 0) or 0) or round(pivot + atr * 1.5, 2)

    b15 = bias_ar(tf15); bd = bias_ar(tf_d); bw = bias_ar(tf_w); bm = bias_ar(tf_m)
    rsi15 = tf_rsi(tf15); rsid = tf_rsi(tf_d)

    pd = "تحت" if gold < piv_d else "فوق"
    pw = "تحت" if gold < piv_w else "فوق"
    pm = "تحت" if gold < piv_mo else "فوق"

    if gold < pivot:
        recom_buy  = f"انتظار ارتداد نحو {s1:.2f}$ للدخول شراء مع وقف {s2:.2f}$"
        recom_sell = f"البيع عند {pivot:.2f}$ مع وقف {r1:.2f}$، وهدف اول {s1:.2f}$"
    else:
        recom_buy  = f"الشراء عند {pivot:.2f}$ مع وقف {s1:.2f}$، وهدف اول {r1:.2f}$"
        recom_sell = f"انتظار الوصول الى {r1:.2f}$ للدخول بيعا مع وقف {r2:.2f}$"

    return (
        "### تحليل الاطارات الزمنية 🕒\n"
        "#### نظرة عامة على السوق 📊\n"
        f"السعر الحالي للذهب هو **{gold:.2f}**💰. مؤشر RSI يبلغ **{rsi:.2f}** 📈، "
        f"مما يشير الى ان السوق في حالة {'بيع' if rsi < 45 else 'شراء'}. "
        f"مؤشر MACD يبلغ **{macd:.4f}** 📉، مما يشير الى ان السوق في اتجاه {'هبوطي' if macd < 0 else 'صعودي'}.\n\n"
        "#### الاطارات الزمنية 🕒\n"
        f"* **15 دقيقة** ⏰: السعر في نطاق {rng_low:.2f}$ — {rng_high:.2f}$ 📊. RSI={rsi15:.1f}. الاتجاه: {b15}.\n"
        f"* **يومية** 📅: السعر يقع {pd} مستوى البيفوت {piv_d:.2f}$ 📊. RSI={rsid:.1f}. الاتجاه: {bd}.\n"
        f"* **اسبوعية** 📆: السعر يقع {pw} مستوى البيفوت {piv_w:.2f}$ 📊. الاتجاه: {bw}.\n"
        f"* **شهرية** 📆: السعر يقع {pm} مستوى البيفوت {piv_mo:.2f}$ 📊. الاتجاه: {bm}.\n\n"
        "#### الدعم والمقاومة 📍\n"
        f"* مقاومة 1: **{r1:.2f}$** | مقاومة 2: **{r2:.2f}$**\n"
        f"* دعم 1: **{s1:.2f}$** | دعم 2: **{s2:.2f}$**\n"
        f"* نقطة المحور: **{pivot:.2f}$**\n\n"
        "#### التوصيات 📝\n"
        f"* **شراء** 🛍️: {recom_buy}\n"
        f"* **بيع** 🚫: {recom_sell}\n\n"
        "#### المخاطر 🚨\n"
        f"* **مخاطر السوق** 📊: RSI {'في منطقة تشبع — مخاطر عالية' if rsi < 30 or rsi > 70 else 'في المنطقة المحايدة — مخاطر متوسطة'} 🚨.\n"
        f"* **ATR التقلب اليومي المتوقع**: {atr:.2f}$ (المدى المتوقع: {round(gold-atr,2)}$ — {round(gold+atr,2)}$) 📊\n\n"
        "#### الخلاصة 📝\n"
        f"السوق في حالة {'بيع 📉' if rsi < 45 else 'شراء 📈'}، والسعر يقع {pd} البيفوت {piv_d:.2f}$. "
        f"{recom_buy if gold >= pivot else recom_sell}. يجب ادارة المخاطر بشكل فعال 📊. 💡"
    )


def _build_spot_s3(d: dict) -> str:
    """3/12 - صفقات زيرو انعكاس"""
    nums = _s_nums(d)
    gold, atr, pivot = nums['gold'], nums['atr'], nums['pivot']
    rsi, macd = nums['rsi'], nums['macd']
    r1, r2, s1, s2 = nums['r1'], nums['r2'], nums['s1'], nums['s2']
    sh, sl = nums['swing_h'], nums['swing_l']
    fib = d.get('fib', {}) or {}

    rb = _s_trades(d, 'rev_buy')
    rs = _s_trades(d, 'rev_sell')

    fib_lines = "\n".join(f"  - {k}: {v}" for k, v in fib.items()) if fib else (
        f"  - دعم 1: {s1:.2f}$ | دعم 2: {s2:.2f}$\n"
        f"  - مقاومة 1: {r1:.2f}$ | مقاومة 2: {r2:.2f}$"
    )

    rsi_read = ('RSI في تشبع بيع — مرشح ارتداد صعودي قوي' if rsi < 30
                else 'RSI في تشبع شراء — مرشح انعكاس هبوطي قوي' if rsi > 70
                else f'RSI={rsi:.2f} في المنطقة المحايدة — انتظار تاكيد')
    macd_read = f'MACD={macd:.4f} {"سلبي — ضغط بيعي" if macd < 0 else "ايجابي — زخم صعودي"}'

    return (
        "### تحليل البيانات 📊\n"
        "نحن نتعامل مع بيانات السوق الفوري (Spot - XAU/USD) 📈.\n\n"
        "### بيانات السوق الحالية 📊\n"
        f"- السعر الحالي: **{gold:.2f}$** 💰\n"
        f"- RSI: **{rsi:.2f}** 📊 ({rsi_read})\n"
        f"- MACD: **{macd:.4f}** 📉 ({macd_read})\n"
        f"- ATR: **{atr:.2f}$** 📊 (المدى اليومي المتوقع)\n"
        "- فيبوناتشي:\n"
        f"{fib_lines}\n"
        f"- اعلى نطاق يومي (Swing H): **{sh:.2f}$** 📈\n"
        f"- ادنى نطاق يومي (Swing L): **{sl:.2f}$** 📉\n"
        f"- محور الدوران: **{pivot:.2f}$** 🔄\n"
        f"- مقاومة R1: **{r1:.2f}$** | مقاومة R2: **{r2:.2f}$**\n"
        f"- دعم S1: **{s1:.2f}$** | دعم S2: **{s2:.2f}$**\n\n"
        "### استراتيجيات التداول 📈\n"
        "استراتيجية زيرو انعكاس تستهدف نقاط الانعكاس عند الدعم والمقاومة الحاسمة.\n\n"
        "### تحليل الاستراتيجيات 📊\n"
        f"بناء على البيانات الحالية، {rsi_read}، و{macd_read}.\n\n"
        "### استراتيجية زيرو انعكاس 🔄\n"
        f"* **شراء عند الانعكاس** — الدخول: **{rb.get('entry',s1):.2f}$** | وقف: **{rb.get('sl',s2):.2f}$** | مخاطر: **{rb.get('risk',atr*0.3):.2f}$**\n"
        f"  الاهداف: **{rb.get('t1',pivot):.2f}$** | **{rb.get('t2',r1):.2f}$** | **{rb.get('t3',r2):.2f}$** 📈\n\n"
        f"* **بيع عند الانعكاس** — الدخول: **{rs.get('entry',r1):.2f}$** | وقف: **{rs.get('sl',r2):.2f}$** | مخاطر: **{rs.get('risk',atr*0.3):.2f}$**\n"
        f"  الاهداف: **{rs.get('t1',pivot):.2f}$** | **{rs.get('t2',s1):.2f}$** | **{rs.get('t3',s2):.2f}$** 📉\n\n"
        "### خلاصة 📝\n"
        "يجب الحذر عند تطبيق استراتيجيات الانعكاس في السوق الفوري 📊. "
        "الانعكاس يحتاج تاكيدا بمؤشرات متعددة (RSI + MACD + شمعة انعكاسية) قبل الدخول 📈."
    )


def _build_spot_s4(d: dict) -> str:
    """4/12 - صفقات السكالبينج"""
    nums = _s_nums(d)
    gold, atr, pivot = nums['gold'], nums['atr'], nums['pivot']
    rsi, macd = nums['rsi'], nums['macd']
    r1, r2, s1, s2 = nums['r1'], nums['r2'], nums['s1'], nums['s2']
    sh, sl = nums['swing_h'], nums['swing_l']
    fib = d.get('fib', {}) or {}
    fib_sup = float(fib.get('100%', 0) or 0) or s2

    sb = _s_trades(d, 'scalp_buy')
    ss = _s_trades(d, 'scalp_sell')

    fib_lines = "\n".join(f" + {k}: {v}" for k, v in fib.items()) if fib else (
        f" + R1: {r1:.2f}$ | R2: {r2:.2f}$\n + S1: {s1:.2f}$ | S2: {s2:.2f}$"
    )

    rsi_zone = ("تشبع بيعي 📉" if rsi < 30 else "منطقة بيع 📉" if rsi < 45
                else "تشبع شرائي 📈" if rsi > 70 else "منطقة شراء 📈")

    return (
        "### تحليل السوق الفوري 📊\n"
        "#### بيانات السوق الحالية 📈\n"
        f"* السعر الحالي: **{gold:.2f}$** 💰\n"
        f"* اعلى النطاق اليومي: **{sh:.2f}$** 📈\n"
        f"* ادنى النطاق اليومي: **{sl:.2f}$** 📉\n"
        f"* نقطة المحور: **{pivot:.2f}$** 📍\n"
        f"* RSI: **{rsi:.2f}** 📊 ({rsi_zone})\n"
        f"* MACD: **{macd:.4f}** 📉\n"
        f"* ATR: **{atr:.2f}$** 📊\n"
        "* Fib:\n"
        f"{fib_lines}\n\n"
        "#### صفقات السكالبينج 🏹\n"
        f"* **شراء** 🛍️\n"
        f" + سعر الدخول: **{sb.get('entry',0):.2f}$**\n"
        f" + وقف الخسارة: **{sb.get('sl',0):.2f}$**\n"
        f" + المخاطرة: **{sb.get('risk',0):.2f}$**\n"
        f" + الاهداف:\n"
        f"    - الاول: **{sb.get('t1',0):.2f}$**\n"
        f"    - الثاني: **{sb.get('t2',0):.2f}$**\n"
        f"    - الثالث: **{sb.get('t3',0):.2f}$**\n\n"
        f"* **بيع** 🛍️\n"
        f" + سعر الدخول: **{ss.get('entry',0):.2f}$**\n"
        f" + وقف الخسارة: **{ss.get('sl',0):.2f}$**\n"
        f" + المخاطرة: **{ss.get('risk',0):.2f}$**\n"
        f" + الاهداف:\n"
        f"    - الاول: **{ss.get('t1',0):.2f}$**\n"
        f"    - الثاني: **{ss.get('t2',0):.2f}$**\n"
        f"    - الثالث: **{ss.get('t3',0):.2f}$**\n\n"
        "#### تحليل الارقام 📊\n"
        f"* RSI عند **{rsi:.2f}** — {rsi_zone}\n"
        f"* MACD عند **{macd:.4f}** — اتجاه {'هبوطي 📉' if macd < 0 else 'صعودي 📈'}\n"
        f"* ATR عند **{atr:.2f}$** — تقلبات {'عالية' if atr > 50 else 'منخفضة'} 📊\n"
        f"* اقرب دعم قوي: **{fib_sup:.2f}$** 📍\n\n"
        "#### استنتاج 📝\n"
        f"* السوق في اتجاه {'هبوطي' if macd < 0 else 'صعودي'}، مع RSI في {rsi_zone}\n"
        f"* **فرصة شراء سكالبينج**: دخول {sb.get('entry',0):.2f}$، هدف {sb.get('t1',0):.2f}$ (+{round(sb.get('t1',0)-sb.get('entry',0),2)}$) 🛍️\n"
        f"* **فرصة بيع سكالبينج**: دخول {ss.get('entry',0):.2f}$، هدف {ss.get('t1',0):.2f}$ (-{round(ss.get('entry',0)-ss.get('t1',0),2)}$) 🛍️\n"
    )


def _build_spot_s5(d: dict) -> str:
    """5/12 - صفقات السوينج"""
    nums = _s_nums(d)
    gold, atr, pivot = nums['gold'], nums['atr'], nums['pivot']
    rsi, macd = nums['rsi'], nums['macd']
    r1, r2, s1, s2 = nums['r1'], nums['r2'], nums['s1'], nums['s2']

    sw_b = _s_trades(d, 'swing_buy')
    sw_s = _s_trades(d, 'swing_sell')

    rratio_b = round((sw_b.get('t2', r1) - sw_b.get('entry', s2)) / max(sw_b.get('risk', atr), 0.01), 1)
    rratio_s = round((sw_s.get('entry', r2) - sw_s.get('t2', pivot)) / max(sw_s.get('risk', atr), 0.01), 1)

    trend      = "هبوطية" if rsi < 45 else "صعودية"
    rsi_note   = ('في تشبع بيع — فرصة شراء سوينج قوية' if rsi < 35
                  else 'في تشبع شراء — فرصة بيع سوينج قوية' if rsi > 65
                  else 'في المنطقة المحايدة — انتظار تاكيد الاتجاه')

    return (
        "### صفقات السوينج 🌊\n"
        "#### نظرة عامة على السوق 📊\n"
        f"سعر الذهب الحالي **{gold:.2f}$**، مؤشر RSI يبلغ **{rsi:.2f}**، MACD يبلغ **{macd:.4f}**. "
        f"السوق في حالة {trend}. RSI {rsi_note}.\n\n"
        "#### صفقات السوينج 🌊\n"
        f"* **صفقة شراء سوينج 🛍️**:\n"
        f" + نقطة الدخول: **{sw_b.get('entry',0):.2f}$**\n"
        f" + نقطة وقف الخسارة: **{sw_b.get('sl',0):.2f}$**\n"
        f" + المخاطرة: **{sw_b.get('risk',0):.2f}$**\n"
        f" + نسبة المكسب للمخاطرة (R:R): **{rratio_b}:1**\n"
        f" + الاهداف:\n"
        f"    - الهدف الاول: **{sw_b.get('t1',0):.2f}$**\n"
        f"    - الهدف الثاني: **{sw_b.get('t2',0):.2f}$**\n"
        f"    - الهدف الثالث: **{sw_b.get('t3',0):.2f}$**\n\n"
        f"* **صفقة بيع سوينج 🚫**:\n"
        f" + نقطة الدخول: **{sw_s.get('entry',0):.2f}$**\n"
        f" + نقطة وقف الخسارة: **{sw_s.get('sl',0):.2f}$**\n"
        f" + المخاطرة: **{sw_s.get('risk',0):.2f}$**\n"
        f" + نسبة المكسب للمخاطرة (R:R): **{rratio_s}:1**\n"
        f" + الاهداف:\n"
        f"    - الهدف الاول: **{sw_s.get('t1',0):.2f}$**\n"
        f"    - الهدف الثاني: **{sw_s.get('t2',0):.2f}$**\n"
        f"    - الهدف الثالث: **{sw_s.get('t3',0):.2f}$**\n\n"
        "#### تحليل الارقام 📊\n"
        f"السوق في حالة {trend}. "
        f"RSI {rsi_note}. "
        f"MACD {'سلبي — الزخم هبوطي' if macd < 0 else 'ايجابي — الزخم صعودي'}.\n"
        f"مستويات الدعم الرئيسية: {s1:.2f}$ و{s2:.2f}$.\n"
        f"مستويات المقاومة الرئيسية: {r1:.2f}$ و{r2:.2f}$.\n\n"
        "#### خلاصة القول 📝\n"
        f"الصفقة الافضل حاليا: {'شراء سوينج عند ' + str(round(sw_b.get('entry',s2),2)) + '$ بهدف ' + str(round(sw_b.get('t2',r1),2)) + '$' if rsi < 45 else 'بيع سوينج عند ' + str(round(sw_s.get('entry',r2),2)) + '$ بهدف ' + str(round(sw_s.get('t2',pivot),2)) + '$'}. "
        "يجب ادارة المخاطر بشكل صارم واستخدام وقف الخسارة دائما. 📈💰"
    )


def _build_spot_s6(d: dict) -> str:
    """6/12 - صفقات اللوت العالي"""
    nums = _s_nums(d)
    gold, atr, pivot = nums['gold'], nums['atr'], nums['pivot']
    rsi, macd = nums['rsi'], nums['macd']
    r1, r2, s1, s2 = nums['r1'], nums['r2'], nums['s1'], nums['s2']
    sh, sl = nums['swing_h'], nums['swing_l']
    fib = d.get('fib', {}) or {}

    hlb = _s_trades(d, 'high_lot_buy')
    hls = _s_trades(d, 'high_lot_sell')

    f236 = float(fib.get('23.6%', 0) or 0) or r2
    f382 = float(fib.get('38.2%', 0) or 0) or r1
    f50  = float(fib.get('50.0%', 0) or 0) or pivot
    f618 = float(fib.get('61.8%', 0) or 0) or s1
    f786 = float(fib.get('78.6%', 0) or 0) or s2

    fib_block = "\n".join(f"  - **{k}:** {v}" for k, v in fib.items()) if fib else (
        f"  - 23.6%: {f236:.2f}$ | 38.2%: {f382:.2f}$\n  - 50%: {f50:.2f}$ | 61.8%: {f618:.2f}$"
    )

    # حساب الوقف والنسبة
    buy_sl_tight = round(hlb.get('entry', f618) - atr * 0.2, 2)
    sell_sl_tight = round(hls.get('entry', f236) + atr * 0.2, 2)

    return (
        "### تحليل الصفقة 📊\n"
        "الدخول من مستويات فيبوناتشي الدقيقة يتيح وقف خسارة ضيق جداً، مما يسمح باستخدام لوت اعلى.\n\n"
        "### بيانات السوق 📈\n"
        f"- **السعر الحالي:** {gold:.2f}$\n"
        f"- **اعلى النطاق (Swing H):** {sh:.2f}$\n"
        f"- **ادنى النطاق (Swing L):** {sl:.2f}$\n"
        f"- **نقطة المحور:** {pivot:.2f}$\n"
        f"- **RSI:** {rsi:.2f} 📉\n"
        f"- **MACD:** {macd:.4f} 📊\n"
        f"- **ATR:** {atr:.2f}$ 📊\n"
        "- **فيبوناتشي:**\n"
        f"{fib_block}\n\n"
        "### خيارات صفقات اللوت العالي 📊\n\n"
        f"**1. شراء لوت عالي من أقرب دعم** 📈\n"
        f" + الدخول: **{hlb.get('entry', f618):.2f}$**\n"
        f" + الوقف الضيق: **{buy_sl_tight:.2f}$** (فارق: {round(hlb.get('entry',f618) - buy_sl_tight, 2)}$)\n"
        f" + الهدف 1: **{hlb.get('t1', f50):.2f}$**\n"
        f" + الهدف 2: **{hlb.get('t2', f382):.2f}$**\n"
        f" + الهدف 3: **{hlb.get('t3', f236):.2f}$**\n\n"
        f"**2. بيع لوت عالي من أقرب مقاومة** 📉\n"
        f" + الدخول: **{hls.get('entry', f236):.2f}$**\n"
        f" + الوقف الضيق: **{sell_sl_tight:.2f}$** (فارق: {round(sell_sl_tight - hls.get('entry',f236), 2)}$)\n"
        f" + الهدف 1: **{hls.get('t1', f382):.2f}$**\n"
        f" + الهدف 2: **{hls.get('t2', f50):.2f}$**\n"
        f" + الهدف 3: **{hls.get('t3', f618):.2f}$**\n\n"
        "### تحليل الصفقات 📝\n"
        f"- **RSI:** {rsi:.2f} — السوق في منطقة {'بيع' if rsi < 45 else 'شراء'}.\n"
        f"- **MACD:** {macd:.4f} — اتجاه {'هبوطي' if macd < 0 else 'صعودي'}.\n"
        f"- **ATR:** {atr:.2f}$ — تقلبات {'عالية' if atr > 50 else 'منخفضة'}.\n\n"
        "### تحذيرات 🚨\n"
        "- اللوت العالي يتطلب انضباطا صارما في ادارة المخاطر.\n"
        "- الدخول يجب ان يكون عند مستويات فيبوناتشي فقط مع تاكيد.\n"
        "- لا تجازف باكثر من 0.5-1% من راس المال في صفقة واحدة.\n\n"
        "### خلاصة القول 📝\n"
        f"افضل فرصة للوت العالي {'شراء عند ' + str(f618) + '$ مع وقف ' + str(buy_sl_tight) + '$' if gold < pivot else 'بيع عند ' + str(f236) + '$ مع وقف ' + str(sell_sl_tight) + '$'}. "
        "الوقف الضيق يتيح نسبة مخاطرة ممتازة مقارنة بالهدف. 📈"
    )


def _build_spot_s7(d: dict) -> str:
    """7/12 - التحليل الفني والزخم"""
    nums = _s_nums(d)
    gold, atr, pivot = nums['gold'], nums['atr'], nums['pivot']
    rsi, macd = nums['rsi'], nums['macd']
    r1, r2, s1, s2 = nums['r1'], nums['r2'], nums['s1'], nums['s2']
    sh, sl = nums['swing_h'], nums['swing_l']
    fib = d.get('fib', {}) or {}

    ema20  = float(d.get('ema20', 0) or 0) or round(gold - atr * 0.3, 2)
    ema50  = float(d.get('ema50', 0) or 0) or round(gold - atr * 0.8, 2)
    ema200 = float(d.get('ema200', 0) or 0) or round(gold - atr * 2.0, 2)
    adx    = float(d.get('adx', 0) or 0) or 20.0
    di_p   = float(d.get('di_plus', 0) or 0) or 20.0
    di_m   = float(d.get('di_minus', 0) or 0) or 20.0
    stoch  = float(d.get('stoch_k', 0) or 0) or 50.0
    bb_up  = float(d.get('bb_upper', 0) or 0) or round(gold + atr, 2)
    bb_lo  = float(d.get('bb_lower', 0) or 0) or round(gold - atr, 2)
    cci    = float(d.get('cci', 0) or 0) or 0.0
    wr     = float(d.get('williams_r', 0) or 0) or -50.0

    if ema20 > ema50 > ema200: ema_note = "توافق صعودي كامل (20>50>200) ✅"
    elif ema20 < ema50 < ema200: ema_note = "توافق هبوطي كامل (20<50<200) ✅"
    else: ema_note = "تقاطع جزئي — مرحلة تحول"

    adx_note = (f"ترند {'صعودي قوي' if di_p > di_m else 'هبوطي قوي'} (ADX>{adx:.0f})"
                if adx > 25 else "لا ترند واضح — تذبذب عرضي")

    sb = _s_trades(d, 'scalp_buy')
    ss = _s_trades(d, 'scalp_sell')

    fib_block = "\n".join(f"  - **{k}**: {v}" for k, v in fib.items()) if fib else (
        f"  - R1: {r1:.2f}$ | R2: {r2:.2f}$\n  - S1: {s1:.2f}$ | S2: {s2:.2f}$"
    )

    return (
        "### تحليل فني وزخم للذهب 📊\n"
        "#### نظرة عامة على السوق 🌐\n"
        f"- السعر الحالي: **{gold:.2f}$** 💰\n"
        f"- اعلى النطاق اليومي: **{sh:.2f}$** ⬆️\n"
        f"- ادنى النطاق اليومي: **{sl:.2f}$** ⬇️\n"
        f"- مؤشر RSI: **{rsi:.2f}** 📉\n"
        f"- مؤشر MACD: **{macd:.4f}** 📊\n"
        f"- Stochastic K: **{stoch:.2f}** 📈\n"
        f"- CCI: **{cci:.2f}** 📊\n"
        f"- Williams %R: **{wr:.2f}** 📉\n\n"
        "#### المتوسطات المتحركة 📊\n"
        f"- EMA20: **{ema20:.2f}$** | EMA50: **{ema50:.2f}$** | EMA200: **{ema200:.2f}$**\n"
        f"- التقييم: {ema_note}\n\n"
        "#### بولنجر باندز 📊\n"
        f"- الحد العلوي: **{bb_up:.2f}$** | الحد السفلي: **{bb_lo:.2f}$**\n"
        f"- السعر {'قريب من الحد العلوي — مقاومة' if gold > (bb_up + bb_lo) / 2 else 'قريب من الحد السفلي — دعم'}\n\n"
        "#### مؤشر ADX والاتجاه 📈\n"
        f"- ADX: **{adx:.2f}** | DI+: **{di_p:.2f}** | DI-: **{di_m:.2f}**\n"
        f"- التقييم: {adx_note}\n\n"
        "#### تحليل الفيبوناتشي 🌈\n"
        f"{fib_block}\n\n"
        "#### استراتيجيات التداول 📈\n"
        f"- **شراء**: دخول **{sb.get('entry',0):.2f}$** | وقف **{sb.get('sl',0):.2f}$** | هدف **{sb.get('t1',0):.2f}$**، **{sb.get('t2',0):.2f}$**، **{sb.get('t3',0):.2f}$** 🎯\n"
        f"- **بيع**: دخول **{ss.get('entry',0):.2f}$** | وقف **{ss.get('sl',0):.2f}$** | هدف **{ss.get('t1',0):.2f}$**، **{ss.get('t2',0):.2f}$**، **{ss.get('t3',0):.2f}$** 🎯\n\n"
        "#### تحليل الزخم 💪\n"
        f"- ATR: **{atr:.2f}$** (المدى اليومي المتوقع — تقلبات {'عالية' if atr > 60 else 'متوسطة' if atr > 30 else 'منخفضة'})\n\n"
        "#### استنتاج 📝\n"
        f"- السوق في وضعية {'هبوطية' if rsi < 45 else 'صعودية'} مع RSI={rsi:.2f}.\n"
        f"- المتوسطات المتحركة تشير الى: {ema_note}\n"
        "- مستويات الفيبوناتشي توفر دعم ومقاومة محتملة.\n\n"
        "تذكر دائما ان التداول يحمل مخاطر، وينبغي ان تكون على دراية تامة بالسوق قبل اتخاذ اي قرار. 🚨"
    )


def _build_spot_s8(d: dict) -> str:
    """8/12 - الاقتصاد الكلي"""
    nums = _s_nums(d)
    gold, atr, pivot = nums['gold'], nums['atr'], nums['pivot']
    rsi, macd = nums['rsi'], nums['macd']
    r1, r2, s1, s2 = nums['r1'], nums['r2'], nums['s1'], nums['s2']
    sh, sl = nums['swing_h'], nums['swing_l']
    fib = d.get('fib', {}) or {}

    interest  = float(d.get('interest_rate', 5.25) or 5.25)
    inflation = float(d.get('inflation_est', 3.5) or 3.5)
    ry        = float(d.get('real_yield', 0) or 0) or round(interest - inflation, 2)
    dxy_p     = float(d.get('dxy_p', 100) or 100)
    dxy_pct   = float(d.get('dxy_pct', 0) or 0)
    fx        = d.get('fx_sorted', []) or []

    sb = _s_trades(d, 'scalp_buy')
    ss = _s_trades(d, 'scalp_sell')

    fib_block = "\n".join(f"- {k}: {v}" for k, v in fib.items()) if fib else (
        f"- R1: {r1:.2f}$ | R2: {r2:.2f}$\n- S1: {s1:.2f}$ | S2: {s2:.2f}$"
    )
    fx_block = "\n".join(f"- {sym}: {pct:+.4f}%" for sym, pct in fx[:8]) if fx else (
        "- بيانات العملات غير متاحة حاليا"
    )

    macro_effect = ("سلبي على الذهب — فائدة عالية وعائد حقيقي موجب يضغط على الذهب"
                    if ry > 1 else
                    "ايجابي على الذهب — عائد حقيقي سلبي يدعم الذهب كتحوط")

    return (
        "### تحليل الاقتصاد الكلي 📊\n"
        "#### نظرة عامة على السوق 🌐\n"
        f"- السعر الحالي: **{gold:.2f}$** 💰\n"
        f"- اعلى النطاق (Swing H): **{sh:.2f}$** ⬆️\n"
        f"- ادنى النطاق (Swing L): **{sl:.2f}$** ⬇️\n"
        f"- نقطة المحور: **{pivot:.2f}$**\n"
        f"- مؤشر RSI: **{rsi:.2f}** 📈\n"
        f"- مؤشر MACD: **{macd:.4f}** 📊\n"
        f"- مؤشر ATR: **{atr:.2f}$** 📊\n\n"
        "#### تحليل الفيبوناتشي 🌈\n"
        f"{fib_block}\n\n"
        "#### تحليل التداول (سكالبينج) 📈\n"
        f"- **شراء**: دخول **{sb.get('entry',0):.2f}$** | وقف **{sb.get('sl',0):.2f}$** | اهداف {sb.get('t1',0):.2f}$, {sb.get('t2',0):.2f}$, {sb.get('t3',0):.2f}$\n"
        f"- **بيع**: دخول **{ss.get('entry',0):.2f}$** | وقف **{ss.get('sl',0):.2f}$** | اهداف {ss.get('t1',0):.2f}$, {ss.get('t2',0):.2f}$, {ss.get('t3',0):.2f}$\n\n"
        "#### تحليل الاقتصاد الكلي 🌎\n"
        f"- معدل الفائدة: **{interest:.2f}%**\n"
        f"- معدل التضخم (CPI): **{inflation:.2f}%**\n"
        f"- العائد الحقيقي (Fائدة - CPI): **{ry:.2f}%**\n"
        f"- مؤشر الدولار (DXY): **{dxy_p:.4f}** ({dxy_pct:+.2f}%)\n"
        f"- التاثير الاجمالي: **{macro_effect}**\n\n"
        "#### تحليل العملات 💸\n"
        f"{fx_block}\n\n"
        "### خلاصة القول 📝\n"
        f"- السوق في حالة {'انخفاض' if macd < 0 else 'ارتفاع'} مع RSI={'منخفض' if rsi<45 else 'مرتفع'} وMACD={'سالب' if macd<0 else 'موجب'}.\n"
        f"- الوضع الاقتصادي: {macro_effect}.\n"
        "- هناك فرص لشراء عند مستويات الدعم وبيع عند مستويات المقاومة.\n"
        "- يجب مراعاة التحليل الفني والاقتصادي عند اتخاذ القرارات التداولية. 📊"
    )


def _build_spot_s9(d: dict) -> str:
    """9/12 - شهية المخاطرة"""
    nums = _s_nums(d)
    gold, atr, pivot = nums['gold'], nums['atr'], nums['pivot']
    rsi, macd = nums['rsi'], nums['macd']
    r1, r2, s1, s2 = nums['r1'], nums['r2'], nums['s1'], nums['s2']
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
    sb  = _s_trades(d, 'scalp_buy');  ss  = _s_trades(d, 'scalp_sell')
    swb = _s_trades(d, 'swing_buy');  sws = _s_trades(d, 'swing_sell')
    db  = adv.get('daily_buy') or {'entry': r1, 'sl': r2, 't1': pivot, 't2': s1, 't3': s2}
    ds  = adv.get('daily_sell') or {'entry': s1, 'sl': s2, 't1': pivot, 't2': r1, 't3': r2}
    wb  = adv.get('weekly_buy') or {'entry': s2, 'sl': round(s2-atr*0.5,2), 't1': s1, 't2': pivot, 't3': r1}
    ws  = adv.get('weekly_sell') or {'entry': r2, 'sl': round(r2+atr*0.5,2), 't1': r1, 't2': pivot, 't3': s1}

    score = 0
    if vix_p > 25: score -= 2
    elif vix_p < 18: score += 2
    if sp500 > 0.5: score += 1
    elif sp500 < -0.5: score -= 1
    if ry > 1.5: score -= 1
    risk_pct = max(30, min(80, 50 + score * 5))
    risk_label = "عالية" if risk_pct > 60 else "متوسطة" if risk_pct > 45 else "منخفضة"

    fib_block = "\n".join(f"  - **{k}:** {v}" for k, v in fib.items()) if fib else (
        f"  - R1: {r1:.2f}$ | R2: {r2:.2f}$\n  - S1: {s1:.2f}$ | S2: {s2:.2f}$"
    )
    fx_block = "\n".join(f"  - **{sym}:** {pct:+.4f}%" for sym, pct in fx[:8]) if fx else "  - بيانات العملات متاحة عند التريجر"

    return (
        "### شهية المخاطرة 📊\n"
        "#### نظرة عامة على السوق 🌐\n"
        f"- **سعر الذهب الحالي:** {gold:.2f}$ 💰\n"
        f"- **اعلى النطاق:** {sh:.2f}$ | **ادنى النطاق:** {sl:.2f}$\n"
        f"- **مؤشر RSI:** {rsi:.2f} 📊\n"
        f"- **مؤشر MACD:** {macd:.4f} 📉\n"
        f"- **مؤشر ATR:** {atr:.2f}$ 📊\n\n"
        "#### تحليل الفني 📈\n"
        "- **مستويات فيبوناتشي:**\n"
        f"{fib_block}\n"
        f"- **نقطة المحور:** {pivot:.2f}$ | **R1:** {r1:.2f}$ | **S1:** {s1:.2f}$\n\n"
        "#### تحليل الاساسي 📊\n"
        f"- **معدل التضخم:** {inflation:.2f}%\n"
        f"- **معدل الفائدة:** {interest:.2f}%\n"
        f"- **العائد الحقيقي:** {ry:.2f}%\n"
        f"- **VIX (مؤشر الخوف):** {vix_p:.2f} ({'مرتفع — تحوط' if vix_p > 25 else 'منخفض — جشع'})\n"
        f"- **S&P 500 اليومي:** {sp500:+.2f}%\n"
        f"- **مؤشر الدولار (DXY):** {dxy_p:.4f}\n"
        "- **قوة العملات:**\n"
        f"{fx_block}\n\n"
        "#### استراتيجيات التداول 📈\n"
        f"- **سكالبينج — شراء:** دخول {sb.get('entry',0):.2f}$، وقف {sb.get('sl',0):.2f}$، اهداف {sb.get('t1',0):.2f}$/{sb.get('t2',0):.2f}$/{sb.get('t3',0):.2f}$\n"
        f"- **سكالبينج — بيع:** دخول {ss.get('entry',0):.2f}$، وقف {ss.get('sl',0):.2f}$، اهداف {ss.get('t1',0):.2f}$/{ss.get('t2',0):.2f}$/{ss.get('t3',0):.2f}$\n"
        f"- **يومي — شراء:** دخول {db.get('entry',0):.2f}$، وقف {db.get('sl',0):.2f}$، اهداف {db.get('t1',0):.2f}$/{db.get('t2',0):.2f}$\n"
        f"- **يومي — بيع:** دخول {ds.get('entry',0):.2f}$، وقف {ds.get('sl',0):.2f}$، اهداف {ds.get('t1',0):.2f}$/{ds.get('t2',0):.2f}$\n"
        f"- **اسبوعي — شراء:** دخول {wb.get('entry',0):.2f}$، وقف {wb.get('sl',0):.2f}$، اهداف {wb.get('t1',0):.2f}$/{wb.get('t2',0):.2f}$/{wb.get('t3',0):.2f}$\n"
        f"- **اسبوعي — بيع:** دخول {ws.get('entry',0):.2f}$، وقف {ws.get('sl',0):.2f}$، اهداف {ws.get('t1',0):.2f}$/{ws.get('t2',0):.2f}$/{ws.get('t3',0):.2f}$\n"
        f"- **سوينج — شراء:** دخول {swb.get('entry',0):.2f}$، وقف {swb.get('sl',0):.2f}$، اهداف {swb.get('t1',0):.2f}$/{swb.get('t2',0):.2f}$/{swb.get('t3',0):.2f}$\n"
        f"- **سوينج — بيع:** دخول {sws.get('entry',0):.2f}$، وقف {sws.get('sl',0):.2f}$، اهداف {sws.get('t1',0):.2f}$/{sws.get('t2',0):.2f}$/{sws.get('t3',0):.2f}$\n\n"
        "#### شهية المخاطرة 📊\n"
        f"- **مستوى المخاطرة الحالي:** {risk_pct:.0f}% ({risk_label})\n"
        f"- **توصية:** لا تجازف باكثر من {100 - risk_pct:.0f}% من راس المال في وقت واحد.\n\n"
        "### خلاصة القول 📝\n"
        "- يجب ان تكون استراتيجية التداول مدروسة وتاخذ بعين الاعتبار جميع المؤشرات الفنية والاساسية.\n"
        "- يجب ان تكون نسبة المخاطرة مدروسة لتجنب الخسائر الكبيرة.\n"
        "- يجب تداول الذهب في السوق الفوري (Spot - XAU/USD) فقط. 📈"
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
        "#### تاثير الارقام على اسعار الذهب 💰\n"
        f"*   **تاثير عائد السندات ({tnx:.2f}%)**: {tnx_impact}\n"
        f"*   **تاثير معدل الفائدة ({interest:.2f}%)**: {int_impact}\n"
        f"*   **تاثير معدل التضخم ({inflation:.2f}%)**: {inf_impact}\n"
        f"*   **تاثير العائد الحقيقي ({ry:.2f}%)**: {ry_impact}\n\n"
        "#### التوقعات 📝\n"
        f"*   **النظرة المستقبلية للذهب**: {gold_outlook}\n"
        f"*   **السعر الحالي**: {gold:.2f}$\n"
        f"*   **منحنى العوائد**: {curve_lbl} — {'اشارة تحوط' if spread < 0 else 'اشارة ايجابية'}\n\n"
        "#### استنتاج 📝\n"
        f"*   بيئة الفائدة الحالية ({interest:.2f}%) مع تضخم ({inflation:.2f}%) تشير الى ان "
        f"العائد الحقيقي {ry:.2f}% وهو {'يضغط سلبا على الذهب' if ry > 0 else 'يدعم الذهب بشكل قوي'}.\n"
        "*   ومع ذلك، يجب مراعاة العوامل الجيوسياسية والطلب المادي على الذهب.\n"
        f"*   توقع تداول الذهب في نطاق متاثر بمنحنى العوائد {curve_lbl}. 🌎"
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

    return (
        "### 🌍 تقرير السيولة النقدية وارتباط الدولار (DXY)
"
        "======================================================

"
        "#### 📊 المعطيات الفنية الحالية (XAU/USD)
"
        f"**السعر الحالي:** {gold:.2f}$ 💰 | **المحور اليومي:** {pivot:.2f}$
"
        f"**مقاومات أساسية:** {r1:.2f}$ (R1) — {r2:.2f}$ (R2)
"
        f"**دعوم أساسية:** {s1:.2f}$ (S1) — {s2:.2f}$ (S2)
"
        f"**الزخم:** RSI = {rsi:.2f} | MACD = {macd:.4f}

"
        "#### 💵 مؤشر الدولار الأمريكي (DXY)
"
        f"**القراءة الحالية:** {dxy_p:.4f} نقطة
"
        f"**التغير اليومي:** {dxy_pct:+.2f}%
"
        f"**الحالة الفنية:** {dxy_effect}
"
        f"💡 *{dxy_gold}*

"
        "#### 🎯 تأثير التدفقات النقدية على الذهب
"
        f"{gold_impact}

"
        "#### 💱 مصفوفة قوة العملات الرئيسية (Currency Matrix)
"
        f"{fx_block}
"
        f"*(تمركز السيولة يوضح شهية المخاطرة في الأسواق المالية)*

"
        "#### 🛠️ الاستراتيجية المقترحة (Smart Money Approach)
"
        f"{buy_res}
"
        f"{sell_res}

"
        f"📌 **القرار النهائي:** {recom}

"
        "⚠️ *تنبيه: العلاقة العكسية بين الذهب والدولار هي علاقة ارتباط قوية، لكنها قد تنكسر مؤقتاً في أوقات التوترات الجيوسياسية الحادة.* 🚨"
    )

def _build_spot_s12(d: dict) -> str:
    """12/12 - الخلاصة المحورية الشاملة"""
    nums = _s_nums(d)
    gold, atr, pivot = nums['gold'], nums['atr'], nums['pivot']
    rsi, macd = nums['rsi'], nums['macd']
    r1, r2, r3 = nums['r1'], nums['r2'], nums['r3']
    s1, s2, s3 = nums['s1'], nums['s2'], nums['s3']
    sh, sl = nums['swing_h'], nums['swing_l']
    fib = d.get('fib', {}) or {}

    interest  = float(d.get('interest_rate', 5.25) or 5.25)
    inflation = float(d.get('inflation_est', 3.5) or 3.5)
    ry        = float(d.get('real_yield', 0) or 0) or round(interest - inflation, 2)
    dxy_p     = float(d.get('dxy_p', 100) or 100)
    dxy_pct   = float(d.get('dxy_pct', 0) or 0)
    vix_p     = float(d.get('vix_p', 20) or 20)

    sb  = _s_trades(d, 'scalp_buy')
    ss  = _s_trades(d, 'scalp_sell')
    swb = _s_trades(d, 'swing_buy')
    sws = _s_trades(d, 'swing_sell')

    fib_block = "\n".join(
        f"- **{k}**: **{v}** {'📈' if k == '0.0%' else '📉' if k == '100%' else '📊'}"
        for k, v in fib.items()
    ) if fib else (
        f"- محسوب: R1={r1:.2f}$ | R2={r2:.2f}$ | S1={s1:.2f}$ | S2={s2:.2f}$"
    )

    # تحليل RSI
    if rsi < 30:
        rsi_note = f"RSI={rsi:.2f} تشبع بيعي حاد — ارتداد صعودي محتمل قوي 📈"
        rsi_action = f"الشراء عند {s1:.2f}$ فرصة ممتازة مع RSI في التشبع البيعي"
    elif rsi > 70:
        rsi_note = f"RSI={rsi:.2f} تشبع شرائي حاد — انعكاس هبوطي محتمل قوي 📉"
        rsi_action = f"البيع عند {r1:.2f}$ فرصة ممتازة مع RSI في التشبع الشرائي"
    else:
        rsi_note = f"RSI={rsi:.2f} في المنطقة المحايدة — الاتجاه غير محسوم"
        rsi_action = f"انتظار كسر {r1:.2f}$ صعودا او {s1:.2f}$ هبوطا للدخول"

    macd_note = (f"MACD={macd:.4f} سلبي — الزخم هبوطي، الضغط البيعي مستمر 📉"
                 if macd < 0 else
                 f"MACD={macd:.4f} ايجابي — الزخم صعودي، الدفع الشرائي قائم 📈")

    atr_note = (f"ATR={atr:.2f}$ — تقلبات {'كبيرة جدا' if atr > 100 else 'عالية' if atr > 60 else 'متوسطة' if atr > 30 else 'منخفضة'}. "
                f"المدى اليومي المتوقع: {round(gold-atr,2)}$—{round(gold+atr,2)}$")

    fib618 = float(fib.get('61.8%', 0) or 0) or s1
    fib236 = float(fib.get('23.6%', 0) or 0) or r2
    if sl < gold < fib618:
        fib_pos = f"السعر بين ادنى النطاق ({sl:.2f}$) ومستوى 61.8% ({fib618:.2f}$) — منطقة بيع مفرطة محتملة 📊."
    elif fib236 < gold < sh:
        fib_pos = f"السعر بين 23.6% ({fib236:.2f}$) واعلى النطاق ({sh:.2f}$) — منطقة شراء مفرطة محتملة 📊."
    else:
        fib_pos = f"السعر في المنطقة المحايدة بين {s1:.2f}$ و{r1:.2f}$."

    # تحليل الاقتصاد الكلي
    macro_read = ("بيئة ضاغطة على الذهب: فائدة عالية وعائد حقيقي موجب يجعل السندات اكثر جاذبية"
                  if ry > 1 else
                  "بيئة داعمة للذهب: عائد حقيقي سلبي يجعل الذهب ملاذا امنا افضل")

    # الخلاصة النهائية
    if rsi < 40 and macd < 0:
        main_dir = "هبوطي مع احتمالية ارتداد"
        best_trade = f"شراء زيرو انعكاس عند {s1:.2f}$ لمن يتحمل المخاطرة، وبيع عند {pivot:.2f}$ للمحافظين"
    elif rsi > 60 and macd > 0:
        main_dir = "صعودي مستمر"
        best_trade = f"شراء عند {pivot:.2f}$ بهدف {r1:.2f}$، مع وقف اسفل {s1:.2f}$"
    elif rsi < 40:
        main_dir = "ضغط بيعي مع RSI منخفض"
        best_trade = f"انتظار الاستقرار عند {s1:.2f}$—{s2:.2f}$ قبل الدخول شراء"
    elif rsi > 60:
        main_dir = "زخم شرائي مع حذر"
        best_trade = f"بيع عند {r1:.2f}$—{r2:.2f}$ مع وقف فوق {r2:.2f}$"
    else:
        main_dir = "متذبذب — بدون اتجاه واضح"
        best_trade = f"تداول في النطاق: شراء {s1:.2f}$، بيع {r1:.2f}$"

    return (
        "### الخلاصة المحورية 📊\n"
        "#### اسعار الذهب الحالية 💰\n"
        f"- السعر الحالي: **{gold:.2f}$** 📈\n"
        f"- نقطة المحور (Pivot): **{pivot:.2f}$** 📊\n"
        f"- اعلى النطاق اليومي (Swing H): **{sh:.2f}$** ⬆️\n"
        f"- ادنى النطاق اليومي (Swing L): **{sl:.2f}$** ⬇️\n\n"
        "#### الدعم والمقاومة 📍\n"
        f"- مقاومة R1: **{r1:.2f}$** | R2: **{r2:.2f}$** | R3: **{r3:.2f}$**\n"
        f"- دعم S1: **{s1:.2f}$** | S2: **{s2:.2f}$** | S3: **{s3:.2f}$**\n\n"
        "#### مؤشرات فنية 📊\n"
        f"- **RSI**: **{rsi:.2f}** 📉 ({rsi_note})\n"
        f"- **MACD**: **{macd:.4f}** 📊 ({macd_note})\n"
        f"- **ATR**: **{atr:.2f}$** 📈 ({atr_note})\n\n"
        "#### مستويات فيبوناتشي 📐\n"
        f"{fib_block}\n"
        f"- {fib_pos}\n\n"
        "#### تحليل الاسواق الكلي 💸\n"
        f"- **مؤشر الدولار (DXY)**: **{dxy_p:.4f}** ({dxy_pct:+.2f}%) 📈\n"
        f"- **معدل الفائدة**: **{interest:.2f}%** | **التضخم**: **{inflation:.2f}%** | **العائد الحقيقي**: **{ry:.2f}%**\n"
        f"- **VIX مؤشر الخوف**: **{vix_p:.2f}** ({'مرتفع — تحوط' if vix_p > 25 else 'طبيعي'})\n"
        f"- **التقييم الاقتصادي**: {macro_read}\n\n"
        "#### الصفقات الموصى بها 📋\n"
        f"- **سكالبينج شراء**: دخول **{sb.get('entry',0):.2f}$** | وقف **{sb.get('sl',0):.2f}$** | اهداف **{sb.get('t1',0):.2f}$**/**{sb.get('t2',0):.2f}$**/**{sb.get('t3',0):.2f}$**\n"
        f"- **سكالبينج بيع**: دخول **{ss.get('entry',0):.2f}$** | وقف **{ss.get('sl',0):.2f}$** | اهداف **{ss.get('t1',0):.2f}$**/**{ss.get('t2',0):.2f}$**/**{ss.get('t3',0):.2f}$**\n"
        f"- **سوينج شراء**: دخول **{swb.get('entry',0):.2f}$** | وقف **{swb.get('sl',0):.2f}$** | هدف **{swb.get('t2',0):.2f}$**\n"
        f"- **سوينج بيع**: دخول **{sws.get('entry',0):.2f}$** | وقف **{sws.get('sl',0):.2f}$** | هدف **{sws.get('t2',0):.2f}$**\n\n"
        "#### الخلاصة النهائية 📝\n"
        f"**الاتجاه العام**: {main_dir}\n\n"
        f"**اهم فرصة حالية**: {best_trade}\n\n"
        f"**تحليل المؤشرات**: {rsi_action}. {macd_note}.\n\n"
        f"**الوضع الاقتصادي**: {macro_read}. DXY {dxy_pct:+.2f}% {'يضغط على الذهب' if dxy_pct > 0 else 'يدعم الذهب'}.\n\n"
        f"**نطاق التداول اليومي**: السعر يتداول بين **{sl:.2f}$** و**{sh:.2f}$** مع المحور عند **{pivot:.2f}$**.\n\n"
        f"**التوصية الختامية**: {'الحذر والانتظار حتى يتضح الاتجاه' if 40 <= rsi <= 60 else ('الشراء عند مستويات الدعم' if rsi < 40 else 'البيع عند مستويات المقاومة')}. "
        "ادارة المخاطر الصارمة واجبة في جميع الاحوال. 📈"
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
        if not t: return "غير متوفر حالياً."
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

📈 نسبة الصعود: [توقعك كنسبة]%
📉 نسبة الهبوط: [توقعك كنسبة]%

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
                        if "تعذر توليد" in str(res) or "⚠️" in str(res):
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
                wrap(12, _build_template_12, data),
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
                
        t0, t1, t2, t3, t4, t5, t7, t8, t9, t10, t11, t12, t13, t6 = results

        if t0: raw_reports.append(("🎯 الصفقات المتقدمة والزيرو انعكاس (الفوري)", t0, None))
        if t1: raw_reports.append(("📊 التقرير الفني المتقدم (الفوري)", t1, None))
        if t2: raw_reports.append(("🌍 تقرير الاقتصاد الكلي (الفوري)", t2, None))
        if t3: raw_reports.append(("⚠️ تقرير شهية المخاطرة (الفوري)", t3, None))
        if t4: raw_reports.append(("📈 تقرير عوائد السندات (الفوري)", t4, None))
        if t5: raw_reports.append(("💱 تقرير قوة العملات (الفوري)", t5, None))
        
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
💧 سيولة اليومي {today_str}

✅ مستوى شراء بعد كسر وثبات {buy_lvl}
الهدف:
{buy_t1}
{buy_t2}
{buy_t3}

🛑 مستوى البيع بعد كسر وثبات {sell_lvl}
الهدف:
{sell_t1}
{sell_t2}
{sell_t3}

✅ الدخول بعد كسر + ثبات
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

🟢 Buy Limit:
دخول: {buy_limit_price}
هدف: {buy_limit_tp}
وقف: {buy_limit_sl}

🔴 Sell Limit:
دخول: {sell_limit_price}
هدف: {sell_limit_tp}
وقف: {sell_limit_sl}
"""

        # ── 6. إغلاق بجسم فريم 5 دقائق ──
        b5_buy = round(gld + (atr_val * 0.25), 2)
        b5_buy_tp = round(b5_buy + (atr_val * 0.6), 2)
        
        b5_sell = round(gld - (atr_val * 0.25), 2)
        b5_sell_tp = round(b5_sell - (atr_val * 0.6), 2)

        breakout_5m_block = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ صفقات الاختراق اللحظي (Breakout)

شراء
كسر {b5_buy}
هدف {b5_buy_tp}

بيع
كسر {b5_sell}
هدف {b5_sell_tp}

إغلاق بجسم فريم 5 دقائق.
شرط أساسي:
لا يتم الدخول في أي صفقة، سواء شراء أو بيع، إلا بعد تحقق شرط:
الإغلاق بجسم شمعة إطار الـ5 دقائق فوق مستوى الكسر في الشراء، أو أسفل مستوى الكسر في البيع.
"""

        bot2_reports = []
        bot2_reports.append(("💧 سيولة اليومي", daily_liquidity_block, None))
        bot2_reports.append(("⏳ الأوامر المعلقة اللحظية", limits_block, None))
        bot2_reports.append(("⚡ صفقات الاختراق اللحظي", breakout_5m_block, None))
        
        # القالب الجديد للمستويات
        bot2_reports.append(("📍 مستويات واتجاهات اليوم", _build_all_tf_levels(data), None))
        # القالب الذكي الجديد CFTC (t11)
        if 't11' in locals() and t11: bot2_reports.append(("📰 تقرير CFTC", t11, None))
        if 't12' in locals() and t12: bot2_reports.append(("🏦 تقرير المشتقات وصناديق الاستثمار", t12, None))
        if 't13' in locals() and t13: bot2_reports.append(("📊⚡ تحليل عقود الأوبشن الاحترافي", t13, None))

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
            log.info(f"[Bot3] جاهز: {len(bot3_reports)} قالب فوري رياضي")
        except Exception as _se:
            log.warning(f"[S1-S12] خطا في توليد القوالب الفورية: {_se}")

        if t7: bot2_reports.append(("🎯 الصفقات المتخصصة والفريمات (الفوري)", t7, None))
        if t8: bot2_reports.append(("🐋 تاثير الاسواق والمؤسسات (الفوري)", t8, None))
        if t9: bot2_reports.append(("📊 تقرير اتجاه الذهب اليومي (الفوري)", t9, None))
        if t10: bot2_reports.append(("📆 التقرير الاسبوعي الشامل (الفوري)", t10, None))
        if t6: bot2_reports.append(("الخلاصة المحورية", t6, None))

        # ── لا T6 خاص هنا ——  الخلاصة ستأتي مشتركة في الأسفل ──

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
                    _send_single(final_text, is_public, "@SovereignMaaregFund")
                    
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
                        _send_single_bot2(final_text2, is_public, "@SovereignMaaregFund")
                        
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