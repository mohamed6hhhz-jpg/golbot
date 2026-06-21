import logging
import time
import os
import asyncio
import numpy as np
from datetime import datetime, timezone, timedelta

from groq import Groq
from Goldbot.data_fetcher import fetch_all_data
from Goldbot.bot import (
    calc_rsi, calc_stoch_rsi, calc_macd, calc_bollinger, calc_ema, calc_adx, calc_cci,
    calc_williams_r, calc_obv, calc_relative_volume, calc_atr, calc_fibonacci, find_swing_levels,
    get_historical_context, get_round_numbers, analyze_timeframe, calc_advanced_trades, calc_price_prediction
)
from Goldbot.ai_generator import generate_ai_template

import requests

log = logging.getLogger(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")
TWELVEDATA_API_KEY = os.environ.get("TWELVEDATA_API_KEY", "a40631d26cb64ba99916a3162880aff3")
TELEGRAM_BOT_TOKEN = "8783502825:AAEEgxaxzgiAxwl4oBp4zl73jmqwBtKCalc"
TARGET_CHATS = [-1002922209855, -1003775201576]
PUBLIC_CHAT_ID = -1003775201576

CAIRO_TZ = timezone(timedelta(hours=3))
MORNING_HOUR_CAI = 8
CLOSING_HOUR_CAI = 23
ALERT_THRESHOLD = 6.0
ROUTINE_MINUTES = 60 # VIP Group gets it every 60 mins

def _http_send(text: str, chat_id: int) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": str(chat_id), "text": text}
    for attempt in range(4):
        try:
            r = requests.post(url, json=payload, timeout=45)
            if r.status_code == 200:
                return True
        except Exception as e:
            time.sleep(2 ** attempt)
    return False

def analyze_market_data(dfs: dict, price: float) -> dict:
    df_1d = dfs.get('1d')
    if df_1d is None or df_1d.empty: return {}
    
    closes = df_1d['Close'].values
    rsi = calc_rsi(closes)
    macd, _, _ = calc_macd(closes)
    atr = calc_atr(df_1d)
    fib = calc_fibonacci(closes)
    
    high = df_1d['High'].iloc[-1]
    low = df_1d['Low'].iloc[-1]
    close = df_1d['Close'].iloc[-1]
    pivot = round((high + low + close) / 3, 2)
    r1 = round((2 * pivot) - low, 2)
    s1 = round((2 * pivot) - high, 2)
    r2 = round(pivot + (high - low), 2)
    s2 = round(pivot - (high - low), 2)
    
    daily_range_high = round(price + atr * 0.5, 2)
    daily_range_low = round(price - atr * 0.5, 2)
    
    tf_15m = analyze_timeframe(dfs.get('15m'), "15m")
    tf_hourly = analyze_timeframe(dfs.get('1h'), "1h")
    tf_4h = analyze_timeframe(dfs.get('4h'), "4h")
    tf_daily = analyze_timeframe(df_1d, "1d")
    
    bias = "bull" if tf_hourly.get('score', 0) > 0 else "bear" if tf_hourly.get('score', 0) < 0 else "neutral"
    
    d_dict = {
        'gold': price, 'atr': atr, 'rsi': rsi, 'macd': macd, 'fib': fib,
        'pivot': pivot, 'r1': r1, 's1': s1, 'r2': r2, 's2': s2,
        'swing_high': find_swing_levels(df_1d)[0],
        'swing_low': find_swing_levels(df_1d)[1],
        'tf_15m': tf_15m, 'tf_hourly': tf_hourly,
    }
    
    trades = calc_advanced_trades(d_dict, bias)
    
    return {
        'price': price, 'rsi': rsi, 'macd': macd, 'atr': atr, 'fib': fib,
        'daily_high': daily_range_high, 'daily_low': daily_range_low,
        'pivot': pivot,
        'timeframes': {'15m': tf_15m, '1h': tf_hourly, '4h': tf_4h, '1d': tf_daily},
        'trades': trades
    }

def generate_24_reports() -> list:
    data = fetch_all_data(TWELVEDATA_API_KEY)
    if not data: return []
        
    spot_analysis = analyze_market_data(data['spot'], data['spot_price'])
    futures_analysis = analyze_market_data(data['futures'], data['futures_price'])
    
    macro_context = {
        'tnx': data['tnx']['Close'].iloc[-1] if data['tnx'] is not None and not data['tnx'].empty else 0,
        'tty': data['tty']['Close'].iloc[-1] if data['tty'] is not None and not data['tty'].empty else 0,
        'inflation': data['inflation'],
        'interest': data['interest_rate'],
        'real_yield': round((data['tnx']['Close'].iloc[-1] if data['tnx'] is not None and not data['tnx'].empty else 0) - data['inflation'], 2),
        'currencies': data['currencies'],
        'dxy': data['dxy']['Close'].iloc[-1] if data['dxy'] is not None and not data['dxy'].empty else 0,
    }
    
    titles = [
        "الأسعار وملخص السوق والفيبوناتشي", "تحليل الإطارات الزمنية", "صفقات زيرو انعكاس", "صفقات السكالبينج",
        "صفقات السوينج", "صفقات اللوت العالي", "التحليل الفني والزخم", "الاقتصاد الكلي", "شهية المخاطرة",
        "عوائد السندات والفائدة والتضخم", "قوة العملات (تأثير DXY)", "الخلاصة المحورية"
    ]
    
    messages = []
    
    for i, title in enumerate(titles, 1):
        ctx = spot_analysis.copy()
        if i >= 8: ctx.update(macro_context)
        msg = generate_ai_template(GROQ_API_KEY, i, title, ctx, is_spot=True)
        messages.append(msg)
        
    for i, title in enumerate(titles, 1):
        ctx = futures_analysis.copy()
        if i >= 8: ctx.update(macro_context)
        msg = generate_ai_template(GROQ_API_KEY, i, title, ctx, is_spot=False)
        messages.append(msg)
        
    return messages

def run_bot(is_alert=False, price_diff=0.0):
    log.info("🚀 Starting v5 Bot Master Loop...")
    last_gold_price = None
    minutes_counter = 0
    last_public_send_time = 0
    morning_sent = False
    closing_sent = False
    
    while True:
        try:
            now_cairo = datetime.now(CAIRO_TZ)
            hour_cairo = now_cairo.hour
            
            # Reset daily flags at midnight
            if hour_cairo == 0:
                morning_sent = False
                closing_sent = False

            current_price = None
            # Just quickly fetch spot price to check alerts without fetching 8 timeframes
            try:
                url = f"https://api.twelvedata.com/price?symbol=XAU/USD&apikey={TWELVEDATA_API_KEY}"
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    p = r.json().get('price')
                    if p: current_price = float(p)
            except: pass
            
            if not current_price:
                # fallback to checking later
                time.sleep(60)
                minutes_counter += 1
                continue
                
            trigger = False
            
            # 1. Morning Trigger
            if hour_cairo == MORNING_HOUR_CAI and not morning_sent:
                trigger = True
                morning_sent = True
            
            # 2. Closing Trigger
            elif hour_cairo == CLOSING_HOUR_CAI and not closing_sent:
                trigger = True
                closing_sent = True
                
            # 3. Alert Trigger
            elif last_gold_price and abs(current_price - last_gold_price) >= ALERT_THRESHOLD:
                trigger = True
                
            # 4. Routine Trigger (VIP every 60 mins)
            elif minutes_counter >= ROUTINE_MINUTES:
                trigger = True
                
            if trigger:
                log.info(f"⚡ Trigger activated! Fetching full data and generating 24 reports...")
                messages = generate_24_reports()
                if messages:
                    # Check if 4 hours passed for public channel
                    now_timestamp = time.time()
                    is_public_allowed = (now_timestamp - last_public_send_time >= 14400)
                    
                    for chat in TARGET_CHATS:
                        if chat == PUBLIC_CHAT_ID and not is_public_allowed:
                            continue
                        for msg in messages:
                            _http_send(msg, chat)
                            time.sleep(1.5)
                            
                    if is_public_allowed:
                        last_public_send_time = now_timestamp
                        
                last_gold_price = current_price
                minutes_counter = 0
            
            time.sleep(60)
            minutes_counter += 1
            
        except Exception as e:
            log.error(f"❌ Master Loop Error: {e}")
            time.sleep(60)
