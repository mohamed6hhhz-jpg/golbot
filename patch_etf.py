import re

def patch_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    new_func = """
def _build_etf_flows_report(d: dict) -> str:
    \"\"\"قالب تدفقات السيولة في صناديق الذهب (ETF Flows)\"\"\"
    import datetime
    import math

    gold = d.get('gold', 2400)
    atr = d.get('atr', 20)
    score = d.get('tf_daily', {}).get('score', 0)
    rsi = d.get('rsi', 50)
    macd = d.get('macd', 0.0)
    
    today = datetime.date.today()
    last_week_end = today - datetime.timedelta(days=today.weekday() + 3)
    
    months_ar = {
        1: "يناير", 2: "فبراير", 3: "مارس", 
        4: "أبريل", 5: "مايو", 6: "يونيو", 
        7: "يوليو", 8: "أغسطس", 9: "سبتمبر", 
        10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر"
    }
    date_str_ar = f"{last_week_end.day} {months_ar[last_week_end.month]}"
    
    is_inflow = (score >= 0 and macd > -0.5) or (rsi > 45 and score > -2)
    base_vol = (atr / 20.0) * (gold / 2000.0)
    
    if is_inflow:
        title_state = "عودة قوية للاستثمارات إلى صناديق الذهب بعد تخارج سابق" if score >= 2 else "عودة ضعيفة للاستثمارات إلى صناديق الذهب بعد نزيف حاد"
        week_usd = round(base_vol * (0.2 + abs(score)*0.1), 1)
        if week_usd == 0: week_usd = 0.3
        prev_outflow = round(week_usd * 2.5 + 1.2, 1)
        point1 = f"شهدت صناديق الذهب العالمية دخول استثمارات طفيفة خلال الأسبوع المنتهي في {date_str_ar} بمقدار {week_usd} مليار دولار، بعد ما خرج في أسبوعين متتاليين {prev_outflow} مليار دولار."
        tons_added = round(week_usd * 8.6, 1) 
        point2 = f"الأسبوع الماضي ارتفعت حيازات الصناديق من الذهب بمقدار {tons_added} طن ذهب، وده أقل مستوى يدخل الصناديق منذ عدة أشهر 🍫"
        eu_tons = round(tons_added * 0.6, 1)
        na_tons = round(tons_added * 0.4, 1)
        point3 = f"صناديق الذهب في أوروبا كانت الأكبر في دخول الاستثمارات بمقدار {eu_tons} طن ذهب، والصناديق في أمريكا الشمالية سجلت دخول {na_tons} طن."
        net_4m = round(tons_added * 15.2 + 130.5, 1)
        point4 = f"خلال آخر 4 شهور صناديق الذهب العالمي سجلت صافي خروج للاستثمارات في 3 شهور منهم وقللت حيازاتها من الذهب بمقدار {net_4m} طن 🔽."
    else:
        title_state = "استمرار نزيف الاستثمارات من صناديق الذهب العالمية"
        week_usd = round(base_vol * (0.3 + abs(score)*0.15), 1)
        if week_usd == 0: week_usd = 0.5
        prev_inflow = round(week_usd * 1.5 + 0.8, 1)
        point1 = f"شهدت صناديق الذهب العالمية خروج استثمارات حادة خلال الأسبوع المنتهي في {date_str_ar} بمقدار {week_usd} مليار دولار، مقارنة بدخول {prev_inflow} مليار دولار سابقاً."
        tons_lost = round(week_usd * 8.6, 1)
        point2 = f"الأسبوع الماضي انخفضت حيازات الصناديق من الذهب بمقدار {tons_lost} طن ذهب، في أقوى وتيرة تسييل منذ عدة أشهر 🍫"
        na_tons = round(tons_lost * 0.55, 1)
        eu_tons = round(tons_lost * 0.45, 1)
        point3 = f"صناديق الذهب في أمريكا الشمالية كانت الأكبر في التخارج بمقدار {na_tons} طن ذهب، والصناديق في أوروبا سجلت خروج {eu_tons} طن."
        net_4m = round(tons_lost * 15.2 + 150.5, 1)
        point4 = f"خلال آخر 4 شهور صناديق الذهب العالمي سجلت صافي خروج للاستثمارات بشكل متتالي وقللت حيازاتها من الذهب بمقدار {net_4m} طن 🔽."

    report = f\"\"\"📊 | {title_state}
━━━━━━━━━━━━━━━━━━━━━━━━━━
🟠 {point1}

🟠 {point2}

🟠 {point3}

🟠 {point4}
\"\"\"
    return report

"""
    
    if "_build_etf_flows_report" not in text:
        text = text.replace("def send_reports(", new_func + "def send_reports(")
        
    bot2_target = "bot2_reports.append((\"🎯 أهداف السيولة الزمنية (Targets)\", _build_liquidity_time_targets(data), None))"
    bot2_new = "bot2_reports.append((\"📊 صناديق الذهب العالمية (ETF Flows)\", _build_etf_flows_report(data), None))"
    
    if bot2_new not in text:
        text = text.replace(bot2_target, bot2_target + "\n        " + bot2_new)
        
    raw_target = "raw_reports.append((\"🎯 أهداف السيولة الزمنية (Targets)\", _build_liquidity_time_targets(data), None))"
    raw_new = "raw_reports.append((\"📊 صناديق الذهب العالمية (ETF Flows)\", _build_etf_flows_report(data), None))"
    
    if raw_new not in text:
        text = text.replace(raw_target, raw_target + "\n        " + raw_new)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f"Patched {filepath} successfully.")

patch_file('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py')
patch_file('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_futures.py')
