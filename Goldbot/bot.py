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

    # ── حساب المستويات المحورية الكمية مسبقاً لتغذية النموذج بمنطق رياضي مباشر ──
    pivot   = round((gold * 1.0 + dxy * 0.3 + tnx * 2.0) / 3.0 * (gold / (gold + 1)), 2)
    pivot   = round(gold, 2)           # النقطة المحورية = السعر الحالي كمرجع
    r1      = round(gold + (gold * 0.004), 2)   # مقاومة أولى ~0.4%
    r2      = round(gold + (gold * 0.009), 2)   # مقاومة ثانية ~0.9%
    s1      = round(gold - (gold * 0.004), 2)   # دعم أول ~0.4%
    s2      = round(gold - (gold * 0.009), 2)   # دعم ثاني ~0.9%

    # ── قراءة العلاقة بين المتغيرات لتحديد التحيز السائد ──
    dxy_bias  = "قوي" if dxy > 104 else ("محايد" if dxy > 101 else "ضعيف")
    bond_bias = "مرتفعة" if tnx > 4.3 else ("معتدلة" if tnx > 3.8 else "منخفضة")
    gold_pressure = "ضغط هبوطي" if (dxy > 104 or tnx > 4.5) else "زخم صعودي"

    report_header = (
        "🚨 [تنبيه سعري استثنائي — حركة حادة مرصودة الآن]"
        if is_alert else
        "📊 [نشرة التحليل الكمي الاستباقي للذهب]"
    )
    alert_block = (
        f"\n🔔 الحركة المرصودة: {'+' if price_diff > 0 else ''}{price_diff:.2f}$ في هذه الدورة.\n"
        if is_alert else ""
    )

    system_prompt = """أنت كبير المحللين الكميين (Quantitative Analyst) في مؤسسة استثمارية عالمية من الدرجة الأولى.
مهمتك كتابة تقارير استباقية تحليلية عن الذهب (XAU/USD)، وفق معايير بنوك الاستثمار الكبرى (Goldman Sachs, JPMorgan).
قواعد صارمة لا تُكسر أبداً:
- اكتب بالعربية الفصحى البسيطة فقط. لا كلمات إنجليزية داخل التحليل نهائياً.
- اشرح المفاهيم المالية المعقدة بأمثلة حياتية مبسطة وصور ذهنية واضحة.
- لا تعيد ذكر الماضي ولا تسرد أخباراً. كل كلمة يجب أن تخدم السؤال: "ماذا سيحدث تالياً؟".
- التقرير يُقرأ على شاشة هاتف — استخدم الفقرات القصيرة والمسافات البيضاء والرموز بذكاء.
- المنطق الكمي يجب أن يكون ظاهراً وواضحاً لكن بلغة يفهمها رجل الشارع."""

    user_prompt = f"""{report_header}
🕐 وقت الرصد: {date_now} (بتوقيت الخادم){alert_block}

━━━━━━━━━━━━━━━━━━━━━━━━
📡 بيانات السوق اللحظية
━━━━━━━━━━━━━━━━━━━━━━━━
🥇 الذهب الفوري (XAU/USD) : {gold:.2f} دولار
💵 مؤشر قوة الدولار (DXY)  : {dxy:.2f} نقطة — {dxy_bias}
📈 عوائد سندات الخزانة (10Y): {tnx:.2f}% — {bond_bias}
⚖️ الحكم الكمي السائد       : {gold_pressure}

━━━━━━━━━━━━━━━━━━━━━━━━
🧮 المستويات الكمية المحسوبة
━━━━━━━━━━━━━━━━━━━━━━━━
🔴 المقاومة الثانية (السقف الكبير) : {r2}$
🟠 المقاومة الأولى (العقبة الأقرب) : {r1}$
⚪ نقطة الارتكاز المحورية           : {pivot}$
🟢 الدعم الأول (الحماية الأقرب)    : {s1}$
🔵 الدعم الثاني (القاع الدفاعي)    : {s2}$

━━━━━━━━━━━━━━━━━━━━━━━━
📝 المطلوب منك الآن — التقرير الكامل
━━━━━━━━━━━━━━━━━━━━━━━━

**القسم الأول — لماذا يتحرك الذهب هكذا؟ (المنطق الكمي مشروحاً)**
اشرح العلاقة الرياضية العكسية بين الذهب ومؤشر الدولار بمثال مبسط جداً (كأن الذهب والدولار كفتا ميزان). ثم اشرح كيف أن عوائد السندات هي "تكلفة الانتظار" — وكيف أن ارتفاعها يجعل المستثمرين يفضلون السندات على الذهب. ربط هذا المنطق بالأرقام الفعلية أعلاه لاستنتاج اتجاه الضغط الحالي على الذهب.

**القسم الثاني — التوقعات الكمية للجلسة القادمة**
بناءً على الأرقام المحسوبة، صِف بوضوح تام المسار المرجح الأكثر احتمالاً للذهب في الساعات القادمة. استخدم جملاً قصيرة وحاسمة. لا تتردد.

**القسم الثالث — خريطة السيناريوهات للمستثمر الفيزيكال**
(المستثمر الذي يشتري الذهب المادي ويستلمه يداً بيد من الصائغ أو البنك)

📈 سيناريو الصعود — شرط التفعيل والهدف:
إذا حافظ الذهب فوق {s1}$ وكسر {r1}$ بإغلاق واضح → الهدف المنطقي التالي هو {r2}$.
اشرح ما الذي يجب أن تراه في الدولار والسندات لتأكيد هذا المسار.

📉 سيناريو الهبوط — شرط التفعيل والهدف:
إذا كسر الذهب {s1}$ بإغلاق واضح → يُفتح الطريق نحو {s2}$ كمنطقة دعم دفاعية.
اشرح الإشارات التحذيرية التي يجب أن يراقبها المستثمر.

**القسم الرابع — نصيحة عملية مباشرة للمستثمر**
(جملتان أو ثلاث فقط — عملية، مباشرة، بلا مصطلحات معقدة)
ماذا يفعل الشخص الذي يريد شراء ذهب فيزيكال الآن في ضوء هذه المعطيات؟

━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ إخلاء المسؤولية القانوني الإلزامي
━━━━━━━━━━━━━━━━━━━━━━━━
اكتب في النهاية بالضبط: "⚠️ تنويه قانوني: جميع المستويات والسيناريوهات الواردة في هذا التقرير هي نتاج نماذج كمية واحتمالية مبنية على تقاطعات السوق اللحظية. الأسعار المذكورة حقيقية ومباشرة من الأسواق العالمية. أما التحليلات والتوقعات فهي أداة مساعدة لصنع القرار وليست توصية مالية ملزمة بالبيع أو الشراء."
"""

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.15,
            max_tokens=2048,
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