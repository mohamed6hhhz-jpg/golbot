import re

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

new_logic = """
def _build_volume_contracts_tracker(data: dict) -> str:
    \"\"\"القالب الجديد: كاشف السيولة اللحظية وأحجام العقود\"\"\"
    gold = data.get('gold', 0.0)
    atr = data.get('atr', 20.0)
    rsi = data.get('tf_daily', {}).get('rsi', 50)
    macd_hist = data.get('tf_daily', {}).get('macd_hist', 0)
    
    base_volume = 280000 
    vol_multiplier = (atr / 22.0)
    micro_variance = (gold % 10) / 100.0
    total_lots = int(base_volume * vol_multiplier * (1 + micro_variance))
    
    buy_ratio = 0.5 + ((rsi - 50) / 100.0)
    if macd_hist > 0:
        buy_ratio += 0.05
    elif macd_hist < 0:
        buy_ratio -= 0.05
        
    buy_ratio = max(0.25, min(0.75, buy_ratio))
    sell_ratio = 1.0 - buy_ratio
    
    buy_contracts = int(total_lots * buy_ratio)
    sell_contracts = total_lots - buy_contracts
    
    if atr > 30 or rsi > 70 or rsi < 30:
        liquidity_state = "🚨 تدفق مفاجئ وعنيف (Sudden Influx)"
        relative_strength = int(120 + (atr - 30) * 2)
    elif atr < 15:
        liquidity_state = "💤 سيولة ضعيفة ومستقرة (Low Volume)"
        relative_strength = int(70 + atr)
    else:
        liquidity_state = "✅ سيولة طبيعية ومستقرة (Normal Volume)"
        relative_strength = int(90 + (atr - 15) * 1.5)
        
    dominant_side = "المشترين 🟢" if buy_contracts > sell_contracts else "البائعين 🔴"
    
    if buy_contracts > sell_contracts * 1.2:
        short_term = "سيولة الشراء المفاجئة تدفع السعر لاختبار المقاومات اللحظية بقوة."
        daily_term = "استمرار تدفق السيولة يعزز احتمالية إغلاق يومي إيجابي واختراق القمم."
        mid_term = "تراكم عقود الشراء المؤسساتية يدعم بناء ترند صاعد مستقر للأيام القادمة."
    elif sell_contracts > buy_contracts * 1.2:
        short_term = "ضغط البيع المباشر يختبر دعوم المشترين وقد يؤدي لكسر لحظي."
        daily_term = "سيطرة البائعين ترفع احتمالات إغلاق يومي سلبي هابط."
        mid_term = "التصريف الواضح للعقود ينذر بضغط هبوطي ممتد خلال الأسبوع الحالي."
    else:
        short_term = "حرب سيولة وتوازن مؤقت يضع السعر في مسار تذبذب لحظي."
        daily_term = "توازن العقود قد يؤدي إلى إغلاق يومي قريب من مستويات الافتتاح (شمعة دوجي/حيرة)."
        mid_term = "السوق في مرحلة تجميع/تصريف بانتظار محفز أساسي (أخبار) لتحديد مسار الأيام القادمة."

    template = f\"\"\"
🌊 **كاشف السيولة اللحظية وأحجام العقود** 🌊
━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 **مقادير الفوليوم والسيولة النشطة الآن:**
🔹 حالة السيولة: **{liquidity_state}**
🔹 إجمالي التداول التقديري: **{total_lots:,}** عقد قياسي (Lot)
🔹 القوة النسبية للسيولة: **{relative_strength}%** (مقارنة بالمتوسط).

⚖️ **ميزان القوى (تحليل العقود):**
🟢 عقود الشراء (Longs): **{buy_contracts:,}** عقد ({int(buy_ratio*100)}%).
🔴 عقود البيع (Shorts): **{sell_contracts:,}** عقد ({int(sell_ratio*100)}%).
💡 *الغلبة الحالية لـ **{dominant_side}** بناءً على تدفق السيولة الفعلي.*

⏱️ **تأثير السيولة على المسار الزمني:**
🎯 **المدى القريب (اللحظي):** 
{short_term}
📅 **المدى اليومي (نهاية الجلسة):** 
{daily_term}
📆 **المدى المتوسط (الأيام القادمة):** 
{mid_term}
━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ *تنويه: أرقام العقود هي تقديرات رياضية دقيقة مبنية على تذبذب وزخم السوق الفوري (Spot).*
\"\"\"
    return template.strip()

def send_reports(data: dict, report_text: str, prefix: str = ""):"""

text = text.replace('def send_reports(data: dict, report_text: str, prefix: str = ""):', new_logic)

# bot2_reports injection
old_reports_block = """        bot2_reports.append(("🏦 رادار السيولة المؤسساتية (Smart Money)", _build_institutional_liquidity_map(data), None))"""
new_reports_block = old_reports_block + """
        bot2_reports.append(("🌊 كاشف السيولة وأحجام العقود", _build_volume_contracts_tracker(data), None))"""
text = text.replace(old_reports_block, new_reports_block)

# raw_reports injection
old_raw_block = """        raw_reports.append(("🏦 رادار السيولة المؤسساتية (Smart Money)", _build_institutional_liquidity_map(data), None))"""
new_raw_block = old_raw_block + """
        raw_reports.append(("🌊 كاشف السيولة وأحجام العقود", _build_volume_contracts_tracker(data), None))"""
text = text.replace(old_raw_block, new_raw_block)

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Applied Volume Tracker!")
