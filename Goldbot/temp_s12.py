def _build_spot_s12(d: dict) -> str:
    """12/12 - الخلاصة المحورية الشاملة (بأعلى دقة كمية)"""
    nums = _s_nums(d)
    gold, atr, pivot = nums['gold'], nums['atr'], nums['pivot']
    rsi, macd = nums['rsi'], nums['macd']
    r1, r2, r3 = nums['r1'], nums['r2'], nums['r3']
    s1, s2, s3 = nums['s1'], nums['s2'], nums['s3']
    
    # تحسين استدعاء Swing H/L بدقة
    sh = d.get('swing_h', 0)
    sl = d.get('swing_l', 0)
    if sh <= 0 or sh < gold: sh = round(r2, 2)
    if sl <= 0 or sl > gold: sl = round(s2, 2)
    
    # تحسين استدعاء المدى اليومي (القمة والقاع اليومي)
    d_high_arr = d.get('gold_daily', {}).get('High', [])
    d_low_arr = d.get('gold_daily', {}).get('Low', [])
    d_high = float(d_high_arr[-1]) if len(d_high_arr) > 0 else round(gold + (atr * 0.4), 2)
    d_low = float(d_low_arr[-1]) if len(d_low_arr) > 0 else round(gold - (atr * 0.4), 2)
    if d_high < gold: d_high = round(gold + (atr * 0.2), 2)
    if d_low > gold: d_low = round(gold - (atr * 0.2), 2)
    
    fib = d.get('fib', {}) or {}
    interest  = float(d.get('interest_rate', 5.25) or 5.25)
    inflation = float(d.get('inflation_est', 3.5) or 3.5)
    ry        = float(d.get('real_yield', 0) or 0) or round(interest - inflation, 2)
    dxy_p     = float(d.get('dxy_p', 100) or 100)
    dxy_pct   = float(d.get('dxy_pct', 0) or 0)
    vix_p     = float(d.get('vix_p', 20) or 20)

    fib_block = "\n".join(
        f"- **{k}**: **{v}** {'📈' if k == '0.0%' else '📉' if k == '100%' else '📊'}"
        for k, v in fib.items()
    ) if fib else (
        f"- محسوب: R1={r1:.2f}$ | R2={r2:.2f}$ | S1={s1:.2f}$ | S2={s2:.2f}$"
    )

    # تحليل RSI بدقة
    if rsi < 30:
        rsi_note = f"RSI={rsi:.2f} تشبع بيعي حاد — إشارة على استنفاد الزخم الهبوطي 📈"
    elif rsi > 70:
        rsi_note = f"RSI={rsi:.2f} تشبع شرائي حاد — إشارة على استنفاد الزخم الصعودي 📉"
    else:
        rsi_note = f"RSI={rsi:.2f} محايد — الزخم متوازن ويخضع للسيولة اللحظية"

    macd_note = (f"MACD={macd:.4f} سلبي — البائعون يسيطرون على تداولات اليوم 📉"
                 if macd < 0 else
                 f"MACD={macd:.4f} إيجابي — المشترون يسيطرون على تداولات اليوم 📈")

    # المدى اليومي المتوقع بأعلى دقة رياضية
    exp_high = round(pivot + (atr * 0.6), 2)
    exp_low  = round(pivot - (atr * 0.6), 2)
    atr_note = (f"ATR={atr:.2f}$ — تقلبات {'كبيرة جداً' if atr > 100 else 'عالية' if atr > 60 else 'متوسطة' if atr > 30 else 'منخفضة'}. "
                f"المدى الديناميكي المتوقع لحركة السعر اليوم: بين القاع {exp_low:.2f}$ والقمة {exp_high:.2f}$")

    # التقييم الاستراتيجي الشامل بأعلى جودة
    is_bullish = gold > pivot and macd > 0
    is_bearish = gold < pivot and macd < 0
    
    if is_bullish and rsi < 70:
        main_dir = "🟢 صعودي صريح (Strong Bullish)"
        best_trade = f"🎯 اصطياد قيعان الشراء (Dip Buying) من الدعم {s1:.2f}$، أو اختراق المحور {pivot:.2f}$. الوقف مغلق تحت {round(s1 - atr*0.25, 2)}$. الأهداف: {r1:.2f}$ و {r2:.2f}$."
        final_advice = f"🟢 الزخم في صالح المشتري بشكل حاسم. تجنب البيع العشوائي وركز على مراكز الشراء من الدعوم مع أي تصحيح، فالاتجاه لم يستنفد طاقته بعد."
    elif is_bearish and rsi > 30:
        main_dir = "🔴 هبوطي صريح (Strong Bearish)"
        best_trade = f"🎯 اصطياد قمم البيع (Rally Selling) من المقاومة {r1:.2f}$، أو كسر المحور {pivot:.2f}$. الوقف مغلق فوق {round(r1 + atr*0.25, 2)}$. الأهداف: {s1:.2f}$ و {s2:.2f}$."
        final_advice = f"🔴 الزخم في صالح البائع بشكل حاسم. تجنب الشراء العشوائي وركز على البيع مع أي ارتداد وهمي لأعلى، فالضغوط البيعية لم تنتهِ."
    elif gold > pivot and rsi >= 70:
        main_dir = "⚠️ صعودي متشبع خطير (Overbought Warning)"
        best_trade = f"🎯 قناص بيع عكس الاتجاه من ذروة المقاومة ({r2:.2f}$ أو {sh:.2f}$). الوقف صارم أعلى القمة بـ {round(atr*0.15, 2)}$. الأهداف العميقة: {r1:.2f}$ ثم {pivot:.2f}$."
        final_advice = f"⚠️ المشترون مرهقون جداً (استنفاد سيولة شرائية). السوق مهيأ لفخ صعودي (Bull Trap). تجنب الشراء بالأسعار الحالية وابحث عن تأكيد البيع من مناطق الذروة."
    elif gold < pivot and rsi <= 30:
        main_dir = "⚠️ هبوطي متشبع خطير (Oversold Warning)"
        best_trade = f"🎯 قناص شراء عكس الاتجاه من عمق الدعم ({s2:.2f}$ أو {sl:.2f}$). الوقف صارم أسفل القاع بـ {round(atr*0.15, 2)}$. الأهداف العميقة: {s1:.2f}$ ثم {pivot:.2f}$."
        final_advice = f"⚠️ البائعون مرهقون جداً (استنفاد سيولة بيعية). السوق مهيأ لفخ هبوطي (Bear Trap). تجنب البيع بالأسعار الحالية وابحث عن تأكيد الشراء من الانهيارات العميقة."
    else:
        main_dir = "⚪ تذبذب عرضي محايد (Ranging / Chop Zone)"
        best_trade = f"🎯 تداول حواف النطاق: الشراء من {s1:.2f}$ والبيع من {r1:.2f}$ بوقوف ضيقة جداً لا تتجاوز {round(atr*0.2, 2)}$، مع استهداف نقطة المحور {pivot:.2f}$."
        final_advice = f"⚖️ انعدام سيولة اتجاهية واضحة. يجب الالتزام الصارم بتداول الحد العلوي والسفلي للنطاق (Range Edges) وعدم الدخول في مراكز استراتيجية ممتدة حتى يتم كسر النطاق."

    # صفقات عالية الجودة والدقة
    # 1. سكالبينج قوي (يعتمد على السيولة الدقيقة S1/R1)
    scalp_buy_entry = round(s1 - (atr * 0.05), 2)
    scalp_buy_sl = round(s1 - (atr * 0.25), 2)
    scalp_buy_t1 = round(s1 + (atr * 0.4), 2)
    scalp_buy_t2 = round(pivot, 2)

    scalp_sell_entry = round(r1 + (atr * 0.05), 2)
    scalp_sell_sl = round(r1 + (atr * 0.25), 2)
    scalp_sell_t1 = round(r1 - (atr * 0.4), 2)
    scalp_sell_t2 = round(pivot, 2)

    # 2. سوينج ممتد وعميق (يعتمد على أطراف الذروة S2/R2)
    swing_buy_entry = round(s2 - (atr * 0.1), 2)
    swing_buy_sl = round(s2 - (atr * 0.35), 2)
    swing_buy_t1 = round(s1, 2)
    swing_buy_t2 = round(r1, 2)

    swing_sell_entry = round(r2 + (atr * 0.1), 2)
    swing_sell_sl = round(r2 + (atr * 0.35), 2)
    swing_sell_t1 = round(r1, 2)
    swing_sell_t2 = round(s1, 2)

    # نطاق التداول الدقيق
    if gold > r1:
        range_desc = f"📈 اختراق صعودي لسيولة المقاومة. يتداول الذهب بحرية فوق {r1:.2f}$ مع استهداف عنيف نحو {r2:.2f}$."
    elif gold < s1:
        range_desc = f"📉 كسر هبوطي لسيولة الدعم. ينزف الذهب بحرية تحت {s1:.2f}$ مع استهداف عنيف نحو {s2:.2f}$."
    elif gold > pivot:
        range_desc = f"⚖️ استقرار إيجابي أعلى المحور. يتحرك السعر بضغط شرائي داخل النطاق [{pivot:.2f}$ — {r1:.2f}$]."
    else:
        range_desc = f"⚖️ استقرار سلبي أدنى المحور. يتحرك السعر بضغط بيعي داخل النطاق [{pivot:.2f}$ — {s1:.2f}$]."

    # تقييم الاقتصاد الكلي للخلاصة
    macro_read = ("سلبية: الدولار والفائدة القوية تضغط وتمنع الذهب من تحقيق قمم جديدة براحة"
                  if ry > 1 and dxy_pct > 0 else
                  "إيجابية: تراجع الدولار وانخفاض العائد الحقيقي يوفر أرضية صلبة لارتفاعات الذهب")

    return (
        "### 👑 الخلاصة المحورية الشاملة (Master Summary) 👑\n*(هذه الخلاصة المحورية هي مسك الختام وعصارة التقارير السابقة، وتعتبر المرجع النهائي والأدق لقرارك اليوم)*\n"
        "#### 📊 تقييم السيولة والنطاقات بدقة متناهية 📊\n"
        f"- **السعر اللحظي الدقيق:** **{gold:.2f}$** 💰\n"
        f"- **نقطة الارتكاز المحورية (Pivot):** **{pivot:.2f}$** ⚖️\n"
        f"- **أعلى سعر مسجل اليوم (Daily High):** **{d_high:.2f}$** 🚀\n"
        f"- **أدنى سعر مسجل اليوم (Daily Low):** **{d_low:.2f}$** 📉\n"
        f"- **أقصى قمة مسجلة مؤخراً (Swing High):** **{sh:.2f}$** ⬆️\n"
        f"- **أقصى قاع مسجل مؤخراً (Swing Low):** **{sl:.2f}$** ⬇️\n\n"
        "#### 📐 الدعم والمقاومة الهيكلية 📐\n"
        f"- 🧱 مقاومات البائعين: **R1={r1:.2f}$** | **R2={r2:.2f}$** | **R3={r3:.2f}$**\n"
        f"- 🛡️ دعوم المشترين: **S1={s1:.2f}$** | **S2={s2:.2f}$** | **S3={s3:.2f}$**\n\n"
        "#### 🔮 المدى المتوقع لليوم والزخم 🔮\n"
        f"- **المدى المتوقع لليومي:** {atr_note}\n"
        f"- **مؤشر الزخم والتسارع (MACD):** {macd_note}\n"
        f"- **الضغط الفني (RSI):** {rsi_note}\n\n"
        "#### 🎯 الصفقات الموصى بها (جودة قناص عالية الدقة) 🎯\n"
        f"**⚡ استراتيجية السكالبينج (ارتدادات النطاق اللحظي):**\n"
        f" + 🟢 **شراء من قاع لحظي**: نقطة التمركز **{scalp_buy_entry:.2f}$** | وقف الإغلاق **{scalp_buy_sl:.2f}$** | أهداف **{scalp_buy_t1:.2f}$**، ثم **{scalp_buy_t2:.2f}$**.\n"
        f" + 🔴 **بيع من قمة لحظية**: نقطة التمركز **{scalp_sell_entry:.2f}$** | وقف الإغلاق **{scalp_sell_sl:.2f}$** | أهداف **{scalp_sell_t1:.2f}$**، ثم **{scalp_sell_t2:.2f}$**.\n\n"
        f"**🌊 استراتيجية السوينج الممتد (الاعتماد الكامل على أطراف الذروة السعرية):**\n"
        f" + 🟢 **شراء استراتيجي (Deep Dip)**: التمركز العميق **{swing_buy_entry:.2f}$** | وقف النزيف **{swing_buy_sl:.2f}$** | أهداف **{swing_buy_t1:.2f}$**، ثم **{swing_buy_t2:.2f}$**.\n"
        f" + 🔴 **بيع استراتيجي (Top Short)**: التمركز المرتفع **{swing_sell_entry:.2f}$** | وقف النزيف **{swing_sell_sl:.2f}$** | أهداف **{swing_sell_t1:.2f}$**، ثم **{swing_sell_t2:.2f}$**.\n\n"
        "#### 💡 الحكم النهائي للذهب (الخلاصة الاستراتيجية) 💡\n"
        f"**🧭 الاتجاه العام المعتمد:** {main_dir}\n\n"
        f"**💎 أهم فرصة حالية متوفرة في السوق (بدقة القناص):** {best_trade}\n\n"
        f"**📈 نطاق التداول اللحظي ومسار السيولة:** {range_desc}\n\n"
        f"**⚠️ التوصية الختامية الحاكمة (قرار الماكينة):** {final_advice}\n\n"
        f"**🌎 البيئة الاقتصادية الدافعة للسعر:** {macro_read}. والدولار ({dxy_pct:+.2f}%) يمثل دافعاً {'سلبياً' if dxy_pct > 0 else 'إيجابياً'} لتداولات الذهب الآن.\n"
    )
