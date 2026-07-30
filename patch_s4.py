import re

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r"            # Prepend correct static probabilities\n            static_probs = f\"📈 نسبة الصعود: \{bull_pct\}%\\n📉 نسبة الهبوط: \{bear_pct\}%\\n\""

replacement = """            # Prepend correct static probabilities
            osc_pct = max(10, 100 - abs(bull_pct - bear_pct))
            tot = bull_pct + bear_pct + osc_pct
            b_p = int(round(bull_pct / tot * 100))
            be_p = int(round(bear_pct / tot * 100))
            o_p = 100 - (b_p + be_p)
            r2_val = round(gold_spot + spot_data.get('atr', 20) * 1.5, 2)
            s2_val = round(gold_spot - spot_data.get('atr', 20) * 1.5, 2)
            static_probs = f\"📈 احتمال صعود للقمه: {b_p}% (نحو {r2_val}$)\\n📉 احتمال هبوط نحو القاع: {be_p}% (نحو {s2_val}$)\\n🔀 احتمالية التذبذب: {o_p}% (حول {gold_spot}$)\\n\""""

text = re.sub(pattern, replacement, text, flags=re.DOTALL)

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Replacement applied")
