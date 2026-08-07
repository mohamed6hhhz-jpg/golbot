import logging
import numpy as np
from datetime import datetime
import pytz

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

def cairo_now():
    """تُرجع الوقت الحالي بتوقيت القاهرة"""
    tz = pytz.timezone('Africa/Cairo')
    return datetime.now(tz)

def analyze_fed_expectations() -> dict | None:
    """
    رادار توقعات أسعار الفائدة: يحلل عوائد السندات (US10Y) ومؤشر الدولار (DXY)
    لتحديد تسعير السوق اللحظي للفائدة وتأثيرها على الذهب.
    """
    try:
        from Goldbot.bot_spot import _fetch
    except ImportError:
        return None

    # Fetch Data
    tnx_df = _fetch("^TNX", period="10d", interval="1d")
    dxy_df = _fetch("DX-Y.NYB", period="10d", interval="1d")
    gold_df = _fetch("GC=F", period="5d", interval="1d")

    if tnx_df is None or dxy_df is None or len(tnx_df) < 2 or len(dxy_df) < 2:
        return None

    # Current values
    tnx_current = float(tnx_df['Close'].iloc[-1])
    tnx_prev = float(tnx_df['Close'].iloc[-2])
    dxy_current = float(dxy_df['Close'].iloc[-1])
    dxy_prev = float(dxy_df['Close'].iloc[-2])
    
    spot_price = float(gold_df['Close'].iloc[-1]) if gold_df is not None else 0

    # Calculate differences
    tnx_diff = tnx_current - tnx_prev
    dxy_diff = dxy_current - dxy_prev

    # Logic for Expectations
    if tnx_diff > 0.05 and dxy_diff > 0.1:
        fed_state = "تشديد نقدي (Hawkish) 🦅"
        market_pricing = "السوق يسعر بقاء الفائدة مرتفعة لفترة أطول."
        gold_impact = "ضغط بيعي قوي على الذهب 🔴"
        advice = "البيئة الحالية تدعم الدولار والسندات، تجنب الشراء من قمم وانتظر تصحيح الذهب."
    elif tnx_diff < -0.05 and dxy_diff < -0.1:
        fed_state = "تيسير نقدي (Dovish) 🕊️"
        market_pricing = "السوق يسعر خفضاً وشيكاً أو تراجعاً في نبرة الفيدرالي."
        gold_impact = "دعم شرائي قوي للذهب 🟢"
        advice = "البيئة الحالية تضغط على الدولار وتدفع السيولة للملاذ الآمن (الذهب). ابحث عن فرص الشراء."
    elif tnx_diff > 0 and dxy_diff < 0:
        fed_state = "تباين وحيرة (Mixed) ⚖️"
        market_pricing = "السندات ترتفع بينما يتراجع الدولار (تضارب في التسعير)."
        gold_impact = "تذبذب عرضي للذهب ⚪"
        advice = "السوق غير متأكد من خطوة الفيدرالي القادمة، يفضل المضاربة السريعة داخل النطاق."
    elif tnx_diff < 0 and dxy_diff > 0:
        fed_state = "تباين وحيرة (Mixed) ⚖️"
        market_pricing = "السندات تتراجع بينما يرتفع الدولار (تضارب في التسعير)."
        gold_impact = "تذبذب عرضي للذهب ⚪"
        advice = "تأثير متعادل على الذهب، ننتظر كسر فني واضح أو بيانات جديدة."
    else:
        fed_state = "هدوء واستقرار (Neutral) ⏸️"
        market_pricing = "لا تغيير كبير في تسعير الفائدة، استقرار في العوائد."
        gold_impact = "تحرك هادئ بناءً على التحليل الفني ⚪"
        advice = "الاقتصاد الكلي لا يشكل ضغطاً الآن، ركز على الدعوم والمقاومات الكلاسيكية."

    return {
        "tnx": round(tnx_current, 2),
        "tnx_diff": round(tnx_diff, 2),
        "dxy": round(dxy_current, 2),
        "dxy_diff": round(dxy_diff, 2),
        "fed_state": fed_state,
        "market_pricing": market_pricing,
        "gold_impact": gold_impact,
        "advice": advice,
        "spot": spot_price
    }

