import yfinance as yf
from groq import Groq
import requests
from datetime import datetime
import time
import os
import logging
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
log = logging.getLogger(__name__)

# ================= الإعدادات =================
GROQ_API_KEY       = os.environ.get("GROQ_API_KEY")
TELEGRAM_BOT_TOKEN = "8678714877:AAE2v6jeeYzsNFYj_83rXK32RJEA7fszQew"
TELEGRAM_CHAT_ID   = "7737655407"

ALERT_THRESHOLD  = 6.0   # دولارات — تنبيه فوري عند هذا التحرك
ROUTINE_MINUTES  = 60    # تقرير روتيني كل ساعة
MORNING_HOUR     = 9     # تقرير الصباح في الساعة 9 صباحاً بتوقيت الخادم
# ==============================================


# ══════════════════════════════════════════════
#  1. جلب البيانات مع Retry ذكي
# ══════════════════════════════════════════════
def _fetch_history(symbol: str, period: str = "60d", max_retries: int = 4):
    """إرجاع DataFrame كامل مع backoff أسي."""
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
#  2. المؤشرات الفنية المحسوبة بـ Python
# ══════════════════════════════════════════════
def calc_rsi(closes: np.ndarray, period: int = 14) -> float:
    """مؤشر RSI — قياس حالة التشبع."""
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
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def calc_macd(closes: np.ndarray, fast=12, slow=26, signal=9):
    """إرجاع (macd_line, signal_line, histogram)."""
    def ema(arr, n):
        k = 2 / (n + 1)
        result = [arr[0]]
        for v in arr[1:]:
            result.append(v * k + result[-1] * (1 - k))
        return np.array(result)
    if len(closes) < slow + signal:
        return 0.0, 0.0, 0.0
    ema_fast   = ema(closes, fast)
    ema_slow   = ema(closes, slow)
    macd_line  = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram  = macd_line - signal_line
    return round(float(macd_line[-1]), 4), round(float(signal_line[-1]), 4), round(float(histogram[-1]), 4)


def calc_bollinger(closes: np.ndarray, period: int = 20, std_dev: float = 2.0):
    """إرجاع (upper, middle, lower)."""
    if len(closes) < period:
        c = closes[-1]
        return c, c, c
    window = closes[-period:]
    mid    = np.mean(window)
    std    = np.std(window)
    return round(float(mid + std_dev * std), 2), round(float(mid), 2), round(float(mid - std_dev * std), 2)


def calc_fibonacci(closes: np.ndarray, lookback: int = 30):
    """مستويات فيبوناتشي على أعلى وأدنى سعر في آخر N شمعة."""
    if len(closes) < lookback:
        lookback = len(closes)
    window = closes[-lookback:]
    high   = float(np.max(window))
    low    = float(np.min(window))
    diff   = high - low
    levels = {
        "0.0%"  : round(high, 2),
        "23.6%" : round(high - 0.236 * diff, 2),
        "38.2%" : round(high - 0.382 * diff, 2),
        "50.0%" : round(high - 0.500 * diff, 2),
        "61.8%" : round(high - 0.618 * diff, 2),
        "78.6%" : round(high - 0.786 * diff, 2),
        "100%"  : round(low, 2),
    }
    return levels


def calc_atr(df, period: int = 14) -> float:
    """Average True Range — قياس التقلب الحقيقي."""
    if df is None or len(df) < period + 1:
        return 0.0
    highs  = df['High'].values
    lows   = df['Low'].values
    closes = df['Close'].values
    tr_list = []
    for i in range(1, len(df)):
        tr = max(highs[i] - lows[i],
                 abs(highs[i] - closes[i-1]),
                 abs(lows[i]  - closes[i-1]))
        tr_list.append(tr)
    return round(float(np.mean(tr_list[-period:])), 2)


