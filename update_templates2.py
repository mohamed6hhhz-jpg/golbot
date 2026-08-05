import re

with open('Goldbot/ai_generator_bot6.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update generate_sudden_liquidity_report
sudden_find = """        gold = data.get("gold", 0)
        atr = data.get("atr", 30)
        rel_vol = data.get("rel_vol", 1.0)
        
        hist = data.get('hist_ctx', {})
        gold_chg = round(hist.get('chg_1d', 0), 2) if hist else 0"""

sudden_replace = """        gold = data.get("gold", 0)
        atr = data.get("atr", 30)
        rel_vol = data.get("rel_vol", 1.0)
        
        hist = data.get('hist_ctx', {})
        gold_chg = round(hist.get('chg_1d', 0), 2) if hist else 0
        
        bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path = _calc_prob_and_reasons(data)"""

content = content.replace(sudden_find, sudden_replace)

sudden_find_2 = """- السعر المستهدف للسيولة الفجائية: {target_price}$"""
sudden_replace_2 = """- قمة السيولة (BSL): السعر يستهدف {round(gold + (atr * 0.8), 2)}$ (احتمالية: {bullish_score}%)
- قاع السيولة (SSL): السعر يستهدف {round(gold - (atr * 0.8), 2)}$ (احتمالية: {bearish_score}%)
- المسار الأقوى: {stronger_path}"""

content = content.replace(sudden_find_2, sudden_replace_2)

sudden_find_3 = """🎯 أهداف السيولة الفجائية:
▪️ السعر المستهدف للسيولة الفجائية: السعر يستهدف ضرب مستوى [السعر المستهدف]$ بقوة الزخم الحالي."""
sudden_replace_3 = """🎯 مسارات السيولة الفجائية المتوقعة:
▪️ مسار الاختراق الصاعد (BSL): السعر يستهدف ضرب مستوى {round(gold + (atr * 0.8), 2)}$ بقوة الزخم الإيجابي.
   (الاحتمالية: {bullish_score}% — السبب: {reason_up_str})
▪️ مسار الكسر الهابط (SSL): السعر يستهدف ضرب مستوى {round(gold - (atr * 0.8), 2)}$ بقوة الزخم السلبي.
   (الاحتمالية: {bearish_score}% — السبب: {reason_down_str})
   📌 الاتجاه الأقرب للحدوث: {stronger_path}"""

content = content.replace(sudden_find_3, sudden_replace_3)


# 2. Update Asian Session
asian_find = """        gold = data.get("gold", 0)
        atr = data.get("atr", 30)"""
asian_replace = """        gold = data.get("gold", 0)
        atr = data.get("atr", 30)
        bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path = _calc_prob_and_reasons(data)"""

content = content.replace(asian_find, asian_replace)

asian_find_2 = """- هدف السيولة الصاعد للجلسة الآسيوية: {asian_upper_target}$
- هدف السيولة الهابط للجلسة الآسيوية: {asian_lower_target}$"""
asian_replace_2 = """- هدف السيولة الصاعد للجلسة الآسيوية: {asian_upper_target}$ (احتمالية: {bullish_score}%)
- هدف السيولة الهابط للجلسة الآسيوية: {asian_lower_target}$ (احتمالية: {bearish_score}%)
- المسار الأقوى: {stronger_path}"""

content = content.replace(asian_find_2, asian_replace_2)

asian_find_3 = """▪️ هدف السيولة الشرائية (الحد العلوي): السعر يستهدف مستوى [الرقم العلوي]$ كقمة متوقعة للجلسة.
▪️ هدف السيولة البيعية (الحد السفلي): السعر يستهدف مستوى [الرقم السفلي]$ كقاع متوقع للجلسة."""
asian_replace_3 = """▪️ هدف السيولة الشرائية (الحد العلوي): السعر يستهدف مستوى {asian_upper_target}$ كقمة متوقعة.
   (الاحتمالية: {bullish_score}% — السبب: {reason_up_str})
▪️ هدف السيولة البيعية (الحد السفلي): السعر يستهدف مستوى {asian_lower_target}$ كقاع متوقع.
   (الاحتمالية: {bearish_score}% — السبب: {reason_down_str})
   📌 الاتجاه المرجح لكسر النطاق: {stronger_path}"""

content = content.replace(asian_find_3, asian_replace_3)


# 3. Update European Session
euro_find = """        gold = data.get("gold", 0)
        atr = data.get("atr", 30)"""
euro_replace = """        gold = data.get("gold", 0)
        atr = data.get("atr", 30)
        bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path = _calc_prob_and_reasons(data)"""
# We only want to replace it for euro & US. It's safe since they have the exact same starting line.
# I'll use a regex replace with count to target them specifically or just replace all instances.
content = content.replace(euro_find, euro_replace)

euro_find_2 = """- هدف السيولة الصاعد للجلسة الأوروبية: {euro_upper_target}$
- هدف السيولة الهابط للجلسة الأوروبية: {euro_lower_target}$"""
euro_replace_2 = """- هدف السيولة الصاعد للجلسة الأوروبية: {euro_upper_target}$ (احتمالية: {bullish_score}%)
- هدف السيولة الهابط للجلسة الأوروبية: {euro_lower_target}$ (احتمالية: {bearish_score}%)
- المسار الأقوى: {stronger_path}"""

content = content.replace(euro_find_2, euro_replace_2)

euro_find_3 = """▪️ هدف السيولة الشرائية العلوية: السعر يستهدف مستوى [الرقم العلوي]$ لامتصاص السيولة والبحث عن الزخم الصاعد.
▪️ هدف السيولة البيعية السفلية: السعر يستهدف مستوى [الرقم السفلي]$ لضرب السيولة وتأسيس قاع لليوم."""
euro_replace_3 = """▪️ هدف السيولة الشرائية العلوية: السعر يستهدف مستوى {euro_upper_target}$ لامتصاص السيولة والبحث عن الزخم الصاعد.
   (الاحتمالية: {bullish_score}% — السبب: {reason_up_str})
▪️ هدف السيولة البيعية السفلية: السعر يستهدف مستوى {euro_lower_target}$ لضرب السيولة وتأسيس قاع لليوم.
   (الاحتمالية: {bearish_score}% — السبب: {reason_down_str})
   📌 المسار الأقوى لافتتاحية لندن: {stronger_path}"""

content = content.replace(euro_find_3, euro_replace_3)


# 4. Update US Session
us_find_2 = """- هدف السيولة الصاعد للجلسة الأمريكية: {us_upper_target}$
- هدف السيولة الهابط للجلسة الأمريكية: {us_lower_target}$"""
us_replace_2 = """- هدف السيولة الصاعد للجلسة الأمريكية: {us_upper_target}$ (احتمالية: {bullish_score}%)
- هدف السيولة الهابط للجلسة الأمريكية: {us_lower_target}$ (احتمالية: {bearish_score}%)
- المسار الأقوى: {stronger_path}"""

content = content.replace(us_find_2, us_replace_2)

us_find_3 = """▪️ هدف السيولة الشرائية العلوية: السعر يستهدف مستوى [الرقم العلوي]$ لامتصاص السيولة الشرائية واختبار قوى المشترين.
▪️ هدف السيولة البيعية السفلية: السعر يستهدف مستوى [الرقم السفلي]$ لضرب السيولة البيعية وتأسيس انعكاس قوي."""
us_replace_3 = """▪️ هدف السيولة الشرائية العلوية: السعر يستهدف مستوى {us_upper_target}$ لامتصاص السيولة الشرائية واختبار قوى المشترين.
   (الاحتمالية: {bullish_score}% — السبب: {reason_up_str})
▪️ هدف السيولة البيعية السفلية: السعر يستهدف مستوى {us_lower_target}$ لضرب السيولة البيعية وتأسيس انعكاس قوي.
   (الاحتمالية: {bearish_score}% — السبب: {reason_down_str})
   📌 المسار الأقوى لافتتاحية نيويورك: {stronger_path}"""

content = content.replace(us_find_3, us_replace_3)


with open('Goldbot/ai_generator_bot6.py', 'w', encoding='utf-8') as f:
    f.write(content)
