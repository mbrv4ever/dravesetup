@echo off
REM ==========================================================
REM DraveSetup_Maker - Nuitka --onefile (1 exe)
REM
REM Bakt logo.png in via base64-injectie zodat de exe geen
REM externe bestanden meer nodig heeft.
REM ==========================================================
setlocal
cd /d "%~dp0"

if not exist "dravesetup_maker.py" (
    echo FOUT: dravesetup_maker.py niet gevonden.
    pause
    exit /b 1
)

REM === Stap 1: bouw een tijdelijke werkmap met logo-injectie ===
if exist "_build_temp" rmdir /s /q "_build_temp"
mkdir "_build_temp"

REM Kopieer de core/ map (Nuitka heeft die nodig voor imports)
xcopy /e /i /q "core" "_build_temp\core" >nul

REM Injecteer logo.png in een gewijzigde kopie van dravesetup_maker.py
python "_inject_logo.py" "dravesetup_maker.py" "_build_temp\dravesetup_maker.py"

if errorlevel 1 (
    echo.
    echo FOUT: Logo-injectie mislukt.
    pause
    exit /b 1
)

REM === Stap 2: Nuitka build op de gewijzigde kopie ===
if not exist "build_output" mkdir build_output

set ICON_ARG=
if exist "logo.ico" set ICON_ARG=--windows-icon-from-ico=logo.ico

python -m nuitka ^
    --standalone ^
    --onefile ^
    --enable-plugin=pyside6 ^
    --windows-console-mode=disable ^
    --include-package=core ^
    %ICON_ARG% ^
    --product-name="DraveSetup Maker" ^
    --product-version=0.1.0 ^
    --file-version=0.1.0 ^
    --file-description="DraveSetup Maker" ^
    --company-name="Dravenlock Software" ^
    --output-dir=build_output ^
    --output-filename=DraveSetup_Maker.exe ^
    --assume-yes-for-downloads ^
    --remove-output ^
    "_build_temp\dravesetup_maker.py"

if errorlevel 1 (
    echo.
    echo FOUT: Nuitka build mislukt.
    pause
    exit /b 1
)

REM === Stap 3: opruimen ===
if exist "_build_temp" rmdir /s /q "_build_temp"

echo.
echo === Build klaar ===
echo Output: build_output\DraveSetup_Maker.exe
echo.
pause
endlocal
