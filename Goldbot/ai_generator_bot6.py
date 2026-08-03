import logging
import traceback
try:
    from Goldbot.ai_client import generate_robust_ai_response
except ImportError:
    from ai_client import generate_robust_ai_response

log = logging.getLogger(__name__)

def generate_cot_report(data: dict) -> str | None:
    """
    يولد تقرير COT للذهب بناءً على الأرقام الحقيقية المسحوبة.
    """
    cot_data = data.get('cot')
    if not cot_data:
        log.warning("⚠️ لا توجد بيانات COT متاحة لتوليد التقرير.")
        return None

    report_date = cot_data.get('report_date', '')
    comm = cot_data.get('commercials', {})
    specs = cot_data.get('large_speculators', {})

    # تحضير سياق الأرقام الحقيقية
    context = f"""
تقرير COT (Legacy) لتاريخ: {report_date}
الأرقام الحقيقية للذهب:
1. Commercials (البنوك والشركات):
   - شراء (Long): {comm.get('long')}
   - بيع (Short): {comm.get('short')}
   - الصافي (Net): {comm.get('net')}

2. Large Speculators (المؤسسات وصناديق الاستثمار):
   - شراء (Long): {specs.get('long')}
   - بيع (Short): {specs.get('short')}
   - الصافي (Net): {specs.get('net')}

السعر الفوري للذهب حالياً: {data.get('gold')}$
"""

    system_prompt = """أنت محلل كمي واقتصادي مؤسسي محترف جداً.
قواعد صارمة:
1. الجودة والدقة بنسبة 100%. لا تخترع أي أرقام من خيالك، استخدم فقط الأرقام المقدمة لك.
2. التحليل يجب أن يكون دقيقاً، حقيقياً، ومبنياً على بيانات COT.
3. اشرح باحترافية وسهولة: "هل المؤسسات ما زالت تدعم الذهب؟"
4. يجب أن يكون التقرير منسقاً بشكل جذاب مع الإيموجيز المناسبة، ومقسماً لفقرات مريحة للعين.
5. استنتج تأثير هذه الأرقام على اتجاه الذهب (صاعد/هابط) على المدى القريب أو المتوسط.
6. ممنوع منعاً باتاً كتابة أي جملة من هذا النوع: "لا يعتبر توصية استثمارية"، "ولا يجب أن يتم اعتباره كتوصية"، أو أي تحذير قانوني أو إخلاء مسؤولية مشابه — لا تكتبه أبداً ولو في آخر التقرير.
"""

    user_prompt = f"""يرجى صياغة تقرير COT بناءً على الهيكل التالي والبيانات الحقيقية المقدمة:

📅 تحليل تقرير COT للذهب – {report_date}
هل المؤسسات ما زالت تدعم الذهب؟
[اكتب استنتاجك الاحترافي بناءً على الأرقام الحقيقية للسعر وصافي المراكز]

📊 أبرز الأرقام:
🟢 Commercials (البنوك والشركات):
شراء: [رقم] عقد
بيع: [رقم] عقد
صافي: [رقم] عقد

🔵 Large Speculators (المؤسسات وصناديق الاستثمار):
شراء: [رقم] عقد
بيع: [رقم] عقد
صافي: [رقم] عقد

🎯 التأثير المتوقع على الذهب:
[اشرح التأثير بوضوح واحترافية]

البيانات الحقيقية:
{context}
"""

    try:
        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1500)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير COT: {e}\n{traceback.format_exc()}")
        return None

def generate_supply_demand_report(data: dict) -> str | None:
    from datetime import datetime
    import traceback

    report_date = datetime.now().strftime('%d %B %Y')

    # ── الأرقام الحقيقية من البيانات المحسوبة ──
    gold      = data.get('gold', 0)
    dxy       = data.get('dxy', 0)
    dxy_pct   = round(data.get('dxy_pct', 0), 2)
    dxy_val   = round(dxy, 2) if dxy else 0
    pivot     = data.get('pivot', 0)

    # تغير الذهب الحقيقي (24 ساعة)
    hist      = data.get('hist_ctx', {})
    gold_chg  = round(hist.get('chg_1d', 0), 2) if hist else 0
    gold_pct  = round(hist.get('pct_1d', 0), 2) if hist else 0

    # توحيد مناطق العرض والطلب لتكون منطقية ومتباعدة (استخدام البيفوتات يضمن دقة المؤسسات)
    supply1   = data.get('r1', 0)
    supply2   = data.get('r2', 0)
    demand1   = data.get('s1', 0)
    demand2   = data.get('s2', 0)

    # اتجاه الدولار والذهب
    dxy_dir   = "يرتفع" if dxy_pct > 0 else "ينخفض"
    gold_dir  = "ارتفاعاً" if gold_chg > 0 else "انخفاضاً"
    gold_dxy_relation = (
        "وهو ضغط طبيعي على الذهب كأصل مقابل الدولار"
        if (dxy_pct > 0 and gold_chg < 0)
        else "وهو دعم طبيعي للذهب كأصل مقابل الدولار"
        if (dxy_pct < 0 and gold_chg > 0)
        else "في ما يُشير إلى تحرك مستقل للذهب عن الدولار"
    )

    # ── توليد السيناريوهات منطقياً ومسبقاً لمنع الـ AI من الخطأ ──
    if gold >= pivot:
        strong_scenario = f"طالما الذهب يتداول بثبات أعلى نقطة التوازن ({pivot}$)، فاحتمال استمرار الصعود نحو {supply1}$ ثم {supply2}$ قائم بقوة."
        alt_scenario = f"إذا كسر السعر نقطة التوازن ({pivot}$) للأسفل واستقر تحتها، فمن المحتمل أن يستهدف مناطق الطلب عند {demand1}$."
    else:
        strong_scenario = f"طالما الذهب يتداول بضغط أسفل نقطة التوازن ({pivot}$)، فاحتمال استمرار الهبوط نحو {demand1}$ ثم {demand2}$ هو الأرجح."
        alt_scenario = f"إذا نجح السعر في اختراق نقطة التوازن ({pivot}$) للأعلى واستقر فوقها، فمن المحتمل أن يستهدف مناطق العرض عند {supply1}$."

    # السياق
    context = f"""
بيانات حية محسوبة فعلياً (ممنوع تغيير أي رقم):
- سعر الذهب الحالي: {gold}$
- تغير الذهب: {'+' if gold_chg >= 0 else ''}{gold_chg}$ ({'+' if gold_pct >= 0 else ''}{gold_pct}%)
- مؤشر الدولار DXY: {dxy_val} ({dxy_dir} بنسبة {abs(dxy_pct)}%)
- العلاقة: {gold_dxy_relation}
- المقاومة 1 و 2: {supply1}$ ، {supply2}$
- الدعم 1 و 2: {demand1}$ ، {demand2}$
- السيناريو الأقوى: {strong_scenario}
- السيناريو البديل: {alt_scenario}
"""

    system_prompt = """أنت محلل فني خبير ومحترف.
قواعد صارمة:
1. استخدم النص والأرقام التي تم توفيرها في "السيناريو الأقوى" و "السيناريو البديل" نصياً دون تغيير أرقامها أبداً.
2. لا تخترع أي أرقام من خيالك، ولا تغير ترتيب المستويات.
3. لا تكتب أي تحذير قانوني أو إخلاء مسؤولية.
4. التزم بالهيكل المقدم حرفياً.
"""

    user_prompt = f"""اكتب تقرير الذهب. عبّئ الأرقام واستخدم السيناريوهات المرفقة في البيانات حرفياً:

📅 تحليل الذهب — مناطق العرض والطلب | {report_date}
شهد الذهب اليوم {gold_dir} بمقدار {abs(gold_chg)}$ ({abs(gold_pct)}%)، بالتزامن مع أن مؤشر الدولار (DXY) {dxy_dir} بنسبة {abs(dxy_pct)}%، {gold_dxy_relation}.

🔹 مناطق العرض (المقاومة): {supply1}$ ثم {supply2}$
🔹 مناطق الطلب (الدعم): {demand1}$ ثم {demand2}$

السيناريوهات المحتملة (فنية):
📉 السيناريو الأقوى:
{strong_scenario}

📈 السيناريو البديل:
{alt_scenario}

البيانات المرجعية (انسخ السيناريوهات منها كما هي):
{context}
"""

    try:
        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1500)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير العرض والطلب: {e}\n{traceback.format_exc()}")
        return None


