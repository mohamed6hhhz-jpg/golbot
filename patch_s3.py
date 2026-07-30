import re

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r"    up_prob_calc = 50 \+ \(score \/ total_weight\) \* 45.*?📉 نسبة الهبوط نحو القاع: \{down_prob\}%\"\"\""

replacement = """    up_prob_calc = 50 + (score / total_weight) * 45
    up_prob_raw = int(round(up_prob_calc))
    up_prob_raw = max(10, min(90, up_prob_raw))
    down_prob_raw = 100 - up_prob_raw
    osc_prob_raw = max(10, 100 - abs(up_prob_raw - down_prob_raw))
    
    # Normalize to 100
    tot = up_prob_raw + down_prob_raw + osc_prob_raw
    up_prob = int(round(up_prob_raw / tot * 100))
    down_prob = int(round(down_prob_raw / tot * 100))
    osc_prob = 100 - (up_prob + down_prob)
    
    r2_val = round(d.get('gold', 2000) + d.get('atr', 20) * 1.5, 2)
    s2_val = round(d.get('gold', 2000) - d.get('atr', 20) * 1.5, 2)
    gld_val = round(d.get('gold', 2000), 2)

    static_header = f\"\"\"🎯 خلاصة انحياز الذهب | التحديث المباشر

📈 احتمال صعود للقمه: {up_prob}% (نحو {r2_val}$)
📉 احتمال هبوط نحو القاع: {down_prob}% (نحو {s2_val}$)
🔀 احتمالية التذبذب: {osc_prob}% (حول {gld_val}$)\"\"\""""

text = re.sub(pattern, replacement, text, flags=re.DOTALL)

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Replacement applied")
