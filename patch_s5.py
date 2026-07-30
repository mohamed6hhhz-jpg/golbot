with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re
# Fix broken string
text = re.sub(r'static_probs = f"\U0001f4c8[^\n]*\n[^\n]*\n[^\n]*\n"', r'static_probs = f"📈 احتمال صعود للقمه: {b_p}% (نحو {r2_val}$)\\n📉 احتمال هبوط نحو القاع: {be_p}% (نحو {s2_val}$)\\n🔀 احتمالية التذبذب: {o_p}% (حول {gold_spot}$)\\n"', text, flags=re.DOTALL)

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
    f.write(text)
