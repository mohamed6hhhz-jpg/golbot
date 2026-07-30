import re

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Fix 1: _build_spot_s14 (14/16 or 18/20 depending on numbering)
s14_old_block = """    # Expected Extremes for the day (not what has been recorded so far)
    expected_high = nums.get('r2', current + atr)
    expected_low = nums.get('s2', current - atr)
    
    rsi = nums.get('rsi', 50)"""

s14_new_block = """    # Expected Extremes for the day (not what has been recorded so far)
    expected_high = nums.get('r2', current + atr)
    expected_low = nums.get('s2', current - atr)
    
    # Recorded extremes
    recorded_high = data.get('daily_high', current)
    if recorded_high <= current: recorded_high = current + (atr * 0.2)
    recorded_low = data.get('daily_low', current)
    if recorded_low >= current: recorded_low = current - (atr * 0.2)
    
    rsi = nums.get('rsi', 50)"""

text = text.replace(s14_old_block, s14_new_block)

s14_old_template = """👑 **خارطة المسار اليومي المتوقع (Daily Expected Range)** 👑
━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 **المحطات السعرية الأقصى توقعاً اليوم (Spot)**
💰 السعر اللحظي الحالي: **{current:.2f}$**
🔺 القمة اليومية المتوقعة (Expected High): **{expected_high:.2f}$**
🔻 القاع اليومي المتوقع (Expected Low): **{expected_low:.2f}$**
🔒 سعر الإغلاق السابق (Prev Close): **{close:.2f}$**
━━━━━━━━━━━━━━━━━━━━━━━━━━"""

s14_new_template = """👑 **خارطة المسار اليومي المتوقع (Daily Expected Range)** 👑
━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 **المحطات السعرية الأقصى توقعاً اليوم (Spot)**
💰 السعر اللحظي الحالي: **{current:.2f}$**
📌 القمة المسجلة حتى الآن: **{recorded_high:.2f}$**
📌 القاع المسجل حتى الآن: **{recorded_low:.2f}$**
━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 القمة المتوقعة (المستهدفة): **{expected_high:.2f}$**
⚓ القاع المتوقع (المستهدف): **{expected_low:.2f}$**
🔒 سعر الإغلاق السابق (Prev Close): **{close:.2f}$**
━━━━━━━━━━━━━━━━━━━━━━━━━━"""

text = text.replace(s14_old_template, s14_new_template)


# Fix 2: _build_summary_template prompt percentages
t12_old_prompt = """📈 نسبة الصعود: [توقعك كنسبة]%
📉 نسبة الهبوط: [توقعك كنسبة]%"""

t12_new_prompt = """📈 احتمال صعود للقمه: [توقعك كنسبة]% (نحو {r2}$)
📉 احتمال هبوط نحو القاع: [توقعك كنسبة]% (نحو {s2}$)
🔀 احتمالية التذبذب: [توقعك كنسبة]% (حول {gold}$)"""

text = text.replace(t12_old_prompt, t12_new_prompt)


# Fix 3: _build_template_6 percentages
t6_old_code = """    up_prob_calc = 50 + (score / total_weight) * 45  # Cap at max 95% / min 5%
    up_prob = int(round(up_prob_calc))
    up_prob = max(10, min(90, up_prob))
    down_prob = 100 - up_prob

    static_header = f\"\"\"🎯 خلاصة انحياز الذهب | التحديث المباشر

📈 نسبة الصعود نحو القمة: {up_prob}%
📉 نسبة الهبوط نحو القاع: {down_prob}%\"\"\""""

t6_new_code = """    up_prob_calc = 50 + (score / total_weight) * 45  # Cap at max 95% / min 5%
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

text = text.replace(t6_old_code, t6_new_code)


with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Replacement 1 done?", s14_old_block in text == False)
print("Replacement 2 done?", t12_old_prompt in text == False)
print("Replacement 3 done?", t6_old_code in text == False)
