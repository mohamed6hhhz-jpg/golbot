import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re
appends_b = re.findall(r'bot2_reports\.append\(', text)
appends_r = re.findall(r'raw_reports\.append\(', text)
print(f'Total bot2_reports: {len(appends_b)}')
print(f'Total raw_reports:  {len(appends_r)}')
print()

templates = [
    '_build_etf_flows_report',
    '_build_liquidity_time_targets',
    '_build_early_warning_alert',
    '_build_sudden_news_alert',
    '_build_volume_contracts_tracker',
    '_build_institutional_liquidity_map',
    '_build_scalping_weekly_monthly',
    '_build_spot_s14',
    '_build_spot_s15',
    '_build_spot_s16',
    '_build_friday_target',
]
for t in templates:
    ok = ('def ' + t) in text
    status = 'OK' if ok else 'MISSING'
    print(f'[{status}] {t}')
