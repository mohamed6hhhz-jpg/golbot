def _build_spot_s4(d: dict) -> str:
    """4/12 - صفقات السكالبينج"""
    nums = _s_nums(d)
    gold, atr, pivot = nums['gold'], nums['atr'], nums['pivot']
    rsi, macd = nums['rsi'], nums['macd']
    r1, r2, s1, s2 = nums['r1'], nums['r2'], nums['s1'], nums['s2']
    sh, sl = nums['swing_h'], nums['swing_l']
    fib = d.get('fib', {}) or {}
    fib_sup = float(fib.get('100%', 0) or 0) or s2

    sb = _s_trades(d, 'scalp_buy')
    ss = _s_trades(d, 'scalp_sell')

    fib_lines = "\n".join(f" + {k}: {v}" for k, v in fib.items()) if fib else (
        f" + R1: {r1:.2f}$ | R2: {r2:.2f}$\n + S1: {s1:.2f}$ | S2: {s2:.2f}$"
    )

    rsi_zone = ("تشبع بيعي 📉" if rsi < 30 else "منطقة بيع 📉" if rsi < 45
                else "تشبع شرائي 📈" if rsi > 70 else "منطقة شراء 📈")

    return (
        "### تحليل السوق الفوري 📊\n"
        "#### بيانات السوق الحالية 📈\n"
        f"* السعر الحالي: **{gold:.2f}$** 💰\n"
        f"* اعلى النطاق اليومي: **{sh:.2f}$** 📈\n"
        f"* ادنى النطاق اليومي: **{sl:.2f}$** 📉\n"
        f"* نقطة المحور: **{pivot:.2f}$** 📍\n"
        f"* RSI: **{rsi:.2f}** 📊 ({rsi_zone})\n"
        f"* MACD: **{macd:.4f}** 📉\n"
        f"* ATR: **{atr:.2f}$** 📊\n"
        "* Fib:\n"
        f"{fib_lines}\n\n"
        "#### صفقات السكالبينج 🏹\n"
        f"* **شراء** 🛍️\n"
        f" + سعر الدخول: **{sb.get('entry',0):.2f}$**\n"
        f" + وقف الخسارة: **{sb.get('sl',0):.2f}$**\n"
        f" + المخاطرة: **{sb.get('risk',0):.2f}$**\n"
        f" + الاهداف:\n"
        f"    - الاول: **{sb.get('t1',0):.2f}$**\n"
        f"    - الثاني: **{sb.get('t2',0):.2f}$**\n"
        f"    - الثالث: **{sb.get('t3',0):.2f}$**\n\n"
        f"* **بيع** 🛍️\n"
        f" + سعر الدخول: **{ss.get('entry',0):.2f}$**\n"
        f" + وقف الخسارة: **{ss.get('sl',0):.2f}$**\n"
        f" + المخاطرة: **{ss.get('risk',0):.2f}$**\n"
        f" + الاهداف:\n"
        f"    - الاول: **{ss.get('t1',0):.2f}$**\n"
        f"    - الثاني: **{ss.get('t2',0):.2f}$**\n"
        f"    - الثالث: **{ss.get('t3',0):.2f}$**\n\n"
        "#### تحليل الارقام 📊\n"
        f"* RSI عند **{rsi:.2f}** — {rsi_zone}\n"
        f"* MACD عند **{macd:.4f}** — اتجاه {'هبوطي 📉' if macd < 0 else 'صعودي 📈'}\n"
        f"* ATR عند **{atr:.2f}$** — تقلبات {'عالية' if atr > 50 else 'منخفضة'} 📊\n"
        f"* اقرب دعم قوي: **{fib_sup:.2f}$** 📍\n\n"
        "#### استنتاج 📝\n"
        f"* السوق في اتجاه {'هبوطي' if macd < 0 else 'صعودي'}، مع RSI في {rsi_zone}\n"
        f"* **فرصة شراء سكالبينج**: دخول {sb.get('entry',0):.2f}$، هدف {sb.get('t1',0):.2f}$ (+{round(sb.get('t1',0)-sb.get('entry',0),2)}$) 🛍️\n"
        f"* **فرصة بيع سكالبينج**: دخول {ss.get('entry',0):.2f}$، هدف {ss.get('t1',0):.2f}$ (-{round(ss.get('entry',0)-ss.get('t1',0),2)}$) 🛍️\n"
    )


