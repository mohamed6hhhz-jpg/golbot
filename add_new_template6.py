import re

with open('Goldbot/ai_generator_bot6.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_func = """
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

        context = f\"\"\"
معلومات حية ودقيقة 100%:
- نوع الصفقة الأفضل للسكالبينج: {trade_dir}
- نقطة الدخول (الارتكاز اللحظي): {entry}$
- وقف الخسارة (SL): {sl}$
- الهدف السريع (TP1): {tp1}$
- الهدف الممتد (TP2): {tp2}$
- نسبة نجاح الصفقة السريعة: {prob}%
- الأسباب الفنية: {reasons}
\"\"\"

        system_prompt = \"\"\"أنت محلل أسواق مالية محترف، خبير في التداول السريع وخطف النقاط (Scalping).
العميل يطلب تقريراً يقدم "أفضل صفقة سكالبينج" متاحة الآن للذهب بناءً على الزخم اللحظي.
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً وبأعلى دقة، ولا تؤلف أي رقم.
2. اكتب فقرة تحليلية واحدة بأسلوب احترافي تشرح فيها قوة هذه الصفقة السريعة ولماذا الدخول والخروج السريع في هذه المستويات مثالي جداً الآن.
3. لا تكتب أي إخلاء مسؤولية.
\"\"\"

        user_prompt = f\"\"\"قم بإنشاء "تقرير أفضل صفقة سكالبينج" بناءً على البيانات التالية.
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
\"\"\"

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1000)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير السكالبينج: {e}\\n{traceback.format_exc()}")
        return None

def generate_fomc_gold_map_report"""

content = content.replace("def generate_fomc_gold_map_report", new_func)

with open('Goldbot/ai_generator_bot6.py', 'w', encoding='utf-8') as f:
    f.write(content)


# Update bot_6.py
with open('Goldbot/bot_6.py', 'r', encoding='utf-8') as f:
    bot_content = f.read()

import_find = "generate_best_closing_point_report"
import_replace = "generate_best_closing_point_report, generate_best_scalping_trade_report"
bot_content = bot_content.replace(import_find, import_replace)

append_code = """
            # توليد تقرير أفضل صفقة سكالبينج (القالب الثالث والعشرون)
            best_scalping = generate_best_scalping_trade_report(data)
            if best_scalping:
                reports_to_send.append(("أفضل صفقة سكالبينج ⚡", best_scalping))
                
            # توليد خريطة الفيدرالي"""

bot_content = bot_content.replace("            # توليد خريطة الفيدرالي", append_code)

with open('Goldbot/bot_6.py', 'w', encoding='utf-8') as f:
    f.write(bot_content)
