import re

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

funcs_to_extract = [
    r'(def _build_spot_s14.*?return template.*?)(?=\ndef _)',
    r'(def _build_spot_s15.*?return template.*?)(?=\ndef _)',
    r'(def _build_spot_s16.*?return template.*?)(?=\ndef _)',
    r'(def _build_early_warning_alert.*?return template.*?)(?=\ndef _)',
    r'(def _build_sudden_news_alert.*?return template.*?)(?=\ndef _)',
    r'(def _build_institutional_liquidity_map.*?return template.*?)(?=\ndef _)',
    r'(def _build_volume_contracts_tracker.*?return template.*?)(?=\ndef _)'
]

extracted = []

# Special for fetch news
match_news = re.search(r'(def _fetch_breaking_news.*?(?=\ndef _))', text, re.DOTALL)
if match_news:
    extracted.append(match_news.group(1))
else:
    print("Failed to find fetch_news")

for pattern in funcs_to_extract:
    match = re.search(pattern, text, re.DOTALL)
    if match:
        extracted.append(match.group(1))
    else:
        print(f"Failed to find pattern: {pattern[:30]}...")

combined_code = "\n\n".join(extracted)
combined_code = combined_code.replace('def _build_spot_s14', 'def _build_futures_s14')
combined_code = combined_code.replace('def _build_spot_s15', 'def _build_futures_s15')
combined_code = combined_code.replace('def _build_spot_s16', 'def _build_futures_s16')
combined_code = combined_code.replace('Spot', 'Futures').replace('الفوري', 'الآجل')

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_futures.py', 'a', encoding='utf-8') as f:
    f.write('\n\n' + combined_code + '\n\n')

print(f"Extracted {len(extracted)} functions.")
