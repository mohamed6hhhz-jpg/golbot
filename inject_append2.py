with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_futures.py', 'r', encoding='utf-8') as f:
    text = f.read()

append_block = """        bot2_reports.append(("👑 مسار القمة والقاع (اتجاه السيولة)", _build_futures_s14(data), None))
        bot2_reports.append(("👑 الرادار المؤسساتي (كشف التلاعب والسيولة)", _build_futures_s15(data), None))
        bot2_reports.append(("👑 الخطة التكتيكية (Full Lot Strategy)", _build_futures_s16(data), None))
        bot2_reports.append(("⏰ تنبيه مبكر — انعكاس مرتقب", _build_early_warning_alert(data), None))
        bot2_reports.append(("🚨 رادار الأخبار العاجلة (Breaking News)", _build_sudden_news_alert(data), None))
        bot2_reports.append(("🏦 رادار السيولة المؤسساتية (Smart Money)", _build_institutional_liquidity_map(data), None))
        bot2_reports.append(("🌊 كاشف السيولة وأحجام العقود", _build_volume_contracts_tracker(data), None))"""

target = 'bot2_reports.append(("[16/16] المستهدف الأسبوعي (الجمعة)", _build_friday_target(data, True), None))'
if target in text:
    text = text.replace(target, target + "\n" + append_block)
    with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_futures.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Injected into bot2_reports successfully!")
else:
    print("Could not find the target string exactly.")
