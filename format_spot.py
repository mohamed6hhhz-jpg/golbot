import re

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

# We need to enhance the formatting of s4 to s11 without altering logic.
# I will build replacement strings.

def format_replacer(match):
    # This is complex, I will just manually provide the new formatted string for each function.
    pass

# For s4 السكالبينج
s4_old = r"### تحليل السوق الفوري 📊\n#### بيانات السوق الحالية 📈\n\* السعر الحالي: \*\*\{gold:\.2f\}\$\*\* 💰\n"
s4_new = "👑 **تحليل السوق الفوري وهندسة السكالبينج (Scalping)** 👑\\n━━━━━━━━━━━━━━━━━━━━━━━━━━\\n📊 **بيانات السوق اللحظية والحيوية**\\n* السعر الحالي: **{gold:.2f}$** 💰\\n"
text = re.sub(r"### تحليل السوق الفوري 📊\\n#### بيانات السوق الحالية 📈\\n\* السعر الحالي: \*\*\{gold:\.2f\}\$\*\* 💰\\n", s4_new, text)

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
    f.write(text)
