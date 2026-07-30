import re

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_futures.py', 'r', encoding='utf-8') as f:
    text = f.read()

append_block = """        bot2_reports.append(("👑 مسار القمة والقاع (اتجاه السيولة)", _build_futures_s14(data), None))
        bot2_reports.append(("👑 الرادار المؤسساتي (كشف التلاعب والسيولة)", _build_futures_s15(data), None))
        bot2_reports.append(("👑 الخطة التكتيكية (Full Lot Strategy)", _build_futures_s16(data), None))
        bot2_reports.append(("⏰ تنبيه مبكر — انعكاس مرتقب", _build_early_warning_alert(data), None))
        bot2_reports.append(("🚨 رادار الأخبار العاجلة (Breaking News)", _build_sudden_news_alert(data), None))
        bot2_reports.append(("🏦 رادار السيولة المؤسساتية (Smart Money)", _build_institutional_liquidity_map(data), None))
        bot2_reports.append(("🌊 كاشف السيولة وأحجام العقود", _build_volume_contracts_tracker(data), None))
"""

# Find _build_friday_target and append right after it
match = re.search(r'(bot2_reports\.append\(\(.*?\], _build_friday_target\(data, True\), None\)\))', text)

if match:
    full_target = match.group(1)
    text = text.replace(full_target, full_target + "\n" + append_block)
    with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_futures.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Appended 7 templates to bot_futures.py successfully!")
else:
    print("Could not find the injection point via regex")
