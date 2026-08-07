import time
import logging
from datetime import datetime
import os
import sys

# إعداد اللوجز
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("Goldbot.bot_8")

try:
    import pytz
    CAIRO_TZ = pytz.timezone("Africa/Cairo")
except ImportError:
    from datetime import timezone, timedelta
    CAIRO_TZ = timezone(timedelta(hours=3))

def cairo_now() -> datetime:
    return datetime.now(CAIRO_TZ)

def calc_algo_pivot_atr(data: dict) -> dict:
    """
    يطبق القواعد الخوارزمية الأربعة الذهبية لدمج البيفوت مع الـ ATR.
    """
    spot = data.get("spot_price", 0) or data.get("gold", 0)
    atr = data.get("atr", 0)
    h = data.get("prev_high", 0)
    l = data.get("prev_low", 0)
    c = data.get("prev_close", 0)
    
    if not (h > 0 and l > 0 and c > 0 and atr > 0):
        return {}
        
    p = (h + l + c) / 3
    r1 = (2 * p) - l
    r2 = p + (h - l)
    r3 = r1 + (h - l)
    
    s1 = (2 * p) - h
    s2 = p - (h - l)
    s3 = s1 - (h - l)
    
    # Rule 1: Zones (±10% ATR)
    z_margin = atr * 0.10
    # Rule 2: Dynamic Stop Loss (30% ATR)
    sl_margin = atr * 0.30
    # Rule 3: Breakout Filter (15% ATR)
    bo_margin = atr * 0.15
    # Rule 4: Max TP Distance (100% ATR)
    max_tp_dist = atr
    
    def _build_level_data(level_price: float, is_resistance: bool) -> dict:
        zone_low = round(level_price - z_margin, 2)
        zone_high = round(level_price + z_margin, 2)
        
        if is_resistance:
            # بالنسبة للمقاومة (بيع أو كسر)
            sl = round(level_price + sl_margin, 2)  # الستوب للمركز البيعي من هنا
            breakout_confirm = round(level_price + bo_margin, 2) # تأكيد اختراق المقاومة (شراء)
            target_down = round(level_price - max_tp_dist, 2) # هدف البيع الأقصى
            return {
                "price": round(level_price, 2),
                "zone": (zone_low, zone_high),
                "sl": sl,
                "breakout_confirm": breakout_confirm,
                "max_target": target_down
            }
        else:
            # بالنسبة للدعم (شراء أو كسر)
            sl = round(level_price - sl_margin, 2) # الستوب للمركز الشرائي من هنا
            breakout_confirm = round(level_price - bo_margin, 2) # تأكيد كسر الدعم (بيع)
            target_up = round(level_price + max_tp_dist, 2) # هدف الشراء الأقصى
            return {
                "price": round(level_price, 2),
                "zone": (zone_low, zone_high),
                "sl": sl,
                "breakout_confirm": breakout_confirm,
                "max_target": target_up
            }

    algo = {
        "atr": round(atr, 2),
        "pivot": _build_level_data(p, False), # المحور ممكن يكون دعم أو مقاومة، نعتبره نقطة ارتكاز
        "r1": _build_level_data(r1, True),
        "r2": _build_level_data(r2, True),
        "r3": _build_level_data(r3, True),
        "s1": _build_level_data(s1, False),
        "s2": _build_level_data(s2, False),
        "s3": _build_level_data(s3, False),
    }
    
    return algo

