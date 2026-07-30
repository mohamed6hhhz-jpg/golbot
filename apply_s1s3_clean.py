import re

def apply_patch():
    with open('c:/Users/lenovo/Desktop/alltoools/new_templates.txt', 'r', encoding='utf-8') as f:
        new_text = f.read()
    
    with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # The regex targets def _build_spot_s1 up to def _build_spot_s4 (exclusive).
    regex = r"def _build_spot_s1\(d: dict\) -> str:.*?def _build_spot_s4\(d: dict\) -> str:"
    
    # We must append def _build_spot_s4 back because it was captured in the regex match!
    replacement = new_text + "\n\ndef _build_spot_s4(d: dict) -> str:"
    
    new_content = re.sub(regex, replacement, content, flags=re.DOTALL)
    
    with open('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
        f.write(new_content)

if __name__ == '__main__':
    apply_patch()