def generate_technical_bias_report(data: dict) -> str | None:
    from datetime import datetime
    import traceback
    
    report_date = datetime.now().strftime('%d %B %Y')
    
    gold = data.get('gold', 0)
    pivot = data.get('pivot', 0)
    r1, r2, r3 = data.get('r1', 0), data.get('r2', 0), data.get('r3', 0)
    s1, s2, s3 = data.get('s1', 0), data.get('s2', 0), data.get('s3', 0)
    bias = data.get('confluence', {}).get('bias', 'NEUTRAL')
    
    context = f"""
السعر الحالي: {gold}$
الارتكاز: {pivot}$
دعم 1: {s1}$ | دعم 2: {s2}$
مقاومة 1: {r1}$ | مقاومة 2: {r2}$
الاتجاه العام (Bias): {bias}
"""
    system_prompt = """أنت محلل فني. التزم حرفياً بالهيكل المقدم وضع الأرقام الحقيقية في أماكنها بناءً على البيانات. اكمل الفراغات بأسلوب احترافي يتناسب مع الهيكل."""
    user_prompt = f"""الرجاء تعبئة هذا الهيكل:

📅 تحليل الذهب | {report_date}
الذهب XAUUSD يحافظ على [ميل إيجابي/سلبي] قصير الأجل بعد ارتداده من منطقة [أقرب دعم أو مقاومة تم الارتداد منها] تقريبًا، مع تحسن واضح في الحركة السعرية واستمرار الثبات [أعلى/أسفل] نطاق [منطقة الدعم أو المقاومة الحالية]، وهو ما يمنح السيناريو [الصاعد/الهابط] أفضلية تُقدّر بنحو [65% مثلا] لاستهداف [الهدف 1] ثم [الهدف 2]، بينما يؤدي اختراق المنطقة الأخيرة والثبات [أعلاها/أسفلها] إلى تعزيز فرص امتداد [الصعود/الهبوط] نحو [الهدف 3]

في المقابل، يبقى السيناريو البديل بنسبة [35% مثلا] قائمًا إذا فقد السعر [منطقة دعم/مقاومة بديلة]، ما قد يعيد الضغط [البيعي/الشرائي] فنيا ولذلك تظل منطقة [نطاق الفصل] هي نطاق الفصل الأهم بين استمرار التعافي وعودة الضعف فنيا

البيانات:
{context}"""
    try:
        return generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1500)
    except Exception as e:
        log.error(f"❌ خطأ: {e}")
        return None

def generate_standard_breakout_report(data: dict) -> str | None:
    import traceback
    gold = data.get('gold', 0)
    atr = data.get('atr', 10)
    
    # حساب نقطة اختراق الشراء والبيع (مسافة متساوية من السعر الحالي)
    buy_level = round(gold + atr*0.3)
    sell_level = round(gold - atr*0.3)
    
    # حساب الأهداف للشراء
    b_tp1, b_tp2, b_tp3 = buy_level+5, buy_level+10, buy_level+20
    b_sl = buy_level-5
    
    # حساب الأهداف للبيع
    s_tp1, s_tp2, s_tp3 = sell_level-5, sell_level-10, sell_level-20
    s_sl = sell_level+5

    report = f"""🔵صفقة على نظام كسر الارقام

- كسر السعر للشراء({buy_level}) أهدافك كالاتي 
🎯 TP1:{b_tp1}
🎯 TP2:{b_tp2}
🎯 TP3:{b_tp3}
🎯 TP4:open

  {b_sl}⛔️ وقف الخسارة :

- كسر السعر للبيع ({sell_level}) أهدافك كالاتي
🎯 TP1:{s_tp1}
🎯 TP2:{s_tp2}
🎯 TP3:{s_tp3}
🎯 TP4:open

 {s_sl}⛔️ وقف الخسارة : 

الرجاء ادارة مخاطر راس المال💵"""
    return report

def generate_box_breakout_report(data: dict) -> str | None:
    import traceback
    gold = data.get('gold', 0)
    
    # نظام الصندوق المحكم: المسافة بين الشراء والبيع ضيقة (نطاق عرضي)
    # والوقف يكون رقم واحد يمثل منتصف النطاق.
    buy_level = round(gold + 3)
    sell_level = round(gold - 4)
    mid_sl = round((buy_level + sell_level) / 2) # نفس الوقف للجهتين
    
    b_tp1, b_tp2, b_tp3 = buy_level+7, buy_level+11, buy_level+15
    s_tp1, s_tp2, s_tp3 = sell_level-5, sell_level-10, sell_level-20

    report = f"""🔵صفقة على نظام كسر الارقام (نطاق ضيق بوقف موحد)

- كسر السعر للشراء({buy_level}) أهدافك كالاتي 
🎯 TP1:{b_tp1}
🎯 TP2:{b_tp2}
🎯 TP3:{b_tp3}
🎯 TP4:open
 {mid_sl}⛔️ وقف الخسارة :

- كسر السعر للبيع ({sell_level}) أهدافك كالاتي
🎯 TP1:{s_tp1}
🎯 TP2:{s_tp2}
🎯 TP3:{s_tp3}
🎯 TP4:open

{mid_sl}⛔️ وقف الخسارة : 

الرجاء ادارة مخاطر راس المال💵"""
    return report