def build_template_fed_expectations(data: dict) -> str:
    """
    يبني قالب توقعات أسعار الفائدة.
    """
    if not data:
        return "⚠️ بيانات الاقتصاد الكلي (السندات والدولار) غير متوفرة حالياً."
        
    send_time = cairo_now().strftime("%I:%M %p")
    
    report = f"""🏦 رادار الفائدة الفيدرالية (Fed Expectations)
━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ التحديث: {send_time} القاهرة
السعر الفوري للذهب: {data['spot']}$
═════════════════════════════
📊 قراءة أدوات تسعير الفائدة:
   🇺🇸 عوائد السندات (10 سنوات): {data['tnx']}% ({data['tnx_diff']:+})
   💵 مؤشر الدولار (DXY): {data['dxy']} ({data['dxy_diff']:+})

🎯 توجهات السياسة النقدية المسعرة حالياً:
   الوضع الحالي: **{data['fed_state']}**
   💬 {data['market_pricing']}

📉 تأثير الفائدة على الذهب الآن:
   {data['gold_impact']}
═════════════════════════════
💡 نصيحة الاستثمار والماكرو:
{data['advice']}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return report

def analyze_economic_data_impact() -> dict | None:
    """
    رادار تأثير البيانات الاقتصادية: يقرأ رد فعل السوق (السيولة)
    لتحديد ما إذا كانت البيانات الأخيرة (مثل ADP أو التضخم) قوية أم ضعيفة.
    """
    try:
        from Goldbot.bot_spot import _fetch
    except ImportError:
        return None

    # Fetch Data
    dxy_df = _fetch("DX-Y.NYB", period="5d", interval="1d")
    gold_df = _fetch("GC=F", period="5d", interval="1d")

    if gold_df is None or dxy_df is None or len(gold_df) < 2 or len(dxy_df) < 2:
        return None

    # Current vs Previous Close
    dxy_current = float(dxy_df['Close'].iloc[-1])
    dxy_prev = float(dxy_df['Close'].iloc[-2])
    gold_current = float(gold_df['Close'].iloc[-1])
    gold_prev = float(gold_df['Close'].iloc[-2])

    dxy_pct_change = ((dxy_current - dxy_prev) / dxy_prev) * 100
    gold_pct_change = ((gold_current - gold_prev) / gold_prev) * 100

    # Strong movement thresholds
    dxy_moved = abs(dxy_pct_change) > 0.15
    gold_moved = abs(gold_pct_change) > 0.30

    if gold_pct_change > 0.30 and dxy_pct_change < -0.15:
        data_sentiment = "بيانات أمريكية ضعيفة / سلبية 📉"
        market_reaction = "السوق يبيع الدولار بقوة ويشتري الملاذ الآمن (الذهب)."
        trend_impact = "دعم صعودي عنيف للذهب 🚀"
        advice = "البيانات الاقتصادية (مثل توظيف ADP أو التضخم) جاءت أضعف من المتوقع، مما يعزز فرص خفض الفائدة. استمر في الشراء."
    elif gold_pct_change < -0.30 and dxy_pct_change > 0.15:
        data_sentiment = "بيانات أمريكية قوية / إيجابية 📈"
        market_reaction = "السوق يشتري الدولار بقوة ويتخلص من الذهب."
        trend_impact = "ضغط هبوطي عنيف على الذهب 🔴"
        advice = "البيانات الاقتصادية جاءت أقوى من المتوقع، مما يقلل احتمالات خفض الفائدة. السوق في وضع بيعي."
    elif gold_moved or dxy_moved:
        data_sentiment = "تسعير متباين للبيانات ⚖️"
        market_reaction = "تفاعل السوق غير متطابق بين الدولار والذهب."
        trend_impact = "تذبذب واختبار للمستويات الفنية ⚪"
        advice = "البيانات لم تكن حاسمة، أو أن هناك عوامل أخرى تتداخل معها (مثل التوترات الجيوسياسية). يرجى الحذر."
    else:
        data_sentiment = "هدوء اقتصادي / غياب بيانات مؤثرة ⏸️"
        market_reaction = "السيولة هادئة ولم يتم تسعير أي صدمات إخبارية حديثة."
        trend_impact = "حركة فنية طبيعية ⚪"
        advice = "السوق هادئ وينتظر الحدث الاقتصادي القادم. التزم بالدعوم والمقاومات."

    return {
        "gold_pct": round(gold_pct_change, 2),
        "dxy_pct": round(dxy_pct_change, 2),
        "data_sentiment": data_sentiment,
        "market_reaction": market_reaction,
        "trend_impact": trend_impact,
        "advice": advice
    }

def build_template_economic_data(data: dict) -> str:
    """
    يبني قالب البيانات الاقتصادية.
    """
    if not data:
        return "⚠️ بيانات تأثير الأخبار غير متوفرة حالياً."
        
    send_time = cairo_now().strftime("%I:%M %p")
    
    report = f"""📰 رادار تأثير البيانات الاقتصادية (Macro News Impact)
━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ التحديث: {send_time} القاهرة
═════════════════════════════
🔍 ماذا تسعر الأسواق الآن؟
   الوضع الحالي: **{data['data_sentiment']}**

📊 قراءة الانفجار السعري اللحظي:
   🥇 رد فعل الذهب: {'صعود' if data['gold_pct'] > 0 else 'هبوط'} ({data['gold_pct']:+}%)
   💵 رد فعل الدولار: {'صعود' if data['dxy_pct'] > 0 else 'هبوط'} ({data['dxy_pct']:+}%)

🎯 التفسير الاقتصادي لما يحدث:
   💬 {data['market_reaction']}
   اتجاه الذهب القادم: {data['trend_impact']}
═════════════════════════════
💡 نصيحة التداول بناءً على الأخبار:
{data['advice']}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return report

