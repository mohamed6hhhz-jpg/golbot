import time
import logging
from datetime import datetime
import os
import sys
import numpy as np

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("Goldbot.bot_9")

try:
    import pytz
    CAIRO_TZ = pytz.timezone("Africa/Cairo")
except ImportError:
    from datetime import timezone, timedelta
    CAIRO_TZ = timezone(timedelta(hours=3))

def cairo_now() -> datetime:
    return datetime.now(CAIRO_TZ)

def calc_ema(closes: np.ndarray, period: int) -> float:
    if len(closes) < period:
        return closes[-1]
    k = 2 / (period + 1)
    ema = np.mean(closes[:period])
    for price in closes[period:]:
        ema = (price - ema) * k + ema
    return round(float(ema), 2)

def analyze_trend_and_correction() -> dict | None:
    try:
        from Goldbot.bot_spot import _fetch
        from Goldbot.bot_daily_levels import fetch_daily_data
    except ImportError:
        try:
            from bot_spot import _fetch
            from bot_daily_levels import fetch_daily_data
        except ImportError:
            log.error("❌ فشل استدعاء الملفات المطلوبة في Bot 9.")
            return None

    # Fetch daily data for spot price
    daily_data = fetch_daily_data()
    if not daily_data:
        return None
        
    spot_price = daily_data.get("spot_price") or daily_data.get("prev_close")
    
    # Fetch Hourly data for Trend & Swings
    df_1h = _fetch("GC=F", period="15d", interval="1h")
    if df_1h is None or len(df_1h) < 200:
        log.error("❌ بيانات الساعة غير كافية لحساب الاتجاه والتصحيح.")
        return None

    closes = df_1h['Close'].dropna().values
    highs = df_1h['High'].dropna().values
    lows = df_1h['Low'].dropna().values

    # Trend using EMAs
    ema_50 = calc_ema(closes, 50)
    ema_200 = calc_ema(closes, 200)

    # Swings over the last 72 hours (approx 3 days)
    lookback = min(72, len(highs))
    swing_high = float(np.max(highs[-lookback:]))
    swing_low = float(np.min(lows[-lookback:]))
    swing_dist = swing_high - swing_low

    if swing_dist == 0:
        return None

    # Determine Trend
    if ema_50 > ema_200:
        trend = "صاعد 📈"
        trend_en = "UP"
        # In Uptrend, correction is downwards to Fib support
        fib_38 = swing_high - (0.382 * swing_dist)
        fib_50 = swing_high - (0.500 * swing_dist)
        fib_61 = swing_high - (0.618 * swing_dist)
        
        correction_start = fib_38
        correction_end = fib_61
        correction_target = "الدعم"
    else:
        trend = "هابط 📉"
        trend_en = "DOWN"
        # In Downtrend, correction is upwards to Fib resistance
        fib_38 = swing_low + (0.382 * swing_dist)
        fib_50 = swing_low + (0.500 * swing_dist)
        fib_61 = swing_low + (0.618 * swing_dist)
        
        correction_start = fib_38
        correction_end = fib_61
        correction_target = "المقاومة"

    # Timing analysis
    now_hour = cairo_now().hour
    if 10 <= now_hour < 15:
        timing_msg = "في توقيت السيولة الأوروبية (لندن)، غالباً يبدأ التصحيح هنا أو يستمر."
        timing_status = "⚠️ توقيت سيولة عالية"
    elif 15 <= now_hour < 19:
        timing_msg = "في توقيت السيولة المزدوجة (لندن وأمريكا)، تبلغ التصحيحات ذروتها أو تنتهي لصالح الاتجاه العام."
        timing_status = "🔥 ذروة السيولة"
    elif 19 <= now_hour < 23:
        timing_msg = "في جلسة نيويورك المسائية، غالباً ما يعود السعر للاتجاه العام بعد انتهاء التصحيح."
        timing_status = "📉 هدوء نسبي واستقرار"
    else:
        timing_msg = "في الجلسة الآسيوية، السعر يتحرك في نطاق ضيق ويمهد لحركة اليوم التالي."
        timing_status = "🌙 جلسة هادئة"

    # State of current price compared to correction
    if trend_en == "UP":
        if spot_price > swing_high:
            price_state = "السعر يحقق قمم جديدة (يواصل الصعود بقوة)."
        elif spot_price < fib_61:
            price_state = "السعر كسر منطقة التصحيح لأسفل (خطر انعكاس الاتجاه تماماً)."
        elif fib_61 <= spot_price <= fib_38:
            price_state = "السعر حالياً **داخل المنطقة الذهبية للتصحيح** (فرصة للارتداد صعوداً)."
        else:
            price_state = "السعر يهبط نحو منطقة التصحيح."
    else:
        if spot_price < swing_low:
            price_state = "السعر يحقق قيعان جديدة (يواصل الهبوط بقوة)."
        elif spot_price > fib_61:
            price_state = "السعر كسر منطقة التصحيح لأعلى (خطر انعكاس الاتجاه تماماً)."
        elif fib_38 <= spot_price <= fib_61:
            price_state = "السعر حالياً **داخل المنطقة الذهبية للتصحيح** (فرصة للارتداد هبوطاً)."
        else:
            price_state = "السعر يصعد نحو منطقة التصحيح."

    return {
        "spot_price": spot_price,
        "trend": trend,
        "ema_50": ema_50,
        "ema_200": ema_200,
        "swing_high": round(swing_high, 2),
        "swing_low": round(swing_low, 2),
        "fib_38": round(fib_38, 2),
        "fib_50": round(fib_50, 2),
        "fib_61": round(fib_61, 2),
        "correction_start": round(correction_start, 2),
        "correction_end": round(correction_end, 2),
        "correction_target": correction_target,
        "timing_msg": timing_msg,
        "timing_status": timing_status,
        "price_state": price_state
    }

