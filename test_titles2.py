import re

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

# find all raw_reports.append
count = 1
with open('titles.txt', 'w', encoding='utf-8') as f_out:
    for line in text.split('\n'):
        if 'raw_reports.append' in line and not line.strip().startswith('#'):
            match = re.search(r'\(\"(.*?)\"', line)
            if match:
                f_out.write(f"{count}/26: {match.group(1)}\n")
                count += 1
