import re

def fix_typo(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # We need to change {tnx:.2f}% to {twy:.2f}% or whatever holds the 2Y value.
    # In `bot_spot.py`, `_build_spot_s10`, the 2Y value is `twy`? 
    # Wait, in `bot_spot.py`, `tnx` is 10-year yield, `twy` is 2-year yield? No, `twy` is Two Year Yield?
    # Let's check:
    # tnx = float(d.get('tnx_val', 0) or 0) or round(interest - 0.3, 2)
    # twy = float(d.get('twy_val', 0) or 0) or round(interest + 0.3, 2)
    # Yes, twy = 2-year yield.
    # So the string `2Y/{tnx:.2f}%` should be `2Y/{twy:.2f}%`.

    if '2Y/{tnx' in content:
        content = content.replace('2Y/{tnx', '2Y/{twy')
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed typo in {filename}")

fix_typo('Goldbot/bot_spot.py')
fix_typo('Goldbot/bot_futures.py')
