import os
import re

with open('bot.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Common changes for both
# 1. Remove truncation from template 6
code = code.replace(
'''    # استخراج الصفقات فقط لتخفيف حجم التوكنز جداً وتجنب خطأ 413 Payload Too Large
    pivot_val = d.get('pivot', '---')
    simple_trades = "الصفقات الأساسية المقترحة:\\n"
    if 'confluence' in d:
        for b in d['confluence'].get('buys', []):
            simple_trades += f"🟢 الشراء: {b.get('entry')} (ثقة {b.get('score', 0)}%)\\n"
        for s in d['confluence'].get('sells', []):
            simple_trades += f"🔴 البيع: {s.get('entry')} (ثقة {s.get('score', 0)}%)\\n"''',
'''    pivot_val = d.get('pivot', '---')'''
)

code = code.replace(
'''--- التقرير الأساسي (مستويات الصفقات الموصى بها): ---
{simple_trades}''',
'''--- التقرير الأساسي (الصفقات ومستويات الدعم والمقاومة): ---
{fixed_rep}'''
)

# ---- bot_futures.py ----
code_futures = code.replace(
    "for mode in ['futures', 'spot']:",
    "for mode in ['futures']:"
)
code_futures = code_futures.replace(
    "Telethon Bot",
    "Telethon Bot (Futures)"
)
code_futures = code_futures.replace(
    "goldbot.session",
    "goldbot_futures.session"
)

with open('bot_futures.py', 'w', encoding='utf-8') as f:
    f.write(code_futures)

# ---- bot_spot.py ----
code_spot = code.replace(
    "for mode in ['futures', 'spot']:",
    "for mode in ['spot']:"
)
code_spot = code_spot.replace(
    'GROQ_API_KEY        = os.environ.get("GROQ_API_KEY", "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")',
    'GROQ_API_KEY        = os.environ.get("GROQ_API_KEY", "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")'
)
code_spot = code_spot.replace(
    'TELEGRAM_BOT_TOKEN  = "8783502825:AAEEgxaxzgiAxwl4oBp4zl73jmqwBtKCalc"',
    'TELEGRAM_BOT_TOKEN  = "8135586080:AAFS1ZI2XcsPrnjtTvAPlXxlTMrSO_Lu3Qc"'
)
code_spot = code_spot.replace(
    "Telethon Bot",
    "Telethon Bot (Spot)"
)
code_spot = code_spot.replace(
    "goldbot.session",
    "goldbot_spot.session"
)

with open('bot_spot.py', 'w', encoding='utf-8') as f:
    f.write(code_spot)

print('Split successful')
