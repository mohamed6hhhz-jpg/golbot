import re

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

# find all raw_reports.append
count = 1
for line in text.split('\n'):
    if 'raw_reports.append' in line and not line.strip().startswith('#'):
        match = re.search(r'\(\"(.*?)\"', line)
        if match:
            print(f"{count}/26: {match.group(1)}")
            count += 1
