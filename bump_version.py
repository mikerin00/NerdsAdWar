import re, sys

f = 'src/version.py'
try:
    txt = open(f).read()
except FileNotFoundError:
    print(f'FOUT: {f} niet gevonden.')
    sys.exit(1)

m = re.search(r'v(\d+)\.(\d+)', txt)
if not m:
    print(f'FOUT: geen versienummer gevonden in {f}.')
    sys.exit(1)

major, build = int(m.group(1)), int(m.group(2)) + 1
new_txt = txt[:m.start()] + f'v{major}.{build}' + txt[m.end():]
open(f, 'w').write(new_txt)
print(f'Versie bijgewerkt naar v{major}.{build}')
