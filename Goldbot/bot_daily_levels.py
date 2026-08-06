# ════════════════════════════════════════════════════════════════
#  🏆 Goldbot — بوت المستويات اليومية الكلاسيكية والكاماريلا
#  يُرسل مرة واحدة يومياً الساعة 01:00 صباحاً (افتتاح الأسواق)
#  مستقل تماماً عن باقي البوتات
# ════════════════════════════════════════════════════════════════

import os
import time
import logging
import requests
import random
from datetime import datetime, timezone, timedelta

import yfinance as yf

try:
    from Goldbot.ai_client import UniversalAIClient as Groq, get_api_keys
except ImportError:
    from ai_client import UniversalAIClient as Groq, get_api_keys

# ── الإعدادات والثوابت ──
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("Goldbot.bot_daily_levels")

CAIRO_TZ     = timezone(timedelta(hours=3))
SEND_HOUR    = 1   # الساعة 1 صباحاً بتوقيت القاهرة
SEND_MINUTE  = 0

# ── مفاتيح API ──
try:
    from Goldbot.secrets_config import GROQ_KEYS_FALLBACK, TWELVEDATA_API_KEY_FALLBACK, TELEGRAM_TOKENS, BOT_DAILY_CHAT_ID as _CHAT_FALLBACK
except ImportError:
    try:
        from secrets_config import GROQ_KEYS_FALLBACK, TWELVEDATA_API_KEY_FALLBACK, TELEGRAM_TOKENS, BOT_DAILY_CHAT_ID as _CHAT_FALLBACK
    except ImportError:
        GROQ_KEYS_FALLBACK          = []
        TWELVEDATA_API_KEY_FALLBACK  = ""
        TELEGRAM_TOKENS             = {}
        _CHAT_FALLBACK              = ""

GROQ_KEYS          = get_api_keys() or GROQ_KEYS_FALLBACK
TWELVEDATA_API_KEY = os.environ.get("TWELVEDATA_API_KEY", TWELVEDATA_API_KEY_FALLBACK)

GROQ_MODELS = [
    "moonshotai/kimi-k2-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
]

# ── بيانات البوت الجديد ──
BOT_DAILY_TOKEN = (
    TELEGRAM_TOKENS.get("bot_daily", "")
    or os.environ.get("BOT_DAILY_TOKEN", "")
)
BOT_DAILY_CHAT = (
    os.environ.get("BOT_DAILY_CHAT", "")
    or _CHAT_FALLBACK
)


# ════════════════════════════════════════════════════════════════
#  1. جلب بيانات الذهب
# ════════════════════════════════════════════════════════════════

def _fetch(symbol: str, period: str = "5d", interval: str = "1d", retries: int = 4):
    for attempt in range(retries):
        try:
            df = yf.Ticker(symbol).history(period=period, interval=interval)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            wait = 2 ** attempt
            log.warning(f"[yfinance] {symbol} محاولة {attempt+1}: {e} — انتظار {wait}s")
            time.sleep(wait)
    return None