def generate_market_session_report(data: dict) -> str | None:
    from datetime import datetime, timezone, timedelta
    import traceback

    try:
        CAIRO_TZ = timezone(timedelta(hours=3))
        now_cairo = datetime.now(CAIRO_TZ)
        hour = now_cairo.hour

        # تحديد الجلسة الحالية
        if 2 <= hour < 10:
            session_name = "الجلسة الآسيوية (طوكيو / سيدني)"
            session_time = "تبدأ 02:00 صباحاً وتنتهي 10:00 صباحاً بتوقيت القاهرة"
        elif 10 <= hour < 15:
            session_name = "الجلسة الأوروبية (لندن)"
            session_time = "تبدأ 10:00 صباحاً وتنتهي 06:00 مساءً بتوقيت القاهرة"
        elif 15 <= hour < 23:
            session_name = "الجلسة الأمريكية (نيويورك)"
            session_time = "تبدأ 03:00 مساءً وتنتهي 11:00 مساءً بتوقيت القاهرة"
        else:
            session_name = "فترة التداخل والإغلاق (سيدني مبكراً)"
            session_time = "من 11:00 مساءً إلى 02:00 صباحاً بتوقيت القاهرة"

        gold = data.get("gold", 0)
        daily_high = data.get("daily_high", gold)
        daily_low = data.get("daily_low", gold)
        
        # مقدار الحركة اليوم
        daily_range = round(daily_high - daily_low, 2) if daily_high and daily_low else 0
        atr = data.get("atr", 30)

        # تحديد قوة الحركة
        if daily_range > atr * 1.2:
            vol_level = "قوية جداً وعنيفة 🔴"
        elif daily_range > atr * 0.7:
            vol_level = "متوسطة إلى قوية 🟡"
        elif daily_range > atr * 0.4:
            vol_level = "طبيعية ومعتدلة 🟢"
        else:
            vol_level = "ضعيفة وتجميعية (نطاق عرضي ضيق) ⚪"

        # نسبة التغير اليومي
        hist = data.get('hist_ctx', {})
        gold_chg  = round(hist.get('chg_1d', 0), 2) if hist else 0
        gold_pct  = round(hist.get('pct_1d', 0), 2) if hist else 0

        context = f"""
معلومات حية ودقيقة 100%:
- الجلسة الحالية: {session_name}
- توقيت الجلسة: {session_time}
- السعر الحالي: {gold}$
- أعلى سعر اليوم: {daily_high}$
- أدنى سعر اليوم: {daily_low}$
- إجمالي حجم التحرك (النطاق): {daily_range}$
- تقييم الحركة آلياً: {vol_level}
- التغير من الافتتاح: {'+' if gold_chg>=0 else ''}{gold_chg}$ ({'+' if gold_pct>=0 else ''}{gold_pct}%)
"""

        system_prompt = """أنت محلل أسواق مالية محترف. 
العميل يطلب تقريراً مباشراً وسريعاً يوضح "تحركات السوق الحالية للذهب".
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً. لا تؤلف أي رقم.
2. اذكر اسم الجلسة الحالية ومواعيدها كما هي مرفقة.
3. اذكر تقييم الحركة (قوية، متوسطة، ضعيفة) كما هو مرفق في البيانات بناءً على حسابات الخوارزمية.
4. اكتب فقرة تحليلية واحدة (تحت عنوان "💡 قراءة الحركة:") بأسلوب احترافي تشرح فيها حالة السيولة باختصار بناءً على النطاق السعري وتقييم الحركة. لا تستخدم أسلوب الروبوتات بل أسلوب محلل بورصة مخضرم في وول ستريت.
5. لا تكتب أي إخلاء مسؤولية.
"""

        user_prompt = f"""قم بإنشاء "تقرير تحركات السوق والسيولة للذهب" بناءً على البيانات التالية.
استخدم هذا الهيكل تماماً:
🌊 التقرير المباشر لتحركات السوق والسيولة

⏱️ الجلسة الحالية: [اسم الجلسة] ([توقيت الجلسة])
📊 تقييم السيولة: تحركات [تقييم الحركة آلياً]

▪️ السعر الحالي: [سعر]$
▪️ أعلى سعر: [أعلى]$
▪️ أدنى سعر: [أدنى]$
▪️ حجم النطاق الكلي اليوم: [حجم النطاق]$
▪️ نسبة التغير: [النسبة]%

💡 قراءة الحركة:
[فقرة احترافية تشرح وضع السوق الحالي للذهب للعميل بوضوح وقوة، بناءً على حجم التحرك وقوته].

البيانات:
{context}
"""

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1000)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير السيولة: {e}\n{traceback.format_exc()}")
        return None

