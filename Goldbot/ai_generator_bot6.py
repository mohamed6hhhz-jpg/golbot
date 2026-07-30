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
    
    # تحضير الأرقام الحقيقية
    gold = data.get('gold', 0)
    dxy_pct = data.get('dxy_pct', 0)
    
    supply1 = data.get('sd_supply') or data.get('r1', 0)
    supply2 = data.get('r2', 0)
    demand1 = data.get('sd_demand') or data.get('s1', 0)
    demand2 = data.get('s2', 0)
    
    dxy_status = "قوة" if dxy_pct > 0 else "ضعف"

    context = f"""
بيانات حية للسوق:
- سعر الذهب الحالي: {gold}$
- مؤشر الدولار (DXY): يشهد {dxy_status} بنسبة {dxy_pct}%
- منطقة العرض الأولى: {supply1}$
- منطقة العرض الثانية: {supply2}$
- منطقة الطلب الأولى: {demand1}$
- منطقة الطلب الثانية: {demand2}$
"""

    system_prompt = """أنت محلل فني خبير في حركة السعر (Price Action) ومناطق العرض والطلب.
قواعد صارمة:
1. التزم بالهيكل الذي يقدمه المستخدم حرفياً.
2. قم بتعبئة الأرقام والبيانات في الأماكن المناسبة.
3. أكمل الجمل الناقصة (مثل السيناريو البديل) بناءً على التحليل المنطقي للسوق.
4. استخدم الأرقام الحقيقية فقط المقدمة لك.
"""

    user_prompt = f"""الرجاء إكمال وتعبئة الهيكل التالي بناءً على البيانات الحية. أكمل السيناريو البديل بشكل احترافي، واملأ مناطق العرض والطلب، واضبط اتجاه السعر بناءً على البيانات:

📅 تحليل الذهب | {report_date}
شهد الذهب اليوم [صف الحالة بناءً على السعر الحالي وقوة الدولار]، بالتزامن مع [حالة الدولار]، وهو ما [تأثير ذلك].
🔹 مناطق العرض: [منطقة 1] ثم [منطقة 2]
🔹 مناطق الطلب: [منطقة 1] ثم [منطقة 2]
السيناريوهات المحتملة:
📉 السيناريو الأقوى:
طالما الذهب يتداول [أكمل بناءً على الأرقام الحالية]، فاحتمال [أكمل السيناريو].
📈 السيناريو البديل:
إذا نجح السعر في اختراق [أكمل السيناريو البديل للاتجاه الآخر].

البيانات الحقيقية:
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

الرجاء ادارة مخاطر راس المال💵
انتبه لفرق السعر يختلف في بعض الشركات  📈"""
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

الرجاء ادارة مخاطر راس المال💵
انتبه لفرق السعر يختلف في بعض الشركات 📈"""
    return report
