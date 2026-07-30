import requests
import xml.etree.ElementTree as ET
import re

r = requests.get('https://www.forexlive.com/feed/news', timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
root = ET.fromstring(r.content)
items = root.findall('.//item')
news_list = []
for item in items[:5]:
    title = item.find('title').text if item.find('title') is not None else ''
    desc = item.find('description').text if item.find('description') is not None else ''
    desc = re.sub(r'<[^>]+>', '', desc).strip()
    news_list.append(f'Title: {title}\nDetails: {desc}')
news_text = '\n\n'.join(news_list)

import sys
sys.path.append('c:/Users/lenovo/Desktop/alltoools/Goldbot')
from bot_spot import GROQ_KEYS, GROQ_MODELS
import random
from groq import Groq

client = Groq(api_key=random.choice(GROQ_KEYS))
prompt = f\"\"\"أنت خبير اقتصادي مختص في الذهب.
إليك آخر 5 أخبار عاجلة من السوق:
{news_text}

المطلوب:
1. اختر أهم خبر واحد يؤثر على السوق وقم بصياغته. لا تقل أبدا أنه لا يوجد خبر مؤثر.
2. قم بصياغته بدقة باللغة العربية داخل هذا القالب بالضبط:

🚨 **رادار الأخبار العاجلة (Breaking News)** 🚨
━━━━━━━━━━━━━━━━━━━━━━━━━━
📰 **الخبر المؤثر:** 
[عنوان الخبر وتفاصيله المترجمة بدقة واحترافية]

🔥 **درجة التأثير:** [عالية جداً / متوسطة]
📈 **التوجه المتوقع للذهب:** [صعودي 🟢 / هبوطي 🔴 / تذبذب 🟡]
\"\"\"
try:
    resp = client.chat.completions.create(
        messages=[{'role': 'user', 'content': prompt}],
        model=random.choice(GROQ_MODELS),
        temperature=0.3,
        max_tokens=600
    )
    ans = resp.choices[0].message.content.strip()
    with open('news_test.txt', 'w', encoding='utf-8') as f:
        f.write(ans)
    print('Groq returned successfully')
except Exception as e:
    print('Groq error:', e)
