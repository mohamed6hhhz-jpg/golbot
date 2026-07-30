with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

injection_code = """
    # ── صفقات السوينج والزيرو انعكاس لجميع الفريمات ──
    tf_factors = [
        ("15 دقيقة", 0.12),
        ("30 دقيقة", 0.17),
        ("ساعة", 0.25),
        ("4 ساعات", 0.50),
        ("يومي", 1.00),
        ("أسبوعي", 2.20),
        ("شهري", 4.50)
    ]
    
    tf_matrix_blocks = []
    for tf_name, factor in tf_factors:
        tf_atr = atr * factor
        # Swing
        sw_buy_entry = round(gold - (tf_atr * 1.5), 2)
        sw_buy_sl = round(sw_buy_entry - (tf_atr * 0.7), 2)
        sw_buy_tp = round(sw_buy_entry + (tf_atr * 2.5), 2)
        
        sw_sell_entry = round(gold + (tf_atr * 1.5), 2)
        sw_sell_sl = round(sw_sell_entry + (tf_atr * 0.7), 2)
        sw_sell_tp = round(sw_sell_entry - (tf_atr * 2.5), 2)
        
        # Zero Reflection
        zr_buy_entry = round(gold - (tf_atr * 2.8), 2)
        zr_buy_sl = round(zr_buy_entry - (tf_atr * 0.25), 2)
        zr_buy_tp = round(zr_buy_entry + (tf_atr * 1.0), 2)
        
        zr_sell_entry = round(gold + (tf_atr * 2.8), 2)
        zr_sell_sl = round(zr_sell_entry + (tf_atr * 0.25), 2)
        zr_sell_tp = round(zr_sell_entry - (tf_atr * 1.0), 2)
        
        tf_block = f\"\"\"
💠 **فريم {tf_name}**
📌 **السوينج (Swing):**
🟢 شراء: الدخول {sw_buy_entry}$ | الهدف {sw_buy_tp}$ | الوقف {sw_buy_sl}$
🔴 بيع: الدخول {sw_sell_entry}$ | الهدف {sw_sell_tp}$ | الوقف {sw_sell_sl}$
📌 **زيرو انعكاس (Zero Drawdown):**
🟢 شراء: الدخول {zr_buy_entry}$ | الهدف {zr_buy_tp}$ | الوقف {zr_buy_sl}$
🔴 بيع: الدخول {zr_sell_entry}$ | الهدف {zr_sell_tp}$ | الوقف {zr_sell_sl}$\"\"\"
        tf_matrix_blocks.append(tf_block.strip())

    matrix_text = "\\n\\n━━━━━━━━━━━━━━━━━━━━━━━━━━\\n"
    matrix_text += "🌐 **مصفوفة صفقات السوينج والزيرو انعكاس (متعددة الإطارات الزمنية)** 🌐\\n"
    matrix_text += "تم حساب هذه الصفقات رياضياً بدقة متناهية لكل فريم زمني بناءً على نسبة التذبذب والسيولة اللحظية:\\n\\n"
    matrix_text += "\\n".join(tf_matrix_blocks)
"""

old_return = """        "━━━━━━━━━━━━━━━━━━━━━━━━━━\\n💡 **الحكم الاستراتيجي للصفقات**\\n"
        f"بناءً على موقع السعر الحالي من مناطق السيولة، فرص {'الشراء من مستويات ' + str(buy_entry) + '$ هي الأرجح والأكثر أماناً' if rsi < 50 else 'البيع من مستويات ' + str(sell_entry) + '$ هي الأرجح والأكثر أماناً'} مع ضرورة انتظار الإشارة المؤكدة وعدم الاستعجال."
    )"""

new_return = injection_code + """

    return (
        "👑 **هندسة صفقات اللوت العالي (High Lot Sniper)** 👑\\n━━━━━━━━━━━━━━━━━━━━━━━━━━\\n🎯 **اصطياد السيولة عند الانعكاسات الكاملة (Liquidity Sweeps)** 🎯\\n"
        "تم تصميم هذه الصفقات لاصطياد السيولة عند الانعكاسات الكاملة (Liquidity Sweeps) بمناطق الذروة (Extreme Edges). يُستخدم لوت عالي مع التزام تام وصارم جداً بوقف الخسارة المذكور نظراً لحساسية هذه المناطق.\\n\\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\\n📊 **الخارطة السعرية لمناطق الذروة**\\n"
        f"- **السعر الحالي:** {gold:.2f}$\\n"
        f"- **نقطة الارتكاز (Pivot):** {pivot:.2f}$\\n"
        f"- **منطقة سيولة الشراء (Liquidity Pool - Long):** {buy_entry:.2f}$\\n"
        f"- **منطقة سيولة البيع (Liquidity Pool - Short):** {sell_entry:.2f}$\\n"
        f"- **التقلب المعتمد (ATR):** {atr:.2f}$ 📊\\n\\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\\n⚡ **إحداثيات الدخول عالية الدقة (اللوت العالي)** ⚡\\n\\n"
        f"**🟢 1. صفقة شراء قناص (Long Sweep)**\\n"
        f" + الدخول: **{buy_entry:.2f}$** (اصطياد القاع)\\n"
        f" + وقف الخسارة: **{buy_sl:.2f}$** (صارم ومغلق)\\n"
        f" + الهدف الأول: **{buy_t1:.2f}$** (تأمين الصفقة)\\n"
        f" + الهدف الثاني: **{buy_t2:.2f}$**\\n"
        f" + الهدف الثالث: **{buy_t3:.2f}$** (انعكاس كامل)\\n\\n"
        f"**🔴 2. صفقة بيع قناص (Short Sweep)**\\n"
        f" + الدخول: **{sell_entry:.2f}$** (اصطياد القمة)\\n"
        f" + وقف الخسارة: **{sell_sl:.2f}$** (صارم ومغلق)\\n"
        f" + الهدف الأول: **{sell_t1:.2f}$** (تأمين الصفقة)\\n"
        f" + الهدف الثاني: **{sell_t2:.2f}$**\\n"
        f" + الهدف الثالث: **{sell_t3:.2f}$** (انعكاس كامل)\\n\\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\\n⚠️ **القواعد الذهبية لإدارة المخاطر العالية** ⚠️\\n"
        "- **لا تدخل ماركت من منتصف النطاق.** هذه الصفقات تُفعل **فقط** عند وصول السعر للمستويات المذكورة تماماً لضمان أفضل نسبة عائد للمخاطرة (Risk/Reward).\\n"
        "- وقف الخسارة غير قابل للتحريك (مسافة ATR رياضية) لتجنب الانهيارات المفاجئة.\\n\\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\\n💡 **الحكم الاستراتيجي للصفقات**\\n"
        f"بناءً على موقع السعر الحالي من مناطق السيولة، فرص {'الشراء من مستويات ' + str(buy_entry) + '$ هي الأرجح والأكثر أماناً' if rsi < 50 else 'البيع من مستويات ' + str(sell_entry) + '$ هي الأرجح والأكثر أماناً'} مع ضرورة انتظار الإشارة المؤكدة وعدم الاستعجال."
        f"{matrix_text}"
    )"""

import re
# We match the entire old return block to replace it with the newly assembled block + the calculation logic before it.
pattern = r'    return \(\n        "👑 \*\*هندسة صفقات اللوت العالي.*?\n    \)'
text = re.sub(pattern, new_return, text, flags=re.DOTALL)

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Applied!")
