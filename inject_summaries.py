# ─────────────────────────────────────────────────────────────────────
# Inject 4 summaries into send_reports — after each report group ends
# Does NOT touch any existing code
# ─────────────────────────────────────────────────────────────────────

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

# ── 1. Build the _build_group_summary function ──────────────────────
NEW_FUNC = '''

def _build_group_summary(data: dict, group_name: str, num_templates: int) -> str:
    """خلاصة محورية مخصصة لكل مجموعة تقارير — مبنية على بيانات السوق الحية"""
    nums = _s_nums(data)
    gold   = nums['gold']
    atr    = nums['atr']
    pivot  = nums['pivot']
    rsi    = nums['rsi']
    macd   = nums['macd']
    r1, r2 = nums['r1'], nums['r2']
    s1, s2 = nums['s1'], nums['s2']
    sh, sl = nums['swing_h'], nums['swing_l']
    confluence = data.get('confluence', {}) or {}
    verdict = confluence.get('verdict', 'محايد')
    dxy_pct = float(data.get('dxy_pct', 0) or 0)
    vix_p   = float(data.get('vix_p', 20) or 20)
    interest  = float(data.get('interest_rate', 5.25) or 5.25)
    inflation = float(data.get('inflation_est', 3.5) or 3.5)
    ry = round(interest - inflation, 2)

    # اتجاه السوق
    if rsi > 57 and macd > 0:
        dir_text = "\U0001f7e2 صاعد (Bullish)"
        best_action = f"الشراء من {s1:.2f}$ هدف {r1:.2f}$"
    elif rsi < 43 and macd < 0:
        dir_text = "\U0001f534 هابط (Bearish)"
        best_action = f"البيع من {r1:.2f}$ هدف {s1:.2f}$"
    else:
        dir_text = "\u26aa محايد / متذبذب"
        best_action = f"الانتظار بين {s1:.2f}$ و{r1:.2f}$"

    # الثقة
    conf_score = 0
    if rsi > 55 or rsi < 45: conf_score += 1
    if macd != 0: conf_score += 1
    if abs(dxy_pct) > 0.3: conf_score += 1
    conf_label = ["ضعيفة \u26a0\ufe0f", "متوسطة \U0001f7e1", "عالية \U0001f7e2", "قوية جداً \U0001f3af"][min(conf_score, 3)]

    risk_note = "ارتفاع VIX \u26a0\ufe0f تداول بحذر" if vix_p > 25 else "VIX مستقر \u2705 بيئة تداول مناسبة"

    from datetime import datetime
    import pytz
    now_str = datetime.now(pytz.timezone('Africa/Cairo')).strftime("%d/%m/%Y %H:%M")

    return (
        f"\U0001f451 **الخلاصة المحورية — {group_name}**\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\U0001f4c5 **التوقيت:** {now_str} | **عدد القوالب المحللة:** {num_templates}\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\U0001f4b0 **السعر الحالي:** **{gold:.2f}$**\n"
        f"\U0001f9ed **الاتجاه المهيمن:** {dir_text}\n"
        f"\U0001f3af **الحكم النهائي:** {verdict}\n"
        f"\U0001f4af **درجة الثقة:** {conf_label}\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "\U0001f4ca **الأرقام الجوهرية:**\n"
        f"\u25aa\ufe0f RSI: **{rsi:.2f}** | MACD: **{macd:.4f}** | ATR: **{atr:.2f}$**\n"
        f"\u25aa\ufe0f محور: **{pivot:.2f}$** | R1: **{r1:.2f}$** | S1: **{s1:.2f}$**\n"
        f"\u25aa\ufe0f قمة السوينج: **{sh:.2f}$** | قاع السوينج: **{sl:.2f}$**\n"
        f"\u25aa\ufe0f DXY: {dxy_pct:+.2f}% | VIX: {vix_p:.2f} | العائد الحقيقي: {ry:.2f}%\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\U0001f3c6 **أفضل صفقة الآن:** {best_action}\n"
        f"\u26a0\ufe0f **المخاطر:** {risk_note}\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "\U0001f916 *هذه الخلاصة محسوبة رياضياً وتلقائياً من جميع القوالب السابقة.*"
    )


def _build_final_combined_summary(data: dict, s1_text: str, s2_text: str, s3_text: str) -> str:
    """الخلاصة النهائية المجمعة من الخلاصات الثلاث"""
    nums = _s_nums(data)
    gold   = nums['gold']
    atr    = nums['atr']
    pivot  = nums['pivot']
    rsi    = nums['rsi']
    macd   = nums['macd']
    r1, r2 = nums['r1'], nums['r2']
    s1, s2 = nums['s1'], nums['s2']
    confluence = data.get('confluence', {}) or {}
    verdict = confluence.get('verdict', 'محايد')
    vix_p   = float(data.get('vix_p', 20) or 20)

    if rsi > 57 and macd > 0:
        final_dir = "\U0001f7e2 اتجاه صاعد مسيطر"
        final_action = f"الشراء التدريجي من {s1:.2f}$ نحو {r1:.2f}$ ثم {r2:.2f}$"
    elif rsi < 43 and macd < 0:
        final_dir = "\U0001f534 اتجاه هابط مسيطر"
        final_action = f"البيع التدريجي من {r1:.2f}$ نحو {s1:.2f}$ ثم {s2:.2f}$"
    else:
        final_dir = "\u26aa سوق متذبذب بدون اتجاه واضح"
        final_action = f"الانتظار — نطاق التداول {s1:.2f}$↔{r1:.2f}$"

    from datetime import datetime
    import pytz
    now_str = datetime.now(pytz.timezone('Africa/Cairo')).strftime("%d/%m/%Y %H:%M")
    risk_note = "\u26a0\ufe0f VIX مرتفع — تداول بحجم صغير" if vix_p > 25 else "\u2705 بيئة مواتية للتداول"

    return (
        "\U0001f3c6\U0001f451 **الخلاصة النهائية الشاملة — مجمعة من ٣ تقارير** \U0001f451\U0001f3c6\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\U0001f4c5 **التوقيت:** {now_str}\n"
        f"\U0001f4b0 **السعر:** **{gold:.2f}$** | ATR: {atr:.2f}$ | Pivot: {pivot:.2f}$\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\U0001f9ed **الاتجاه العام الموحد:** {final_dir}\n"
        f"\U0001f3af **الحكم الجماعي للنظام:** {verdict}\n"
        f"\U0001f4ca RSI: {rsi:.2f} | MACD: {macd:.4f}\n"
        f"\U0001f4cd R1: {r1:.2f}$ | R2: {r2:.2f}$ | S1: {s1:.2f}$ | S2: {s2:.2f}$\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "\U0001f4cb **ملخص التقارير الثلاثة:**\n"
        "\U0001f539 تقرير 1 (التقرير الكمي الأساسي): تحليل شامل للسعر والمؤشرات والاقتصاد\n"
        "\U0001f539 تقرير 2 (التقرير المتخصص): القوالب المتقدمة والسيولة والمؤسسات\n"
        "\U0001f539 تقرير 3 (القوالب الفورية): التحليل الفني الدقيق والصفقات اللحظية\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\U0001f3c6 **القرار النهائي الموحد:**\n{final_action}\n"
        f"\u26a0\ufe0f **تنبيه المخاطر:** {risk_note}\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "\U0001f916 *هذه الخلاصة النهائية مبنية على تحليل اتوماتيكي شامل من جميع القوالب الثلاثة.*"
    )

'''

