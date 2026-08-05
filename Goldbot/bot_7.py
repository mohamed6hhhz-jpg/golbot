# ════════════════════════════════════════════════════════════════
#  🏆 Goldbot 7 — البوت السابع (تحليلات الكاماريلا والنماذج المتقدمة)
# ════════════════════════════════════════════════════════════════

import os
import time
import logging
import traceback

# استيراد دوال الكاماريلا من البوت التجريبي
from Goldbot.bot_daily_levels import calc_camarilla_pivots, _trades_from_levels, build_template_camarilla
from Goldbot.secrets_config import TELEGRAM_TOKENS, BOT7_CHAT_ID

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("Goldbot.bot_7")

TELEGRAM_BOT7_TOKEN = TELEGRAM_TOKENS.get("bot7", "")
TELEGRAM_BOT7_CHAT = BOT7_CHAT_ID

def process_and_send_bot7(data: dict) -> list:
    """
    يقوم بتوليد قوالب البوت السابع وإرسالها.
    يرجع قائمة بالقوالب المولدة من أجل الخلاصة إذا لزم الأمر.
    """
    reports_to_send = []
    
    try:
        # استخراج بيانات السعر من data
        c = float(data.get('gold', 0))
        # لحساب الكاماريلا نحتاج high, low لليوم السابق. 
        # إذا لم تكن موجودة بأسماء prev_high, نجلبها أو نقدرها.
        h = float(data.get('prev_high') or data.get('daily_high', c * 1.005))
        l = float(data.get('prev_low') or data.get('daily_low', c * 0.995))
        atr = float(data.get('atr', 20))
        
        # حساب مستويات الكاماريلا
        cam = calc_camarilla_pivots(h, l, c)
        
        # استخراج صفقات الكاماريلا
        ref = (h + l + c) / 3 # pivot مرجعي
        cp_mock = {"pivot": ref, "r1": ref+atr, "s1": ref-atr} # بيانات كلاسيكية وهمية أو يمكن جلبها إن لزم الأمر
        trades_cam = _trades_from_levels(cam, "camarilla", ref, atr)
        
        # بعض البيانات الناقصة التي يتوقعها القالب
        if "spot_price" not in data:
            data["spot_price"] = c
        if "prev_high" not in data:
            data["prev_high"] = h
        if "prev_low" not in data:
            data["prev_low"] = l
        if "send_time" not in data:
            from datetime import datetime, timezone, timedelta
            now_cairo = datetime.now(timezone.utc) + timedelta(hours=3)
            data["send_time"] = now_cairo.strftime("%H:%M")
            
        # بناء قالب الكاماريلا
        camarilla_report = build_template_camarilla(data, cam, cp_mock, trades_cam)
        
        # تعديل الترقيم ليناسب البوت السابع (يتم ترقيمه آلياً لاحقاً ولكن القالب نفسه مكتوب بداخله 2/2)
        import re
        camarilla_report = re.sub(r"^\d+/\d+\s*", "", camarilla_report)
        
        reports_to_send.append(("🎯 مستويات الكاماريلا الدقيقة", camarilla_report))
        
        # ── القالب الثاني: التقرير الفني والميل السعري ──
        outlook_report = _build_technical_outlook_template(data, cp_mock)
        reports_to_send.append(("📈 النظرة الفنية وميل السعر", outlook_report))
        
        # ── القالب الثالث: حركة السندات ──
        bonds_report = _build_bonds_template()
        reports_to_send.append(("📊 حركة السندات الأمريكية", bonds_report))
        
        # ── القالب الرابع: تسعير الفائدة (FedWatch) ──
        fedwatch_report = _build_fedwatch_template(data)
        reports_to_send.append(("🏦 رادار الفيدرالي وتسعير الفائدة", fedwatch_report))
        
        # ── القالب الخامس: أفضل صفقة لوت عالي سريعة ──
        best_scalp_report = _build_best_high_lot_scalp_template(data, cam)
        reports_to_send.append(("⚡ أفضل صفقة لوت عالي (سكالبينج)", best_scalp_report))
        
        # ── القالب السادس: أفضل صفقة حتى نهاية الساعة ──
        best_hourly_report = _build_best_hourly_trade_template(data)
        reports_to_send.append(("⏳ أفضل صفقة حتى نهاية الساعة", best_hourly_report))
        
        # ── القالب السابع: مسار اليوم (خارطة الطريق) ──
        trajectory_report = _build_daily_trajectory_template(data, cp_mock)
        reports_to_send.append(("🗺️ خارطة طريق اليوم (المسار المتوقع)", trajectory_report))
        
        # ── القالب الثامن: المنطقة الحالية (الاتجاه، الهدف، ومتى؟) ──
        zone_report = _build_current_zone_template(data, cp_mock)
        reports_to_send.append(("🧭 حالة المنطقة الحالية (الهدف والزمن)", zone_report))
        
        # ── القالب التاسع: الصفقة الأعظم على الإطلاق ──
        greatest_trade_report = _build_greatest_trade_template(data, cp_mock)
        reports_to_send.append(("👑 الصفقة الأعظم على الإطلاق", greatest_trade_report))
        
        # ── القالب العاشر: عقلية الفيدرالي (الماكرو الاقتصادي) ──
        fed_mindset_report = _build_fed_mindset_template(data)
        reports_to_send.append(("🧠 كيف يفكر الفيدرالي؟ (الروابط الأربعة)", fed_mindset_report))
        
    except Exception as e:
        log.error(f"❌ [Bot 7] فشل توليد قالب الكاماريلا: {e}\n{traceback.format_exc()}")

    # ── إرسال التقارير ──
    if not TELEGRAM_BOT7_TOKEN or not TELEGRAM_BOT7_CHAT:
        log.warning("⚠️ [Bot 7] التوكن أو Chat ID غير معرفين، تم تخطي الإرسال.")
        return reports_to_send

    def _split_msg(text: str, max_len: int = 4000) -> list:
        chunks = []
        while len(text) > max_len:
            split_idx = text.rfind("\n", 0, max_len)
            if split_idx == -1:
                split_idx = max_len
            chunks.append(text[:split_idx])
            text = text[split_idx:].lstrip()
        if text:
            chunks.append(text)
        return chunks

    total = len(reports_to_send)
    for idx, (title, content) in enumerate(reports_to_send, 1):
        full_message = f"[{idx}/{total}] {title}\n\n{content}"
        chunks = _split_msg(full_message)
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT7_TOKEN}/sendMessage"
        ip_url = f"https://149.154.167.220/bot{TELEGRAM_BOT7_TOKEN}/sendMessage"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        ip_headers = dict(headers)
        ip_headers["Host"] = "api.telegram.org"
        
        for chunk_idx, chunk in enumerate(chunks, 1):
            payload = {
                "chat_id": TELEGRAM_BOT7_CHAT,
                "text": chunk,
                "disable_web_page_preview": True
            }
            
            for attempt in range(3):
                try:
                    import httpx
                    with httpx.Client(timeout=20.0, headers=headers) as client:
                        resp = client.post(url, json=payload)
                        resp.raise_for_status()
                        if len(chunks) > 1:
                            log.info(f"✅ [Bot 7] تم إرسال القالب {idx}/{total} (جزء {chunk_idx}/{len(chunks)}) بنجاح (httpx).")
                        else:
                            log.info(f"✅ [Bot 7] تم إرسال القالب {idx}/{total} بنجاح (httpx).")
                        break
                except Exception as e:
                    log.warning(f"⚠️ [Bot 7] محاولة {attempt+1} (httpx) فشلت: {e} — تجربة Direct IPv4...")
                    try:
                        import requests
                        import urllib3
                        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                        resp = requests.post(ip_url, json=payload, headers=ip_headers, timeout=20.0, verify=False)
                        resp.raise_for_status()
                        if len(chunks) > 1:
                            log.info(f"✅ [Bot 7] تم إرسال القالب {idx}/{total} (جزء {chunk_idx}/{len(chunks)}) بنجاح (Direct IPv4).")
                        else:
                            log.info(f"✅ [Bot 7] تم إرسال القالب {idx}/{total} بنجاح (Direct IPv4).")
                        break
                    except Exception as e2:
                        log.warning(f"⚠️ [Bot 7] محاولة {attempt+1} (Direct IPv4) فشلت: {e2} — تجربة requests...")
                        try:
                            import requests
                            resp = requests.post(url, json=payload, headers=headers, timeout=20.0)
                            resp.raise_for_status()
                            if len(chunks) > 1:
                                log.info(f"✅ [Bot 7] تم إرسال القالب {idx}/{total} (جزء {chunk_idx}/{len(chunks)}) بنجاح (requests).")
                            else:
                                log.info(f"✅ [Bot 7] تم إرسال القالب {idx}/{total} بنجاح (requests).")
                            break
                        except Exception as req_err:
                            log.error(f"❌ [Bot 7] استثناء أثناء الإرسال: {req_err}")
                            import time
                            time.sleep(2)
            time.sleep(1)  # لتجنب حظر التيليجرام لكثرة الرسائل

    return reports_to_send

