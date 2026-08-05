import re

with open('Goldbot/ai_generator_bot6.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_func = """
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

        context = f\"\"\"
معلومات حية ودقيقة 100%:
- نوع الصفقة الأفضل (سوينج): {trade_dir}
- نقطة الدخول (مناطق قصوى آمنة): {entry}$
- وقف الخسارة (SL واسع وآمن): {sl}$
- الهدف السوينج الأول (TP1): {tp1}$
- الهدف السوينج الكبير (TP2): {tp2}$
- التوافق مع الاتجاه العام: {prob}%
- الأسباب الفنية لنجاح السوينج: {reasons}
\"\"\"

        system_prompt = \"\"\"أنت محلل أسواق مالية محترف، متخصص في صفقات المدى المتوسط والطويل (Swing Trades).
العميل يطلب تقريراً يقدم "أفضل صفقة سوينج" متوفرة للذهب تعتمد على مناطق الدخول القصوى (Extremes) لتحقيق أعلى عائد بأمان من التذبذب اليومي.
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً وبأعلى دقة، ولا تؤلف أي رقم.
2. اكتب فقرة تحليلية واحدة بأسلوب احترافي تشرح فيها لماذا هذه النقطة هي الأفضل للدخول في صفقة سوينج تظل مفتوحة لأيام، وكيف أن مساحة الوقف والأهداف تحميها من صانع السوق.
3. لا تكتب أي إخلاء مسؤولية.
\"\"\"

        user_prompt = f\"\"\"قم بإنشاء "تقرير أفضل صفقة سوينج" بناءً على البيانات التالية.
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
\"\"\"

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1000)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير السوينج: {e}\\n{traceback.format_exc()}")
        return None

def generate_fomc_gold_map_report"""

content = content.replace("def generate_fomc_gold_map_report", new_func)

with open('Goldbot/ai_generator_bot6.py', 'w', encoding='utf-8') as f:
    f.write(content)


# Update bot_6.py
with open('Goldbot/bot_6.py', 'r', encoding='utf-8') as f:
    bot_content = f.read()

import_find = "generate_best_scalping_trade_report"
import_replace = "generate_best_scalping_trade_report, generate_best_swing_trade_report"
bot_content = bot_content.replace(import_find, import_replace)

append_code = """
            # توليد تقرير أفضل صفقة سوينج (القالب الرابع والعشرون)
            best_swing = generate_best_swing_trade_report(data)
            if best_swing:
                reports_to_send.append(("أفضل صفقة سوينج 🦅", best_swing))
                
            # توليد خريطة الفيدرالي"""

bot_content = bot_content.replace("            # توليد خريطة الفيدرالي", append_code)

with open('Goldbot/bot_6.py', 'w', encoding='utf-8') as f:
    f.write(bot_content)
