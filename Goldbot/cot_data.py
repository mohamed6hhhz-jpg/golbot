import time
import datetime
import pandas as pd
import cot_reports as cot

def fetch_gold_cot():
    """
    يجلب تقرير COT الأسبوعي للذهب (Legacy Futures Only).
    """
    current_year = datetime.datetime.now().year
    
    try:
        # محاولة جلب بيانات العام الحالي
        df = cot.cot_year(year=current_year, cot_report_type='legacy_fut')
    except Exception as e:
        try:
            # إذا فشل، حاول العام السابق
            df = cot.cot_year(year=current_year - 1, cot_report_type='legacy_fut')
        except Exception as e2:
            print(f"⚠️ [COT] فشل جلب تقرير COT: {e2}")
            return None

    if df is None or df.empty:
        return None

    # تصفية الذهب (الذهب في كوميكس)
    df_gold = df[df['Market and Exchange Names'].str.contains('GOLD - COMMODITY EXCHANGE', na=False, case=False)].copy()
    if df_gold.empty:
        df_gold = df[df['Market and Exchange Names'].str.contains('GOLD', na=False, case=False)].copy()
    
    if df_gold.empty:
        return None

    # فرز حسب التاريخ للحصول على أحدث تقرير
    df_gold = df_gold.sort_values(by='As of Date in Form YYYY-MM-DD', ascending=True)
    latest = df_gold.iloc[-1]

    report_date = latest.get('As of Date in Form YYYY-MM-DD', 'N/A')
    
    # تحويل القيم إلى أرقام صحيحة
    def _to_int(val):
        try:
            return int(float(val))
        except:
            return 0

    comm_long = _to_int(latest.get('Commercial Positions-Long (All)', 0))
    comm_short = _to_int(latest.get('Commercial Positions-Short (All)', 0))
    comm_net = comm_long - comm_short

    noncomm_long = _to_int(latest.get('Noncommercial Positions-Long (All)', 0))
    noncomm_short = _to_int(latest.get('Noncommercial Positions-Short (All)', 0))
    noncomm_net = noncomm_long - noncomm_short

    return {
        "report_date": report_date,
        "commercials": {
            "long": comm_long,
            "short": comm_short,
            "net": comm_net
        },
        "large_speculators": {
            "long": noncomm_long,
            "short": noncomm_short,
            "net": noncomm_net
        }
    }

if __name__ == "__main__":
    # Test
    res = fetch_gold_cot()
    if res:
        print(f"COT Date: {res['report_date']}")
        print(f"Commercials: Long={res['commercials']['long']} Short={res['commercials']['short']} Net={res['commercials']['net']}")
        print(f"Large Specs: Long={res['large_speculators']['long']} Short={res['large_speculators']['short']} Net={res['large_speculators']['net']}")
    else:
        print("No data found.")