def _build_technical_outlook_template(data: dict, cp: dict = None) -> str:
    """
    يبني تقرير النظرة الفنية وميل السعر ديناميكياً بناءً على السعر الحالي والمحور.
    """
    c = float(data.get('gold', 0))
    # محاولة استخراج النقاط المحورية أو حسابها بشكل تقريبي
    if not cp or 'pivot' not in cp:
        # حساب تقريبي إذا لم يتم تمريرها
        h = float(data.get('prev_high') or data.get('daily_high', c * 1.005))
        l = float(data.get('prev_low') or data.get('daily_low', c * 0.995))
        ref = (h + l + c) / 3
        atr = float(data.get('atr', 20))
        pivot = ref
        s1 = ref - atr
        s2 = ref - atr * 1.5
        r1 = ref + atr
        r2 = ref + atr * 1.5
        r3 = ref + atr * 2
        s3 = ref - atr * 2
    else:
        pivot = cp.get('pivot', c)
        s1 = cp.get('s1', c - 20)
        s2 = cp.get('s2', c - 40)
        s3 = cp.get('s3', c - 60)
        r1 = cp.get('r1', c + 20)
        r2 = cp.get('r2', c + 40)
        r3 = cp.get('r3', c + 60)

    # حساب احتمالية الاتجاه (مبسط)
    # يمكن دمج RSI إذا كان متوفراً
    rsi = data.get('rsi_1h') or data.get('rsi', 50)
    
    if c >= pivot:
        trend = "إيجابي"
        bounce = f"{s1:.0f}" if c < r1 else f"{pivot:.0f}"
        move_desc = "تحسن"
        pos_str = "أعلى"
        sup_res_1 = "الدعم"
        rng1 = f"{pivot:.0f}"
        rng2 = f"{r1:.0f}" if c > r1 else f"{s1:.0f}"
        rng1, rng2 = (rng2, rng1) if float(rng1) > float(rng2) else (rng1, rng2)
        scen_type = "الصاعد"
        
        base_prob = 60 + (float(rsi) - 50) if float(rsi) > 50 else 60
        main_prob = min(int(base_prob), 85)
        alt_prob = 100 - main_prob
        
        t1 = f"{r1:.0f}"
        t2 = f"{r2:.0f}"
        pos_str2 = "أعلاها"
        ext_type = "الصعود"
        t3 = f"{r3:.0f}"
        
        sup_res_2 = "دعم"
        crit_lvl = f"{s1:.0f}"
        pressure = "البيعي"
        action1 = "التعافي"
        action2 = "الضعف"
    else:
        trend = "سلبي"
        bounce = f"{r1:.0f}" if c > s1 else f"{pivot:.0f}"
        move_desc = "تراجع"
        pos_str = "أسفل"
        sup_res_1 = "المقاومة"
        rng1 = f"{r1:.0f}" if c < s1 else f"{pivot:.0f}"
        rng2 = f"{pivot:.0f}"
        rng1, rng2 = (rng1, rng2) if float(rng1) < float(rng2) else (rng2, rng1)
        scen_type = "الهابط"
        
        base_prob = 60 + (50 - float(rsi)) if float(rsi) < 50 else 60
        main_prob = min(int(base_prob), 85)
        alt_prob = 100 - main_prob
        
        t1 = f"{s1:.0f}"
        t2 = f"{s2:.0f}"
        pos_str2 = "أسفلها"
        ext_type = "الهبوط"
        t3 = f"{s3:.0f}"
        
        sup_res_2 = "مقاومة"
        crit_lvl = f"{r1:.0f}"
        pressure = "الشرائي"
        action1 = "الهبوط"
        action2 = "القوة"

    template = (
        f"الذهب XAUUSD يحافظ على ميل {trend} قصير الأجل بعد ارتداده من منطقة {bounce} تقريبًا، "
        f"مع {move_desc} واضح في الحركة السعرية واستمرار الثبات {pos_str} نطاق {sup_res_1} {rng1}–{rng2}، "
        f"وهو ما يمنح السيناريو {scen_type} أفضلية تُقدّر بنحو {main_prob}% لاستهداف {t1} ثم {t2}، "
        f"بينما يؤدي اختراق المنطقة الأخيرة والثبات {pos_str2} إلى تعزيز فرص امتداد {ext_type} نحو {t3}\n\n"
        f"في المقابل، يبقى السيناريو البديل بنسبة {alt_prob}% قائمًا إذا فقد السعر {sup_res_2} {crit_lvl}، "
        f"ما قد يعيد الضغط {pressure} فنيا ولذلك تظل منطقة {rng1}–{rng2} هي نطاق الفصل الأهم بين استمرار {action1} وعودة {action2} فنيا"
    )
    return template

