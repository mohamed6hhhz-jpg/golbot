import yfinance as yf
from groq import Groq
import requests
from datetime import datetime
import time
import os

# ================= الإعدادات الآمنة والنهائية =================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") 
TELEGRAM_BOT_TOKEN = "8678714877:AAE2v6jeeYzsNFYj_83rXK32RJEA7fszQew"
TELEGRAM_CHAT_ID = "7737655407"

# إعدادات مؤسسية تحافظ على الباقة وتضمن استقرار النظام
ALERT_THRESHOLD = 8.0 
ROUTINE_MINUTES = 60  
# ==========================================================

def get_groq_client():
    if not GROQ_API_KEY:
        print("❌ خطأ: لم يتم العثور على GROQ_API_KEY")
        return None
    return Groq(api_key=GROQ_API_KEY)

def get_market_data():
    try:
        # تم التعديل إلى 5 أيام لتجنب أخطاء أيام الإجازات وإغلاق الأسواق
        gold = yf.Ticker("GC=F").history(period="5d")['Close'].iloc[-1]
        dxy = yf.Ticker("DX-Y.NYB").history(period="5d")['Close'].iloc[-1]
        tnx = yf.Ticker("^TNX").history(period="5d")['Close'].iloc[-1]
        return gold, dxy, tnx
    except IndexError:
        print("السوق مغلق أو لا توجد بيانات كافية.")
        return None, None, None
    except Exception as e:
        print(f"حدث خطأ أثناء سحب البيانات: {e}")
        return None, None, None

def generate_report(gold, dxy, tnx, is_alert=False, price_diff=0.0):
    client = get_groq_client()
    if not client:
        return None

    date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_type = "[تنبيه استثنائي عاجل لحركة سعرية متوقعة]" if is_alert else "[تقرير استباقي للاتجاهات القادمة]"
    alert_text = f"مقدار التغير المفاجئ الحالي: {round(price_diff, 2)} دولار" if is_alert else ""

    prompt_lines = [
        "أنت خبير مالي محترف. مهمتك هي كتابة 'تقرير استباقي وتوقعي' لحركة الذهب (XAU/USD).",
        f"البيانات اللحظية الحالية المستلمة في ({date_now}):",
        f"- السعر الحالي للذهب الفوري: {gold:.2f} دولار.",
        f"- مؤشر الدولار (DXY): {dxy:.2f}.",
        f"- عوائد السندات (US10Y): {tnx:.2f}%.",
        "",
        f"نوع التقرير المطلوب: {report_type}",
        alert_text,
        "",
        "المطلوب منك كتابة تحليل مالي استباقي باللغة العربية البسيطة جداً والمباشرة، مع الالتزام الصارم بالآتي:",
        "1. النظرة المستقبلية: سطرين بحد أقصى عن الاتجاه القادم المتوقع بناءً على المعطيات الحالية.",
        "2. الأرقام المحورية: حدد 3 أرقام فقط بوضوح (نقطة الدعم القادمة، المقاومة القادمة، والنقطة المحورية لليوم).",
        "3. شجرة السيناريوهات (للمستثمر الفعلي الذي يشتري الذهب المادي ويستلمه يداً بيد):",
        "📈 السيناريو الإيجابي: 'إذا كسر الذهب سعر [رقم المقاومة]، فالمحطة القادمة ستكون [رقم الهدف].'",
        "📉 السيناريو السلبي: 'إذا كسر الذهب سعر [رقم الدعم]، فقد ينزلق إلى [رقم الهدف السفلي].'",
        "4. البساطة والتركيز: ممنوع تماماً سرد أحداث الماضي أو الأخبار القديمة. ركز فقط على 'ماذا سيحدث تالياً'. تجنب المصطلحات المعقدة ليكون مفهوماً لغير المتخصصين.",
        "5. إخلاء مسؤولية ثابت ومختصر في النهاية:",
        "⚠️ إخلاء مسؤولية: هذا التحليل لتوضيح المسارات المتوقعة رياضياً بناءً على تقاطعات السوق، وليس توصية مباشرة بالبيع أو الشراء."
    ]
    prompt = "\n".join(prompt_lines)

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "أنت خبير مالي استراتيجي يكتب بلغة مبسطة."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.2, 
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"⚠️ تنبيه صامت: تم الوصول للحد الأقصى أو حدث خطأ بالسيرفر: {e}")
        return None

def send_to_telegram(message):
    protocol = "https://"
    domain = "api.telegram.org"
    url = f"{protocol}{domain}/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] تم إرسال التقرير بنجاح لتليجرام.")
    except Exception as e:
        print(f"خطأ في الإرسال لتليجرام: {e}")

def run_bot():
    print("البوت بدأ العمل بنظام المراقبة المؤسسي الآمن...")
    last_gold_price = None
    minutes_counter = 0
    
    while True:
        current_gold, current_dxy, current_tnx = get_market_data()
        if current_gold and current_dxy and current_tnx:
            if last_gold_price is None:
                print("إرسال التقرير الافتتاحي الأول...")
                last_gold_price = current_gold
                report = generate_report(current_gold, current_dxy, current_tnx, is_alert=False)
                if report:
                    send_to_telegram(report)
                minutes_counter = 0
            
            price_difference = current_gold - last_gold_price
            if abs(price_difference) >= ALERT_THRESHOLD:
                print(f"🚨 استثناء عاجل! تحرك السعر بمقدار {price_difference:.2f} دولار. جاري التحديث...")
                report = generate_report(current_gold, current_dxy, current_tnx, is_alert=True, price_diff=price_difference)
                if report:
                    send_to_telegram(report)
                    last_gold_price = current_gold 
                    minutes_counter = 0 
            
            elif minutes_counter >= ROUTINE_MINUTES:
                print(f"مرت {ROUTINE_MINUTES} دقيقة.. إرسال التقرير الروتيني المحدث...")
                report = generate_report(current_gold, current_dxy, current_tnx, is_alert=False)
                if report:
                    send_to_telegram(report)
                    last_gold_price = current_gold 
                    minutes_counter = 0 
        else:
            print("لم يتم العثور على بيانات في هذه الدورة. سيتم المحاولة مجدداً.")
            
        time.sleep(60)
        minutes_counter += 1

# Note: run_bot() is called by the root main.py orchestrator as a background thread.
# The __main__ block is intentionally removed to avoid conflicts with FastAPI.