import re

with open('Goldbot/ai_generator_bot6.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_func = """
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

        context = f\"\"\"
معلومات حية ودقيقة 100%:
- السعر الحالي: {gold}$
- التحرك الأفضل المتوقع (خلال 15 دقيقة القادمة): {move_dir}
- هدف التحرك اللحظي: {target_15m}$
- احتمالية حدوث التحرك: {prob}%
- الأسباب الفنية: {reasons}
\"\"\"

        system_prompt = \"\"\"أنت محلل أسواق مالية محترف، متخصص في قراءة الزخم اللحظي وتوقع الحركات الدقيقة جداً (Micro-movements).
العميل يطلب تقريراً مباشراً وحاسماً يحدد "أفضل وأرجح تحرك للذهب خلال الـ 15 دقيقة القادمة" بناءً على السيولة اللحظية.
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً وبأعلى دقة.
2. اكتب فقرة تحليلية واحدة بأسلوب احترافي ومثير تشرح فيها قوة هذا التحرك القصير جداً ولماذا سيحدث فوراً.
3. لا تكتب أي إخلاء مسؤولية.
\"\"\"

        user_prompt = f\"\"\"قم بإنشاء "تقرير توقع الربع ساعة القادمة" بناءً على البيانات التالية.
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
\"\"\"

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1000)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير الـ 15 دقيقة: {e}\\n{traceback.format_exc()}")
        return None

def generate_fomc_gold_map_report"""

content = content.replace("def generate_fomc_gold_map_report", new_func)

with open('Goldbot/ai_generator_bot6.py', 'w', encoding='utf-8') as f:
    f.write(content)


# Update bot_6.py
with open('Goldbot/bot_6.py', 'r', encoding='utf-8') as f:
    bot_content = f.read()

import_find = "generate_best_swing_trade_report"
import_replace = "generate_best_swing_trade_report, generate_next_15m_movement_report"
bot_content = bot_content.replace(import_find, import_replace)

append_code = """
            # توليد تقرير حركة الربع ساعة (القالب الخامس والعشرون)
            next_15m = generate_next_15m_movement_report(data)
            if next_15m:
                reports_to_send.append(("الحركة اللحظية المتوقعة ⏱️", next_15m))
                
            # توليد خريطة الفيدرالي"""

bot_content = bot_content.replace("            # توليد خريطة الفيدرالي", append_code)

with open('Goldbot/bot_6.py', 'w', encoding='utf-8') as f:
    f.write(bot_content)
