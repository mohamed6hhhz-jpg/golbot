import logging
try:
    from Goldbot.ai_client import UniversalAIClient as Groq
except ImportError:
    from ai_client import UniversalAIClient as Groq
import time

log = logging.getLogger(__name__)
GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "llama3-8b-8192"
]

def generate_ai_template(api_key: str, template_num: int, title: str, context: dict, is_spot: bool) -> str:
    if not api_key: return "⚠️ Missing Groq API Key."
    client = Groq(api_key=api_key)
    
    market_type = "الفوري (Spot - XAU/USD)" if is_spot else "الآجل (Futures - GC=F)"
    
    # Custom instructions per template
    custom_instruction = ""
    if template_num == 3: # Zero reflection
        custom_instruction = "هذا التقرير مخصص لصفقات **الزيرو انعكاس**. اشرح لماذا هذه الصفقة (إن وجدت) دقيقة جداً. لا تذكر أي صفقة نسبة نجاحها أقل من 65%."
    elif template_num == 4: # Scalping
        custom_instruction = "هذا التقرير مخصص لـ **السكالبينج** (المضاربة السريعة على فريمات 5m-15m-30m). ركز على الأهداف القريبة."
    elif template_num == 5: # Swing
        custom_instruction = "هذا التقرير مخصص لـ **السوينج** (المدى الطويل، فريمات 4h-1d-1w). ركز على الاتجاه العام."
    elif template_num == 6: # High Lot
        custom_instruction = "هذا التقرير مخصص لصفقات **اللوت العالي**. ركز على الصفقات الآمنة جداً ذات الوقف الضيق."
    elif template_num == 10: # Bonds/Inflation
        custom_instruction = "تحدث عن عوائد السندات (10 سنوات و 30 سنة)، ومعدل التضخم، وسعر الفائدة، والعائد الحقيقي (الفائدة - التضخم). اشرح تأثير ذلك على الذهب."
    elif template_num == 11: # Currencies
        custom_instruction = "تحدث عن قوة العملات. استخرج أقوى 3 عملات وأضعف 3 عملات من البيانات، واشرح تأثيرها على مؤشر الدولار DXY والذهب XAU/USD."
    elif template_num == 12: # Summary
        custom_instruction = "هذه هي **الخلاصة النهائية**. يجب أن تبني نتيجتك على الـ 11 تقريراً السابقة. قم بإضافة 'نقطة الفصل المحورية اليومية' (Daily Pivot Point) واشرح بشكل صريح: فوقها صاعد، تحتها هابط."
    
    system_prompt = f"""أنت محلل كمي مؤسسي.
قواعد صارمة:
1. الجودة بنسبة 100%. لا تقبل أي صفقة أو مستوى نسبة نجاحه أقل من 65%.
2. التحليل مخصص فقط للسوق: {market_type}. 
3. لا تستخدم نطاقات واسعة (مثل 4290 إلى 4350) للبيع/الشراء، بل استخدم نقاط دقيقة بناءً على الدعم والمقاومة.
4. {custom_instruction}
"""

    prompt = f"قم بكتابة تقرير بعنوان '{title}' بناءً على البيانات التالية:\n{context}\n\nيجب أن يكون الرد منسقاً بشكل جذاب وواضح بصيغة الماركداون (Markdown) مع استخدام الإيموجي المناسب."
    
    try:
        from Goldbot.ai_client import generate_robust_ai_response
    except ImportError:
        from ai_client import generate_robust_ai_response
        
    ai_content = generate_robust_ai_response(system_prompt, prompt, max_tokens=1500)
    
    prefix = f"[{'الفوري' if is_spot else 'الآجل'}] قالب رقم {template_num}: {title}\n\n"
    if "فشل توليد التقرير" in ai_content:
        return prefix + "⚠️ فشل توليد التقرير."
    return prefix + ai_content
