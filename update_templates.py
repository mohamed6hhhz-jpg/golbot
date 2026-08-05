import re

with open('Goldbot/ai_generator_bot6.py', 'r', encoding='utf-8') as f:
    content = f.read()

helper_func = """
def _calc_prob_and_reasons(data: dict):
    hist = data.get('hist_ctx', {})
    gold_chg = round(hist.get('chg_1d', 0), 2) if hist else 0
    gold = data.get("gold", 0)
    vwap = data.get("vwap", gold)
    
    bullish_score = 50
    reasoning_up = []
    reasoning_down = []

    if gold_chg > 0:
        bullish_score += 10
        reasoning_up.append("تغير السعر الإيجابي")
    else:
        bullish_score -= 10
        reasoning_down.append("تغير السعر السلبي")

    if gold > vwap:
        bullish_score += 15
        reasoning_up.append("تمركز السعر فوق VWAP")
    else:
        bullish_score -= 15
        reasoning_down.append("تمركز السعر أسفل VWAP")

    rsi = data.get('rsi', 50)
    if rsi > 55:
        bullish_score += 10
        reasoning_up.append("زخم المشتريين قوي (RSI)")
    elif rsi < 45:
        bullish_score -= 10
        reasoning_down.append("زخم البائعين قوي (RSI)")

    macd = data.get('macd_hist', 0)
    if macd > 0:
        bullish_score += 5
        reasoning_up.append("MACD إيجابي")
    elif macd < 0:
        bullish_score -= 5
        reasoning_down.append("MACD سلبي")

    bullish_score = max(10, min(90, int(bullish_score)))
    bearish_score = 100 - bullish_score

    if not reasoning_up: reasoning_up.append("لا محفزات شرائية واضحة")
    if not reasoning_down: reasoning_down.append("لا محفزات بيعية واضحة")
    
    reason_up_str = " + ".join(reasoning_up[:3])
    reason_down_str = " + ".join(reasoning_down[:3])
    
    if bullish_score > bearish_score:
        stronger_path = "المسار الصاعد (BSL) هو الأقوى"
    elif bearish_score > bullish_score:
        stronger_path = "المسار الهابط (SSL) هو الأقوى"
    else:
        stronger_path = "توازن تام في السيولة"
        
    return bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path


def generate_liquidity_flow_report"""

content = content.replace('def generate_liquidity_flow_report', helper_func)

inline_logic = """        # 3. حساب الاحتماليات والأسباب
        bullish_score = 50
        reasoning_up = []
        reasoning_down = []

        if gold_chg > 0:
            bullish_score += 10
            reasoning_up.append("تغير السعر الإيجابي")
        else:
            bullish_score -= 10
            reasoning_down.append("تغير السعر السلبي")

        if gold > vwap:
            bullish_score += 15
            reasoning_up.append("تمركز السعر فوق VWAP")
        else:
            bullish_score -= 15
            reasoning_down.append("تمركز السعر أسفل VWAP")

        rsi = data.get('rsi', 50)
        if rsi > 55:
            bullish_score += 10
            reasoning_up.append("زخم المشتريين قوي (RSI)")
        elif rsi < 45:
            bullish_score -= 10
            reasoning_down.append("زخم البائعين قوي (RSI)")

        macd = data.get('macd_hist', 0)
        if macd > 0:
            bullish_score += 5
            reasoning_up.append("MACD إيجابي")
        elif macd < 0:
            bullish_score -= 5
            reasoning_down.append("MACD سلبي")

        bullish_score = max(10, min(90, int(bullish_score)))
        bearish_score = 100 - bullish_score

        if not reasoning_up: reasoning_up.append("لا محفزات شرائية واضحة")
        if not reasoning_down: reasoning_down.append("لا محفزات بيعية واضحة")
        
        reason_up_str = " + ".join(reasoning_up[:3])
        reason_down_str = " + ".join(reasoning_down[:3])
        
        if bullish_score > bearish_score:
            stronger_path = "المسار الصاعد (BSL) هو الأقوى"
        elif bearish_score > bullish_score:
            stronger_path = "المسار الهابط (SSL) هو الأقوى"
        else:
            stronger_path = "توازن تام في السيولة"
"""

content = content.replace(inline_logic, "        bullish_score, bearish_score, reason_up_str, reason_down_str, stronger_path = _calc_prob_and_reasons(data)\n")

with open('Goldbot/ai_generator_bot6.py', 'w', encoding='utf-8') as f:
    f.write(content)
