import re

def fix_pd(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add import pandas as pd inside the try block just in case
    new_content = content.replace("h = gold_5m.copy()\n            # التعامل مع MultiIndex", "h = gold_5m.copy()\n            import pandas as pd\n            # التعامل مع MultiIndex")
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(new_content)

fix_pd('Goldbot/bot_spot.py')
fix_pd('Goldbot/bot_futures.py')