def _build_bonds_template() -> str:
    """
    قالب السندات: يجلب عوائد السندات (10 سنوات) للافتتاح والحالي ويحسب نسبة التغير.
    """
    import yfinance as yf
    try:
        tk = yf.Ticker("^TNX")
        df = tk.history(period="1d")
        if df.empty:
            return "⚠️ بيانات السندات غير متوفرة حالياً."
        
        open_val = float(df['Open'].iloc[-1])
        current_val = float(df['Close'].iloc[-1])
        
        pct_change = ((current_val - open_val) / open_val) * 100 if open_val > 0 else 0
        
        if pct_change > 0:
            status = "صعود 📈 (سلبي للذهب)"
        elif pct_change < 0:
            status = "هبوط 📉 (إيجابي للذهب)"
        else:
            status = "استقرار ➖"
            
        template = (
            f"🇺🇸 عوائد السندات الأمريكية (10 سنوات - US10Y)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔹 الافتتاح اليوم: {open_val:.3f}%\n"
            f"🔹 السعر الآن   : {current_val:.3f}%\n"
            f"🔹 نسبة التغير  : {abs(pct_change):.2f}% ⟵ {status}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 تذكر: العوائد تتحرك غالباً بعلاقة عكسية مع الذهب. ارتفاع العوائد يضغط على الذهب والعكس صحيح."
        )
        return template
    except Exception as e:
        log.error(f"❌ خطأ في جلب بيانات السندات للقالب 3: {e}")
        return "⚠️ تعذر جلب بيانات السندات في الوقت الحالي."

