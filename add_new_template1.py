import re

with open('Goldbot/ai_generator_bot6.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_func = """
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

        context = f\"\"\"
معلومات حية ودقيقة 100%:
- نوع الصفقة الأفضل: {trade_dir}
- نقطة الدخول الذهبية: {entry}$
- وقف الخسارة الصارم (SL): {sl}$
- الهدف الأول (TP1): {tp1}$
- الهدف الثاني (TP2): {tp2}$
- نسبة النجاح المتوقعة: {prob}%
- الأسباب الفنية: {reasons}
\"\"\"

        system_prompt = \"\"\"أنت محلل أسواق مالية محترف، متخصص في قنص "أفضل صفقة تداول يومية (Trade of the Day)".
العميل يطلب تقريراً يقدم صفقة واحدة فقط تُعتبر "الخيار الأفضل والأكثر أماناً" لليوم بناءً على الزخم اللحظي ومناطق العرض/الطلب.
قواعد صارمة:
1. استخدم الأرقام المرفقة في البيانات حرفياً وبأعلى دقة، ولا تؤلف أي رقم.
2. اكتب فقرة تحليلية واحدة بأسلوب احترافي تشرح فيها لماذا تم اختيار هذه الصفقة كأفضل خيار لليوم، وما هو سر قوتها، مع ذكر نسبة النجاح المرفقة.
3. لا تكتب أي إخلاء مسؤولية.
\"\"\"

        user_prompt = f\"\"\"قم بإنشاء "تقرير أفضل صفقة اليوم" للذهب بناءً على البيانات التالية.
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
\"\"\"

        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=1000)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير أفضل صفقة اليوم: {e}\\n{traceback.format_exc()}")
        return None

def generate_fomc_gold_map_report"""

content = content.replace("def generate_fomc_gold_map_report", new_func)

with open('Goldbot/ai_generator_bot6.py', 'w', encoding='utf-8') as f:
    f.write(content)
