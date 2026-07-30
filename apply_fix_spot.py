with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_t_logic = """        if t0: raw_reports.append(("🎯 الصفقات المتقدمة والزيرو انعكاس (الفوري)", t0, None))
        if t1: raw_reports.append(("📊 التقرير الفني المتقدم (الفوري)", t1, None))
        if t2: raw_reports.append(("🌍 تقرير الاقتصاد الكلي (الفوري)", t2, None))
        if t3: raw_reports.append(("⚠️ تقرير شهية المخاطرة (الفوري)", t3, None))
        if t4: raw_reports.append(("📈 تقرير عوائد السندات (الفوري)", t4, None))
        if t5: raw_reports.append(("💱 تقرير قوة العملات (الفوري)", t5, None))"""

new_t_logic = """        raw_reports.append(("🎯 الصفقات المتقدمة والزيرو انعكاس (الفوري)", t0 if t0 else "⚠️ تعذر توليد القالب بسبب الضغط، يرجى المحاولة لاحقاً.", None))
        raw_reports.append(("📊 التقرير الفني المتقدم (الفوري)", t1 if t1 else "⚠️ تعذر توليد القالب بسبب الضغط، يرجى المحاولة لاحقاً.", None))
        raw_reports.append(("🌍 تقرير الاقتصاد الكلي (الفوري)", t2 if t2 else "⚠️ تعذر توليد القالب بسبب الضغط، يرجى المحاولة لاحقاً.", None))
        raw_reports.append(("⚠️ تقرير شهية المخاطرة (الفوري)", t3 if t3 else "⚠️ تعذر توليد القالب بسبب الضغط، يرجى المحاولة لاحقاً.", None))
        raw_reports.append(("📈 تقرير عوائد السندات (الفوري)", t4 if t4 else "⚠️ تعذر توليد القالب بسبب الضغط، يرجى المحاولة لاحقاً.", None))
        raw_reports.append(("💱 تقرير قوة العملات (الفوري)", t5 if t5 else "⚠️ تعذر توليد القالب بسبب الضغط، يرجى المحاولة لاحقاً.", None))"""

if old_t_logic in text:
    text = text.replace(old_t_logic, new_t_logic)
    with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Replaced logic in bot_spot.py successfully!")
else:
    print("Could not find the text block in bot_spot.py")