def generate_liquidity_flow_report(data: dict) -> str | None:
    from datetime import datetime, timezone, timedelta
    import traceback

    try:
        CAIRO_TZ = timezone(timedelta(hours=3))
        now_cairo = datetime.now(CAIRO_TZ)
        hour = now_cairo.hour

        # تحديد الجلسة الحالية
        if 2 <= hour < 10:
            session_name = "الجلسة الآسيوية (طوكيو / سيدني)"
            session_time = "تبدأ 02:00 صباحاً وتنتهي 10:00 صباحاً بتوقيت القاهرة"
        elif 10 <= hour < 15:
            session_name = "الجلسة الأوروبية (لندن)"
            session_time = "تبدأ 10:00 صباحاً وتنتهي 06:00 مساءً بتوقيت القاهرة"
        elif 15 <= hour < 23:
            session_name = "الجلسة الأمريكية (نيويورك)"
            session_time = "تبدأ 03:00 مساءً وتنتهي 11:00 مساءً بتوقيت القاهرة"
        else:
            session_name = "فترة التداخل والإغلاق (سيدني مبكراً)"
            session_time = "من 11:00 مساءً إلى 02:00 صباحاً بتوقيت القاهرة"

        gold = data.get("gold", 0)
        vwap = data.get("vwap", gold)
        atr = data.get("atr", 30)
        r1 = data.get("r1", gold + atr * 0.5)
        s1 = data.get("s1", gold - atr * 0.5)
        
        hist = data.get('hist_ctx', {})
        gold_chg = round(hist.get('chg_1d', 0), 2) if hist else 0

        # اتجاه السيولة الحالي
        if gold_chg > 0 and gold > vwap:
            liq_dir = "صاعد 📈"
        elif gold_chg < 0 and gold < vwap:
            liq_dir = "هابط 📉"
        else:
            liq_dir = "متذبذب / حيادي ⚖️ (يبحث عن اتجاه)"

        # حساب أهداف السيولة الاحترافية (Liquidity Pools / Stop Hunts)
        # 1. نستخرج مناطق السيولة بناءً على القمم والقيعان الرئيسية
        sw_h = float(data.get('swing_high') or r2)
        sw_l = float(data.get('swing_low') or s2)
        
        # التأكد من منطقية مناطق السيولة بناءً على السعر الحالي
        if sw_h <= gold + (atr * 0.1): 
            sw_h = float(data.get('r3') or gold + (atr * 0.8))
        if sw_l >= gold - (atr * 0.1): 
            sw_l = float(data.get('s3') or gold - (atr * 0.8))

        # 2. منطقة السحب الفعلي للسيولة تمتد بعد القمة/القاع لضرب الوقف
        upper_target = round(sw_h + 2.0, 2)
        lower_target = round(sw_l - 2.0, 2)

        context = f"""
معلومات حية ودقيقة 100%:
- اتجاه السيولة آلياً: {liq_dir}
- الإطار الزمني والصلاحية: {session_name} ({session_time})
- السعر الحالي: {gold}$
- قمة السيولة (BSL): {sw_h}$ والهدف الممتد: {upper_target}$
- قاع السيولة (SSL): {sw_l}$ والهدف الممتد: {lower_target}$
"""

        system_prompt = """أنت محلل أسواق مالية محترف. 
العميل يطلب تقريراً مباشراً وسريعاً يوضح "اتجاه السيولة اللحظية للذهب ومناطق سحب السيولة (Liquidity Pools)".
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً. لا تؤلف أي رقم.
2. اذكر اسم الجلسة الحالية ومواعيدها كما هي مرفقة.
3. اكتب فقرة تحليلية واحدة (تحت عنوان "💡 تحليل تدفق الأموال:") بأسلوب احترافي تشرح فيها كيف يقرأ العميل هذا الاتجاه، ولماذا يستهدف السعر المستويات المذكورة (لضرب الوقف أو سحب السيولة).
4. استخدم لغة سوقية قوية (مثلاً: امتصاص السيولة، سحب أو ضرب الوقف، تدفق السيولة).
5. لا تكتب أي إخلاء مسؤولية.
"""

        user_prompt = f"""قم بإنشاء "تقرير اتجاه السيولة اللحظية ومناطق السحب للذهب" بناءً على البيانات التالية.
استخدم هذا الهيكل تماماً:
رادار السيولة اللحظي (Liquidity Flow) 💧🎯

🧭 اتجاه السيولة الحالي: [الاتجاه المرفق]
⏱️ فترة الصلاحية: فعالة خلال [اسم الجلسة] ([توقيت الجلسة])

🎯 أهداف السيولة ومناطق الجذب السعري (Liquidity Pools):
▪️ مسار السيولة الصاعد (BSL): السعر يستهدف اختراق القمة {sw_h}$ وصولاً إلى {upper_target}$ لامتصاص السيولة الشرائية وضرب وقفات الخسارة.
▪️ مسار السيولة الهابط (SSL): السعر يستهدف كسر القاع {sw_l}$ وصولاً إلى {lower_target}$ لامتصاص السيولة البيعية وضرب وقفات الخسارة.

💡 تحليل تدفق الأموال:
[فقرة احترافية تشرح وضع السوق الحالي بوضوح بناءً على اتجاه السيولة والأهداف].

البيانات:
{context}
"""

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1000)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير مسار السيولة: {e}\n{traceback.format_exc()}")
        return None


def generate_sudden_liquidity_report(data: dict) -> str | None:
    from datetime import datetime, timezone, timedelta
    import traceback

    try:
        CAIRO_TZ = timezone(timedelta(hours=3))
        now_cairo = datetime.now(CAIRO_TZ)
        
        gold = data.get("gold", 0)
        atr = data.get("atr", 30)
        rel_vol = data.get("rel_vol", 1.0)
        
        hist = data.get('hist_ctx', {})
        gold_chg = round(hist.get('chg_1d', 0), 2) if hist else 0

        # تحديد اتجاه السيولة الفجائية
        if gold_chg > 0:
            sudden_dir = "سيولة شرائية فجائية صاعدة 🚀"
            target_price = round(gold + (atr * 0.8), 2)  # امتداد الهدف بعد دخول السيولة
        else:
            sudden_dir = "سيولة بيعية فجائية هابطة 🩸"
            target_price = round(gold - (atr * 0.8), 2)

        # تحديد قوة السيولة الفجائية
        if rel_vol > 1.5:
            vol_status = f"سيولة عنيفة جداً (أعلى من المعدل الطبيعي بـ {round(rel_vol*100-100)}%)"
        elif rel_vol > 1.0:
            vol_status = f"سيولة نشطة مفاجئة (أعلى من المعدل بـ {round(rel_vol*100-100)}%)"
        else:
            vol_status = "لا توجد سيولة فجائية غير طبيعية حالياً، حركة اعتيادية."
            # في حال عدم وجود سيولة فجائية، نضع هدفاً قريباً
            target_price = round(gold + (atr * 0.3) if gold_chg > 0 else gold - (atr * 0.3), 2)

        # تحديد التوقيت (صلاحية السيولة الفجائية تكون قصيرة الأمد عادة 2-4 ساعات)
        end_time = now_cairo + timedelta(hours=3)
        time_validity = f"من الآن ({now_cairo.strftime('%I:%M %p')}) وحتى ({end_time.strftime('%I:%M %p')}) بتوقيت القاهرة"

        context = f"""
معلومات حية ودقيقة 100%:
- وضع السيولة الفجائية: {vol_status}
- اتجاه السيولة الفجائية: {sudden_dir}
- السعر الحالي: {gold}$
- السعر المستهدف للسيولة الفجائية: {target_price}$
- الإطار الزمني والصلاحية: {time_validity}
"""

        system_prompt = """أنت محلل أسواق مالية محترف، متخصص في رصد "السيولة الفجائية (Smart Money / Sudden Volume)".
العميل يطلب تقريراً مباشراً يوضح إذا كان هناك سيولة دخلت فجأة، إلى أين تتجه، وما هو هدفها الرقمي الدقيق، ومن متى لمتى.
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً. لا تؤلف أي رقم.
2. اذكر السعر المستهدف والمدة الزمنية كما هي مرفقة تماماً.
3. اكتب فقرة تحليلية واحدة بأسلوب احترافي تشرح فيها تأثير هذه السيولة الفجائية على السعر، ولماذا يستهدف الرقم المذكور بناءً على الزخم اللحظي.
4. استخدم لغة "وول ستريت" (مثلاً: انفجار سعري، سيولة ذكية، ضخ سيولة فجائي).
5. لا تكتب أي إخلاء مسؤولية.
"""

        user_prompt = f"""قم بإنشاء "تقرير السيولة الفجائية للذهب" بناءً على البيانات التالية.
استخدم هذا الهيكل تماماً:
🚨 إنذار السيولة الفجائية (Smart Money Tracker) ⚡

📊 وضع السيولة الآن: [وضع السيولة الفجائية]
🧭 اتجاه الضخ: [اتجاه السيولة الفجائية]
⏱️ فترة الفعالية: [الإطار الزمني والصلاحية]

🎯 أهداف السيولة الفجائية:
▪️ السعر الحالي: [سعر]$
▪️ السعر المستهدف للسيولة الفجائية: السعر يستهدف ضرب مستوى [السعر المستهدف]$ بقوة الزخم الحالي.

💡 تحليل حركة الأموال الذكية:
[فقرة احترافية تشرح وضع السوق المرفق بوضوح، مع التركيز على السيولة التي دخلت فجأة وكيف ستدفع السعر نحو الهدف المذكور في المدة الزمنية المحددة].

البيانات:
{context}
"""

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1000)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير السيولة الفجائية: {e}\n{traceback.format_exc()}")
        return None

