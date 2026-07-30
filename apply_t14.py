with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Define the exact block to replace using the actual file content
import re

# Block 1: Add expected_close calculation
old_logic_1 = """    close = data.get('prev_close', current)
    confluence = data.get('confluence', {})
    trend = confluence.get('verdict', 'محايد')
    
    if "شراء" in trend or "صاعد" in trend or (rsi > 55 and macd > 0):"""

new_logic_1 = """    close = data.get('prev_close', current)
    confluence = data.get('confluence', {})
    trend = confluence.get('verdict', 'محايد')
    
    if "شراء" in trend or "صاعد" in trend or (rsi > 55 and macd > 0):
        expected_close = nums.get('r1', current + (atr * 0.5))
    elif "بيع" in trend or "هابط" in trend or (rsi < 45 and macd < 0):
        expected_close = nums.get('s1', current - (atr * 0.5))
    else:
        expected_close = pivot
        
    if "شراء" in trend or "صاعد" in trend or (rsi > 55 and macd > 0):"""

text = text.replace(old_logic_1, new_logic_1)

# Block 2: Rearrange template
old_logic_2 = """📌 القاع المسجل حتى الآن: **{recorded_low:.2f}$**
━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 القمة المتوقعة (المستهدفة): **{expected_high:.2f}$**
⚓ القاع المتوقع (المستهدف): **{expected_low:.2f}$**
🔒 سعر الإغلاق السابق (Prev Close): **{close:.2f}$**
━━━━━━━━━━━━━━━━━━━━━━━━━━"""

new_logic_2 = """📌 القاع المسجل حتى الآن: **{recorded_low:.2f}$**
🔒 سعر الإغلاق السابق (Prev Close): **{close:.2f}$**
━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 القمة المتوقعة (المستهدفة): **{expected_high:.2f}$**
⚓ القاع المتوقع (المستهدف): **{expected_low:.2f}$**
🏁 سعر الإغلاق المتوقع (Expected Close): **{expected_close:.2f}$**
━━━━━━━━━━━━━━━━━━━━━━━━━━"""

text = text.replace(old_logic_2, new_logic_2)

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Template updated successfully")
