with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()
import re

new_s9 = """
def _build_spot_s9(d: dict) -> str:
    \"\"\"9/12 - مصفوفة التداول والاسكالبينج الاحترافي\"\"\"
    nums = _s_nums(d)
    gold, atr, pivot = nums['gold'], nums['atr'], nums['pivot']
    rsi, macd = nums['rsi'], nums['macd']
    r1, r2, r3, s1, s2, s3 = nums['r1'], nums['r2'], nums.get('r3', nums['r2']+atr), nums['s1'], nums['s2'], nums.get('s3', nums['s2']-atr)
    sh, sl = nums['swing_h'], nums['swing_l']
    fib = d.get('fib', {}) or {}

    interest  = float(d.get('interest_rate', 5.25) or 5.25)
    inflation = float(d.get('inflation_est', 3.5) or 3.5)
    ry        = float(d.get('real_yield', 0) or 0) or round(interest - inflation, 2)
    dxy_p     = float(d.get('dxy_p', 100) or 100)
    vix_p     = float(d.get('vix_p', 20) or 20)
    sp500     = float(d.get('sp500_pct', 0) or 0)
    fx        = d.get('fx_sorted', []) or []

    adv = d.get('adv_trades', {}) or {}
    
    # Mathematical Precision Fallbacks (Corrected Directions)
    sb  = adv.get('scalp_buy') or {'entry': round(s1 + (pivot - s1) * 0.2, 2), 'sl': round(s1 - atr * 0.2, 2), 't1': pivot, 't2': round((pivot+r1)/2, 2), 't3': r1}
    ss  = adv.get('scalp_sell') or {'entry': round(r1 - (r1 - pivot) * 0.2, 2), 'sl': round(r1 + atr * 0.2, 2), 't1': pivot, 't2': round((pivot+s1)/2, 2), 't3': s1}
    db  = adv.get('daily_buy') or {'entry': s1, 'sl': s2, 't1': pivot, 't2': r1, 't3': r2}
    ds  = adv.get('daily_sell') or {'entry': r1, 'sl': r2, 't1': pivot, 't2': s1, 't3': s2}
    swb = adv.get('swing_buy') or {'entry': s2, 'sl': s3, 't1': s1, 't2': pivot, 't3': r1}
    sws = adv.get('swing_sell') or {'entry': r2, 'sl': r3, 't1': r1, 't2': pivot, 't3': s1}

    score = 0
    if vix_p > 25: score -= 2
    elif vix_p < 18: score += 2
    if sp500 > 0.5: score += 1
    elif sp500 < -0.5: score -= 1
    if ry > 1.5: score -= 1
    risk_pct = max(30, min(80, 50 + score * 5))
    risk_label = "عالية 🔴" if risk_pct > 60 else "متوسطة 🟡" if risk_pct > 45 else "منخفضة 🟢"

    fib_block = "\\n".join(f"  - **{k}:** {v}" for k, v in fib.items()) if fib else (
        f"  - R1: {r1:.2f}$ | R2: {r2:.2f}$\\n  - S1: {s1:.2f}$ | S2: {s2:.2f}$"
    )
    fx_block = "\\n".join(f"  - **{sym}:** {pct:+.4f}%" for sym, pct in fx[:8]) if fx else "  - بيانات العملات متاحة عند التريجر"

    return (
        "👑 **مؤشر شهية المخاطرة الشامل (Risk Appetite)** 👑\\n━━━━━━━━━━━━━━━━━━━━━━━━━━\\n"
        "🌐 **المسح السعري اللحظي والسيولة:**\\n"
        f"- 💰 **سعر الذهب الحالي:** **{gold:.2f}$**\\n"
        f"- 🎯 **اعلى النطاق:** {sh:.2f}$ | **ادنى النطاق:** {sl:.2f}$\\n"
        f"- 📊 **مؤشر RSI:** {rsi:.2f}\\n"
        f"- 📉 **مؤشر MACD:** {macd:.4f}\\n"
        f"- 📏 **مؤشر ATR:** {atr:.2f}$\\n\\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\\n📈 **الركائز الفنية الأساسية:**\\n"
        "- 🔢 **مستويات فيبوناتشي:**\\n"
        f"{fib_block}\\n"
        f"- 🎯 **المحور:** {pivot:.2f}$ | **R1:** {r1:.2f}$ | **S1:** {s1:.2f}$\\n\\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\\n📊 **الركائز الأساسية (الماكرو والسيولة):**\\n"
        f"- 📉 **معدل التضخم:** {inflation:.2f}%\\n"
        f"- 🏦 **معدل الفائدة:** {interest:.2f}%\\n"
        f"- ⚖️ **العائد الحقيقي:** {ry:.2f}%\\n"
        f"- 🚨 **VIX (مؤشر الخوف):** {vix_p:.2f} ({'مرتفع — تحوط' if vix_p > 25 else 'منخفض — جشع'})\\n"
        f"- 📈 **S&P 500 اليومي:** {sp500:+.2f}%\\n"
        f"- 💵 **مؤشر الدولار (DXY):** {dxy_p:.4f}\\n"
        "- 💱 **قوة العملات:**\\n"
        f"{fx_block}\\n\\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\\n🎯 **مصفوفة استراتيجيات التداول الشاملة (Trading Matrix)** 🎯\\n*(هذه المصفوفة عالية الدقة توضح نقاط الدخول المثالية للسكالبينج والسوينج بناءً على خوارزميات السيولة)*\\n\\n"
        "⚡ **1. السكالبينج (خطف سريع - مخاطرة عالية)**\\n"
        f"🟢 **شراء:** دخول: **{sb.get('entry',0):.2f}$** | الاستوب: **{sb.get('sl',0):.2f}$**\\n"
        f"🎯 الأهداف: {sb.get('t1',0):.2f}$ - {sb.get('t2',0):.2f}$ - {sb.get('t3',0):.2f}$\\n"
        f"🔴 **بيع:** دخول: **{ss.get('entry',0):.2f}$** | الاستوب: **{ss.get('sl',0):.2f}$**\\n"
        f"🎯 الأهداف: {ss.get('t1',0):.2f}$ - {ss.get('t2',0):.2f}$ - {ss.get('t3',0):.2f}$\\n\\n"
        "📅 **2. التداول اليومي (Intraday - مخاطرة متوسطة)**\\n"
        f"🟢 **شراء:** دخول: **{db.get('entry',0):.2f}$** | الاستوب: **{db.get('sl',0):.2f}$**\\n"
        f"🎯 الأهداف: {db.get('t1',0):.2f}$ - {db.get('t2',0):.2f}$\\n"
        f"🔴 **بيع:** دخول: **{ds.get('entry',0):.2f}$** | الاستوب: **{ds.get('sl',0):.2f}$**\\n"
        f"🎯 الأهداف: {ds.get('t1',0):.2f}$ - {ds.get('t2',0):.2f}$\\n\\n"
        "📆 **3. السوينج الاستراتيجي (مخاطرة مضبوطة)**\\n"
        f"🟢 **السوينج الشرائي:** دخول: **{swb.get('entry',0):.2f}$** | الاستوب: **{swb.get('sl',0):.2f}$**\\n"
        f"🎯 الأهداف: {swb.get('t1',0):.2f}$ - {swb.get('t2',0):.2f}$ - {swb.get('t3',0):.2f}$\\n"
        f"🔴 **السوينج البيعي:** دخول: **{sws.get('entry',0):.2f}$** | الاستوب: **{sws.get('sl',0):.2f}$**\\n"
        f"🎯 الأهداف: {sws.get('t1',0):.2f}$ - {sws.get('t2',0):.2f}$ - {sws.get('t3',0):.2f}$\\n\\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\\n⚠️ **ضوابط إدارة المخاطر (Risk Management)** ⚠️\\n"
        f"- 🚨 **التقييم الكمي للمخاطرة الآن:** **{risk_pct:.0f}% ({risk_label})**\\n"
        f"- 💼 **إدارة المحفظة:** يُنصح بحجم مركز لا يتجاوز **{100 - risk_pct:.0f}%** من هامش المحفظة للصفقة الواحدة نظراً للظروف الحالية.\\n\\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\\n💡 **الحكم الاستراتيجي للصفقات**\\n"
        f"بناءً على التقييم الكلي للمخاطرة، التوجه الأفضل للمتداولين {'في ظل هذه المخاطرة المنخفضة هو التداول بثقة مع الاتجاه واستهداف السوينج.' if risk_pct <= 45 else 'الآن هو التداول اللحظي السريع (سكالبينج) لتقليل فترة التعرض للسوق والهروب من التذبذب.' if risk_pct > 60 else 'هو التداول اليومي بحذر والالتزام التام بنقاط الوقف وتأمين الأرباح أولاً بأول.'}"
    )
"""

# Regex substitute the old function with the new one
pattern = re.compile(r'def _build_spot_s9.*?return \(\n.*?\.strip\(\)\n\s*\)\n', re.DOTALL)
# Wait, the old return statement ends with:
#        f"بناءً على التقييم الكلي للمخاطرة، التوجه الأفضل للمتداولين {'في ظل هذه المخاطرة المنخفضة هو التداول بثقة مع الاتجاه' if risk_pct <= 45 else 'الآن هو التداول اللحظي السريع (سكالبينج) لتقليل فترة التعرض للسوق' if risk_pct > 60 else 'هو التداول اليومي بحذر والالتزام التام بنقاط الوقف'}."
#    )

pattern2 = re.compile(r'def _build_spot_s9\(d: dict\) -> str:.*?    \)\n', re.DOTALL)

match = pattern2.search(text)
if match:
    text = text[:match.start()] + new_s9.strip() + "\n\n" + text[match.end():]
    with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Patched successfully")
else:
    print("Could not match the function body!")
