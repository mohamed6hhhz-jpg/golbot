import re

file_path = "Goldbot/bot_spot.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

target_str = """        _td_r = requests.get(f"https://api.twelvedata.com/price?symbol=XAU/USD&apikey={TWELVEDATA_API_KEY}", timeout=4)"""
replacement_str = """        # Fetch complete quote for accurate daily high/low
        try:
            _td_quote = requests.get(f"https://api.twelvedata.com/quote?symbol=XAU/USD&apikey={TWELVEDATA_API_KEY}", timeout=4)
            twelve_high = None
            twelve_low = None
            if _td_quote.status_code == 200:
                _q_json = _td_quote.json()
                if 'high' in _q_json and 'low' in _q_json:
                    twelve_high = float(_q_json['high'])
                    twelve_low = float(_q_json['low'])
        except Exception as e:
            log.warning(f"Failed to fetch quote from TwelveData: {e}")
            twelve_high, twelve_low = None, None

        _td_r = requests.get(f"https://api.twelvedata.com/price?symbol=XAU/USD&apikey={TWELVEDATA_API_KEY}", timeout=4)"""

if target_str in content:
    content = content.replace(target_str, replacement_str)

target_str_2 = """    daily_high = round(float(gold_daily['High'].iloc[-1]), 2) if gold_daily is not None else gold
    daily_low = round(float(gold_daily['Low'].iloc[-1]), 2) if gold_daily is not None else gold"""

replacement_str_2 = """    daily_high = round(float(gold_daily['High'].iloc[-1]), 2) if gold_daily is not None else gold
    daily_low = round(float(gold_daily['Low'].iloc[-1]), 2) if gold_daily is not None else gold

    # Override with accurate spot high/low if fetched from TwelveData
    if mode == "spot" and 'twelve_high' in locals() and twelve_high and twelve_low:
        daily_high = round(twelve_high, 2)
        daily_low = round(twelve_low, 2)"""

if target_str_2 in content:
    content = content.replace(target_str_2, replacement_str_2)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Fixed High/Low in bot_spot.py!")
