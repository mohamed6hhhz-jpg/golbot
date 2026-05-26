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

# ══ قائمة الموديلات — كل موديل له حد يومي مستقل ══
GROQ_MODELS = [
    "llama-3.3-70b-versatile",   # الأقوى — 100K token/day
    "llama-3.1-8b-instant",      # سريع وخفيف — 500K token/day
    "gemma2-9b-it",              # جوجل — حد مستقل
    "mixtral-8x7b-32768",        # ميكستراล — حد مستقل
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
log = logging.getLogger(__name__)

# ================= الإعدادات =================
GROQ_API_KEY       = os.environ.get("GROQ_API_KEY")
TELEGRAM_BOT_TOKEN = "8678714877:AAE2v6jeeYzsNFYj_83rXK32RJEA7fszQew"
TELEGRAM_CHAT_ID   = -1003775201576   # قناة Gold Reports

# Telethon credentials
API_ID   = 34105911
API_HASH = 'b444ab6b4eeba8a66db4143b934dc540'
SESSION_STRING = (
    os.environ.get("AUTO_COPY_SESSION_STRING") or
    os.environ.get("SHEETS_SESSION_STRING") or
    ""
)

# توقيت القاهرة (UTC+3)
CAIRO_TZ         = timezone(timedelta(hours=3))
ALERT_THRESHOLD  = 6.0    # دولار — تنبيه فوري عند هذا التحرك
ROUTINE_MINUTES  = 60     # تقرير روتيني كل ساعة
MORNING_HOUR_CAI = 9      # تقرير الصباح بتوقيت القاهرة
CLOSING_HOUR_CAI = 23     # تقرير نهاية الجلسة بتوقيت القاهرة
HEARTBEAT_HOUR   = 12     # Heartbeat عند الظهر بتوقيت القاهرة
MARKET_OPEN_HOUR = 1      # سوق الذهب يفتح 01:00 قاهرة الاثنين
# ==================================================


def cairo_now() -> datetime:
    """الوقت الحالي بتوقيت القاهرة."""
    return datetime.now(CAIRO_TZ)


def is_market_open() -> bool:
    """
    سوق الذهب الفوري مفتوح من الاثنين 01:00 إلى الجمعة 24:00 بتوقيت القاهرة.
    السبت والأحد مغلق تماماً.
    """
    now     = cairo_now()
    weekday = now.weekday()  # 0=Mon ... 4=Fri, 5=Sat, 6=Sun
    hour    = now.hour
    if weekday == 5 or weekday == 6:
        return False
    if weekday == 0 and hour < MARKET_OPEN_HOUR:
        return False
    return True


# ══════════════════════════════════════════════
#  1. جلب البيانات مع Retry ذكي
# ══════════════════════════════════════════════
def _fetch_history(symbol: str, period: str = "60d", max_retries: int = 4):
    for attempt in range(max_retries):
        try:
            df = yf.Ticker(symbol).history(period=period)
            if not df.empty:
                return df
            log.warning(f"[yfinance] لا بيانات للرمز {symbol} — السوق مغلق أو إجازة.")
            return None
        except Exception as e:
            wait = 2 ** attempt
            log.warning(f"[yfinance] محاولة {attempt+1}/{max_retries} للرمز {symbol} فشلت: {e} — انتظار {wait}s")
            time.sleep(wait)
    log.error(f"[yfinance] ❌ فشل تحميل {symbol} بعد {max_retries} محاولات.")
    return None


def _last_close(df) -> float | None:
    if df is None or df.empty:
        return None
    return float(df['Close'].iloc[-1])


# ══════════════════════════════════════════════
#  2. المؤشرات الفنية
# ══════════════════════════════════════════════
def calc_rsi(closes: np.ndarray, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes)
    gains  = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    return round(100 - (100 / (1 + avg_gain / avg_loss)), 2)


def calc_macd(closes: np.ndarray, fast=12, slow=26, signal=9):
    def ema(arr, n):
        k = 2 / (n + 1)
        result = [arr[0]]
        for v in arr[1:]:
            result.append(v * k + result[-1] * (1 - k))
        return np.array(result)
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
    mid    = np.mean(window)
    std    = np.std(window)
    return round(float(mid + std_dev * std), 2), round(float(mid), 2), round(float(mid - std_dev * std), 2)


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
    highs, lows, closes = df['High'].values, df['Low'].values, df['Close'].values
    tr_list = [max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
               for i in range(1, len(df))]
    return round(float(np.mean(tr_list[-period:])), 2)


# ══════════════════════════════════════════════
#  3. جلب كل بيانات السوق دفعة واحدة
# ══════════════════════════════════════════════
def get_full_market_data():
    symbols = {"gold": "GC=F", "silver": "SI=F", "oil": "CL=F",
               "dxy": "DX-Y.NYB", "tnx": "^TNX", "vix": "^VIX", "sp500": "^GSPC"}
    dfs = {}
    for key, sym in symbols.items():
        dfs[key] = _fetch_history(sym, period="60d")
        time.sleep(0.8)

    gold_df = dfs.get("gold")
    if gold_df is None or gold_df.empty:
        return None

    closes_gold = gold_df['Close'].values
    gold   = _last_close(dfs["gold"])
    silver = _last_close(dfs["silver"])
    oil    = _last_close(dfs["oil"])
    dxy    = _last_close(dfs["dxy"])
    tnx    = _last_close(dfs["tnx"])
    vix    = _last_close(dfs["vix"])
    sp500  = _last_close(dfs["sp500"])

    if not all([gold, dxy, tnx]):
        return None

    rsi                          = calc_rsi(closes_gold)
    macd, macd_sig, macd_hist    = calc_macd(closes_gold)
    bb_upper, bb_mid, bb_lower   = calc_bollinger(closes_gold)
    fib                          = calc_fibonacci(closes_gold)
    atr                          = calc_atr(gold_df)

    prev_high  = float(gold_df['High'].iloc[-2])
    prev_low   = float(gold_df['Low'].iloc[-2])
    prev_close = float(gold_df['Close'].iloc[-2])
    pivot = round((prev_high + prev_low + prev_close) / 3, 2)
    r1    = round(2 * pivot - prev_low, 2)
    r2    = round(pivot + (prev_high - prev_low), 2)
    r3    = round(prev_high + 2 * (pivot - prev_low), 2)
    s1    = round(2 * pivot - prev_high, 2)
    s2    = round(pivot - (prev_high - prev_low), 2)
    s3    = round(prev_low - 2 * (prev_high - pivot), 2)

    gs_ratio     = round(gold / silver, 1) if silver else None
    rsi_label    = "تشبع شراء 🔴" if rsi > 70 else ("تشبع بيع 🟢" if rsi < 30 else "محايد ⚪")
    macd_label   = "زخم صعودي 🟢" if macd_hist > 0 else "زخم هبوطي 🔴"
    vix_label    = "خوف شديد — ذهب مدعوم 🟢" if (vix and vix > 25) else ("توتر معتدل ⚠️" if (vix and vix > 18) else "هدوء 🔴")
    bb_label     = "قريب من السقف" if gold > bb_upper * 0.998 else ("قريب من القاع" if gold < bb_lower * 1.002 else "داخل النطاق")
    dxy_bias     = "قوي" if dxy > 104 else ("محايد" if dxy > 101 else "ضعيف")
    bond_bias    = "مرتفعة" if tnx > 4.3 else ("معتدلة" if tnx > 3.8 else "منخفضة")
    gold_pressure = "ضغط هبوطي" if (dxy > 104 or tnx > 4.5) else "زخم صعودي"

    return dict(
        gold=gold, silver=silver, oil=oil, dxy=dxy, tnx=tnx, vix=vix, sp500=sp500,
        rsi=rsi, rsi_label=rsi_label,
        macd=macd, macd_sig=macd_sig, macd_hist=macd_hist, macd_label=macd_label,
        bb_upper=bb_upper, bb_mid=bb_mid, bb_lower=bb_lower, bb_label=bb_label,
        atr=atr, pivot=pivot, r1=r1, r2=r2, r3=r3, s1=s1, s2=s2, s3=s3,
        fib=fib, gs_ratio=gs_ratio,
        buy_entry=round(s1, 2), buy_sl=round(s1 - 1.5 * atr, 2),
        buy_tp1=round(r1, 2), buy_tp2=round(r2, 2),
        short_entry=round(r1, 2), short_sl=round(r1 + 1.5 * atr, 2),
        short_tp1=round(s1, 2), short_tp2=round(s2, 2),
        dxy_bias=dxy_bias, bond_bias=bond_bias,
        gold_pressure=gold_pressure, vix_label=vix_label,
    )


# ══════════════════════════════════════════════
#  4. توليد التقرير بالذكاء الاصطناعي
# ══════════════════════════════════════════════
def generate_report(d: dict, is_alert: bool = False, price_diff: float = 0.0, is_morning: bool = False) -> str | None:
    client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
    if not client:
        return None

    date_now = cairo_now().strftime("%Y-%m-%d %H:%M قاهرة")

    if is_morning:
        header = "🌅 [نشرة الصباح — استراتيجية جلسة اليوم الكاملة]"
    elif is_alert:
        header = "🚨 [تنبيه سعري استثنائي — حركة حادة مرصودة الآن]"
    else:
        header = "📊 [نشرة التحليل الكمي الاستباقي للذهب]"

    alert_block = (
        f"\n🔔 الحركة المرصودة: {'+' if price_diff > 0 else ''}{price_diff:.2f}$ في آخر دورة.\n"
        if is_alert else ""
    )

    fib_table = "\n".join([f"   {k:7s} ▸ {v}$" for k, v in d['fib'].items()])

    system_prompt = """أنت كبير المحللين الكميين في صندوق تحوط عالمي من الدرجة الأولى.
مهمتك كتابة تقارير استباقية تنبؤية عن الذهب (XAU/USD) بمعايير بنوك الاستثمار العالمية.
قواعد صارمة:
- اكتب بالعربية الفصحى البسيطة فقط. لا كلمات إنجليزية إطلاقاً.
- كل جملة تخدم سؤالاً واحداً: "ماذا سيحدث تالياً؟"
- اشرح المؤشرات الفنية بأمثلة حياتية. المستخدم النهائي ليس متخصصاً.
- أصدر حكماً واضحاً وحاسماً. التردد لا قيمة له.
- الأرقام المعطاة محسوبة رياضياً — بنِ عليها فقط.
- استخدم فقرات قصيرة ومسافات بيضاء. التقرير يُقرأ على هاتف."""

    user_prompt = f"""{header}
🕐 وقت الرصد: {date_now}{alert_block}

━━━━━━━━━━━━━━━━━━━━━━━━
📡 لوحة البيانات اللحظية
━━━━━━━━━━━━━━━━━━━━━━━━
🥇 الذهب (XAU/USD)    : {d['gold']:.2f}$
🥈 الفضة (XAG/USD)    : {f"{d['silver']:.3f}$" if d['silver'] else 'غير متاح'}
🛢️ النفط (CL)          : {f"{d['oil']:.2f}$" if d['oil'] else 'غير متاح'}
💵 مؤشر الدولار (DXY)  : {d['dxy']:.2f} — {d['dxy_bias']}
📈 سندات الخزانة 10Y   : {d['tnx']:.2f}% — {d['bond_bias']}
😨 مؤشر الخوف (VIX)   : {f"{d['vix']:.2f} — {d['vix_label']}" if d['vix'] else 'غير متاح'}
📊 S&P 500              : {f"{d['sp500']:.0f}" if d['sp500'] else 'غير متاح'}
🔄 نسبة الذهب/الفضة    : {f"{d['gs_ratio']}:1" if d['gs_ratio'] else 'غير متاح'}
⚖️ الحكم الكمي السائد  : {d['gold_pressure']}

━━━━━━━━━━━━━━━━━━━━━━━━
🧮 المؤشرات الفنية
━━━━━━━━━━━━━━━━━━━━━━━━
📉 RSI (14)      : {d['rsi']} — {d['rsi_label']}
📊 MACD          : {d['macd']} | إشارة: {d['macd_sig']} | هيستوجرام: {d['macd_hist']} — {d['macd_label']}
📐 بولينجر      : سقف {d['bb_upper']}$ | وسط {d['bb_mid']}$ | قاع {d['bb_lower']}$ ({d['bb_label']})
📏 ATR (14)      : {d['atr']}$ — متوسط التقلب اليومي

━━━━━━━━━━━━━━━━━━━━━━━━
🎯 نقاط المحاور (Pivot)
━━━━━━━━━━━━━━━━━━━━━━━━
🔴 R3: {d['r3']}$ | 🟠 R2: {d['r2']}$ | 🟡 R1: {d['r1']}$
⚪ محور: {d['pivot']}$
🟢 S1: {d['s1']}$ | 🔵 S2: {d['s2']}$ | 🟣 S3: {d['s3']}$

━━━━━━━━━━━━━━━━━━━━━━━━
📐 فيبوناتشي (آخر 30 يوم)
━━━━━━━━━━━━━━━━━━━━━━━━
{fib_table}

━━━━━━━━━━━━━━━━━━━━━━━━
🎯 نقاط الدخول (محسوبة بـ ATR)
━━━━━━━━━━━━━━━━━━━━━━━━
📗 شراء: دخول {d['buy_entry']}$ | وقف {d['buy_sl']}$ | هدف1 {d['buy_tp1']}$ | هدف2 {d['buy_tp2']}$
📕 بيع : دخول {d['short_entry']}$ | وقف {d['short_sl']}$ | هدف1 {d['short_tp1']}$ | هدف2 {d['short_tp2']}$

━━━━━━━━━━━━━━━━━━━━━━━━
📝 التقرير الكامل — 5 أقسام
━━━━━━━━━━━━━━━━━━━━━━━━

**القسم الأول — المشهد الكلي (الماكرو)**
اربط بين الذهب والدولار والسندات وVIX والنفط. استخدم مثال الميزان للذهب والدولار. اشرح ماذا يقول VIX عن مزاج السوق الآن.

**القسم الثاني — قراءة المؤشرات الفنية**
اشرح RSI بمثال حياتي. اشرح MACD كـ"محرك سيارة". اشرح بولينجر كـ"أنبوب ضغط". أصدر حكماً فنياً واحداً حاسماً من المؤشرات الثلاثة.

**القسم الثالث — السيناريوهات الكمية**
📈 سيناريو الصعود (الشرط + الهدف + الاحتمال %):
📉 سيناريو الهبوط (الشرط + الهدف + الاحتمال %):
⚡ سيناريو التذبذب العرضي (متى ينتهي؟):

**القسم الرابع — نقاط الدخول للمتداول**
اشرح معنى "وقف الخسارة" بمثال من الحياة. ثم اشرح نقاط الدخول بلغة بسيطة.

**القسم الخامس — نصيحة للمستثمر الفيزيكال**
(3 جمل فقط — عملية ومباشرة بلا مصطلحات)

━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ تنويه قانوني إلزامي
━━━━━━━━━━━━━━━━━━━━━━━━
اختم بالنص التالي حرفياً:
"⚠️ تنويه قانوني: جميع المستويات والسيناريوهات الواردة في هذا التقرير هي نتاج نماذج كمية واحتمالية مبنية على تقاطعات السوق اللحظية. الأسعار المذكورة حقيقية ومباشرة من الأسواق العالمية. أما التحليلات والتوقعات فهي أداة مساعدة لصنع القرار وليست توصية مالية ملزمة بالبيع أو الشراء."
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
                temperature=0.12,
                max_tokens=2500,
            )
            log.info(f"✅ نجح الاتصال مع الموديل: {model_name}")
            return resp.choices[0].message.content
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate_limit" in err_str.lower():
                log.warning(f"⚠️ [{model_name}] وصل للحد الأقصى (429) — الانتقال للموديل التالي...")
                time.sleep(2)
                continue
            else:
                log.error(f"❌ [{model_name}] خطأ غير متوقع: {e}")
                break
    log.error("❌ جميع الموديلات فشلت.")
    return None


# ══════════════════════════════════════════════
#  5. إرسال تيليجرام — Telethon MTProto أولاً ثم HTTP fallback
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
    """إرسال عبر Telethon باستخدام Bot Token — يصل للـ chat الصحيح."""
    try:
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.start(bot_token=TELEGRAM_BOT_TOKEN)
        await client.send_message(TELEGRAM_CHAT_ID, text)
        await client.disconnect()
        return True
    except Exception as e:
        log.warning(f"⚠️ [Telethon Bot] فشل الإرسال عبر MTProto: {e}")
        return False


def _http_send(text: str) -> bool:
    """Fallback: HTTP Bot API."""
    url     = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": str(TELEGRAM_CHAT_ID), "text": text}
    headers = {"Connection": "close"}
    for attempt in range(3):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=(5, 20))
            r.raise_for_status()
            return True
        except Exception as e:
            log.warning(f"⚠️ [HTTP API] محاولة {attempt+1}/3 — {e}")
            time.sleep(2 ** attempt)
    return False


def _send_single(text: str) -> bool:
    """يجرب Telethon أولاً، ثم HTTP API كـ fallback."""
    try:
        result = asyncio.run(_telethon_send(text))
        if result:
            log.info("✅ [Telethon] تم الإرسال عبر MTProto بنجاح.")
            return True
    except RuntimeError:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_telethon_send(text))
            loop.close()
            if result:
                log.info("✅ [Telethon] تم الإرسال (new loop) بنجاح.")
                return True
        except Exception as e:
            log.warning(f"⚠️ [Telethon loop] {e}")
    except Exception as e:
        log.warning(f"⚠️ [Telethon] {e}")

    log.info("🔄 [Goldbot] جاري المحاولة عبر HTTP API...")
    return _http_send(text)


def send_to_telegram(message: str) -> bool:
    if not message:
        return False
    chunks = _split_message(message)
    log.info(f"📤 إرسال التقرير في {len(chunks)} جزء...")
    all_ok = True
    for i, chunk in enumerate(chunks, 1):
        prefix = f"[{i}/{len(chunks)}] " if len(chunks) > 1 else ""
        ok = _send_single(prefix + chunk)
        if ok:
            log.info(f"✅ الجزء {i}/{len(chunks)} وصل بنجاح.")
        else:
            log.error(f"❌ فشل إرسال الجزء {i}/{len(chunks)}.")
            all_ok = False
        if i < len(chunks):
            time.sleep(1.5)
    return all_ok


# ══════════════════════════════════════════════
#  6. الحلقة الرئيسية — متكاملة ومحكمة
# ══════════════════════════════════════════════
def run_bot():
    log.info("🚀 Goldbot Ultra بدأ العمل بنظام التحليل الكمي المتكامل...")

    last_gold_price      = None
    minutes_counter      = 0
    morning_sent_today   = False
    closing_sent_today   = False
    heartbeat_sent_today = False
    all_models_notified  = False
    last_report_date     = None   # منع التقرير الافتتاحي المكرر عند إعادة التشغيل
    consec_failures      = 0      # عداد الفشل المتتالي

    day_names = ["اثنين", "ثلاثاء", "أربعاء", "خميس", "جمعة", "سبت", "أحد"]

    while True:
        now_cairo  = cairo_now()
        today      = now_cairo.date()
        hour_cairo = now_cairo.hour
        weekday    = now_cairo.weekday()

        # ── إعادة ضبط الحالات اليومية عند بداية يوم جديد ──
        if last_report_date != today:
            morning_sent_today   = False
            closing_sent_today   = False
            heartbeat_sent_today = False
            all_models_notified  = False

        # ── سوق مغلق — انتظر 30 دقيقة ──
        if not is_market_open():
            log.info(f"🛌 سوق الذهب مغلق ({day_names[weekday]} {hour_cairo:02d}:00 قاهرة). محاولة بعد 30 دقيقة.")
            last_gold_price = None   # سيُرسل تقرير افتتاحي عند فتح السوق
            time.sleep(30 * 60)
            continue

        data = get_full_market_data()

        if data and data["gold"]:
            consec_failures     = 0
            all_models_notified = False
            current_gold        = data["gold"]

            # ── تقرير افتتاحي — مرة واحدة فقط لكل يوم عند فتح السوق ──
            if last_gold_price is None and last_report_date != today:
                log.info("📊 إرسال التقرير الافتتاحي...")
                report = generate_report(data, is_alert=False)
                if report:
                    send_to_telegram(report)
                last_gold_price  = current_gold
                last_report_date = today
                minutes_counter  = 0

            # ── Heartbeat يومي عند الظهر ──
            elif hour_cairo == HEARTBEAT_HOUR and not heartbeat_sent_today:
                send_to_telegram(
                    f"💚 [Goldbot Heartbeat] البوت يعمل بشكل طبيعي ✔️\n"
                    f"📊 ذهب: {current_gold:.2f}$ — {now_cairo.strftime('%H:%M قاهرة')}"
                )
                heartbeat_sent_today = True
                log.info("💚 Heartbeat تم إرساله.")

            # ── تقرير الصباح ──
            elif hour_cairo == MORNING_HOUR_CAI and not morning_sent_today:
                log.info("🌅 إرسال تقرير استراتيجية الصباح...")
                report = generate_report(data, is_alert=False, is_morning=True)
                if report:
                    send_to_telegram(report)
                    morning_sent_today = True
                    last_gold_price    = current_gold
                    minutes_counter    = 0

            # ── تقرير نهاية الجلسة ──
            elif hour_cairo == CLOSING_HOUR_CAI and not closing_sent_today:
                log.info("🌙 إرسال ملخص جلسة اليوم...")
                report = generate_report(data, is_alert=False)
                if report:
                    send_to_telegram("🌙 [ملخص جلسة اليوم — تقرير نهائي]\n" + report)
                    closing_sent_today = True
                    last_gold_price    = current_gold
                    minutes_counter    = 0

            else:
                price_diff = current_gold - (last_gold_price or current_gold)

                # ── تنبيه التحرك الحاد ──
                if abs(price_diff) >= ALERT_THRESHOLD:
                    log.info(f"🚨 تحرك حاد! {price_diff:+.2f}$ — إرسال تنبيه...")
                    report = generate_report(data, is_alert=True, price_diff=price_diff)
                    if report:
                        send_to_telegram(report)
                        last_gold_price = current_gold
                        minutes_counter = 0

                # ── التقرير الروتيني كل ساعة ──
                elif minutes_counter >= ROUTINE_MINUTES:
                    log.info(f"⏰ مرت {ROUTINE_MINUTES} دقيقة — إرسال التقرير الدوري...")
                    report = generate_report(data, is_alert=False)
                    if report:
                        send_to_telegram(report)
                        last_gold_price = current_gold
                        minutes_counter = 0

        else:
            consec_failures += 1
            log.warning(f"⚠️ فشل جلب البيانات للمرة {consec_failures} على التوالي.")
            # ── إشعار عند 3 فشل متتالي ──
            if consec_failures >= 3 and not all_models_notified:
                send_to_telegram(
                    "🚨 تحذير — جولدبوت يواجه مشكلة!\n"
                    "جميع موديلات الذكاء الاصطناعي وصلت للحد الأقصى أو فشل الاتصال.\n"
                    "سيتم إعادة المحاولة تلقائياً. لا يوجد تدخل مطلوب."
                )
                all_models_notified = True

        time.sleep(60)
        minutes_counter += 1


# Note: run_bot() is called by the root main.py orchestrator as a background thread.