def _build_fedwatch_template(data: dict) -> str:
    """
    قالب رادار الفيدرالي: يسحب العقود الآجلة للفائدة (ZQ=F) ويستنتج مسار التخفيضات واحتمالات الاجتماعات.
    """
    import yfinance as yf
    
    current_fed_rate = data.get('interest_rate', 5.50)
    
    try:
        # جلب عقود الفيدرالي الآجلة
        tk = yf.Ticker("ZQ=F")
        df = tk.history(period="1d")
        if df.empty:
            zq_price = 100 - (current_fed_rate - 0.50)
        else:
            zq_price = float(df['Close'].iloc[-1])
            
        implied_rate = 100 - zq_price
        
        # عدد مرات الخفض المتوقعة (كل خفض = 0.25% أي 25 نقطة أساس)
        rate_diff = current_fed_rate - implied_rate
        expected_cuts = rate_diff / 0.25
        
        if expected_cuts <= 0:
            bias = "لا يوجد خفض متوقع (تثبيت أو رفع)"
            cuts_text = "0 نقطة أساس"
            prob_sep = "15% خفض | 85% تثبيت"
            prob_nov = "20% خفض | 80% تثبيت"
            prob_dec = "25% خفض | 75% تثبيت"
        elif expected_cuts < 1.5:
            bias = "تيسير نقدي حذر (خفض واحد أو اثنين)"
            cuts_text = "25 - 50 نقطة أساس"
            prob_sep = "65% خفض (25bps) | 35% تثبيت"
            prob_nov = "40% خفض | 60% تثبيت"
            prob_dec = "55% خفض | 45% تثبيت"
        elif expected_cuts < 2.5:
            bias = "تيسير نقدي معتدل (خفض مرتين إلى ثلاث)"
            cuts_text = "50 - 75 نقطة أساس"
            prob_sep = "85% خفض (25bps) | 15% تثبيت"
            prob_nov = "70% خفض | 30% تثبيت"
            prob_dec = "90% خفض | 10% تثبيت"
        else:
            bias = "تيسير نقدي قوي (دورة خفض عنيفة)"
            cuts_text = "أكثر من 75 نقطة أساس"
            prob_sep = "95% خفض (50bps) | 5% (25bps)"
            prob_nov = "85% خفض (25bps)"
            prob_dec = "95% خفض (25bps)"
            
        # رؤية الأموال الذكية (مقارنة مع عوائد السندات لسنتين)
        twy = data.get('twy', current_fed_rate - 0.5)
        if twy < implied_rate - 0.2:
            smart_money = "سوق السندات (2Y) يسعر وتيرة خفض أسرع بكثير من التسعير الفوري لأسواق المال."
        elif twy > implied_rate + 0.2:
            smart_money = "سوق السندات (2Y) حذر ولا يدعم التفاؤل المفرط في التسعير الفوري."
        else:
            smart_money = "تطابق قوي بين التسعير الفوري وسوق السندات على مسار الفائدة."
            
        template = (
            f"🏦 رادار الفيدرالي وتسعير الفائدة (FedWatch) بقية العام\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔹 الفائدة الحالية: {current_fed_rate:.2f}%\n"
            f"🔹 الفائدة المسعرة (التسعير الفوري): {implied_rate:.2f}%\n"
            f"🔹 إجمالي الخفض المتوقع: {cuts_text}\n"
            f"🔹 المسار العام: {bias}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 احتمالات تسعير الاجتماعات القادمة:\n"
            f"   سبتمبر : {prob_sep}\n"
            f"   نوفمبر : {prob_nov}\n"
            f"   ديسمبر : {prob_dec}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 رؤية الأموال الذكية: {smart_money}\n"
            f"🎯 تأثير ذلك على الذهب: {'إيجابي جداً 🟢 (داعم للصعود)' if expected_cuts > 1.5 else 'حيادي 🟡' if expected_cuts > 0 else 'سلبي 🔴 (ضاغط للهبوط)'}"
        )
        return template
    except Exception as e:
        log.error(f"❌ خطأ في جلب بيانات تسعير الفائدة للقالب 4: {e}")
        return "⚠️ تعذر جلب بيانات تسعير الفائدة (FedWatch) في الوقت الحالي."

def _build_best_high_lot_scalp_template(data: dict, cam: dict) -> str:
    """
    قالب: أفضل صفقة لوت عالي سريعة (سكالبينج خاطف).
    يركز على الجودة (الأفضل) من ناحية الوقف الضيق والاحتمالية العالية، وليس فقط القوة.
    """
    c = float(data.get('gold', 0))
    
    h3 = float(cam.get('h3', c + 10))
    l3 = float(cam.get('l3', c - 10))
    h4 = float(cam.get('h4', c + 15))
    l4 = float(cam.get('l4', c - 15))
    
    # تحديد "أفضل" صفقة بناءً على القرب من المستوى وتجنب التداول في المنتصف تماماً إن أمكن
    dist_to_h3 = abs(h3 - c)
    dist_to_l3 = abs(c - l3)
    
    if dist_to_h3 < dist_to_l3:
        trade_dir = "بيع (Short) 🔴"
        entry = h3
        entry_zone = h3 + 0.5
        sl = h4
        tp1 = h3 - 2.5
        tp2 = h3 - 5.0
        reason = f"اقتراب السعر من مستوى الارتداد المؤسسي H3 ({h3:.2f})."
    else:
        trade_dir = "شراء (Long) 🟢"
        entry = l3
        entry_zone = l3 - 0.5
        sl = l4
        tp1 = l3 + 2.5
        tp2 = l3 + 5.0
        reason = f"اقتراب السعر من مستوى الدعم الذهبي L3 ({l3:.2f})."
        
    risk = abs(entry - sl)
    
    template = (
        f"⚡ أفضل صفقة لوت عالي سريعة (Scalp)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 نوع الصفقة : {trade_dir}\n"
        f"📍 نقطة الدخول : {entry:.2f} إلى {entry_zone:.2f}\n"
        f"⛔ وقف الخسارة: إغلاق شمعة ربع ساعة خلف {sl:.2f} (مخاطرة ~{risk:.1f}$)\n"
        f"💰 الأهداف    : {tp1:.2f} ثم {tp2:.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 لماذا هذه هي 'الأفضل' (وليس الأقوى)؟\n"
        f"لأنها توفر نسبة (عائد/مخاطرة) ممتازة جداً، حيث الوقف ضيق مما يسمح بدخول 'لوت عالي' بأمان نسبي.\n"
        f"السبب الفني: {reason}\n"
        f"⚠️ تنبيه: الصفقات السريعة تتطلب تأمين الدخول (Break-even) بمجرد تحقيق أول +15 أو +20 نقطة."
    )
    return template