def _build_spot_s5(d: dict) -> str:
    """5/12 - صفقات السوينج"""
    nums = _s_nums(d)
    gold, atr, pivot = nums['gold'], nums['atr'], nums['pivot']
    rsi, macd = nums['rsi'], nums['macd']
    r1, r2, s1, s2 = nums['r1'], nums['r2'], nums['s1'], nums['s2']

    sw_b = _s_trades(d, 'swing_buy')
    sw_s = _s_trades(d, 'swing_sell')

    rratio_b = round((sw_b.get('t2', r1) - sw_b.get('entry', s2)) / max(sw_b.get('risk', atr), 0.01), 1)
    rratio_s = round((sw_s.get('entry', r2) - sw_s.get('t2', pivot)) / max(sw_s.get('risk', atr), 0.01), 1)

    trend      = "هبوطية" if rsi < 45 else "صعودية"
    rsi_note   = ('في تشبع بيع — فرصة شراء سوينج قوية' if rsi < 35
                  else 'في تشبع شراء — فرصة بيع سوينج قوية' if rsi > 65
                  else 'في المنطقة المحايدة — انتظار تاكيد الاتجاه')

    return (
        "### صفقات السوينج 🌊\n"
        "#### نظرة عامة على السوق 📊\n"
        f"سعر الذهب الحالي **{gold:.2f}$**، مؤشر RSI يبلغ **{rsi:.2f}**، MACD يبلغ **{macd:.4f}**. "
        f"السوق في حالة {trend}. RSI {rsi_note}.\n\n"
        "#### صفقات السوينج 🌊\n"
        f"* **صفقة شراء سوينج 🛍️**:\n"
        f" + نقطة الدخول: **{sw_b.get('entry',0):.2f}$**\n"
        f" + نقطة وقف الخسارة: **{sw_b.get('sl',0):.2f}$**\n"
        f" + المخاطرة: **{sw_b.get('risk',0):.2f}$**\n"
        f" + نسبة المكسب للمخاطرة (R:R): **{rratio_b}:1**\n"
        f" + الاهداف:\n"
        f"    - الهدف الاول: **{sw_b.get('t1',0):.2f}$**\n"
        f"    - الهدف الثاني: **{sw_b.get('t2',0):.2f}$**\n"
        f"    - الهدف الثالث: **{sw_b.get('t3',0):.2f}$**\n\n"
        f"* **صفقة بيع سوينج 🚫**:\n"
        f" + نقطة الدخول: **{sw_s.get('entry',0):.2f}$**\n"
        f" + نقطة وقف الخسارة: **{sw_s.get('sl',0):.2f}$**\n"
        f" + المخاطرة: **{sw_s.get('risk',0):.2f}$**\n"
        f" + نسبة المكسب للمخاطرة (R:R): **{rratio_s}:1**\n"
        f" + الاهداف:\n"
        f"    - الهدف الاول: **{sw_s.get('t1',0):.2f}$**\n"
        f"    - الهدف الثاني: **{sw_s.get('t2',0):.2f}$**\n"
        f"    - الهدف الثالث: **{sw_s.get('t3',0):.2f}$**\n\n"
        "#### تحليل الارقام 📊\n"
        f"السوق في حالة {trend}. "
        f"RSI {rsi_note}. "
        f"MACD {'سلبي — الزخم هبوطي' if macd < 0 else 'ايجابي — الزخم صعودي'}.\n"
        f"مستويات الدعم الرئيسية: {s1:.2f}$ و{s2:.2f}$.\n"
        f"مستويات المقاومة الرئيسية: {r1:.2f}$ و{r2:.2f}$.\n\n"
        "#### خلاصة القول 📝\n"
        f"الصفقة الافضل حاليا: {'شراء سوينج عند ' + str(round(sw_b.get('entry',s2),2)) + '$ بهدف ' + str(round(sw_b.get('t2',r1),2)) + '$' if rsi < 45 else 'بيع سوينج عند ' + str(round(sw_s.get('entry',r2),2)) + '$ بهدف ' + str(round(sw_s.get('t2',pivot),2)) + '$'}. "
        "يجب ادارة المخاطر بشكل صارم واستخدام وقف الخسارة دائما. 📈💰"
    )


