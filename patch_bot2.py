import re

def prettify_bot2_blocks(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replacement 1: daily_liquidity_block
    old_daily = '''        daily_liquidity_block = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
💧 سيولة اليومي {today_str}

✅ مستوى شراء بعد كسر وثبات {buy_lvl}
الهدف:
{buy_t1}
{buy_t2}
{buy_t3}

🛑 مستوى البيع بعد كسر وثبات {sell_lvl}
الهدف:
{sell_t1}
{sell_t2}
{sell_t3}

✅ الدخول بعد كسر + ثبات
"""'''

    new_daily = '''        daily_liquidity_block = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
💧 سيولة اليومي ({today_str})
━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ شراء مع الاتجاه (Buy Stop)
الكسر والثبات أعلى: {buy_lvl}$
🎯 الأهداف:
1️⃣ {buy_t1}$
2️⃣ {buy_t2}$
3️⃣ {buy_t3}$
━━━━━━━━━━━━━━━━━━━━━━━━━━
🛑 بيع مع الاتجاه (Sell Stop)
الكسر والثبات أسفل: {sell_lvl}$
🎯 الأهداف:
1️⃣ {sell_t1}$
2️⃣ {sell_t2}$
3️⃣ {sell_t3}$
━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ تنبيه: الدخول فقط بعد الكسر والثبات (إغلاق شمعة).
"""'''

    # Replacement 2: limits_block
    old_limits = '''        limits_block = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
⏳ الأوامر المعلقة اللحظية (Limit Orders)
(جودة وتمركز > 65% | تحديث ديناميكي)

🟢 Buy Limit:
دخول: {buy_limit_price}
هدف: {buy_limit_tp}
وقف: {buy_limit_sl}

🔴 Sell Limit:
دخول: {sell_limit_price}
هدف: {sell_limit_tp}
وقف: {sell_limit_sl}
"""'''

    new_limits = '''        limits_block = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
⏳ الأوامر المعلقة اللحظية (Limit Orders)
(جودة وتمركز > 65% | تحديث ديناميكي)
━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 أمر شراء معلق (Buy Limit):
🔹 الدخول: {buy_limit_price}$
🎯 الهدف: {buy_limit_tp}$
🛑 الوقف: {buy_limit_sl}$
━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 أمر بيع معلق (Sell Limit):
🔹 الدخول: {sell_limit_price}$
🎯 الهدف: {sell_limit_tp}$
🛑 الوقف: {sell_limit_sl}$
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""'''

    # Replacement 3: breakout_5m_block
    old_breakout = '''        breakout_5m_block = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ صفقات الاختراق اللحظي (Breakout)

شراء
كسر {b5_buy}
هدف {b5_buy_tp}

بيع
كسر {b5_sell}
هدف {b5_sell_tp}

إغلاق بجسم فريم 5 دقائق.
شرط أساسي:
لا يتم الدخول في أي صفقة، سواء شراء أو بيع، إلا بعد تحقق شرط:
الإغلاق بجسم شمعة إطار الـ5 دقائق فوق مستوى الكسر في الشراء، أو أسفل مستوى الكسر في البيع.
"""'''

    new_breakout = '''        breakout_5m_block = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ صفقات الاختراق اللحظي السريعة (Breakout)
━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 إشارة الشراء:
اختراق مستوى: {b5_buy}$
🎯 الهدف السريع: {b5_buy_tp}$

🔴 إشارة البيع:
كسر مستوى: {b5_sell}$
🎯 الهدف السريع: {b5_sell_tp}$
━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ شرط أساسي للتنفيذ:
إغلاق شمعة (5 دقائق) بالكامل فوق مستوى الكسر للشراء، أو أسفل مستوى الكسر للبيع.
"""'''

    if old_daily in content:
        content = content.replace(old_daily, new_daily)
        print(f"Updated daily_liquidity_block in {filename}")
    else:
        print(f"daily_liquidity_block not found in {filename}")

    if old_limits in content:
        content = content.replace(old_limits, new_limits)
        print(f"Updated limits_block in {filename}")
    else:
        print(f"limits_block not found in {filename}")

    if old_breakout in content:
        content = content.replace(old_breakout, new_breakout)
        print(f"Updated breakout_5m_block in {filename}")
    else:
        print(f"breakout_5m_block not found in {filename}")

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

prettify_bot2_blocks('Goldbot/bot_spot.py')
prettify_bot2_blocks('Goldbot/bot_futures.py')