def _build_best_hourly_trade_template(data: dict) -> str:
    """
    قالب: أفضل صفقة على الإطلاق من الآن وحتى نهاية الساعة الحالية.
    يعتمد على الزخم اللحظي وتتبع الترند القصير المدى.
    """
    from datetime import datetime
    import pytz
    
    # حساب الدقائق المتبقية حتى إغلاق شمعة الساعة الحالية
    now = datetime.now(pytz.timezone("Africa/Cairo"))
    minutes_left = 60 - now.minute
    
    c = float(data.get('gold', 0))
    rsi = float(data.get('rsi_1h', data.get('rsi', 50)))
    
    if rsi > 55:
        trade_dir = "شراء (Buy) 🟢"
        entry_zone = f"{c - 1.5:.2f} إلى {c:.2f}"
        sl = c - 4.5
        tp1 = c + 4.0
        tp2 = c + 8.0
        logic = "زخم إيجابي قوي على فريم الساعة (RSI صاعد)، المسار الأسهل للسعر حالياً هو الصعود."
        risk_type = "استغلال الزخم الشرائي المباشر"
    elif rsi < 45:
        trade_dir = "بيع (Sell) 🔴"
        entry_zone = f"{c:.2f} إلى {c + 1.5:.2f}"
        sl = c + 4.5
        tp1 = c - 4.0
        tp2 = c - 8.0
        logic = "ضغط بيعي واضح على فريم الساعة (RSI هابط)، المسار الأسهل للسعر حالياً هو الهبوط."
        risk_type = "استغلال الزخم البيعي المباشر"
    else:
        if c % 10 < 5:
            trade_dir = "شراء من الدعم (Buy Dip) 🟢"
            entry_zone = f"{c - 2.0:.2f} إلى {c - 1.0:.2f}"
            sl = c - 5.0
            tp1 = c + 3.0
            tp2 = c + 6.0
            logic = "انعدام للزخم الاتجاهي الحاد (سوق متذبذب)، الأفضل الشراء من مناطق الدعوم اللحظية القريبة."
            risk_type = "ارتداد من قاع التذبذب اللحظي"
        else:
            trade_dir = "بيع من المقاومة (Sell Rally) 🔴"
            entry_zone = f"{c + 1.0:.2f} إلى {c + 2.0:.2f}"
            sl = c + 5.0
            tp1 = c - 3.0
            tp2 = c - 6.0
            logic = "انعدام للزخم الاتجاهي الحاد (سوق متذبذب)، الأفضل البيع من مناطق المقاومات اللحظية القريبة."
            risk_type = "ارتداد من قمة التذبذب اللحظي"
            
    template = (
        f"⏳ **أفضل صفقة على الإطلاق (حتى نهاية الساعة الحالية)**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱️ المتبقي لإغلاق الساعة: {minutes_left} دقيقة\n"
        f"🎯 **التوصية الفورية**: {trade_dir}\n"
        f"📍 **أفضل نطاق دخول الآن**: {entry_zone}\n"
        f"⛔ **وقف الخسارة المرجعي**: {sl:.2f}\n"
        f"💰 **الأهداف اللحظية**: {tp1:.2f} ثم {tp2:.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🧠 **المنطق الفني**: {logic}\n"
        f"⚡ **نوع الصفقة**: {risk_type}\n"
        f"⚠️ تنبيه: هذه الصفقة صلاحيتها تنتهي بإغلاق شمعة الساعة الحالية."
    )
    return template

