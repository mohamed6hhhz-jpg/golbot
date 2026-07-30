import re

def patch_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    # Find the tfs array and modify it
    old_tfs = """    tfs = [
        ('5 دقائق', 'tf_5m', 0.05),
        ('10 دقائق', 'tf_10m', 0.1),
        ('15 دقيقة', 'tf_15m', 0.15),
        ('30 دقيقة', 'tf_30m', 0.25),
        ('1 ساعة', 'tf_hourly', 0.4),
        ('4 ساعات', 'tf_4h', 0.7),
        ('يومي', 'tf_daily', 1.2),
        ('أسبوعي', 'tf_weekly', 2.5),
        ('شهري', 'tf_monthly', 4.5)
    ]"""
    
    new_tfs = """    tfs = [
        ('5 دقائق', 'tf_5m', 0.05),
        ('10 دقائق', 'tf_10m', 0.1),
        ('15 دقيقة', 'tf_15m', 0.15),
        ('30 دقيقة', 'tf_30m', 0.25),
        ('1 ساعة', 'tf_hourly', 0.4),
        ('4 ساعات', 'tf_4h', 0.7),
        ('يومي', 'tf_daily', 1.2)
    ]"""

    if old_tfs in text:
        text = text.replace(old_tfs, new_tfs)
    else:
        print(f"Warning: old_tfs not found in {filepath}")

    # Now find the end of the loop to inject the new blocks
    old_loop_end = """        out.append(f"- الهدف: {tp}$")
        out.append(f"- وقف الخسارة: {sl}$")
        
    out.append("\\n💡 الحكم النهائي للتداول المتعدد:")"""
    
    new_loop_end = """        out.append(f"- الهدف: {tp}$")
        out.append(f"- وقف الخسارة: {sl}$")

    # --- Advanced Weekly and Monthly Scalping ---
    out.append("\\n━━━━━━━━━━━━━━━━━━━━━━━━━━")
    out.append("🦅 صفقات السكالبينج الاحترافية (فريم أسبوعي وشهري)")
    out.append("*(استهداف ارتدادات السيولة الكبرى مع احترام الاتجاه العام بأهداف متعددة وإدارة مخاطر فائقة)*")
    
    adv_tfs = [
        ('الأسبوعي (Weekly Scalp)', 'tf_weekly', 2.5),
        ('الشهري (Monthly Scalp)', 'tf_monthly', 4.5)
    ]
    
    for label, key, atr_mult in adv_tfs:
        tf_data = d.get(key)
        
        if not tf_data or 'pivot' not in tf_data:
            bias = d.get('confluence', {}).get('bias', 'bull')
            piv = gold
            r1 = gold + atr * atr_mult * 0.5
            s1 = gold - atr * atr_mult * 0.5
            r2 = gold + atr * atr_mult
            s2 = gold - atr * atr_mult
        else:
            bias = tf_data.get('bias', 'bull')
            piv = tf_data.get('pivot', gold)
            r1 = tf_data.get('r1', gold + atr * atr_mult * 0.5)
            s1 = tf_data.get('s1', gold - atr * atr_mult * 0.5)
            r2 = tf_data.get('r2', gold + atr * atr_mult)
            s2 = tf_data.get('s2', gold - atr * atr_mult)
            
        if 'bull' in str(bias).lower() or 'صاعد' in str(bias) or 'إيجابي' in str(bias):
            dir_str = "🟢 صاعد (شراء من الانخفاضات)"
            entry = round(piv - (atr * atr_mult * 0.15), 2)
            sl = round(piv - (atr * atr_mult * 0.5), 2)
            t1 = round(piv + (atr * atr_mult * 0.3), 2)
            t2 = round(r1, 2)
            t3 = round(r2, 2)
        else:
            dir_str = "🔴 هابط (بيع من الارتفاعات)"
            entry = round(piv + (atr * atr_mult * 0.15), 2)
            sl = round(piv + (atr * atr_mult * 0.5), 2)
            t1 = round(piv - (atr * atr_mult * 0.3), 2)
            t2 = round(s1, 2)
            t3 = round(s2, 2)
            
        out.append(f"\\n⏱️ **سكالبينج {label}:**")
        out.append(f" - الاتجاه الهيكلي: {dir_str}")
        out.append(f" - 📍 منطقة الدخول المثالية: **{entry}$**")
        out.append(f" - 🎯 الهدف الأول (تأمين 50%): **{t1}$**")
        out.append(f" - 🎯 الهدف الثاني (جني أرباح رئيسي): **{t2}$**")
        out.append(f" - 🎯 الهدف الثالث (الامتداد الأقصى): **{t3}$**")
        out.append(f" - 🛑 وقف الخسارة (صارم): **{sl}$**")
        
    out.append("\\n💡 الحكم النهائي للتداول المتعدد:")"""

    if old_loop_end in text:
        text = text.replace(old_loop_end, new_loop_end)
    else:
        print(f"Warning: old_loop_end not found in {filepath}")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f"Patched {filepath} successfully.")

patch_file('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py')
patch_file('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_futures.py')
