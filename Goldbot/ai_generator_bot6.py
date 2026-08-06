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
7. قم بإضافة نسبة مئوية تقديرية لاحتمالية الصعود والهبوط بناءً على أرقام البنوك، ونسبة أخرى بناءً على أرقام المؤسسات، ونسبة للحكم النهائي الكلي في نهاية التقرير.

- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
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
📈 احتمالية الاتجاه بناءً على البنوك: صعود [رقم]% | هبوط [رقم]%

🔵 Large Speculators (المؤسسات وصناديق الاستثمار):
شراء: [رقم] عقد
بيع: [رقم] عقد
صافي: [رقم] عقد
📈 احتمالية الاتجاه بناءً على المؤسسات: صعود [رقم]% | هبوط [رقم]%

🎯 التأثير المتوقع على الذهب:
[اشرح التأثير بوضوح واحترافية]

⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

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

- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
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


⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

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
    system_prompt = """أنت محلل فني. التزم حرفياً بالهيكل المقدم وضع الأرقام الحقيقية في أماكنها بناءً على البيانات. اكمل الفراغات بأسلوب احترافي يتناسب مع الهيكل.
- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
"""
    user_prompt = f"""الرجاء تعبئة هذا الهيكل:

📅 تحليل الذهب | {report_date}
الذهب XAUUSD يحافظ على [ميل إيجابي/سلبي] قصير الأجل بعد ارتداده من منطقة [أقرب دعم أو مقاومة تم الارتداد منها] تقريبًا، مع تحسن واضح في الحركة السعرية واستمرار الثبات [أعلى/أسفل] نطاق [منطقة الدعم أو المقاومة الحالية]، وهو ما يمنح السيناريو [الصاعد/الهابط] أفضلية تُقدّر بنحو [65% مثلا] لاستهداف [الهدف 1] ثم [الهدف 2]، بينما يؤدي اختراق المنطقة الأخيرة والثبات [أعلاها/أسفلها] إلى تعزيز فرص امتداد [الصعود/الهبوط] نحو [الهدف 3]

في المقابل، يبقى السيناريو البديل بنسبة [35% مثلا] قائمًا إذا فقد السعر [منطقة دعم/مقاومة بديلة]، ما قد يعيد الضغط [البيعي/الشرائي] فنيا ولذلك تظل منطقة [نطاق الفصل] هي نطاق الفصل الأهم بين استمرار التعافي وعودة الضعف فنيا

البيانات:
{context}

⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

"""
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

        system_prompt = """أنت كبير محللي السيولة وحركة الأسواق (Market Maker Analyst) في صندوق تحوط عالمي (مثل Bridgewater).
العميل يطلب "تقرير تحركات السوق والسيولة للذهب" لغرفة تداول احترافية.
قواعد صارمة جداً (إن خالفاتها سيتم رفض التقرير):
1. الدقة الفائقة المطلقة: الأرقام المقدمة لك (السعر الحالي، أعلى سعر، أدنى سعر) هي أسعار السوق الفعلية اللحظية. استخدمها بحذافيرها بالنقطة العشرية، ولا تقم بتقريبها أو اختراع أرقام من خيالك نهائياً!
2. الاحترافية العميقة: في قسم "💡 قراءة الحركة"، ممنوع كتابة كلام سطحي للمبتدئين (مثل "السوق متذبذب" أو "نترقب الأخبار"). يجب استخدام مصطلحات صناعة السوق الحقيقية (Liquidity Sweeps, Stop Hunts, Accumulation/Distribution, Order Flow, Imbalance).
3. التحليل الموقعي: اشرح بصرامة كيف تتصرف الأموال الذكية (Smart Money) الآن بناءً على موقع السعر الحالي مقارنة بأعلى وأدنى نقطة اليوم. أين تتمركز السيولة؟
4. كن قاطعاً ومباشراً ولا تستخدم لغة الاحتمالات الضعيفة.
5. التزم بالهيكل المطلوب حرفياً دون أي إضافات، ولا تضع أي تحذيرات قانونية.
"""

        user_prompt = f"""قم بإنشاء تقرير احترافي صارم لتحركات السوق والسيولة للذهب.
البيانات الحقيقية الفورية (التزم بها حرفياً):
{context}

الهيكل الإجباري للرد:
🌊 التقرير المباشر لتحركات السوق والسيولة

⏱️ الجلسة الحالية: {session_name} ({session_time})
📊 تقييم السيولة: تحركات {vol_level}

▪️ السعر الحالي: {gold}$
▪️ أعلى سعر: {daily_high}$
▪️ أدنى سعر: {daily_low}$
▪️ حجم النطاق الكلي اليوم: {daily_range}$
▪️ نسبة التغير: {'+' if gold_chg>=0 else ''}{gold_chg}$ ({'+' if gold_pct>=0 else ''}{gold_pct}%)

💡 قراءة الحركة (Smart Money Concept):
[اكتب فقرة تحليلية قوية وعميقة كأنك تتحدث في Bloomberg لمدير صندوق تحوط. اشرح بصرامة ماذا يفعل صناع السوق الآن بناءً على قرب السعر الحالي من القمة أو القاع المذكورين أعلاه. هل تم ضرب سيولة (Liquidity Sweep)؟ هل هناك تجميع (Accumulation) أو تصريف (Distribution)؟ أعطِ استنتاجاً دقيقاً وحقيقياً].

⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]
"""

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1000)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير السيولة: {e}\n{traceback.format_exc()}")
        return None


