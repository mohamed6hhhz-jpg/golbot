import re

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Using regex to extract each function block
funcs_to_extract = [
    r'(def _build_spot_s14.*?return template\n)',
    r'(def _build_spot_s15.*?return template\n)',
    r'(def _build_spot_s16.*?return template\n)',
    r'(def _build_early_warning_alert.*?return template\n)',
    r'(def _fetch_breaking_news.*?(?=def _build_sudden_news_alert))',
    r'(def _build_sudden_news_alert.*?return template\n)',
    r'(def _build_institutional_liquidity_map.*?return template\n)',
    r'(def _build_volume_contracts_tracker.*?return template\n)'
]

extracted = []
for pattern in funcs_to_extract:
    match = re.search(pattern, text, re.DOTALL)
    if match:
        extracted.append(match.group(1))
    else:
        print(f"Failed to find pattern: {pattern[:30]}...")

combined_code = "\n\n".join(extracted)
combined_code = combined_code.replace('def _build_spot_s14', 'def _build_futures_s14')
combined_code = combined_code.replace('def _build_spot_s15', 'def _build_futures_s15')
combined_code = combined_code.replace('def _build_spot_s16', 'def _build_futures_s16')
# Make sure the template title says "الآجل - Futures" instead of "Spot" or "الفوري"
combined_code = combined_code.replace('Spot', 'Futures').replace('الفوري', 'الآجل')

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_futures.py', 'a', encoding='utf-8') as f:
    f.write('\n\n' + combined_code + '\n\n')

# Now update send_reports in bot_futures.py to append these
with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_futures.py', 'r', encoding='utf-8') as f:
    f_text = f.read()

append_block = """
        bot2_reports.append(("👑 مسار القمة والقاع (اتجاه السيولة)", _build_futures_s14(data), None))
        bot2_reports.append(("👑 الرادار المؤسساتي (كشف التلاعب والسيولة)", _build_futures_s15(data), None))
        bot2_reports.append(("👑 الخطة التكتيكية (Full Lot Strategy)", _build_futures_s16(data), None))
        bot2_reports.append(("⏰ تنبيه مبكر — انعكاس مرتقب", _build_early_warning_alert(data), None))
        bot2_reports.append(("🚨 رادار الأخبار العاجلة (Breaking News)", _build_sudden_news_alert(data), None))
        bot2_reports.append(("🏦 رادار السيولة المؤسساتية (Smart Money)", _build_institutional_liquidity_map(data), None))
        bot2_reports.append(("🌊 كاشف السيولة وأحجام العقود", _build_volume_contracts_tracker(data), None))
"""

target = "bot2_reports.append((\"[16/16] المستهدف الأسبوعي (الجمعة)\", _build_friday_target(data, True), None))"

if target in f_text:
    f_text = f_text.replace(target, target + append_block)
    with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_futures.py', 'w', encoding='utf-8') as f:
        f.write(f_text)
    print("Injected into bot_futures.py successfully!")
else:
    print("Could not find the injection point in bot_futures.py")

