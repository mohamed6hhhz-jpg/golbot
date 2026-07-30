import re

def fix_bot_futures_t1(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    content = re.sub(
        r'(\{zone_color\}) (\{zone_name\}): (\{exact_zone\}\$)',
        r'\1 مستوى المراقبة (\2): \3',
        content
    )

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

fix_bot_futures_t1('Goldbot/bot_futures.py')