def _calc_prob_and_reasons(data: dict):
    hist = data.get('hist_ctx', {})
    gold_chg = round(hist.get('chg_1d', 0), 2) if hist else 0
    gold = data.get("gold", 0)
    vwap = data.get("vwap", gold)
    
    bullish_score = 50
    reasoning_up = []
    reasoning_down = []

    if gold_chg > 0:
        bullish_score += 10
        reasoning_up.append("تغير السعر الإيجابي")
    else:
        bullish_score -= 10
        reasoning_down.append("تغير السعر السلبي")

    if gold > vwap:
        bullish_score += 15
        reasoning_up.append("تمركز السعر فوق VWAP")
    else:
        bullish_score -= 15
        reasoning_down.append("تمركز السعر أسفل VWAP")

    rsi = data.get('rsi', 50)
    if rsi > 55:
        bullish_score += 10
        reasoning_up.append("زخم المشتريين قوي (RSI)")
    elif rsi < 45:
        bullish_score -= 10
        reasoning_down.append("زخم البائعين قوي (RSI)")

    macd = data.get('macd_hist', 0)
    if macd > 0:
        bullish_score += 5
        reasoning_up.append("MACD إيجابي")
    elif macd < 0:
        bullish_score -= 5
        reasoning_down.append("MACD سلبي")

    bullish_score = max(10, min(90, int(bullish_score)))
    bearish_score = 100 - bullish_score

    if not reasoning_up: reasoning_up.append("لا محفزات شرائية واضحة")
    if not reasoning_down: reasoning_down.append("لا محفزات بيعية واضحة")
    
    reason_up_str = " + ".join(reasoning_up[:3])
    reason_down_str = " + ".join(reasoning_down[:3])
    
    if bullish_score > bearish_score:
        stronger_path = "المسار الصاعد (BSL) هو الأقوى"
    elif bearish_score > bullish_score:
        stronger_path = "المسار الهابط (SSL) هو الأقوى"
    else:
        stronger_path = "توازن تام في السيولة"
        
    return bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path


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
        
        bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path = _calc_prob_and_reasons(data)

        context = f"""
معلومات حية ودقيقة 100%:
- اتجاه السيولة آلياً: {liq_dir}
- الإطار الزمني والصلاحية: {session_name} ({session_time})
- السعر الحالي: {gold}$
- قمة السيولة (BSL): {sw_h}$ والهدف الممتد: {upper_target}$ (احتمالية: {bullish_score}%)
- قاع السيولة (SSL): {sw_l}$ والهدف الممتد: {lower_target}$ (احتمالية: {bearish_score}%)
- المسار الأقوى: {stronger_path}
"""

        system_prompt = """أنت محلل أسواق مالية محترف. 
العميل يطلب تقريراً مباشراً وسريعاً يوضح "اتجاه السيولة اللحظية للذهب ومناطق سحب السيولة (Liquidity Pools)".
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً. لا تؤلف أي رقم.
2. اذكر اسم الجلسة الحالية ومواعيدها كما هي مرفقة.
3. اكتب فقرة تحليلية واحدة (تحت عنوان "💡 تحليل تدفق الأموال:") بأسلوب احترافي تشرح فيها كيف يقرأ العميل هذا الاتجاه، ولماذا يستهدف السعر المستويات المذكورة (لضرب الوقف أو سحب السيولة).
4. استخدم لغة سوقية قوية (مثلاً: امتصاص السيولة، سحب أو ضرب الوقف، تدفق السيولة).
5. لا تكتب أي إخلاء مسؤولية.

- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
"""

        user_prompt = f"""قم بإنشاء "تقرير اتجاه السيولة اللحظية ومناطق السحب للذهب" بناءً على البيانات التالية.
استخدم هذا الهيكل تماماً:
رادار السيولة اللحظي (Liquidity Flow) 💧🎯

🧭 اتجاه السيولة الحالي: [الاتجاه المرفق]
⏱️ فترة الصلاحية: فعالة خلال [اسم الجلسة] ([توقيت الجلسة])

🎯 أهداف السيولة ومناطق الجذب السعري (Liquidity Pools):
▪️ مسار السيولة الصاعد (BSL): السعر يستهدف اختراق القمة {sw_h}$ وصولاً إلى {upper_target}$ لامتصاص السيولة الشرائية.
   (الاحتمالية: {bullish_score}% — السبب: {reason_up_str})
▪️ مسار السيولة الهابط (SSL): السعر يستهدف كسر القاع {sw_l}$ وصولاً إلى {lower_target}$ لامتصاص السيولة البيعية.
   (الاحتمالية: {bearish_score}% — السبب: {reason_down_str})
   📌 المسار الأقوى حالياً: {stronger_path}

💡 تحليل تدفق الأموال:
[فقرة احترافية تشرح وضع السوق الحالي بوضوح بناءً على اتجاه السيولة والأهداف].

البيانات:
{context}


⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

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
        bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path = _calc_prob_and_reasons(data)
        rel_vol = data.get("rel_vol", 1.0)
        
        hist = data.get('hist_ctx', {})
        gold_chg = round(hist.get('chg_1d', 0), 2) if hist else 0
        
        bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path = _calc_prob_and_reasons(data)

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
- قمة السيولة (BSL): السعر يستهدف {round(gold + (atr * 0.8), 2)}$ (احتمالية: {bullish_score}%)
- قاع السيولة (SSL): السعر يستهدف {round(gold - (atr * 0.8), 2)}$ (احتمالية: {bearish_score}%)
- المسار الأقوى: {stronger_path}
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

- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
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


⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

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
        bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path = _calc_prob_and_reasons(data)
        
        # أهداف الجلسة الآسيوية غالباً ما تكون هادئة وتميل لتشكيل قمم وقيعان (نطاق عرضي)
        # لذا يتم الاعتماد على نسبة أقل من الـ ATR لتمثيل النطاق المستهدف
        asian_upper_target = round(gold + (atr * 0.35), 2)
        asian_lower_target = round(gold - (atr * 0.35), 2)

        time_validity = "من 02:00 صباحاً وحتى 10:00 صباحاً بتوقيت القاهرة"

        context = f"""
معلومات حية ودقيقة 100%:
- السعر الحالي: {gold}$
- هدف السيولة الصاعد للجلسة الآسيوية: {asian_upper_target}$ (احتمالية: {bullish_score}%)
- هدف السيولة الهابط للجلسة الآسيوية: {asian_lower_target}$ (احتمالية: {bearish_score}%)
- المسار الأقوى: {stronger_path}
- توقيت الجلسة: {time_validity}
"""

        system_prompt = """أنت محلل أسواق مالية محترف، متخصص في تحليل "السيولة وجلسات التداول (Session Liquidity)".
العميل يطلب تقريراً مباشراً يوضح أهداف سيولة "الجلسة الآسيوية (طوكيو)" فقط.
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً. لا تؤلف أي رقم.
2. اذكر أهداف السيولة ومواعيد الجلسة كما هي مرفقة.
3. اكتب فقرة تحليلية واحدة بأسلوب احترافي تشرح فيها طبيعة سيولة الجلسة الآسيوية (غالباً ما تكون هادئة وتبني نطاقاً عرضياً يتم اختراقه لاحقاً في جلسة لندن)، ولماذا السعر يستهدف المستويات المذكورة كنطاق (Range).
4. لا تكتب أي إخلاء مسؤولية.

- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
"""

        user_prompt = f"""قم بإنشاء "تقرير سيولة الجلسة الآسيوية للذهب" بناءً على البيانات التالية.
استخدم هذا الهيكل تماماً:
🏮 تقرير سيولة الجلسة الآسيوية (Asian Range) 🎯

⏱️ توقيت الجلسة: فعالة [توقيت الجلسة]

🎯 مستهدفات السيولة والنطاق السعري (Asian Box):
▪️ السعر الحالي: [سعر]$
▪️ هدف السيولة الشرائية (الحد العلوي): السعر يستهدف مستوى {asian_upper_target}$ كقمة متوقعة.
   (الاحتمالية: {bullish_score}% — السبب: {reason_up_str})
▪️ هدف السيولة البيعية (الحد السفلي): السعر يستهدف مستوى {asian_lower_target}$ كقاع متوقع.
   (الاحتمالية: {bearish_score}% — السبب: {reason_down_str})
   📌 الاتجاه المرجح لكسر النطاق: {stronger_path}

💡 تحليل الجلسة الآسيوية:
[فقرة احترافية تشرح وضع سيولة الجلسة الآسيوية وكيفية تشكيلها لنطاق سعري (Range) وتأثير ذلك بناءً على الأرقام المرفقة].

البيانات:
{context}


⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

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
        bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path = _calc_prob_and_reasons(data)
        
        # الجلسة الأوروبية (لندن) تتميز بالسيولة العالية وتحديد الاتجاه
        # لذا نستخدم نسبة أكبر من الـ ATR لتمثيل النطاق المستهدف الفعلي (اختراق النطاق الآسيوي)
        euro_upper_target = round(gold + (atr * 0.6), 2)
        euro_lower_target = round(gold - (atr * 0.6), 2)

        time_validity = "من 10:00 صباحاً وحتى 06:00 مساءً بتوقيت القاهرة"

        context = f"""
معلومات حية ودقيقة 100%:
- السعر الحالي: {gold}$
- هدف السيولة الصاعد للجلسة الأوروبية: {euro_upper_target}$ (احتمالية: {bullish_score}%)
- هدف السيولة الهابط للجلسة الأوروبية: {euro_lower_target}$ (احتمالية: {bearish_score}%)
- المسار الأقوى: {stronger_path}
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

- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
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


⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

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
        bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path = _calc_prob_and_reasons(data)
        
        # الجلسة الأمريكية (نيويورك) هي الأعنف وتتسم بالسيولة الضخمة جداً
        # لذا نستخدم نسبة أكبر من الـ ATR لتمثيل النطاق المستهدف الفعلي (اختراق نطاق لندن/آسيا)
        us_upper_target = round(gold + (atr * 0.7), 2)
        us_lower_target = round(gold - (atr * 0.7), 2)

        time_validity = "من 03:00 مساءً وحتى 11:00 مساءً بتوقيت القاهرة"

        context = f"""
معلومات حية ودقيقة 100%:
- السعر الحالي: {gold}$
- هدف السيولة الصاعد للجلسة الأمريكية: {us_upper_target}$ (احتمالية: {bullish_score}%)
- هدف السيولة الهابط للجلسة الأمريكية: {us_lower_target}$ (احتمالية: {bearish_score}%)
- المسار الأقوى: {stronger_path}
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

- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
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


⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

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
        bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path = _calc_prob_and_reasons(data)
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

- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
"""

        user_prompt = f"""قم بإخراج هذا النص كما هو بالضبط دون أي إضافات:
{exact_text}


⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

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
        bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path = _calc_prob_and_reasons(data)
        
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

- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
"""

        user_prompt = f"""قم بإخراج هذا النص كما هو بالضبط دون أي إضافات:
{exact_text}


⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

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
        bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path = _calc_prob_and_reasons(data)
        
        # مستويات اللمس السريع (Sniper Entries / Touch & Go)
        # أرقام قريبة نسبياً لالتقاط التذبذب اللحظي
        upper_trigger = round(gold + (atr * 0.35), 2)
        upper_target = round(upper_trigger + (atr * 0.45), 2)
        
        lower_trigger = round(gold - (atr * 0.35), 2)
        lower_target = round(lower_trigger - (atr * 0.45), 2)

        # النص بالهيكل الثابت المرفق من العميل مع تأكيد قاطع كما طلب
        exact_text = f"""بمجرد لمس {upper_trigger} يروح {upper_target}
بمجرد لمس {lower_trigger} يروح {lower_target}

السعر الحالي {gold}
لا نحتاج الي اغلاقات أو تأكيدات. 
⚠️ تأكيد قاطع: الأرقام تعمل بمجرد اللمس فقط (Touch & Go). طالما لمس الرقم سيصل للهدف فوراً وبشكل حتمي بقوة السيولة، ولا يحتاج لأي توقع أو إغلاق شمعة للتحقق."""

        system_prompt = """أنت روبوت تنفيذي دقيق جداً.
العميل أرسل هيكلاً ثابتاً لصفقات اللمس السريع (Sniper / Limit)، ومهمتك الوحيدة هي إعادة كتابة النص الذي سأعطيه لك كما هو تماماً بالحرف الواحد، دون إضافة أي كلمة أخرى.
لا تكتب أي مقدمات أو اعتذارات أو استنتاجات.

- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
"""

        user_prompt = f"""قم بإخراج هذا النص كما هو بالضبط دون أي إضافات:
{exact_text}


⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

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
        bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path = _calc_prob_and_reasons(data)
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

- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
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


⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

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
        bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path = _calc_prob_and_reasons(data)
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

- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
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


⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

"""

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=350)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير صفقة اللوت العالي: {e}\n{traceback.format_exc()}")
        return None