def build_template_trend_correction(data: dict) -> str:
    """
    يبني القالب الخاص بتحديد الاتجاه ومناطق وتوقيت التصحيح.
    """
    if not data:
        return "⚠️ بيانات الاتجاه والتصحيح غير متوفرة حالياً."

    send_time = cairo_now().strftime("%I:%M %p")
    
    report = f"""[1/7] 🧭 رادار الاتجاه والتصحيحات (Trend & Retracement)
📈 تحليل دقيق للاتجاه العام ومناطق الارتداد المتوقعة

━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ السعر الفوري (لحظة الإرسال): {data['spot_price']}$ — {send_time} القاهرة
🧭 الاتجاه العام الحالي: {data['trend']}
   (مبني على تقاطع المتوسطات EMA 50 / 200)
═════════════════════════════
🌊 موجة السوينج الحالية (الأيام الثلاثة الماضية):
   🔺 قمة الموجة: {data['swing_high']}$
   🔻 قاع الموجة: {data['swing_low']}$
═════════════════════════════
🎯 خريطة التصحيح المؤقت (Retracement Zone):
   بما أن الاتجاه {data['trend']}، إذا قرر الذهب التصحيح فإنه سيتجه نحو {data['correction_target']} لاختبار مناطق السيولة الذهبية قبل استكمال مساره.
   
   ✨ المنطقة الذهبية للتصحيح (فيبوناتشي 38.2% - 61.8%):
   بداية منطقة التصحيح: {data['correction_start']}$
   عمق منطقة التصحيح: {data['fib_50']}$
   نهاية منطقة التصحيح: {data['correction_end']}$
   
   ⚠️ كسر النقطة ({data['correction_end']}$) يُعتبر إنذاراً بتغيير الاتجاه بالكامل وليس مجرد تصحيح!
═════════════════════════════
📍 وضع السعر الآن:
   {data['price_state']}
═════════════════════════════
⏳ توقيت التصحيح وحالة السيولة:
   وضع السوق الآن: {data['timing_status']}
   💡 {data['timing_msg']}
━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 خلاصة التداول:
لا تتداول عكس الاتجاه العام ({data['trend']})، بل انتظر السعر ليهبط/يصعد إلى "المنطقة الذهبية للتصحيح" وادخل مع الاتجاه فور ظهور إشارات الارتداد منها.
"""
    return report

