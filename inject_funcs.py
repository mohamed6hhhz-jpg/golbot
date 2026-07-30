with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/temp_s9.py', 'r', encoding='utf-8') as f:
    s9_code = f.read()
    
with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/temp_s12.py', 'r', encoding='utf-8') as f:
    s12_code = f.read()

s9_code = s9_code.replace('def _build_spot_s9(', 'def _build_futures_s9(')
s12_code = s12_code.replace('def _build_spot_s12(', 'def _build_futures_s12(')

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_futures.py', 'a', encoding='utf-8') as f:
    f.write('\n\n' + s9_code + '\n\n' + s12_code + '\n\n')

print("Functions injected into bot_futures.py successfully!")
