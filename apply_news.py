import re

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

new_logic = """
def _fetch_breaking_news() -> str:
    \"\"\"جلب آخر الأخبار العاجلة من ForexLive\"\"\"
    try:
        import requests
        import xml.etree.ElementTree as ET
        import re
        r = requests.get('https://www.forexlive.com/feed/news', timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            items = root.findall('.//item')
            news_list = []
            for item in items[:5]:
                title = item.find('title').text if item.find('title') is not None else ""
                desc = item.find('description').text if item.find('description') is not None else ""
                desc = re.sub(r'<[^>]+>', '', desc).strip()
                news_list.append(f"Title: {title}\\nDetails: {desc}")
            return "\\n\\n".join(news_list)
    except Exception as e:
        log.warning(f"⚠️ فشل جلب الأخبار العاجلة: {e}")
    return ""

def _build_sudden_news_alert(data: dict) -> str:
    \"\"\"القالب الجديد: رادار الأخبار العاجلة باستخدام الذكاء الاصطناعي\"\"\"
    news_text = _fetch_breaking_news()
    if not news_text or len(news_text) < 10:
        return "🚨 **رادار الأخبار العاجلة (Breaking News)** 🚨\\n━━━━━━━━━━━━━━━━━━━━━━━━━━\\nلا توجد أخبار عاجلة أو مؤثرة حالياً. السوق يتحرك بناءً على السيولة التقنية."
    
    prompt = f\"\"\"أنت خبير اقتصادي مختص في الذهب.
إليك آخر 5 أخبار عاجلة من السوق:
{news_text}

المطلوب:
1. اختر أهم خبر واحد فقط يؤثر بقوة على "الذهب والدولار".
2. إذا لم يكن هناك خبر مؤثر جداً، قل "لا توجد أحداث مؤثرة بشدة".
3. إذا وجدت خبراً مؤثراً، قم بصياغته بدقة باللغة العربية داخل هذا القالب بالضبط:

🚨 **رادار الأخبار العاجلة (Breaking News)** 🚨
━━━━━━━━━━━━━━━━━━━━━━━━━━
📰 **الخبر المؤثر:** 
[عنوان الخبر وتفاصيله المترجمة بدقة واحترافية]

🔥 **درجة التأثير:** [عالية جداً / متوسطة]
📈 **التوجه المتوقع للذهب:** [صعودي 🟢 / هبوطي 🔴 / تذبذب 🟡]

💡 **التحليل الأساسي السريع:**
[جملة واحدة قوية تشرح لماذا هذا الخبر يرفع/يهبط بالذهب]
━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ *تنويه: وقت الأخبار العاجلة يُفضل الالتزام الصارم بإدارة المخاطر وتوسيع الوقف.*

قواعد صارمة:
- لا تضف أي نص خارج القالب.
- لا تضف مقدمات.
- حافظ على دقة الترجمة والمصطلحات الاقتصادية.\"\"\"

    import time
    for model_name in GROQ_MODELS:
        try:
            log.info(f"🤖 جاري توليد (رادار الأخبار العاجلة) عبر {model_name}...")
            resp = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": MASTER_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                model=model_name,
                temperature=0.2,
                max_tokens=500,
            )
            content = resp.choices[0].message.content.strip()
            if "رادار الأخبار العاجلة" in content:
                return content
            return "🚨 **رادار الأخبار العاجلة (Breaking News)** 🚨\\n━━━━━━━━━━━━━━━━━━━━━━━━━━\\nلا توجد أخبار عاجلة أو مؤثرة حالياً. السوق يتحرك بناءً على السيولة التقنية."
        except Exception as e:
            log.warning(f"⚠️ [{model_name}] فشل في توليد رادار الأخبار: {e}")
            time.sleep(2)
            continue
            
    return "🚨 **رادار الأخبار العاجلة (Breaking News)** 🚨\\n━━━━━━━━━━━━━━━━━━━━━━━━━━\\nلا توجد أخبار عاجلة أو مؤثرة حالياً. السوق يتحرك بناءً على السيولة التقنية."

def send_reports(data: dict, report_text: str, prefix: str = ""):"""

text = text.replace('def send_reports(data: dict, report_text: str, prefix: str = ""):', new_logic)

# Now inject it into the bot2_reports array
old_reports_block = """        bot2_reports.append(("👑 الخطة التكتيكية (Full Lot Strategy)", _build_spot_s16(data), None))
        bot2_reports.append(("⏰ تنبيه مبكر — انعكاس مرتقب", _build_early_warning_alert(data), None))"""
new_reports_block = old_reports_block + """
        bot2_reports.append(("🚨 رادار الأخبار العاجلة (Breaking News)", _build_sudden_news_alert(data), None))"""
text = text.replace(old_reports_block, new_reports_block)

# And inject it into the raw_reports array
old_raw_block = """        raw_reports.append(("👑 الخطة التكتيكية (Full Lot Strategy)", _build_spot_s16(data), None))
        raw_reports.append(("⏰ تنبيه مبكر — انعكاس مرتقب", _build_early_warning_alert(data), None))"""
new_raw_block = old_raw_block + """
        raw_reports.append(("🚨 رادار الأخبار العاجلة (Breaking News)", _build_sudden_news_alert(data), None))"""
text = text.replace(old_raw_block, new_raw_block)

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Applied News alert!")
