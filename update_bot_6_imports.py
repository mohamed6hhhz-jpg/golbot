import re

with open("Goldbot/bot_6.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add import
content = content.replace(
    ", generate_next_15m_movement_report",
    ", generate_next_15m_movement_report, generate_liquidity_target_timing_report"
)

# Add calling logic before "total_reports = len(reports_to_send)"
insert_str = """
            # توليد الوجهة القادمة للسيولة (القالب السابع والعشرون)
            liq_timing = generate_liquidity_target_timing_report(data)
            if liq_timing:
                reports_to_send.append(("الوجهة القادمة للسيولة والزمن المتوقع 🎯⏳", liq_timing))
        
        total_reports = len(reports_to_send)
"""

content = content.replace("        total_reports = len(reports_to_send)", insert_str.lstrip('\n'))

with open("Goldbot/bot_6.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Updated bot_6.py successfully!")