def analyze_exhaustion() -> dict | None:
    """
    تحليل علامات الإرهاق ونهاية الاتجاه الكبير بناءً على:
    1. التشبع (RSI)
    2. الابتعاد عن المتوسطات (Overextension من EMA 200)
    3. التباين (Divergence البسيط)
    """
    try:
        from Goldbot.bot_spot import _fetch, calc_rsi
    except ImportError:
        try:
            from bot_spot import _fetch, calc_rsi
        except ImportError:
            return None

    # فريم يومي لاكتشاف التشبعات الكبرى
    df_1d = _fetch("GC=F", period="2y", interval="1d")
    if df_1d is None or len(df_1d) < 250:
        return None

    closes = df_1d['Close'].dropna().values
    highs = df_1d['High'].dropna().values
    
    current_price = closes[-1]
    
    # 1. RSI
    rsi_14 = calc_rsi(closes, 14)
    
    # 2. Overextension (EMA 200)
    ema_200 = calc_ema(closes, 200)
    distance_pct = ((current_price - ema_200) / ema_200) * 100
    
    # 3. Simple Divergence detection
    # هل السعر صنع قمة جديدة مؤخراً بينما الـ RSI لم يصنع؟
    recent_high_price = np.max(highs[-10:])
    older_high_price = np.max(highs[-30:-10])
    
    recent_rsi = calc_rsi(closes[-10:], 14) if len(closes[-10:])>=14 else rsi_14
    older_rsi = calc_rsi(closes[-30:-10], 14) if len(closes[-30:-10])>=14 else 50
    
    divergence_msg = "لا يوجد تباين واضح"
    if recent_high_price > older_high_price and recent_rsi < older_rsi and rsi_14 > 65:
        divergence_msg = "⚠️ تباين سلبي (Bearish Divergence): السعر يصنع قمم أعلى بينما الزخم يضعف."
    elif recent_high_price < older_high_price and recent_rsi > older_rsi and rsi_14 < 35:
        divergence_msg = "⚠️ تباين إيجابي (Bullish Divergence): السعر يصنع قيعان أدنى بينما الزخم يقوى."

    # تحديد مستوى الخطر
    danger_level = 0
    warnings = []
    
    if rsi_14 > 75:
        danger_level += 2
        warnings.append("🔥 تشبع شرائي حاد (RSI > 75) — المستثمرون منهكون من الشراء.")
    elif rsi_14 < 25:
        danger_level += 2
        warnings.append("❄️ تشبع بيعي حاد (RSI < 25) — البائعون منهكون من البيع.")
        
    if abs(distance_pct) > 8:
        danger_level += 2
        direction = "أعلى" if distance_pct > 0 else "أسفل"
        warnings.append(f"🧲 شذوذ سعري (Overextension): السعر يبتعد بنسبة {abs(distance_pct):.1f}% {direction} متوسط 200 يوم. المتوسط يعمل كمغناطيس قوي للسعر.")
        
    if "⚠️" in divergence_msg:
        danger_level += 1
        warnings.append(divergence_msg)
        
    if danger_level >= 4:
        status = "🚨 خطر جداً (عالي)"
        action = "توقع انعكاس عنيف قريباً (نهاية الاتجاه)."
    elif danger_level >= 2:
        status = "⚠️ تحذير (متوسط)"
        action = "السوق يظهر علامات إرهاق، يجب الحذر ورفع وقف الخسارة."
    else:
        status = "🟢 مستقر (آمن)"
        action = "لا توجد علامات واضحة على انهيار الاتجاه."
        
    return {
        "rsi": round(rsi_14, 1),
        "ema_200": ema_200,
        "distance_pct": round(distance_pct, 1),
        "divergence": divergence_msg,
        "status": status,
        "action": action,
        "warnings": warnings,
        "danger_level": danger_level
    }

def build_template_exhaustion(data: dict) -> str:
    """
    يبني قالب رادار الإرهاق.
    """
    if not data:
        return "⚠️ بيانات الإرهاق غير متوفرة."
        
    send_time = cairo_now().strftime("%I:%M %p")
    
    if data['danger_level'] >= 4:
        header = "🚨🚨 [2/7] إنذار أحمر: رادار انهيار الاتجاه 🚨🚨"
    else:
        header = "🔍 [2/7] رادار الإرهاق وانعكاس الاتجاه (Trend Exhaustion)"
        
    report = f"""{header}
━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ التحديث: {send_time} القاهرة
🚦 مستوى خطر الانعكاس: {data['status']}
═════════════════════════════
📊 مؤشرات الإرهاق الكبرى (فريم يومي):
   ▪️ مؤشر القوة (RSI): {data['rsi']}
   ▪️ مسافة الشذوذ (EMA 200): السعر يبتعد {data['distance_pct']}% عن المركز ({data['ema_200']}$).
   ▪️ سلوك الزخم: {data['divergence']}
═════════════════════════════
"""
    if data['warnings']:
        report += "⚠️ علامات الخطر المرصودة:\n"
        for w in data['warnings']:
            report += f"   - {w}\n"
        report += "═════════════════════════════\n"
        
    report += f"""💡 النصيحة الخوارزمية:
{data['action']}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return report

def analyze_breakout_signal() -> dict | None:
    """
    يحسب إشارة الاختراق والكسر السريعة (Breakout Signal) باستخدام مستويات الكاماريلا (H4 للكسر الشرائي و L4 للكسر البيعي).
    """
    try:
        from Goldbot.bot_daily_levels import fetch_daily_data, calc_camarilla_pivots
    except ImportError:
        try:
            from bot_daily_levels import fetch_daily_data, calc_camarilla_pivots
        except ImportError:
            return None

    data = fetch_daily_data()
    if not data:
        return None
        
    spot = data.get("spot_price") or data.get("prev_close")
    h = data.get("prev_high", 0)
    l = data.get("prev_low", 0)
    c = data.get("prev_close", 0)
    
    if not (h > 0 and l > 0 and c > 0):
        return None
        
    cam = calc_camarilla_pivots(h, l, c)
    if not cam:
        return None
        
    return {
        "spot": spot,
        "support": cam['l4'],    # L4 is the breakdown point (Sell)
        "resistance": cam['h4']  # H4 is the breakout point (Buy)
    }

def build_template_breakout(data: dict) -> str:
    """
    يبني قالب الاختراق بالشكل الثابت الذي طلبه المستخدم.
    """
    if not data:
        return "⚠️ بيانات الاختراق غير متوفرة."
        
    # الهيكل الثابت الذي طلبه المستخدم بالحرف
    report = f"""[3/7] كسر {data['support']}$ للبيع او اختراق {data['resistance']}$ للشرا الاستوب 90 نقطه
