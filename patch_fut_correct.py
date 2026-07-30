import re

new_func = r'''def _build_friday_target(d: dict, is_futures: bool = False) -> str:
    from datetime import datetime, timezone
    
    # Safely extract basic nums
    gold = float(d.get('gold', 0))
    pivot = float(d.get('pivot', 0))
    atr = float(d.get('atr', 40))
    if atr == 0: atr = 40
    
    tf_w = d.get('tf_weekly', {}) or {}
    w_pivot = float(tf_w.get('pivot', 0) or pivot)
    w_atr = float(tf_w.get('atr', 60) or 60)
    if w_atr == 0: w_atr = 60
    
    tf_d = d.get('tf_daily', {}) or {}
    d_rsi = float(tf_d.get('rsi', 50) or 50)
    
    macd_val = float(d.get('macd_hist', d.get('macd', 0)) or 0)
    
    today = datetime.now(timezone.utc).weekday()
    days = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
    day_name = days[today]
    
    is_bullish = gold >= w_pivot and d_rsi >= 45
    is_bearish = gold < w_pivot and d_rsi <= 55
    
    if is_bullish:
        trend_ar = "صاعد 🟢"
        reason = f"السعر يتداول فوق نقطة الارتكاز الأسبوعية ({w_pivot:.2f}$) مع زخم إيجابي قوي."
        target_price = round(w_pivot + w_atr * 0.8, 2)
        if gold > target_price: target_price = round(gold + w_atr * 0.3, 2)
        cancel_cond = f"إغلاق شمعة يومية أسفل الدعم الأسبوعي المركزي ({round(w_pivot - w_atr*0.3, 2)}$)"
    elif is_bearish:
        trend_ar = "هابط 🔴"
        reason = f"السعر يتداول أسفل نقطة الارتكاز الأسبوعية ({w_pivot:.2f}$) مع ضغط بيعي مستمر."
        target_price = round(w_pivot - w_atr * 0.8, 2)
        if gold < target_price: target_price = round(gold - w_atr * 0.3, 2)
        cancel_cond = f"إغلاق شمعة يومية أعلى المقاومة الأسبوعية المركزية ({round(w_pivot + w_atr*0.3, 2)}$)"
    else:
        trend_ar = "عرضي (تذبذب) 🟡"
        reason = f"السعر يتداول حول نقطة الارتكاز ({w_pivot:.2f}$) بدون سيطرة واضحة لأي من الطرفين."
        target_price = round(w_pivot, 2)
        cancel_cond = f"كسر النطاق السعري العرضي الحالي بإغلاق قوي"
        
    accuracy = "عالية جداً 🔥" if today >= 2 else "متوسطة (تتضح الرؤية تدريجياً خلال الأسبوع) ⏳"
    
    return (
        "🎯 **البوصلة الأسبوعية: مستهدف إغلاق يوم الجمعة الرئيسي** 🎯\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 **اليوم الحالي:** {day_name}\n"
        f"🧭 **الاتجاه العام حتى نهاية الأسبوع:** {trend_ar}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📊 **قراءة السيولة التراكمية:**\n"
        f"بناءً على تداولات الأيام السابقة وتمركز السيولة، فإن {reason}\n\n"
        "🎯 **المستهدف الرئيسي (يوم الجمعة):**\n"
        f"🔹 **مستهدف الإغلاق المتوقع:** **{target_price:.2f}$**\n"
        f"🔹 **نسبة التحقق المتوقعة:** {accuracy}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ **شرط إلغاء السيناريو:** يتغير هذا المستهدف بالكامل وتفشل النظرة الحالية فقط في حال {cancel_cond}."
    )

'''

def patch_file(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if '_build_friday_target' not in content:
        content = content.replace('def _build_fixed_template', new_func + '\n\ndef _build_fixed_template')
        
    if 'fixed += "\\n\\n" + _build_friday_target' not in content:
        content = content.replace(
            'return fixed, ai_instructions',
            'fixed += "\\n\\n" + _build_friday_target(d, True)\n    return fixed, ai_instructions'
        )
        
    # Find the end of bot2_reports appending block
    # In bot_futures.py, after appending bot2_reports there is a return or end of block
    append_str = 'bot2_reports.append(("[16/16] المستهدف الأسبوعي (الجمعة)", _build_friday_target(data, True), None))'
    if append_str not in content:
        # Search for `if s9_report:\n            bot2_reports.append(("👑 مصفوفة التداول السريعة والاسكالبينج الاحترافي (Futures)", s9_report, None))`
        # and insert right after it.
        pattern = r'(if s9_report:\s*bot2_reports\.append\(\("👑 مصفوفة التداول السريعة والاسكالبينج الاحترافي \(Futures\)", s9_report, None\)\))'
        content = re.sub(pattern, r'\1\n        ' + append_str, content)

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

patch_file('Goldbot/bot_futures.py')