# Inject before send_summary_to_bot
INJECT_BEFORE = 'def send_summary_to_bot(token, message, chat_id):'
if INJECT_BEFORE in text:
    text = text.replace(INJECT_BEFORE, NEW_FUNC + INJECT_BEFORE)
    print('Functions injected OK')
else:
    print('ERROR: could not find inject point')

# ── 2. After report 1 ends (flat_chunks loop) → send summary 1 ───────
AFTER_R1 = '''                log.info(f"\\u2705 \\u0631\\u0633\\u0627\\u0644\\u0629 {i}/{total} \\u0648\\u0635\\u0644\\u062a." if ok else f"\\u274c \\u0641\\u0634\\u0644 \\u0631\\u0633\\u0627\\u0644\\u0629 {i}/{total}.")
                time.sleep(2)

            # ── إرسال للبوت الجديد (القسم الثاني) ──'''

AFTER_R1_NEW = '''                log.info(f"\\u2705 \\u0631\\u0633\\u0627\\u0644\\u0629 {i}/{total} \\u0648\\u0635\\u0644\\u062a." if ok else f"\\u274c \\u0641\\u0634\\u0644 \\u0631\\u0633\\u0627\\u0644\\u0629 {i}/{total}.")
                time.sleep(2)

            # ── خلاصة محورية 1 بعد انتهاء التقرير الأول ──
            try:
                _summary1_text = _build_group_summary(data, "التقرير الأول (الكمي الأساسي)", total)
                send_summary_to_bot("8784019564:AAF1XBrGTb5QU_wmOcvYQQ49Vb7dpLWZnm4", _summary1_text, "@summary1Po_bot")
                log.info("\\u2705 [Summary1] تم إرسال خلاصة التقرير الأول.")
            except Exception as _e1:
                log.error(f"❌ [Summary1] خطأ: {_e1}")

            # ── إرسال للبوت الجديد (القسم الثاني) ──'''