السعر الحالي {data['spot']}$"""
    
    return report

def analyze_bounce_prediction() -> dict | None:
    """
    يتوقع الارتداد بدقة: إمتى هيرد؟ ومن أي سعر؟ وهيكمل لفين (الهدف النهائي)؟
    """
    try:
        from Goldbot.bot_spot import _fetch, calc_rsi, calc_stoch_rsi
        from Goldbot.bot_daily_levels import fetch_daily_data
    except ImportError:
        return None

    # Fetch daily data for spot price
    daily_data = fetch_daily_data()
    if not daily_data:
        return None
        
    spot_price = daily_data.get("spot_price") or daily_data.get("prev_close")
    
    # Fetch Hourly data for Trend & Swings
    df_1h = _fetch("GC=F", period="15d", interval="1h")
    if df_1h is None or len(df_1h) < 200:
        return None

    closes = df_1h['Close'].dropna().values
    highs = df_1h['High'].dropna().values
    lows = df_1h['Low'].dropna().values

    ema_50 = calc_ema(closes, 50)
    ema_200 = calc_ema(closes, 200)

    # Swings over the last 72 hours
    lookback = min(72, len(highs))
    swing_high = float(np.max(highs[-lookback:]))
    swing_low = float(np.min(lows[-lookback:]))
    swing_dist = swing_high - swing_low

    if swing_dist == 0:
        return None
        
    # Stochastic RSI for timing
    try:
        stoch_k, _ = calc_stoch_rsi(closes)
        stoch_k_val = stoch_k[-1]
    except Exception:
        stoch_k_val = 50

    if ema_50 > ema_200:
        trend = "صاعد 📈"
        # In Uptrend, it bounces from Fib support (61.8%)
        bounce_price = swing_high - (0.618 * swing_dist)
        # Target is Fib Extension (161.8%) upwards
        target_price = swing_high + (0.618 * swing_dist) 
        
        # Timing based on Stoch
        if stoch_k_val < 20:
            bounce_time = "الارتداد لأعلى وشيك جداً (تشبع بيعي على فريم الساعة)."
        else:
            bounce_time = "بمجرد هبوط السعر لنقطة الدعم واستقرار السيولة (غالباً مع افتتاح الجلسة القادمة)."
            
    else:
        trend = "هابط 📉"
        # In Downtrend, it bounces from Fib resistance (61.8%)
        bounce_price = swing_low + (0.618 * swing_dist)
        # Target is Fib Extension (161.8%) downwards
        target_price = swing_low - (0.618 * swing_dist)
        
        # Timing based on Stoch
        if stoch_k_val > 80:
            bounce_time = "الارتداد لأسفل وشيك جداً (تشبع شرائي على فريم الساعة)."
        else:
            bounce_time = "بمجرد صعود السعر لنقطة المقاومة واستقرار السيولة (غالباً مع افتتاح الجلسة القادمة)."

    return {
        "spot": spot_price,
        "trend": trend,
        "bounce_price": round(bounce_price, 2),
        "target_price": round(target_price, 2),
        "bounce_time": bounce_time
    }

def build_template_bounce(data: dict) -> str:
    """
    يبني قالب الارتداد والأهداف.
    """
    if not data:
        return "⚠️ بيانات الارتداد غير متوفرة."
        
    send_time = cairo_now().strftime("%I:%M %p")
    
    report = f"""[4/7] 🎯 رادار قنص الارتداد (Bounce Prediction)
━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ التحديث: {send_time} القاهرة
🧭 الاتجاه المسيطر: {data['trend']}
═════════════════════════════
1️⃣ من أي سعر سيرتد الذهب؟ (نقطة الصفر)
   📌 السعر الذهبي المتوقع للارتداد: {data['bounce_price']}$
   (يمثل مستوى 61.8% فيبوناتشي وهو الأقوى خوارزمياً)