def generate_best_overall_trade_report(data: dict) -> str | None:
    import traceback
    try:
        gold = data.get("gold", 0)
        atr = data.get("atr", 30)
        vwap = data.get("vwap", gold)
        bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path = _calc_prob_and_reasons(data)
        
        # أفضل صفقة اليوم تعتمد على الاتجاه الأقوى مع نسبة عائد لمخاطرة (R:R) عالية جداً
        is_buy = bullish_score >= bearish_score
        
        if is_buy:
            trade_dir = "شراء (Buy Limit) 🟢"
            # الدخول من منطقة خصم قوية (Deep Discount) أسفل السعر الحالي أو عند VWAP
            entry = round(min(gold - (atr * 0.25), vwap), 2)
            # الوقف تحت الدعم القوي
            sl = round(entry - (atr * 0.35), 2)
            # أهداف قوية
            tp1 = round(entry + (atr * 0.40), 2)
            tp2 = round(entry + (atr * 0.80), 2)
            reasons = reason_up_str
            prob = bullish_score
        else:
            trade_dir = "بيع (Sell Limit) 🔴"
            # الدخول من منطقة قسط قوية (Deep Premium) أعلى السعر الحالي أو عند VWAP
            entry = round(max(gold + (atr * 0.25), vwap), 2)
            sl = round(entry + (atr * 0.35), 2)
            tp1 = round(entry - (atr * 0.40), 2)
            tp2 = round(entry - (atr * 0.80), 2)
            reasons = reason_down_str
            prob = bearish_score

        context = f"""
معلومات حية ودقيقة 100%:
- نوع الصفقة الأفضل: {trade_dir}
- نقطة الدخول الذهبية: {entry}$
- وقف الخسارة الصارم (SL): {sl}$
- الهدف الأول (TP1): {tp1}$
- الهدف الثاني (TP2): {tp2}$
- نسبة النجاح المتوقعة: {prob}%
- الأسباب الفنية: {reasons}
"""

        system_prompt = """أنت محلل أسواق مالية محترف، متخصص في قنص "أفضل صفقة تداول يومية (Trade of the Day)".
العميل يطلب تقريراً يقدم صفقة واحدة فقط تُعتبر "الخيار الأفضل والأكثر أماناً" لليوم بناءً على الزخم اللحظي ومناطق العرض/الطلب.
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً وبأعلى دقة، ولا تؤلف أي رقم.
2. اكتب فقرة تحليلية واحدة بأسلوب احترافي تشرح فيها لماذا تم اختيار هذه الصفقة كأفضل خيار لليوم، وما هو سر قوتها، مع ذكر نسبة النجاح المرفقة.
3. لا تكتب أي إخلاء مسؤولية.

- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
"""

        user_prompt = f"""قم بإنشاء "تقرير أفضل صفقة اليوم" للذهب بناءً على البيانات التالية.
استخدم هذا الهيكل تماماً:
👑 أفضل صفقة اليوم بشكل عام (Trade of the Day) 🎯

▪️ نوع الصفقة: {trade_dir}
▪️ نقطة الدخول (Entry): {entry}$ (نقطة ارتكاز قوية جداً)
▪️ وقف الخسارة (SL): {sl}$ (مستوى حماية صارم)
▪️ الهدف الأول (TP1): {tp1}$
▪️ الهدف الثاني (TP2): {tp2}$

💡 التحليل الفني لسر قوة الصفقة:
[فقرة احترافية تشرح قوة هذه الصفقة ولماذا هي الأفضل اليوم، مع الإشارة للأسباب المرفقة ونسبة النجاح {prob}%].

البيانات:
{context}


⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

"""

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1000)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير أفضل صفقة اليوم: {e}\n{traceback.format_exc()}")
        return None


def generate_daily_best_direction_report(data: dict) -> str | None:
    import traceback
    try:
        gold = data.get("gold", 0)
        vwap = data.get("vwap", gold)
        bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path = _calc_prob_and_reasons(data)
        
        # تحديد الاتجاه الأفضل لليوم
        is_bullish = bullish_score >= bearish_score
        
        if is_bullish:
            best_dir = "صاعد (Bullish) 📈"
            prob = bullish_score
            reasons = reason_up_str
            condition = f"طالما أن السعر مستقر أعلى مستوى {vwap}$ (الـ VWAP اللحظي)"
        else:
            best_dir = "هابط (Bearish) 📉"
            prob = bearish_score
            reasons = reason_down_str
            condition = f"طالما أن السعر مستقر أسفل مستوى {vwap}$ (الـ VWAP اللحظي)"

        context = f"""
معلومات حية ودقيقة 100%:
- أفضل اتجاه لليوم: {best_dir}
- احتمالية استمرار الاتجاه: {prob}%
- السعر الحالي: {gold}$
- شرط الحفاظ على الاتجاه: {condition}
- الأسباب الفنية: {reasons}
"""

        system_prompt = """أنت محلل أسواق مالية محترف.
العميل يطلب تقريراً مباشراً وحاسماً يحدد "أفضل اتجاه للذهب خلال اليوم" بناءً على البيانات الحية.
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً وبأعلى دقة.
2. اكتب فقرة تحليلية واحدة بأسلوب احترافي ومقنع تشرح فيها لماذا هذا الاتجاه هو الأقوى والأفضل اليوم، مع ذكر نسبة النجاح المرفقة والشرط الأساسي.
3. لا تكتب أي إخلاء مسؤولية.

- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
"""

        user_prompt = f"""قم بإنشاء "تقرير أفضل اتجاه للذهب اليوم" بناءً على البيانات التالية.
استخدم هذا الهيكل تماماً:
🧭 أفضل اتجاه للذهب خلال اليوم (Daily Bias) 📊

▪️ الاتجاه العام المُرجح: {best_dir}
▪️ نسبة قوة الاتجاه: {prob}%
▪️ نقطة الارتكاز المحورية (الشرط): {condition}

💡 التحليل الفني لاتجاه اليوم:
[فقرة احترافية وقوية تشرح لماذا هذا الاتجاه هو الأفضل فنياً اليوم، وكيف تدعم الأسباب المرفقة هذا القرار بقوة].

البيانات:
{context}


⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

"""

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1000)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير أفضل اتجاه اليوم: {e}\n{traceback.format_exc()}")
        return None


