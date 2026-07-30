def generate_advanced_tf(label, key, atr_mult, d):
    gold = d.get('gold', 2000)
    atr = d.get('atr', 20)
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
        
    return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
🦅 صفقات السكالبينج العميق: الفريم الـ {label} (جودة فائقة)
(استهداف ارتدادات السيولة الكبرى مع احترام الاتجاه العام)
- الاتجاه العام للفريم: {dir_str}
- منطقة التمركز والدخول: {entry}$
- الأهداف:
   1️⃣ الهدف الأول: {t1}$ (تأمين)
   2️⃣ الهدف الثاني: {t2}$ (رئيسي)
   3️⃣ الهدف الثالث: {t3}$ (ممتد)
- وقف الخسارة (صارم): {sl}$"""

# Test it
d = {'gold': 2400, 'atr': 20, 'tf_weekly': {'bias': 'bull', 'pivot': 2405}}
print(generate_advanced_tf('أسبوعي', 'tf_weekly', 2.5, d))