2️⃣ إمتى هيرد؟ (التوقيت المتوقع)
   ⏳ {data['bounce_time']}

3️⃣ هيكمل الاتجاه لفين؟ (الهدف النهائي)
   🚀 هدف الموجة القادمة بعد الارتداد: {data['target_price']}$
   (يمثل امتداد 161.8% لاصطياد قمة/قاع جديد)
═════════════════════════════
💡 الخلاصة:
راقب السعر عند {data['bounce_price']}$، لأن الارتداد من هذا المستوى سيأخذ السعر مباشرة لاستهداف {data['target_price']}$.
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return report

def calc_bollinger_bands(closes: np.ndarray, period=20, std_dev=2.0) -> tuple:
    if len(closes) < period:
        return closes[-1], closes[-1], closes[-1]
    sma = np.mean(closes[-period:])
    std = np.std(closes[-period:])
    upper = sma + (std_dev * std)
    lower = sma - (std_dev * std)
    return sma, upper, lower

def analyze_volatility_explosion() -> dict | None:
    """
    رادار الانفجار السعري: يحسب اتجاه الحركة اللحظية، مقدارها المتوقع (ATR)، ومتى ستشد بعنف (BB Squeeze & Time).
    """
    try:
        from Goldbot.bot_spot import _fetch
        from Goldbot.bot_daily_levels import fetch_daily_data
    except ImportError:
        return None

    # Fetch daily data for ATR
    daily_data = fetch_daily_data()
    if not daily_data:
        return None
        
    atr = daily_data.get("atr", 0)
    
    # Fetch Hourly data for Momentum and Bollinger Bands
    df_1h = _fetch("GC=F", period="5d", interval="1h")
    if df_1h is None or len(df_1h) < 30:
        return None

    closes = df_1h['Close'].dropna().values

    # Short term direction (EMA 9 vs EMA 21)
    ema_9 = calc_ema(closes, 9)
    ema_21 = calc_ema(closes, 21)
    
    if ema_9 > ema_21:
        direction = "صاعد 📈 (سيطرة شرائية لحظية)"
        bias = "صعوداً"
    elif ema_9 < ema_21:
        direction = "هابط 📉 (سيطرة بيعية لحظية)"
        bias = "هبوطاً"
    else:
        direction = "عرضي ↔️ (تجميع)"
        bias = "في أي اتجاه"

    # Bollinger Bands for Squeeze detection (Volatility)
    sma_20, upper_bb, lower_bb = calc_bollinger_bands(closes, 20, 2.0)
    bb_width_dollars = upper_bb - lower_bb
    
    # 15 dollars width on 1H chart for Gold is considered a very tight squeeze
    if bb_width_dollars < 18.0:
        squeeze_status = "تضيق شديد جداً (Squeeze)"
        explosion_ready = True
    elif bb_width_dollars < 25.0:
        squeeze_status = "ضغط متوسط يتجه للتضيق"
        explosion_ready = False
    else:
        squeeze_status = "مفتوح (السيولة تتحرك بحرية)"
        explosion_ready = False

    # Timing
    now_hour = cairo_now().hour
    is_ny_open = 15 <= now_hour <= 18
    is_london_open = 10 <= now_hour <= 13
    
    if explosion_ready and (is_ny_open or is_london_open):
        timing_msg = "🔥 السعر هيشد بعنف *الآن* (البولينجر مضغوط تماماً وتوقيت السيولة الحالي متفجر)."
    elif explosion_ready:
        timing_msg = "⚠️ السعر مضغوط جداً وهيشد بعنف مع دخول سيولة الجلسة القادمة (لندن أو نيويورك)."
    elif is_ny_open:
        timing_msg = "🇺🇸 نحن الآن في توقيت السيولة الأمريكية، الحركة متذبذبة ولكنها سريعة."
    elif is_london_open:
        timing_msg = "🇬🇧 نحن الآن في توقيت السيولة الأوروبية، السوق يبني اتجاه اليوم."
    else:
        timing_msg = "🌙 السوق في مرحلة هدوء نسبي، لا يتوقع شد عنيف في الساعات القليلة القادمة."

    return {
        "direction": direction,
        "bias": bias,
        "atr": round(atr, 2),
        "bb_width": round(bb_width_dollars, 2),
        "squeeze_status": squeeze_status,
        "timing_msg": timing_msg
    }

