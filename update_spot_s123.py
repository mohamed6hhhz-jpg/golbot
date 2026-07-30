import re

def update_templates(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    new_s1 = r'''def _build_spot_s1(d: dict) -> str:
    """1/12 - الاسعار والفيبوناتشي"""
    nums   = _s_nums(d)
    gold, atr, pivot = nums['gold'], nums['atr'], nums['pivot']
    rsi, macd = nums['rsi'], nums['macd']
    r1, r2, s1, s2 = nums['r1'], nums['r2'], nums['s1'], nums['s2']
    sh, sl = nums['swing_h'], nums['swing_l']
    fib = d.get('fib', {}) or {}
    ctx = d.get('hist_ctx', {}) or {}

    f50  = float(fib.get('50.0%', 0) or 0) or pivot
    f618 = float(fib.get('61.8%', 0) or 0) or s1
    f382 = float(fib.get('38.2%', 0) or 0) or r1

    if gold < f618:
        pos_note = f"الأسعار تتداول تحت مستوى الدعم الذهبي 61.8% من فيبوناتشي ({f618:.2f}$)، مما يشير إلى تصحيح عميق وضغط بيعي قوي."
    elif gold < f50:
        pos_note = f"الأسعار تتداول تحت مستوى التوازن 50.0% ({f50:.2f}$)، مما يضعف الزخم الصعودي ويشير إلى استمرار الهبوط."
    elif gold < f382:
        pos_note = f"الأسعار تختبر مستوى المقاومة الأولي 38.2% ({f382:.2f}$)، اختراقه سيدعم استمرار الزخم الصعودي بقوة."
    else:
        pos_note = f"الأسعار تتداول بثبات فوق مستوى 38.2% ({f382:.2f}$)، مما يؤكد سيطرة المشترين وقوة الاتجاه الصاعد."

    if rsi < 30:
        rsi_note = f"مؤشر القوة النسبية (RSI) عند {rsi:.2f} يعكس حالة **تشبع بيعي عميق** (Oversold) — احتمالية قوية لارتداد سعري."
        recom = f"💡 **إستراتيجية مقترحة:** مراقبة إشارات الانعكاس الشرائية قرب مستويات الدعم ({s1:.2f}$ - {s2:.2f}$)، مع وقف خسارة صارم أسفل {s2:.2f}$."
    elif rsi > 70:
        rsi_note = f"مؤشر القوة النسبية (RSI) عند {rsi:.2f} يعكس حالة **تشبع شرائي مفرط** (Overbought) — احتمالية للتصحيح الهبوطي."
        recom = f"💡 **إستراتيجية مقترحة:** البحث عن فرص بيع عند ملامسة المقاومات ({r1:.2f}$ - {r2:.2f}$)، مع تأمين الصفقات بوقف خسارة أعلى {r2:.2f}$."
    else:
        rsi_note = f"مؤشر القوة النسبية (RSI) عند {rsi:.2f} يستقر في **المنطقة الحيادية** — الزخم الحالي ينتظر محفزات جديدة للكسر."
        recom = f"💡 **إستراتيجية مقترحة:** التداول مع الاختراقات المؤكدة (شراء فوق {r1:.2f}$ أو بيع أسفل {s1:.2f}$)."

    macd_val = d.get('macd_hist', macd) if isinstance(d.get('macd_hist', macd), float) else macd
    macd_note = f"مؤشر MACD يسجل قراءة ({macd_val:.4f})، مما يدعم {'الزخم الهبوطي الحالي 📉' if macd_val < 0 else 'القوة الشرائية الحالية 📈'}."

    fib_lines = "\n".join(
        f"🔸 مستوى {k:<5} : **{v}** {'🎯 (الدعم/المقاومة الأهم)' if k in ('50.0%', '61.8%') else '📍'}"
        for k, v in fib.items()
    ) if fib else f"🔸 لم يتم حساب الفيبوناتشي بدقة (نطاق ATR: دعم {s1:.2f}$ | مقاومة {r1:.2f}$)"

    chg1d = ctx.get('chg_1d', 0) or 0
    pct1d = ctx.get('pct_1d', 0) or 0
    chg7d = ctx.get('chg_7d', 0) or 0
    pct7d = ctx.get('pct_7d', 0) or 0

    return (
        "👑 **التقرير المالي الفني: نظرة شاملة على الفوري (Spot - XAU/USD)** 👑\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📊 **الملخص السعري والمؤشرات الفنية**\n"
        f"💰 **السعر الحالي:** {gold:.2f}$\n"
        f"📏 **نطاق التذبذب اليومي (ATR):** {atr:.2f}$\n"
        f"📉 **أدنى قاع يومي (Swing Low):** {sl:.2f}$\n"
        f"📈 **أعلى قمة يومية (Swing High):** {sh:.2f}$\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⏱️ **أداء السعر التاريخي**\n"
        f"🔹 **التغير اللحظي (اليومي):** {chg1d:+.2f}$ ({pct1d:+.2f}%)\n"
        f"🔹 **التغير التراكمي (الأسبوعي):** {chg7d:+.2f}$ ({pct7d:+.2f}%)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📐 **مستويات التصحيح الذهبية (Fibonacci Retracement)**\n"
        f"{fib_lines}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🛡️ **مناطق العرض والطلب (الدعم والمقاومة)**\n"
        f"🔺 **مستويات المقاومة:** R1: {r1:.2f}$ | R2: {r2:.2f}$\n"
        f"🔻 **مستويات الدعم:** S1: {s1:.2f}$ | S2: {s2:.2f}$\n"
        f"🔄 **مستوى الارتكاز (Pivot Point):** {pivot:.2f}$\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔬 **التحليل الحركي والاتجاهي**\n"
        f"📌 {pos_note}\n"
        f"📌 {rsi_note}\n"
        f"📌 {macd_note}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📝 **خلاصة القرار المالي**\n"
        f"{recom}\n"
        "⚠️ *تنويه: الإدارة الصارمة للمخاطر هي مفتاح البقاء في الأسواق اللامركزية.*"
    )'''

    new_s2 = r'''def _build_spot_s2(d: dict) -> str:
    """2/12 - تحليل الاطارات الزمنية"""
    nums = _s_nums(d)
    gold, atr, pivot = nums['gold'], nums['atr'], nums['pivot']
    rsi, macd = nums['rsi'], nums['macd']
    r1, r2, s1, s2 = nums['r1'], nums['r2'], nums['s1'], nums['s2']

    tf15 = d.get('tf_15m', {}) or {}
    tf_h = d.get('tf_hourly', {}) or {}
    tf_d = d.get('tf_daily', {}) or {}
    tf_w = d.get('tf_weekly', {}) or {}
    tf_m = d.get('tf_monthly', {}) or {}

    def bias_ar(tf):
        if not tf: return "محايد ⚪"
        b = str(tf.get('bias', ''))
        if 'صعودي' in b or 'bull' in b.lower(): return "صاعد 🟢"
        if 'هبوطي' in b or 'bear' in b.lower(): return "هابط 🔴"
        return "عرضي 🟡"

    def tf_rsi(tf): return float(tf.get('rsi', rsi) or rsi) if tf else rsi

    piv_h  = float(tf_h.get('pivot', 0) or 0) or pivot
    piv_d  = float(tf_d.get('pivot', 0) or 0) or pivot
    piv_w  = float(tf_w.get('pivot', 0) or 0) or round(pivot + atr * 0.5, 2)
    piv_mo = float(tf_m.get('pivot', 0) or 0) or round(pivot + atr * 1.5, 2)

    b15 = bias_ar(tf15); bh = bias_ar(tf_h); bd = bias_ar(tf_d); bw = bias_ar(tf_w); bm = bias_ar(tf_m)
    rsi15 = tf_rsi(tf15); rsih = tf_rsi(tf_h); rsid = tf_rsi(tf_d)

    ph = "أدنى 🔴" if gold < piv_h else "أعلى 🟢"
    pd = "أدنى 🔴" if gold < piv_d else "أعلى 🟢"
    pw = "أدنى 🔴" if gold < piv_w else "أعلى 🟢"
    pm = "أدنى 🔴" if gold < piv_mo else "أعلى 🟢"

    if gold < pivot:
        recom_buy  = f"اقتناص فرصة الارتداد من {s1:.2f}$ لاستهداف {pivot:.2f}$ (وقف الخسارة إغلاق تحت {s2:.2f}$)."
        recom_sell = f"الاستمرار في الاتجاه الهابط من {pivot:.2f}$ لاستهداف {s1:.2f}$ و {s2:.2f}$ (وقف الخسارة إغلاق فوق {r1:.2f}$)."
    else:
        recom_buy  = f"الاستمرار في الاتجاه الصاعد من {pivot:.2f}$ لاستهداف {r1:.2f}$ و {r2:.2f}$ (وقف الخسارة إغلاق تحت {s1:.2f}$)."
        recom_sell = f"اقتناص فرصة التصحيح من {r1:.2f}$ لاستهداف {pivot:.2f}$ (وقف الخسارة إغلاق فوق {r2:.2f}$)."

    return (
        "🕒 **التحليل الميكانيكي الشامل للإطارات الزمنية (Timeframes Analysis)** 🕒\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🧭 **البوصلة الحالية للذهب (الزخم العام)**\n"
        f"السعر اللحظي يتداول عند **{gold:.2f}$**، مستقراً **{'فوق' if gold >= pivot else 'تحت'}** مستوى البيفوت المركزي ({pivot:.2f}$).\n"
        f"استمرار السعر في هذا النطاق يرجح السيطرة **{'الشرائية 🟢' if gold >= pivot else 'البيعية 🔴'}** في المدى القصير.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔬 **فحص الهيكل الزمني (الترند المتعدد)**\n"
        f"⚡ **إطار 15 دقيقة:** الاتجاه {b15} | RSI: {rsi15:.1f}\n"
        f"⏱️ **إطار الساعة:** الاتجاه {bh} | السعر {ph} بيفوت ({piv_h:.2f}$) | RSI: {rsih:.1f}\n"
        f"📅 **إطار اليومي:** الاتجاه {bd} | السعر {pd} بيفوت ({piv_d:.2f}$) | RSI: {rsid:.1f}\n"
        f"📆 **إطار الأسبوعي:** الاتجاه {bw} | السعر {pw} بيفوت ({piv_w:.2f}$)\n"
        f"🗓️ **إطار الشهري:** الاتجاه {bm} | السعر {pm} بيفوت ({piv_mo:.2f}$)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚖️ **موازين القوى (الدعم والمقاومة الحاسمة)**\n"
        f"🔴 **المقاومات الشرسة:** R1 ({r1:.2f}$) ➖ R2 ({r2:.2f}$)\n"
        f"🔵 **مستوى التعادل (البيفوت):** {pivot:.2f}$\n"
        f"🟢 **الدعوم الصلبة:** S1 ({s1:.2f}$) ➖ S2 ({s2:.2f}$)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 **خارطة الطريق التكتيكية**\n"
        f"🛒 **سيناريو الشراء:** {recom_buy}\n"
        f"📉 **سيناريو البيع:** {recom_sell}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ **مؤشر المخاطر والتقلبات**\n"
        f"معدل التقلب المتوقع (ATR) يبلغ **{atr:.2f}$** يومياً.\n"
        f"حالة مؤشر RSI ({rsi:.2f}): **{'خطورة عالية (انعكاس وشيك) 🚨' if rsi < 30 or rsi > 70 else 'استقرار نسبي (مناسب لاتباع الاتجاه) ⚖️'}**"
    )'''

    new_s3 = r'''def _build_spot_s3(d: dict) -> str:
    """3/12 - صفقات زيرو انعكاس"""
    nums = _s_nums(d)
    gold, atr, pivot = nums['gold'], nums['atr'], nums['pivot']
    rsi, macd = nums['rsi'], nums['macd']
    r1, r2, s1, s2 = nums['r1'], nums['r2'], nums['s1'], nums['s2']
    sh, sl = nums['swing_h'], nums['swing_l']
    fib = d.get('fib', {}) or {}

    rb = _s_trades(d, 'rev_buy')
    rs = _s_trades(d, 'rev_sell')

    fib_lines = "\n".join(f"🔸 {k:<5} : **{v}**" for k, v in fib.items()) if fib else (
        f"🔸 S1: {s1:.2f}$ | S2: {s2:.2f}$\n🔸 R1: {r1:.2f}$ | R2: {r2:.2f}$"
    )

    rsi_read = ('حالة تشبع بيعي حاد (Oversold) — ارتداد شرائي قوي متوقع 📈' if rsi < 30
                else 'حالة تشبع شرائي حاد (Overbought) — تصحيح هبوطي قوي متوقع 📉' if rsi > 70
                else f'منطقة سيولة محايدة ({rsi:.2f}) — ينتظر سيطرة أحد الطرفين ⚖️')
    
    macd_val = d.get('macd_hist', macd) if isinstance(d.get('macd_hist', macd), float) else macd
    macd_read = f'({macd_val:.4f}) يشير إلى ضغط بيعي 🔴' if macd_val < 0 else f'({macd_val:.4f}) يشير إلى زخم شرائي 🟢'

    return (
        "🔍 **تحليل البيانات العميق وهندسة زيرو انعكاس (Zero Drawdown)** 🔍\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📊 **التشخيص الدقيق للسوق (الفوري - Spot)**\n"
        f"💰 **نقطة التمركز الحالية (السعر):** {gold:.2f}$\n"
        f"🔄 **محور الدوران الرئيسي (Pivot):** {pivot:.2f}$\n"
        f"📉 **أدنى قاع يومي (Swing L):** {sl:.2f}$\n"
        f"📈 **أعلى قمة يومية (Swing High):** {sh:.2f}$\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🧬 **القراءة المتقدمة للمؤشرات الحيوية**\n"
        f"📡 **مؤشر (RSI):** {rsi_read}\n"
        f"📡 **مؤشر (MACD):** {macd_read}\n"
        f"📏 **حجم التقلب اللحظي (ATR):** {atr:.2f}$ (يعكس متوسط الحركة الكامنة)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📐 **هندسة التراجعات (مستويات فيبوناتشي)**\n"
        f"{fib_lines}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 **التوصيات الذهبية: إستراتيجية الزيرو انعكاس (Counter-trend Sniper)** 🎯\n"
        "*(تستهدف هذه الإستراتيجية اصطياد الانعكاس من الحواف المتطرفة بانعدام الانعكاس السلبي تقريباً)*\n\n"
        f"🛒 **شراء قناص (من القاع الممتد):**\n"
        f"   🔹 **الدخول:** {rb.get('entry',s2):.2f}$\n"
        f"   🛑 **وقف الخسارة الميكانيكي:** {rb.get('sl',s2-atr*0.3):.2f}$ (مخاطرة: {rb.get('risk',atr*0.3):.2f}$)\n"
        f"   🎯 **الأهداف بالترتيب:** {rb.get('t1',s1):.2f}$ ➖ {rb.get('t2',pivot):.2f}$ ➖ {rb.get('t3',r1):.2f}$\n\n"
        f"📉 **بيع قناص (من القمة الممتدة):**\n"
        f"   🔻 **الدخول:** {rs.get('entry',r2):.2f}$\n"
        f"   🛑 **وقف الخسارة الميكانيكي:** {rs.get('sl',r2+atr*0.3):.2f}$ (مخاطرة: {rs.get('risk',atr*0.3):.2f}$)\n"
        f"   🎯 **الأهداف بالترتيب:** {rs.get('t1',r1):.2f}$ ➖ {rs.get('t2',pivot):.2f}$ ➖ {rs.get('t3',s1):.2f}$\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ **الخلاصة الإستراتيجية:** الدخول الانعكاسي (زيرو انعكاس) يتطلب صرامة تامة في الالتزام بنقطة الدخول المتطرفة المحددة أعلاه، وعدم الاستعجال لتجنب مصيدة السيولة."
    )'''

    # Using re.sub to replace the 3 functions
    
    pat1 = r'def _build_spot_s1\(d: dict\) -> str:.*?def _build_spot_s2'
    content = re.sub(pat1, new_s1 + '\n\n\ndef _build_spot_s2', content, flags=re.DOTALL)
    
    pat2 = r'def _build_spot_s2\(d: dict\) -> str:.*?def _build_spot_s3'
    content = re.sub(pat2, new_s2 + '\n\n\ndef _build_spot_s3', content, flags=re.DOTALL)
    
    pat3 = r'def _build_spot_s3\(d: dict\) -> str:.*?def _build_spot_s4'
    content = re.sub(pat3, new_s3 + '\n\n\ndef _build_spot_s4', content, flags=re.DOTALL)

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

update_templates('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py')
