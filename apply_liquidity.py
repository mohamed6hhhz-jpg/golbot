import re

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

new_logic = """
def _build_institutional_liquidity_map(data: dict) -> str:
    \"\"\"القالب الجديد: خريطة السيولة المؤسساتية (Smart Money Concepts)\"\"\"
    gold = data.get('gold', 0.0)
    atr = data.get('atr', 20.0)
    s3 = data.get('s3', gold - atr * 2)
    r3 = data.get('r3', gold + atr * 2)
    sh = data.get('swing_h', gold + atr)
    sl = data.get('swing_l', gold - atr)
    
    hist_ctx = data.get('hist_ctx', {}) or {}
    low_52w = hist_ctx.get('low_52w', gold - atr * 15)
    high_52w = hist_ctx.get('high_52w', gold + atr * 15)
    
    # Buy-side Liquidity (Whales buying from retail sell-stops)
    buy_zone_top = round(min(s3, sl) + (atr * 0.2), 2)
    buy_zone_bot = round(min(s3, sl) - (atr * 0.8), 2)
    
    # Sell-side Liquidity (Whales selling into retail buy-stops)
    sell_zone_bot = round(max(r3, sh) - (atr * 0.2), 2)
    sell_zone_top = round(max(r3, sh) + (atr * 0.8), 2)
    
    # Sovereign / Macro zones (using nearest 100 round numbers or 52W extremes)
    macro_buy = round(low_52w, 2)
    if gold - macro_buy > 200:
        macro_buy = round(gold - (gold % 100), 2)  # nearest lower 100
        
    macro_sell = round(high_52w, 2)
    if macro_sell - gold > 200:
        macro_sell = round(gold + (100 - (gold % 100)), 2) # nearest upper 100

    template = f\"\"\"
🏦 **رادار السيولة المؤسساتية (Smart Money & Whales)** 🏦
━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 **خريطة الأوامر المعلقة لكبار اللاعبين**

🟢 **1. منطقة تجميع الحيتان (Discount Liquidity Pool):**
📍 **النطاق المستهدف:** **{buy_zone_bot:.2f}$** إلى **{buy_zone_top:.2f}$**
💡 **من ينتظر هنا؟** صناديق التحوط والمؤسسات المالية الكبرى.
⚙️ **الاستراتيجية:** اصطياد قيعان الأفراد (Stop-Hunt) لبناء مراكز شراء ضخمة بأسعار مخفضة جداً، حيث تتحول ستوبات المبيعات إلى وقود لصعودهم.

🔴 **2. منطقة تصريف الحيتان (Premium Liquidity Pool):**
📍 **النطاق المستهدف:** **{sell_zone_bot:.2f}$** إلى **{sell_zone_top:.2f}$**
💡 **من ينتظر هنا؟** البنوك التجارية وكبار المضاربين (Whales).
⚙️ **الاستراتيجية:** ضرب قمم الأفراد وتصريف العقود الشرائية الضخمة وجني الأرباح العنيفة عند هذه المستويات.

🏛️ **3. الجدار الاستراتيجي (مناطق البنوك المركزية والصناديق السيادية):**
🛡️ **خط الدفاع الشرائي (أوامر سيادية):** بالقرب من **{macro_buy:.2f}$**
🧱 **خط الدفاع البيعي (تدخلات عكسية):** بالقرب من **{macro_sell:.2f}$**
💡 **ملاحظة:** هذه المستويات تُمثل "القيمة العادلة الكبرى" ولا تُكسر بسهولة، وتُعد أهدافاً استثمارية طويلة الأمد للإبقاء على توازن الأسواق.

━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ *تنويه: الأسعار داخل هذه المناطق تشهد تذبذباً عنيفاً جداً (Spikes) ومحاولات خداع (Fakeouts) قبل أخذ الاتجاه الحقيقي (Mark-up / Mark-down).*
\"\"\"
    return template.strip()

def send_reports(data: dict, report_text: str, prefix: str = ""):"""

text = text.replace('def send_reports(data: dict, report_text: str, prefix: str = ""):', new_logic)

# Inject into bot2_reports
old_reports_block = """        bot2_reports.append(("🚨 رادار الأخبار العاجلة (Breaking News)", _build_sudden_news_alert(data), None))"""
new_reports_block = old_reports_block + """
        bot2_reports.append(("🏦 رادار السيولة المؤسساتية (Smart Money)", _build_institutional_liquidity_map(data), None))"""
text = text.replace(old_reports_block, new_reports_block)

# Inject into raw_reports
old_raw_block = """        raw_reports.append(("🚨 رادار الأخبار العاجلة (Breaking News)", _build_sudden_news_alert(data), None))"""
new_raw_block = old_raw_block + """
        raw_reports.append(("🏦 رادار السيولة المؤسساتية (Smart Money)", _build_institutional_liquidity_map(data), None))"""
text = text.replace(old_raw_block, new_raw_block)

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Applied Institutional Liquidity!")