def generate_asian_session_liquidity_report(data: dict) -> str | None:
    from datetime import datetime, timezone, timedelta
    import traceback

    try:
        gold = data.get("gold", 0)
        atr = data.get("atr", 30)
        
        # أهداف الجلسة الآسيوية غالباً ما تكون هادئة وتميل لتشكيل قمم وقيعان (نطاق عرضي)
        # لذا يتم الاعتماد على نسبة أقل من الـ ATR لتمثيل النطاق المستهدف
        asian_upper_target = round(gold + (atr * 0.35), 2)
        asian_lower_target = round(gold - (atr * 0.35), 2)

        time_validity = "من 02:00 صباحاً وحتى 10:00 صباحاً بتوقيت القاهرة"

        context = f"""
معلومات حية ودقيقة 100%:
- السعر الحالي: {gold}$
- هدف السيولة الصاعد للجلسة الآسيوية: {asian_upper_target}$
- هدف السيولة الهابط للجلسة الآسيوية: {asian_lower_target}$
- توقيت الجلسة: {time_validity}
"""

        system_prompt = """أنت محلل أسواق مالية محترف، متخصص في تحليل "السيولة وجلسات التداول (Session Liquidity)".
العميل يطلب تقريراً مباشراً يوضح أهداف سيولة "الجلسة الآسيوية (طوكيو)" فقط.
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً. لا تؤلف أي رقم.
2. اذكر أهداف السيولة ومواعيد الجلسة كما هي مرفقة.
3. اكتب فقرة تحليلية واحدة بأسلوب احترافي تشرح فيها طبيعة سيولة الجلسة الآسيوية (غالباً ما تكون هادئة وتبني نطاقاً عرضياً يتم اختراقه لاحقاً في جلسة لندن)، ولماذا السعر يستهدف المستويات المذكورة كنطاق (Range).
4. لا تكتب أي إخلاء مسؤولية.
"""

        user_prompt = f"""قم بإنشاء "تقرير سيولة الجلسة الآسيوية للذهب" بناءً على البيانات التالية.
استخدم هذا الهيكل تماماً:
🏮 تقرير سيولة الجلسة الآسيوية (Asian Range) 🎯

⏱️ توقيت الجلسة: فعالة [توقيت الجلسة]

🎯 مستهدفات السيولة والنطاق السعري (Asian Box):
▪️ السعر الحالي: [سعر]$
▪️ هدف السيولة الشرائية (الحد العلوي): السعر يستهدف مستوى [الرقم العلوي]$ كقمة متوقعة للجلسة.
▪️ هدف السيولة البيعية (الحد السفلي): السعر يستهدف مستوى [الرقم السفلي]$ كقاع متوقع للجلسة.

💡 تحليل الجلسة الآسيوية:
[فقرة احترافية تشرح وضع سيولة الجلسة الآسيوية وكيفية تشكيلها لنطاق سعري (Range) وتأثير ذلك بناءً على الأرقام المرفقة].

البيانات:
{context}
"""

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1000)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير سيولة الجلسة الآسيوية: {e}\n{traceback.format_exc()}")
        return None

def generate_european_session_liquidity_report(data: dict) -> str | None:
    from datetime import datetime, timezone, timedelta
    import traceback

    try:
        gold = data.get("gold", 0)
        atr = data.get("atr", 30)
        
        # الجلسة الأوروبية (لندن) تتميز بالسيولة العالية وتحديد الاتجاه
        # لذا نستخدم نسبة أكبر من الـ ATR لتمثيل النطاق المستهدف الفعلي (اختراق النطاق الآسيوي)
        euro_upper_target = round(gold + (atr * 0.6), 2)
        euro_lower_target = round(gold - (atr * 0.6), 2)

        time_validity = "من 10:00 صباحاً وحتى 06:00 مساءً بتوقيت القاهرة"

        context = f"""
معلومات حية ودقيقة 100%:
- السعر الحالي: {gold}$
- هدف السيولة الصاعد للجلسة الأوروبية: {euro_upper_target}$
- هدف السيولة الهابط للجلسة الأوروبية: {euro_lower_target}$
- توقيت الجلسة: {time_validity}
"""

        system_prompt = """أنت محلل أسواق مالية محترف، متخصص في "سيولة جلسة لندن / الجلسة الأوروبية".
العميل يطلب تقريراً يوضح أهداف سيولة "الجلسة الأوروبية" للذهب.
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً. لا تؤلف أي رقم.
2. اذكر أهداف السيولة ومواعيد الجلسة كما هي مرفقة.
3. اكتب فقرة تحليلية احترافية تشرح فيها كيف أن الجلسة الأوروبية (لندن) تتميز بالسيولة العالية وغالباً ما تضرب سيولة الجلسة الآسيوية لتحدد الاتجاه الحقيقي لليوم، ولماذا يستهدف السعر هذه المستويات المذكورة.
4. استخدم مصطلحات مثل (السيولة الأوروبية القوية، ضرب السيولة الآسيوية، تحديد الاتجاه، London Session).
5. لا تكتب أي إخلاء مسؤولية.
"""

        user_prompt = f"""قم بإنشاء "تقرير سيولة الجلسة الأوروبية للذهب" بناءً على البيانات التالية.
استخدم هذا الهيكل تماماً:
🏛️ تقرير سيولة الجلسة الأوروبية (London Session) 🎯

⏱️ توقيت الجلسة: فعالة [توقيت الجلسة]

🎯 مستهدفات السيولة العالية (London Targets):
▪️ السعر الحالي: [سعر]$
▪️ هدف السيولة الشرائية العلوية: السعر يستهدف مستوى [الرقم العلوي]$ لامتصاص السيولة والبحث عن الزخم الصاعد.
▪️ هدف السيولة البيعية السفلية: السعر يستهدف مستوى [الرقم السفلي]$ لامتصاص السيولة والبحث عن الزخم الهابط.

💡 تحليل الجلسة الأوروبية (لندن):
[فقرة احترافية تشرح طبيعة سيولة الجلسة الأوروبية القوية، وكيف تضرب سيولة الجلسة السابقة لتأسيس الاتجاه اليومي، مع الاستناد للأرقام المرفقة].

البيانات:
{context}
"""

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1000)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير سيولة الجلسة الأوروبية: {e}\n{traceback.format_exc()}")
        return None

