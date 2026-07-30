with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Let's find the end of raw_reports building. 
# raw_reports is built from _split_fixed_report and T0-T5, then T6, then flat_chunks.
# Actually, the user's `raw_reports` is just the first section.
# I'll just append it before `flat_chunks = []`.

target = "        flat_chunks = []\n"
repl = "        raw_reports.append((\"👑 مسار القمة والقاع (اتجاه السيولة)\", _build_spot_s14(data), None))\n        flat_chunks = []\n"

if target in text:
    text = text.replace(target, repl)
    with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Patched raw_reports')
else:
    print('Could not find flat_chunks = []')
