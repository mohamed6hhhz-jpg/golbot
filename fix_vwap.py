import re

def fix_vwap(filename, mode='spot'):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
        
    old_code = r'''    # ── \[4\] مستويات محسّنة: VWAP \+ سابق أسبوع/شهر \+ مناطق الطلب/عرض ──
    # VWAP \(سعر مرجح بالحجم\) من بيانات الساعي
    vwap = None
    if gold_hourly is not None and len\(gold_hourly\) > 0:
        try:
            h = gold_hourly.copy\(\)
            h\['tp'\]     = \(h\['High'\] \+ h\['Low'\] \+ h\['Close'\]\) / 3
            h\['tp_vol'\] = h\['tp'\] \* h\['Volume'\]
            total_vol   = h\['Volume'\].sum\(\)
            vwap = round\(float\(h\['tp_vol'\].sum\(\) / total_vol\), 2\) if total_vol > 0 else None
        except Exception:
            vwap = None'''

    new_code = '''    # ── [4] مستويات محسّنة: VWAP الحقيقي (Intraday) ──
    vwap = None
    if gold_5m is not None and not gold_5m.empty:
        try:
            h = gold_5m.copy()
            # التعامل مع MultiIndex في مكتبة yfinance الجديدة
            if isinstance(h.columns, pd.MultiIndex):
                h.columns = h.columns.droplevel(1)
            
            # فلترة بيانات اليوم الحالي فقط لحساب Intraday VWAP
            today_str = h.index[-1].strftime('%Y-%m-%d')
            h = h.loc[today_str]
            
            if not h.empty:
                h['tp'] = (h['High'] + h['Low'] + h['Close']) / 3
                h['tp_vol'] = h['tp'] * h['Volume']
                total_vol = h['Volume'].sum()
                vwap_val = float(h['tp_vol'].sum() / total_vol) if total_vol > 0 else None
                
                if vwap_val is not None:
                    vwap = round(vwap_val, 2)
                    # تعديل سعر الفوليوم للفوري بناء على الفارق بين العقود الآجلة والفوري (Contango/Basis)
                    if "spot" == "{mode}" and gold_spot and gold_futures:
                        basis = gold_futures - gold_spot
                        vwap = round(vwap_val - basis, 2)
        except Exception as e:
            vwap = None'''.replace('{mode}', mode)
    
    new_content = re.sub(old_code, new_code, content)
    
    if new_content != content:
        print(f"Fixed VWAP in {filename}")
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(new_content)
    else:
        print(f"Failed to match in {filename}")

fix_vwap('Goldbot/bot_spot.py', 'spot')
fix_vwap('Goldbot/bot_futures.py', 'futures')
