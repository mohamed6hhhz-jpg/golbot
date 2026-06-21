import sys

def patch_send_reports(filename, market_label):
    with open(filename, 'r', encoding='utf-8') as f:
        code = f.read()

    # Change the header of every chunk
    old_header = 'final_text = f"{prefix}[{i}/{total}] 👑 التقرير الكمي الشامل للذهب\\n{subtitle}\\n\\n{chunk}"'
    new_header = f'final_text = f"{{prefix}}[{{i}}/{{total}}] 👑 التقرير الكمي الشامل للذهب ({market_label})\\n{{subtitle}}\\n\\n{{chunk}}"'
    
    code = code.replace(old_header, new_header)

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(code)

patch_send_reports('bot_futures.py', 'الآجل - Futures')
patch_send_reports('bot_spot.py', 'الفوري - Spot')
print('Patched headers')