def generate_strongest_top_and_bottom_report(data: dict) -> str | None:
    import traceback
    try:
        gold = data.get("gold", 0)
        atr = data.get("atr", 30)
        
        # أقوى قمة (مستوى المقاومة الأقصى المتوقع لليوم)
        r3 = float(data.get("r3") or (gold + atr * 1.5))
        sw_h = float(data.get("swing_high") or r3)
        strongest_top = round(max(r3, sw_h), 2)
        
        # أقوى قاع (مستوى الدعم الأقصى المتوقع لليوم)
        s3 = float(data.get("s3") or (gold - atr * 1.5))
        sw_l = float(data.get("swing_low") or s3)
        strongest_bottom = round(min(s3, sw_l), 2)
        
        # حساب المسافة من السعر الحالي
        distance_to_top = round(strongest_top - gold, 2)
        distance_to_bottom = round(gold - strongest_bottom, 2)

        context = f"""
معلومات حية ودقيقة 100%:
- السعر الحالي: {gold}$
- القمة القصوى المتوقعة لليوم (أقوى قمة): {strongest_top}$ (تبعد {distance_to_top}$ عن السعر الحالي)
- القاع الأقصى المتوقع لليوم (أقوى قاع): {strongest_bottom}$ (يبعد {distance_to_bottom}$ عن السعر الحالي)
"""

        system_prompt = """أنت محلل أسواق مالية محترف.
العميل يطلب تقريراً مباشراً يحدد "أقوى قمة وقاع متوقعين للذهب اليوم" بناءً على البيانات الحية.
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً وبأعلى دقة.
2. اكتب فقرة تحليلية واحدة بأسلوب احترافي تشرح فيها أهمية هذين المستويين (القمة والقاع) وكيف يمكن استغلالهما للتمركز المعاكس (البيع من القمة المذكورة، والشراء من القاع المذكور لأنها تعتبر الحدود القصوى لليوم).
3. لا تكتب أي إخلاء مسؤولية.

- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
"""

        user_prompt = f"""قم بإنشاء "تقرير أقوى قمة وقاع للذهب اليوم" بناءً على البيانات التالية.
استخدم هذا الهيكل تماماً:
🏔️ أقوى قمة وقاع متوقع لليوم (Daily Extremes) 📉📈

▪️ أقوى قمة لليوم (أقوى مقاومة للبيع): {strongest_top}$
   (مسافة الصعود المتبقية: {distance_to_top}$)
▪️ أقوى قاع لليوم (أقوى دعم للشراء): {strongest_bottom}$
   (مسافة الهبوط المتبقية: {distance_to_bottom}$)

💡 التفاصيل الفنية وطريقة الاستغلال:
[فقرة احترافية تشرح أهمية هذه المستويات كحدود قصوى لحركة اليوم (Extremes)، وكيف يمكن للمتداول الاستفادة منها كأهداف نهائية أو مناطق انعكاس آمنة جداً].

البيانات:
{context}


⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

"""

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1000)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير أقوى قمة وقاع: {e}\n{traceback.format_exc()}")
        return None

def generate_best_top_and_bottom_report(data: dict) -> str | None:
    import traceback
    try:
        gold = data.get("gold", 0)
        atr = data.get("atr", 30)
        
        # أفضل قمة فعلية قابلة للتحقيق (غالباً R2 أو قمة قريبة من النطاق اليومي الفعلي)
        r2 = float(data.get("r2") or (gold + atr * 0.8))
        best_top = round(r2, 2)
        
        # أفضل قاع فعلي قابل للتحقيق (غالباً S2 أو قاع قريب من النطاق اليومي الفعلي)
        s2 = float(data.get("s2") or (gold - atr * 0.8))
        best_bottom = round(s2, 2)
        
        # حساب المسافة من السعر الحالي
        distance_to_top = round(best_top - gold, 2)
        distance_to_bottom = round(gold - best_bottom, 2)

        context = f"""
معلومات حية ودقيقة 100%:
- السعر الحالي: {gold}$
- أفضل قمة قابلة للتحقيق اليوم: {best_top}$ (تبعد {distance_to_top}$ عن السعر الحالي)
- أفضل قاع قابل للتحقيق اليوم: {best_bottom}$ (يبعد {distance_to_bottom}$ عن السعر الحالي)
"""

        system_prompt = """أنت محلل أسواق مالية محترف.
العميل يطلب تقريراً مباشراً يحدد "أفضل قمة وقاع (Optimal Levels) للذهب اليوم" بناءً على البيانات الحية. هذه هي المستويات الأكثر واقعية وقابلية للتحقيق (وليس الحدود القصوى المستبعدة).
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً وبأعلى دقة.
2. اكتب فقرة تحليلية احترافية تشرح لماذا تعتبر هذه المستويات هي الأفضل والأكثر واقعية اليوم لاصطياد الانعكاسات اليومية (Day Trading Reversals) بناءً على النطاق الطبيعي للسوق.
3. لا تكتب أي إخلاء مسؤولية.

- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
"""

        user_prompt = f"""قم بإنشاء "تقرير أفضل قمة وقاع للذهب اليوم" بناءً على البيانات التالية.
استخدم هذا الهيكل تماماً:
🎯 أفضل قمة وقاع لليوم (Optimal Daily Reversals) 📉📈

▪️ أفضل قمة لليوم (أفضل مقاومة للبيع): {best_top}$
   (مسافة الصعود المتبقية: {distance_to_top}$)
▪️ أفضل قاع لليوم (أفضل دعم للشراء): {best_bottom}$
   (مسافة الهبوط المتبقية: {distance_to_bottom}$)

💡 التفاصيل الفنية وطريقة الاستغلال:
[فقرة احترافية تشرح أهمية هذه المستويات كأفضل مناطق الانعكاس اليومية المرجحة بقوة، وكيفية التداول منها بأمان عالي نظراً لواقعيتها ضمن السيولة الحالية].

البيانات:
{context}


⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

"""

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1000)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير أفضل قمة وقاع: {e}\n{traceback.format_exc()}")
        return None