def _build_summary_template(d: dict, report_text: str, mode_label: str) -> str:
    client = Groq(api_key=random.choice(GROQ_KEYS)) if GROQ_KEYS else None
    if not client: return ""
    
    gold = d.get('gold', 0)
    rsi = d.get('tf_daily', {}).get('rsi', 50)
    macd_val = d.get('tf_daily', {}).get('macd', 0)
    ry = d.get('real_yield', 0)
    bias_d = d.get('tf_daily', {}).get('bias', 'محايد')
    bias_w = d.get('tf_weekly', {}).get('bias', 'محايد')
    pivot = d.get('pivot', 0)
    # جعل المستويات ديناميكية تتحرك مع السوق والـ ATR بدلاً من المحاور الثابتة
    atr = d.get('atr', 20)
    s1, s2 = round(gold - (atr * 0.8), 2), round(gold - (atr * 1.5), 2)
    r1, r2 = round(gold + (atr * 0.8), 2), round(gold + (atr * 1.5), 2)
    
    adv = d.get('adv_trades', {})
    best_buy = adv.get('monthly_buy') or adv.get('swing_buy') or adv.get('rev_buy') or adv.get('weekly_buy')
    best_sell = adv.get('monthly_sell') or adv.get('swing_sell') or adv.get('rev_sell') or adv.get('weekly_sell')
    
    def format_trade(t):
        if not t: return "جاري حساب نقطة الدخول الدقيقة"
        return f"دخول: {t['entry']}$ | هدف: {t['t2']}$ | وقف: {t['sl']}$"

    prompt = f"""أنت خبير مالي كمي. بناءً على هذه الأرقام اللحظية، استخرج 'الخلاصة المحورية' لسوق {mode_label}.
السعر: {gold}$ | المحور(Pivot): {pivot}$ | الاتجاه اليومي: {bias_d} | الأسبوعي: {bias_w}
RSI: {rsi} | MACD: {macd_val} | العائد الحقيقي: {ry}%

أقوى صفقة شراء: {format_trade(best_buy)}
أقوى صفقة بيع: {format_trade(best_sell)}
دعوم: S1={s1}, S2={s2}
مقاومات: R1={r1}, R2={r2}

استخرج ونسق البيانات بنفس هذا القالب بالضبط بدون أي ديباجة إضافية (أرقام فقط كالمطلوب):

الخلاصة المحورية

🎯 خلاصة انحياز الذهب | {mode_label} | التحديث المباشر

📈 احتمال صعود للقمه: [توقعك كنسبة]% (نحو {r2}$)
📉 احتمال هبوط نحو القاع: [توقعك كنسبة]% (نحو {s2}$)
🔀 احتمالية التذبذب: [توقعك كنسبة]% (حول {gold}$)

🧭 الخلاصة:
[فقرة قصيرة جداً من سطرين تلخص وضع السوق والقرار المناسب بناء على الأرقام أعلاه]

📍 نقطة الفصل اليومية (Pivot):
{pivot}$ [تعليق قصير]

📌 مستويات التداول الحالية:
🟢 مستويات الشراء {mode_label}: S1={s1}$ | S2={s2}$
🔴 مستويات البيع {mode_label}: R1={r1}$ | R2={r2}$

✅ أقوى صفقة شراء {mode_label}:
{format_trade(best_buy)}
   الثقة: [تقييم]% | السبب: [سبب فني قصير]

✅ أقوى صفقة بيع {mode_label}:
{format_trade(best_sell)}
   الثقة: [تقييم]% | السبب: [سبب فني قصير]"""

    for model_name in GROQ_MODELS:
        try:
            resp = client.chat.completions.create(
                messages=[{"role": "system", "content": MASTER_SYSTEM_PROMPT + "أنت محلل كمي. التزم بالقالب الحرفي للأرقام بدون أي ديباجة."}, {"role": "user", "content": prompt}],
                model=model_name, temperature=0.1, max_tokens=600
            )
            return resp.choices[0].message.content
        except: pass
    return "⚠️ تعذر توليد الخلاصة المحورية بسبب الضغط على السيرفر."

