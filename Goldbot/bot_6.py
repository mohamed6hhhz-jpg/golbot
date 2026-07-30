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
TELEGRAM_BOT6_CHAT = "-5584357836"

import requests
import socket
import requests.packages.urllib3.util.connection as urllib3_cn

def allowed_gai_family():
    """إجبار بايثون على استخدام IPv4 فقط لتفادي مشاكل تعليق شبكات IPv6 في HuggingFace عند الاتصال بـ api.telegram.org"""
    return socket.AF_INET

urllib3_cn.allowed_gai_family = allowed_gai_family
def send_to_bot6_telegram(text: str):
    if not text:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT6_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_BOT6_CHAT,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code != 200:
            log.error(f"❌ [Bot 6] فشل الإرسال للتيليجرام: {r.text}")
        else:
            log.info("✅ [Bot 6] تم إرسال التقرير للتيليجرام بنجاح!")
    except Exception as e:
        log.error(f"❌ [Bot 6] خطأ أثناء الإرسال: {e}")

def run_bot6():
    """
    الحلقة الرئيسية للبوت السادس.
    يربط مع البيانات المشتركة (get_full_market_data) ويولد تقارير مخصصة مثل COT.
    """
    log.info("🚀 [Bot 6] بدء تشغيل البوت السادس...")

    # يمكننا ضبط المؤقتات الخاصة بهذا البوت هنا
    # مثلاً: نشر تقرير COT يوم السبت صباحاً
    last_cot_report_date = None

    while True:
        try:
            now_cairo = cairo_now()
            today = now_cairo.date()
            weekday = now_cairo.weekday()
            
            # مثال: إصدار تقرير COT مرة واحدة كل أسبوع (مثلاً يوم السبت حيث تكون البيانات قد صدرت الجمعة مساءً)
            # أو يمكن إصداره بمجرد تغير تاريخ التقرير.
            
            # لجلب أحدث الأرقام الحقيقية (بما فيها COT الذي أضفناه)
            data = get_full_market_data(mode='spot')
            
            if data and data.get('cot'):
                cot_date = data['cot'].get('report_date')
                
                # إذا كان لدينا تقرير COT جديد لم ننشره بعد
                if cot_date and cot_date != last_cot_report_date:
                    log.info(f"📊 [Bot 6] اكتشاف تقرير COT جديد لتاريخ: {cot_date}. جاري التوليد...")
                    cot_report = generate_cot_report(data)
                    
                    if cot_report:
                        log.info(f"✅ [Bot 6] تم توليد تقرير COT بنجاح:\n{cot_report[:100]}...")
                        send_to_bot6_telegram(cot_report)
                        
                        last_cot_report_date = cot_date
            
            if data:
                # توليد تقرير العرض والطلب
                sd_report = generate_supply_demand_report(data)
                if sd_report:
                    log.info(f"✅ [Bot 6] تم توليد تقرير العرض والطلب بنجاح")
                    send_to_bot6_telegram(sd_report)
                    
                # توليد تقرير الميل الفني (الاتجاه)
                bias_report = generate_technical_bias_report(data)
                if bias_report:
                    log.info(f"✅ [Bot 6] تم توليد تقرير الاتجاه الفني بنجاح")
                    send_to_bot6_telegram(bias_report)
                    
                # توليد صفقات نظام كسر الأرقام
                breakout_std = generate_standard_breakout_report(data)
                breakout_box = generate_box_breakout_report(data)
                if breakout_std and breakout_box:
                    log.info(f"✅ [Bot 6] تم توليد تقارير نظام كسر الأرقام بنجاح")
                    send_to_bot6_telegram(breakout_std)
                    send_to_bot6_telegram(breakout_box)
            # ننتظر 15 دقيقة قبل فحص السوق مرة أخرى للبوت 6 (يمكن تعديله)
            time.sleep(15 * 60)
        except Exception as e:
            log.error(f"❌ [Bot 6 CRITICAL ERROR] {e}\n{traceback.format_exc()}")
            time.sleep(60)

if __name__ == "__main__":
    run_bot6()
