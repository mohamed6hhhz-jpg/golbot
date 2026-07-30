import re

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_futures.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update the conditional appends
old_t_logic = """        if t0: raw_reports.append(("🎯 الصفقات المتقدمة والزيرو انعكاس (الآجل)", t0, None))
        if t1: raw_reports.append(("📊 التقرير الفني المتقدم (الآجل)", t1, None))
        if t2: raw_reports.append(("🌍 تقرير الاقتصاد الكلي (الآجل)", t2, None))
        if t3: raw_reports.append(("⚠️ تقرير شهية المخاطرة (الآجل)", t3, None))
        if t4: raw_reports.append(("📈 تقرير عوائد السندات (الآجل)", t4, None))
        if t5: raw_reports.append(("💱 تقرير قوة العملات (الآجل)", t5, None))"""

new_t_logic = """        raw_reports.append(("🎯 الصفقات المتقدمة والزيرو انعكاس (الآجل)", t0 if t0 else "⚠️ تعذر توليد القالب بسبب الضغط، يرجى المحاولة لاحقاً.", None))
        raw_reports.append(("📊 التقرير الفني المتقدم (الآجل)", t1 if t1 else "⚠️ تعذر توليد القالب بسبب الضغط، يرجى المحاولة لاحقاً.", None))
        raw_reports.append(("🌍 تقرير الاقتصاد الكلي (الآجل)", t2 if t2 else "⚠️ تعذر توليد القالب بسبب الضغط، يرجى المحاولة لاحقاً.", None))
        raw_reports.append(("⚠️ تقرير شهية المخاطرة (الآجل)", t3 if t3 else "⚠️ تعذر توليد القالب بسبب الضغط، يرجى المحاولة لاحقاً.", None))
        raw_reports.append(("📈 تقرير عوائد السندات (الآجل)", t4 if t4 else "⚠️ تعذر توليد القالب بسبب الضغط، يرجى المحاولة لاحقاً.", None))
        raw_reports.append(("💱 تقرير قوة العملات (الآجل)", t5 if t5 else "⚠️ تعذر توليد القالب بسبب الضغط، يرجى المحاولة لاحقاً.", None))"""

text = text.replace(old_t_logic, new_t_logic)

# 2. Update s12_report and s9_report logic in raw_reports
old_s_raw = """        # Inject the Master Summary & High Lot Sniper into Bot2 (the 13-chunk report)
        s12_report = None  # Not implemented for futures
        if s12_report:
            raw_reports.append(("👑 الخلاصة المحورية لليوم (الآجل - Futures)", s12_report, None))
            
        s9_report = None   # Not implemented for futures
        if s9_report:
            raw_reports.append(("👑 مصفوفة التداول السريعة (الآجل - Futures)", s9_report, None))"""

new_s_raw = """        # Inject the Master Summary & High Lot Sniper into Bot2 (the 13-chunk report)
        s12_report = _build_futures_s12(data)
        raw_reports.append(("👑 الخلاصة المحورية لليوم (الآجل - Futures)", s12_report, None))
            
        s9_report = _build_futures_s9(data)
        raw_reports.append(("👑 مصفوفة التداول السريعة (الآجل - Futures)", s9_report, None))"""

text = text.replace(old_s_raw, new_s_raw)

# 3. Update s12_report and s9_report logic in bot2_reports (duplicate?)
old_s_bot2 = """        s12_report = None  # Not implemented for futures
        if s12_report:
            bot2_reports.append(("👑 الخلاصة المحورية والدقيقة (الجيل الخامس - Futures)", s12_report, None))
            
        s9_report = None   # Not implemented for futures
        if s9_report:
            bot2_reports.append(("👑 مصفوفة التداول السريعة والاسكالبينج الاحترافي (Futures)", s9_report, None))"""

new_s_bot2 = """        # s12_report and s9_report already appended to raw_reports, no need to duplicate in bot2_reports?
        # Actually, let's keep them appended to bot2_reports if the user expects them there too.
        # Wait, if they are appended to both, the user gets duplicates!
        # I'll just remove the duplicate block completely from bot2_reports to avoid confusion, 
        # OR keep it if it's required for the 'Bot 2 independent send'. Let's just fix the None.
        s12_report_bot2 = _build_futures_s12(data)
        bot2_reports.append(("👑 الخلاصة المحورية والدقيقة (الجيل الخامس - Futures)", s12_report_bot2, None))
            
        s9_report_bot2 = _build_futures_s9(data)
        bot2_reports.append(("👑 مصفوفة التداول السريعة والاسكالبينج الاحترافي (Futures)", s9_report_bot2, None))"""

text = text.replace(old_s_bot2, new_s_bot2)

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_futures.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Replaced logic in bot_futures.py successfully!")
