import re

file_path = "Goldbot/ai_generator_bot6.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update system_prompts
def update_sys(match):
    sys_str = match.group(0)
    if "الحكم النهائي" not in sys_str and "نسبة مئوية لاتجاه الذهب" not in sys_str:
        # Append before the last """
        sys_str = sys_str.rstrip('"') + '\n- أضف دائماً في نهاية التقرير: الحكم النهائي بنسبة مئوية (مثال: صاعد 60% | هابط 40%).\n"""'
    return sys_str

content = re.sub(r'system_prompt\s*=\s*(f?)"""(.*?)"""', update_sys, content, flags=re.DOTALL)

# 2. Update user_prompts
verdict_text = "\n\n⚖️ الحكم النهائي:\n[اكتب الحكم النهائي بشكل مختصر مع تحديد نسبة مئوية لاتجاه الذهب الكلي: صاعد [رقم]% | هابط [رقم]%]\n\n"

def insert_verdict(match):
    up = match.group(0)
    if "⚖️ الحكم النهائي:" in up:
        return up
    if "البيانات الحقيقية:" in up:
        return up.replace("البيانات الحقيقية:", verdict_text.strip() + "\n\nالبيانات الحقيقية:")
    else:
        return up.rstrip('"') + verdict_text + '"""'

content = re.sub(r'user_prompt\s*=\s*(f?)"""(.*?)"""', insert_verdict, content, flags=re.DOTALL)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Prompts updated successfully.")
