import re

def prettify_futures(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # T1 update for bot_futures.py
    old_t1 = '''تحليل الذهب 🟡

1W (الأسبوعي)
التحيز الأسبوعي: {w_bias}

1D (اليومي)
التحيز اليومي: {d_bias}

{zone_color} مستوى {zone_name}: {exact_zone}$

في حال احترام المستوى، نتوقع استهداف:
🎯 {t1}$
🎯 {t2}$

وفي حالة كسر {t2}$، سيستمر {break_dir} لمستويات أبعد.

{rev_color} أما إذا لم يحترم السعر مستوى {exact_zone}$ وتمكن من اختراقه، فسيستهدف {rev_zone}$.
وتعتبر نقطة {rev_zone}$ هي النقطة الذهبية الفاصلة بين الصعود والهبوط، وباختراقها والثبات أعلاه يمكننا القول إن السعر بدأ يغير اتجاهه ويميل إلى {rev_dir}.'''

    new_t1 = '''📊 التقرير الفني المتقدم للذهب (الآجل) 🟡
━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 1W (الأسبوعي)
   التحيز الأسبوعي: {w_bias}

📆 1D (اليومي)
   التحيز اليومي: {d_bias}
━━━━━━━━━━━━━━━━━━━━━━━━━━
{zone_color} مستوى المراقبة ({zone_name}): {exact_zone}$

في حال احترام المستوى، نتوقع استهداف:
🎯 {t1}$
🎯 {t2}$

وفي حالة كسر {t2}$، سيستمر {break_dir} لمستويات أبعد.

{rev_color} أما إذا لم يحترم السعر مستوى {exact_zone}$ وتمكن من اختراقه، فسيستهدف {rev_zone}$.
وتعتبر نقطة {rev_zone}$ هي النقطة الذهبية الفاصلة بين الصعود والهبوط، وباختراقها والثبات أعلاه يمكننا القول إن السعر بدأ يغير اتجاهه ويميل إلى {rev_dir}.
━━━━━━━━━━━━━━━━━━━━━━━━━━'''

    if old_t1 in content:
        content = content.replace(old_t1, new_t1)
        print("Updated T1 in bot_futures.py EXACT MATCH")
    else:
        print("No exact match, trying regex...")
        content = re.sub(
            r'تحليل الذهب 🟡\s*1W \(الأسبوعي\)\s*التحيز الأسبوعي: \{w_bias\}\s*1D \(اليومي\)\s*التحيز اليومي: \{d_bias\}',
            r'📊 التقرير الفني المتقدم للذهب (الآجل) 🟡\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n📅 1W (الأسبوعي)\n   التحيز الأسبوعي: {w_bias}\n\n📆 1D (اليومي)\n   التحيز اليومي: {d_bias}\n━━━━━━━━━━━━━━━━━━━━━━━━━━',
            content
        )
        content = re.sub(
            r'(\{zone_color\}) مستوى (\{zone_name\}): (\{exact_zone\}\$)',
            r'\1 مستوى المراقبة (\2): \3',
            content
        )
        content = re.sub(
            r'(وتعتبر نقطة \{rev_zone\}\$ هي النقطة الذهبية الفاصلة بين الصعود والهبوط، وباختراقها والثبات أعلاه يمكننا القول إن السعر بدأ يغير اتجاهه ويميل إلى \{rev_dir\}\.)',
            r'\1\n━━━━━━━━━━━━━━━━━━━━━━━━━━',
            content
        )

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

prettify_futures('Goldbot/bot_futures.py')