def build_template_explosion(data: dict) -> str:
    """
    يبني قالب رادار الانفجار السعري.
    """
    if not data:
        return "⚠️ بيانات الانفجار السعري غير متوفرة."
        
    send_time = cairo_now().strftime("%I:%M %p")
    
    report = f"""[5/7] 🚀 رادار الانفجار السعري (Volatility Radar)
━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ التحديث: {send_time} القاهرة
═════════════════════════════
1️⃣ الاتجاه اللحظي للحركة دلوقتي:
   🧭 {data['direction']}
   (مبني على تقاطع الزخم السريع لآخر الساعات)

2️⃣ مقدار الحركة المتوقعة (طاقة السوق):
   📏 الذهب يمتلك طاقة حركة بمقدار {data['atr']}$ اليوم.
   (هذا هو المدى الكامل الذي يمكن أن يتحركه السعر)

3️⃣ حالة الضغط السعري (البولينجر باند):
   🗜️ حالة النطاق: {data['squeeze_status']} (مسافة {data['bb_width']}$)

4️⃣ إمتى هتشد بعنف؟ (توقيت الانفجار):
   ⏰ {data['timing_msg']}
═════════════════════════════
💡 الخلاصة:
إذا حدث الانفجار بناءً على المعطيات الحالية، فالاحتمال الأكبر أن يشد السعر بعنف ({data['bias']}) ليفرغ طاقة الـ {data['atr']}$ المتراكمة.
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return report

def analyze_daily_continuation() -> dict | None:
    """
    رادار استكمال أو انعكاس اليوم (Intraday Continuation vs Reversal).
    يحسب المدى اللحظي ويقارنه بـ ATR لمعرفة إذا استنفد الذهب طاقته أم سيستمر.
    """
    try:
        from Goldbot.bot_spot import _fetch
        from Goldbot.bot_daily_levels import fetch_daily_data
    except ImportError:
        return None

    # Fetch daily data for ATR
    daily_data = fetch_daily_data()
    if not daily_data:
        return None
        
    atr = daily_data.get("atr", 0)
    spot_price = daily_data.get("spot_price") or daily_data.get("prev_close")
    
    # Fetch Hourly data to calculate today's range (last 24 hours as a proxy for the daily session)
    df_1h = _fetch("GC=F", period="5d", interval="1h")
    if df_1h is None or len(df_1h) < 24:
        return None

    recent_highs = df_1h['High'].dropna().values[-24:]
    recent_lows = df_1h['Low'].dropna().values[-24:]
    recent_opens = df_1h['Open'].dropna().values[-24:]
    
    intraday_high = float(np.max(recent_highs))
    intraday_low = float(np.min(recent_lows))
    intraday_open = float(recent_opens[0])  # Proxy for daily open
    
    current_range = intraday_high - intraday_low
    
    if atr <= 0:
        return None
        
    exhaustion_pct = (current_range / atr) * 100
    
    # Determine basic intraday direction
    if spot_price > intraday_open:
        intraday_trend = "صاعد 📈"
    else:
        intraday_trend = "هابط 📉"

    now_hour = cairo_now().hour
    late_session = now_hour >= 19 or now_hour < 2
    
    if exhaustion_pct >= 85:
        verdict = "عكس مساره أو تذبذب عرضي 🪃"
        explanation = f"الذهب تحرك {exhaustion_pct:.0f}% من طاقته الكلية اليوم. (وقود الاتجاه نفد تقريباً)."
        advice = "تجنب الدخول مع الاتجاه الحالي. ابحث عن فرص الانعكاس أو جني الأرباح فوراً."
    elif exhaustion_pct >= 65 and late_session:
        verdict = "تذبذب وجني أرباح ⚠️"
        explanation = f"الذهب تحرك {exhaustion_pct:.0f}% من طاقته، ودخلنا في توقيت جني الأرباح المسائي."
        advice = "يفضل إغلاق الصفقات، السوق يميل للاستقرار وتصفية المراكز حتى نهاية اليوم."
    elif exhaustion_pct < 65:
        verdict = "استكمال الاتجاه 🚀"
        explanation = f"الذهب لم يتحرك سوى {exhaustion_pct:.0f}% من طاقته. (لا يزال هناك وقود قوي)."
        advice = f"ابحث عن صفقات مع الاتجاه ({intraday_trend}) لاستهداف باقي طاقة الـ ATR."
    else:
        verdict = "مرحلة حسم ⚖️"
        explanation = f"الذهب استهلك {exhaustion_pct:.0f}% من طاقته. نحن في منتصف الطريق."
        advice = "انتظر كسر مقاومة أو دعم لتحديد إذا كان سيكمل أم يعكس."

    return {
        "spot": spot_price,
        "intraday_trend": intraday_trend,
        "current_range": round(current_range, 2),
        "atr": round(atr, 2),
        "exhaustion_pct": round(exhaustion_pct, 1),
        "verdict": verdict,
        "explanation": explanation,
        "advice": advice
    }

def build_template_continuation(data: dict) -> str:
    """
    يبني قالب الاستكمال والانعكاس.
    """
    if not data:
        return "⚠️ بيانات الاستكمال والانعكاس غير متوفرة."
        
    send_time = cairo_now().strftime("%I:%M %p")
    
    report = f"""[6/7] ⚖️ رادار الاستكمال أو الانعكاس (Continuation vs Reversal)
