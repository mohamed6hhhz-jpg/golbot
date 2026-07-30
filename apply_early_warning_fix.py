import re

new_func = """def _build_early_warning_alert(data: dict) -> str:
    \"\"\"القالب الجديد: تنبيه مبكر — انعكاس مرتقب\"\"\"
    current = data.get('gold', 0.0)
    rsi = data.get('tf_hourly', {}).get('rsi', 50)
    atr = data.get('atr', 20.0)
    
    if rsi >= 70:
        grade = "A"
        expected_price = data.get('r3', current + atr * 2.5)
        hours_to_rev = 12
    elif rsi <= 30:
        grade = "A"
        expected_price = data.get('s3', current - atr * 2.5)
        hours_to_rev = 12
    elif rsi > 55:
        grade = "B"
        expected_price = data.get('r2', current + atr * 1.5)
        hours_to_rev = 24
    elif rsi < 45:
        grade = "B"
        expected_price = data.get('s2', current - atr * 1.5)
        hours_to_rev = 24
    else:
        grade = "C"
        expected_price = data.get('r1', current + atr * 0.8) if current > data.get('pivot', current) else data.get('s1', current - atr * 0.8)
        hours_to_rev = 48
        
    try:
        from datetime import datetime, timedelta
        import pytz
        CAIRO_TZ = pytz.timezone('Africa/Cairo')
        rev_date = datetime.now(CAIRO_TZ) + timedelta(hours=hours_to_rev)
        today_date = datetime.now(CAIRO_TZ).date()
        
        if rev_date.date() == today_date:
            day_str = "اليوم"
        elif rev_date.date() == today_date + timedelta(days=1):
            day_str = "غداً"
        else:
            day_str = "قريباً"
            
        date_formatted = rev_date.strftime("%d %b %Y %H:00")
    except:
        day_str = "قريباً"
        date_formatted = ""

    if grade == "A":
        grade_desc = "تشبع حاد ومفرط (انعكاس وشيك جداً وعنيف)"
    elif grade == "B":
        grade_desc = "بداية تشبع وزخم قوي ممتد (انعكاس محتمل قريباً)"
    else:
        grade_desc = "تذبذب سيولة (انعكاس ضعيف يعتمد على الدعوم/المقاومات)"
        
    template = f\"\"\"
⏰ **تنبيه مبكر — انعكاس مرتقب**
*(هذا التنبيه يخبرك بأن الاتجاه الحالي شارف على الانتهاء وسيعكس مساره)*
━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 **XAUUSD | H1**
⏳ **الإطار الزمني المتوقع للانعكاس:** {day_str} — {date_formatted}
━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 **نقطة الارتطام (السعر المتوقع):** **{expected_price:.2f}$**
*(هي النقطة التي سينتهي عندها المسار الحالي وينعكس منها السوق، وهي أفضل منطقة لتعليق أوامر Limit عكسية)*

🧠 **قوة التأكيد (الدرجة {grade}):** **{grade_desc}**
━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ **استعد وراقب السعر عند نقطة الارتطام لتقتنص الانعكاس.**
\"\"\"
    return template.strip()
"""

for filepath in ['c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_futures.py']:
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # We find the existing function using regex from 'def _build_early_warning_alert' to 'return template.strip()'
    pattern = r'def _build_early_warning_alert\(data: dict\) -> str:.*?return template\.strip\(\)'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        text = text[:match.start()] + new_func + text[match.end():]
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"Replaced in {filepath} successfully")
    else:
        print(f"Failed to find target in {filepath}")
