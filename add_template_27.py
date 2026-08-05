def append_template():
    with open('Goldbot/ai_generator_bot6.py', 'a', encoding='utf-8') as f:
        f.write('''

def generate_liquidity_target_timing_report(data: dict) -> str | None:
    import traceback
    try:
        gold = data.get('gold', 0)
        atr = data.get('atr', 0)
        hist = data.get('hist_ctx', {})
        chg_1d = hist.get('chg_1d', 0) if hist else 0
        
        # أهداف السيولة الأقرب (استخدام R1, S1 للسيولة القريبة و R2, S2 للأهداف الأبعد)
        r1 = data.get('r1', 0)
        s1 = data.get('s1', 0)
        
        if not (gold and atr and r1 and s1):
            log.warning("⚠️ بيانات غير مكتملة لتوليد تقرير الوجهة القادمة للسيولة.")
            return None
            
        # تقدير الاتجاه اللحظي بناءً على التغير أو موقع السعر مقارنة بالبيفوت
        pivot = data.get('pivot', 0)
        if gold > pivot or chg_1d > 0:
            target_direction = "صاعد (Bullish)"
            target_price = r1
            distance = target_price - gold
        else:
            target_direction = "هابط (Bearish)"
            target_price = s1
            distance = gold - target_price
            
        # تقدير الوقت بناءً على ATR الساعي أو اليومي (إذا افترضنا أن ATR هو تذبذب يومي، فنقسمه على 24 للحصول على السرعة التقريبية)
        # سرعة السعر بالساعة تقريباً = atr / 12 (بافتراض أوقات الذروة)
        speed_per_hour = atr / 12.0 if atr else 1.0
        hours_estimated = distance / speed_per_hour if speed_per_hour > 0 else 0
        
        if hours_estimated < 1:
            time_frame = "خلال أقل من ساعة"
        elif hours_estimated < 4:
            time_frame = "خلال 1 إلى 4 ساعات"
        elif hours_estimated < 12:
            time_frame = "خلال 4 إلى 12 ساعة (بنهاية جلسة اليوم)"
        else:
            time_frame = "خلال 12 إلى 24 ساعة (جلسة الغد)"
            
        context = f"""
معلومات حية ودقيقة 100%:
- السعر الفوري للذهب الآن: {gold}$
- اتجاه السيولة اللحظي الأرجح: {target_direction}
- المستهدف الرقمي للسيولة (أقرب تجمع سيولة): {target_price}$
- متوسط حركة السوق الحالي (ATR): {atr} دولار
- الإطار الزمني المقدر رياضياً للوصول: {time_frame}
"""

        system_prompt = """أنت محلل أسواق مالية متقدم جداً، متخصص في تحليل السيولة (Liquidity Concepts) وحسابات الوقت والسرعة.
قواعد صارمة:
1. استخدم الأرقام المرفقة بدقة شديدة ولا تخترع أي أرقام.
2. اشرح باحترافية وسهولة كيف وأين تتجه السيولة الان، ولماذا هذا الهدف هو المنطقي.
3. قدم شرحاً واضحاً للزمن المتوقع للوصول ولماذا (اربطه بسرعة السوق الحالية).
4. اكتب بأسلوب جذاب ومقسم بشكل مريح للعين، بدون إخلاء مسؤولية.

- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).
"""

        user_prompt = f"""قم بإنشاء "تقرير الوجهة القادمة للسيولة والزمن المتوقع" بناءً على البيانات التالية.
استخدم هذا الهيكل تماماً:
🎯 الوجهة القادمة للسيولة والزمن المتوقع ⏳

▪️ اتجاه السيولة الحالي: [اشرح الاتجاه]
▪️ المستهدف السعري (Target): {target_price}$ (شرح سبب استهداف هذا الرقم)
▪️ الإطار الزمني للوصول: {time_frame} (كيف تم تقديره بناءً على سرعة السوق)

💡 التحليل الفني والسيولة:
[شرح متقدم وموجز لحركة السيولة من الآن وحتى الوصول للهدف]

⚖️ الحكم النهائي:
[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]

البيانات الحقيقية:
{context}
"""
        
        ai_content = generate_robust_ai_response(system_prompt, user_prompt, max_tokens=800)
        return ai_content
    except Exception as e:
        log.error(f"❌ فشل توليد تقرير الوجهة القادمة للسيولة: {e}\\n{traceback.format_exc()}")
        return None
''')

if __name__ == "__main__":
    append_template()
