import re

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

match = re.search(r'(def _build_volume_contracts_tracker.*)', text, re.DOTALL)
if match:
    code = match.group(1)
    with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_futures.py', 'a', encoding='utf-8') as f:
        f.write('\n\n' + code + '\n\n')
    print("Appended volume contracts tracker")
else:
    print("Still failed to find volume contracts tracker")
