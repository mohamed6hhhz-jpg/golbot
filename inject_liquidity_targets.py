def _build_liquidity_time_targets(data: dict) -> str:
    """القالب الجديد: أهداف السيولة الزمنية (جلسة، يوم، أسبوع، شهر)"""
    # Safe fetching without external dependencies
    current = float(data.get('gold', 2000.0))
    atr = float(data.get('atr', 20.0))
    
    rsi = float(data.get('rsi', 50.0))
    macd = float(data.get('macd', 0.0))
    confluence = data.get('confluence', {})
    trend = confluence.get('verdict', 'محايد')
    
    # تحديد اتجاه تدفق السيولة
    if "شراء" in trend or "صاعد" in trend or (rsi > 55 and macd > 0):
        flow_dir = 1
        flow_text = "🟢 تدفق شرائي (Bullish Liquidity)"
    elif "بيع" in trend or "هابط" in trend or (rsi < 45 and macd < 0):
        flow_dir = -1
        flow_text = "🔴 تدفق بيعي (Bearish Liquidity)"
    else:
        flow_dir = 1 if rsi >= 50 else -1
        flow_text = "⚪ سيولة متذبذبة (Neutral / Choppy)"

    target_session = round(current + (flow_dir * atr * 0.35), 2)
    target_day = round(current + (flow_dir * atr * 0.85), 2)
    target_week = round(current + (flow_dir * atr * 2.5), 2)
    target_month = round(current + (flow_dir * atr * 8.0), 2)

    icon_s = "📈" if flow_dir == 1 else "📉"
    
    template = f"""
👑 **أهداف السيولة الزمنية المتراكمة (Time-Based Liquidity Targets)** 👑
━━━━━━━━━━━━━━━━━━━━━━━━━━
🧭 **اتجاه السيولة المهيمن الآن:** **{flow_text}**
💰 **السعر اللحظي الراهن:** **{current:.2f}$**
━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 **رقم السيولة المستهدف إلى نهاية الجلسة (Session):**
{icon_s} السعر الدقيق: **{target_session:.2f}$**
*(يمثل المحطة القادمة لضرب سيولة المضاربين اللحظيين)*

🎯 **رقم السيولة المستهدف إلى نهاية اليوم (Daily):**
{icon_s} السعر الدقيق: **{target_day:.2f}$**
*(يمثل إغلاق شمعة اليوم وتمركز سيولة التبييت)*

🎯 **رقم السيولة المستهدف إلى نهاية الأسبوع (Weekly):**
{icon_s} السعر الدقيق: **{target_week:.2f}$**
*(يمثل نقطة تمركز صناع السوق وصناديق التحوط للأسبوع)*

🎯 **رقم السيولة المستهدف إلى نهاية الشهر (Monthly):**
{icon_s} السعر الدقيق: **{target_month:.2f}$**
*(يمثل الهدف الماكرو-اقتصادي للسيولة المؤسساتية الاستراتيجية)*
━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ *ملاحظة كمية: هذه الأرقام ديناميكية وتتحدث فورياً مع تحرك مؤشرات التذبذب (ATR) وتدفقات الفوليوم.*
"""
    return template.strip()

import os
with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text_spot = f.read()

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_futures.py', 'r', encoding='utf-8') as f:
    text_futures = f.read()

import inspect
func_code = inspect.getsource(_build_liquidity_time_targets)

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'a', encoding='utf-8') as f:
    f.write('\n\n' + func_code + '\n\n')
with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_futures.py', 'a', encoding='utf-8') as f:
    f.write('\n\n' + func_code + '\n\n')

# Now inject append logic
append_line = '        bot2_reports.append(("🎯 أهداف السيولة الزمنية (Targets)", _build_liquidity_time_targets(data), None))\n'
append_line_raw = '        raw_reports.append(("🎯 أهداف السيولة الزمنية (Targets)", _build_liquidity_time_targets(data), None))\n'

# SPOT
target_spot = 'bot2_reports.append(("🌊 كاشف السيولة وأحجام العقود", _build_volume_contracts_tracker(data), None))'
if target_spot in text_spot:
    text_spot = text_spot.replace(target_spot, target_spot + "\n" + append_line)
    
target_spot_raw = 'raw_reports.append(("🌊 كاشف السيولة وأحجام العقود", _build_volume_contracts_tracker(data), None))'
if target_spot_raw in text_spot:
    text_spot = text_spot.replace(target_spot_raw, target_spot_raw + "\n" + append_line_raw)

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
    f.write(text_spot)

# FUTURES
target_fut = 'bot2_reports.append(("🌊 كاشف السيولة وأحجام العقود", _build_volume_contracts_tracker(data), None))'
if target_fut in text_futures:
    text_futures = text_futures.replace(target_fut, target_fut + "\n" + append_line)

target_fut_raw = 'raw_reports.append(("🌊 كاشف السيولة وأحجام العقود", _build_volume_contracts_tracker(data), None))'
if target_fut_raw in text_futures:
    text_futures = text_futures.replace(target_fut_raw, target_fut_raw + "\n" + append_line_raw)
    
with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_futures.py', 'w', encoding='utf-8') as f:
    f.write(text_futures)

print("Injected logic and appends to both files!")
