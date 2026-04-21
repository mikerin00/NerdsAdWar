import re, sys

# ── Bump version.py ──────────────────────────────────────────────────────────
ver_file = 'src/version.py'
try:
    ver_txt = open(ver_file).read()
except FileNotFoundError:
    print(f'ERROR: {ver_file} not found.')
    sys.exit(1)

m = re.search(r'v(\d+)\.(\d+)', ver_txt)
if not m:
    print(f'ERROR: no version number found in {ver_file}.')
    sys.exit(1)

major   = int(m.group(1))
old_num = int(m.group(2))
new_num = old_num + 1
old_ver = f'v{major}.{old_num}'
new_ver = f'v{major}.{new_num}'

new_ver_txt = ver_txt[:m.start()] + new_ver + ver_txt[m.end():]
open(ver_file, 'w').write(new_ver_txt)
print(f'Version updated: {old_ver} -> {new_ver}')

# ── Update whats_new.py changelog key ───────────────────────────────────────
wn_file = 'src/game/menu/whats_new.py'
try:
    wn_txt = open(wn_file, encoding='utf-8').read()
except FileNotFoundError:
    print(f'WARNING: {wn_file} not found — skipping changelog key update.')
    sys.exit(0)

old_key = f'"{old_ver}"'
new_key = f'"{new_ver}"'

if new_key in wn_txt:
    print(f'Changelog key {new_key} already exists — no change needed.')
    sys.exit(0)

if old_key not in wn_txt:
    print(f'WARNING: changelog key {old_key} not found in {wn_file}.')
    print(f'Add a "{new_ver}" entry manually to CHANGELOG in {wn_file}.')
    sys.exit(0)

# Replace the old key with the new key
wn_txt = wn_txt.replace(old_key, new_key, 1)
open(wn_file, 'w', encoding='utf-8').write(wn_txt)
print(f'Changelog key updated: {old_key} -> {new_key}')
