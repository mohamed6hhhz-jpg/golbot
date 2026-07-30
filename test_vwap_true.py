import yfinance as yf
import pandas as pd
from datetime import datetime

def test_vwap_true():
    gold_5m = yf.download("GC=F", period="5d", interval="5m", progress=False)
    
    if gold_5m is not None and not gold_5m.empty:
        try:
            h = gold_5m.copy()
            if isinstance(h.columns, pd.MultiIndex):
                h.columns = h.columns.droplevel(1)
            
            today_str = h.index[-1].strftime('%Y-%m-%d')
            h = h.loc[today_str].copy()
            
            if not h.empty:
                h['tp'] = (h['High'] + h['Low'] + h['Close']) / 3
                h['tp_vol'] = h['tp'] * h['Volume']
                total_vol = h['Volume'].sum()
                vwap_val = float(h['tp_vol'].sum() / total_vol) if total_vol > 0 else None
                print(f"Calculated VWAP: {vwap_val}")
        except Exception as e:
            print(f"Error: {e}")

test_vwap_true()