def analyze_geopolitical_risk() -> dict | None:
    """
    رادار التوترات الجيوسياسية والملاذات الآمنة: يقرأ VIX, Oil, DXY, Gold
    لاكتشاف شذوذ السيولة وتسعير الأزمات العالمية.
    """
    try:
        from Goldbot.bot_spot import _fetch
    except ImportError:
        return None

    # Fetch Data
    gold_df = _fetch("GC=F", period="5d", interval="1d")
    dxy_df = _fetch("DX-Y.NYB", period="5d", interval="1d")
    oil_df = _fetch("CL=F", period="5d", interval="1d")
    vix_df = _fetch("^VIX", period="5d", interval="1d")

    if not all(df is not None and len(df) >= 2 for df in [gold_df, dxy_df, oil_df, vix_df]):
        return None

    def get_pct_change(df):
        cur = float(df['Close'].iloc[-1])
        prev = float(df['Close'].iloc[-2])
        return cur, ((cur - prev) / prev) * 100

    gold_price, gold_pct = get_pct_change(gold_df)
    dxy_price, dxy_pct = get_pct_change(dxy_df)
    oil_price, oil_pct = get_pct_change(oil_df)
    vix_price, vix_pct = get_pct_change(vix_df)

    # Logic Triggers
    gold_surging = gold_pct > 0.4
    dxy_surging = dxy_pct > 0.3
    oil_surging = oil_pct > 1.0
    vix_surging = vix_price > 18.0 and vix_pct > 3.0

    if gold_surging and dxy_surging:
        geo_state = "صدمة رعب عالمي (Extreme Panic) 🚨"
        explanation = "شذوذ في الأسواق: الذهب والدولار يرتفعان معاً! السيولة تهرب من الأسهم وتندفع لشراء الملاذات الآمنة أياً كانت بسبب أزمة عالمية كبرى."
        safe_haven_demand = "الطلب على الذهب: عنيف وجنوني 🚀🚀"
    elif gold_surging and oil_surging:
        geo_state = "توترات طاقة / صراع جيوسياسي (War/Energy Crisis) 🔥"
        explanation = "الذهب والنفط يرتفعان معاً بقوة. السوق يسعر صراعاً جيوسياسياً (غالباً في الشرق الأوسط أو روسيا) يهدد إمدادات الطاقة."
        safe_haven_demand = "الطلب على الذهب: مرتفع جداً 🚀"
    elif vix_surging and gold_surging:
        geo_state = "مخاوف انهيار الأسهم (Stock Market Fear) 📉"
        explanation = f"مؤشر الخوف VIX يرتفع بقوة ليتجاوز {vix_price:.1f}. المستثمرون يسيلون محافظ الأسهم ويحتمون بالذهب."
        safe_haven_demand = "الطلب على الذهب: قوي كتحوط (Hedging) 📈"
    elif gold_surging and not dxy_surging and not oil_surging and not vix_surging:
        geo_state = "لا توجد أزمات حادة (Technical / Macro Move) ⚪"
        explanation = "الذهب يرتفع لأسباب فنية أو بسبب بيانات اقتصادية عادية، ولا توجد علامات على (Panic Buying) أو رعب عالمي."
        safe_haven_demand = "الطلب على الذهب: طبيعي ومستقر 🟢"
    elif not gold_surging:
        geo_state = "هدوء الملاذات الآمنة (Risk-On Sentiment) 🕊️"
        explanation = "شهية المخاطرة جيدة في الأسواق، ولا يوجد طلب استثنائي على الملاذات الآمنة حالياً."
        safe_haven_demand = "الطلب على الذهب: ضعيف / يتعرض للتصحيح 🔴"
    else:
        geo_state = "بيئة معقدة وغير واضحة ⚖️"
        explanation = "تضارب في مؤشرات الملاذات الآمنة."
        safe_haven_demand = "الطلب على الذهب: محايد ⚪"

    return {
        "gold_pct": round(gold_pct, 2),
        "dxy_pct": round(dxy_pct, 2),
        "oil_pct": round(oil_pct, 2),
        "vix": round(vix_price, 2),
        "vix_pct": round(vix_pct, 2),
        "geo_state": geo_state,
        "explanation": explanation,
        "safe_haven_demand": safe_haven_demand
    }

