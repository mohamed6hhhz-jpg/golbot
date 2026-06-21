import re

def process_file(filename, mode_label):
    with open(filename, 'r', encoding='utf-8') as f:
        code = f.read()

    # 1. Update prices in _build_fixed_template
    if mode_label == "Spot":
        price_block = f"""📍 السعر الحالي
   سوق الفوري (Spot) : {{spot_label}}"""
    else:
        price_block = f"""📍 السعر الحالي
   سوق الآجل (Futures) : {{futures_label}}{{contango_str}}"""
        
    code = re.sub(
        r"📍 أسعار الذهب.*?آجل   \(GC=F\)    : \{futures_label\}\{contango_str\}",
        price_block,
        code,
        flags=re.DOTALL
    )

    # 2. Add explicit chunks to flat_chunks inside send_reports instead of rewriting build_fixed_template
    # Actually, the simplest way is to intercept the report_text in send_reports, split it manually, and add it.
    
    reports_append_old = '''    if report_text:
        raw_reports.append(("👑 التقرير الكمي الشامل للذهب", report_text, None))'''
        
    reports_append_new = '''    if report_text:
        # Split report_text manually into exactly 4 chunks to guarantee exactly 12 reports total!
        import re
        sections = re.split(r"━━━━━━━━━━━━━━━━━━━━━━━━━━\\n[🔴🟢📉]", report_text)
        
        if len(sections) >= 1:
            raw_reports.append(("👑 تقرير السعر وحالة السوق", sections[0].strip(), None))
        
        # We need a robust way to extract the 4 parts without breaking.
        # Let's just do text matching since the template is fixed.
        
        # A simpler way: just append report_text as ONE, and let flat_chunks just be what it is?
        # No, the user wants EXACTLY 12 chunks.
        # Total AI templates = 7 (t0, t1, t2, t3, t4, t5, t6)
        # So we need exactly 5 fixed template pieces!
        pass
'''
    
    # Wait! If I just run the script via regex, it might be brittle.
    # Instead, I will write the python script to just add the asyncio.sleep and replace the "Spot vs Futures" header.
    pass

def simple_patch(filename, mode_label):
    with open(filename, 'r', encoding='utf-8') as f:
        code = f.read()

    # Fix the prices
    if mode_label == "Spot":
        code = re.sub(r"📍 أسعار الذهب.*?آجل   \(GC=F\)    : \{futures_label\}\{contango_str\}", 
                      "📍 السعر الحالي\\n   سوق الفوري (Spot) : {spot_label}", code, flags=re.DOTALL)
    else:
        code = re.sub(r"📍 أسعار الذهب.*?آجل   \(GC=F\)    : \{futures_label\}\{contango_str\}", 
                      "📍 السعر الحالي\\n   سوق الآجل (Futures) : {futures_label}{contango_str}", code, flags=re.DOTALL)

    # Add sleep for ordering
    code = code.replace(
        "await client.send_message(VIP_CHAT, chunk, parse_mode='html', link_preview=False)",
        "await client.send_message(VIP_CHAT, chunk, parse_mode='html', link_preview=False)\\n                    import asyncio\\n                    await asyncio.sleep(1.5)"
    )

    # To guarantee exactly 12 messages:
    # 1. We have t0, t1, t2, t3, t4, t5, t6 (7 chunks)
    # 2. We need fixed_rep to be split into 5 chunks. 
    # The Telegram limit split function (_split_message) automatically splits if we lower the max_len? No.
    # Let's just disable _split_message entirely for the AI templates, and split the fixed template explicitly by "━━━━━━━━━━━━━━━━━━━━━━━━━━".
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(code)

simple_patch('bot_futures.py', 'Futures')
simple_patch('bot_spot.py', 'Spot')
print("Patch done")