def generate_american_session_liquidity_report(data: dict) -> str | None:
    from datetime import datetime, timezone, timedelta
    import traceback

    try:
        gold = data.get("gold", 0)
        atr = data.get("atr", 30)
        
        # الجلسة الأمريكية (نيويورك) هي الأعنف وتتسم بالسيولة الضخمة جداً
        # لذا نستخدم نسبة أكبر من الـ ATR لتمثيل النطاق المستهدف الفعلي (اختراق نطاق لندن/آسيا)
        us_upper_target = round(gold + (atr * 0.7), 2)
        us_lower_target = round(gold - (atr * 0.7), 2)

        time_validity = "من 03:00 مساءً وحتى 11:00 مساءً بتوقيت القاهرة"

        context = f"""
معلومات حية ودقيقة 100%:
- السعر الحالي: {gold}$
- هدف السيولة الصاعد للجلسة الأمريكية: {us_upper_target}$
- هدف السيولة الهابط للجلسة الأمريكية: {us_lower_target}$
- توقيت الجلسة: {time_validity}
"""

        system_prompt = """أنت محلل أسواق مالية محترف، متخصص في "سيولة جلسة نيويورك / الجلسة الأمريكية".
العميل يطلب تقريراً يوضح أهداف سيولة "الجلسة الأمريكية" للذهب.
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً. لا تؤلف أي رقم.
2. اذكر أهداف السيولة ومواعيد الجلسة كما هي مرفقة.
3. اكتب فقرة تحليلية احترافية تشرح فيها كيف أن الجلسة الأمريكية (نيويورك) تتميز بالسيولة الأعنف في السوق (خصوصاً وقت تداخلها مع لندن)، وغالباً ما تصنع انعكاسات قوية أو امتداداً للاتجاه وتستهدف السيولة العميقة، ولماذا يستهدف السعر هذه المستويات المذكورة.
4. استخدم مصطلحات مثل (السيولة الأمريكية العنيفة، تداخل الجلسات، انعكاس الاتجاه، سحب سيولة عميقة، New York Session).
5. لا تكتب أي إخلاء مسؤولية.
"""

        user_prompt = f"""قم بإنشاء "تقرير سيولة الجلسة الأمريكية للذهب" بناءً على البيانات التالية.
استخدم هذا الهيكل تماماً:
🗽 تقرير سيولة الجلسة الأمريكية (New York Session) 🎯

⏱️ توقيت الجلسة: فعالة [توقيت الجلسة]

🎯 مستهدفات السيولة العميقة (New York Targets):
▪️ السعر الحالي: [سعر]$
▪️ هدف السيولة الشرائية العلوية: السعر يستهدف مستوى [الرقم العلوي]$ لامتصاص السيولة الشرائية واختبار قوى المشترين.
▪️ هدف السيولة البيعية السفلية: السعر يستهدف مستوى [الرقم السفلي]$ لامتصاص السيولة البيعية واختبار قوى البائعين.

💡 تحليل الجلسة الأمريكية (نيويورك):
[فقرة احترافية تشرح طبيعة سيولة الجلسة الأمريكية العنيفة، وتأثير تداخلها مع جلسة لندن، وكيف تبحث عن أهداف السيولة العميقة، مع الاستناد للأرقام المرفقة].

البيانات:
{context}
"""

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1000)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير سيولة الجلسة الأمريكية: {e}\n{traceback.format_exc()}")
        return None

def generate_scalping_setup_report(data: dict) -> str | None:
    from datetime import datetime, timezone, timedelta
    import traceback

    try:
        gold = data.get("gold", 0)
        atr = data.get("atr", 30)
        vwap = data.get("vwap", gold)
        
        # تحديد الاتجاه اللحظي (شراء أو بيع) بناءً على السعر و VWAP
        is_buy = gold >= vwap
        
        trade_type = "الشراء" if is_buy else "البيع"
        above_below = "اعلي" if is_buy else "اسفل"
        
        if is_buy:
            zone1 = round(gold - (atr * 0.15), 2)
            zone2 = round(gold - (atr * 0.25), 2)
            cond_level = round(gold - (atr * 0.35), 2)
            stop_loss = round(gold - (atr * 0.50), 2)
            scalp_target = round(gold + (atr * 0.25), 2)
            target1 = round(gold + (atr * 0.40), 2)
            target2 = round(gold + (atr * 0.60), 2)
            target3 = round(gold + (atr * 0.90), 2)
        else:
            zone1 = round(gold + (atr * 0.15), 2)
            zone2 = round(gold + (atr * 0.25), 2)
            cond_level = round(gold + (atr * 0.35), 2)
            stop_loss = round(gold + (atr * 0.50), 2)
            scalp_target = round(gold - (atr * 0.25), 2)
            target1 = round(gold - (atr * 0.40), 2)
            target2 = round(gold - (atr * 0.60), 2)
            target3 = round(gold - (atr * 0.90), 2)

        # تجهيز النص المكتوب بدقة 100% ليتم إرساله كما هو
        exact_text = f"الدهب {trade_type} مناسب الان بالقرب من {zone1} / {zone2} بشرط الثبات {above_below} {cond_level} فريم نصف ساعه و عدم كسر المستوي نهائيا ستوب ثابت لأي {trade_type} {stop_loss} هدف {scalp_target} للسكالبينج اهداف {trade_type} {target1} / {target2} / {target3}"

        system_prompt = """أنت روبوت تنفيذي دقيق جداً.
العميل أرسل هيكلاً ثابتاً لصفقة سكالبينج، ومهمتك الوحيدة هي إعادة كتابة النص الذي سأعطيه لك كما هو تماماً بالحرف الواحد دون إضافة أي كلمة أخرى أو رموز، فقط أعد طباعة النص.
لا تكتب أي مقدمات أو اعتذارات أو استنتاجات.
"""

        user_prompt = f"""قم بإخراج هذا النص كما هو بالضبط دون أي إضافات:
{exact_text}
"""

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=200)
        
        # لضمان عدم وجود أي إضافات من الـ AI
        if not ai_content or len(ai_content) < 10:
            ai_content = exact_text
            
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير صفقة السكالبينج: {e}\n{traceback.format_exc()}")
        return None