def build_template_geopolitical(data: dict) -> str:
    """
    يبني قالب التوترات الجيوسياسية.
    """
    if not data:
        return "⚠️ بيانات الملاذات الآمنة والتوترات غير متوفرة حالياً."
        
    send_time = cairo_now().strftime("%I:%M %p")
    
    report = f"""🌍 رادار التوترات الجيوسياسية (Safe-Haven Radar)
━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ التحديث: {send_time} القاهرة
═════════════════════════════
🛡️ حالة الملاذات الآمنة والسيولة العالمية:
   الوضع الحالي: **{data['geo_state']}**

📊 قراءة شاشات الرعب العالمية (النبض اللحظي):
   مؤشر الخوف (VIX): {data['vix']} ({data['vix_pct']:+}%)
   النفط الخام (Oil): {data['oil_pct']:+}%
   مؤشر الدولار (DXY): {data['dxy_pct']:+}%
   الذهب الفوري (Gold): {data['gold_pct']:+}%

🎯 التفسير الخوارزمي لتحركات الحيتان:
   💬 {data['explanation']}

🛡️ {data['safe_haven_demand']}
═════════════════════════════
💡 الخلاصة:
هذا الرادار يكتشف الأزمات الصامتة قبل ظهورها في الأخبار بناءً على تدفق الأموال الذكية وتوافق الأصول.
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return report

def analyze_options_sentiment() -> dict | None:
    """
    رادار أوبشن الذهب (Options Sentiment): يقرأ مؤشر تقلبات أوبشن الذهب (GVZ)
    لمعرفة تسعير صنّاع السوق والحيتان لحركة الذهب القادمة.
    """
    try:
        from Goldbot.bot_spot import _fetch
    except ImportError:
        return None

    # Fetch Data
    gvz_df = _fetch("^GVZ", period="10d", interval="1d")
    
    if gvz_df is None or len(gvz_df) < 2:
        return None

    gvz_current = float(gvz_df['Close'].iloc[-1])
    gvz_prev = float(gvz_df['Close'].iloc[-2])
    
    gvz_pct_change = ((gvz_current - gvz_prev) / gvz_prev) * 100

    # Logic based on CBOE Gold Volatility Index thresholds
    if gvz_current > 18.0 and gvz_pct_change > 2.0:
        sentiment = "تسعير لانفجار سعري عنيف (High Volatility Priced In) 🧨"
        explanation = "حيتان الأوبشن يدفعون (علاوات/Premiums) باهظة للتحوط. السوق يتوقع حركة عنيفة جداً للذهب في الأيام القادمة."
        options_bias = "توقع اختراقات سعرية كبرى (لا تتداول عكس الاتجاه)."
    elif gvz_pct_change > 4.0:
        sentiment = "ارتفاع في قلق صنّاع السوق (Rising Premiums) 📈"
        explanation = "مؤشر الأوبشن يرتفع بقوة، مما يعني زيادة الطلب على عقود الحماية (Puts/Calls). هناك ترقب لحدث كبير."
        options_bias = "السوق يجهز لحركة سريعة ومفاجئة."
    elif gvz_pct_change < -3.0 and gvz_current < 15.0:
        sentiment = "تسعير استقرار وتذبذب عرضي (Volatility Crush) 📉"
        explanation = "مؤشر أوبشن الذهب يتراجع. صناع السوق يبيعون العقود ولا يتوقعون حركات عنيفة قريباً."
        options_bias = "توقع حركة عرضية واحترام للدعوم والمقاومات الكلاسيكية."
    elif gvz_current < 12.0:
        sentiment = "هدوء ما قبل العاصفة (Extreme Complacency) 😴"
        explanation = "عقود الأوبشن رخيصة جداً. السوق في حالة استرخاء تام، وهو غالباً الهدوء الذي يسبق العاصفة."
        options_bias = "احذر من كسر النطاق العرضي فجأة."
    else:
        sentiment = "تسعير طبيعي (Normal Options Pricing) ⚪"
        explanation = "لا يوجد شذوذ في تسعير عقود الخيارات للذهب حالياً. السيولة تتحرك بشكل فني ومستقر."
        options_bias = "احترام الاتجاه العام للسوق."

    return {
        "gvz": round(gvz_current, 2),
        "gvz_pct": round(gvz_pct_change, 2),
        "sentiment": sentiment,
        "explanation": explanation,
        "options_bias": options_bias
    }

def build_template_options(data: dict) -> str:
    """
    يبني قالب سوق الأوبشن.
    """
    if not data:
        return "⚠️ بيانات أوبشن الذهب (GVZ) غير متوفرة حالياً."
        
    send_time = cairo_now().strftime("%I:%M %p")
    
    report = f"""📊 رادار سوق الأوبشن (Options Market Sentiment)
━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ التحديث: {send_time} القاهرة
═════════════════════════════
👁️‍🗨️ رؤية حيتان الأوبشن وصنّاع السوق الآن:
   الوضع الحالي: **{data['sentiment']}**

📉 قراءة مؤشر سيولة الأوبشن (GVZ):
   المستوى الحالي: {data['gvz']} نقطة
   التغير اليومي: {data['gvz_pct']:+}%

🎯 التفسير من داخل مطبخ الأوبشن:
   💬 {data['explanation']}
═════════════════════════════
💡 الانعكاس على تداول الذهب الفوري:
{data['options_bias']}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return report

