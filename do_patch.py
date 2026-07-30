import re

def get_liquidity_targets_code():
    return """
def _build_liquidity_time_targets(data: dict) -> str:
    \"\"\"القالب الجديد: أهداف السيولة الزمنية (جلسة، يوم، أسبوع، شهر)\"\"\"
    current = float(data.get('gold', 2000.0))
    atr = float(data.get('atr', 20.0))
    
    rsi = float(data.get('rsi', 50.0))
    macd = float(data.get('macd', 0.0))
    confluence = data.get('confluence', {})
    trend = confluence.get('verdict', 'محايد')
    
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
    
    template = f\"\"\"
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
\"\"\"
    return template.strip()
"""

with open('extracted_funcs.py', 'r', encoding='utf-8') as f:
    extracted = "\n" + f.read() + "\n"

def patch_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    changed = False
    
    # 1. Inject missing functions BEFORE _generate_all
    # Instead of replacing def send_reports( which is error-prone, let's inject before def send_reports(
    
    inject_block = ""
    
    if "def _build_liquidity_time_targets(" not in text:
        inject_block += get_liquidity_targets_code() + "\n"
        
    if "def _s_nums(" not in text:
        inject_block += extracted + "\n"
        
    if inject_block:
        text = text.replace("def send_reports(", inject_block + "\ndef send_reports(")
        changed = True

    if changed:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"Patched {filepath} successfully.")
    else:
        print(f"No changes needed for {filepath}.")

patch_file('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py')
patch_file('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_futures.py')
