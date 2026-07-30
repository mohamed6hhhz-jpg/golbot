import time
import logging
import traceback
from datetime import datetime, timezone

try:
    from Goldbot.bot_spot import get_full_market_data, cairo_now
    from Goldbot.ai_generator_bot6 import (
        generate_cot_report, generate_supply_demand_report,
        generate_technical_bias_report, generate_standard_breakout_report, generate_box_breakout_report
    )
except ImportError:
    from bot_spot import get_full_market_data, cairo_now
    from ai_generator_bot6 import (
        generate_cot_report, generate_supply_demand_report,
        generate_technical_bias_report, generate_standard_breakout_report, generate_box_breakout_report
    )

log = logging.getLogger(__name__)

TELEGRAM_BOT6_TOKEN = "8607967462:AAGJ649TsE3fdp7Z-7q0Pmk4N0ut27IToVk"
TELEGRAM_BOT6_CHAT = "-1004335538720"

import requests
import socket
import requests.packages.urllib3.util.connection as urllib3_cn

def allowed_gai_family():
    return socket.AF_INET

urllib3_cn.allowed_gai_family = allowed_gai_family

def send_to_bot6_telegram(text: str):
    if not text:
        return
    import httpx
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT6_TOKEN}/sendMessage"
    ip_url = f"https://149.154.167.220/bot{TELEGRAM_BOT6_TOKEN}/sendMessage"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    ip_headers = dict(headers)
    ip_headers["Host"] = "api.telegram.org"
    
    payload = {
        "chat_id": TELEGRAM_BOT6_CHAT,
        "text": text
    }
    
    chat_success = False
    for attempt in range(3):
        try:
            with httpx.Client(timeout=15.0, headers=headers) as client:
                r = client.post(url, json=payload)
                if r.status_code != 200:
                    log.warning(f"⚠️ [Bot 6] خطأ تيليجرام (httpx): {r.text}")
                r.raise_for_status()
                chat_success = True
                log.info("✅ [Bot 6] تم إرسال التقرير للتيليجرام بنجاح (httpx)!")
                break
        except Exception as e:
            log.warning(f"⚠️ [Bot 6] {attempt+1}/3 محاولة httpx فشلت: {e}")
            try:
                r = requests.post(ip_url, json=payload, headers=ip_headers, timeout=15.0, verify=False)
                if r.status_code != 200:
                    log.warning(f"⚠️ [Bot 6] خطأ تيليجرام (IPv4): {r.text}")
                r.raise_for_status()
                chat_success = True
                log.info("✅ [Bot 6] تم الإرسال للتيليجرام بنجاح (Direct IPv4)!")
                break
            except Exception as e2:
                log.warning(f"⚠️ [Bot 6] {attempt+1}/3 محاولة Direct IPv4 فشلت: {e2}")
                try:
                    r = requests.post(url, json=payload, headers=headers, timeout=15.0)
                    if r.status_code != 200:
                        log.warning(f"⚠️ [Bot 6] خطأ تيليجرام (requests): {r.text}")
                    r.raise_for_status()
                    chat_success = True
                    log.info("✅ [Bot 6] تم الإرسال للتيليجرام بنجاح (requests)!")
                    break
                except Exception as e3:
                    log.error(f"❌ [Bot 6] {attempt+1}/3 جميع محاولات الإرسال فشلت: {e3}")
                    import time
                    time.sleep(2)

def run_bot6():
    """
    الحلقة الرئيسية للبوت السادس.
    يربط مع البيانات المشتركة (get_full_market_data) ويولد تقارير مخصصة مثل COT.
    """
    log.info("🚀 [Bot 6] بدء تشغيل البوت السادس...")

    # يمكننا ضبط المؤقتات الخاصة بهذا البوت هنا
    # مثلاً: نشر تقرير COT يوم السبت صباحاً
    last_cot_report_date = None

def process_and_send_bot6(data: dict, last_cot_report_date: str) -> tuple[str, list]:
    """
    يقوم بتوليد قوالب البوت السادس وإرسالها، ويعيد تاريخ آخر COT و قائمة القوالب المُولدة.
    """
    reports_to_send = []
    new_cot_date = last_cot_report_date
    
    try:
        if data and data.get('cot'):
            cot_date = data['cot'].get('report_date')
            if cot_date and cot_date != last_cot_report_date:
                log.info(f"📊 [Bot 6] اكتشاف تقرير COT جديد لتاريخ: {cot_date}. جاري التوليد...")
                cot_report = generate_cot_report(data)
                if cot_report:
                    reports_to_send.append(("تحليل تقرير COT 📊", cot_report))
                    new_cot_date = cot_date
        
        if data:
            # توليد تقرير العرض والطلب
            sd_report = generate_supply_demand_report(data)
            if sd_report:
                reports_to_send.append(("مناطق العرض والطلب 📉📈", sd_report))
                
            # توليد تقرير الميل الفني (الاتجاه)
            bias_report = generate_technical_bias_report(data)
            if bias_report:
                reports_to_send.append(("الاتجاه الفني (الميل السعري) 🧭", bias_report))
                
            # توليد صفقات نظام كسر الأرقام
            breakout_std = generate_standard_breakout_report(data)
            if breakout_std:
                reports_to_send.append(("نظام كسر الأرقام (القياسي) 🔵", breakout_std))
                
            breakout_box = generate_box_breakout_report(data)
            if breakout_box:
                reports_to_send.append(("نظام كسر الأرقام (البديل) 📦", breakout_box))
        
        total_reports = len(reports_to_send)
        for index, (title, content) in enumerate(reports_to_send, 1):
            formatted_message = f"📌 [قالب {index}/{total_reports}] {title}\n\n{content}"
            log.info(f"✅ [Bot 6] جاري إرسال القالب {index}/{total_reports}: {title}")
            send_to_bot6_telegram(formatted_message)
            time.sleep(2)  # فاصل زمني بسيط بين الرسائل لتجنب الحظر
            
    except Exception as e:
        log.error(f"❌ [Bot 6 CRITICAL ERROR] {e}\n{traceback.format_exc()}")
        
    return new_cot_date, reports_to_send

# Removed __main__ since this is now just a module
