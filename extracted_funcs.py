def _s_nums(d):
    """مساعد: يرجع كل الارقام الاساسية مع ضمان عدم وجود اصفار او None"""
    gold  = float(d.get('gold', 0) or 0)
    atr   = float(d.get('atr', 0) or 0) or 50.0
    pivot = float(d.get('pivot', 0) or 0) or gold
    rsi   = float(d.get('rsi', 50) or 50)
    macd  = float(d.get('macd', 0) or 0)
    r1 = float(d.get('r1', 0) or 0) or round(pivot + atr * 0.9, 2)
    r2 = float(d.get('r2', 0) or 0) or round(pivot + atr * 1.8, 2)
    r3 = float(d.get('r3', 0) or 0) or round(pivot + atr * 2.7, 2)
    s1 = float(d.get('s1', 0) or 0) or round(pivot - atr * 0.9, 2)
    s2 = float(d.get('s2', 0) or 0) or round(pivot - atr * 1.8, 2)
    s3 = float(d.get('s3', 0) or 0) or round(pivot - atr * 2.7, 2)
    swing_h = float(d.get('swing_high', 0) or 0) or r2
    swing_l = float(d.get('swing_low',  0) or 0) or s2
    return dict(gold=gold, atr=atr, pivot=pivot, rsi=rsi, macd=macd,
                r1=r1, r2=r2, r3=r3, s1=s1, s2=s2, s3=s3,
                swing_h=swing_h, swing_l=swing_l)

def _s_trades(d, n):
    """مساعد: يرجع الصفقات من adv_trades او يحسبها رياضيا"""
    adv  = d.get('adv_trades', {}) or {}
    nums = _s_nums(d)
    g, a, pv = nums['gold'], nums['atr'], nums['pivot']
    r1, r2 = nums['r1'], nums['r2']
    s1, s2 = nums['s1'], nums['s2']
    sh, sl = nums['swing_h'], nums['swing_l']

    if n == 'scalp_buy':
        t = adv.get('scalp_buy')
        if not t:
            ent = round(s1 + (pv - s1) * 0.25, 2)
            slv = round(ent - a * 0.4, 2)
            t = {'entry': ent, 'sl': slv, 'risk': round(ent - slv, 2),
                 't1': round(ent + a * 0.45, 2), 't2': round(pv, 2), 't3': round(r1, 2)}
    elif n == 'scalp_sell':
        t = adv.get('scalp_sell')
        if not t:
            ent = round(r1 - (r1 - pv) * 0.25, 2)
            slv = round(ent + a * 0.4, 2)
            risk = round(slv - ent, 2)
            _t1 = round(ent - a * 0.45, 2)          # هدف أول: أقرب (R:R ~1.1x)
            _t2 = round(ent - a * 0.72, 2)           # هدف ثاني: أبعد دائماً (R:R ~1.8x)
            _t3 = round(s1, 2)                        # هدف ثالث: S1
            # ضمان الترتيب التنازلي للبيع (T1 > T2 > T3)
            if _t2 >= _t1: _t2 = round(_t1 - a * 0.1, 2)
            if _t3 >= _t2: _t3 = round(_t2 - a * 0.1, 2)
            t = {'entry': ent, 'sl': slv, 'risk': risk,
                 't1': _t1, 't2': _t2, 't3': _t3}
    elif n == 'swing_buy':
        t = adv.get('swing_buy') or adv.get('long_swing_buy')
        if not t:
            ent = round(s2, 2)
            slv = round(s2 - a * 0.5, 2)
            t = {'entry': ent, 'sl': slv, 'risk': round(ent - slv, 2),
                 't1': round(s1, 2), 't2': round(pv, 2), 't3': round(r1, 2)}
    elif n == 'swing_sell':
        t = adv.get('swing_sell') or adv.get('long_swing_sell')
        if not t:
            ent = round(r2, 2)
            slv = round(r2 + a * 0.5, 2)
            risk = round(slv - ent, 2)
            t = {'entry': ent, 'sl': slv, 'risk': risk,
                 't1': round(r1, 2),          # هدف أول: R1 (مكسب فوري)
                 't2': round(pv, 2),           # هدف ثاني: المحور (سوينج متوسط)
                 't3': round(s1, 2)}           # هدف ثالث: S1 (سوينج ممتد)
    elif n == 'rev_buy':
        t = adv.get('rev_buy')
        if not t:
            ent = round(sl + a * 0.3, 2)
            slv = round(sl - a * 0.2, 2)
            t = {'entry': ent, 'sl': slv, 'risk': round(ent - slv, 2),
                 't1': round(ent + a * 0.5, 2), 't2': round(pv, 2), 't3': round(r1, 2)}
    elif n == 'rev_sell':
        t = adv.get('rev_sell')
        if not t:
            ent = round(sh - a * 0.3, 2)
            slv = round(sh + a * 0.2, 2)
            t = {'entry': ent, 'sl': slv, 'risk': round(slv - ent, 2),
                 't1': round(ent - a * 0.5, 2), 't2': round(pv, 2), 't3': round(s1, 2)}
    elif n == 'high_lot_buy':
        t = adv.get('high_lot_buy')
        if not t:
            fib   = d.get('fib', {}) or {}
            ent   = float(fib.get('61.8%', 0) or 0) or s2
            slv   = round(ent - a * 0.25, 2)
            t = {'entry': round(ent, 2), 'sl': slv, 'risk': round(ent - slv, 2),
                 't1': round(fib.get('50.0%', pv) or pv, 2),
                 't2': round(fib.get('38.2%', r1) or r1, 2),
                 't3': round(fib.get('23.6%', r2) or r2, 2)}
    elif n == 'high_lot_sell':
        t = adv.get('high_lot_sell')
        if not t:
            fib   = d.get('fib', {}) or {}
            ent   = float(fib.get('23.6%', 0) or 0) or r2
            slv   = round(ent + a * 0.25, 2)
            t = {'entry': round(ent, 2), 'sl': slv, 'risk': round(slv - ent, 2),
                 't1': round(fib.get('38.2%', r1) or r1, 2),
                 't2': round(fib.get('50.0%', pv) or pv, 2),
                 't3': round(fib.get('61.8%', s1) or s1, 2)}
    else:
        t = {}
    return t or {}

