def _build_spot_s9(d: dict) -> str:
    """9/12 - مصفوفة التداول والاسكالبينج الاحترافي"""
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

    fib_block = "\n".join(f"  - **{k}:** {v}" for k, v in fib.items()) if fib else (
        f"  - R1: {r1:.2f}$ | R2: {r2:.2f}$\n  - S1: {s1:.2f}$ | S2: {s2:.2f}$"
    )
    fx_block = "\n".join(f"  - **{sym}:** {pct:+.4f}%" for sym, pct in fx[:8]) if fx else "  - بيانات العملات متاحة عند التريجر"

    return (
        "👑 **مؤشر شهية المخاطرة الشامل (Risk Appetite)** 👑\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🌐 **المسح السعري اللحظي والسيولة:**\n"
        f"- 💰 **سعر الذهب الحالي:** **{gold:.2f}$**\n"
        f"- 🎯 **اعلى النطاق:** {sh:.2f}$ | **ادنى النطاق:** {sl:.2f}$\n"
        f"- 📊 **مؤشر RSI:** {rsi:.2f}\n"
        f"- 📉 **مؤشر MACD:** {macd:.4f}\n"
        f"- 📏 **مؤشر ATR:** {atr:.2f}$\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n📈 **الركائز الفنية الأساسية:**\n"
        "- 🔢 **مستويات فيبوناتشي:**\n"
        f"{fib_block}\n"
        f"- 🎯 **المحور:** {pivot:.2f}$ | **R1:** {r1:.2f}$ | **S1:** {s1:.2f}$\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n📊 **الركائز الأساسية (الماكرو والسيولة):**\n"
        f"- 📉 **معدل التضخم:** {inflation:.2f}%\n"
        f"- 🏦 **معدل الفائدة:** {interest:.2f}%\n"
        f"- ⚖️ **العائد الحقيقي:** {ry:.2f}%\n"
        f"- 🚨 **VIX (مؤشر الخوف):** {vix_p:.2f} ({'مرتفع — تحوط' if vix_p > 25 else 'منخفض — جشع'})\n"
        f"- 📈 **S&P 500 اليومي:** {sp500:+.2f}%\n"
        f"- 💵 **مؤشر الدولار (DXY):** {dxy_p:.4f}\n"
        "- 💱 **قوة العملات:**\n"
        f"{fx_block}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n🎯 **مصفوفة استراتيجيات التداول الشاملة (Trading Matrix)** 🎯\n*(هذه المصفوفة عالية الدقة توضح نقاط الدخول المثالية للسكالبينج والسوينج بناءً على خوارزميات السيولة)*\n\n"
        "⚡ **1. السكالبينج (خطف سريع - مخاطرة عالية)**\n"
        f"🟢 **شراء:** دخول: **{sb.get('entry',0):.2f}$** | الاستوب: **{sb.get('sl',0):.2f}$**\n"
        f"🎯 الأهداف: {sb.get('t1',0):.2f}$ - {sb.get('t2',0):.2f}$ - {sb.get('t3',0):.2f}$\n"
        f"🔴 **بيع:** دخول: **{ss.get('entry',0):.2f}$** | الاستوب: **{ss.get('sl',0):.2f}$**\n"
        f"🎯 الأهداف: {ss.get('t1',0):.2f}$ - {ss.get('t2',0):.2f}$ - {ss.get('t3',0):.2f}$\n\n"
        "📅 **2. التداول اليومي (Intraday - مخاطرة متوسطة)**\n"
        f"🟢 **شراء:** دخول: **{db.get('entry',0):.2f}$** | الاستوب: **{db.get('sl',0):.2f}$**\n"
        f"🎯 الأهداف: {db.get('t1',0):.2f}$ - {db.get('t2',0):.2f}$\n"
        f"🔴 **بيع:** دخول: **{ds.get('entry',0):.2f}$** | الاستوب: **{ds.get('sl',0):.2f}$**\n"
        f"🎯 الأهداف: {ds.get('t1',0):.2f}$ - {ds.get('t2',0):.2f}$\n\n"
        "📆 **3. السوينج الاستراتيجي (مخاطرة مضبوطة)**\n"
        f"🟢 **السوينج الشرائي:** دخول: **{swb.get('entry',0):.2f}$** | الاستوب: **{swb.get('sl',0):.2f}$**\n"
        f"🎯 الأهداف: {swb.get('t1',0):.2f}$ - {swb.get('t2',0):.2f}$ - {swb.get('t3',0):.2f}$\n"
        f"🔴 **السوينج البيعي:** دخول: **{sws.get('entry',0):.2f}$** | الاستوب: **{sws.get('sl',0):.2f}$**\n"
        f"🎯 الأهداف: {sws.get('t1',0):.2f}$ - {sws.get('t2',0):.2f}$ - {sws.get('t3',0):.2f}$\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n⚠️ **ضوابط إدارة المخاطر (Risk Management)** ⚠️\n"
        f"- 🚨 **التقييم الكمي للمخاطرة الآن:** **{risk_pct:.0f}% ({risk_label})**\n"
        f"- 💼 **إدارة المحفظة:** يُنصح بحجم مركز لا يتجاوز **{100 - risk_pct:.0f}%** من هامش المحفظة للصفقة الواحدة نظراً للظروف الحالية.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n💡 **الحكم الاستراتيجي للصفقات**\n"
        f"بناءً على التقييم الكلي للمخاطرة، التوجه الأفضل للمتداولين {'في ظل هذه المخاطرة المنخفضة هو التداول بثقة مع الاتجاه واستهداف السوينج.' if risk_pct <= 45 else 'الآن هو التداول اللحظي السريع (سكالبينج) لتقليل فترة التعرض للسوق والهروب من التذبذب.' if risk_pct > 60 else 'هو التداول اليومي بحذر والالتزام التام بنقاط الوقف وتأمين الأرباح أولاً بأول.'}"
    )

    fx_block = "\n".join(f"  - **{sym}:** {pct:+.4f}%" for sym, pct in fx[:8]) if fx else "  - بيانات العملات متاحة عند التريجر"

    return (
        "👑 **مؤشر شهية المخاطرة الشامل (Risk Appetite)** 👑\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🌐 **المسح السعري اللحظي**\n"
        f"- **سعر الذهب الحالي:** {gold:.2f}$ 💰\n"
        f"- **اعلى النطاق:** {sh:.2f}$ | **ادنى النطاق:** {sl:.2f}$\n"
        f"- **مؤشر RSI:** {rsi:.2f} 📊\n"
        f"- **مؤشر MACD:** {macd:.4f} 📉\n"
        f"- **مؤشر ATR:** {atr:.2f}$ 📊\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n📈 **الركائز الفنية الأساسية**\n"
        "- **مستويات فيبوناتشي:**\n"
        f"{fib_block}\n"
        f"- **نقطة المحور:** {pivot:.2f}$ | **R1:** {r1:.2f}$ | **S1:** {s1:.2f}$\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n📊 **الركائز الأساسية (الماكرو والسيولة)**\n"
        f"- **معدل التضخم:** {inflation:.2f}%\n"
        f"- **معدل الفائدة:** {interest:.2f}%\n"
        f"- **العائد الحقيقي:** {ry:.2f}%\n"
        f"- **VIX (مؤشر الخوف):** {vix_p:.2f} ({'مرتفع — تحوط' if vix_p > 25 else 'منخفض — جشع'})\n"
        f"- **S&P 500 اليومي:** {sp500:+.2f}%\n"
        f"- **مؤشر الدولار (DXY):** {dxy_p:.4f}\n"
        "- **قوة العملات:**\n"
        f"{fx_block}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n🎯 **مصفوفة استراتيجيات التداول الشاملة (Trading Matrix)** 🎯\n*(بناءً على تفصيل الصفقات في القوالب السابقة، نضع بين يديك الآن \"المصفوفة الشاملة\" لإدارة رأس المال وتوزيع المخاطرة للسكالبينج والسوينج)*\n\n"
        "⚡ **1. السكالبينج (خطف سريع - مخاطرة عالية)**\n"
        f"- **🟢 شراء:** الدخول {sb.get('entry',0):.2f}$ | الوقف {sb.get('sl',0):.2f}$ | الأهداف {sb.get('t1',0):.2f}$ - {sb.get('t2',0):.2f}$ - {sb.get('t3',0):.2f}$\n"
        f"- **🔴 بيع:** الدخول {ss.get('entry',0):.2f}$ | الوقف {ss.get('sl',0):.2f}$ | الأهداف {ss.get('t1',0):.2f}$ - {ss.get('t2',0):.2f}$ - {ss.get('t3',0):.2f}$\n\n"
        "📅 **2. التداول اليومي (Intraday - مخاطرة متوسطة)**\n"
        f"- **🟢 شراء:** الدخول {db.get('entry',0):.2f}$ | الوقف {db.get('sl',0):.2f}$ | الأهداف {db.get('t1',0):.2f}$ - {db.get('t2',0):.2f}$\n"
        f"- **🔴 بيع:** الدخول {ds.get('entry',0):.2f}$ | الوقف {ds.get('sl',0):.2f}$ | الأهداف {ds.get('t1',0):.2f}$ - {ds.get('t2',0):.2f}$\n\n"
        "📆 **3. السوينج الاستراتيجي (مخاطرة مضبوطة)**\n"
        f"- **🟢 السوينج الشرائي:** الدخول {swb.get('entry',0):.2f}$ | الوقف {swb.get('sl',0):.2f}$ | الأهداف {swb.get('t1',0):.2f}$ - {swb.get('t2',0):.2f}$ - {swb.get('t3',0):.2f}$\n"
        f"- **🔴 السوينج البيعي:** الدخول {sws.get('entry',0):.2f}$ | الوقف {sws.get('sl',0):.2f}$ | الأهداف {sws.get('t1',0):.2f}$ - {sws.get('t2',0):.2f}$ - {sws.get('t3',0):.2f}$\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n⚠️ **ضوابط إدارة المخاطر (Risk Management)** ⚠️\n"
        f"- **التقييم الكمي للمخاطرة في السوق الآن:** {risk_pct:.0f}% ({risk_label})\n"
        f"- **إدارة المحفظة:** يُنصح بحجم مركز لا يتجاوز {100 - risk_pct:.0f}% من هامش المحفظة للصفقة الواحدة نظراً للظروف الحالية.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n💡 **الحكم الاستراتيجي للصفقات**\n"
        f"بناءً على التقييم الكلي للمخاطرة، التوجه الأفضل للمتداولين {'في ظل هذه المخاطرة المنخفضة هو التداول بثقة مع الاتجاه' if risk_pct <= 45 else 'الآن هو التداول اللحظي السريع (سكالبينج) لتقليل فترة التعرض للسوق' if risk_pct > 60 else 'هو التداول اليومي بحذر والالتزام التام بنقاط الوقف'}."
    )