def generate_first_target_expected_report(data: dict) -> str | None:
    import traceback
    try:
        gold = data.get("gold", 0)
        atr = data.get("atr", 30)
        bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path = _calc_prob_and_reasons(data)
        
        # أفضل قمة وقاع
        r3 = float(data.get("r3") or (gold + atr * 1.5))
        sw_h = float(data.get("swing_high") or r3)
        best_top = round(max(r3, sw_h), 2)
        
        s3 = float(data.get("s3") or (gold - atr * 1.5))
        sw_l = float(data.get("swing_low") or s3)
        best_bottom = round(min(s3, sw_l), 2)
        
        distance_to_top = round(best_top - gold, 2)
        distance_to_bottom = round(gold - best_bottom, 2)

        # تحديد الهدف الأقرب والأرجح للضرب أولاً
        is_bullish = bullish_score >= bearish_score
        
        if is_bullish:
            first_target = f"القمة ({best_top}$)"
            second_target = f"القاع ({best_bottom}$)"
            prob = bullish_score
            reasons = reason_up_str
        else:
            first_target = f"القاع ({best_bottom}$)"
            second_target = f"القمة ({best_top}$)"
            prob = bearish_score
            reasons = reason_down_str

        context = f"""
معلومات حية ودقيقة 100%:
- السعر الحالي: {gold}$
- الهدف الأرجح للضرب أولاً: {first_target}
- الهدف المستبعد حالياً: {second_target}
- احتمالية ضرب الهدف الأول: {prob}%
- المسافة للقمة: {distance_to_top}$
- المسافة للقاع: {distance_to_bottom}$
- الأسباب الفنية: {reasons}
"""

        system_prompt = """أنت محلل أسواق مالية محترف.
العميل يطلب تقريراً حاسماً يحدد "أيهما سيُضرب أولاً: القمة أم القاع؟" بناءً على الزخم اللحظي وقوة الاتجاه.
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً وبأعلى دقة.
2. اكتب فقرة تحليلية واحدة بأسلوب احترافي وحاسم تشرح فيها سبب توجه السعر نحو الهدف المذكور أولاً، وتؤكد على الاحتمالية المرفقة.
3. لا تكتب أي إخلاء مسؤولية.

- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
"""

        user_prompt = f"""قم بإنشاء "تقرير الهدف الأرجح (القمة أم القاع)" بناءً على البيانات التالية.
استخدم هذا الهيكل تماماً:
🎯 مسار الأهداف المرجح (أيهما سيُضرب أولاً؟) ⏳

▪️ المستهدف الأول والأقرب للحدوث: {first_target}
▪️ احتمالية التحقق قبل الهدف المعاكس: {prob}%
▪️ المستهدف الثاني (مؤجل أو مستبعد حالياً): {second_target}

💡 التحليل الفني ومبررات الحركة:
[فقرة احترافية تشرح لماذا السيولة والزخم الحالي يدفعان السعر بقوة نحو هذا المستهدف أولاً، وتوضح تأثير الأسباب المرفقة في حسم هذا المسار].

البيانات:
{context}


⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

"""

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1000)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير الهدف الأول: {e}\n{traceback.format_exc()}")
        return None


def generate_best_closing_point_report(data: dict) -> str | None:
    import traceback
    try:
        gold = data.get("gold", 0)
        atr = data.get("atr", 30)
        vwap = data.get("vwap", gold)
        bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path = _calc_prob_and_reasons(data)
        
        is_bullish = bullish_score >= bearish_score
        
        if is_bullish:
            # من المتوقع أن يغلق السعر في منطقة إيجابية
            expected_close = round(max(gold, vwap) + (atr * 0.2), 2)
            bias_str = "إغلاق إيجابي (صاعد)"
            reasons = reason_up_str
        else:
            # من المتوقع أن يغلق السعر في منطقة سلبية
            expected_close = round(min(gold, vwap) - (atr * 0.2), 2)
            bias_str = "إغلاق سلبي (هابط)"
            reasons = reason_down_str
            
        # نطاق الإغلاق التقريبي (للدقة)
        close_upper = round(expected_close + (atr * 0.15), 2)
        close_lower = round(expected_close - (atr * 0.15), 2)

        context = f"""
معلومات حية ودقيقة 100%:
- السعر الحالي: {gold}$
- الإغلاق المتوقع: {bias_str}
- نقطة الإغلاق المرجحة: {expected_close}$
- نطاق الإغلاق اليومي (الأمان): بين {close_lower}$ و {close_upper}$
- الأسباب الفنية: {reasons}
"""

        system_prompt = """أنت محلل أسواق مالية محترف.
العميل يطلب تقريراً مباشراً يحدد "أفضل نقطة إغلاق يومية مرجحة" للذهب بناءً على البيانات الحية.
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً وبأعلى دقة.
2. اكتب فقرة تحليلية واحدة بأسلوب احترافي تشرح فيها سبب ترجيح منطقة الإغلاق هذه، وكيف أنها تعكس وضع السيولة ونهاية تداولات اليوم.
3. لا تكتب أي إخلاء مسؤولية.

- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
"""

        user_prompt = f"""قم بإنشاء "تقرير أفضل نقطة إغلاق متوقعة" بناءً على البيانات التالية.
استخدم هذا الهيكل تماماً:
🏁 أفضل نقطة إغلاق متوقعة لليوم (Daily Close Projection) 🕰️

▪️ طبيعة الإغلاق المرجح: {bias_str}
▪️ نقطة الإغلاق المرجحة للذهب: {expected_close}$
▪️ نطاق الإغلاق اليومي المتوقع: من {close_lower}$ إلى {close_upper}$

💡 التحليل الفني لتوقعات الإغلاق:
[فقرة احترافية تشرح أسباب استقرار السعر وإغلاقه في هذا النطاق بنهاية اليوم بناءً على الزخم اللحظي، وكيف تؤكد الأسباب المرفقة هذا الاستقرار].

البيانات:
{context}


⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

"""

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1000)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير نقطة الإغلاق: {e}\n{traceback.format_exc()}")
        return None


def generate_best_scalping_trade_report(data: dict) -> str | None:
    import traceback
    try:
        gold = data.get("gold", 0)
        atr = data.get("atr", 30)
        bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path = _calc_prob_and_reasons(data)
        
        is_buy = bullish_score >= bearish_score
        
        if is_buy:
            trade_dir = "شراء (Buy Scalp) 🟢"
            # دخول سريع بالقرب من السعر الحالي
            entry = round(gold - (atr * 0.05), 2)
            # وقف خسارة ضيق جداً (للسكالبينج)
            sl = round(entry - (atr * 0.20), 2)
            # هدف سريع وخطف نقاط
            tp1 = round(entry + (atr * 0.20), 2)
            tp2 = round(entry + (atr * 0.35), 2)
            reasons = reason_up_str
            prob = bullish_score
        else:
            trade_dir = "بيع (Sell Scalp) 🔴"
            entry = round(gold + (atr * 0.05), 2)
            sl = round(entry + (atr * 0.20), 2)
            tp1 = round(entry - (atr * 0.20), 2)
            tp2 = round(entry - (atr * 0.35), 2)
            reasons = reason_down_str
            prob = bearish_score

        context = f"""
معلومات حية ودقيقة 100%:
- نوع الصفقة الأفضل للسكالبينج: {trade_dir}
- نقطة الدخول (الارتكاز اللحظي): {entry}$
- وقف الخسارة (SL): {sl}$
- الهدف السريع (TP1): {tp1}$
- الهدف الممتد (TP2): {tp2}$
- نسبة نجاح الصفقة السريعة: {prob}%
- الأسباب الفنية: {reasons}
"""

        system_prompt = """أنت محلل أسواق مالية محترف، خبير في التداول السريع وخطف النقاط (Scalping).
العميل يطلب تقريراً يقدم "أفضل صفقة سكالبينج" متاحة الآن للذهب بناءً على الزخم اللحظي.
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً وبأعلى دقة، ولا تؤلف أي رقم.
2. اكتب فقرة تحليلية واحدة بأسلوب احترافي تشرح فيها قوة هذه الصفقة السريعة ولماذا الدخول والخروج السريع في هذه المستويات مثالي جداً الآن.
3. لا تكتب أي إخلاء مسؤولية.

- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
"""

        user_prompt = f"""قم بإنشاء "تقرير أفضل صفقة سكالبينج" بناءً على البيانات التالية.
استخدم هذا الهيكل تماماً:
⚡ أفضل صفقة سكالبينج لحظية (Scalping Trade) 🎯

▪️ نوع الصفقة: {trade_dir}
▪️ نقطة الدخول (Entry): {entry}$ (دخول سريع مع الزخم)
▪️ وقف الخسارة (SL): {sl}$ (حماية صارمة للرصيد)
▪️ الهدف السريع (TP1): {tp1}$
▪️ الهدف الإضافي (TP2): {tp2}$

💡 التحليل الفني وقوة الصفقة:
[فقرة احترافية تشرح سر قوة هذا السكالبينج الآن بناءً على الأسباب المرفقة ونسبة النجاح {prob}%، مع التأكيد على خطف النقاط السريع].

البيانات:
{context}


⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

"""

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1000)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير السكالبينج: {e}\n{traceback.format_exc()}")
        return None


