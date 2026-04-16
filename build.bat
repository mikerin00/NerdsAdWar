@echo off
:: ────────────────────────────────────────────────────────────────────────────
:: build.bat  —  Nerds ad War 2  •  Nuitka + Inno Setup builder
:: Dubbelklik dit bestand om te bouwen.
:: Resultaat:
::   dist\NerdsAdWar2.exe            ← voor GitHub Release (updater)
::   dist\Setup_NerdsAdWar2_vX.Y.exe ← installer voor nieuwe spelers
:: ────────────────────────────────────────────────────────────────────────────
setlocal
cd /d "%~dp0"

echo [1/5] Controleer Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo FOUT: Python niet gevonden. Installeer Python 3.10+ via python.org
    pause & exit /b 1
)

echo [2/5] Installeer Nuitka en pygame...
python -m pip install --upgrade nuitka pygame ordered-set zstandard
if errorlevel 1 (
    echo FOUT: pip install mislukt.
    pause & exit /b 1
)

echo [3/5] Verhoog versienummer...
python bump_version.py
if errorlevel 1 (
    echo FOUT: bump_version mislukt.
    pause & exit /b 1
)

:: Lees het nieuwe versienummer uit voor de installer-bestandsnaam
for /f "delims=" %%v in ('python -c "from src.version import VERSION; print(VERSION)"') do set VER=%%v
echo     Versie: %VER%

echo [4/5] Bouw exe met Nuitka (kan 5-10 min duren bij eerste keer)...
if exist dist rmdir /s /q dist

:: Basisopties
set NUITKA_OPTS=--onefile --windows-disable-console --enable-plugin=pygame
set NUITKA_OPTS=%NUITKA_OPTS% --output-dir=dist --output-filename=NerdsAdWar2.exe
set NUITKA_OPTS=%NUITKA_OPTS% --assume-yes-for-downloads

:: Icoon meegeven als het bestand bestaat
if exist icon.ico set NUITKA_OPTS=%NUITKA_OPTS% --windows-icon-from-ico=icon.ico

python -m nuitka %NUITKA_OPTS% main.py
if errorlevel 1 (
    echo FOUT: Nuitka bouw mislukt.
    pause & exit /b 1
)

echo [5/5] Maak installer met Inno Setup (optioneel)...
where iscc >nul 2>&1
if not errorlevel 1 (
    iscc NerdsAdWar2.iss /DMyAppVersion=%VER%
    if errorlevel 1 (
        echo WAARSCHUWING: Inno Setup faalde, maar de exe staat klaar.
    ) else (
        echo     Installer: dist\Setup_NerdsAdWar2_%VER%.exe
    )
) else (
    echo     Inno Setup niet gevonden — sla installer-stap over.
    echo     Download op: https://jrsoftware.org/isdl.php
)

echo.
echo ╔══════════════════════════════════════════════════════════════════╗
echo ║  Klaar!  Upload beide bestanden naar GitHub Releases:           ║
echo ║                                                                 ║
echo ║    dist\NerdsAdWar2.exe              (updater downloadt dit)    ║
echo ║    dist\Setup_NerdsAdWar2_%VER%.exe  (voor nieuwe spelers)      ║
echo ╚══════════════════════════════════════════════════════════════════╝
echo.
pause