def generate_fed_scenarios_report(data: dict) -> str | None:
    from datetime import datetime, timezone, timedelta
    import traceback

    try:
        gold = data.get("gold", 0)
        atr = data.get("atr", 30)
        
        # مستويات الفيدرالي تتطلب نطاقات تذبذب عنيفة جداً (أضعاف الـ ATR الطبيعي)
        hawk_target_1 = round(gold - (atr * 0.8), 2)
        hawk_target_2 = round(gold - (atr * 1.5), 2)
        
        hike_break = hawk_target_2
        hike_target_1 = round(gold - (atr * 2.5), 2)
        hike_target_2 = round(gold - (atr * 3.5), 2)
        
        dovish_target = round(gold + (atr * 2.0), 2)

        # النص بالهيكل الثابت المرفق من العميل
        exact_text = f"""❓  السيناريو المتوقع من الفيدرالي اليوم
التأثير على الدولار الأمريكي
التأثير على أسعار الذهب (XAU)
📌📌  تثبيت الفائدة مع لهجة متشددة / تلويح برفع قادم
الدولار يحافظ على مكاسبه ويميل للصعود
الذهب   نحو مستويات {hawk_target_1} _ {hawk_target_2}$
🔼🔼 رفع مفاجئ للفائدة بـ 25 نقطة أساس
الدولار قفزة قوية وفورية
الذهب هبوط سريع لكسر حاجز {hike_break}$ الى {hike_target_1} - {hike_target_2}
💱  تثبيت الفائدة مع لهجة مرنة أو مهدئة لأسواق الطاقة
الدولار يتراجع ويفقد مستوياته الشهرية العليا
الذهب ارتداد سريع لأعلى يتجاوز {dovish_target}$"""

        system_prompt = """أنت روبوت تنفيذي دقيق جداً.
العميل أرسل هيكلاً ثابتاً لسيناريوهات الفيدرالي، ومهمتك الوحيدة هي إعادة كتابة النص الذي سأعطيه لك كما هو تماماً بالحرف الواحد والرموز والتنسيق، دون إضافة أي كلمة أخرى.
لا تكتب أي مقدمات أو اعتذارات أو استنتاجات.
"""

        user_prompt = f"""قم بإخراج هذا النص كما هو بالضبط دون أي إضافات:
{exact_text}
"""

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=300)
        
        # لضمان عدم وجود أي إضافات من الـ AI (في حال أخطأ، نستخدم النص المباشر)
        if not ai_content or len(ai_content) < 20:
            ai_content = exact_text
            
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير سيناريوهات الفيدرالي: {e}\n{traceback.format_exc()}")
        return None

def generate_touch_and_go_report(data: dict) -> str | None:
    import traceback

    try:
        gold = data.get("gold", 0)
        atr = data.get("atr", 30)
        
        # مستويات اللمس السريع (Sniper Entries / Touch & Go)
        # أرقام قريبة نسبياً لالتقاط التذبذب اللحظي
        upper_trigger = round(gold + (atr * 0.35), 2)
        upper_target = round(upper_trigger + (atr * 0.45), 2)
        
        lower_trigger = round(gold - (atr * 0.35), 2)
        lower_target = round(lower_trigger - (atr * 0.45), 2)

        # النص بالهيكل الثابت المرفق من العميل
        exact_text = f"""بمجرد لمس {upper_trigger} يروح {upper_target}
بمجرد لمس {lower_trigger} يروح {lower_target}

السعر الحالي {gold}
لا نحتاج الي اغلاقات أو تأكيدات"""

        system_prompt = """أنت روبوت تنفيذي دقيق جداً.
العميل أرسل هيكلاً ثابتاً لصفقات اللمس السريع (Sniper / Limit)، ومهمتك الوحيدة هي إعادة كتابة النص الذي سأعطيه لك كما هو تماماً بالحرف الواحد، دون إضافة أي كلمة أخرى.
لا تكتب أي مقدمات أو اعتذارات أو استنتاجات.
"""

        user_prompt = f"""قم بإخراج هذا النص كما هو بالضبط دون أي إضافات:
{exact_text}
"""

        # نستخدم دالة الذكاء الاصطناعي مع قيود صارمة
        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=150)
        
        # لضمان عدم وجود أي إضافات من الـ AI
        if not ai_content or len(ai_content) < 10:
            ai_content = exact_text
            
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير اللمس السريع: {e}\n{traceback.format_exc()}")
        return None

def generate_best_zero_drawdown_trade_report(data: dict) -> str | None:
    import traceback

    try:
        gold = data.get("gold", 0)
        atr = data.get("atr", 30)
        vwap = data.get("vwap", gold)
        
        # الاعتماد على صفقات "أفضل نقطة" يعني انتظار السعر عند مستويات عميقة وآمنة
        # لتفادي أي انعكاس (Zero Drawdown)
        is_buy = gold >= vwap
        
        if is_buy:
            trade_type = "شراء (Buy Limit)"
            # الدخول من دعم عميق لتفادي الانعكاس
            entry = round(gold - (atr * 0.45), 2)
            stop_loss = round(entry - (atr * 0.15), 2)  # ستوب ضيق جداً
            target_1 = round(entry + (atr * 0.35), 2)
            target_2 = round(entry + (atr * 0.60), 2)
        else:
            trade_type = "بيع (Sell Limit)"
            # الدخول من مقاومة عميقة لتفادي الانعكاس
            entry = round(gold + (atr * 0.45), 2)
            stop_loss = round(entry + (atr * 0.15), 2)  # ستوب ضيق جداً
            target_1 = round(entry - (atr * 0.35), 2)
            target_2 = round(entry - (atr * 0.60), 2)

        context = f"""
- السعر الحالي: {gold}$
- نوع الصفقة الأفضل الآن: {trade_type}
- منطقة الدخول الدقيقة (Zero Drawdown): {entry}$
- وقف الخسارة (ضيق وآمن): {stop_loss}$
- الأهداف: {target_1}$ ثم {target_2}$
"""

        system_prompt = """أنت محلل أسواق مالية قناص، تبحث عن "الصفقة الأفضل" وليس الأقوى. 
الصفقة الأفضل تعني الدخول بأقل مخاطرة ممكنة، من مستويات دقيقة جداً لا تتوقع ارتداد السعر منها (زيرو انعكاس).
العميل يريد تقريراً يطرح "أفضل صفقة متاحة الآن".
قواعد صارمة:
1. استخدم الأرقام المرفقة حرفياً.
2. ركز بقوة على كلمة "الأفضل" وأن هذه المنطقة اختيرت لتفادي الانعكاس (Zero Drawdown).
3. لا تؤلف أي رقم من عندك.
4. لا تكتب إخلاء مسؤولية.
"""

        user_prompt = f"""قم بإنشاء "تقرير أفضل صفقة زيرو انعكاس" للذهب بناءً على الأرقام.
استخدم هذا الهيكل تماماً:
💎 أفضل صفقة متاحة الآن (Zero Drawdown) 🎯

▪️ السعر الحالي: [سعر]$
▪️ نوع الصفقة: [نوع الصفقة] من مستوى [رقم الدخول]$
▪️ وقف الخسارة الصارم: [الوقف]$
▪️ أهداف الصفقة الأفضل: [الهدف 1]$ / [الهدف 2]$

💡 لماذا هذه هي الصفقة الأفضل؟
[اكتب فقرة احترافية تركز بشدة على أن هذه النقطة هي "الأفضل" والمختارة بعناية فائقة لتوفير زيرو انعكاس ونسبة عائد لمخاطرة ممتازة بناءً على المعطيات].

البيانات:
{context}
"""

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=350)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير صفقة الزيرو انعكاس: {e}\n{traceback.format_exc()}")
        return None