def generate_best_swing_trade_report(data: dict) -> str | None:
    import traceback
    try:
        gold = data.get("gold", 0)
        atr = data.get("atr", 30)
        bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path = _calc_prob_and_reasons(data)
        
        is_buy = bullish_score >= bearish_score
        
        if is_buy:
            trade_dir = "شراء سوينج (Buy Limit) 🟢"
            # الدخول من دعم تاريخي عميق بعيد عن الضوضاء
            s3 = float(data.get("s3") or (gold - atr * 1.5))
            sw_l = float(data.get("swing_low") or s3)
            entry = round(min(s3, sw_l, gold - (atr * 1.0)), 2)
            
            # وقف خسارة واسع لحماية الصفقة من التذبذب
            sl = round(entry - (atr * 1.2), 2)
            
            # أهداف كبيرة جداً (أيام إلى أسابيع)
            tp1 = round(entry + (atr * 1.5), 2)
            tp2 = round(entry + (atr * 3.0), 2)
            reasons = reason_up_str
            prob = bullish_score
        else:
            trade_dir = "بيع سوينج (Sell Limit) 🔴"
            # الدخول من مقاومة تاريخية قصوى
            r3 = float(data.get("r3") or (gold + atr * 1.5))
            sw_h = float(data.get("swing_high") or r3)
            entry = round(max(r3, sw_h, gold + (atr * 1.0)), 2)
            
            sl = round(entry + (atr * 1.2), 2)
            
            tp1 = round(entry - (atr * 1.5), 2)
            tp2 = round(entry - (atr * 3.0), 2)
            reasons = reason_down_str
            prob = bearish_score

        context = f"""
معلومات حية ودقيقة 100%:
- نوع الصفقة الأفضل (سوينج): {trade_dir}
- نقطة الدخول (مناطق قصوى آمنة): {entry}$
- وقف الخسارة (SL واسع وآمن): {sl}$
- الهدف السوينج الأول (TP1): {tp1}$
- الهدف السوينج الكبير (TP2): {tp2}$
- التوافق مع الاتجاه العام: {prob}%
- الأسباب الفنية لنجاح السوينج: {reasons}
"""

        system_prompt = """أنت محلل أسواق مالية محترف، متخصص في صفقات المدى المتوسط والطويل (Swing Trades).
العميل يطلب تقريراً يقدم "أفضل صفقة سوينج" متوفرة للذهب تعتمد على مناطق الدخول القصوى (Extremes) لتحقيق أعلى عائد بأمان من التذبذب اليومي.
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً وبأعلى دقة، ولا تؤلف أي رقم.
2. اكتب فقرة تحليلية واحدة بأسلوب احترافي تشرح فيها لماذا هذه النقطة هي الأفضل للدخول في صفقة سوينج تظل مفتوحة لأيام، وكيف أن مساحة الوقف والأهداف تحميها من صانع السوق.
3. لا تكتب أي إخلاء مسؤولية.

- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
"""

        user_prompt = f"""قم بإنشاء "تقرير أفضل صفقة سوينج" بناءً على البيانات التالية.
استخدم هذا الهيكل تماماً:
🦅 أفضل صفقة سوينج (Swing Trade) 📈📉

▪️ نوع الصفقة: {trade_dir}
▪️ نقطة الدخول (Entry): {entry}$ (نقطة تمركز تاريخية)
▪️ وقف الخسارة (SL): {sl}$ (تأمين بعيد عن التذبذب العشوائي)
▪️ الهدف الأول (TP1): {tp1}$
▪️ الهدف الاستراتيجي (TP2): {tp2}$

💡 التحليل الفني لسر قوة السوينج:
[فقرة احترافية تشرح سر قوة وتمركز هذه الصفقة السوينج، ولماذا هذا المستوى بالتحديد يمثل أفضل نقطة لاصطياد حركة عنيفة وطويلة المدى بناءً على الأسباب المرفقة ونسبة التوافق {prob}%].

البيانات:
{context}


⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

"""

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1000)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير السوينج: {e}\n{traceback.format_exc()}")
        return None