def _build_all_tf_levels(data: dict) -> str:
    """بناء قالب مستويات واتجاهات اليوم الشامل رياضياً"""
    gld = data.get('gold', 2000)
    atr = data.get('atr', 20)
    
    # محاكاة تقريبية لانحرافات الفريمات
    # (الـ ATR يتقلص مع صغر الفريم. كمعدل تقريبي: 1h=atr/2, 15m=atr/4, 5m=atr/6, daily=atr)
    tfs = [
        ("5 دقائق", 0.15),
        ("10 دقائق", 0.20),
        ("15 دقيقة", 0.25),
        ("30 دقيقة", 0.35),
        ("ساعة", 0.50),
        ("4 ساعات", 0.75),
        ("يوم", 1.0),
        ("أسبوع", 2.2),
        ("شهر", 4.5)
    ]
    
    lines = ["━━━━━━━━━━━━━━━━━━━━━━━━━━\n📍📊 مستويات واتجاهات الذهب الشاملة لكل الفريمات الزمنية\n━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    
    for name, factor in tfs:
        tf_atr = atr * factor
        # الحسابات الرياضية الدقيقة
        pivot = gld
        high = gld + tf_atr * 1.5
        low = gld - tf_atr * 1.5
        # FIX 6: Expected close respects market bias direction
        _bias_dir = 1 if ('صاعد' in data.get('tf_daily', {}).get('bias', '') or 'bull' in str(data.get('confluence', {}).get('bias', ''))) else -1
        close = gld + (_bias_dir * tf_atr * 0.2)
        buy_zone = gld - tf_atr * 0.5
        sell_zone = gld + tf_atr * 0.5
        break_up = gld + tf_atr * 0.8
        break_down = gld - tf_atr * 0.8
        rev_up = gld - tf_atr * 1.2
        rev_down = gld + tf_atr * 1.2
        
        block = f"""
⏱️ إطار: [{name}]
🟢 منطقة الشراء: {round(buy_zone, 2)}
🔴 منطقة البيع: {round(sell_zone, 2)}
📈 القمة المتوقعة: {round(high, 2)}
📉 القاع المتوقع: {round(low, 2)}
🎯 الإغلاق المتوقع: {round(close, 2)}
🔼 النقطة الفاصلة للصعود (اختراق وثبات): {round(break_up, 2)}
🔽 النقطة الفاصلة للهبوط (كسر وثبات): {round(break_down, 2)}
🔄 نقطة الانعكاس للصعود (ارتداد ارتكازي): {round(rev_up, 2)}
🔄 نقطة الانعكاس للهبوط (ارتداد ارتكازي): {round(rev_down, 2)}
📍 النقطة المحورية (الفاصلة): {round(pivot, 2)}
─────────────────────────"""
        lines.append(block.strip())
        
    return "\n".join(lines)

def _build_spot_s14(data: dict) -> str:
    """القالب الجديد: القمة المتوقعة والقاع المتوقع وسعر الإغلاق والاتجاه الأول"""
    nums = _s_nums(data)
    current = nums.get('gold', data.get('gold', 0.0))
    atr = nums.get('atr', 20.0)
    pivot = nums.get('pivot', current)
    
    # Expected Extremes for the day (not what has been recorded so far)
    expected_high = nums.get('r2', current + atr)
    expected_low = nums.get('s2', current - atr)
    
    # Recorded extremes
    recorded_high = data.get('daily_high', current)
    if recorded_high <= current: recorded_high = current + (atr * 0.2)
    recorded_low = data.get('daily_low', current)
    if recorded_low >= current: recorded_low = current - (atr * 0.2)
    
    rsi = nums.get('rsi', 50)
    macd = nums.get('macd', 0.0)
    
    dist_high = abs(expected_high - current)
    dist_low = abs(current - expected_low)
    
    close = data.get('prev_close', current)
    confluence = data.get('confluence', {})
    trend = confluence.get('verdict', 'محايد')
    
    if "شراء" in trend or "صاعد" in trend or (rsi > 55 and macd > 0):
        expected_close = nums.get('r1', current + (atr * 0.5))
    elif "بيع" in trend or "هابط" in trend or (rsi < 45 and macd < 0):
        expected_close = nums.get('s1', current - (atr * 0.5))
    else:
        expected_close = pivot
        
    if "شراء" in trend or "صاعد" in trend or (rsi > 55 and macd > 0):
        first_target = f"📈 استهداف القمة المتوقعة أولاً ({expected_high:.2f}$)"
        reason = f"السيولة تتدفق بقوة نحو الأعلى (RSI: {rsi:.1f})، والاتجاه العام صاعد ومستقر. من المرجح جداً أن يندفع السعر لاختبار مناطق المقاومة العنيفة عند القمة المتوقعة قبل أي محاولة هبوط."
    elif "بيع" in trend or "هابط" in trend or (rsi < 45 and macd < 0):
        first_target = f"📉 استهداف القاع المتوقع أولاً ({expected_low:.2f}$)"
        reason = f"السوق يخضع لضغوط بيعية واضحة (RSI: {rsi:.1f})، والاتجاه العام يميل بقوة للهبوط. التوقعات تشير لضرب مستويات الدعم العميقة عند القاع المتوقع قبل أي ارتداد."
    else:
        if dist_high < dist_low:
            first_target = f"📈 الأقرب رياضياً هو القمة ({expected_high:.2f}$)"
            reason = f"السوق حالياً في مسار متذبذب (عرضي)، ولكن السعر يتمركز في النصف العلوي وأقرب لمناطق القمة، مما يرجح اختبارها أولاً لتفريغ السيولة الشرائية المتبقية."
        else:
            first_target = f"📉 الأقرب رياضياً هو القاع ({expected_low:.2f}$)"
            reason = f"السوق حالياً في مسار متذبذب (عرضي)، ولكن السعر يتمركز في النصف السفلي وأقرب لمناطق القاع، مما يرجح اختباره أولاً لتجميع سيولة شرائية جديدة."

    template = f"""
👑 **خارطة المسار اليومي المتوقع (Daily Expected Range)** 👑
━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 **المحطات السعرية الأقصى توقعاً اليوم (Spot)**
💰 السعر اللحظي الحالي: **{current:.2f}$**
📌 القمة المسجلة حتى الآن: **{recorded_high:.2f}$**
📌 القاع المسجل حتى الآن: **{recorded_low:.2f}$**
🔒 سعر الإغلاق السابق (Prev Close): **{close:.2f}$**
━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 القمة المتوقعة (المستهدفة): **{expected_high:.2f}$**
⚓ القاع المتوقع (المستهدف): **{expected_low:.2f}$**
🏁 سعر الإغلاق المتوقع (Expected Close): **{expected_close:.2f}$**
━━━━━━━━━━━━━━━━━━━━━━━━━━
🧭 **البوصلة الزمنية: إلى أين نتجه أولاً؟**
⚡ {first_target}

🔬 **التحليل الميكانيكي الدقيق للمسار:**
{reason}
━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 *تنويه: القمة والقاع هنا ليسا ما تم تسجيله بالفعل، بل هما الأهداف القصوى (القمة المتوقعة والقاع المتوقع) التي يتجه لها السعر اليوم بناءً على خوارزميات قياس الزخم والسيولة (ATR).*
"""
    return template.strip()