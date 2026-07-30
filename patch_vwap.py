import re

def fix_vwap(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # The block we want to replace:
    old_vwap_regex = r"# ── \[4\] مستويات محسّنة: VWAP الحقيقي \(Intraday\) ──\s+vwap = None\s+if gold_5m is not None and not gold_5m\.empty:.*?except Exception as e:\s+vwap = None"
    
    new_vwap = '''# ── [4] مستويات محسّنة: VWAP الحقيقي (Intraday) ──
    vwap = None
    if gold_5m is not None and not gold_5m.empty:
        try:
            h = gold_5m.copy()
            import pandas as pd
            if isinstance(h.columns, pd.MultiIndex):
                h.columns = h.columns.droplevel(1)
            
            # حساب VWAP دقيق: أخذ آخر 24 ساعة من التداول الفعلي بدلا من الاعتماد على تاريخ اليوم فقط لتجنب مشكلة فروق التوقيت
            h = h.tail(288) # 288 شمعة 5 دقائق = 24 ساعة
            
            if not h.empty:
                h['tp'] = (h['High'] + h['Low'] + h['Close']) / 3
                h['tp_vol'] = h['tp'] * h['Volume']
                total_vol = h['Volume'].sum()
                vwap_val = float(h['tp_vol'].sum() / total_vol) if total_vol > 0 else None
                
                if vwap_val is not None:
                    vwap = round(vwap_val, 2)
                    # تعديل سعر الفوليوم للفوري بناء على الفارق بين العقود الآجلة والفوري
                    if "spot" == "spot" and gold_spot and gold_futures:
                        basis = gold_futures - gold_spot
                        vwap = round(vwap_val - basis, 2)
        except Exception as e:
            vwap = None'''

    if "bot_futures" in filename:
        new_vwap = new_vwap.replace('if "spot" == "spot" and gold_spot and gold_futures:', 'if False:') # No basis adjustment for futures

    content = re.sub(old_vwap_regex, new_vwap, content, flags=re.DOTALL)

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

fix_vwap('Goldbot/bot_spot.py')
fix_vwap('Goldbot/bot_futures.py')
