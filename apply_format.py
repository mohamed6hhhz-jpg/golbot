import re

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_logic = """    if "شراء" in trend or "صاعد" in trend or (rsi > 55 and macd > 0):
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
📌 القمة المسجلة حتى الآن: **{recorded_high:.2f}$**
📌 القاع المسجل حتى الآن: **{recorded_low:.2f}$**
━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 القمة المتوقعة (المستهدفة): **{expected_high:.2f}$**
⚓ القاع المتوقع (المستهدف): **{expected_low:.2f}$**
🔒 سعر الإغلاق السابق (Prev Close): **{close:.2f}$**
━━━━━━━━━━━━━━━━━━━━━━━━━━
🧭 **البوصلة الزمنية: إلى أين نتجه أولاً؟**
⚡ {first_target}

🔬 **التحليل الميكانيكي الدقيق للمسار:**
{reason}
\"\"\""""

new_logic = """    if "شراء" in trend or "صاعد" in trend or (rsi > 55 and macd > 0):
        first_target = f"📈 استهداف القمة المتوقعة أولاً ({expected_high:.2f}$)"
        reason = f"السيولة تتدفق بقوة نحو الأعلى (RSI: {rsi:.1f})، والاتجاه العام صاعد ومستقر. من المرجح جداً أن يندفع السعر لاختبار مناطق المقاومة العنيفة عند القمة المتوقعة قبل أي محاولة هبوط."
        expected_close = nums.get('r1', current + (atr * 0.5))
    elif "بيع" in trend or "هابط" in trend or (rsi < 45 and macd < 0):
        first_target = f"📉 استهداف القاع المتوقع أولاً ({expected_low:.2f}$)"
        reason = f"السوق يخضع لضغوط بيعية واضحة (RSI: {rsi:.1f})، والاتجاه العام يميل بقوة للهبوط. التوقعات تشير لضرب مستويات الدعم العميقة عند القاع المتوقع قبل أي ارتداد."
        expected_close = nums.get('s1', current - (atr * 0.5))
    else:
        if dist_high < dist_low:
            first_target = f"📈 الأقرب رياضياً هو القمة ({expected_high:.2f}$)"
            reason = f"السوق حالياً في مسار متذبذب (عرضي)، ولكن السعر يتمركز في النصف العلوي وأقرب لمناطق القمة، مما يرجح اختبارها أولاً لتفريغ السيولة الشرائية المتبقية."
        else:
            first_target = f"📉 الأقرب رياضياً هو القاع ({expected_low:.2f}$)"
            reason = f"السوق حالياً في مسار متذبذب (عرضي)، ولكن السعر يتمركز في النصف السفلي وأقرب لمناطق القاع، مما يرجح اختباره أولاً لتجميع سيولة شرائية جديدة."
        expected_close = pivot

    template = f\"\"\"
👑 **خارطة المسار اليومي المتوقع (Daily Expected Range)** 👑
━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 **المحطات السعرية الأقصى توقعاً اليوم (Spot)**
💰 السعر اللحظي الحالي: **{current:.2f}$**
📌 القمة المسجلة حتى الآن: **{recorded_high:.2f}$**
📌 القاع المسجل حتى الآن: **{recorded_low:.2f}$**
🔒 سعر الإغلاق السابق (Prev Close): **{close:.2f}$**
━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 القمة المتوقعة (المستهدفة): **{expected_high:.2f}$**
⚓ القاع المتوقع (المستهدف): **{expected_low:.2f}$**
🏁 سعر الإغلاق المتوقع (Expected Close): **{expected_close:.2f}$**
━━━━━━━━━━━━━━━━━━━━━━━━━━
🧭 **البوصلة الزمنية: إلى أين نتجه أولاً؟**
⚡ {first_target}

🔬 **التحليل الميكانيكي الدقيق للمسار:**
{reason}
\"\"\""""

if old_logic in text:
    text = text.replace(old_logic, new_logic)
    with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Replaced successfully")
else:
    print("Not found! Fallback regex search...")
    # attempt regex fallback
    fallback_pattern = re.compile(re.escape("""    if "شراء" in trend or "صاعد" in trend or (rsi > 55 and macd > 0):""").replace(r'\r', '').replace(r'\n', r'\r?\n') + r'.*?' + re.escape('"""'), re.DOTALL)
    match = fallback_pattern.search(text)
    if match:
        text = text[:match.start()] + new_logic + text[match.end():]
        with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
            f.write(text)
        print("Replaced via regex successfully")
    else:
        print("Failed to replace!")
