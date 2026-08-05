import re

with open('Goldbot/ai_generator_bot6.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_func = """
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

        context = f\"\"\"
معلومات حية ودقيقة 100%:
- السعر الحالي: {gold}$
- الإغلاق المتوقع: {bias_str}
- نقطة الإغلاق المرجحة: {expected_close}$
- نطاق الإغلاق اليومي (الأمان): بين {close_lower}$ و {close_upper}$
- الأسباب الفنية: {reasons}
\"\"\"

        system_prompt = \"\"\"أنت محلل أسواق مالية محترف.
العميل يطلب تقريراً مباشراً يحدد "أفضل نقطة إغلاق يومية مرجحة" للذهب بناءً على البيانات الحية.
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً وبأعلى دقة.
2. اكتب فقرة تحليلية واحدة بأسلوب احترافي تشرح فيها سبب ترجيح منطقة الإغلاق هذه، وكيف أنها تعكس وضع السيولة ونهاية تداولات اليوم.
3. لا تكتب أي إخلاء مسؤولية.
\"\"\"

        user_prompt = f\"\"\"قم بإنشاء "تقرير أفضل نقطة إغلاق متوقعة" بناءً على البيانات التالية.
استخدم هذا الهيكل تماماً:
🏁 أفضل نقطة إغلاق متوقعة لليوم (Daily Close Projection) 🕰️

▪️ طبيعة الإغلاق المرجح: {bias_str}
▪️ نقطة الإغلاق المرجحة للذهب: {expected_close}$
▪️ نطاق الإغلاق اليومي المتوقع: من {close_lower}$ إلى {close_upper}$

💡 التحليل الفني لتوقعات الإغلاق:
[فقرة احترافية تشرح أسباب استقرار السعر وإغلاقه في هذا النطاق بنهاية اليوم بناءً على الزخم اللحظي، وكيف تؤكد الأسباب المرفقة هذا الاستقرار].

البيانات:
{context}
\"\"\"

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1000)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير نقطة الإغلاق: {e}\\n{traceback.format_exc()}")
        return None

def generate_fomc_gold_map_report"""

content = content.replace("def generate_fomc_gold_map_report", new_func)

with open('Goldbot/ai_generator_bot6.py', 'w', encoding='utf-8') as f:
    f.write(content)


# Update bot_6.py
with open('Goldbot/bot_6.py', 'r', encoding='utf-8') as f:
    bot_content = f.read()

import_find = "generate_first_target_expected_report"
import_replace = "generate_first_target_expected_report, generate_best_closing_point_report"
bot_content = bot_content.replace(import_find, import_replace)

append_code = """
            # توليد تقرير نقطة الإغلاق المتوقعة (القالب الثاني والعشرون)
            closing_point_report = generate_best_closing_point_report(data)
            if closing_point_report:
                reports_to_send.append(("نقطة الإغلاق المرجحة لليوم 🏁", closing_point_report))
                
            # توليد خريطة الفيدرالي"""

bot_content = bot_content.replace("            # توليد خريطة الفيدرالي", append_code)

with open('Goldbot/bot_6.py', 'w', encoding='utf-8') as f:
    f.write(bot_content)
