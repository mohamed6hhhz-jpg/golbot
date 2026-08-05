with open('Goldbot/bot_6.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add import
import_find = "generate_best_overall_trade_report"
import_replace = "generate_best_overall_trade_report, generate_daily_best_direction_report"
content = content.replace(import_find, import_replace)

# Add to reports_to_send list
append_code = """
            # توليد تقرير أفضل اتجاه لليوم (القالب التاسع عشر)
            best_direction = generate_daily_best_direction_report(data)
            if best_direction:
                reports_to_send.append(("أفضل اتجاه للذهب خلال اليوم 🧭", best_direction))
                
            # توليد خريطة الفيدرالي"""

content = content.replace("            # توليد خريطة الفيدرالي", append_code)

with open('Goldbot/bot_6.py', 'w', encoding='utf-8') as f:
    f.write(content)
