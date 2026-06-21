import re

def force_12(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        code = f.read()

    # The string we want to replace is where report_text is appended to raw_reports
    old_append = '''    if report_text:
        raw_reports.append(("👑 التقرير الكمي الشامل للذهب", report_text, None))'''
        
    new_append = '''    if report_text:
        # Split the giant fixed report into exactly 5 sections to ensure we get EXACTLY 12/12 Telegram messages
        sections = report_text.split("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        if len(sections) >= 6:
            raw_reports.append(("👑 الأسعار وحالة السوق", sections[0] + "━━━━━━━━━━━━━━━━━━━━━━━━━━" + sections[1] + "━━━━━━━━━━━━━━━━━━━━━━━━━━" + sections[2], None))
            raw_reports.append(("📌 القمم والقيعان الحالية", sections[3], None))
            raw_reports.append(("🟢 صفقات الشراء الموصى بها", sections[4], None))
            raw_reports.append(("🔴 صفقات البيع الموصى بها", sections[5], None))
            raw_reports.append(("📉 الفنيات والمستويات", sections[6] if len(sections) > 6 else "", None))
        else:
            raw_reports.append(("👑 التقرير الكمي الشامل للذهب", report_text, None))'''
            
    code = code.replace(old_append, new_append)
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(code)

force_12('bot_futures.py')
force_12('bot_spot.py')
print("Forced 12 successfully")
