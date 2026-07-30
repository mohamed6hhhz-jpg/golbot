with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

s15_func = """
def _build_spot_s15(data: dict) -> str:
    \"\"\"القالب الجديد: الحجم والسيولة والزخم وهل الاختراق حقيقي أم وهمي\"\"\"
    current = data.get('gold', 0.0)
    vol = data.get('rel_vol', 1.0)
    rsi = data.get('rsi', 50.0)
    macd_hist = data.get('macd_hist', 0.0)
    
    if vol > 1.5:
        vol_state = "🔵 سيولة مؤسساتية ضخمة (حجم تداول مرتفع جداً)"
        vol_score = "ممتاز ✅"
    elif vol > 1.0:
        vol_state = "🟢 سيولة نشطة (حجم تداول فوق المتوسط)"
        vol_score = "جيد ☑️"
    elif vol > 0.7:
        vol_state = "🟡 سيولة طبيعية (حجم تداول متوسط)"
        vol_score = "مقبول ➖"
    else:
        vol_state = "🔴 سيولة ضعيفة/جفاف (حجم تداول منخفض)"
        vol_score = "ضعيف ❌"

    if rsi >= 65 and macd_hist > 0:
        mom_state = "🚀 زخم شرائي انفجاري"
    elif rsi <= 35 and macd_hist < 0:
        mom_state = "🩸 زخم بيعي عنيف"
    elif rsi > 50:
        mom_state = "📈 زخم شرائي معتدل"
    elif rsi < 50:
        mom_state = "📉 زخم بيعي معتدل"
    else:
        mom_state = "⚖️ زخم محايد (انعدام اتجاه واضح)"

    if vol >= 1.2:
        if rsi >= 55:
            breakout_state = "✅ الاختراقات الصاعدة (Breakouts) حقيقية وموثوقة (مدعومة بسيولة شراء قوية)."
        elif rsi <= 45:
            breakout_state = "✅ الكسور الهابطة (Breakdowns) حقيقية وموثوقة (مدعومة بسيولة بيع قوية)."
        else:
            breakout_state = "⚠️ الحركات السعرية الحالية تحتاج تأكيد بإغلاق الشموع (حرب سيولة ومحاولة للسيطرة)."
    else:
        breakout_state = "❌ احذر: الاختراقات والكسور الحالية غالباً **(وهمية - Fakeouts)** بسبب ضعف الفوليوم والسيولة الداعمة (مصيدة صناع السوق)."

    template = f\"\"\"
👑 **الرادار المؤسساتي: كشف السيولة والكسور الوهمية** 👑
━━━━━━━━━━━━━━━━━━━━━━━━━━
🌊 **مؤشرات الفوليوم وتدفق السيولة (Liquidity)**
🔹 حالة السيولة اللحظية: **{vol_state}**
🔹 قوة الزخم (Momentum): **{mom_state}**
━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 **كشف التلاعب: هل الاختراقات والكسور حقيقية؟**
🚨 **التقييم الخوارزمي:** 
{breakout_state}

💡 *القاعدة الذهبية: لا تثق بأي اختراق لمقاومة أو كسر لدعم ما لم يكن مصحوباً بسيولة مؤسساتية مؤكدة لتجنب مصيدة صناع السوق.*
\"\"\"
    return template.strip()

def send_reports
"""

text = text.replace("def send_reports", s15_func.strip())

bot3_target = """bot3_reports.append(("[فوري] 14/14 مسار القمة والقاع", _build_spot_s14(data), None))"""
bot3_repl = bot3_target + "\n            bot3_reports.append((\"[فوري] 15/15 الرادار المؤسساتي والسيولة\", _build_spot_s15(data), None))"
text = text.replace(bot3_target, bot3_repl)

bot2_target = """bot2_reports.append(("👑 مسار القمة والقاع (اتجاه السيولة)", _build_spot_s14(data), None))"""
bot2_repl = bot2_target + "\n        bot2_reports.append((\"👑 الرادار المؤسساتي (كشف التلاعب والسيولة)\", _build_spot_s15(data), None))"
text = text.replace(bot2_target, bot2_repl)

bot1_target = """raw_reports.append(("👑 مسار القمة والقاع (اتجاه السيولة)", _build_spot_s14(data), None))"""
bot1_repl = bot1_target + "\n        raw_reports.append((\"👑 الرادار المؤسساتي (كشف التلاعب والسيولة)\", _build_spot_s15(data), None))"
text = text.replace(bot1_target, bot1_repl)

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
    f.write(text)
