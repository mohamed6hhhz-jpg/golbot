import yfinance as yf
import pandas as pd
import requests
import time
import logging
from datetime import datetime, timezone, timedelta
import numpy as np

log = logging.getLogger(__name__)

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
    try:
        url = f"https://api.twelvedata.com/price?symbol=XAU/USD&apikey={twelvedata_api_key}"
        r = requests.get(url, timeout=6, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            p = r.json().get('price')
            if p and float(p) > 1000:
                return round(float(p), 2)
    except: pass
    
    try:
        r = requests.get("https://api.metals.live/v1/spot/gold", timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            j = r.json()
            p = j.get('price') or j.get('gold') or (j[0].get('gold') if isinstance(j, list) else None)
            if p and float(p) > 1000:
                return round(float(p), 2)
    except: pass
    return None

def get_macro_data() -> dict:
    macro = {
        'inflation_annual': 2.5,
        'inflation_monthly': 0.2,
        'fed_funds_rate': 5.25,
        'yield_10y': 4.2,
        'yield_30y': 4.5,
        'real_yield': 2.75,
        'dxy': 104.5,
        'silver': 30.5,
        'copper': 4.1
    }
    
    # DXY
    df_dxy = fetch_yfinance_history("DX-Y.NYB", "1d", "1d")
    if df_dxy is not None and not df_dxy.empty:
        macro['dxy'] = round(df_dxy['Close'].iloc[-1], 2)
        
    # 10Y Yield
    df_10y = fetch_yfinance_history("^TNX", "1d", "1d")
    if df_10y is not None and not df_10y.empty:
        macro['yield_10y'] = round(df_10y['Close'].iloc[-1], 2)
        
    # 30Y Yield
    df_30y = fetch_yfinance_history("^TYX", "1d", "1d")
    if df_30y is not None and not df_30y.empty:
        macro['yield_30y'] = round(df_30y['Close'].iloc[-1], 2)
        
    # Silver
    df_si = fetch_yfinance_history("SI=F", "1d", "1d")
    if df_si is not None and not df_si.empty:
        macro['silver'] = round(df_si['Close'].iloc[-1], 2)
        
    # Copper
    df_hg = fetch_yfinance_history("HG=F", "1d", "1d")
    if df_hg is not None and not df_hg.empty:
        macro['copper'] = round(df_hg['Close'].iloc[-1], 2)
        
    # Interest Rate (FRED)
    try:
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS"
        r = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            for line in reversed(r.text.strip().split('\\n')[1:]):
                parts = line.split(',')
                if len(parts) == 2 and parts[1].strip() not in ('.', '', 'NA'):
                    macro['fed_funds_rate'] = round(float(parts[1].strip()), 2)
                    break
    except: pass

    # Inflation (FRED 10Y Breakeven as proxy if BLS fails)
    try:
        fred_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10YIE"
        r = requests.get(fred_url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            for line in reversed(r.text.strip().split('\\n')[1:]):
                parts = line.split(',')
                if len(parts) == 2 and parts[1].strip() not in ('.', '', 'NA'):
                    macro['inflation_annual'] = round(float(parts[1].strip()), 2)
                    break
    except: pass
    
    macro['real_yield'] = round(macro['fed_funds_rate'] - macro['inflation_annual'], 2)
    return macro

def infer_whale_liquidity(df_1h: pd.DataFrame, df_1d: pd.DataFrame) -> dict:
    """Smart Inference algorithm to estimate whale positions and liquidity zones."""
    whales = {
        'buy_liquidity_zones': [],
        'sell_liquidity_zones': [],
        'recent_injection_dir': 'Neutral',
        'injection_volume': 0,
        'positions_above': 0.0,
        'positions_below': 0.0
    }
    
    if df_1h is None or df_1h.empty or len(df_1h) < 24:
        return whales

    # Look for the largest volume spike in the last 24 hours
    last_24 = df_1h.tail(24)
    max_vol_idx = last_24['Volume'].idxmax()
    max_vol_row = last_24.loc[max_vol_idx]
    
    avg_vol = last_24['Volume'].mean()
    
    if max_vol_row['Volume'] > avg_vol * 2.0:
        # Significant whale activity
        is_bullish_spike = max_vol_row['Close'] > max_vol_row['Open']
        whales['recent_injection_dir'] = 'صعودية (شراء)' if is_bullish_spike else 'هبوطية (بيع)'
        whales['injection_volume'] = int(max_vol_row['Volume'])
    
    # Calculate Liquidity Zones based on recent daily wicks
    if df_1d is not None and not df_1d.empty and len(df_1d) >= 5:
        last_5d = df_1d.tail(5)
        highest = last_5d['High'].max()
        lowest = last_5d['Low'].min()
        
        whales['sell_liquidity_zones'] = [round(highest + 5, 2), round(highest + 15, 2)]
        whales['buy_liquidity_zones'] = [round(lowest - 5, 2), round(lowest - 15, 2)]
        whales['positions_above'] = round(highest, 2)
        whales['positions_below'] = round(lowest, 2)

    return whales

def fetch_all_data_v5(twelvedata_api_key: str) -> dict:
    data = {}
    
    df_5m = fetch_yfinance_history("GC=F", period="5d", interval="5m")
    df_15m = fetch_yfinance_history("GC=F", period="5d", interval="15m")
    df_1h = fetch_yfinance_history("GC=F", period="30d", interval="1h")
    df_1d = fetch_yfinance_history("GC=F", period="90d", interval="1d")
    df_1wk = fetch_yfinance_history("GC=F", period="2y", interval="1wk")
    df_1mo = fetch_yfinance_history("GC=F", period="5y", interval="1mo")
    
    df_10m = resample_dataframe(df_5m, '10min')
    df_30m = resample_dataframe(df_15m, '30min')
    df_4h = resample_dataframe(df_1h, '4h')
    
    futures_dfs = {
        '5m': df_5m, '10m': df_10m, '15m': df_15m, '30m': df_30m,
        '1h': df_1h, '4h': df_4h, '1d': df_1d, '1wk': df_1wk, '1mo': df_1mo
    }
    
    spot_price = get_real_time_spot(twelvedata_api_key)
    futures_price = df_1d['Close'].iloc[-1] if (df_1d is not None and not df_1d.empty) else None
    
    spot_offset = (spot_price - futures_price) if spot_price and futures_price else -10.0
    
    spot_dfs = {tf: simulate_spot(df, spot_offset) for tf, df in futures_dfs.items()}
    
    data['futures_dfs'] = futures_dfs
    data['spot_dfs'] = spot_dfs
    data['futures_price'] = futures_price
    data['spot_price'] = spot_price
    data['macro'] = get_macro_data()
    data['futures_whales'] = infer_whale_liquidity(df_1h, df_1d)
    data['spot_whales'] = infer_whale_liquidity(spot_dfs['1h'], spot_dfs['1d'])

    return data
