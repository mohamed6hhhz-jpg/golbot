with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()
import re

new_func = """def _build_spot_s14(data: dict) -> str:
    \"\"\"القالب الجديد: القمة المتوقعة والقاع المتوقع وسعر الإغلاق والاتجاه الأول\"\"\"
    nums = _s_nums(data)
    current = nums.get('gold', data.get('gold', 0.0))
    atr = nums.get('atr', 20.0)
    pivot = nums.get('pivot', current)
    
    # Expected Extremes for the day (not what has been recorded so far)
    expected_high = nums.get('r2', current + atr)
    expected_low = nums.get('s2', current - atr)
    
    rsi = nums.get('rsi', 50)
    macd = nums.get('macd', 0.0)
    
    dist_high = abs(expected_high - current)
    dist_low = abs(current - expected_low)
    
    close = data.get('prev_close', current)
    confluence = data.get('confluence', {})
    trend = confluence.get('verdict', 'محايد')
    
    if "شراء" in trend or "صاعد" in trend or (rsi > 55 and macd > 0):
        first_target = f"📈 استهداف القمة المتوقعة أولاً ({expected_high:.2f}$)"
        reason = f"السيولة تتدفق بقوة نحو الأعلى (RSI: {rsi:.1f})، والاتجاه العام صاعد ومستقر. من المرجح جداً أن يندفع السعر لاختبار مناطق المقاومة العنيفة عند القمة المتوقعة قبل أي محاولة هبوط."
    elif "بيع" in trend or "هابط" in trend or (rsi < 45 and macd < 0):
        first_target = f"📉 استهداف القاع المتوقع أولاً ({expected_low:.2f}$)"
        reason = f"السوق يخضع لضغوط بيعية واضحة (RSI: {rsi:.1f})، والاتجاه العام يميل بقوة للهبوط. التوقعات تشير لضرب مستويات الدعم العميقة عند القاع المتوقع قبل أي ارتداد."
    else:
        if dist_high < dist_low:
            first_target = f"📈 الأقرب رياضياً هو القمة ({expected_high:.2f}$)"
            reason = f"السوق حالياً في مسار متذبذب (عرضي)، ولكن السعر يتمركز في النصف العلوي وأقرب لمناطق القمة، مما يرجح اختبارها أولاً لتفريغ السيولة الشرائية المتبقية."
        else:
            first_target = f"📉 الأقرب رياضياً هو القاع ({expected_low:.2f}$)"
            reason = f"السوق حالياً في مسار متذبذب (عرضي)، ولكن السعر يتمركز في النصف السفلي وأقرب لمناطق القاع، مما يرجح اختباره أولاً لتجميع سيولة شرائية جديدة."

    template = f\"\"\"
👑 **خارطة المسار اليومي المتوقع (Daily Expected Range)** 👑
━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 **المحطات السعرية الأقصى توقعاً اليوم (Spot)**
💰 السعر اللحظي الحالي: **{current:.2f}$**
🔺 القمة اليومية المتوقعة (Expected High): **{expected_high:.2f}$**
🔻 القاع اليومي المتوقع (Expected Low): **{expected_low:.2f}$**
🔒 سعر الإغلاق السابق (Prev Close): **{close:.2f}$**
━━━━━━━━━━━━━━━━━━━━━━━━━━
🧭 **البوصلة الزمنية: إلى أين نتجه أولاً؟**
⚡ {first_target}

🔬 **التحليل الميكانيكي الدقيق للمسار:**
{reason}
━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 *تنويه: القمة والقاع هنا ليسا ما تم تسجيله بالفعل، بل هما الأهداف القصوى (القمة المتوقعة والقاع المتوقع) التي يتجه لها السعر اليوم بناءً على خوارزميات قياس الزخم والسيولة (ATR).*
\"\"\"
    return template.strip()"""

pattern = re.compile(r'def _build_spot_s14\(data: dict\) -> str:.*?return template\.strip\(\)', re.DOTALL)
match = pattern.search(text)
if match:
    text = text[:match.start()] + new_func + text[match.end():]
    with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Patched s14 successfully")
else:
    print("Could not find s14 function")
