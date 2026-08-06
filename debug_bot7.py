from Goldbot.bot_spot import get_full_market_data
from Goldbot.bot_7 import process_and_send_bot7

print("Starting diagnostics for bot 7...")
try:
    d = get_full_market_data(mode='spot')
    print("Market data fetched successfully.")
    
    reports = process_and_send_bot7(d)
    print(f"process_and_send_bot7 returned {len(reports)} reports.")
    for title, content in reports:
        print(f"Title: {title}")
except Exception as e:
    import traceback
    traceback.print_exc()
print("Done.")
