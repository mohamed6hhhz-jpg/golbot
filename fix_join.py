with open('Goldbot/bot_spot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if line.startswith('    fib_lines = "') and lines[i+1].startswith('".join('):
        lines[i] = '    fib_lines = "\\n".join(\n'
        lines[i+1] = ''

with open('Goldbot/bot_spot.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
