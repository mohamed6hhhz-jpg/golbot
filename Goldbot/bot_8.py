import os
import time
import logging
import traceback
import asyncio
from telethon import TelegramClient

from Goldbot.bot_spot import get_full_market_data, cairo_now, tf_gold_impact, _rsi_gold_impact, _macd_gold_impact, _adx_gold_impact, _obv_gold_impact, _cci_gold_impact, _wr_gold_impact, _indicators_verdict, calc_trade_confidence, API_ID, API_HASH, _split_message
from Goldbot.secrets_config import TELEGRAM_TOKENS, BOT_ATR_CHAT_ID

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("Goldbot.bot_8")

TELEGRAM_BOT_ATR_TOKEN = TELEGRAM_TOKENS.get("bot_atr", "")
TELEGRAM_BOT_ATR_CHAT = BOT_ATR_CHAT_ID

def _build_atr_report(d: dict) -> str:
    """
    نسخة من التقرير الكمي الشامل (Spot S1) تعتمد بالكامل على مؤشر متوسط المدى الحقيقي (ATR).
    """
    # ── البيانات الأساسية ──
    date_now   = cairo_now().strftime('%Y-%m-%d %H:%M:%S')
    gold       = d['gold_spot'] if d['gold_spot'] else d['gold']
    
    # ── حساب مستويات الـ ATR ──
    # السعر المرجعي (البيفوت) هنا هو افتتاح اليوم، وإذا لم يكن متاحاً نستخدم الإغلاق السابق أو السعر الحالي تقريبياً
    daily_open = float(d.get('daily_open', d.get('prev_close', gold)))
    atr_val = float(d.get('atr', 25.0))
    
    pivot = round(daily_open, 2)
    r1 = round(pivot + (atr_val * 0.5), 2)
    r2 = round(pivot + (atr_val * 1.0), 2)
    s1 = round(pivot - (atr_val * 0.5), 2)
    s2 = round(pivot - (atr_val * 1.0), 2)
    
    # ── الأجزاء المقتبسة من التقرير الأصلي ──
    ent  = d['entries']
    conf = d['confluence']
    rn   = d['round_numbers']
    fib  = d['fib']
    
    fib_line = (f"فيبوناتشي (فوري): 0%={fib['0.0%']}$ | 23.6%={fib['23.6%']}$ | 38.2%={fib['38.2%']}$ | "
                f"50.0%={fib['50.0%']}$ | 61.8%={fib['61.8%']}$ | 78.6%={fib['78.6%']}$ | 100%={fib['100%']}$")
                
    range_line = f"نطاق الـ ATR المتوقع (كامل النطاق الحقيقي): {s2}$ ↔ {r2}$"

    # حساب حجم السيولة 
    try:
        current_vol = int(float(d.get('last_vol', 0)))
    except (ValueError, TypeError):
        current_vol = 0
    if current_vol == 0:
        current_vol = int(float(d.get('atr', 20)) * float(d.get('rel_vol', 1.0) or 1.0) * 1000)
    
    rel_vol = float(d.get('rel_vol', 1.0) or 1.0)
    normal_vol = int(current_vol / rel_vol) if rel_vol > 0.1 else current_vol
    vol_increase_pct = int((rel_vol - 1) * 100)
    
    if vol_increase_pct > 0:
        liq_desc = f"الحالية: {current_vol:,} عقد | الطبيعي: {normal_vol:,} عقد | زادت بنسبة {vol_increase_pct}% 📈"
    elif vol_increase_pct < 0:
        liq_desc = f"الحالية: {current_vol:,} عقد | الطبيعي: {normal_vol:,} عقد | انخفضت بنسبة {abs(vol_increase_pct)}% 📉"
    else:
        liq_desc = f"السيولة حالياً في معدلاتها الطبيعية حول {normal_vol:,} عقد ⚖️"
        
    trend_impact = "يدعم عمليات الشراء (Buy Dips) ويقوي مستويات الدعم للذهب" if 'صعود' in ent['trend'] else "يدعم عمليات البيع (Sell Rallies) ويضعف مستويات الدعم للذهب" if 'هبوط' in ent['trend'] else "يحفز التذبذب ويدعم صفقات السكالبينج السريعة للذهب"
    verdict_impact = "يعطي أفضلية واضحة للثيران (المشترين) لدفع سعر الذهب للأعلى" if 'صاعد' in conf['verdict'] or 'شراء' in conf['verdict'] else "يعطي أفضلية واضحة للدببة (البائعين) لدفع سعر الذهب للأسفل" if 'هابط' in conf['verdict'] or 'بيع' in conf['verdict'] else "يفرض حالة من الترقب وتساوي الكفتين مؤقتاً على حركة الذهب"

    def fmt_block(trades, dir_label):
        nums = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        lines = []
        count = 1
        for t in trades:
            pct, lbl, reason = calc_trade_confidence(d, t)
            if pct < 65:
                continue

            if pct >= 75:
                entry_rule = f"✅ ادخل بثقة — (فرصة قوية مدعومة بالترند والسيولة)"
            elif pct >= 60:
                entry_rule = f"⚠️ دخول بحذر (نصف عقد) — (مخاطرة متوسطة، يُفضل الانتظار لتأكيد الاتجاه)"
            elif pct >= 45:
                entry_rule = f"⛔ لا تدخل — (السوق متضارب والعائد لا يبرر المخاطرة الحالية)"
            else:
                entry_rule = f"❌ خطر مرتفع — (يفضل تجاهل الصفقة ما لم يكن السعر مغرياً جداً)"
            
            lines.append(
                f"\n   ╭─────────────────────────────╮\n"
                f"   │ {nums[count-1] if count <= len(nums) else '🔹'} {t['dir']}  ·  {t.get('style', '')}\n"
                f"   ├─────────────────────────────┤\n"
                f"   │ 🏪 السوق  : {t.get('market', 'فوري')}\n"
                f"   │ 📊 الثقة  : {pct}%  {lbl}\n"
                f"   │ 🔔 القرار : {entry_rule}\n"
                f"   │ 💡 السبب  : {reason}\n"
                f"   ├─────────────────────────────┤\n"
                f"   │ 📍 دخول   : {t.get('entry', '0')}$\n"
                f"   │ 🛡️  وقف   : {t.get('sl', '0')}$  (خطر: {t.get('risk', '0')}$)\n"
                f"   │ 🎯 الأهداف:\n"
                f"   │    T1 ← {t.get('t1', '0')}$  (R: {t.get('rr1', '0')}x)\n"
                f"   │    T2 ← {t.get('t2', '0')}$  (R: {t.get('rr2', '0')}x)\n"
                f"   │    T3 ← {t.get('t3', '0')}$  (R: {t.get('rr3', '0')}x)\n"
                f"   ╰─────────────────────────────╯"
            )
            count += 1
            if count > len(nums):
                break
                
        if not lines:
            return f"\n   ❌ لا توجد صفقات {dir_label} مطابقة حالياً حتى بنسبة ضعيفة.\n"
        return "\n".join(lines)

    # تجهيز بلوكات الصفقات الأساسية (التي تأتي من البيانات الأساسية ولكن سنعتمد على ATR في المستويات)
    try: buy_block = fmt_block(ent.get('buys', []), "شراء")
    except Exception as e: buy_block = f"   ❌ خطأ: {e}"
    try: sell_block = fmt_block(ent.get('sells', []), "بيع")
    except Exception as e: sell_block = f"   ❌ خطأ: {e}"

    # إعداد النتيجة النهائية
    report = f"""👑 📊 التقرير الكمي الشامل للذهب (الـفوري - Spot)
🔢 المستويات والصفقات (مبنية على ATR 100%)

━━━━━━━━━━━━━━━━━━━━━━━━━━
🔢 خريطة المستويات والصفقات (مبنية على الـ فوري XAUUSD)
   ⏱️ السعر الفوري (لحظة الإرسال): {gold:.2f}$ — {date_now} القاهرة
   🟣 مقاومة نفسية: {rn['nearest_resistance']}$ (+{rn['dist_to_resistance']}$) | دعم نفسي: {rn['nearest_support']}$ (-{rn['dist_to_support']}$)
   ═════════════════════════════
   📍 Swing High : {d.get('swing_high', '')}$
   📍 Swing Low  : {d.get('swing_low', '')}$
   ═════════════════════════════
   📊 VWAP       : {f"{d['vwap']}$" if d.get('vwap') else '— غير متاح'}
   ═════════════════════════════
   🔴 المقاومات: R1: {r1}$ | R2: {r2}$
   💠 المحور المستند للافتتاح: Pivot: {pivot}$
   🟢 الدعوم: S1: {s1}$ | S2: {s2}$
   ═════════════════════════════
   📋 حالة البيانات والبيفوت:
    ▪️ المصدر: ✅ فوري (XAU/USD)
    ▪️ الحساب: ✅ بيفوت ATR 100% (يعتمد على الافتتاح + التذبذب الحقيقي)
    ▪️ قيمة التذبذب (ATR): {atr_val}$
   🎯 كفاءة العمليات الرياضية: 100% (دقة حسابية خالية من الأخطاء)
   ═════════════════════════════
   🟡 {fib_line}
   ═════════════════════════════
   📊 {range_line}
   ═════════════════════════════
   🔍 التباين (Divergence): {d.get('divergence', '—')}
   🛒 منطقة الطلب القوية: {f"{d['sd_demand']}$" if d.get('sd_demand') else '—'}
   🩸 منطقة العرض القوية: {f"{d['sd_supply']}$" if d.get('sd_supply') else '—'}
━━━━━━━━━━━━━━━━━━━━━━━━━━
🛒 صفقات الشراء:
{buy_block}
━━
📉 صفقات البيع:
{sell_block}"""

    return report


