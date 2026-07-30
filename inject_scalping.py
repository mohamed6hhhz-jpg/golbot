with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Add to bot2_reports after ETF
old = '        bot2_reports.append(("\U0001f4ca \u0635\u0646\u0627\u062f\u064a\u0642 \u0627\u0644\u0630\u0647\u0628 \u0627\u0644\u0639\u0627\u0644\u0645\u064a\u0629 (ETF Flows)", _build_etf_flows_report(data), None))'
new = old + '\n        bot2_reports.append(("\U0001f4c5 \u0645\u0635\u0641\u0648\u0641\u0629 \u0627\u0644\u0633\u0643\u0627\u0644\u0628\u064a\u0646\u062c \u0627\u0644\u0634\u0627\u0645\u0644\u0629 (\u064a\u0648\u0645\u064a/\u0623\u0633\u0628\u0648\u0639\u064a/\u0634\u0647\u0631\u064a)", _build_scalping_weekly_monthly(data), None))'

if old in text:
    text = text.replace(old, new)
    print('bot2_reports: OK')
else:
    print('bot2_reports: NOT FOUND')

# Add to raw_reports after ETF
old2 = '        raw_reports.append(("\U0001f4ca \u0635\u0646\u0627\u062f\u064a\u0642 \u0627\u0644\u0630\u0647\u0628 \u0627\u0644\u0639\u0627\u0644\u0645\u064a\u0629 (ETF Flows)", _build_etf_flows_report(data), None))'
new2 = old2 + '\n        raw_reports.append(("\U0001f4c5 \u0645\u0635\u0641\u0648\u0641\u0629 \u0627\u0644\u0633\u0643\u0627\u0644\u0628\u064a\u0646\u062c \u0627\u0644\u0634\u0627\u0645\u0644\u0629 (\u064a\u0648\u0645\u064a/\u0623\u0633\u0628\u0648\u0639\u064a/\u0634\u0647\u0631\u064a)", _build_scalping_weekly_monthly(data), None))'

if old2 in text:
    text = text.replace(old2, new2)
    print('raw_reports: OK')
else:
    print('raw_reports: NOT FOUND')

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Done!')
