with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

s16_func = """
def _build_spot_s16(data: dict) -> str:
    \"\"\"القالب الجديد: استراتيجية التداول بحجم اللوت الكامل (Full Lot Strategy)\"\"\"
    current = data.get('gold', 0.0)
    s1 = data.get('s1', current - 15)
    s2 = data.get('s2', current - 30)
    s3 = data.get('s3', current - 50)
    r1 = data.get('r1', current + 15)
    r2 = data.get('r2', current + 30)
    r3 = data.get('r3', current + 50)

    template = f\"\"\"
👑 **الخطة التكتيكية للسيولة (Full Lot Strategy)** 👑
━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 **1. استراتيجية الشراء (الدعوم الحيوية):**
🛒 **نشتري لوت كامل:** **{s1:.2f}$**
🎯 **الهدف:** **{r1:.2f}$**
🛑 **الاستوب:** إغلاق شمعة ساعة أسفل **{s2:.2f}$**

🔴 **2. استراتيجية تأكيد الكسر (التحول البيعي):**
🔻 **بيع لوت كامل** بعد إغلاق شمعة ساعة أسفل: **{s2:.2f}$**
🎯 **الهدف الممتد:** **{s3:.2f}$**

🩸 **3. استراتيجية البيع العكسي (القمم):**
📉 **بيع لوت كامل:** **{r2:.2f}$**
🎯 **الهدف الممتد:** **{s3:.2f}$**
🛑 **الاستوب:** إغلاق شمعة يومية أعلى **{r3:.2f}$**
━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 *تنويه: يُرجى الالتزام التام بشروط الإغلاق الموضحة في وقف الخسارة لحماية رأس المال.*
\"\"\"
    return template.strip()

def send_reports
"""

text = text.replace("def send_reports", s16_func.strip())

bot3_target = """bot3_reports.append(("[فوري] 15/15 الرادار المؤسساتي والسيولة", _build_spot_s15(data), None))"""
bot3_repl = bot3_target + "\n            bot3_reports.append((\"[فوري] 16/16 استراتيجية اللوت الكامل\", _build_spot_s16(data), None))"
text = text.replace(bot3_target, bot3_repl)

bot2_target = """bot2_reports.append(("👑 الرادار المؤسساتي (كشف التلاعب والسيولة)", _build_spot_s15(data), None))"""
bot2_repl = bot2_target + "\n        bot2_reports.append((\"👑 الخطة التكتيكية (Full Lot Strategy)\", _build_spot_s16(data), None))"
text = text.replace(bot2_target, bot2_repl)

bot1_target = """raw_reports.append(("👑 الرادار المؤسساتي (كشف التلاعب والسيولة)", _build_spot_s15(data), None))"""
bot1_repl = bot1_target + "\n        raw_reports.append((\"👑 الخطة التكتيكية (Full Lot Strategy)\", _build_spot_s16(data), None))"
text = text.replace(bot1_target, bot1_repl)

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
    f.write(text)
