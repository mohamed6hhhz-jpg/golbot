import re

def prettify_templates(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # T0 update
    old_t0 = '''🎯 التقرير التمهيدي: صفقات ذكية واتجاهات الذهب

💵 السعر اللحظي للذهب: {gold_val:.2f}$
⏱️ الاتجاه خلال ساعة: [ترجم إلى العربية بدقة: {bias_1h}]
📅 الاتجاه خلال يوم: [ترجم إلى العربية بدقة: {bias_1d}]
🏁 الأقرب للضرب أولاً: {first_hit}

🔥 صفقات السكالبينج (خطف سريع):
{scalp_str}

🌊 صفقات السوينج (مدى أبعد):
{swing_str}

🎯 صفقات زيرو انعكاس (قناص):
{rev_str}'''

    new_t0 = '''🎯 التقرير التمهيدي: صفقات ذكية واتجاهات الذهب
━━━━━━━━━━━━━━━━━━━━━━━━━━
💵 السعر اللحظي للذهب: {gold_val:.2f}$
⏱️ الاتجاه خلال ساعة: [ترجم إلى العربية بدقة: {bias_1h}]
📅 الاتجاه خلال يوم: [ترجم إلى العربية بدقة: {bias_1d}]
🏁 الأقرب للضرب أولاً: {first_hit}
━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 صفقات السكالبينج (خطف سريع):
{scalp_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━
🌊 صفقات السوينج (مدى أبعد):
{swing_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 صفقات زيرو انعكاس (قناص):
{rev_str}'''

    if old_t0 in content:
        content = content.replace(old_t0, new_t0)
        print(f"Updated T0 in {filename}")
    else:
        print(f"T0 not found exactly in {filename}, regex matching...")
        # fallback regex for T0
        content = re.sub(
            r'(🎯 التقرير التمهيدي: صفقات ذكية واتجاهات الذهب)\n+(\s*💵 السعر اللحظي للذهب:)',
            r'\1\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\2',
            content
        )
        content = re.sub(
            r'(\n+)(\s*🔥 صفقات السكالبينج \(خطف سريع\):)',
            r'\1━━━━━━━━━━━━━━━━━━━━━━━━━━\n\2',
            content
        )
        content = re.sub(
            r'(\n+)(\s*🌊 صفقات السوينج \(مدى أبعد\):)',
            r'\1━━━━━━━━━━━━━━━━━━━━━━━━━━\n\2',
            content
        )
        content = re.sub(
            r'(\n+)(\s*🎯 صفقات زيرو انعكاس \(قناص\):)',
            r'\1━━━━━━━━━━━━━━━━━━━━━━━━━━\n\2',
            content
        )


    # T1 update
    old_t1 = '''تحليل الذهب 🟡

1W (الأسبوعي)
التحيز الأسبوعي: {w_bias} {w_icon}

1D (اليومي)
التحيز اليومي: {d_bias} {d_icon}

4H - 1H
{context_text}

{zone_color} مستوى {zone_name}: {exact_zone}

في حال احترام المستوى، نتوقع استهداف:
{t1}
{t2}

وفي حالة كسر {t2}، سيستمر {break_dir} لمستويات أقل.

{rev_color} أما إذا لم يحترم السعر مستوى {exact_zone} وتمكن من اختراقه، فسيستهدف {rev_zone}.
وتعتبر نقطة {rev_zone} هي النقطة الذهبية الفاصلة بين الصعود والهبوط، وباختراقها والثبات أعلاه يمكننا القول إن السعر بدأ يغير اتجاهه ويميل إلى {rev_dir}.'''

    new_t1 = '''📊 التقرير الفني المتقدم للذهب 🟡
━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 1W (الأسبوعي)
   التحيز الأسبوعي: {w_bias} {w_icon}

📆 1D (اليومي)
   التحيز اليومي: {d_bias} {d_icon}
━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ 4H - 1H (المدى القصير)
   {context_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━
{zone_color} مستوى المراقبة ({zone_name}): {exact_zone}

في حال احترام المستوى، نتوقع استهداف:
🎯 {t1}
🎯 {t2}

وفي حالة كسر {t2}، سيستمر {break_dir} لمستويات أبعد.

{rev_color} أما إذا لم يحترم السعر مستوى {exact_zone} وتمكن من اختراقه، فسيستهدف {rev_zone}.
وتعتبر نقطة {rev_zone} هي النقطة الذهبية الفاصلة بين الصعود والهبوط، وباختراقها والثبات أعلاه يمكننا القول إن السعر بدأ يغير اتجاهه ويميل إلى {rev_dir}.
━━━━━━━━━━━━━━━━━━━━━━━━━━'''

    if old_t1 in content:
        content = content.replace(old_t1, new_t1)
        print(f"Updated T1 in {filename}")
    else:
        print(f"T1 not found exactly in {filename}, regex matching...")
        # fallback regex
        content = re.sub(
            r'(تحليل الذهب 🟡)\s+(1W \(الأسبوعي\))\s+(التحيز الأسبوعي: \{w_bias\} \{w_icon\})\s+(1D \(اليومي\))\s+(التحيز اليومي: \{d_bias\} \{d_icon\})\s+(4H - 1H)\s+(\{context_text\})',
            r'📊 التقرير الفني المتقدم للذهب 🟡\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n📅 \2\n   \3\n\n📆 \4\n   \5\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n⏱️ \6 (المدى القصير)\n   \7\n━━━━━━━━━━━━━━━━━━━━━━━━━━',
            content
        )
        content = re.sub(
            r'(\{zone_color\} مستوى )(\{zone_name\})(: \{exact_zone\}\s+في حال احترام المستوى، نتوقع استهداف:\s+)(\{t1\})\s+(\{t2\})',
            r'\1المراقبة (\2)\3🎯 \4\n🎯 \5',
            content
        )
        content = re.sub(
            r'(وفي حالة كسر \{t2\}، سيستمر \{break_dir\} لمستويات) (أقل)\.',
            r'\1 أبعد.',
            content
        )
        content = re.sub(
            r'(وتعتبر نقطة \{rev_zone\} هي النقطة الذهبية الفاصلة بين الصعود والهبوط، وباختراقها والثبات أعلاه يمكننا القول إن السعر بدأ يغير اتجاهه ويميل إلى \{rev_dir\}\.)',
            r'\1\n━━━━━━━━━━━━━━━━━━━━━━━━━━',
            content
        )

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

prettify_templates('Goldbot/bot_spot.py')
prettify_templates('Goldbot/bot_futures.py')
