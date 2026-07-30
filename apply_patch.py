import sys

file_path = r"c:\Users\lenovo\Desktop\alltoools\Goldbot\bot_spot.py"

with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()

# 1. Remove friday target from fixed template
old_fixed = """    fixed += "\\n\\n" + _build_friday_target(d, False)
    return fixed, ai_instructions"""
new_fixed = """    return fixed, ai_instructions"""
text = text.replace(old_fixed, new_fixed)

# 2. Update generate_report to make two AI calls and reorder
old_gen = """    for model_name in GROQ_MODELS:
        try:
            log.info(f"🤖 جاري الاتصال بـ Groq — {model_name}")
            resp = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": MASTER_SYSTEM_PROMPT + "أنت محلل ذهب كمي. اكتب فقط ما طُلب منك بالعربية الفصحى. لا تكتب أي شيء خارج الأقسام المطلوبة."},
                    {"role": "user",   "content": ai_instructions},
                ],
                model=model_name,
                temperature=0.07,
                max_tokens=700,
            )
            ai_analysis = resp.choices[0].message.content
            log.info(f"✅ نجح الاتصال: {model_name}")
            return fixed_block + "\\n\\n" + ai_analysis
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate_limit" in err_str.lower():
                log.warning(f"⚠️ [{model_name}] 429 — الانتقال للتالي...")
                time.sleep(10)
                continue
            log.error(f"❌ [{model_name}] {e}")
            break

    log.error("❌ جميع الموديلات فشلت — إرسال الجزء الثابت فقط.")
    return fixed_block"""

new_gen = """    friday_tgt = _build_friday_target(d, False)
    
    ai_instructions_general = ai_instructions.replace(
        "🤖 التحليل الكمي", "🤖 التحليل الكمي (النظرة العامة الشاملة)"
    ).replace(
        "فوري (Spot)", "للسوق المفتوح"
    ).replace(
        "اكتب هذه الأقسام فقط بالترتيب:",
        "اكتب هذه الأقسام بناءً على النظرة الكلية للذهب بشكل عام لكامل التقرير:"
    )

    for model_name in GROQ_MODELS:
        try:
            log.info(f"🤖 جاري الاتصال بـ Groq — {model_name} (General & Custom)")
            resp_gen = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": MASTER_SYSTEM_PROMPT + "أنت محلل ذهب كمي. اكتب فقط ما طُلب منك بالعربية الفصحى."},
                    {"role": "user",   "content": ai_instructions_general},
                ],
                model=model_name,
                temperature=0.1,
                max_tokens=700,
            )
            ai_analysis_general = resp_gen.choices[0].message.content
            
            resp_cust = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": MASTER_SYSTEM_PROMPT + "أنت محلل ذهب كمي مخصص. اكتب فقط ما طُلب منك بالعربية الفصحى."},
                    {"role": "user",   "content": ai_instructions},
                ],
                model=model_name,
                temperature=0.07,
                max_tokens=700,
            )
            ai_analysis_custom = resp_cust.choices[0].message.content
            
            log.info(f"✅ نجح الاتصال المزدوج: {model_name}")
            return fixed_block + "\\n\\n" + ai_analysis_general + "\\n\\n━━━━━━━━━━━━━━━━━━━━━━━━━━\\n\\n" + friday_tgt + "\\n\\n" + ai_analysis_custom
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate_limit" in err_str.lower():
                log.warning(f"⚠️ [{model_name}] 429 — الانتقال للتالي...")
                import time
                time.sleep(10)
                continue
            log.error(f"❌ [{model_name}] {e}")
            break

    log.error("❌ جميع الموديلات فشلت — إرسال الجزء الثابت فقط.")
    return fixed_block + "\\n\\n" + friday_tgt"""

text = text.replace(old_gen, new_gen)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(text)

print("Done apply_patch.py")