def analyze_market_maker_vision() -> dict | None:
    """
    رؤية صانع السوق (Market Maker Vision): يعتمد على مفاهيم السيولة الذكية (SMC)
    ويحلل كسر وتلاعبات قمة وقاع اليوم السابق (PDH / PDL).
    """
    try:
        from Goldbot.bot_spot import _fetch
    except ImportError:
        return None

    # Fetch daily data for Gold
    gold_df = _fetch("GC=F", period="5d", interval="1d")
    
    if gold_df is None or len(gold_df) < 3:
        return None

    # Previous Day (إغلاق اليوم السابق المكتمل)
    prev_day = gold_df.iloc[-2]
    pdh = float(prev_day['High'])
    pdl = float(prev_day['Low'])
    
    # Current Day (اليوم الحالي المفتوح)
    curr_day = gold_df.iloc[-1]
    cdh = float(curr_day['High'])
    cdl = float(curr_day['Low'])
    current_price = float(curr_day['Close'])

    # Smart Money Concepts (SMC) Logic
    if cdh > pdh and current_price < pdh:
        # Swept PDH and rejected (Buy-side Liquidity Sweep)
        mm_state = "مصيدة مشترين (Bull Trap / BSL Sweep) 🔴"
        action = f"صانع السوق اخترق قمة أمس ({pdh:.2f}) ليوهم المتداولين بالصعود، ثم ضرب ستوباتهم وتراجع بقوة."
        target = f"الهدف القادم لصانع السوق هو ضرب قاع أمس ({pdl:.2f}) للبحث عن سيولة البيع."
        trend_bias = "هبوطي (سحب سيولة من أعلى والهبوط بها)."
    elif cdl < pdl and current_price > pdl:
        # Swept PDL and rejected (Sell-side Liquidity Sweep)
        mm_state = "مصيدة بائعين (Bear Trap / SSL Sweep) 🟢"
        action = f"صانع السوق كسر قاع أمس ({pdl:.2f}) للإيهام بالهبوط وضرب ستوبات المشترين، ثم ارتد بقوة لأعلى."
        target = f"الهدف القادم لصانع السوق هو الانطلاق لضرب قمة أمس ({pdh:.2f})."
        trend_bias = "صعودي (تجميع الأوامر من القاع والصعود بها)."
    elif current_price > pdh:
        # Strong expansion upside
        mm_state = "مرحلة توسع سعري صاعد (Bullish Expansion) 🚀"
        action = f"تم اختراق قمة أمس ({pdh:.2f}) بنجاح والسعر يستقر فوقها."
        target = "صانع السوق يبحث عن مناطق سيولة أعلى على الفريمات الكبرى (الأسبوعية)."
        trend_bias = "ترند صاعد قوي (السيولة تدعم الاتجاه)."
    elif current_price < pdl:
        # Strong expansion downside
        mm_state = "مرحلة توسع سعري هابط (Bearish Expansion) 🩸"
        action = f"تم كسر قاع أمس ({pdl:.2f}) بنجاح والسعر ينهار دونه."
        target = "صانع السوق يدفع السعر لمناطق سيولة شرائية أعمق على الفريمات الكبرى."
        trend_bias = "ترند هابط قوي (السيولة تدفع للأسفل)."
    else:
        # Inside Day / Accumulation
        mm_state = "مرحلة تجميع الأوامر (Accumulation Phase) ⚖️"
        action = f"السعر محصور بين قمة أمس ({pdh:.2f}) وقاع أمس ({pdl:.2f}). صانع السوق يبني مناطق سيولة."
        target = "انتظار (التلاعب - Manipulation) بكسر كاذب لأحد المستويين قبل تحديد الاتجاه الحقيقي."
        trend_bias = "عرضي ومخادع (لا تتسرع في الدخول)."

    return {
        "current_price": round(current_price, 2),
        "pdh": round(pdh, 2),
        "pdl": round(pdl, 2),
        "mm_state": mm_state,
        "action": action,
        "target": target,
        "trend_bias": trend_bias
    }