━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ التحديث: {send_time} القاهرة
🧭 الاتجاه المسيطر اليوم: {data['intraday_trend']}
═════════════════════════════
🔋 تحليل طاقة السوق (ATR Exhaustion):
   ▪️ طاقة الذهب القصوى اليوم: {data['atr']}$
   ▪️ ما تم استهلاكه حتى الآن: {data['current_range']}$
   ▪️ نسبة استنفاد الوقود: {data['exhaustion_pct']}%

🎯 هل سيكمل الذهب مساره أم يعكس باقي اليوم؟
   القرار الخوارزمي: **{data['verdict']}**
   
   💡 التفسير: 
   {data['explanation']}
═════════════════════════════
💡 نصيحة التداول لباقي اليوم:
{data['advice']}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return report

def analyze_trend_conditions() -> dict | None:
    """
    خريطة شروط الاتجاه (Trend Validation Checklist).
    تختبر 3 شروط ذهبية للصعود و 3 للهبوط وتعيد حالة كل شرط (✅ أو ❌).
    """
    try:
        from Goldbot.bot_spot import _fetch, calc_rsi
        from Goldbot.bot_daily_levels import fetch_daily_data
    except ImportError:
        return None

    # Fetch daily data for yesterday's HLC to calculate Pivots
    daily_data = fetch_daily_data()
    if not daily_data:
        return None
        
    spot_price = daily_data.get("spot_price") or daily_data.get("prev_close")
    h = daily_data.get("prev_high", 0)
    l = daily_data.get("prev_low", 0)
    c = daily_data.get("prev_close", 0)
    
    if not (h > 0 and l > 0 and c > 0):
        return None
        
    # Classical Pivot Calculation
    pivot = (h + l + c) / 3
    r1 = (2 * pivot) - l
    s1 = (2 * pivot) - h
    
    # Fetch Hourly data for RSI
    df_1h = _fetch("GC=F", period="5d", interval="1h")
    if df_1h is None or len(df_1h) < 20:
        return None

    closes = df_1h['Close'].dropna().values
    rsi_14 = calc_rsi(closes, 14)
    
    # Evaluate Uptrend Conditions
    up_cond_1 = spot_price > pivot
    up_cond_2 = rsi_14 < 70  # Not overbought
    up_cond_3 = spot_price > r1
    
    # Evaluate Downtrend Conditions
    dn_cond_1 = spot_price < pivot
    dn_cond_2 = rsi_14 > 30  # Not oversold
    dn_cond_3 = spot_price < s1

    # Formatting checkboxes
    chk = lambda x: "✅ متحقق" if x else "❌ غير متحقق"
    
    # Verdict
    up_score = sum([up_cond_1, up_cond_2, up_cond_3])
    dn_score = sum([dn_cond_1, dn_cond_2, dn_cond_3])
    
    if up_score == 3:
        overall_verdict = "صعود قوي ومدعوم بكافة الشروط 🚀"
    elif dn_score == 3:
        overall_verdict = "هبوط قوي ومدعوم بكافة الشروط 📉"
    elif up_score == 2 and up_cond_1:
        overall_verdict = "صعود إيجابي ولكن يحتاج لتأكيد اختراق المقاومة 📈"
    elif dn_score == 2 and dn_cond_1:
        overall_verdict = "هبوط سلبي ولكن يحتاج لتأكيد كسر الدعم 📉"
    else:
        overall_verdict = "حالة تذبذب وعدم وضوح (نطاق عرضي) ⚖️"

    return {
        "spot": spot_price,
        "pivot": round(pivot, 2),
        "r1": round(r1, 2),
        "s1": round(s1, 2),
        "rsi": round(rsi_14, 1),
        "up_c1": chk(up_cond_1),
        "up_c2": chk(up_cond_2),
        "up_c3": chk(up_cond_3),
        "dn_c1": chk(dn_cond_1),
        "dn_c2": chk(dn_cond_2),
        "dn_c3": chk(dn_cond_3),
        "verdict": overall_verdict
    }

