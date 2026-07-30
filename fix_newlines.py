import re

def fix_newlines(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Let's fix the broken join lines:
    content = content.replace('fib_lines = "\n".join(', 'fib_lines = "\\n".join(')
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

fix_newlines('c:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py')
