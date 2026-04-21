@echo off
:: ────────────────────────────────────────────────────────────────────────────
:: build.bat  —  Nerds at War  •  Nuitka + Inno Setup builder
:: Double-click this file to build.
:: Output:
::   dist\NerdsAdWar.exe            ← for GitHub Release (updater)
::   dist\Setup_NerdsAdWar_vX.Y.exe ← installer for new players
:: ────────────────────────────────────────────────────────────────────────────
setlocal
cd /d "%~dp0"

echo [1/5] Check Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.10+ from python.org
    pause & exit /b 1
)

:: Windows Store Python does not work with Nuitka (missing C headers)
python -c "import sys; exit(1 if 'WindowsApps' in sys.executable or 'Packages' in sys.executable else 0)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: You are using Windows Store Python, which does NOT work with Nuitka.
    echo.
    echo Install Python from: https://www.python.org/downloads/
    echo Check 'Add Python to PATH' during installation.
    echo.
    pause & exit /b 1
)

echo [2/5] Install Nuitka and pygame...
python -m pip install --upgrade nuitka pygame ordered-set zstandard
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause & exit /b 1
)

echo [3/5] Bump version number...
python tools\bump_version.py
if errorlevel 1 (
    echo ERROR: bump_version failed.
    pause & exit /b 1
)

:: Read the new version number for the installer filename
for /f "delims=" %%v in ('python -c "from src.version import VERSION; print(VERSION)"') do set VER=%%v
echo     Version: %VER%

echo [4/6] Convert logo to icon...
if exist assets\logo.png (
    python -m pip install --quiet pillow
    python -c "from PIL import Image; img=Image.open('assets/logo.png').convert('RGBA'); img.save('assets/icon.ico', format='ICO', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])"
    if errorlevel 1 (
        echo WARNING: assets\logo.png could not be converted to icon.ico
    ) else (
        echo     assets\icon.ico created from assets\logo.png
    )
)

echo [5/6] Build exe with Nuitka (first time can take 5-10 min)...
if exist dist rmdir /s /q dist
if exist main.build rmdir /s /q main.build
if exist main.dist  rmdir /s /q main.dist

:: Base options
set NUITKA_OPTS=--onefile --windows-disable-console
set NUITKA_OPTS=%NUITKA_OPTS% --onefile-tempdir-spec={CACHE_DIR}/NerdsAdWar/runtime
set NUITKA_OPTS=%NUITKA_OPTS% --include-data-files=assets/audio/music_menu_custom.mpeg=assets/audio/music_menu_custom.mpeg
set NUITKA_OPTS=%NUITKA_OPTS% --output-dir=dist --output-filename=NerdsAdWar.exe
set NUITKA_OPTS=%NUITKA_OPTS% --assume-yes-for-downloads

:: Include icon if it exists
if exist assets\icon.ico set NUITKA_OPTS=%NUITKA_OPTS% --windows-icon-from-ico=assets\icon.ico

python -m nuitka %NUITKA_OPTS% main.py
if errorlevel 1 (
    echo ERROR: Nuitka build failed.
    pause & exit /b 1
)

echo [6/6] Create installer with Inno Setup (optional)...
set ISCC=
where iscc >nul 2>&1 && set ISCC=iscc
if "%ISCC%"=="" if exist "C:\Program Files (x86)\Inno Setup 6\iscc.exe" set ISCC=C:\Program Files (x86)\Inno Setup 6\iscc.exe
if "%ISCC%"=="" if exist "C:\Program Files\Inno Setup 6\iscc.exe"       set ISCC=C:\Program Files\Inno Setup 6\iscc.exe
if "%ISCC%"=="" if exist "C:\Program Files (x86)\Inno Setup 7\iscc.exe" set ISCC=C:\Program Files (x86)\Inno Setup 7\iscc.exe
if "%ISCC%"=="" if exist "C:\Program Files\Inno Setup 7\iscc.exe"       set ISCC=C:\Program Files\Inno Setup 7\iscc.exe

if not "%ISCC%"=="" (
    "%ISCC%" tools\NerdsAdWar.iss /DMyAppVersion=%VER%
    if errorlevel 1 (
        echo WARNING: Inno Setup failed, but the exe is ready.
    ) else (
        echo     Installer: dist\Setup_NerdsAdWar_%VER%.exe
    )
) else (
    echo     Inno Setup not found — skipping installer step.
    echo     Download at: https://jrsoftware.org/isdl.php
)

echo.
echo ╔══════════════════════════════════════════════════════════════════╗
echo ║  Done!  Upload both files to GitHub Releases:                   ║
echo ║                                                                 ║
echo ║    dist\NerdsAdWar.exe              (updater downloads this)   ║
echo ║    dist\Setup_NerdsAdWar_%VER%.exe  (for new players)          ║
echo ╚══════════════════════════════════════════════════════════════════╝
echo.
pause
