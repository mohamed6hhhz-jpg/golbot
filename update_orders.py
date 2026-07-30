import re

def update_file(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    new_order_groups = '''    order_groups = [
        ('🛒 صفقات السكالبينج السريع (5 - 10 دقائق)',
         ['scalp_5m_buy','scalp_5m_sell','tight_scalp_buy','tight_scalp_sell']),
        ('🏹 صفقات السكالبينج الممتد (15 - 30 دقيقة)',
         ['scalp_buy','scalp_sell','scalp_30m_buy','scalp_30m_sell']),
        ('⏱️ صفقات التداول اللحظي (ساعة - 4 ساعات)',
         ['scalp_1h_buy','scalp_1h_sell','scalp_4h_buy','scalp_4h_sell']),
        ('📅 صفقات يومية وأسبوعية (Intraday / Weekly)',
         ['daily_buy','daily_sell','weekly_buy','weekly_sell']),
        ('🌊 سوينج طويل وشهري (Swing / Monthly)',
         ['long_swing_buy','long_swing_sell','monthly_buy','monthly_sell','swing_buy','swing_sell']),
        ('💰 صفقات لوت عالي (بالميلي - جودة > 90%)',
         ['high_lot_buy','high_lot_sell']),
        ('🔄 صفقات زيرو انعكاس (Counter-trend - جودة > 90%)',
         ['rev_buy','rev_sell']),
    ]'''

    # The regex targets the old order_groups list regardless of unicode escapes
    pattern = re.compile(r'    order_groups = \[.*?\]', re.DOTALL)
    new_content = pattern.sub(new_order_groups, content)
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"Updated {filename}")

update_file('Goldbot/bot_spot.py')
update_file('Goldbot/bot_futures.py')
