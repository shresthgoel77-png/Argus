import os
with open('fix.txt', 'w', encoding='utf-8') as f_out:
    try:
        f_out.write(open('fix_mypy.txt', encoding='utf-16').read())
    except:
        f_out.write('Mypy decode error\n')
    f_out.write('\n---FLAKE8---\n')
    try:
        f_out.write(open('fix_flake8.txt', encoding='utf-16').read())
    except:
        f_out.write('Flake8 decode error\n')