# ══════════════════════════════════════════════
#  3. جلب كل بيانات السوق دفعة واحدة
# ══════════════════════════════════════════════
def get_full_market_data():
    """إرجاع dict كامل بكل المؤشرات أو None عند الفشل."""
    symbols = {
        "gold"  : "GC=F",
        "silver": "SI=F",
        "oil"   : "CL=F",
        "dxy"   : "DX-Y.NYB",
        "tnx"   : "^TNX",
        "vix"   : "^VIX",
        "sp500" : "^GSPC",
    }

    dfs = {}
    for key, sym in symbols.items():
        df = _fetch_history(sym, period="60d")
        dfs[key] = df
        time.sleep(0.8)  # تجنب rate-limit

    gold_df = dfs.get("gold")
    if gold_df is None or gold_df.empty:
        return None

    closes_gold = gold_df['Close'].values

    # ── أسعار لحظية ──
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
    rsi              = calc_rsi(closes_gold)
    macd, macd_sig, macd_hist = calc_macd(closes_gold)
    bb_upper, bb_mid, bb_lower = calc_bollinger(closes_gold)
    fib              = calc_fibonacci(closes_gold)
    atr              = calc_atr(gold_df)

    # ── مستويات الدعم والمقاومة الكلاسيكية (Pivot Points) ──
    prev_high  = float(gold_df['High'].iloc[-2])
    prev_low   = float(gold_df['Low'].iloc[-2])
    prev_close = float(gold_df['Close'].iloc[-2])
    pivot      = round((prev_high + prev_low + prev_close) / 3, 2)
    r1         = round(2 * pivot - prev_low, 2)
    r2         = round(pivot + (prev_high - prev_low), 2)
    r3         = round(prev_high + 2 * (pivot - prev_low), 2)
    s1         = round(2 * pivot - prev_high, 2)
    s2         = round(pivot - (prev_high - prev_low), 2)
    s3         = round(prev_low - 2 * (prev_high - pivot), 2)

    # ── نقاط الدخول المثلى (بناءً على ATR) ──
    buy_entry   = round(s1, 2)
    buy_sl      = round(s1 - 1.5 * atr, 2)
    buy_tp1     = round(r1, 2)
    buy_tp2     = round(r2, 2)
    short_entry = round(r1, 2)
    short_sl    = round(r1 + 1.5 * atr, 2)
    short_tp1   = round(s1, 2)
    short_tp2   = round(s2, 2)

    # ── نسبة الذهب/الفضة (Gold-Silver Ratio) ──
    gs_ratio = round(gold / silver, 1) if silver else None

    # ── قراءات نصية ──
    rsi_label  = "تشبع شراء 🔴" if rsi > 70 else ("تشبع بيع 🟢" if rsi < 30 else "منطقة محايدة ⚪")
    macd_label = "زخم صعودي 🟢" if macd_hist > 0 else "زخم هبوطي 🔴"
    vix_label  = "خوف شديد — ذهب مدعوم 🟢" if (vix and vix > 25) else ("توتر معتدل ⚠️" if (vix and vix > 18) else "هدوء — شهية مخاطرة 🔴")
    bb_label   = "قريب من السقف" if gold > bb_upper * 0.998 else ("قريب من القاع" if gold < bb_lower * 1.002 else "داخل النطاق")
    dxy_bias   = "قوي" if dxy > 104 else ("محايد" if dxy > 101 else "ضعيف")
    bond_bias  = "مرتفعة" if tnx > 4.3 else ("معتدلة" if tnx > 3.8 else "منخفضة")
    gold_pressure = "ضغط هبوطي" if (dxy > 104 or tnx > 4.5) else "زخم صعودي"

    return {
        # أسعار
        "gold": gold, "silver": silver, "oil": oil,
        "dxy": dxy, "tnx": tnx, "vix": vix, "sp500": sp500,
        # مؤشرات فنية
        "rsi": rsi, "rsi_label": rsi_label,
        "macd": macd, "macd_sig": macd_sig, "macd_hist": macd_hist, "macd_label": macd_label,
        "bb_upper": bb_upper, "bb_mid": bb_mid, "bb_lower": bb_lower, "bb_label": bb_label,
        "atr": atr,
        # pivot points
        "pivot": pivot, "r1": r1, "r2": r2, "r3": r3, "s1": s1, "s2": s2, "s3": s3,
        # فيبوناتشي
        "fib": fib,
        # نقاط دخول
        "buy_entry": buy_entry, "buy_sl": buy_sl, "buy_tp1": buy_tp1, "buy_tp2": buy_tp2,
        "short_entry": short_entry, "short_sl": short_sl, "short_tp1": short_tp1, "short_tp2": short_tp2,
        # نسب وتحيزات
        "gs_ratio": gs_ratio,
        "dxy_bias": dxy_bias, "bond_bias": bond_bias,
        "gold_pressure": gold_pressure, "vix_label": vix_label,
    }