def build_template_algo_pivot_atr(data: dict, algo: dict) -> str:
    """
    يبني القالب الاحترافي للبوت الثامن (المعادلات الخوارزمية).
    """
    spot_str = f"{data.get('spot_price', 0):.2f}$" if data.get("spot_price") else "غير متاح"
    send_time = data.get("send_time", cairo_now().strftime("%I:%M %p"))
    atr = algo.get("atr", 0)
    
    if not algo or atr == 0:
        return "⚠️ بيانات ATR أو مستويات البيفوت غير متوفرة لحساب القالب الخوارزمي."

    def fmt_zone(z: tuple) -> str:
        return f"{z[0]:.2f}$ ↔ {z[1]:.2f}$"
        
    p = algo['pivot']
    r1 = algo['r1']
    s1 = algo['s1']

    report = f"""👑 📊 التقرير الخوارزمي الذكي للذهب (البيفوت × ATR)
🔢 خوارزمية التداول المؤسسي (الفوري XAUUSD)

━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ السعر الفوري (لحظة الإرسال): {spot_str} — {send_time} القاهرة
⚡ طاقة السوق اليومية (ATR): {atr}$
═════════════════════════════
🛡️ القاعدة 1: تحويل الخطوط إلى مناطق سيولة (±10% ATR)
   ▪️ منطقة (R1) للبيع: {fmt_zone(r1['zone'])}
   ▪️ منطقة (Pivot) للمحور: {fmt_zone(p['zone'])}
   ▪️ منطقة (S1) للشراء: {fmt_zone(s1['zone'])}
═════════════════════════════
🛑 القاعدة 2: وقف الخسارة الديناميكي (30% ATR للحماية من ضرب الستوب)
   ▪️ ستوب بيع (R1): إغلاق أعلى {r1['sl']}$
   ▪️ ستوب شراء (S1): إغلاق أسفل {s1['sl']}$
═════════════════════════════
🚀 القاعدة 3: فلتر الاختراق الكاذب (تأكيد 15% ATR)
   ▪️ شراء باختراق R1: فقط إذا أغلق وتجاوز {r1['breakout_confirm']}$
   ▪️ بيع بكسر S1: فقط إذا أغلق وانخفض عن {s1['breakout_confirm']}$
═════════════════════════════
🎯 القاعدة 4: الأهداف المرنة (حد أقصى يعادل طاقة السوق ATR)
   ▪️ أقصى هدف شرائي من S1: {s1['max_target']}$
   ▪️ أقصى هدف بيعي من R1: {r1['max_target']}$
━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 خلاصة التداول:
النظام يمنع الدخول المبكر عبر (مناطق السيولة)، يحميك من ذيول الشموع عبر (الستوب الديناميكي)، ويفلتر الاختراقات الوهمية لتجنب فخاخ صناع السوق.
"""
    return report

def process_and_send_bot8():
    """
    دالة التشغيل الرئيسية للبوت الثامن.
    """
    log.info("🚀 [Bot8] بدء توليد التقرير الخوارزمي الذكي...")
    try:
        from Goldbot.bot_daily_levels import fetch_daily_data
        from Goldbot.bot_spot import _http_fallback_send
        from Goldbot.secrets_config import TELEGRAM_TOKENS, BOT8_CHAT_ID
    except ImportError:
        try:
            from bot_daily_levels import fetch_daily_data
            from bot_spot import _http_fallback_send
            from secrets_config import TELEGRAM_TOKENS, BOT8_CHAT_ID
        except ImportError:
            log.error("❌ فشل استدعاء الملفات المطلوبة في Bot 8.")
            return False

    token = TELEGRAM_TOKENS.get("bot8")
    if not token or not BOT8_CHAT_ID:
        log.error("❌ التوكن أو جروب Bot8 غير معرف.")
        return False

    data = fetch_daily_data()
    if not data:
        log.error("❌ فشل جلب البيانات في Bot 8.")
        return False

    algo = calc_algo_pivot_atr(data)
    if not algo:
        log.error("❌ فشل حساب الخوارزمية في Bot 8.")
        return False

    template = build_template_algo_pivot_atr(data, algo)
    
    # الإرسال للجروب
    success = _http_fallback_send(template, token, [BOT8_CHAT_ID])
    if success:
        log.info("✅ [Bot8] تم إرسال القالب الخوارزمي بنجاح!")
    else:
        log.error("❌ [Bot8] فشل في إرسال القالب.")
    
    return success

if __name__ == "__main__":
    process_and_send_bot8()