def build_template_conditions(data: dict) -> str:
    """
    يبني قالب شروط الاتجاه.
    """
    if not data:
        return "⚠️ بيانات شروط الاتجاه غير متوفرة."
        
    send_time = cairo_now().strftime("%I:%M %p")
    
    report = f"""[7/7] 📋 خريطة شروط الاتجاه (Trend Checklist)
━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ التحديث: {send_time} القاهرة
🎯 الخلاصة الفنية: {data['verdict']}
═════════════════════════════
🟢 شروط تأكيد الاتجاه الصاعد اليوم:
   1️⃣ الارتكاز: السعر ({data['spot']}$) أعلى المحور ({data['pivot']}$)
       👈 {data['up_c1']}
   2️⃣ الزخم: لا يوجد تشبع شرائي يمنع الصعود (RSI < 70)
       👈 {data['up_c2']} (الحالي: {data['rsi']})
   3️⃣ السيولة: السعر يخترق المقاومة الأولى ({data['r1']}$)
       👈 {data['up_c3']}
═════════════════════════════
🔴 شروط تأكيد الاتجاه الهابط اليوم:
   1️⃣ الارتكاز: السعر ({data['spot']}$) أسفل المحور ({data['pivot']}$)
       👈 {data['dn_c1']}
   2️⃣ الزخم: لا يوجد تشبع بيعي يمنع الهبوط (RSI > 30)
       👈 {data['dn_c2']} (الحالي: {data['rsi']})
   3️⃣ السيولة: السعر يكسر الدعم الأول ({data['s1']}$)
       👈 {data['dn_c3']}
━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 نصيحة الخوارزمية:
لا تدخل في صفقة حتى يتحقق شرطان على الأقل من شروط الاتجاه الذي ترغب في التداول به!
"""
    return report

def process_and_send_bot9():
    """
    التشغيل الرئيسي للبوت التاسع.
    """
    log.info("🚀 [Bot9] بدء توليد التقارير السبعة...")
    try:
        from Goldbot.bot_spot import _http_fallback_send
        from Goldbot.secrets_config import TELEGRAM_TOKENS, BOT9_CHAT_ID
    except ImportError:
        try:
            from bot_spot import _http_fallback_send
            from secrets_config import TELEGRAM_TOKENS, BOT9_CHAT_ID
        except ImportError:
            log.error("❌ فشل استدعاء الملفات المطلوبة في Bot 9.")
            return False

    token = TELEGRAM_TOKENS.get("bot9")
    if not token or not BOT9_CHAT_ID:
        log.error("❌ التوكن أو جروب Bot9 غير معرف.")
        return False

    # 1. إشارة الاختراق (Breakout Signal)
    breakout_data = analyze_breakout_signal()
    if breakout_data:
        template3 = build_template_breakout(breakout_data)
        _http_fallback_send(template3, token, [BOT9_CHAT_ID])
        import time
        time.sleep(1)

    # 2. تقرير قنص الارتداد (Bounce Prediction)
    bounce_data = analyze_bounce_prediction()
    if bounce_data:
        template4 = build_template_bounce(bounce_data)
        _http_fallback_send(template4, token, [BOT9_CHAT_ID])
        import time
        time.sleep(1)

    # 3. تقرير الانفجار السعري والسيولة (Volatility Radar)
    vol_data = analyze_volatility_explosion()
    if vol_data:
        template5 = build_template_explosion(vol_data)
        _http_fallback_send(template5, token, [BOT9_CHAT_ID])
        import time
        time.sleep(1)

    # 4. تقرير الاتجاه والتصحيحات
    algo_data = analyze_trend_and_correction()
    if algo_data:
        template1 = build_template_trend_correction(algo_data)
        _http_fallback_send(template1, token, [BOT9_CHAT_ID])
        import time
        time.sleep(1)
    else:
        log.error("❌ فشل حساب الاتجاه والتصحيح في Bot 9.")
        
    # 5. رادار الاستكمال أو الانعكاس (Continuation vs Reversal)
    cont_data = analyze_daily_continuation()
    if cont_data:
        template6 = build_template_continuation(cont_data)
        _http_fallback_send(template6, token, [BOT9_CHAT_ID])
        import time
        time.sleep(1)

    # 6. تقرير الإرهاق (Exhaustion)
    exhaustion_data = analyze_exhaustion()
    if exhaustion_data:
        template2 = build_template_exhaustion(exhaustion_data)
        _http_fallback_send(template2, token, [BOT9_CHAT_ID])
        import time
        time.sleep(1)
        
    # 7. خريطة شروط الاتجاه (Trend Checklist)
    cond_data = analyze_trend_conditions()
    if cond_data:
        template7 = build_template_conditions(cond_data)
        success = _http_fallback_send(template7, token, [BOT9_CHAT_ID])
    else:
        success = False
        
    if success:
        log.info("✅ [Bot9] تم إرسال جميع قوالب Bot9 السبعة بنجاح!")
    else:
        log.error("❌ [Bot9] فشل في إرسال بعض القوالب.")
    
    return success

if __name__ == "__main__":
    process_and_send_bot9()
