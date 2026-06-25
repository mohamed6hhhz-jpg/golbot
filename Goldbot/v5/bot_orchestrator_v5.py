import asyncio
import logging
import os
import time

from Goldbot.v5.config import TARGET_CHATS_SPOT, TARGET_CHATS_FUTURES
from Goldbot.v5.data_fetcher import fetch_all_data_v5
from Goldbot.v5.ai_generator import generate_ai_section
from Goldbot.v5.bot_spot_core import build_multi_timeframe_context
from Goldbot.v5.telegram_publisher import publish_report_to_telegram

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
log = logging.getLogger(__name__)

# Semaphores to prevent Groq API rate limits when generating 20+ reports
concurrent_requests = asyncio.Semaphore(2)

async def generate_section_async(sec_id: str, sec_title: str, context: str, is_spot: bool):
    async with concurrent_requests:
        # We run the synchronous Groq call in a thread pool to avoid blocking asyncio
        loop = asyncio.get_running_loop()
        rep = await loop.run_in_executor(None, generate_ai_section, sec_id, sec_title, context, is_spot)
        # Small delay to respect rate limits
        await asyncio.sleep(2)
        return sec_title, rep

async def orchestrate_v5():
    log.info("🚀 بدء أضخم محرك مالي (Orchestrator V5)...")
    
    twelvedata_key = os.environ.get("TWELVEDATA_API_KEY", "")
    
    # 1. Fetch unified data once
    log.info("📡 جلب البيانات المتكاملة (ماكرو، فوري، آجل، حيتان)...")
    data = fetch_all_data_v5(twelvedata_key)
    if not data or 'spot_price' not in data or 'futures_price' not in data:
        log.error("❌ فشل في جلب البيانات الجذرية.")
        return

    macro = data['macro']
    
    # Calculate mathematically precise levels to prevent hallucinations
    def get_levels(df_1d):
        if df_1d is None or df_1d.empty: return "لا تتوفر مستويات دقيقة."
        last_row = df_1d.iloc[-2] if len(df_1d) > 1 else df_1d.iloc[-1]
        h, l, c = last_row['High'], last_row['Low'], last_row['Close']
        pivot = (h + l + c) / 3
        r1 = (2 * pivot) - l
        r2 = pivot + (h - l)
        s1 = (2 * pivot) - h
        s2 = pivot - (h - l)
        fib_38 = h - (h - l) * 0.382
        fib_61 = h - (h - l) * 0.618
        return f"Pivot: {pivot:.2f}$ | R1: {r1:.2f}$ | R2: {r2:.2f}$ | S1: {s1:.2f}$ | S2: {s2:.2f}$ | Fib38: {fib_38:.2f}$ | Fib61: {fib_61:.2f}$"
        
    spot_levels = get_levels(data['spot_dfs'].get('1d'))
    futures_levels = get_levels(data['futures_dfs'].get('1d'))
    
    # 2. Build Contexts
    spot_context = f"""
    -- البيانات الاقتصادية --
    السعر الفوري الحالي: {data['spot_price']}$
    التضخم السنوي: {macro.get('inflation_annual', 2.5)}%
    الفائدة الفيدرالية: {macro.get('fed_funds_rate', 5.25)}%
    عائد 10 سنوات: {macro.get('yield_10y', 4.2)}%
    عائد 30 سنة: {macro.get('yield_30y', 4.5)}%
    العائد الحقيقي: {macro.get('real_yield', 2.75)}%
    مؤشر الدولار: {macro.get('dxy', 104.5)}
    
    -- سيولة الحيتان (الفوري) --
    الضخ: {data['spot_whales']['recent_injection_dir']}
    سيولة بيعية: {data['spot_whales']['sell_liquidity_zones']}
    سيولة شرائية: {data['spot_whales']['buy_liquidity_zones']}
    
    -- المستويات الرياضية الدقيقة للفوري --
    {spot_levels}
    
    -- التحليل الفني متعدد الأطر --
    {build_multi_timeframe_context(data['spot_dfs'])}
    """
    
    futures_context = f"""
    -- البيانات الاقتصادية --
    سعر الآجل الحالي: {data['futures_price']}$
    التضخم السنوي: {macro.get('inflation_annual', 2.5)}%
    الفائدة الفيدرالية: {macro.get('fed_funds_rate', 5.25)}%
    عائد 10 سنوات: {macro.get('yield_10y', 4.2)}%
    عائد 30 سنة: {macro.get('yield_30y', 4.5)}%
    العائد الحقيقي: {macro.get('real_yield', 2.75)}%
    مؤشر الدولار: {macro.get('dxy', 104.5)}
    
    -- سيولة الحيتان (الآجل) --
    الضخ: {data['futures_whales']['recent_injection_dir']}
    سيولة بيعية: {data['futures_whales']['sell_liquidity_zones']}
    سيولة شرائية: {data['futures_whales']['buy_liquidity_zones']}
    
    -- المستويات الرياضية الدقيقة للآجل --
    {futures_levels}
    
    -- التحليل الفني متعدد الأطر --
    {build_multi_timeframe_context(data['futures_dfs'])}
    """

    sections_to_gen = [
        ("macro", "التقرير الاقتصادي"),
        ("whales_institutions", "الحيتان والمؤسسات"),
        ("gold_strength", "قوة الذهب"),
        ("trend_report", "الاتجاه اليومي"),
        ("levels_fibonacci", "مستويات الفيبوناتشي"),
        ("trade_zero_inikass", "زيرو انعكاس"),
        ("trade_high_lot", "اللوت العالي"),
        ("trade_scalping", "السكالبينج"),
        ("trade_swing", "السوينج")
    ]

    # 3. Generate Spot Reports
    log.info("🤖 توليد 9 تقارير للفوري...")
    spot_tasks = [generate_section_async(sid, title, spot_context, True) for sid, title in sections_to_gen]
    spot_results = await asyncio.gather(*spot_tasks)
    
    # 4. Generate Futures Reports
    log.info("🤖 توليد 9 تقارير للآجل...")
    futures_tasks = [generate_section_async(sid, title, futures_context, False) for sid, title in sections_to_gen]
    futures_results = await asyncio.gather(*futures_tasks)

    # 5. Build Grand Conclusion
    log.info("🎯 بناء الخلاصة النهائية المشتركة...")
    grand_context = f"""
    -- ملخص الفوري --
    السعر: {data['spot_price']}$
    نتائج التحليل: {[r[1][:150] for r in spot_results]}...
    
    -- ملخص الآجل --
    السعر: {data['futures_price']}$
    نتائج التحليل: {[r[1][:150] for r in futures_results]}...
    """
    
    grand_conclusion = await generate_section_async("final_conclusion", "الخلاصة المركزية", grand_context, True)
    
    # 6. Build and Publish Separate Reports
    spot_full_report = "="*50 + "\n🔥 تقارير الفوري 🔥\n" + "="*50 + "\n"
    for t, r in spot_results:
        spot_full_report += f"\n[{t}]\n{r}\n"
    spot_full_report += "\n" + "="*50 + "\n🎯 الخلاصة النهائية 🎯\n" + "="*50 + "\n"
    spot_full_report += grand_conclusion[1]
        
    futures_full_report = "="*50 + "\n🔥 تقارير الآجل 🔥\n" + "="*50 + "\n"
    for t, r in futures_results:
        futures_full_report += f"\n[{t}]\n{r}\n"
    futures_full_report += "\n" + "="*50 + "\n🎯 الخلاصة النهائية 🎯\n" + "="*50 + "\n"
    futures_full_report += grand_conclusion[1]

    with open("V5_GRAND_REPORT_SPOT.txt", "w", encoding="utf-8") as f:
        f.write(spot_full_report)
    with open("V5_GRAND_REPORT_FUTURES.txt", "w", encoding="utf-8") as f:
        f.write(futures_full_report)

    log.info("✅ اكتمل توليد الجيل الخامس! جاري النشر لتيليجرام...")
    
    # Send Spot Report
    if TARGET_CHATS_SPOT:
        await publish_report_to_telegram(spot_full_report, TARGET_CHATS_SPOT)
        
    # Send Futures Report
    if TARGET_CHATS_FUTURES:
        await publish_report_to_telegram(futures_full_report, TARGET_CHATS_FUTURES)

async def main_loop():
    while True:
        try:
            await orchestrate_v5()
        except Exception as e:
            log.error(f"❌ خطأ فادح في دورة التشغيل: {e}")
        
        log.info("⏳ انتظار 4 ساعات للدورة القادمة...")
        await asyncio.sleep(4 * 3600)

if __name__ == "__main__":
    asyncio.run(main_loop())
