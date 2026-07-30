with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_futures.py', 'r', encoding='utf-8') as f:
    text = f.read()

append_block = """
        raw_reports.append(("👑 مسار القمة والقاع (اتجاه السيولة)", _build_futures_s14(data), None))
        raw_reports.append(("👑 الرادار المؤسساتي (كشف التلاعب والسيولة)", _build_futures_s15(data), None))
        raw_reports.append(("👑 الخطة التكتيكية (Full Lot Strategy)", _build_futures_s16(data), None))
        raw_reports.append(("⏰ تنبيه مبكر — انعكاس مرتقب", _build_early_warning_alert(data), None))
        raw_reports.append(("🚨 رادار الأخبار العاجلة (Breaking News)", _build_sudden_news_alert(data), None))
        raw_reports.append(("🏦 رادار السيولة المؤسساتية (Smart Money)", _build_institutional_liquidity_map(data), None))
        raw_reports.append(("🌊 كاشف السيولة وأحجام العقود", _build_volume_contracts_tracker(data), None))"""

# find a good spot in raw_reports, maybe near where s12_report is added
target = 'raw_reports.append(("👑 مصفوفة التداول السريعة (الآجل - Futures)", s9_report, None))'
if target in text:
    text = text.replace(target, target + "\n" + append_block)
    with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_futures.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Injected into raw_reports successfully!")
else:
    print("Could not find the target string exactly.")