# ══════════════════════════════════════════════
#  4. توليد التقرير بالذكاء الاصطناعي
# ══════════════════════════════════════════════
def generate_report(d: dict, is_alert: bool = False, price_diff: float = 0.0, is_morning: bool = False) -> str | None:
    client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
    if not client:
        return None

    date_now = datetime.now().strftime("%Y-%m-%d %H:%M")

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

    # بناء جدول فيبوناتشي
    fib_table = "\n".join([f"   {k:7s} ▸ {v}$" for k, v in d['fib'].items()])

    system_prompt = """أنت كبير المحللين الكميين (Quantitative Strategist) في صندوق تحوط عالمي من الدرجة الأولى.
مهمتك كتابة تقارير استباقية تنبؤية عن الذهب (XAU/USD) بمعايير بنوك الاستثمار العالمية الكبرى.

قواعد صارمة لا تُكسر أبداً:
- اكتب بالعربية الفصحى البسيطة فقط. لا كلمات إنجليزية داخل التحليل إطلاقاً.
- كل جملة يجب أن تخدم سؤالاً واحداً فقط: "ماذا سيحدث تالياً؟"
- اشرح المؤشرات الفنية بأمثلة حياتية. المستخدم النهائي ليس متخصصاً.
- لا تتردد في إصدار حكم واضح وحاسم. التردد لا قيمة له.
- الأرقام المعطاة لك محسوبة رياضياً وهي حقيقية — بنِ عليها ولا تخترع أرقاماً جديدة.
- استخدم الفقرات القصيرة والمسافات البيضاء والرموز. التقرير يُقرأ على شاشة هاتف."""

    user_prompt = f"""{header}
🕐 وقت الرصد: {date_now} (UTC){alert_block}

━━━━━━━━━━━━━━━━━━━━━━━━
📡 لوحة البيانات اللحظية الكاملة
━━━━━━━━━━━━━━━━━━━━━━━━
🥇 الذهب الفوري (XAU/USD)  : {d['gold']:.2f}$
🥈 الفضة الفورية (XAG/USD)  : {f"{d['silver']:.3f}$" if d['silver'] else 'غير متاح'}
🛢️ خام برنت / نايمكس (CL)   : {f"{d['oil']:.2f}$" if d['oil'] else 'غير متاح'}
💵 مؤشر الدولار (DXY)        : {d['dxy']:.2f} — {d['dxy_bias']}
📈 عوائد سندات الخزانة 10Y   : {d['tnx']:.2f}% — {d['bond_bias']}
😨 مؤشر الخوف (VIX)          : {f"{d['vix']:.2f} — {d['vix_label']}" if d['vix'] else 'غير متاح'}
📊 مؤشر S&P 500               : {f"{d['sp500']:.0f}" if d['sp500'] else 'غير متاح'}
🔄 نسبة الذهب / الفضة         : {f"{d['gs_ratio']}:1" if d['gs_ratio'] else 'غير متاح'}
⚖️ الحكم الكمي السائد          : {d['gold_pressure']}

━━━━━━━━━━━━━━━━━━━━━━━━
🧮 المؤشرات الفنية المحسوبة
━━━━━━━━━━━━━━━━━━━━━━━━
📉 RSI (14)       : {d['rsi']} — {d['rsi_label']}
📊 MACD           : {d['macd']} | إشارة: {d['macd_sig']} | هيستوجرام: {d['macd_hist']} — {d['macd_label']}
📐 بولينجر باندز  : سقف {d['bb_upper']}$ | وسط {d['bb_mid']}$ | قاع {d['bb_lower']}$ ({d['bb_label']})
📏 ATR (14 يوم)   : {d['atr']}$ — متوسط التقلب اليومي الحقيقي

━━━━━━━━━━━━━━━━━━━━━━━━
🎯 نقاط المحاور الكلاسيكية (Pivot Points)
━━━━━━━━━━━━━━━━━━━━━━━━
🔴 مقاومة ثالثة (R3) : {d['r3']}$
🟠 مقاومة ثانية (R2) : {d['r2']}$
🟡 مقاومة أولى  (R1) : {d['r1']}$
⚪ المحور المحوري    : {d['pivot']}$
🟢 دعم أول      (S1) : {d['s1']}$
🔵 دعم ثاني     (S2) : {d['s2']}$
🟣 دعم ثالث     (S3) : {d['s3']}$

━━━━━━━━━━━━━━━━━━━━━━━━
📐 مستويات فيبوناتشي (آخر 30 يوم)
━━━━━━━━━━━━━━━━━━━━━━━━
{fib_table}

━━━━━━━━━━━━━━━━━━━━━━━━
🎯 نقاط الدخول المثلى (محسوبة بـ ATR)
━━━━━━━━━━━━━━━━━━━━━━━━
📗 صفقة شراء (BUY):
   دخول عند  : {d['buy_entry']}$
   وقف خسارة : {d['buy_sl']}$ (1.5× ATR تحت الدعم)
   هدف أول   : {d['buy_tp1']}$
   هدف ثاني  : {d['buy_tp2']}$

📕 صفقة بيع (SELL):
   دخول عند  : {d['short_entry']}$
   وقف خسارة : {d['short_sl']}$ (1.5× ATR فوق المقاومة)
   هدف أول   : {d['short_tp1']}$
   هدف ثاني  : {d['short_tp2']}$

━━━━━━━━━━━━━━━━━━━━━━━━
📝 المطلوب منك — التقرير الكامل في 5 أقسام
━━━━━━━━━━━━━━━━━━━━━━━━

**القسم الأول — قراءة المشهد الكلي (الماكرو)**
اربط بين الذهب والدولار والسندات وVIX والنفط في فقرة واحدة متماسكة. استخدم مثال الميزان للذهب والدولار. اشرح ماذا يقول VIX عن مزاج السوق الآن.

**القسم الثاني — قراءة المؤشرات الفنية**
اشرح RSI بمثال حياتي (كأن السوق "مرهق" أو "مستعد للانطلاق"). اشرح MACD كـ"محرك السيارة". اشرح بولينجر كـ"أنبوب" يضغط السعر. استنتج من المؤشرات الثلاثة معاً حكماً فنياً واحداً حاسماً.

**القسم الثالث — خريطة السيناريوهات الكمية**
بناءً على الأرقام المحسوبة أعلاه، اكتب بوضوح تام:

📈 سيناريو الصعود (الشرط + الهدف + الاحتمال المقدر %):
اذكر شرط تفعيله بدقة (أي رقم يجب كسره)، وهدفه، ولماذا هذا الرقم تحديداً.

📉 سيناريو الهبوط (الشرط + الهدف + الاحتمال المقدر %):
اذكر شرط تفعيله بدقة، وهدفه، والإشارات التحذيرية.

⚡ سيناريو التذبذب العرضي:
متى يظل السعر عالقاً بين مستويين؟ وما العلامة التي تنهيه؟

**القسم الرابع — نقاط الدخول والمخاطرة**
اشرح لغير المتخصص معنى "وقف الخسارة" بمثال من الحياة اليومية. ثم اشرح نقاط الدخول المحسوبة أعلاه بلغة بسيطة: "إذا نزل الذهب إلى X فهذه فرصة شراء محسوبة، وإذا صعد إلى Y فهذه إشارة بيع."

**القسم الخامس — نصيحة اليوم للمستثمر الفيزيكال**
(3 جمل فقط — عملية ومباشرة بلا مصطلحات)
ماذا يفعل الشخص الذي يريد شراء ذهب فيزيكال أو سبائك من الصائغ أو البنك الآن؟

━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ إخلاء المسؤولية الإلزامي
━━━━━━━━━━━━━━━━━━━━━━━━
اختم بالنص التالي حرفياً:
"⚠️ تنويه قانوني: جميع المستويات والسيناريوهات الواردة في هذا التقرير هي نتاج نماذج كمية واحتمالية مبنية على تقاطعات السوق اللحظية. الأسعار المذكورة حقيقية ومباشرة من الأسواق العالمية. أما التحليلات والتوقعات فهي أداة مساعدة لصنع القرار وليست توصية مالية ملزمة بالبيع أو الشراء."
"""

    try:
        resp = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.12,
            max_tokens=3000,
        )
        return resp.choices[0].message.content
    except Exception as e:
        log.warning(f"⚠️ خطأ في Groq API: {e}")
        return None