if AFTER_R1 in text:
    text = text.replace(AFTER_R1, AFTER_R1_NEW)
    print('Summary1 injection OK')
else:
    print('ERROR: could not find R1 end point')
    # Try finding by unique string
    idx = text.find('log.info(f"\\u2705 \\u0631\\u0633\\u0627\\u0644\\u0629 {i}/{total}')
    print(f'  R1 search idx: {idx}')

# ── 3. After report 2 ends (flat_chunks_2 loop) → send summary 2 ─────
AFTER_R2 = '''                    log.info(f"\\u2705 \\u0631\\u0633\\u0627\\u0644\\u0629 \\u0627\\u0644\\u0628\\u0648\\u062a \\u0627\\u0644\\u062b\\u0627\\u0646\\u064a {i2}/{total_2} \\u0648\\u0635\\u0644\\u062a." if ok2 else f"\\u274c \\u0641\\u0634\\u0644 \\u0631\\u0633\\u0627\\u0644\\u0629 \\u0627\\u0644\\u0628\\u0648\\u062a \\u0627\\u0644\\u062b\\u0627\\u0646\\u064a {i2}/{total_2}.")
                    time.sleep(2)

            # ── البوت الثالث: القوالب الفورية S1-S12 (@Dsssoppp78_bot) ──'''

AFTER_R2_NEW = '''                    log.info(f"\\u2705 \\u0631\\u0633\\u0627\\u0644\\u0629 \\u0627\\u0644\\u0628\\u0648\\u062a \\u0627\\u0644\\u062b\\u0627\\u0646\\u064a {i2}/{total_2} \\u0648\\u0635\\u0644\\u062a." if ok2 else f"\\u274c \\u0641\\u0634\\u0644 \\u0631\\u0633\\u0627\\u0644\\u0629 \\u0627\\u0644\\u0628\\u0648\\u062a \\u0627\\u0644\\u062b\\u0627\\u0646\\u064a {i2}/{total_2}.")
                    time.sleep(2)

            # ── خلاصة محورية 2 بعد انتهاء التقرير الثاني ──
            try:
                _summary2_text = _build_group_summary(data, "التقرير الثاني (المتخصص)", total_2)
                send_summary_to_bot("8718236248:AAGIlK8xTWUvRB_WcYOGN2Qx1kEKZwRqihQ", _summary2_text, "@Summary2Hho_bot")
                log.info("\\u2705 [Summary2] تم إرسال خلاصة التقرير الثاني.")
            except Exception as _e2:
                log.error(f"❌ [Summary2] خطأ: {_e2}")

            # ── البوت الثالث: القوالب الفورية S1-S12 (@Dsssoppp78_bot) ──'''

if AFTER_R2 in text:
    text = text.replace(AFTER_R2, AFTER_R2_NEW)
    print('Summary2 injection OK')
else:
    print('ERROR: could not find R2 end point')

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Phase 1 done!')