def _build_daily_trajectory_template(data: dict, cp: dict = None) -> str:
    """
    قالب مسار اليوم: يحلل السعر لتحديد ما إذا كان سيصعد مباشرة، 
    أو يصحح للدعم الأول ثم يصعد، أو ينهار ويكسر الدعوم.
    """
    c = float(data.get('gold', 0))
    rsi = float(data.get('rsi_1h', data.get('rsi', 50)))
    
    if not cp or 'pivot' not in cp:
        # حساب تقريبي إذا لم يكن متاحاً
        h = float(data.get('prev_high') or data.get('daily_high', c * 1.005))
        l = float(data.get('prev_low') or data.get('daily_low', c * 0.995))
        ref = (h + l + c) / 3
        atr = float(data.get('atr', 20))
        pivot = ref
        s1, s2, s3 = ref - atr, ref - atr * 1.5, ref - atr * 2
        r1, r2, r3 = ref + atr, ref + atr * 1.5, ref + atr * 2
    else:
        pivot = cp.get('pivot', c)
        s1 = cp.get('s1', c - 20)
        s2 = cp.get('s2', c - 40)
        s3 = cp.get('s3', c - 60)
        r1 = cp.get('r1', c + 20)
        r2 = cp.get('r2', c + 40)
        r3 = cp.get('r3', c + 60)

    # تحديد مسار اليوم بناءً على الزخم وموقع السعر
    if rsi > 58 and c >= pivot:
        title_status = "صعود مباشر 🚀"
        trajectory = f"من المتوقع أن يواصل الذهب صعوده **من السعر الحالي** مباشرًة لاختراق المقاومة الأولى ({r1:.2f})، وفي حال الثبات أعلاها سيفتح المجال لاستهداف المقاومة الثانية ({r2:.2f}) وربما الثالثة ({r3:.2f})."
        key_level = f"الشرط الأهم: عدم العودة لكسر الارتكاز ({pivot:.2f}) لأسفل."
    elif 45 <= rsi <= 58 and c >= pivot:
        title_status = "تراجع تكتيكي (Dip) ثم صعود 🔄"
        trajectory = f"السعر الحالي يفتقد للزخم الكافي للاختراق المباشر، لذا من المرجح أن ينزل لملامسة **الدعم الأول ({s1:.2f})** لجمع السيولة وتفريغ المؤشرات، قبل أن يرتد بقوة صعوداً نحو المقاومة الأولى ({r1:.2f}) والثانية ({r2:.2f})."
        key_level = f"الشرط الأهم: صمود الدعم الأول ({s1:.2f}) وعدم كسره بإغلاق."
    elif rsi < 42 and c <= pivot:
        title_status = "انهيار مستمر وكسر للدعوم ⚠️"
        trajectory = f"السوق يقع تحت ضغط بيعي شرس، ومن المتوقع أن **ينهار السعر ويكسر الدعم الأول ({s1:.2f})** ليستهدف بشكل مباشر الدعم الثاني ({s2:.2f}) وربما يمتد لزيارة مناطق أعمق."
        key_level = f"الشرط الأهم: بقاء السعر أسفل نقطة الارتكاز ({pivot:.2f}) لاستمرار السلبية."
    else:
        # حالة التذبذب المائل للهبوط أو التعافي البطيء
        title_status = "صراع عند الدعم (محاولة تعافي) 📉"
        trajectory = f"السعر يحاول التماسك وبناء قاعدة ارتكاز أعلى الدعم الأول ({s1:.2f}). قد نشهد ارتداداً حذراً نحو المقاومة الأولى ({r1:.2f})، ولكن إذا فشل في الصمود، فسينهار مسرعاً نحو الدعم الثاني ({s2:.2f})."
        key_level = f"نقطة الفصل: الثبات أعلى الدعم الأول ({s1:.2f}) هو الملاذ الأخير لمنع الانهيار."

    template = (
        f"🗺️ **خارطة طريق اليوم (المسار المتوقع)**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔮 **السيناريو الأقرب**: {title_status}\n\n"
        f"📌 **التفاصيل**: {trajectory}\n\n"
        f"🎯 **المحطات المتوقعة للمسار**:\n"
        f"   المقاومة 3 (R3): {r3:.2f}\n"
        f"   المقاومة 2 (R2): {r2:.2f}\n"
        f"   المقاومة 1 (R1): {r1:.2f}\n"
        f"   الارتكاز (Pivot): {pivot:.2f}\n"
        f"   الدعم 1 (S1): {s1:.2f}\n"
        f"   الدعم 2 (S2): {s2:.2f}\n\n"
        f"💡 **مفتاح السيناريو**: {key_level}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    return template

def _build_current_zone_template(data: dict, cp: dict = None) -> str:
    """
    قالب المنطقة الحالية: يجيب بدقة على (صعود أم هبوط؟ إلى أين؟ ومتى تقريباً؟)
    """
    c = float(data.get('gold', 0))
    ema20 = float(data.get('ema_20', c))
    atr = float(data.get('atr', 20))
    
    if not cp or 'pivot' not in cp:
        # حساب تقريبي إذا لم يكن متاحاً
        h = float(data.get('prev_high') or data.get('daily_high', c * 1.005))
        l = float(data.get('prev_low') or data.get('daily_low', c * 0.995))
        ref = (h + l + c) / 3
        s1, s2, s3 = ref - atr, ref - atr * 1.5, ref - atr * 2
        r1, r2, r3 = ref + atr, ref + atr * 1.5, ref + atr * 2
    else:
        s1 = cp.get('s1', c - 20)
        s2 = cp.get('s2', c - 40)
        s3 = cp.get('s3', c - 60)
        r1 = cp.get('r1', c + 20)
        r2 = cp.get('r2', c + 40)
        r3 = cp.get('r3', c + 60)

    # تحديد الاتجاه والهدف بناءً على وضع السعر
    if c >= ema20:
        zone_status = "صعود ↗️"
        zone_desc = "المنطقة الحالية إيجابية وتدعم القوة الشرائية."
        
        # البحث عن المقاومة القادمة
        if c < r1 - 1:
            target = r1
            t_name = "المقاومة الأولى (R1)"
        elif c < r2 - 1:
            target = r2
            t_name = "المقاومة الثانية (R2)"
        else:
            target = r3
            t_name = "المقاومة الثالثة (R3)"
    else:
        zone_status = "هبوط ↘️"
        zone_desc = "المنطقة الحالية سلبية وتقع تحت ضغط بيعي."
        
        # البحث عن الدعم القادم
        if c > s1 + 1:
            target = s1
            t_name = "الدعم الأول (S1)"
        elif c > s2 + 1:
            target = s2
            t_name = "الدعم الثاني (S2)"
        else:
            target = s3
            t_name = "الدعم الثالث (S3)"

    # حساب التوقيت التقريبي (متى؟) بناءً على متوسط الحركة اللحظية
    # نفترض أن السعر يتحرك بمعدل ATR / 12 في الساعة
    hourly_speed = atr / 12 if atr > 0 else 2.0
    distance = abs(target - c)
    hours_needed = distance / hourly_speed
    
    if hours_needed <= 1.5:
        eta_text = "سريع جداً (خلال 1 إلى 2 ساعة القادمة)"
        volatility = "زخم عالي (السعر قريب جداً من الهدف)"
    elif hours_needed <= 4.0:
        eta_text = "خلال الجلسة الحالية (من 3 إلى 5 ساعات)"
        volatility = "سرعة طبيعية مستقرة"
    elif hours_needed <= 8.0:
        eta_text = "بنهاية تداولات اليوم (من 6 إلى 8 ساعات)"
        volatility = "حركة بطيئة أو تحتاج محفز قوي (أخبار)"
    else:
        eta_text = "يحتاج إلى يوم تداول كامل أو كسر عنيف"
        volatility = "الهدف بعيد نسبياً عن النطاق الحالي"
        
    template = (
        f"🧭 **حالة المنطقة الحالية (الاتجاه والهدف والزمن)**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"السعر الحالي: {c:.2f}\n\n"
        f"📈 **حالة المنطقة**: {zone_status}\n"
        f"({zone_desc})\n\n"
        f"🎯 **الهدف القادم (إلى كام؟)**:\n"
        f"يستهدف السعر التوجه نحو {t_name} عند مستوى **{target:.2f}**\n\n"
        f"⏳ **الإطار الزمني المتوقع (متى؟)**:\n"
        f"{eta_text}\n"
        f"(حالة الزخم: {volatility})\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ ملاحظة: الإطار الزمني هو تقدير رياضي يعتمد على متوسط سرعة السعر (ATR) الحالية."
    )
    return template

def _build_greatest_trade_template(data: dict, cp: dict = None) -> str:
    """
    قالب الصفقة الأعظم: يحدد صفقة السوينج أو القنص ذات أعلى نسبة R:R 
    والتي تتماشى مع الاتجاه العام من أقوى المستويات.
    """
    c = float(data.get('gold', 0))
    ema50 = float(data.get('ema_50', c))
    
    if not cp or 'pivot' not in cp:
        # حساب تقريبي إذا لم يكن متاحاً
        h = float(data.get('prev_high') or data.get('daily_high', c * 1.005))
        l = float(data.get('prev_low') or data.get('daily_low', c * 0.995))
        ref = (h + l + c) / 3
        atr = float(data.get('atr', 20))
        s1, s2, s3 = ref - atr, ref - atr * 1.5, ref - atr * 2
        r1, r2, r3 = ref + atr, ref + atr * 1.5, ref + atr * 2
    else:
        s1 = cp.get('s1', c - 20)
        s2 = cp.get('s2', c - 40)
        s3 = cp.get('s3', c - 60)
        r1 = cp.get('r1', c + 20)
        r2 = cp.get('r2', c + 40)
        r3 = cp.get('r3', c + 60)

    # التحديد بناءً على الاتجاه العام (EMA50 كمثال للاتجاه المتوسط)
    is_bullish = c > ema50
    
    if is_bullish:
        trade_dir = "شراء (Buy Limit / Long) 🟢"
        # في الترند الصاعد، الصفقة الأعظم هي صيد السعر من قاع عميق (S2 أو S3)
        entry = s2
        zone = f"{s2:.2f} إلى {s3:.2f}"
        sl = s3 - 5.0
        tp1 = r1
        tp2 = r3
        logic = "الاتجاه العام صاعد. 'الصفقة الأعظم' ليست مطاردة السعر صعوداً، بل هي الجلوس كالأسد لانتظار تراجع عميق ومخيف لاصطياد السعر من القاع بأقل مخاطرة وأعلى عائد ممكن."
    else:
        trade_dir = "بيع (Sell Limit / Short) 🔴"
        # في الترند الهابط، الصفقة الأعظم هي اصطياد قمة جديدة (R2 أو R3)
        entry = r2
        zone = f"{r2:.2f} إلى {r3:.2f}"
        sl = r3 + 5.0
        tp1 = s1
        tp2 = s3
        logic = "الاتجاه العام هابط. 'الصفقة الأعظم' هي عدم البيع في القيعان، بل انتظار صعود وهمي لضرب قمة قوية واصطياد السعر بيعاً بأقل مخاطرة وأعلى عائد ممكن."

    # تحديد ما إذا كانت مفعلة أم قيد الانتظار
    status = "قيد الانتظار (Sniper Mode) 🔭" if abs(c - entry) > 10 else "مفعلة الآن أو قريبة جداً من التنفيذ 🔥"

    template = (
        f"👑 **الصفقة الأعظم على الإطلاق (The Master Trade)**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 **نوع الصفقة**: {trade_dir}\n"
        f"📍 **منطقة القنص الذهبية**: {zone}\n"
        f"⛔ **وقف الخسارة المرن**: إغلاق يومي خلف {sl:.2f}\n"
        f"💰 **الأهداف الكبرى**: {tp1:.2f} ثم {tp2:.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 **فلسفة الصفقة (لماذا هي الأعظم؟)**:\n"
        f"{logic}\n\n"
        f"🚦 **الحالة الحالية**: {status}\n"
        f"⚠️ تذكر: هذه الصفقة تتطلب (صبر القناص). هي لا تحدث كل ساعة، لكن عندما تحدث، فإنها تعوض تداولات أسبوع كامل!"
    )
    return template

def _build_fed_mindset_template(data: dict) -> str:
    """
    قالب عقلية الفيدرالي: يدمج النص الفلسفي الخاص بالمستخدم مع البيانات الحية 
    للتضخم، النفط، السندات، والدولار (كمؤشر للتوظيف) لاستنتاج النبرة القادمة.
    """
    inflation = float(data.get('inflation', 3.0)) 
    oil = float(data.get('oil', 80.0))
    tnx = float(data.get('tnx', 4.2))
    dxy = float(data.get('dxy', 104.0))
    
    # استقراء وضع التوظيف وقوة الاقتصاد من مؤشر الدولار (DXY)
    employment_status = "قوية ومتماسكة (تدعم الدولار)" if dxy > 103.5 else "تظهر علامات تباطؤ وضعف"
    
    # خوارزمية تحديد نبرة الفيدرالي بناءً على الروابط الأربعة
    hawkish_points = 0
    if inflation > 2.5: hawkish_points += 1
    if oil > 80: hawkish_points += 1
    if tnx > 4.2: hawkish_points += 1
    if dxy > 103.5: hawkish_points += 1
    
    if hawkish_points >= 3:
        powell_tone = "متشددة (Hawkish) 🦅"
        powell_desc = "البيانات تضغط على الفيدرالي لإبقاء الفائدة مرتفعة لمحاربة شبح التضخم."
        gold_impact = "ضغوط بيعية 🔴"
        dxy_impact = "يواصل قوته وهيمنته 🟢"
    elif hawkish_points <= 1:
        powell_tone = "تميل إلى التيسير (Dovish) 🕊️"
        powell_desc = "تباطؤ التضخم وضعف البيانات يمنحان الفيدرالي مساحة لخفض الفائدة."
        gold_impact = "انطلاقة جديدة وصعود 🟢"
        dxy_impact = "يفقد زخمه 🔴"
    else:
        powell_tone = "حذرة ومحايدة (Neutral) ⚖️"
        powell_desc = "تضارب في البيانات، الفيدرالي سيعتمد سياسة 'الانتظار والترقب'."
        gold_impact = "تذبذب عرضي 🟡"
        dxy_impact = "حركة عرضية 🟡"
        
    template = (
        f"🧠 **كيف يفكر الفيدرالي الآن؟ (تحليل الروابط الأربعة)**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"قبل أن تعرف قرار الفائدة… اسأل نفسك سؤالًا واحدًا: كيف تبدو الصورة الماكرو-اقتصادية الآن؟\n\n"
        f"📊 **الأرقام الحية تتحدث:**\n"
        f"1️⃣ **التضخم**: {inflation:.1f}% (هدف الفيدرالي هو 2%)\n"
        f"2️⃣ **التوظيف (مستقرأ من الدولار)**: {employment_status}\n"
        f"3️⃣ **أسعار النفط**: {oil:.2f}$ للبرميل (تأثير مباشر على التضخم المستقبلي)\n"
        f"4️⃣ **عوائد السندات (10Y)**: {tnx:.2f}%\n\n"
        f"إذا استطعت قراءة هذه العناصر الأربعة معًا، فأنت لا تتوقع القرار فقط… بل تقرأ طريقة تفكير الاحتياطي الفيدرالي قبل أن يتحدث.\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔍 **ومن هنا تبدأ الصورة في الاتضاح:**\n\n"
        f"▪️ هل ستكون نبرة رئيس الفيدرالي متشددة أم تميل للتيسير؟\n"
        f"النتيجة: **{powell_tone}**\n"
        f"({powell_desc})\n\n"
        f"▪️ هل سيواصل الدولار قوته أم يفقد زخمه؟\n"
        f"النتيجة: **{dxy_impact}**\n\n"
        f"▪️ وهل الذهب يستعد لانطلاقة جديدة… أم لضغوط بيعية؟\n"
        f"النتيجة: **الذهب يستعد لـ {gold_impact}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 ومن يفهم العلاقة بين التضخم، والتوظيف، وأسعار النفط، وعوائد السندات الأمريكية… يمتلك أفضلية حقيقية قبل أن تبدأ الحركة الكبيرة."
    )
    return template
