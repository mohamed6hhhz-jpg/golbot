import re

with open('Goldbot/ai_generator_bot6.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_func = """
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

        context = f\"\"\"
معلومات حية ودقيقة 100%:
- السعر الحالي: {gold}$
- الهدف الأرجح للضرب أولاً: {first_target}
- الهدف المستبعد حالياً: {second_target}
- احتمالية ضرب الهدف الأول: {prob}%
- المسافة للقمة: {distance_to_top}$
- المسافة للقاع: {distance_to_bottom}$
- الأسباب الفنية: {reasons}
\"\"\"

        system_prompt = \"\"\"أنت محلل أسواق مالية محترف.
العميل يطلب تقريراً حاسماً يحدد "أيهما سيُضرب أولاً: القمة أم القاع؟" بناءً على الزخم اللحظي وقوة الاتجاه.
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً وبأعلى دقة.
2. اكتب فقرة تحليلية واحدة بأسلوب احترافي وحاسم تشرح فيها سبب توجه السعر نحو الهدف المذكور أولاً، وتؤكد على الاحتمالية المرفقة.
3. لا تكتب أي إخلاء مسؤولية.
\"\"\"

        user_prompt = f\"\"\"قم بإنشاء "تقرير الهدف الأرجح (القمة أم القاع)" بناءً على البيانات التالية.
استخدم هذا الهيكل تماماً:
🎯 مسار الأهداف المرجح (أيهما سيُضرب أولاً؟) ⏳

▪️ المستهدف الأول والأقرب للحدوث: {first_target}
▪️ احتمالية التحقق قبل الهدف المعاكس: {prob}%
▪️ المستهدف الثاني (مؤجل أو مستبعد حالياً): {second_target}

💡 التحليل الفني ومبررات الحركة:
[فقرة احترافية تشرح لماذا السيولة والزخم الحالي يدفعان السعر بقوة نحو هذا المستهدف أولاً، وتوضح تأثير الأسباب المرفقة في حسم هذا المسار].

البيانات:
{context}
\"\"\"

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1000)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير الهدف الأول: {e}\\n{traceback.format_exc()}")
        return None

def generate_fomc_gold_map_report"""

content = content.replace("def generate_fomc_gold_map_report", new_func)

with open('Goldbot/ai_generator_bot6.py', 'w', encoding='utf-8') as f:
    f.write(content)


# Update bot_6.py
with open('Goldbot/bot_6.py', 'r', encoding='utf-8') as f:
    bot_content = f.read()

import_find = "generate_best_top_and_bottom_report"
import_replace = "generate_best_top_and_bottom_report, generate_first_target_expected_report"
bot_content = bot_content.replace(import_find, import_replace)

append_code = """
            # توليد تقرير الهدف الأول المتوقع (القالب الحادي والعشرون)
            first_target_report = generate_first_target_expected_report(data)
            if first_target_report:
                reports_to_send.append(("مسار الأهداف المرجح 🎯", first_target_report))
                
            # توليد خريطة الفيدرالي"""

bot_content = bot_content.replace("            # توليد خريطة الفيدرالي", append_code)

with open('Goldbot/bot_6.py', 'w', encoding='utf-8') as f:
    f.write(bot_content)