def generate_next_15m_movement_report(data: dict) -> str | None:
    import traceback
    try:
        gold = data.get("gold", 0)
        atr = data.get("atr", 30)
        bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path = _calc_prob_and_reasons(data)
        
        is_bullish = bullish_score >= bearish_score
        
        # تحرك الربع ساعة يعتمد على مسافة قصيرة جداً (Micro-movement)
        micro_move = round(atr * 0.12, 2)
        
        if is_bullish:
            move_dir = "اندفاع صاعد (Bullish Push) 🚀"
            target_15m = round(gold + micro_move, 2)
            prob = bullish_score
            reasons = reason_up_str
        else:
            move_dir = "انزلاق هابط (Bearish Drop) 🩸"
            target_15m = round(gold - micro_move, 2)
            prob = bearish_score
            reasons = reason_down_str

        context = f"""
معلومات حية ودقيقة 100%:
- السعر الحالي: {gold}$
- التحرك الأفضل المتوقع (خلال 15 دقيقة القادمة): {move_dir}
- هدف التحرك اللحظي: {target_15m}$
- احتمالية حدوث التحرك: {prob}%
- الأسباب الفنية: {reasons}
"""

        system_prompt = """أنت محلل أسواق مالية محترف، متخصص في قراءة الزخم اللحظي وتوقع الحركات الدقيقة جداً (Micro-movements).
العميل يطلب تقريراً مباشراً وحاسماً يحدد "أفضل وأرجح تحرك للذهب خلال الـ 15 دقيقة القادمة" بناءً على السيولة اللحظية.
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً وبأعلى دقة.
2. اكتب فقرة تحليلية واحدة بأسلوب احترافي ومثير تشرح فيها قوة هذا التحرك القصير جداً ولماذا سيحدث فوراً.
3. لا تكتب أي إخلاء مسؤولية.

- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
"""

        user_prompt = f"""قم بإنشاء "تقرير توقع الربع ساعة القادمة" بناءً على البيانات التالية.
استخدم هذا الهيكل تماماً:
⏱️ توقعات الحركة اللحظية (الـ 15 دقيقة القادمة) 🔍

▪️ السعر الحالي للذهب: {gold}$
▪️ الاتجاه الأرجح للربع ساعة القادمة: {move_dir}
▪️ نقطة الاستهداف اللحظية السريعة: {target_15m}$
▪️ احتمالية التحقق السريع: {prob}%

💡 نبض السوق اللحظي:
[فقرة احترافية تشرح حالة السيولة الحالية، وكيف تدفع الأسباب المرفقة السعر بقوة وسرعة نحو هذا الهدف خلال الـ 15 دقيقة القادمة].

البيانات:
{context}


⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

"""

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1000)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير الـ 15 دقيقة: {e}\n{traceback.format_exc()}")
        return None

def generate_fomc_gold_map_report(data: dict) -> str | None:
    import traceback

    try:
        gold = data.get("gold", 0)
        atr = data.get("atr", 30)
        bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path = _calc_prob_and_reasons(data)
        
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

- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
"""

        user_prompt = f"""قم بإخراج هذا النص كما هو بالضبط دون أي إضافات:
{exact_text}


⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

"""

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=300)
        
        if not ai_content or len(ai_content) < 20:
            ai_content = exact_text
            
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد خريطة الفيدرالي: {e}\n{traceback.format_exc()}")
        return None









def generate_liquidity_target_timing_report(data: dict) -> str | None:
    import traceback
    try:
        gold = data.get('gold', 0)
        atr = data.get('atr', 0)
        hist = data.get('hist_ctx', {})
        chg_1d = hist.get('chg_1d', 0) if hist else 0
        
        # أهداف السيولة الأقرب (استخدام R1, S1 للسيولة القريبة و R2, S2 للأهداف الأبعد)
        r1 = data.get('r1', 0)
        s1 = data.get('s1', 0)
        
        if not (gold and atr and r1 and s1):
            log.warning("⚠️ بيانات غير مكتملة لتوليد تقرير الوجهة القادمة للسيولة.")
            return None
            
        # تقدير الاتجاه اللحظي بناءً على التغير أو موقع السعر مقارنة بالبيفوت
        pivot = data.get('pivot', 0)
        if gold > pivot or chg_1d > 0:
            target_direction = "صاعد (Bullish)"
            target_price = r1
            distance = target_price - gold
        else:
            target_direction = "هابط (Bearish)"
            target_price = s1
            distance = gold - target_price
            
        # تقدير الوقت بناءً على ATR الساعي أو اليومي (إذا افترضنا أن ATR هو تذبذب يومي، فنقسمه على 24 للحصول على السرعة التقريبية)
        # سرعة السعر بالساعة تقريباً = atr / 12 (بافتراض أوقات الذروة)
        speed_per_hour = atr / 12.0 if atr else 1.0
        hours_estimated = distance / speed_per_hour if speed_per_hour > 0 else 0
        
        if hours_estimated < 1:
            time_frame = "خلال أقل من ساعة"
        elif hours_estimated < 4:
            time_frame = "خلال 1 إلى 4 ساعات"
        elif hours_estimated < 12:
            time_frame = "خلال 4 إلى 12 ساعة (بنهاية جلسة اليوم)"
        else:
            time_frame = "خلال 12 إلى 24 ساعة (جلسة الغد)"
            
        context = f"""
معلومات حية ودقيقة 100%:
- السعر الفوري للذهب الآن: {gold}$
- اتجاه السيولة اللحظي الأرجح: {target_direction}
- المستهدف الرقمي للسيولة (أقرب تجمع سيولة): {target_price}$
- متوسط حركة السوق الحالي (ATR): {atr} دولار
- الإطار الزمني المقدر رياضياً للوصول: {time_frame}
"""

        system_prompt = """أنت محلل أسواق مالية متقدم جداً، متخصص في تحليل السيولة (Liquidity Concepts) وحسابات الوقت والسرعة.
قواعد صارمة:
1. استخدم الأرقام المرفقة بدقة شديدة ولا تخترع أي أرقام.
2. اشرح باحترافية وسهولة كيف وأين تتجه السيولة الان، ولماذا هذا الهدف هو المنطقي.
3. قدم شرحاً واضحاً للزمن المتوقع للوصول ولماذا (اربطه بسرعة السوق الحالية).
4. اكتب بأسلوب جذاب ومقسم بشكل مريح للعين، بدون إخلاء مسؤولية.

- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
"""

        user_prompt = f"""قم بإنشاء "تقرير الوجهة القادمة للسيولة والزمن المتوقع" بناءً على البيانات التالية.
استخدم هذا الهيكل تماماً:
🎯 الوجهة القادمة للسيولة والزمن المتوقع ⏳

▪️ اتجاه السيولة الحالي: [اشرح الاتجاه]
▪️ المستهدف السعري (Target): {target_price}$ (شرح سبب استهداف هذا الرقم)
▪️ الإطار الزمني للوصول: {time_frame} (كيف تم تقديره بناءً على سرعة السوق)

💡 التحليل الفني والسيولة:
[شرح متقدم وموجز لحركة السيولة من الآن وحتى الوصول للهدف]

⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

البيانات الحقيقية:
{context}
"""
        
        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=800)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير الوجهة القادمة للسيولة: {e}\n{traceback.format_exc()}")
        return None
