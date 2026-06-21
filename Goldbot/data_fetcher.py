import yfinance as yf
import pandas as pd
import requests
import time
import logging
from datetime import datetime, timezone, timedelta
import numpy as np

log = logging.getLogger(__name__)
CAIRO_TZ = timezone(timedelta(hours=3))

def fetch_yfinance_history(symbol: str, period: str, interval: str, max_retries: int = 4) -> pd.DataFrame | None:
    for attempt in range(max_retries):
        try:
            df = yf.Ticker(symbol).history(period=period, interval=interval)
            if not df.empty:
                return df
            time.sleep(1)
        except Exception as e:
            log.warning(f"[yfinance] {symbol} [{interval}] محاولة {attempt+1}: {e}")
            time.sleep(2 ** attempt)
    return None

def resample_dataframe(df: pd.DataFrame, timeframe: str) -> pd.DataFrame | None:
    if df is None or df.empty:
        return None
    try:
        resampled = df.resample(timeframe).agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()
        return resampled
    except Exception as e:
        log.error(f"Error resampling to {timeframe}: {e}")
        return None

def simulate_spot(df_futures: pd.DataFrame, offset: float) -> pd.DataFrame | None:
    if df_futures is None or df_futures.empty:
        return None
    df_spot = df_futures.copy()
    for col in ['Open', 'High', 'Low', 'Close']:
        df_spot[col] = df_spot[col] + offset
    return df_spot

def get_real_time_spot(twelvedata_api_key: str) -> float | None:
    # 1. TwelveData
    try:
        url = f"https://api.twelvedata.com/price?symbol=XAU/USD&apikey={twelvedata_api_key}"
        r = requests.get(url, timeout=6, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            p = r.json().get('price')
            if p and float(p) > 1000:
                return round(float(p), 2)
    except: pass
    # 2. metals.live
    try:
        r = requests.get("https://api.metals.live/v1/spot/gold", timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            j = r.json()
            p = j.get('price') or j.get('gold') or (j[0].get('gold') if isinstance(j, list) else None)
            if p and float(p) > 1000:
                return round(float(p), 2)
    except: pass
    # 3. open.er-api
    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5)
        if r.status_code == 200:
            xau_r = r.json().get('rates', {}).get('XAU')
            if xau_r and xau_r > 0:
                p = round(1.0 / xau_r, 2)
                if p > 1000: return p
    except: pass
    return None

def get_inflation() -> float:
    # BLS
    try:
        import json
        bls_url = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
        payload = json.dumps({"seriesid": ["CUUR0000SA0"], "startyear": str(datetime.now().year-2), "endyear": str(datetime.now().year)})
        r = requests.post(bls_url, data=payload, headers={'Content-Type': 'application/json'}, timeout=6)
        if r.status_code == 200:
            series = r.json().get('Results', {}).get('series', [])
            if series:
                data = sorted(series[0].get('data', []), key=lambda x: (x.get('year', ''), x.get('period', '')))
                if len(data) >= 13:
                    latest = float(data[-1]['value'])
                    year_ago = float(data[-13]['value'])
                    return round((latest - year_ago) / year_ago * 100, 2)
    except: pass
    # FRED
    try:
        fred_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10YIE"
        r = requests.get(fred_url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            for line in reversed(r.text.strip().split('\\n')[1:]):
                parts = line.split(',')
                if len(parts) == 2 and parts[1].strip() not in ('.', '', 'NA'):
                    return round(float(parts[1].strip()), 2)
    except: pass
    return 2.5 # default

def get_fed_funds_rate() -> float:
    try:
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS"
        r = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            for line in reversed(r.text.strip().split('\\n')[1:]):
                parts = line.split(',')
                if len(parts) == 2 and parts[1].strip() not in ('.', '', 'NA'):
                    return round(float(parts[1].strip()), 2)
    except: pass
    return 5.25 # default

def fetch_all_data(twelvedata_api_key: str) -> dict | None:
    data = {}
    
    # 1. Gold Futures Timeframes
    df_5m = fetch_yfinance_history("GC=F", period="5d", interval="5m")
    if df_5m is None: return None
    
    df_15m = fetch_yfinance_history("GC=F", period="5d", interval="15m")
    df_1h = fetch_yfinance_history("GC=F", period="30d", interval="1h")
    df_1d = fetch_yfinance_history("GC=F", period="90d", interval="1d")
    df_1wk = fetch_yfinance_history("GC=F", period="2y", interval="1wk")
    df_1mo = fetch_yfinance_history("GC=F", period="5y", interval="1mo")
    
    # Resampled
    df_10m = resample_dataframe(df_5m, '10min')
    df_30m = resample_dataframe(df_15m, '30min')
    df_4h = resample_dataframe(df_1h, '4h')
    
    futures_dfs = {
        '5m': df_5m, '10m': df_10m, '15m': df_15m, '30m': df_30m,
        '1h': df_1h, '4h': df_4h, '1d': df_1d, '1wk': df_1wk, '1mo': df_1mo
    }
    
    # 2. Spot Calculation
    spot_price = get_real_time_spot(twelvedata_api_key)
    futures_price = df_1d['Close'].iloc[-1] if not df_1d.empty else None
    
    spot_offset = (spot_price - futures_price) if spot_price and futures_price else -10.0
    
    spot_dfs = {}
    for tf, df in futures_dfs.items():
        spot_dfs[tf] = simulate_spot(df, spot_offset)
        
    data['futures'] = futures_dfs
    data['spot'] = spot_dfs
    data['spot_price'] = spot_price
    data['futures_price'] = futures_price
    
    # 3. Macro & Bonds
    data['tnx'] = fetch_yfinance_history("^TNX", period="5d", interval="1d")
    data['tty'] = fetch_yfinance_history("^TYX", period="5d", interval="1d") # 30Y
    data['inflation'] = get_inflation()
    data['interest_rate'] = get_fed_funds_rate()
    
    # 4. Currencies
    currencies = ['EURUSD=X', 'GBPUSD=X', 'AUDUSD=X', 'NZDUSD=X', 'JPY=X', 'CHF=X', 'CAD=X']
    data['currencies'] = {}
    for c in currencies:
        df = fetch_yfinance_history(c, period="5d", interval="1d")
        if df is not None and len(df) >= 2:
            change = (df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2] * 100
            data['currencies'][c] = change
            
    # DXY
    data['dxy'] = fetch_yfinance_history("DX-Y.NYB", period="5d", interval="1d")
    
    return data