def build_template_market_maker(data: dict) -> str:
    """
    يبني قالب رؤية صانع السوق.
    """
    if not data:
        return "⚠️ بيانات مستويات السيولة غير متوفرة حالياً."
        
    send_time = cairo_now().strftime("%I:%M %p")
    
    report = f"""🕵️‍♂️ رؤية صانع السوق (Market Maker Vision)
━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ التحديث: {send_time} القاهرة
السعر الحالي: {data['current_price']}$
═════════════════════════════
🏦 تحليل السيولة الذكية (SMC) لليوم:
   الوضع الحالي: **{data['mm_state']}**

📍 مستويات اللعب (اصطياد الستوبات):
   قمة أمس (سيولة الشراء): {data['pdh']}$
   قاع أمس (سيولة البيع): {data['pdl']}$

🎯 نية صانع السوق الآن (ماذا يفعل الحيتان؟):
   💬 {data['action']}

📉 الهدف القادم للسيولة:
   {data['target']}
═════════════════════════════
💡 الخلاصة الاتجاهية للمحترفين:
{data['trend_bias']}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return report

def process_and_send_bot10():
    """
    التشغيل الرئيسي للبوت العاشر.
    """
    log.info("🚀 [Bot10] بدء توليد التقارير...")
    try:
        from Goldbot.bot_spot import _http_fallback_send
        from Goldbot.secrets_config import TELEGRAM_TOKENS, BOT10_CHAT_ID
    except ImportError:
        try:
            from bot_spot import _http_fallback_send
            from secrets_config import TELEGRAM_TOKENS, BOT10_CHAT_ID
        except ImportError:
            log.error("❌ فشل استدعاء الملفات المطلوبة في Bot 10.")
            return False

    token = TELEGRAM_TOKENS.get("bot10")
    if not token or not BOT10_CHAT_ID:
        log.error("❌ التوكن أو جروب Bot10 غير معرف.")
        return False
        
    # 1. رادار توقعات الفائدة (Fed Expectations)
    fed_data = analyze_fed_expectations()
    if fed_data:
        template1 = build_template_fed_expectations(fed_data)
        success = _http_fallback_send(template1, token, [BOT10_CHAT_ID])
        import time
        time.sleep(1)
    else:
        success = False

    # 2. رادار البيانات الاقتصادية (Economic Data Impact)
    eco_data = analyze_economic_data_impact()
    if eco_data:
        template2 = build_template_economic_data(eco_data)
        _http_fallback_send(template2, token, [BOT10_CHAT_ID])
        import time
        time.sleep(1)

    # 3. رادار التوترات الجيوسياسية (Geopolitical & Safe-Haven Radar)
    geo_data = analyze_geopolitical_risk()
    if geo_data:
        template3 = build_template_geopolitical(geo_data)
        _http_fallback_send(template3, token, [BOT10_CHAT_ID])
        import time
        time.sleep(1)

    # 4. رادار سوق الأوبشن (Options Market Sentiment)
    options_data = analyze_options_sentiment()
    if options_data:
        template4 = build_template_options(options_data)
        _http_fallback_send(template4, token, [BOT10_CHAT_ID])
        import time
        time.sleep(1)

    # 5. رؤية صانع السوق (Market Maker Vision)
    mm_data = analyze_market_maker_vision()
    if mm_data:
        template5 = build_template_market_maker(mm_data)
        _http_fallback_send(template5, token, [BOT10_CHAT_ID])
        import time
        time.sleep(1)

def analyze_daily_news_sentiment() -> dict | None:
    """
    رؤية المستثمرين لأخبار اليوم (Daily News Sentiment):
    يحلل تشريح شمعة اليوم (Open, High, Low, Close) لمعرفة كيف تعاملت السيولة مع الأخبار.
    """
    try:
        from Goldbot.bot_spot import _fetch
    except ImportError:
        return None

    # Fetch daily data for Gold
    gold_df = _fetch("GC=F", period="2d", interval="1d")
    
    if gold_df is None or len(gold_df) < 1:
        return None

    # Current Day Data
    curr_day = gold_df.iloc[-1]
    op = float(curr_day['Open'])
    hi = float(curr_day['High'])
    lo = float(curr_day['Low'])
    cp = float(curr_day['Close'])

    day_range = hi - lo
    if day_range == 0:
        day_range = 0.001 # Prevent division by zero

    # Position of current price relative to the day's range (0% to 100%)
    position_pct = ((cp - lo) / day_range) * 100
    
    # Distance from Open
    net_change = cp - op

    if day_range < 12.0:
        sentiment = "ترقب وتجاهل (Indecision / No News Impact) ⏸️"
        explanation = "النطاق السعري لليوم ضيق جداً. المستثمرون يتجاهلون الأخبار الحالية أو ينتظرون صدور حدث اقتصادي أهم لضخ السيولة."
        action = "تجنب التداول الآن، السوق يفتقر للزخم."
    elif net_change > 0 and position_pct > 75:
        sentiment = "شراء الأخبار (Buy the News / Bullish Sentiment) 🚀"
        explanation = f"الذهب افتتح عند {op:.2f} واندفع للأعلى ويستقر الآن بالقرب من قمة اليوم. المستثمرون استقبلوا أخبار اليوم بإيجابية بالغة ويشترون كل تراجع."
        action = "الزخم الشرائي مسيطر، البحث عن فرص الشراء مع الاتجاه."
    elif net_change < 0 and position_pct < 25:
        sentiment = "بيع الأخبار (Sell the News / Bearish Sentiment) 🩸"
        explanation = f"الذهب افتتح عند {op:.2f} وانهار للأسفل ويستقر الآن بالقرب من قاع اليوم. المستثمرون يهربون من الذهب ويعتبرون أخبار اليوم سلبية جداً."
        action = "الزخم البيعي مسيطر، لا تحاول الشراء عكس التيار."
    elif net_change > 0 and position_pct < 40:
        sentiment = "تلاشي الأخبار الإيجابية (Fading the News / Profit Taking) 📉"
        explanation = "الذهب ارتفع بقوة مع الأخبار مكوناً قمة، لكن المستثمرين الكبار استغلوا هذا الصعود لجني الأرباح والبيع، ليعود السعر قريباً من نقطة الافتتاح."
        action = "احذر! المشترون فقدوا السيطرة، وقد نشهد انعكاساً هبوطياً."
    elif net_change < 0 and position_pct > 60:
        sentiment = "رفض الأخبار السلبية (Buying the Dip / Rejection) 🟢"
        explanation = "الذهب هبط بقوة مع الأخبار مكوناً قاعاً، لكن المستثمرين استغلوا هذا الهبوط كفرصة ذهبية للشراء، ليرتد السعر بقوة لأعلى."
        action = "البائعون فقدوا السيطرة، والسوق يستعد للانطلاق صعوداً."
    else:
        sentiment = "تذبذب وحيرة (Choppy Market) ⚖️"
        explanation = "السعر يتحرك صعوداً وهبوطاً حول سعر الافتتاح دون اتجاه واضح. استجابة الأسواق للأخبار متضاربة."
        action = "المضاربة السريعة (سكالبينج) أو البقاء خارج السوق."

    return {
        "open": round(op, 2),
        "high": round(hi, 2),
        "low": round(lo, 2),
        "current": round(cp, 2),
        "range": round(day_range, 2),
        "sentiment": sentiment,
        "explanation": explanation,
        "action": action
    }

def build_template_news_sentiment(data: dict) -> str:
    """
    يبني قالب رؤية المستثمرين في أخبار اليوم.
    """
    if not data:
        return "⚠️ بيانات حركة السعر اليومية غير متوفرة."
        
    send_time = cairo_now().strftime("%I:%M %p")
    
    report = f"""📰 رؤية المستثمرين لأخبار اليوم (Daily News Sentiment)
━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ التحديث: {send_time} القاهرة
الافتتاح: {data['open']}$ | السعر الآن: {data['current']}$
(نطاق الحركة اليومي: {data['range']}$)
═════════════════════════════
👁️‍🗨️ كيف تفاعلت السيولة الذكية مع الأخبار؟
   الوضع الحالي: **{data['sentiment']}**

🎯 التفسير المباشر من الشارت:
   💬 {data['explanation']}

