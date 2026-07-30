import re
with open('Goldbot/bot_futures.py', 'r', encoding='utf-8') as f:
    content = f.read()

if '16/16' not in content:
    content = re.sub(
        r'(bot2_reports\.append.*?\s+s9_report.*?\n)',
        r'\1            bot2_reports.append(("[16/16] المستهدف الأسبوعي (الجمعة)", _build_friday_target(data, True), None))\n',
        content
    )
    with open('Goldbot/bot_futures.py', 'w', encoding='utf-8') as f:
        f.write(content)
