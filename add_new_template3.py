import re

with open('Goldbot/ai_generator_bot6.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_func = """
def generate_best_top_and_bottom_report(data: dict) -> str | None:
    import traceback
    try:
        gold = data.get("gold", 0)
        atr = data.get("atr", 30)
        
        # أفضل قمة (مستوى المقاومة الأقصى المتوقع لليوم)
        r3 = float(data.get("r3") or (gold + atr * 1.5))
        sw_h = float(data.get("swing_high") or r3)
        best_top = round(max(r3, sw_h), 2)
        
        # أفضل قاع (مستوى الدعم الأقصى المتوقع لليوم)
        s3 = float(data.get("s3") or (gold - atr * 1.5))
        sw_l = float(data.get("swing_low") or s3)
        best_bottom = round(min(s3, sw_l), 2)
        
        # حساب المسافة من السعر الحالي
        distance_to_top = round(best_top - gold, 2)
        distance_to_bottom = round(gold - best_bottom, 2)

        context = f\"\"\"
معلومات حية ودقيقة 100%:
- السعر الحالي: {gold}$
- القمة القصوى المتوقعة لليوم: {best_top}$ (تبعد {distance_to_top}$ عن السعر الحالي)
- القاع الأقصى المتوقع لليوم: {best_bottom}$ (يبعد {distance_to_bottom}$ عن السعر الحالي)
\"\"\"

        system_prompt = \"\"\"أنت محلل أسواق مالية محترف.
العميل يطلب تقريراً مباشراً يحدد "أفضل وأقوى قمة وقاع متوقعين للذهب اليوم" بناءً على البيانات الحية.
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً وبأعلى دقة.
2. اكتب فقرة تحليلية واحدة بأسلوب احترافي تشرح فيها أهمية هذين المستويين (القمة والقاع) وكيف يمكن استغلالهما للتمركز المعاكس (البيع من القمة المذكورة، والشراء من القاع المذكور لأنها تعتبر الحدود القصوى لليوم).
3. لا تكتب أي إخلاء مسؤولية.
\"\"\"

        user_prompt = f\"\"\"قم بإنشاء "تقرير أفضل قمة وقاع للذهب اليوم" بناءً على البيانات التالية.
استخدم هذا الهيكل تماماً:
🏔️ أفضل قمة وقاع متوقع لليوم (Daily Extremes) 📉📈

▪️ أفضل قمة لليوم (أقوى مقاومة للبيع): {best_top}$
   (مسافة الصعود المتبقية: {distance_to_top}$)
▪️ أفضل قاع لليوم (أقوى دعم للشراء): {best_bottom}$
   (مسافة الهبوط المتبقية: {distance_to_bottom}$)

💡 التفاصيل الفنية وطريقة الاستغلال:
[فقرة احترافية تشرح أهمية هذه المستويات كحدود قصوى لحركة اليوم (Extremes)، وكيف يمكن للمتداول الاستفادة منها كأهداف نهائية أو مناطق انعكاس آمنة جداً].

البيانات:
{context}
\"\"\"

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1000)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير أفضل قمة وقاع: {e}\\n{traceback.format_exc()}")
        return None

def generate_fomc_gold_map_report"""

content = content.replace("def generate_fomc_gold_map_report", new_func)

with open('Goldbot/ai_generator_bot6.py', 'w', encoding='utf-8') as f:
    f.write(content)


# Update bot_6.py
with open('Goldbot/bot_6.py', 'r', encoding='utf-8') as f:
    bot_content = f.read()

import_find = "generate_daily_best_direction_report"
import_replace = "generate_daily_best_direction_report, generate_best_top_and_bottom_report"
bot_content = bot_content.replace(import_find, import_replace)

append_code = """
            # توليد تقرير أفضل قمة وقاع لليوم (القالب العشرون)
            best_extremes = generate_best_top_and_bottom_report(data)
            if best_extremes:
                reports_to_send.append(("أفضل قمة وقاع اليوم 🏔️", best_extremes))
                
            # توليد خريطة الفيدرالي"""

bot_content = bot_content.replace("            # توليد خريطة الفيدرالي", append_code)

with open('Goldbot/bot_6.py', 'w', encoding='utf-8') as f:
    f.write(bot_content)
