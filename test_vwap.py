import yfinance as yf
import pandas as pd

def test_vwap():
    df = yf.download("GC=F", period="5d", interval="5m", progress=False)
    if df.empty:
        print("DF empty")
        return
        
    today_str = df.index[-1].strftime('%Y-%m-%d')
    h = df.loc[today_str].copy()
    
    h['tp'] = (h['High'] + h['Low'] + h['Close']) / 3
    # Yfinance returns columns as MultiIndex if multiple tickers, but we passed string so it's normal.
    # But let's check
    if 'Volume' in h.columns:
        if isinstance(h['Volume'], pd.DataFrame):
            h['Volume'] = h['Volume'].iloc[:, 0]
        h['tp_vol'] = h['tp'] * h['Volume']
        total_vol = h['Volume'].sum()
        vwap = float(h['tp_vol'].sum() / total_vol) if total_vol > 0 else None
        print(f"Today's Futures VWAP: {vwap}")
    else:
        print("No volume")

test_vwap()
