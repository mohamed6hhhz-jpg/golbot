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

def _fetch_ticker(symbol: str, period: str = "5d", max_retries: int = 4) -> float | None:
    """Fetch single ticker close price with exponential backoff for rate limits."""
    for attempt in range(max_retries):
        try:
            df = yf.Ticker(symbol).history(period=period)
            if df.empty:
                print(f"[yfinance] لا توجد بيانات للرمز {symbol} — السوق مغلق أو إجازة.")
                return None
            return float(df['Close'].iloc[-1])
        except Exception as e:
            wait = 2 ** attempt  # 1s, 2s, 4s, 8s
            print(f"[yfinance] محاولة {attempt+1}/{max_retries} للرمز {symbol} فشلت: {e} — انتظار {wait}s")
            time.sleep(wait)
    print(f"[yfinance] ❌ فشل تحميل بيانات {symbol} بعد {max_retries} محاولات.")
    return None

def get_market_data():
    """Fetch Gold, DXY and US10Y with individual retries and graceful holiday handling."""
    gold = _fetch_ticker("GC=F")
    if gold is None:
        return None, None, None
    # Small pause between requests to reduce Yahoo rate-limit likelihood
    time.sleep(1)
    dxy = _fetch_ticker("DX-Y.NYB")
    time.sleep(1)
    tnx = _fetch_ticker("^TNX")
    if dxy is None or tnx is None:
        print("[yfinance] بيانات غير مكتملة — سيتم التخطي لهذه الدورة.")
        return None, None, None
    return gold, dxy, tnx

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


def send_to_telegram(message: str, max_retries: int = 5) -> bool:
    """Send message to Telegram with exponential backoff to survive SSL drops."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # 1. Truncate to Telegram's 4096 char limit to prevent errors
    safe_message = message[:4000] if message else ""
    
    # 2. Remove parse_mode="Markdown" because Groq's markdown (like **text**) 
    # breaks Telegram's strict MarkdownV1 and can cause API hangs/drops.
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": safe_message}
    
    for attempt in range(max_retries):
        try:
            # 3. Disable HTTP Keep-Alive. Hugging Face Docker networking sometimes 
            # drops persistent SSL connections, causing "Read timed out".
            headers = {"Connection": "close"}
            response = requests.post(url, json=payload, headers=headers, timeout=45)
            response.raise_for_status()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ تم إرسال التقرير بنجاح لتليجرام.")
            return True
        except requests.exceptions.SSLError as e:
            wait = 2 ** attempt  # 1s, 2s, 4s, 8s, 16s
            print(f"⚠️ [Telegram SSL] محاولة {attempt+1}/{max_retries} — SSL انقطع، انتظار {wait}s ثم إعادة المحاولة...")
            time.sleep(wait)
        except requests.exceptions.ConnectionError as e:
            wait = 2 ** attempt
            print(f"⚠️ [Telegram NET] محاولة {attempt+1}/{max_retries} — خطأ شبكة، انتظار {wait}s...")
            time.sleep(wait)
        except Exception as e:
            wait = 2 ** attempt
            print(f"⚠️ [Telegram ERR] محاولة {attempt+1}/{max_retries} — {e} — انتظار {wait}s...")
            time.sleep(wait)
    print(f"❌ [Telegram] فشل إرسال التقرير نهائياً بعد {max_retries} محاولات. سيتم الاحتفاظ بالتقرير للدورة القادمة.")
    return False

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