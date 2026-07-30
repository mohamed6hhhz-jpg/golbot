import re

def fix_rev(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
        
    old_code = r'''    # ── انعكاس \(Counter-trend\) ──
    sl_rev  = round\(atr \* 0\.28, 2\)
    if rsi <= 50:
        t = dict\(entry=round\(gold, 2\), sl=round\(gold - sl_rev, 2\), risk=sl_rev,
                 t1=round\(gold \+ atr\*0\.4, 2\), t2=round\(gold \+ atr\*0\.8, 2\), t3=round\(gold \+ atr\*1\.5, 2\),
                 market=market_name, tf='1-4س', typ='زيرو انعكاس 🔄', dir='buy'\)
        trades\['rev_buy'\] = t
    else:
        t = dict\(entry=round\(gold, 2\), sl=round\(gold \+ sl_rev, 2\), risk=sl_rev,
                 t1=round\(gold - atr\*0\.4, 2\), t2=round\(gold - atr\*0\.8, 2\), t3=round\(gold - atr\*1\.5, 2\),
                 market=market_name, tf='1-4س', typ='زيرو انعكاس 🔄', dir='sell'\)
        trades\['rev_sell'\] = t'''

    new_code = '''    # ── انعكاس (Counter-trend) ──
    sl_rev = max(round(atr * 0.28, 2), 3.0)
    
    rev_buy_entry = round(min(s2, sw_l), 2) if sw_l > 0 else round(s2, 2)
    trades['rev_buy'] = dict(
        entry=rev_buy_entry, sl=round(rev_buy_entry - sl_rev, 2), risk=sl_rev,
        t1=round(rev_buy_entry + atr * 0.5, 2), 
        t2=round(rev_buy_entry + atr * 1.0, 2), 
        t3=round(rev_buy_entry + atr * 1.5, 2),
        market=market_name, tf='1-4س', typ='زيرو انعكاس 🔄', dir='buy'
    )
    
    rev_sell_entry = round(max(r2, sw_h), 2) if sw_h > 0 else round(r2, 2)
    trades['rev_sell'] = dict(
        entry=rev_sell_entry, sl=round(rev_sell_entry + sl_rev, 2), risk=sl_rev,
        t1=round(rev_sell_entry - atr * 0.5, 2), 
        t2=round(rev_sell_entry - atr * 1.0, 2), 
        t3=round(rev_sell_entry - atr * 1.5, 2),
        market=market_name, tf='1-4س', typ='زيرو انعكاس 🔄', dir='sell'
    )'''
    
    new_content = re.sub(old_code, new_code, content)
    
    if new_content != content:
        print(f"Fixed {filename}")
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(new_content)
    else:
        print(f"Failed to match in {filename}")

fix_rev('Goldbot/bot_spot.py')
fix_rev('Goldbot/bot_futures.py')
