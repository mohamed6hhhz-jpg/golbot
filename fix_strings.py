with open("c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
# Find all occurrences of a quote that end the string prematurely due to literal newlines.
# E.g.: "Text
# "
# We want: "Text\n"
text = re.sub(r'([^\n])\n\s*"', r'\1\\n"\n        "', text)
text = re.sub(r'fib_lines = "\n"\.join\(', r'fib_lines = "\\n".join(', text)

with open("c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py", "w", encoding="utf-8") as f:
    f.write(text)