def _build_spot_s6(d: dict) -> str:
    """6/12 - صفقات اللوت العالي"""
    nums = _s_nums(d)
    gold, atr, pivot = nums['gold'], nums['atr'], nums['pivot']
    rsi, macd = nums['rsi'], nums['macd']
    r1, r2, s1, s2 = nums['r1'], nums['r2'], nums['s1'], nums['s2']
    sh, sl = nums['swing_h'], nums['swing_l']

    # صفقات عالية الجودة تعتمد على ضرب السيولة (Liquidity Sweeps)
    # دخول الشراء تحت S2 أو القاع السابق لاصطياد الانعكاس
    base_buy = min(s2, sl) if sl > 0 else s2
    buy_entry = round(base_buy - (atr * 0.05), 2)
    buy_sl = round(buy_entry - (atr * 0.25), 2)  
    buy_t1 = round(buy_entry + (atr * 0.4), 2)
    buy_t2 = round(buy_entry + (atr * 0.8), 2)
    buy_t3 = round(buy_entry + (atr * 1.5), 2)
    
    # دخول البيع فوق R2 أو القمة السابقة لاصطياد الانعكاس
    base_sell = max(r2, sh) if sh > 0 else r2
    sell_entry = round(base_sell + (atr * 0.05), 2)
    sell_sl = round(sell_entry + (atr * 0.25), 2)
    sell_t1 = round(sell_entry - (atr * 0.4), 2)
    sell_t2 = round(sell_entry - (atr * 0.8), 2)
    sell_t3 = round(sell_entry - (atr * 1.5), 2)

    return (
        "### 🎯 صفقات اللوت العالي (High Lot Sniper) 🎯\n"
        "تم تصميم هذه الصفقات لاصطياد السيولة عند الانعكاسات الكاملة (Liquidity Sweeps) بمناطق الذروة (Extreme Edges). يُستخدم لوت عالي مع التزام تام وصارم جداً بوقف الخسارة المذكور نظراً لحساسية هذه المناطق.\n\n"
        "### 📊 مستويات السوق الحالية 📊\n"
        f"- **السعر الحالي:** {gold:.2f}$\n"
        f"- **نقطة الارتكاز (Pivot):** {pivot:.2f}$\n"
        f"- **منطقة سيولة الشراء (Liquidity Pool - Long):** {buy_entry:.2f}$\n"
        f"- **منطقة سيولة البيع (Liquidity Pool - Short):** {sell_entry:.2f}$\n"
        f"- **التقلب المعتمد (ATR):** {atr:.2f}$ 📊\n\n"
        "### ⚡ صفقات القناص عالية الدقة (اللوت العالي) ⚡\n\n"
        f"**🟢 1. صفقة شراء قناص (Long Sweep)**\n"
        f" + الدخول: **{buy_entry:.2f}$** (اصطياد القاع)\n"
        f" + وقف الخسارة: **{buy_sl:.2f}$** (صارم ومغلق)\n"
        f" + الهدف الأول: **{buy_t1:.2f}$** (تأمين الصفقة)\n"
        f" + الهدف الثاني: **{buy_t2:.2f}$**\n"
        f" + الهدف الثالث: **{buy_t3:.2f}$** (انعكاس كامل)\n\n"
        f"**🔴 2. صفقة بيع قناص (Short Sweep)**\n"
        f" + الدخول: **{sell_entry:.2f}$** (اصطياد القمة)\n"
        f" + وقف الخسارة: **{sell_sl:.2f}$** (صارم ومغلق)\n"
        f" + الهدف الأول: **{sell_t1:.2f}$** (تأمين الصفقة)\n"
        f" + الهدف الثاني: **{sell_t2:.2f}$**\n"
        f" + الهدف الثالث: **{sell_t3:.2f}$** (انعكاس كامل)\n\n"
        "### ⚠️ قواعد التداول ⚠️\n"
        "- **لا تدخل ماركت من منتصف النطاق.** هذه الصفقات تُفعل **فقط** عند وصول السعر للمستويات المذكورة تماماً لضمان أفضل نسبة عائد للمخاطرة (Risk/Reward).\n"
        "- وقف الخسارة غير قابل للتحريك (مسافة ATR رياضية) لتجنب الانهيارات المفاجئة.\n\n"
        "### 💡 الحكم للتأثير النهائي على التداول 💡\n"
        f"بناءً على موقع السعر الحالي من مناطق السيولة، فرص {'الشراء من مستويات ' + str(buy_entry) + '$ هي الأرجح والأكثر أماناً' if rsi < 50 else 'البيع من مستويات ' + str(sell_entry) + '$ هي الأرجح والأكثر أماناً'} مع ضرورة انتظار الإشارة المؤكدة وعدم الاستعجال."
    )
def _build_spot_s7(d: dict) -> str: