# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec voor Nerds ad War 2  —  single-file modus
# Gebruik:  pyinstaller NerdsAdWar2.spec
# Resultaat: dist\NerdsAdWar2.exe  (één bestand, stuur dit door)
#
# Noot: bij de eerste start pakt de exe zichzelf uit naar %TEMP% (~3-5 sec).
# Daarna verschijnt het laadscherm terwijl de game-modules worden geladen.

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    # maps/ wordt meegebundeld. audio/ wordt NIET gebundeld — die bestanden
    # worden bij de eerste start gegenereerd naast de exe (schrijfbaar).
    datas=[
        ('maps', 'maps'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Single-file: alle binaries en data direct in EXE, geen COLLECT
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='NerdsAdWar2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # geen zwart CMD-venster
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