def _build_spot_s10(d: dict) -> str:
    """10/12 - عوائد السندات والفائدة والتضخم"""
    interest  = float(d.get('interest_rate', 5.25) or 5.25)
    inflation = float(d.get('inflation_est', 3.5) or 3.5)
    ry        = float(d.get('real_yield', 0) or 0) or round(interest - inflation, 2)
    tnx       = float(d.get('tnx_val', 0) or 0) or round(interest - 0.3, 2)
    twy       = float(d.get('twy_val', 0) or 0) or round(interest + 0.3, 2)
    gold      = float(d.get('gold', 0) or 0)

    spread    = round(tnx - twy, 2)
    curve_lbl = ("طبيعي — اقتصاد سليم" if spread > 0.5
                 else "مقلوب — خطر ركود اقتصادي 🚨" if spread < 0
                 else "مسطح — مرحلة تحول")

    tnx_impact = "سلبي — يزيد الضغط على الذهب" if tnx > 4.5 else "محايد — دعم محدود للذهب"
    int_impact = "سلبي — تكلفة الفرصة البديلة عالية" if interest > 4 else "ايجابي — يدعم الذهب"
    inf_impact = "ايجابي — الذهب تحوط ممتاز ضد التضخم 📈" if inflation > 3 else "محدود — التضخم تحت السيطرة"
    ry_impact  = ("سلبي — العائد الحقيقي الموجب يجعل السندات اكثر جاذبية من الذهب 📉"
                  if ry > 1 else
                  "ايجابي — العائد الحقيقي السلبي يجعل الذهب ملاذا امنا افضل 📈")

    gold_outlook = ("هبوطي — ضغط مزدوج من الفائدة والعائد الحقيقي" if ry > 1 and tnx > 4.5
                    else "صعودي — بيئة مواتية للذهب مع عائد حقيقي سلبي" if ry < 0
                    else "محايد — تاثيرات متعادلة")

    return (
        "### تحليل السوق 📊\n"
        "#### اسعار السندات والفائدة والتضخم 📈\n\n"
        f"*   **عائد سندات الخزانة الامريكية (10 سنوات - TNX)**: {tnx:.2f}% 📊\n"
        f"*   **عائد سندات الخزانة الامريكية (2 سنة - TWY)**: {twy:.2f}% 📊\n"
        f"*   **فارق منحنى العوائد (10Y - 2Y)**: {spread:+.2f}% — {curve_lbl}\n"
        f"*   **معدل الفائدة الفيدرالي**: {interest:.2f}% 📈\n"
        f"*   **معدل التضخم (CPI)**: {inflation:.2f}% 📊\n"
        f"*   **العائد الحقيقي** (TNX - CPI): **{ry:.2f}%** 📊\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n💰 **ترجمة الأرقام لتأثير سعري مباشر على الذهب**\n"
        f"*   **تاثير عائد السندات ({tnx:.2f}%)**: {tnx_impact}\n"
        f"*   **تاثير معدل الفائدة ({interest:.2f}%)**: {int_impact}\n"
        f"*   **تاثير معدل التضخم ({inflation:.2f}%)**: {inf_impact}\n"
        f"*   **تاثير العائد الحقيقي ({ry:.2f}%)**: {ry_impact}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n🔮 **توقعات المسار السعري (Forecasting)**\n"
        f"*   **النظرة المستقبلية للذهب**: {gold_outlook}\n"
        f"*   **السعر الحالي**: {gold:.2f}$\n"
        f"*   **منحنى العوائد**: {curve_lbl} — {'اشارة تحوط' if spread < 0 else 'اشارة ايجابية'}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n📝 **الخلاصة الميكانيكية للسكالبينج**\n"
        f"*   بيئة الفائدة الحالية ({interest:.2f}%) مع تضخم ({inflation:.2f}%) تشير الى ان "
        f"العائد الحقيقي {ry:.2f}% وهو {'يضغط سلبا على الذهب' if ry > 0 else 'يدعم الذهب بشكل قوي'}.\n"
        "*   ومع ذلك، يجب مراعاة العوامل الجيوسياسية والطلب المادي على الذهب.\n"
        f"*   توقع تداول الذهب في نطاق متاثر بمنحنى العوائد {curve_lbl}.\n"
        f"*   {'⚠️ منحنى مقلوب: مؤشر تاريخي على ركود وشيك — يُعزز الطلب على الذهب.' if spread < 0 else '✅ منحنى طبيعي: ثقة بنمو الاقتصاد — يُقلل الطلب على الملاذات الآمنة مؤقتاً.' if spread > 0.5 else '⚠️ منحنى مسطح: مرحلة تحول اقتصادي — تريث وراقب.'} 🌎"
    )