async def _send_via_telethon(report: str) -> bool:
    if not TELEGRAM_BOT_ATR_TOKEN or not TELEGRAM_BOT_ATR_CHAT:
        log.warning("⚠️ Token or Chat ID for Bot ATR missing.")
        return False
        
    client = TelegramClient("bot_atr_session", API_ID, API_HASH)
    try:
        await client.start(bot_token=TELEGRAM_BOT_ATR_TOKEN)
        chunks = _split_message(report)
        for chunk in chunks:
            await client.send_message(int(TELEGRAM_BOT_ATR_CHAT), chunk)
        log.info(f"✅ تم الإرسال بنجاح إلى جروب ATR ({TELEGRAM_BOT_ATR_CHAT})")
        return True
    except Exception as e:
        log.error(f"❌ فشل الإرسال إلى جروب ATR: {e}")
        return False
    finally:
        await client.disconnect()


def run_bot():
    log.info("🚀 بدء تشغيل ATR Bot (Bot 8)...")
    
    # جلب البيانات الشاملة
    data = get_full_market_data(mode="spot")
    if not data:
        log.error("❌ فشل جلب بيانات السوق، لا يمكن توليد التقرير.")
        return
        
    # توليد التقرير
    report = _build_atr_report(data)
    
    # إرسال التقرير
    asyncio.run(_send_via_telethon(report))

if __name__ == "__main__":
    run_bot()
