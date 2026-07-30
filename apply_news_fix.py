import re

new_func = """def _build_sudden_news_alert(data: dict) -> str:
    \"\"\"القالب الجديد: رادار الأخبار العاجلة باستخدام الذكاء الاصطناعي\"\"\"
    news_text = _fetch_breaking_news()
    if not news_text or len(news_text) < 10:
        return "🚨 **رادار الأخبار العاجلة (Breaking News)** 🚨\\n━━━━━━━━━━━━━━━━━━━━━━━━━━\\nلا توجد تحديثات إخبارية حالياً. السوق يتحرك بناءً على السيولة التقنية."
    
    prompt = f\"\"\"أنت خبير اقتصادي مختص في الذهب.
إليك آخر 5 أخبار عاجلة من السوق:
{news_text}

المطلوب:
1. اختر أهم خبر من هذه الأخبار الخمسة مهما كان تأثيره (حتى لو كان متوسطاً أو ضعيفاً).
2. إياك أن تقول 'لا توجد أحداث مؤثرة'، بل صغ أهم ما جاء في الأخبار.
3. قم بصياغة الخبر بدقة باللغة العربية داخل هذا القالب بالضبط ولا تضف أي ديباجة:

🚨 **رادار الأخبار العاجلة (Breaking News)** 🚨
━━━━━━━━━━━━━━━━━━━━━━━━━━
📰 **الخبر البارز:** 
[عنوان الخبر وتفاصيله المترجمة بدقة واحترافية]

🔥 **درجة التأثير:** [عالية جداً / متوسطة / ضعيفة]
📈 **التوجه المتوقع للذهب بناءً على الخبر:** [صعودي 🟢 / هبوطي 🔴 / تذبذب 🟡]
\"\"\"
    try:
        from groq import Groq
        import random
    except:
        pass
    client = Groq(api_key=random.choice(GROQ_KEYS)) if GROQ_KEYS else None
    if client:
        try:
            resp = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=random.choice(GROQ_MODELS),
                temperature=0.3,
                max_tokens=600
            )
            ans = resp.choices[0].message.content.strip()
            return ans
        except Exception as e:
            pass
    return "🚨 **رادار الأخبار العاجلة (Breaking News)** 🚨\\n━━━━━━━━━━━━━━━━━━━━━━━━━━\\nلا توجد تحديثات إخبارية حالياً. السوق يتحرك بناءً على السيولة التقنية."
"""

for filepath in ['c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_futures.py']:
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # We find the existing function using regex from 'def _build_sudden_news_alert' to 'return "...السيولة التقنية."'
    # Since the string varies slightly, we can match until we hit the next 'def ' or end of file.
    pattern = r'def _build_sudden_news_alert\(data: dict\) -> str:.*?(?=\ndef [a-zA-Z_]|$)'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        text = text[:match.start()] + new_func + text[match.end():]
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"Replaced in {filepath} successfully")
    else:
        print(f"Failed to find target in {filepath}")

