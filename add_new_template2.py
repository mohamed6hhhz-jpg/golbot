import re

with open('Goldbot/ai_generator_bot6.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_func = """
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

        context = f\"\"\"
معلومات حية ودقيقة 100%:
- أفضل اتجاه لليوم: {best_dir}
- احتمالية استمرار الاتجاه: {prob}%
- السعر الحالي: {gold}$
- شرط الحفاظ على الاتجاه: {condition}
- الأسباب الفنية: {reasons}
\"\"\"

        system_prompt = \"\"\"أنت محلل أسواق مالية محترف.
العميل يطلب تقريراً مباشراً وحاسماً يحدد "أفضل اتجاه للذهب خلال اليوم" بناءً على البيانات الحية.
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً وبأعلى دقة.
2. اكتب فقرة تحليلية واحدة بأسلوب احترافي ومقنع تشرح فيها لماذا هذا الاتجاه هو الأقوى والأفضل اليوم، مع ذكر نسبة النجاح المرفقة والشرط الأساسي.
3. لا تكتب أي إخلاء مسؤولية.
\"\"\"

        user_prompt = f\"\"\"قم بإنشاء "تقرير أفضل اتجاه للذهب اليوم" بناءً على البيانات التالية.
استخدم هذا الهيكل تماماً:
🧭 أفضل اتجاه للذهب خلال اليوم (Daily Bias) 📊

▪️ الاتجاه العام المُرجح: {best_dir}
▪️ نسبة قوة الاتجاه: {prob}%
▪️ نقطة الارتكاز المحورية (الشرط): {condition}

💡 التحليل الفني لاتجاه اليوم:
[فقرة احترافية وقوية تشرح لماذا هذا الاتجاه هو الأفضل فنياً اليوم، وكيف تدعم الأسباب المرفقة هذا القرار بقوة].

البيانات:
{context}
\"\"\"

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1000)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير أفضل اتجاه اليوم: {e}\\n{traceback.format_exc()}")
        return None

def generate_fomc_gold_map_report"""

content = content.replace("def generate_fomc_gold_map_report", new_func)

with open('Goldbot/ai_generator_bot6.py', 'w', encoding='utf-8') as f:
    f.write(content)
