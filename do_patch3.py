with open('c:/Users/lenovo/Desktop/alltoools/new_templates.txt', 'r', encoding='utf-8') as f:
    new_text = f.read()

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    content = f.read()

import re
# Use lambda m: new_text so re.sub does NOT evaluate backslashes in new_text!
regex = r"def _build_spot_s1\(d: dict\) -> str:.*?def _build_spot_s4\(d: dict\) -> str:"
new_content = re.sub(regex, lambda m: new_text + "\n\ndef _build_spot_s4(d: dict) -> str:", content, flags=re.DOTALL)

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
