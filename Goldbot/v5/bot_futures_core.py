import asyncio
import logging
from Goldbot.v5.data_fetcher import fetch_all_data_v5
from Goldbot.v5.ai_generator import generate_ai_section
from Goldbot.v5.config import GROQ_API_KEY
from Goldbot.v5.indicators import calc_rsi, calc_macd, calc_ema

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
log = logging.getLogger(__name__)

def build_multi_timeframe_context(dfs: dict) -> str:
    """Builds a technical summary for all 9 timeframes."""
    lines = []
    for tf, df in dfs.items():
        if df is None or df.empty or len(df) < 200:
            lines.append(f"الفريم [{tf}]: لا توجد بيانات كافية")
            continue
            
        rsi = calc_rsi(df['Close'].values, 14)
        macd, sig, _ = calc_macd(df['Close'].values)
        ema50 = calc_ema(df['Close'].values, 50)
        ema200 = calc_ema(df['Close'].values, 200)
        
        trend = "صاعد" if ema50 > ema200 else "هابط"
        
        lines.append(f"الفريم [{tf}]: RSI={rsi:.1f} | الاتجاه(50vs200)={trend} | MACD={macd:.1f} (Signal: {sig:.1f})")
    
    return "\n".join(lines)

async def run_futures_v5():
    log.info("🚀 بدء تشغيل Goldbot V5 (Futures Core - Phase 2)...")
    
    import os
    twelvedata_key = os.environ.get("TWELVEDATA_API_KEY", "")
    
    data = fetch_all_data_v5(twelvedata_key)
    if not data or 'futures_price' not in data:
        log.error("❌ فشل جلب البيانات للآجل.")
        return
        
    futures_price = data['futures_price']
    macro = data['macro']
    whales = data['futures_whales']
    
    tf_context = build_multi_timeframe_context(data['futures_dfs'])
    
    context = f"""
    -- البيانات الاقتصادية والحيتان --
    السعر الحالي: {futures_price}$
    العائد الحقيقي: {macro['real_yield']}%
    سيولة الحيتان: {whales['recent_injection_dir']}
    مناطق سيولة بيعية: {whales['sell_liquidity_zones']}
    مناطق سيولة شرائية: {whales['buy_liquidity_zones']}
    
    -- التحليل الفني متعدد الأطر (من 5 دقائق إلى شهر) --
    {tf_context}
    """

    sections_to_generate = [
        ("trade_zero_inikass", "صفقات زيرو انعكاس"),
        ("trade_high_lot", "صفقات اللوت العالي"),
        ("trade_scalping", "السكالبينج"),
        ("trade_swing", "السوينج")
    ]
    
    reports = []
    for sec_id, sec_title in sections_to_generate:
        log.info(f"🤖 جاري توليد {sec_title}...")
        rep = generate_ai_section(sec_id, sec_title, context, is_spot=False)
        reports.append(rep)
        
    with open("test_reports_futures.txt", "w", encoding="utf-8") as f:
        f.write("\n" + "="*50 + "\n")
        for r in reports:
            f.write(r + "\n")
            f.write("="*50 + "\n")
    log.info("تم حفظ التقارير في test_reports_futures.txt")

if __name__ == "__main__":
    asyncio.run(run_futures_v5())