# ══════════════════════════════════════════════
#  5. إرسال تيليجرام مع Retry
# ══════════════════════════════════════════════
def send_to_telegram(message: str, max_retries: int = 5) -> bool:
    url        = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    safe_msg   = message[:4000] if message else ""
    payload    = {"chat_id": TELEGRAM_CHAT_ID, "text": safe_msg}
    headers    = {"Connection": "close"}

    for attempt in range(max_retries):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=45)
            r.raise_for_status()
            log.info(f"✅ تم إرسال التقرير بنجاح لتيليجرام.")
            return True
        except requests.exceptions.SSLError as e:
            wait = 2 ** attempt
            log.warning(f"⚠️ [SSL] محاولة {attempt+1}/{max_retries} — انتظار {wait}s...")
            time.sleep(wait)
        except Exception as e:
            wait = 2 ** attempt
            log.warning(f"⚠️ [Telegram ERR] محاولة {attempt+1}/{max_retries} — {e} — انتظار {wait}s...")
            time.sleep(wait)
    log.error(f"❌ فشل إرسال التقرير نهائياً بعد {max_retries} محاولات.")
    return False


# ══════════════════════════════════════════════
#  6. الحلقة الرئيسية
# ══════════════════════════════════════════════
def run_bot():
    log.info("🚀 Goldbot Ultra بدأ العمل بنظام التحليل الكمي المتكامل...")
    last_gold_price  = None
    minutes_counter  = 0
    morning_sent_today = False

    while True:
        now  = datetime.utcnow()
        hour = now.hour

        # إعادة ضبط تقرير الصباح كل يوم جديد
        if hour == 0:
            morning_sent_today = False

        data = get_full_market_data()

        if data and data["gold"]:
            current_gold = data["gold"]

            # ── التقرير الافتتاحي عند أول تشغيل ──
            if last_gold_price is None:
                log.info("📊 إرسال التقرير الافتتاحي...")
                last_gold_price = current_gold
                report = generate_report(data, is_alert=False)
                if report:
                    send_to_telegram(report)
                minutes_counter = 0

            # ── تقرير الصباح ──
            elif hour == MORNING_HOUR and not morning_sent_today:
                log.info("🌅 إرسال تقرير استراتيجية الصباح...")
                report = generate_report(data, is_alert=False, is_morning=True)
                if report:
                    send_to_telegram(report)
                    morning_sent_today = True
                    last_gold_price   = current_gold
                    minutes_counter   = 0

            else:
                price_diff = current_gold - last_gold_price

                # ── تنبيه التحرك الحاد ──
                if abs(price_diff) >= ALERT_THRESHOLD:
                    log.info(f"🚨 تحرك حاد! {price_diff:+.2f}$ — إرسال تنبيه فوري...")
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
            log.warning("⚠️ لم يتم الحصول على بيانات في هذه الدورة. المحاولة مجدداً...")

        time.sleep(60)
        minutes_counter += 1