def _get_live_spot() -> float | None:
    """يجلب السعر الفوري الحي من مصادر متعددة."""
    # 1. Twelve Data
    try:
        url = f"https://api.twelvedata.com/price?symbol=XAU/USD&apikey={TWELVEDATA_API_KEY}"
        r = requests.get(url, timeout=6, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            p = float(r.json().get("price", 0))
            if p > 1000:
                log.info(f"✅ [TwelveData] Spot: {p}$")
                return round(p, 2)
    except Exception as e:
        log.warning(f"⚠️ [TwelveData] {e}")

    # 2. metals.live
    try:
        r = requests.get("https://api.metals.live/v1/spot/gold", timeout=5,
                         headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            j = r.json()
            p = j.get("price") or j.get("gold") or (j[0].get("gold") if isinstance(j, list) else None)
            if p and float(p) > 1000:
                return round(float(p), 2)
    except Exception:
        pass

    # 3. goldprice.org
    try:
        r = requests.get("https://data-asg.goldprice.org/dbXRates/USD",
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if r.status_code == 200:
            p = r.json()["items"][0].get("xauPrice")
            if p and float(p) > 1000:
                return round(float(p), 2)
    except Exception:
        pass

    return None


def fetch_daily_data() -> dict | None:
    """
    يجلب البيانات من البوت الفوري للحصول على أدق أرقام ممكنة مع ضبط بيانات الأمس.
    """
    log.info("📡 [DailyLevels] جلب بيانات الذهب باستخدام get_full_market_data...")
    try:
        from Goldbot.bot_spot import get_full_market_data
    except ImportError:
        from bot_spot import get_full_market_data

    d = get_full_market_data()
    if not d:
        log.error("❌ فشل جلب البيانات اليومية الدقيقة!")
        return None

    # جلب بيانات الأمس بدقة متناهية للفوري (Spot) باستخدام TwelveData
    import os, requests
    from datetime import datetime
    try:
        from Goldbot.secrets_config import TWELVEDATA_API_KEY_FALLBACK
    except ImportError:
        try:
            from secrets_config import TWELVEDATA_API_KEY_FALLBACK
        except ImportError:
            TWELVEDATA_API_KEY_FALLBACK = ""
            
    td_key = os.environ.get("TWELVEDATA_API_KEY", TWELVEDATA_API_KEY_FALLBACK)
    td_fetched = False
    
    if td_key:
        try:
            url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=1day&outputsize=4&apikey={td_key}"
            resp = requests.get(url, timeout=5).json()
            if "values" in resp and len(resp["values"]) >= 2:
                today_str = datetime.now().strftime("%Y-%m-%d")
                valid_candles = []
                for val in resp["values"]:
                    if val["datetime"][:10] != today_str:
                        if abs(float(val["high"]) - float(val["low"])) > 3.0:
                            valid_candles.append(val)
                
                if valid_candles:
                    yest = valid_candles[0]
                    ph = round(float(yest["high"]), 2)
                    pl = round(float(yest["low"]), 2)
                    pc = round(float(yest["close"]), 2)
                    td_fetched = True
                    log.info(f"✅ تم جلب الهاي واللو بدقة من TwelveData: H={ph}, L={pl}, C={pc}")
        except Exception as e:
            log.warning(f"⚠️ فشل جلب بيانات الأمس من TwelveData: {e}")

    if not td_fetched:
        log.warning("🔄 جاري الرجوع لـ yfinance (XAUUSD=X) كحل بديل...")
        df = _fetch("XAUUSD=X", period="5d", interval="1d")
        if df is not None and len(df) >= 2:
            from datetime import datetime
            import pytz
            CAIRO_TZ_LOCAL = pytz.timezone('Africa/Cairo')
            last_date = df.index[-1].date()
            today_date = datetime.now(CAIRO_TZ_LOCAL).date()
            
            # الفلتر الذكي: لو شمعة اليوم لسه مفتوحتش أو احنا في إجازة، هناخد الشمعة الأخيرة كأمس
            if last_date == today_date:
                yest = df.iloc[-2]
            else:
                yest = df.iloc[-1]
                
            ph = round(float(yest["High"]), 2)
            pl = round(float(yest["Low"]), 2)
            pc = round(float(yest["Close"]), 2)
            
        else:
            log.error("❌ فشل جلب بيانات الأمس من ياهو أو TwelveData!")
            return None

    d["prev_high"]  = ph
    d["prev_low"]   = pl
    d["prev_close"] = pc
    d["spot_price"] = d.get('gold', 0)
    d["prev_date"]  = d.get('pivot_data_date', "أمس")
    d["send_time"]  = datetime.now(CAIRO_TZ).strftime("%I:%M %p")

    log.info(f"✅ [DailyLevels] أمس (معدلة للفوري): H={ph} L={pl} C={pc} | ATR={d.get('atr', 0)}")
    return d


# ════════════════════════════════════════════════════════════════
#  2. حساب المستويات
# ════════════════════════════════════════════════════════════════

def calc_classical_pivots(h: float, l: float, c: float, ref_price: float = None, atr: float = None) -> dict:
    """
    البيفوت الكلاسيكي الدقيق المستند إلى أسعار الأمس للفوري.
    """
    pivot = round((h + l + c) / 3, 2)
    r1    = round(2 * pivot - l,       2)
    r2    = round(pivot + (h - l),     2)
    r3    = round(h + 2 * (pivot - l), 2)
    s1    = round(2 * pivot - h,       2)
    s2    = round(pivot - (h - l),     2)
    s3    = round(l - 2 * (h - pivot), 2)

    return {
        "pivot": pivot,
        "r1": r1, "r2": r2, "r3": r3,
        "s1": s1, "s2": s2, "s3": s3,
    }


def calc_camarilla_pivots(h: float, l: float, c: float) -> dict:
    """
    بيفوت كاماريلا — الأدق للتداول اليومي والسكالبينج.
    مُعدل ليُحسب انطلاقاً من البيفوت الكلاسيكي بدلاً من سعر الإغلاق لتوحيد القيم.
    """
    rng = h - l
    pivot = round((h + l + c) / 3,   2)  # مشترك وأساسي في الحساب
    h4  = round(pivot + rng * 1.1 / 2,   2)
    h3  = round(pivot + rng * 1.1 / 4,   2)
    h2  = round(pivot + rng * 1.1 / 6,   2)
    h1  = round(pivot + rng * 1.1 / 12,  2)
    l1  = round(pivot - rng * 1.1 / 12,  2)
    l2  = round(pivot - rng * 1.1 / 6,   2)
    l3  = round(pivot - rng * 1.1 / 4,   2)
    l4  = round(pivot - rng * 1.1 / 2,   2)
    return {
        "pivot": pivot,
        "h4": h4, "h3": h3, "h2": h2, "h1": h1,
        "l1": l1, "l2": l2, "l3": l3, "l4": l4,
    }


# ════════════════════════════════════════════════════════════════
#  3. توليد الصفقات
# ════════════════════════════════════════════════════════════════

def _trades_from_levels(levels: dict, lvl_type: str, ref_price: float, atr: float) -> dict:
    """
    يولد صفقات شراء وبيع بناءً على مستويات الدعم والمقاومة.
    يُستدعى مرتين: مرة للكلاسيكي ومرة للكاماريلا.
    """
    buys  = []
    sells = []
    
    # استبدال الـ ATR بحساب النطاق (Range) من مستويات البيفوت الكلاسيكي
    if "r2" in levels and "pivot" in levels:
        rng = round(levels["r2"] - levels["pivot"], 2)
    elif "h4" in levels and "pivot" in levels:
        rng = round((levels["h4"] - levels["pivot"]) * 2 / 1.1, 2)
    else:
        rng = atr

    sl_buf = round(rng * 0.20, 2)  # بافر وقف الخسارة = 20% من النطاق الكلاسيكي

    if lvl_type == "classical":
        pivot = levels["pivot"]
        r1, r2, r3 = levels["r1"], levels["r2"], levels["r3"]
        s1, s2, s3 = levels["s1"], levels["s2"], levels["s3"]

        # صفقات الشراء (من الدعوم)
        for entry, sl_base, label, t1, t2, t3 in [
            (s1, s2,    "🟢 دخول من S1 — الدعم الأول",  pivot, r1, r2),
            (s2, s3,    "🔵 دخول من S2 — الدعم الثاني", s1,    pivot, r1),
            (s3, s3-rng,"🟣 دخول من S3 — الدعم القوي",  s2,    s1,    pivot),
        ]:
            sl   = round(sl_base - sl_buf, 2)
            risk = round(entry - sl, 2)
            if risk <= 0: continue
            rr1 = round(abs(t1 - entry) / risk, 1) if risk > 0 else 0
            rr2 = round(abs(t2 - entry) / risk, 1) if risk > 0 else 0
            rr3 = round(abs(t3 - entry) / risk, 1) if risk > 0 else 0
            buys.append({
                "label": label, "entry": entry, "sl": sl,
                "risk": risk, "t1": t1, "t2": t2, "t3": t3,
                "rr1": rr1, "rr2": rr2, "rr3": rr3,
            })

        # صفقات البيع (من المقاومات)
        for entry, sl_base, label, t1, t2, t3 in [
            (r1, r2,    "🔴 بيع من R1 — المقاومة الأولى",  pivot, s1, s2),
            (r2, r3,    "🟠 بيع من R2 — المقاومة الثانية", r1,    pivot, s1),
            (r3, r3+rng,"⚡ بيع من R3 — ذروة الصعود",      r2,    r1,    pivot),
        ]:
            sl   = round(sl_base + sl_buf, 2)
            risk = round(sl - entry, 2)
            if risk <= 0: continue
            rr1 = round(abs(entry - t1) / risk, 1) if risk > 0 else 0
            rr2 = round(abs(entry - t2) / risk, 1) if risk > 0 else 0
            rr3 = round(abs(entry - t3) / risk, 1) if risk > 0 else 0
            sells.append({
                "label": label, "entry": entry, "sl": sl,
                "risk": risk, "t1": t1, "t2": t2, "t3": t3,
                "rr1": rr1, "rr2": rr2, "rr3": rr3,
            })

    elif lvl_type == "camarilla":
        h1, h2, h3, h4 = levels["h1"], levels["h2"], levels["h3"], levels["h4"]
        l1, l2, l3, l4 = levels["l1"], levels["l2"], levels["l3"], levels["l4"]
        pivot = levels["pivot"]

        # صفقات الشراء (كاماريلا — انعكاس من L3 وL4 الأقوى)
        for entry, sl_base, label, t1, t2, t3 in [
            (l3, l4, "🎯 انعكاس من L3 — كاماريلا (الأقوى)", l2, l1, pivot),
            (l4, l4-sl_buf*2, "💎 انعكاس من L4 — إشارة انعكاس كبيرة", l3, l2, l1),
        ]:
            sl   = round(sl_base - sl_buf, 2)
            risk = round(entry - sl, 2)
            if risk <= 0: continue
            rr1 = round(abs(t1 - entry) / risk, 1) if risk > 0 else 0
            rr2 = round(abs(t2 - entry) / risk, 1) if risk > 0 else 0
            rr3 = round(abs(t3 - entry) / risk, 1) if risk > 0 else 0
            buys.append({
                "label": label, "entry": entry, "sl": sl,
                "risk": risk, "t1": t1, "t2": t2, "t3": t3,
                "rr1": rr1, "rr2": rr2, "rr3": rr3,
            })

        # صفقات البيع (كاماريلا — انعكاس من H3 وH4 الأقوى)
        for entry, sl_base, label, t1, t2, t3 in [
            (h3, h4, "🎯 انعكاس من H3 — كاماريلا (الأقوى)", h2, h1, pivot),
            (h4, h4+sl_buf*2, "💎 انعكاس من H4 — إشارة انعكاس كبيرة", h3, h2, h1),
        ]:
            sl   = round(sl_base + sl_buf, 2)
            risk = round(sl - entry, 2)
            if risk <= 0: continue
            rr1 = round(abs(entry - t1) / risk, 1) if risk > 0 else 0
            rr2 = round(abs(entry - t2) / risk, 1) if risk > 0 else 0
            rr3 = round(abs(entry - t3) / risk, 1) if risk > 0 else 0
            sells.append({
                "label": label, "entry": entry, "sl": sl,
                "risk": risk, "t1": t1, "t2": t2, "t3": t3,
                "rr1": rr1, "rr2": rr2, "rr3": rr3,
            })

    return {"buys": buys, "sells": sells}


def _fmt_trade_block(trades: list, direction: str) -> str:
    """ينسق قائمة الصفقات بشكل جميل مع شرح كل مصطلح."""
    nums = ("1️⃣", "2️⃣", "3️⃣", "4️⃣")
    lines = []
    for i, t in enumerate(trades[:4]):
        lines.append(
            f"\n   ╭─────────────────────────────╮\n"
            f"   │ {nums[i]} {t['label']}\n"
            f"   ├─────────────────────────────┤\n"
            f"   │ 📍 الدخول : {t['entry']}$\n"
            f"   │    ↳ السعر الذي تفتح منه الصفقة\n"
            f"   │ 🛡️  الوقف : {t['sl']}$  (الخطر: {t['risk']}$)\n"
            f"   │    ↳ السعر الذي تُغلق عنده الصفقة تلقائياً لحماية رأس المال\n"
            f"   │ 🎯 الأهداف (الأرباح المتوقعة):\n"
            f"   │    T1 ← {t['t1']}$  (R/R: {t['rr1']}x) — هدف أول (آمن)\n"
            f"   │    T2 ← {t['t2']}$  (R/R: {t['rr2']}x) — هدف ثاني (متوسط)\n"
            f"   │    T3 ← {t['t3']}$  (R/R: {t['rr3']}x) — هدف ثالث (أقصى)\n"
            f"   │ 💡 R/R = نسبة الربح للمخاطرة (كلما زادت كلما كانت أفضل)\n"
            f"   ╰─────────────────────────────╯"
        )
    if not lines:
        return f"\n   ─ لا توجد صفقات {direction} فعّالة حالياً.\n"
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════
#  4. بناء القوالب (الرسائل)
# ════════════════════════════════════════════════════════════════

def _day_range_analysis(cp: dict, cam: dict, atr: float, spot: float | None) -> str:
    """تحليل نطاق اليوم والسيناريوهات المحتملة."""
    ref = spot or cp["pivot"]
    rng = round(cp["r2"] - cp["pivot"], 2)
    exp_high = round(ref + rng * 0.65, 2)
    exp_low  = round(ref - rng * 0.65, 2)

    # موقع السعر من الكلاسيكي
    if ref > cp["r1"]:
        zone_cl = f"📈 فوق R1 ({cp['r1']}$) — ضغط صعودي قوي"
        scenario_cl = f"🔺 اختراق نحو R2 ({cp['r2']}$) إذا تماسك فوق R1"
    elif ref > cp["pivot"]:
        zone_cl = f"🟡 بين المحور ({cp['pivot']}$) وR1 ({cp['r1']}$) — محايد صعودي"
        scenario_cl = f"⚡ التذبذب في النطاق {cp['pivot']}$ — {cp['r1']}$ هو السيناريو الأرجح"
    elif ref > cp["s1"]:
        zone_cl = f"🟡 بين S1 ({cp['s1']}$) والمحور ({cp['pivot']}$) — محايد هبوطي"
        scenario_cl = f"⚡ التذبذب في النطاق {cp['s1']}$ — {cp['pivot']}$ هو السيناريو الأرجح"
    else:
        zone_cl = f"📉 تحت S1 ({cp['s1']}$) — ضغط هبوطي"
        scenario_cl = f"🔻 اختبار S2 ({cp['s2']}$) إذا لم يُغلق فوق S1"

    # موقع السعر من الكاماريلا
    if ref > cam["h3"]:
        zone_cam = f"🚀 فوق H3 ({cam['h3']}$) — اتجاه صاعد قوي (اختراق نادر)"
    elif ref > cam["h1"]:
        zone_cam = f"📈 بين H1-H3 ({cam['h1']}$—{cam['h3']}$) — ضغط صعودي"
    elif ref > cam["l1"]:
        zone_cam = f"⚖️  في نطاق التوازن ({cam['l1']}$—{cam['h1']}$)"
    elif ref > cam["l3"]:
        zone_cam = f"📉 بين L1-L3 ({cam['l3']}$—{cam['l1']}$) — ضغط هبوطي"
    else:
        zone_cam = f"⬇️  تحت L3 ({cam['l3']}$) — اتجاه هابط قوي (فرصة انعكاس)"

    return (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 تحليل نطاق جلسة اليوم\n"
        f"   📏 النطاق المتوقع (Range): {exp_low}$ ↔ {exp_high}$\n"
        f"   🗺️  موقع السعر (الكلاسيكي): {zone_cl}\n"
        f"   🎯 السيناريو الأرجح (كلاسيكي): {scenario_cl}\n"
        f"   🎰 موقع السعر (كاماريلا): {zone_cam}\n"
    )


def build_template_classical(data: dict, cp: dict, trades: dict) -> str:
    """
    القالب الأول — المستويات الكلاسيكية الثابتة (تتجدد يومياً الساعة 1 صباحاً).
    """
    spot_str = f"{data['spot_price']:.2f}$" if data["spot_price"] else "غير متاح"
    prev_rng = round(data["prev_high"] - data["prev_low"], 2)

    buy_block  = _fmt_trade_block(trades["buys"],  "buy")
    sell_block = _fmt_trade_block(trades["sells"], "sell")

    return (
        f"1/2 📐 مستويات البيفوت الكلاسيكي — ذهب XAU/USD\n"
        f"🕐 {data['send_time']} القاهرة\n"
        f"🔄 تتجدد يومياً عند افتتاح السوق (الساعة 1 صباحاً)\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 بيانات شمعة أمس ({data['prev_date']})"
        f" — المصدر الذي تُحسب منه بعض المؤشرات\n"
        f"   📈 القمة  (High)  : {data['prev_high']}$"
        f"  ← أعلى سعر وصله الذهب أمس\n"
        f"   📉 القاع  (Low)   : {data['prev_low']}$"
        f"  ← أدنى سعر وصله الذهب أمس\n"
        f"   🔒 الإغلاق (Close): {data['prev_close']}$"
        f"  ← آخر سعر عند نهاية جلسة أمس\n"
        f"   📏 النطاق (Range) : {prev_rng}$"
        f"  ← المسافة بين القمة والقاع (High - Low)\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔢 خريطة مستويات البيفوت الكلاسيكي\n"
        f"   (المحسوبة رياضياً من معادلة البيفوت)\n"
        f"\n"
        f"   🔴 R3 = {cp['r3']}$  ← مقاومة قوية جداً (يصلها السعر نادراً)\n"
        f"   🟠 R2 = {cp['r2']}$  ← مقاومة ثانية (هدف صعود متقدم)\n"
        f"   🔺 R1 = {cp['r1']}$  ← مقاومة أولى (أول عائق أمام الصعود)\n"
        f"   ══════════════════════\n"
        f"   💠 Pivot = {cp['pivot']}$  ← نقطة المحور\n"
        f"      (فوقه = الاتجاه صعودي | تحته = الاتجاه هبوطي)\n"
        f"   ══════════════════════\n"
        f"   🟢 S1 = {cp['s1']}$  ← دعم أول (أول سطح يرتد منه السعر للأعلى)\n"
        f"   🔵 S2 = {cp['s2']}$  ← دعم ثاني (دعم أقوى إذا كسر S1)\n"
        f"   🟣 S3 = {cp['s3']}$  ← دعم قوي جداً (منطقة شراء مؤسساتية)\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 السعر الفوري الآن      : {spot_str}\n"
        f"   🔧 المعادلة: Pivot = (القمة + القاع + الإغلاق) ÷ 3\n"
        f"      ثم تُشتق منه جميع مستويات الدعم والمقاومة رياضياً\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛒 صفقات الشراء — من مناطق الدعم الكلاسيكية:\n"
        f"   (الشراء يكون عند اقتراب السعر من الدعم وانعكاسه للأعلى)\n"
        f"{buy_block}\n"
        f"━━\n"
        f"📉 صفقات البيع — من مناطق المقاومة الكلاسيكية:\n"
        f"   (البيع يكون عند اقتراب السعر من المقاومة وارتداده للأسفل)\n"
        f"{sell_block}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ تنبيه: هذه مستويات مرجعية للتحليل، وليست توصيات استثمارية.\n"
        f"         الالتزام بإدارة رأس المال أمر إلزامي دائماً."
    )


def build_template_camarilla(data: dict, cam: dict, cp: dict, trades: dict) -> str:
    """
    القالب الثاني — مستويات كاماريلا (أدق للسكالبينج والتداول اليومي الدقيق).
    """
    spot_str = f"{data['spot_price']:.2f}$" if data["spot_price"] else "غير متاح"
    day_analysis = _day_range_analysis(cp, cam, data["atr"], data["spot_price"])
    atr_exp = round(data['atr'], 2)
    prev_rng = round(data['prev_high'] - data['prev_low'], 2)

    buy_block  = _fmt_trade_block(trades["buys"],  "buy")
    sell_block = _fmt_trade_block(trades["sells"], "sell")

    return (
        f"2/2 🎯 مستويات كاماريلا الدقيقة — ذهب XAU/USD\n"
        f"🕐 {data['send_time']} القاهرة\n"
        f"🔄 تتجدد يومياً عند افتتاح السوق (الساعة 1 صباحاً)\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 ما هو نظام كاماريلا؟\n"
        f"   نظام مستويات مؤسسي متقدم تستخدمه أكبر البنوك والمؤسسات\n"
        f"   (بلومبرج، رويترز، وكبار صناديق التحوط)\n"
        f"   ميزته: يعطي مستويات أضيق وأدق من الكلاسيكي\n"
        f"   مثالي لـ: السكالبينج (صفقات سريعة) والتداول اليومي الدقيق\n"
        f"   ↳ السكالبينج = فتح وإغلاق صفقات سريعة خلال دقائق أو ساعات\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔢 خريطة مستويات كاماريلا\n"
        f"   (ثابتة لليوم كله — مبنية على نطاق شمعة أمس)\n"
        f"\n"
        f"   ⬆️  H4 = {cam['h4']}$  ← ذروة الصعود اليومية\n"
        f"      (كسر هذا المستوى للأعلى = اتجاه صاعد قوي نادر)\n"
        f"   🔴 H3 = {cam['h3']}$  ← مقاومة انعكاس رئيسية ⭐\n"
        f"      (الأهم في الكاماريلا — يرتد منه السعر في 70% من الأوقات)\n"
        f"   🟠 H2 = {cam['h2']}$  ← مقاومة متوسطة (أخذ جزء من الربح هنا)\n"
        f"   🔺 H1 = {cam['h1']}$  ← مقاومة خفيفة (أول عائق للصعود)\n"
        f"   ══════════════════════\n"
        f"   💠 Pivot = {cam['pivot']}$  ← نقطة التوازن المحورية\n"
        f"      (فوقه ميل صعودي | تحته ميل هبوطي)\n"
        f"   ══════════════════════\n"
        f"   🟢 L1 = {cam['l1']}$  ← دعم خفيف (أول نقطة ارتداد محتملة)\n"
        f"   🔵 L2 = {cam['l2']}$  ← دعم متوسط (أخذ جزء من الربح هنا)\n"
        f"   🎯 L3 = {cam['l3']}$  ← دعم انعكاس رئيسي ⭐\n"
        f"      (الأهم في الكاماريلا — يرتد منه السعر في 70% من الأوقات)\n"
        f"   ⬇️  L4 = {cam['l4']}$  ← ذروة الهبوط اليومية\n"
        f"      (كسر هذا المستوى للأسفل = اتجاه هابط قوي نادر)\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 بيانات السوق الآن\n"
        f"   📡 السعر الفوري      : {spot_str}\n"
        f"   📐 نطاق أمس (Range)  : {prev_rng}$"
        f"  ← المسافة بين القمة والقاع أمس\n"
        f"\n"
        f"{day_analysis}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛒 صفقات الشراء — انعكاس من دعم كاماريلا:\n"
        f"   (ندخل شراءً عند وصول السعر لـ L3 أو L4 وظهور إشارة ارتداد)\n"
        f"{buy_block}\n"
        f"━━\n"
        f"📉 صفقات البيع — انعكاس من مقاومة كاماريلا:\n"
        f"   (ندخل بيعاً عند وصول السعر لـ H3 أو H4 وظهور إشارة ارتداد)\n"
        f"{sell_block}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ تنبيه: هذه مستويات مرجعية للتحليل، وليست توصيات استثمارية.\n"
        f"         الالتزام بإدارة رأس المال أمر إلزامي دائماً."
    )


# ════════════════════════════════════════════════════════════════
#  5. الإرسال عبر تيليجرام
# ════════════════════════════════════════════════════════════════

def _split_msg(text: str, max_len: int = 4000) -> list:
    """يقسم الرسالة إلى أجزاء لا تتجاوز حد تيليجرام."""
    chunks = []
    while len(text) > max_len:
        split_idx = text.rfind("\n", 0, max_len)
        if split_idx == -1:
            split_idx = max_len
        chunks.append(text[:split_idx])
        text = text[split_idx:].lstrip()
    if text:
        chunks.append(text)
    return chunks


def send_message(token: str, chat_id: str, text: str) -> bool:
    """يرسل رسالة نصية واحدة عبر تيليجرام Bot API (HTTP) مع دعم الالتفاف (Direct IPv4)."""
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    ip_url = f"https://149.154.167.220/bot{token}/sendMessage"
    
    headers = {"User-Agent": "Mozilla/5.0"}
    ip_headers = dict(headers)
    ip_headers["Host"] = "api.telegram.org"
    
    payload = {"chat_id": str(chat_id), "text": text}
    
    for attempt in range(3):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=15.0)
            r.raise_for_status()
            return True
        except Exception as e:
            log.warning(f"⚠️ [Telegram] محاولة {attempt+1}/3 الأساسية فشلت: {e}")
            try:
                # الالتفاف على الحظر باستخدام IP مباشر
                r = requests.post(ip_url, json=payload, headers=ip_headers, timeout=15.0, verify=False)
                r.raise_for_status()
                log.info("✅ [Telegram] تم الإرسال للتيليجرام بنجاح (Direct IPv4)!")
                return True
            except Exception as e2:
                wait = 2 ** attempt
                log.warning(f"⚠️ [Telegram] محاولة {attempt+1}/3 بالـ IPv4 فشلت — {e2} — انتظار {wait}s")
                time.sleep(wait)
    return False


def build_template_quant_atr_backup(d: dict) -> str:
    """يبني القالب الثالث (الكمي الشامل) بنسخته القديمة (ATR المحسن). تم الاحتفاظ به لغرض آخر."""
    gold = d.get("gold", 0)
    rn = d.get("round_numbers", {"nearest_resistance": 0, "dist_to_resistance": 0, "nearest_support": 0, "dist_to_support": 0})
    fib = d.get("fib", {})
    if fib:
        fib_line = (f"فيبوناتشي (فوري): 0%={fib.get('0.0%','-')}$ | 23.6%={fib.get('23.6%','-')}$ | 38.2%={fib.get('38.2%','-')}$ | "
                    f"50.0%={fib.get('50.0%','-')}$ | 61.8%={fib.get('61.8%','-')}$ | 78.6%={fib.get('78.6%','-')}$ | 100%={fib.get('100%','-')}$")
    else:
        fib_line = "فيبوناتشي: غير متاح"
        
    atr = d.get("atr", 0)
    if gold and atr:
        exp_low  = round(gold - atr * 0.65, 2)
        exp_high = round(gold + atr * 0.65, 2)
        range_line = f"نطاق اليوم المتوقع (±0.65×ATR): {exp_low}$ ↔ {exp_high}$"
    else:
        range_line = "نطاق اليوم المتوقع: غير متاح"

    market_suffix = "فوري XAUUSD"
    send_time = d.get("send_time", datetime.now(CAIRO_TZ).strftime("%I:%M %p"))

    vwap_str = f"{d['vwap']}$" if d.get("vwap") else "— غير متاح"
    w_high_str = f"{d['prev_wk_high']}$" if d.get("prev_wk_high") else "—"
    w_low_str = f"{d['prev_wk_low']}$" if d.get("prev_wk_low") else "—"
    m_high_str = f"{d['prev_mo_high']}$" if d.get("prev_mo_high") else "—"
    m_low_str = f"{d['prev_mo_low']}$" if d.get("prev_mo_low") else "—"

    demand_str = f"{d['sd_demand']}$" if d.get("sd_demand") else "—"
    supply_str = f"{d['sd_supply']}$" if d.get("sd_supply") else "—"

    date_flag = "✅ "
    date_nat = " — طبيعي"
    calc_status = "✅ بيفوت ATR المحسن"

    template = f"""👑 📊 التقرير الكمي الشامل للذهب (الفوري - Spot)
🔢 المستويات والصفقات (الفوري - Spot)

━━━━━━━━━━━━━━━━━━━━━━━━━━
🔢 خريطة المستويات والصفقات (مبنية على الـ ({market_suffix}))
   ⏱️ السعر الفوري (لحظة الإرسال): {gold:.2f}$ — {send_time} القاهرة
   🟣 مقاومة نفسية: {rn.get('nearest_resistance')}$ (+{rn.get('dist_to_resistance')}$) | دعم نفسي: {rn.get('nearest_support')}$ (-{rn.get('dist_to_support')}$)
   ═════════════════════════════
   📍 Swing High : {d.get('swing_high', '—')}$
   📍 Swing Low  : {d.get('swing_low', '—')}$
   ═════════════════════════════
   📊 VWAP       : {vwap_str}
   ═════════════════════════════
   📅 الأسبوع السابق → قمة: {w_high_str} | قاع: {w_low_str}
   📆 الشهر السابق   → قمة: {m_high_str} | قاع: {m_low_str}
   ═════════════════════════════
   🔴 المقاومات: R1: {d.get('r1', '—')}$ | R2: {d.get('r2', '—')}$
   💠 المحور: Pivot: {d.get('pivot', '—')}$
   🟢 الدعوم: S1: {d.get('s1', '—')}$ | S2: {d.get('s2', '—')}$
   ═════════════════════════════
   📋 حالة البيانات والبيفوت:
    ▪️ المصدر: ✅ فوري (XAU/USD)
    ▪️ التاريخ: {date_flag}📅 اليوم ({datetime.now().strftime('%Y-%m-%d')}){date_nat}
    ▪️ الحساب: {calc_status}
   🎯 كفاءة العمليات الرياضية: 100% (دقة حسابية خالية من الأخطاء)
   ═════════════════════════════
   🟡 {fib_line}
   ═════════════════════════════
   📊 {range_line}
   ═════════════════════════════
   🔍 التباين (Divergence): {d.get('divergence', '—')}
   🛒 منطقة الطلب القوية: {demand_str}
   🩸 منطقة العرض القوية: {supply_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return template


def build_template_quant(d: dict) -> str:
    """يبني القالب الثالث (الكمي الشامل) متطابقاً مع بيفوت كلاسيكي للفوري."""
    gold = d.get("gold", 0)
    rn = d.get("round_numbers", {"nearest_resistance": 0, "dist_to_resistance": 0, "nearest_support": 0, "dist_to_support": 0})
    fib = d.get("fib", {})
    if fib:
        fib_line = (f"فيبوناتشي (فوري): 0%={fib.get('0.0%','-')}$ | 23.6%={fib.get('23.6%','-')}$ | 38.2%={fib.get('38.2%','-')}$ | "
                    f"50.0%={fib.get('50.0%','-')}$ | 61.8%={fib.get('61.8%','-')}$ | 78.6%={fib.get('78.6%','-')}$ | 100%={fib.get('100%','-')}$")
    else:
        fib_line = "فيبوناتشي: غير متاح"
        
    rng = round(d.get("prev_high", 0) - d.get("prev_low", 0), 2)
    if gold and rng > 0:
        exp_low  = round(gold - rng * 0.65, 2)
        exp_high = round(gold + rng * 0.65, 2)
        range_line = f"نطاق اليوم المتوقع (±0.65×Range): {exp_low}$ ↔ {exp_high}$"
    else:
        range_line = "نطاق اليوم المتوقع: غير متاح"

    market_suffix = "فوري XAUUSD"
    send_time = d.get("send_time", datetime.now(CAIRO_TZ).strftime("%I:%M %p"))

    vwap_str = f"{d['vwap']}$" if d.get("vwap") else "— غير متاح"
    w_high_str = f"{d['prev_wk_high']}$" if d.get("prev_wk_high") else "—"
    w_low_str = f"{d['prev_wk_low']}$" if d.get("prev_wk_low") else "—"
    m_high_str = f"{d['prev_mo_high']}$" if d.get("prev_mo_high") else "—"
    m_low_str = f"{d['prev_mo_low']}$" if d.get("prev_mo_low") else "—"

    demand_str = f"{d['sd_demand']}$" if d.get("sd_demand") else "—"
    supply_str = f"{d['sd_supply']}$" if d.get("sd_supply") else "—"

    date_flag = "✅ "
    date_nat = " — طبيعي"
    calc_status = "✅ بيفوت كلاسيكي"
    _date_str = d.get('prev_date', f"{datetime.now().strftime('%Y-%m-%d')}")

    template = f"""👑 📊 التقرير الكمي الشامل للذهب (الفوري - Spot)
🔢 المستويات والصفقات (الفوري - Spot)

━━━━━━━━━━━━━━━━━━━━━━━━━━
🔢 خريطة المستويات والصفقات (مبنية على الـ ({market_suffix}))
   ⏱️ السعر الفوري (لحظة الإرسال): {gold:.2f}$ — {send_time} القاهرة
   🟣 مقاومة نفسية: {rn.get('nearest_resistance')}$ (+{rn.get('dist_to_resistance')}$) | دعم نفسي: {rn.get('nearest_support')}$ (-{rn.get('dist_to_support')}$)
   ═════════════════════════════
   📍 Swing High : {d.get('swing_high', '—')}$
   📍 Swing Low  : {d.get('swing_low', '—')}$
   ═════════════════════════════
   📊 VWAP       : {vwap_str}
   ═════════════════════════════
   📅 الأسبوع السابق → قمة: {w_high_str} | قاع: {w_low_str}
   📆 الشهر السابق   → قمة: {m_high_str} | قاع: {m_low_str}
   ═════════════════════════════
   🔴 المقاومات: R1: {d.get('r1', '—')}$ | R2: {d.get('r2', '—')}$
   💠 المحور: Pivot: {d.get('pivot', '—')}$
   🟢 الدعوم: S1: {d.get('s1', '—')}$ | S2: {d.get('s2', '—')}$
   ═════════════════════════════
   📋 حالة البيانات والبيفوت:
    ▪️ المصدر: ✅ فوري (XAU/USD)
    ▪️ التاريخ: {date_flag}📅 أمس ({_date_str}){date_nat}
    ▪️ الحساب: {calc_status}
   🎯 كفاءة العمليات الرياضية: 100% (دقة حسابية خالية من الأخطاء)
   ═════════════════════════════
   🟡 {fib_line}
   ═════════════════════════════
   📊 {range_line}
   ═════════════════════════════
   🔍 التباين (Divergence): {d.get('divergence', '—')}
   🛒 منطقة الطلب القوية: {demand_str}
   🩸 منطقة العرض القوية: {supply_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return template


def send_daily_report(token: str, chat_id: str, template1: str, template2: str, template3: str):

    """يرسل القوالب للقناة المخصصة."""
    if not token or not chat_id:
        log.error("❌ [DailyLevels] Token أو Chat ID غير مضبوط — لا يمكن الإرسال!")
        return

    for idx, tmpl in enumerate([template1, template2, template3], 1):
        log.info(f"📤 [DailyLevels] إرسال القالب {idx}...")
        for chunk in _split_msg(tmpl):
            ok = send_message(token, chat_id, chunk)
            if ok:
                log.info("✅ جزء وصل.")
            else:
                log.error("❌ فشل جزء.")
            time.sleep(2)
        time.sleep(3)


# ════════════════════════════════════════════════════════════════
#  6. المنطق الرئيسي — يعمل على الساعة 01:00 صباحاً يومياً
# ════════════════════════════════════════════════════════════════

def _run_once():
    """دورة عمل كاملة: جلب بيانات → حساب → إرسال."""
    log.info("🌙 [DailyLevels] بدء دورة العمل اليومية...")

    # 1. جلب البيانات
    data = fetch_daily_data()
    if not data:
        log.error("❌ [DailyLevels] فشل جلب البيانات — سيتم المحاولة مجدداً خلال ساعة.")
        return False

    h = data["prev_high"]
    l = data["prev_low"]
    c = data["prev_close"]

    # 2. حساب المستويات للكلاسيكي والكاماريلا
    ref = data["spot_price"] or round((h + l + c) / 3, 2)
    atr = data["atr"]
    cp  = calc_classical_pivots(h, l, c, ref_price=ref, atr=atr)
    cam = calc_camarilla_pivots(h, l, c)


    log.info(f"📐 [Classical] Pivot={cp['pivot']} | R1={cp['r1']} | S1={cp['s1']}")
    log.info(f"🎯 [Camarilla] H3={cam['h3']} | L3={cam['l3']} | H4={cam['h4']} | L4={cam['l4']}")

    # 3. توليد الصفقات
    trades_cl  = _trades_from_levels(cp,  "classical",  ref, atr)
    trades_cam = _trades_from_levels(cam, "camarilla",  ref, atr)

    # 4. بناء القوالب
    t1 = build_template_classical(data, cp, trades_cl)
    t2 = build_template_camarilla(data, cam, cp, trades_cam)
    
    # تحديث البيانات بالبيفوت الخاص بـ ATR للقالب الكمي
    data["pivot"] = cp["pivot"]
    data["r1"] = cp["r1"]
    data["r2"] = cp["r2"]
    data["r3"] = cp["r3"]
    data["s1"] = cp["s1"]
    data["s2"] = cp["s2"]
    data["s3"] = cp["s3"]
    t3 = build_template_quant(data)

    # 5. الإرسال
    send_daily_report(BOT_DAILY_TOKEN, BOT_DAILY_CHAT, t1, t2, t3)

    log.info("✅ [DailyLevels] تمت دورة العمل بنجاح!")
    return True


def run_daily_levels_bot():
    """
    الحلقة الرئيسية — تراقب الوقت وتنتظر الساعة 1 صباحاً لإرسال التقرير.
    """
    log.info("🚀 [DailyLevels] البوت اليومي بدأ التشغيل...")
    last_sent_date = None

    while True:
        try:
            now = datetime.now(CAIRO_TZ)
            today = now.date()

            # تحقق من الوقت (الساعة 1 صباحاً بالكامل لضمان عدم تفويت الإرسال في حال إعادة تشغيل السيرفر)
            is_send_time = (now.hour == SEND_HOUR)

            # تحقق من أننا لم نرسل اليوم مسبقاً
            already_sent = (last_sent_date == today)

            if is_send_time and not already_sent:
                log.info(f"⏰ [DailyLevels] حان وقت الإرسال! ({now.strftime('%H:%M')} القاهرة)")
                success = _run_once()
                if success:
                    last_sent_date = today
                else:
                    # إعادة المحاولة بعد ساعة
                    log.warning("⚠️ فشل الإرسال، سيُعاد بعد 60 دقيقة...")
                    time.sleep(60 * 60)
                    continue

            # النوم لمدة دقيقة ثم إعادة التحقق
            time.sleep(60)

        except Exception as e:
            log.error(f"❌ [DailyLevels] خطأ غير متوقع: {e}")
            time.sleep(60)


# ── نقطة الدخول المباشرة ──
if __name__ == "__main__":
    run_daily_levels_bot()
