import re

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

s14_func = """
def _build_spot_s14(data: dict) -> str:
    \"\"\"القالب الجديد: القمة والقاع وسعر الإغلاق والاتجاه الأول\"\"\"
    current = data.get('gold', 0.0)
    high = data.get('daily_high', current + 15)
    low = data.get('daily_low', current - 15)
    close = data.get('prev_close', current)

    confluence = data.get('confluence', {})
    trend = confluence.get('verdict', 'محايد')
    rsi = data.get('rsi', 50)
    
    dist_high = abs(high - current)
    dist_low = abs(current - low)
    
    if dist_high < 1.5 and dist_low > 5.0:
        first_target = "📈 السعر يختبر القمة بالفعل (احتمالية اختراق أو ارتداد من القمة)."
        reason = "التداول يتم بالقرب من قمة اليوم."
    elif dist_low < 1.5 and dist_high > 5.0:
        first_target = "📉 السعر يختبر القاع بالفعل (احتمالية كسر أو ارتداد من القاع)."
        reason = "التداول يتم بالقرب من قاع اليوم."
    elif "شراء" in trend or "صاعد" in trend or rsi > 55:
        first_target = "📈 استهداف القمة أولاً (مسار صاعد)"
        reason = f"زخم المشترين أقوى (RSI: {rsi:.1f}) والاتجاه العام يدعم الصعود، مما يدعم الاندفاع نحو {high:.2f}$ أولاً."
    elif "بيع" in trend or "هابط" in trend or rsi < 45:
        first_target = "📉 استهداف القاع أولاً (مسار هابط)"
        reason = f"سيطرة بيعية واضحة (RSI: {rsi:.1f}) والاتجاه يدعم الهبوط، مما يرجح اختبار القاع {low:.2f}$ أولاً."
    else:
        if dist_high < dist_low:
            first_target = "📈 استهداف القمة أولاً (مسار عرضي/متذبذب)"
            reason = f"السوق متذبذب، ولكن السعر أقرب حالياً للقمة {high:.2f}$ ويستعد لاختبارها قبل القاع."
        else:
            first_target = "📉 استهداف القاع أولاً (مسار عرضي/متذبذب)"
            reason = f"السوق متذبذب، ولكن السعر أقرب للقاع {low:.2f}$ والأقرب هو اختباره قبل القمة."

    template = f\"\"\"
👑 **الخارطة السعرية الحيوية: القمة والقاع** 👑
━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 **أهم مستويات اليوم الحالية**
💰 السعر اللحظي: **{current:.2f}$**
🔺 القمة المسجلة (High): **{high:.2f}$**
🔻 القاع المسجل (Low): **{low:.2f}$**
🔒 الإغلاق السابق (Close): **{close:.2f}$**
━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 **البوصلة الزمنية: أيهما يُضرب أولاً اليوم؟**
⚡ {first_target}

🔬 **التفسير الميكانيكي:**
{reason}
\"\"\"
    return template.strip()

def send_reports
"""

text = text.replace("def send_reports", s14_func.strip())

bot3_target = """bot3_reports.append(("[فوري] 13/13 المستهدف الأسبوعي", _build_friday_target(data, False), None))"""
bot3_repl = bot3_target + "\n            bot3_reports.append((\"[فوري] 14/14 مسار القمة والقاع\", _build_spot_s14(data), None))"
text = text.replace(bot3_target, bot3_repl)

bot2_target = """bot2_reports.append(("[16/16] المستهدف الأسبوعي (الجمعة)", _build_friday_target(data, False), None))"""
bot2_repl = bot2_target + "\n        bot2_reports.append((\"👑 مسار القمة والقاع (اتجاه السيولة)\", _build_spot_s14(data), None))"
text = text.replace(bot2_target, bot2_repl)

bot1_target = """raw_reports.append(("👑 الخلاصة المحورية والدقيقة (الجيل الخامس - Spot)", s12_report or f"الخلاصة المحورية: السعر {data.get('gold',0):.2f}$", None))"""
bot1_repl = bot1_target + "\n        raw_reports.append((\"👑 مسار القمة والقاع (اتجاه السيولة)\", _build_spot_s14(data), None))"
text = text.replace(bot1_target, bot1_repl)

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
    f.write(text)
