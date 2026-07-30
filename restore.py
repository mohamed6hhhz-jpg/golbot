with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re
# We need to remove the broken block and restore the original _build_spot_s6 up to the return statement.
# Because the file is currently syntactically broken at line 4946, let's just restore from backup or find the bad block and replace it.
text = re.sub(r'    # ── صفقات السوينج والزيرو انعكاس لجميع الفريمات ──.*?    \)', """    return (
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
    )""", text, flags=re.DOTALL)

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
    f.write(text)
