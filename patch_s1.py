with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Fix 1: tf_gold_impact
text = text.replace('return "↔ محايد — لا تأثير واضح على الذهب"', 'return "↔ محايد — مسار عرضي تجميعي للذهب (ترقب للسيولة)"')

# Fix 2: _macd_gold_impact
text = text.replace('return "⚪ زخم ضعيف → لا تأثير واضح على الذهب"', 'return "⚪ زخم ضعيف → تذبذب عرضي للذهب (ترقب لضخ السيولة)"')

# Fix 3: PC ratio formatting in template 1
old_pc = "   🎯 نسبة P/C:{f\"{d['gld_pcr']}({d['pcr_source']})\" if d['gld_pcr'] else '—'} {'→تشاؤم (بيع سائد)' if d['gld_pcr'] and d['gld_pcr']>1.2 else '→تفاؤل (شراء سائد)' if d['gld_pcr'] and d['gld_pcr']<0.8 else '→توازن' if d['gld_pcr'] else ''}"
new_pc = "   🎯 نسبة (Put/Call Ratio): {f\"{d['gld_pcr']}\" if d['gld_pcr'] else '—'} {'→ تشاؤم مؤسساتي (سيطرة عقود البيع)' if d['gld_pcr'] and d['gld_pcr']>1.2 else '→ تفاؤل مؤسساتي (سيطرة عقود الشراء)' if d['gld_pcr'] and d['gld_pcr']<0.8 else '→ تعادل مؤسساتي (توازن بين البيع والشراء)' if d['gld_pcr'] else ''}\n   💡 (شرح مؤشر الـ P/C: يقيس معنويات كبار المستثمرين في عقود الأوبشن؛ إذا كانت النسبة أعلى من 1.0 يعني تحوط وتوقع هبوط، وإذا كانت أقل من 1.0 يعني تفاؤل وتوقع صعود)"

text = text.replace(old_pc, new_pc)

with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Modifications done successfully")
