import yfinance as yf
from groq import Groq
import requests
from datetime import datetime
import time
import os

# ================= الإعدادات =================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "7737655407")
ALERT_THRESHOLD = 5.0 
# ============================================

client = Groq(api_key=GROQ_API_KEY)

def get_market_data():
    try:
        gold = yf.Ticker("GC=F").history(period="1d")['Close'].iloc[-1]
        dxy = yf.Ticker("DX-Y.NYB").history(period="1d")['Close'].iloc[-1]
        tnx = yf.Ticker("^TNX").history(period="1d")['Close'].iloc[-1]
        return gold, dxy, tnx
    except Exception as e:
        print(f"حدث خطأ أثناء سحب البيانات: {e}")
        return None, None, None

def generate_report(gold, dxy, tnx, is_alert=False, price_diff=0.0):
    date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prompt = f"""
    أنت كبير المحللين الاقتصاديين ورئيس قسم أبحاث السلع في بنك استثماري دولي.
    البيانات اللحظية الحالية المستلمة في ({date_now}):
    - السعر الحالي للذهب الفوري (XAU/USD): {gold:.2f} دولار.
    - مؤشر الدولار الأمريكي (DXY): {dxy:.2f} نقاط.
    - عوائد خزانة الولايات المتحدة لأجل 10 سنوات (US10Y): {tnx:.2f}%

    نوع التقرير المطلوب: {"[تنبيه استثنائي عاجل لحركة سعرية مفاجئة]" if is_alert else "[تقرير روتيني مفصل ومدروس]"}
    {"مقدار التغير المفاجئ المكتشف: " + str(round(price_diff, 2)) + " دولار" if is_alert else ""}

    المطلوب منك صياغة تحليل مالي متعمق ومؤسسي (باللغة العربية الفصحى فقط)، مع الالتزام الصارم بالآتي:
    1. التحليل المالي: اشرح حركة الذهب بناءً على "قانون الارتباط العكسي الرياضي" مع مؤشر DXY، وتأثير "تكلفة الفرصة البديلة المستندة إلى عوائد السندات".
    2. الأرقام والمستويات: حدد الدعوم والمقاومات اللحظية القريبة بناءً على النطاق السعري الفعلي لليوم (بفارق يتراوح بين 10 إلى 30 دولار).
    3. البلاغة وعدم التكرار: يُمنع التكرار اللفظي (مثل تكرار جملة "نلاحظ أن"). استخدم مفردات مالية متنوعة واجعل الصياغة طبيعية واحترافية.
    4. السيناريوهات للمستثمر الفيزيكال: صغ سيناريوهات واضحة للمستثمرين الذين يشترون الذهب الفعلي (فيزيكال) بأسعار الشاشة اللحظية ويستلمونه يداً بيد.
    5. شجرة السيناريوهات: يُمنع تماماً استخدام أي أكواد برمجية (مثل Mermaid). بدلاً من ذلك، ارسم في نهاية التقرير "شجرة سيناريوهات نصية" أنيقة ومنسقة تناسب العرض على شاشة تطبيق تليجرام. استخدم الرموز والأسهم لتوضيح مسار السعر هكذا:
    📈 سيناريو الصعود: [الشرح والهدف 🎯]
    📉 سيناريو الهبوط: [الشرح والهدف 🎯]
    
    6. إخلاء المسؤولية الإلزامي: يجب أن تضيف النص التالي حرفياً في نهاية التقرير تماماً وتفصله بسطر فارغ:
    "⚠️ إخلاء مسؤولية: الأسعار الواردة في هذا التقرير هي أسعار حقيقية ومباشرة من الأسواق العالمية لحظة إصداره. أما التحليلات، والدعوم، والمقاومات، والسيناريوهات فهي نتاج خوارزميات ذكاء اصطناعي (AI) تُبنى على الاحتمالات الاقتصادية، وتُقدم كأداة مساعدة لمتخذي القرار وليست توصية مالية حتمية."
    """
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "أنت محلل مالي أكاديمي صارم تستخدم المعادلات والقوانين الاقتصادية لتحليل الأسواق وتلتزم ببنود التقارير بدقة."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.2, 
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"خطأ في توليد التقرير: {e}")
        return "حدث خطأ أثناء إعداد التحليل المالي."

def send_to_telegram(message):
    protocol = "https://"
    domain = "api.telegram.org"
    url = f"{protocol}{domain}/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    
    for attempt in range(3):
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] تم إرسال التقرير بنجاح لتليجرام.")
            return
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
            else:
                print("⚠️ Telegram API network hiccup: Could not send message after 3 attempts.")

def run_bot():
    print("البوت بدأ العمل بنظام المراقبة اللحظية والروتينية...")
    last_gold_price = None
    minutes_counter = 0
    
    while True:
        current_gold, current_dxy, current_tnx = get_market_data()
        if current_gold and current_dxy and current_tnx:
            if last_gold_price is None:
                last_gold_price = current_gold
                report = generate_report(current_gold, current_dxy, current_tnx, is_alert=False)
                send_to_telegram(report)
                minutes_counter = 0
            
            price_difference = current_gold - last_gold_price
            if abs(price_difference) >= ALERT_THRESHOLD:
                report = generate_report(current_gold, current_dxy, current_tnx, is_alert=True, price_diff=price_difference)
                send_to_telegram(report)
                last_gold_price = current_gold 
                minutes_counter = 0 
            
            elif minutes_counter >= 15:
                report = generate_report(current_gold, current_dxy, current_tnx, is_alert=False)
                send_to_telegram(report)
                last_gold_price = current_gold 
                minutes_counter = 0 
        time.sleep(60)
        minutes_counter += 1