def _build_spot_s11(d: dict) -> str:
    """11/12 - قوة العملات وتاثير DXY"""
    nums = _s_nums(d)
    gold, atr, pivot = nums['gold'], nums['atr'], nums['pivot']
    rsi, macd = nums['rsi'], nums['macd']
    r1, r2, s1, s2 = nums['r1'], nums['r2'], nums['s1'], nums['s2']
    sh, sl = nums['swing_h'], nums['swing_l']

    dxy_p   = float(d.get('dxy_p', 100) or 100)
    dxy_pct = float(d.get('dxy_pct', 0) or 0)
    fx      = d.get('fx_sorted', []) or []

    # تحليل DXY والعلاقة مع الذهب باحترافية عالية
    if dxy_pct > 0.5:
        dxy_effect  = "🔴 **قوي جداً** — ضغط هبوطي حاد على الملاذات الآمنة"
        dxy_gold    = f"مؤشر الدولار يسجل ارتفاعاً ملحوظاً بنسبة {dxy_pct:+.2f}%، مما يضع الذهب تحت ضغط بيعي مكثف بفضل العلاقة العكسية التاريخية."
        gold_impact = f"نتوقع استمرار الضغط البيعي لاختبار مستويات الدعم السفلية. كسر {s1:.2f}$ قد يفتح المجال للهبوط نحو {s2:.2f}$."
        buy_res     = f"🚫 **تجنب الشراء** — الزخم الحالي لصالح الدولار، الشراء يُعتبر التقاطاً للسكين الساقط."
        sell_res    = f"✅ **توصية بيع** — الدخول عند أي ارتداد طفيف نحو {pivot:.2f}$ أو {r1:.2f}$ مع وضع وقف الخسارة أعلى {r2:.2f}$ بقليل."
        recom       = f"الاستراتيجية المثلى: **البيع مع الاتجاه الهابط** مستهدفين {s1:.2f}$ ثم {s2:.2f}$."
    elif dxy_pct > 0.15:
        dxy_effect  = "🟠 **إيجابي** — ضغط هبوطي متوسط على الذهب"
        dxy_gold    = f"الدولار يظهر قوة تدريجية (مكاسب {dxy_pct:+.2f}%)، مما يحد من فرص صعود الذهب ويجعله يميل للسلبية."
        gold_impact = f"الذهب يواجه مقاومة عنيدة عند {r1:.2f}$ بفضل قوة الدولار، ويميل لاختبار الدعم الأول {s1:.2f}$."
        buy_res     = f"⚠️ **شراء بحذر** — فقط من مناطق الدعم القصوى ({s2:.2f}$) مع وقف خسارة ضيق جداً."
        sell_res    = f"✅ **فرصة بيع** — حول مستويات {pivot:.2f}$ أو المقاومة الأولى {r1:.2f}$، مستهدفين {s1:.2f}$."
        recom       = f"الاستراتيجية المثلى: **البيع من مناطق المقاومة** ({r1:.2f}$) مع وقف {r2:.2f}$."
    elif dxy_pct < -0.5:
        dxy_effect  = "🟢 **ضعيف جداً** — دعم صعودي قوي جداً للذهب"
        dxy_gold    = f"الدولار يتعرض لعمليات بيع واسعة (خسائر {dxy_pct:+.2f}%)، مما يعطي الذهب الضوء الأخضر لتحقيق مكاسب قوية."
        gold_impact = f"ضعف الدولار يعزز من جاذبية الذهب. نتوقع اختراق {r1:.2f}$ واستهداف {r2:.2f}$ وما فوقها."
        buy_res     = f"✅ **توصية شراء** — الدخول من مستويات الدعم الحالية أو عند {pivot:.2f}$، مستهدفين {r1:.2f}$ و {r2:.2f}$."
        sell_res    = f"🚫 **تجنب البيع** — السباحة عكس التيار في ظل ضعف الدولار تحمل مخاطر عالية جداً."
        recom       = f"الاستراتيجية المثلى: **الشراء مع الاتجاه الصاعد** مستهدفين {r1:.2f}$ ثم {r2:.2f}$."
    elif dxy_pct < -0.15:
        dxy_effect  = "🔵 **سلبي** — دعم صعودي متوسط للذهب"
        dxy_gold    = f"مؤشر الدولار يتراجع بنسبة {dxy_pct:+.2f}%، مما يوفر بيئة داعمة للذهب للتماسك وبناء مراكز شرائية."
        gold_impact = f"الذهب يتلقى دعماً كافياً لاختبار المقاومة {r1:.2f}$. البقاء فوق {pivot:.2f}$ يُعد إيجابياً."
        buy_res     = f"✅ **فرصة شراء** — حول {pivot:.2f}$ أو الدعم {s1:.2f}$، مستهدفين المقاومة {r1:.2f}$."
        sell_res    = f"⚠️ **بيع بحذر** — فقط من مستويات المقاومة القصوى ({r2:.2f}$) وبلوت صغير."
        recom       = f"الاستراتيجية المثلى: **الشراء من الدعوم** ({s1:.2f}$) مع وقف {s2:.2f}$."
    else:
        dxy_effect  = "⚪ **محايد** — تأثير محدود (تذبذب عرضي)"
        dxy_gold    = f"مؤشر الدولار مستقر نسبياً (تغير {dxy_pct:+.2f}%)، مما يترك الذهب للتحرك بناءً على العوامل الفنية الصرفة."
        gold_impact = f"في غياب المحفزات من الدولار، الذهب محصور فنياً في النطاق العرضي بين {s1:.2f}$ و {r1:.2f}$."
        buy_res     = f"✅ **الشراء** من الحد السفلي للنطاق ({s1:.2f}$) بهدف المحور ({pivot:.2f}$)."
        sell_res    = f"✅ **البيع** من الحد العلوي للنطاق ({r1:.2f}$) بهدف المحور ({pivot:.2f}$)."
        recom       = f"الاستراتيجية المثلى: **تداول النطاق العرضي (Range Trading)** بين {s1:.2f}$ و {r1:.2f}$."

    # تنسيق مصفوفة العملات بشكل احترافي
    if fx and len(fx) >= 2:
        top_fx = f"🟩 **أقوى العملات:** {fx[0][0]} ({fx[0][1]:+.2f}%) | {fx[1][0]} ({fx[1][1]:+.2f}%)"
        bot_fx = f"🟥 **أضعف العملات:** {fx[-1][0]} ({fx[-1][1]:+.2f}%) | {fx[-2][0]} ({fx[-2][1]:+.2f}%)"
        fx_block = f"{top_fx}\n{bot_fx}"
    else:
        fx_block = "⏳ بيانات تدفق السيولة للعملات قيد التحديث..."

    return f'''### 🌍 تقرير السيولة النقدية وارتباط الدولار (DXY)
======================================================

#### 📊 المعطيات الفنية الحالية (XAU/USD)
**السعر الحالي:** {gold:.2f}$ 💰 | **المحور اليومي:** {pivot:.2f}$
**مقاومات أساسية:** {r1:.2f}$ (R1) — {r2:.2f}$ (R2)
**دعوم أساسية:** {s1:.2f}$ (S1) — {s2:.2f}$ (S2)
**الزخم:** RSI = {rsi:.2f} | MACD = {macd:.4f}

#### 💵 مؤشر الدولار الأمريكي (DXY)
**القراءة الحالية:** {dxy_p:.4f} نقطة
**التغير اليومي:** {dxy_pct:+.2f}%
**حالة السيولة:** {dxy_effect}

#### 💱 مصفوفة قوة العملات (FX Flow)
{fx_block}

#### 🔗 التأثير المتوقع على الذهب
{dxy_gold}
{gold_impact}

#### 🎯 الخلاصة الاستراتيجية (النقاط المفصلية)
{buy_res}
{sell_res}

💡 {recom}
'''
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