💡 التوجيه الفني للمتداول:
   {data['action']}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return report

def process_and_send_bot10():
    """
    التشغيل الرئيسي للبوت العاشر.
    """
    log.info("🚀 [Bot10] بدء توليد التقارير...")
    try:
        from Goldbot.bot_spot import _http_fallback_send
        from Goldbot.secrets_config import TELEGRAM_TOKENS, BOT10_CHAT_ID
    except ImportError:
        try:
            from bot_spot import _http_fallback_send
            from secrets_config import TELEGRAM_TOKENS, BOT10_CHAT_ID
        except ImportError:
            log.error("❌ فشل استدعاء الملفات المطلوبة في Bot 10.")
            return False

    token = TELEGRAM_TOKENS.get("bot10")
    if not token or not BOT10_CHAT_ID:
        log.error("❌ التوكن أو جروب Bot10 غير معرف.")
        return False
        
    # 1. رادار توقعات الفائدة (Fed Expectations)
    fed_data = analyze_fed_expectations()
    if fed_data:
        template1 = build_template_fed_expectations(fed_data)
        success = _http_fallback_send(template1, token, [BOT10_CHAT_ID])
        import time
        time.sleep(1)
    else:
        success = False

    # 2. رادار البيانات الاقتصادية (Economic Data Impact)
    eco_data = analyze_economic_data_impact()
    if eco_data:
        template2 = build_template_economic_data(eco_data)
        _http_fallback_send(template2, token, [BOT10_CHAT_ID])
        import time
        time.sleep(1)

    # 3. رادار التوترات الجيوسياسية (Geopolitical & Safe-Haven Radar)
    geo_data = analyze_geopolitical_risk()
    if geo_data:
        template3 = build_template_geopolitical(geo_data)
        _http_fallback_send(template3, token, [BOT10_CHAT_ID])
        import time
        time.sleep(1)

    # 4. رادار سوق الأوبشن (Options Market Sentiment)
    options_data = analyze_options_sentiment()
    if options_data:
        template4 = build_template_options(options_data)
        _http_fallback_send(template4, token, [BOT10_CHAT_ID])
        import time
        time.sleep(1)

    # 5. رؤية صانع السوق (Market Maker Vision)
    mm_data = analyze_market_maker_vision()
    if mm_data:
        template5 = build_template_market_maker(mm_data)
        _http_fallback_send(template5, token, [BOT10_CHAT_ID])
        import time
        time.sleep(1)

def analyze_options_market_maker() -> dict | None:
    """
    رؤية صانع سوق الأوبشن (Options Dealer Vision):
    يدمج بين مؤشر تقلبات الأوبشن (GVZ) ومستويات السيولة (PDH/PDL) 
    لاكتشاف (خنق السعر Gamma Pinning) أو (الانفجار الإجباري Gamma Squeeze).
    """
    try:
        from Goldbot.bot_spot import _fetch
    except ImportError:
        return None

    # Fetch Data
    gold_df = _fetch("GC=F", period="5d", interval="1d")
    gvz_df = _fetch("^GVZ", period="5d", interval="1d")

    if gold_df is None or gvz_df is None or len(gold_df) < 3 or len(gvz_df) < 2:
        return None

    # Gold SMC Data
    prev_day = gold_df.iloc[-2]
    pdh = float(prev_day['High'])
    pdl = float(prev_day['Low'])
    current_price = float(gold_df.iloc[-1]['Close'])

    # GVZ Options Volatility Data
    gvz_current = float(gvz_df['Close'].iloc[-1])
    gvz_prev = float(gvz_df['Close'].iloc[-2])
    gvz_pct = ((gvz_current - gvz_prev) / gvz_prev) * 100

    # Options Dealer (Market Maker) Logic
    if current_price > pdh and gvz_pct > 3.0:
        dealer_state = "انفجار إجباري صاعد (Call Gamma Squeeze) 🚀"
        explanation = "صانع سوق الأوبشن فقد السيطرة! الماركت ميكر بايع عقود (Calls) كثيرة، ومع ارتفاع السعر وكسر القمة أصبح (مجبراً) على شراء الذهب بكثافة للتحوط (Delta Hedging)، مما يضاعف الانفجار السعري."
        action = "اتجاه صاعد عنيف ومستمر (لا تفكر في البيع أبداً)."
    elif current_price < pdl and gvz_pct > 3.0:
        dealer_state = "انفجار إجباري هابط (Put Gamma Squeeze) 🩸"
        explanation = "صانع سوق الأوبشن في ورطة! الماركت ميكر بايع عقود (Puts) كثيرة، ومع كسر القاع أصبح (مجبراً) على بيع الذهب بكثافة للتحوط، مما يضاعف الانهيار."
        action = "اتجاه هابط عنيف ومستمر (لا تفكر في الشراء أبداً)."
    elif pdl <= current_price <= pdh and gvz_pct < -2.0:
        dealer_state = "خنق وتثبيت السعر (Gamma Pinning) 🗜️"
        explanation = "صانع سوق الأوبشن يضغط السعر ويجعله يتحرك بملل داخل النطاق (بين قمة وقاع أمس)، ويسحق التقلبات لكي تموت جميع عقود الأوبشن المشتراة (Puts و Calls) بلا قيمة (يحتفظ هو بالعلاوة)."
        action = "تجنب تداول الاختراقات، السعر سيعود للمنتصف. تداول من الأطراف فقط (Range Trading)."
    elif gvz_pct < -5.0:
        dealer_state = "سحق التقلبات (Volatility Crush) 📉"
        explanation = "صانع سوق الأوبشن يسحق التقلبات فجأة ليخفض أسعار العقود ويدمر قيمة التحوط للمشترين المتأخرين."
        action = "السوق يعود للهدوء، احذر من التذبذب العشوائي."
    else:
        dealer_state = "تحوط طبيعي (Normal Dealer Hedging) ⚪"
        explanation = "صانع سوق الأوبشن يتحوط بشكل طبيعي دون وجود ضغوط لـ (خنق السعر) أو (انفجارات إجبارية)."
        action = "الاعتماد على التحليل الفني الكلاسيكي وحركة السيولة العادية."

    return {
        "gvz_pct": round(gvz_pct, 2),
        "current_price": round(current_price, 2),
        "pdh": round(pdh, 2),
        "pdl": round(pdl, 2),
        "dealer_state": dealer_state,
        "explanation": explanation,
        "action": action
    }

def build_template_options_mm(data: dict) -> str:
    """
    يبني قالب رؤية صانع سوق الأوبشن للذهب.
    """
    if not data:
        return "⚠️ بيانات صانع سوق الأوبشن غير متوفرة."
        
    send_time = cairo_now().strftime("%I:%M %p")
    
    report = f"""🕵️‍♂️ رؤية صانع سوق الأوبشن (Options Dealer Vision)
━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ التحديث: {send_time} القاهرة
السعر الآن: {data['current_price']}$ | (القمة: {data['pdh']}$ - القاع: {data['pdl']}$)
═════════════════════════════
🎭 تكتيك الماركت ميكر في عقود الأوبشن الآن:
   الوضع الحالي: **{data['dealer_state']}**

🎯 ماذا يحدث خلف الكواليس؟
   💬 {data['explanation']}

💡 نصيحة التداول الذهبية:
   {data['action']}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return report

def process_and_send_bot10():
    """
    التشغيل الرئيسي للبوت العاشر.
    """
    log.info("🚀 [Bot10] بدء توليد التقارير...")
    try:
        from Goldbot.bot_spot import _http_fallback_send
        from Goldbot.secrets_config import TELEGRAM_TOKENS, BOT10_CHAT_ID
    except ImportError:
        try:
            from bot_spot import _http_fallback_send
            from secrets_config import TELEGRAM_TOKENS, BOT10_CHAT_ID
        except ImportError:
            log.error("❌ فشل استدعاء الملفات المطلوبة في Bot 10.")
            return False

    token = TELEGRAM_TOKENS.get("bot10")
    if not token or not BOT10_CHAT_ID:
        log.error("❌ التوكن أو جروب Bot10 غير معرف.")
        return False
        
    # 1. رادار توقعات الفائدة (Fed Expectations)
    fed_data = analyze_fed_expectations()
    if fed_data:
        template1 = build_template_fed_expectations(fed_data)
        success = _http_fallback_send(template1, token, [BOT10_CHAT_ID])
        import time
        time.sleep(1)
    else:
        success = False

    # 2. رادار البيانات الاقتصادية (Economic Data Impact)
    eco_data = analyze_economic_data_impact()
    if eco_data:
        template2 = build_template_economic_data(eco_data)
        _http_fallback_send(template2, token, [BOT10_CHAT_ID])
        import time
        time.sleep(1)

    # 3. رادار التوترات الجيوسياسية (Geopolitical & Safe-Haven Radar)
    geo_data = analyze_geopolitical_risk()
    if geo_data:
        template3 = build_template_geopolitical(geo_data)
        _http_fallback_send(template3, token, [BOT10_CHAT_ID])
        import time
        time.sleep(1)

    # 4. رادار سوق الأوبشن (Options Market Sentiment)
    options_data = analyze_options_sentiment()
    if options_data:
        template4 = build_template_options(options_data)
        _http_fallback_send(template4, token, [BOT10_CHAT_ID])
        import time
        time.sleep(1)

    # 5. رؤية صانع السوق (Market Maker Vision)
    mm_data = analyze_market_maker_vision()
    if mm_data:
        template5 = build_template_market_maker(mm_data)
        _http_fallback_send(template5, token, [BOT10_CHAT_ID])
        import time
        time.sleep(1)

    # 6. رؤية المستثمرين في أخبار اليوم (Daily News Sentiment)
    news_sentiment_data = analyze_daily_news_sentiment()
    if news_sentiment_data:
        template6 = build_template_news_sentiment(news_sentiment_data)
        _http_fallback_send(template6, token, [BOT10_CHAT_ID])
        import time
        time.sleep(1)

    # 7. رؤية صانع سوق الأوبشن (Options Dealer Vision)
    dealer_data = analyze_options_market_maker()
    if dealer_data:
        template7 = build_template_options_mm(dealer_data)
        _http_fallback_send(template7, token, [BOT10_CHAT_ID])
        import time
        time.sleep(1)

    if success:
        log.info("✅ [Bot10] تم إرسال القوالب بنجاح!")
    else:
        log.error("❌ [Bot10] فشل في إرسال القوالب.")

    return success

if __name__ == "__main__":
    process_and_send_bot10()