def generate_best_high_lot_trade_report(data: dict) -> str | None:
    import traceback

    try:
        gold = data.get("gold", 0)
        atr = data.get("atr", 30)
        vwap = data.get("vwap", gold)
        
        # صفقة اللوت العالي تتطلب "أفضل وأقوى ارتداد مؤكد" وليس مجرد ترند قوي
        # لذا ننتظر السعر عند أقصى مقاومة/دعم متطرف (Extreme Levels) لهدف قريب وسريع
        is_buy = gold >= vwap
        
        if is_buy:
            trade_type = "شراء بلوت عالي (High Lot Buy Limit)"
            # دعم متطرف جداً لضمان رد فعل سعري (Bounce) سريع
            entry = round(gold - (atr * 0.55), 2)
            stop_loss = round(entry - (atr * 0.10), 2)  # ستوب ضيق للغاية ليتناسب مع اللوت العالي
            # أهداف اللوت العالي تكون قريبة جداً لأن الحركة البسيطة تعطي أرباحاً ضخمة
            target_1 = round(entry + (atr * 0.15), 2)
            target_2 = round(entry + (atr * 0.25), 2)
        else:
            trade_type = "بيع بلوت عالي (High Lot Sell Limit)"
            # مقاومة متطرفة جداً لضمان رد فعل سعري سريع
            entry = round(gold + (atr * 0.55), 2)
            stop_loss = round(entry + (atr * 0.10), 2)
            target_1 = round(entry - (atr * 0.15), 2)
            target_2 = round(entry - (atr * 0.25), 2)

        context = f"""
- السعر الحالي: {gold}$
- نوع الصفقة الأفضل للوت العالي: {trade_type}
- نقطة الاقتناص المتطرفة (Sniper Entry): {entry}$
- وقف الخسارة الصارم: {stop_loss}$
- أهداف الخطف السريع (Scalp): {target_1}$ ثم {target_2}$
"""

        system_prompt = """أنت محلل أسواق مالية قناص، متخصص في الصفقات ذات المخاطرة المحسوبة بـ "اللوت العالي (High Volume)".
تبحث عن "أفضل نقطة" تضمن "رد فعل سعري فوري وسريع (Immediate Bounce)" حتى لو لنقاط قليلة، لأن اللوت العالي لا يحتاج لنقاط كثيرة ليحقق ربحاً ضخماً، لكنه يحتاج لنقطة دخول صلبة جداً.
قواعد صارمة:
1. استخدم الأرقام المرفقة حرفياً.
2. ركز بقوة على كلمة "الأفضل" للمخاطرة بلوت عالي، وأن هذه المنطقة صلبة ومرشحة لرد فعل سريع والخروج بأرباح سريعة (خطف).
3. لا تؤلف أي رقم من عندك.
4. لا تكتب إخلاء مسؤولية.
"""

        user_prompt = f"""قم بإنشاء "تقرير أفضل صفقة لوت عالي (High Lot)" للذهب بناءً على الأرقام.
استخدم هذا الهيكل تماماً:
🔥 أفضل صفقة (لوت عالي / High Lot) 🎯

▪️ السعر الحالي: [سعر]$
▪️ نوع الصفقة: [نوع الصفقة] من المستوى الفولاذي [رقم الدخول]$
▪️ وقف الخسارة الصارم: [الوقف]$ (يجب الالتزام به تماماً)
▪️ أهداف الخطف السريع: [الهدف 1]$ / [الهدف 2]$

💡 لماذا هذه أفضل نقطة لمخاطرة اللوت العالي؟
[اكتب فقرة احترافية تركز على أن هذه النقطة هي "الأفضل والأصلب" لارتداد سريع للسعر، وأن الأهداف قريبة لأن حجم العقد (اللوت) الكبير لا يحتاج لمسافة طويلة بل لنقطة دخول لا تقبل الخطأ].

البيانات:
{context}
"""

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=350)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير صفقة اللوت العالي: {e}\n{traceback.format_exc()}")
        return None

def generate_fomc_gold_map_report(data: dict) -> str | None:
    import traceback

    try:
        gold = data.get("gold", 0)
        atr = data.get("atr", 30)
        
        # مستويات الفيدرالي تتطلب مسافات اختراق وكسر واضحة، وأهدافاً ممتدة جداً
        up_break = round(gold + (atr * 0.4), 2)
        up_t1 = round(gold + (atr * 0.8), 2)
        up_t2 = round(gold + (atr * 1.5), 2)
        up_t3 = round(gold + (atr * 2.2), 2)
        up_t4 = round(gold + (atr * 3.5), 2)
        
        down_break = round(gold - (atr * 0.4), 2)
        down_t1 = round(gold - (atr * 0.8), 2)
        down_t2 = round(gold - (atr * 1.5), 2)
        down_t3 = round(gold - (atr * 2.2), 2)
        down_t4 = round(gold - (atr * 3.5), 2)

        exact_text = f"""🚨 GOLD MAP | FOMC DAY 🟡📊

🧠 لا تتوقع... بل استعد لكل الاحتمالات.

📍 الخريطة توضح أهم مستويات الذهب

 اليوم: 🟢 السيناريو الصاعد في حالة اختراق {up_break} → {up_t1} → {up_t2} → {up_t3} → 
{up_t4} 🚀

🔴 السيناريو الهابط في حالة كسر {down_break} → 
{down_t1} → {down_t2} → {down_t3} → {down_t4} 📉

⚠️ ليلة الفيدرالي = تقلبات عنيفة جدًا. 🛡️

 التزم بإدارة رأس المال، ولا تدخل قبل تأكيد الاختراق أو الكسر.

👀 راقب المستويات... ودع السوق يؤكد الاتجاه. 🔥💰"""

        system_prompt = """أنت روبوت تنفيذي دقيق جداً.
العميل أرسل هيكلاً ثابتاً لخريطة الفيدرالي (FOMC Map)، ومهمتك الوحيدة هي إعادة كتابة النص الذي سأعطيه لك كما هو تماماً بالحرف الواحد، دون إضافة أي كلمة أخرى.
لا تكتب أي مقدمات أو اعتذارات أو استنتاجات.
"""

        user_prompt = f"""قم بإخراج هذا النص كما هو بالضبط دون أي إضافات:
{exact_text}
"""

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=300)
        
        if not ai_content or len(ai_content) < 20:
            ai_content = exact_text
            
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد خريطة الفيدرالي: {e}\n{traceback.format_exc()}")
        return None







