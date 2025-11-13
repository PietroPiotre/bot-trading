@echo off
setlocal ENABLEDELAYEDEXPANSION

rem Go to script folder
cd /d "%~dp0"

title TheMiidsOne - Crypto Trading Bot
color 0A

echo ==========================================
echo         TheMiidsOne Crypto Bot
echo ==========================================
echo.

rem Detect Python launcher
set "PYTHON_CMD="
for %%P in (py python python3) do (
    if not defined PYTHON_CMD (
        %%P --version >nul 2>&1 && set "PYTHON_CMD=%%P"
    )
)

if not defined PYTHON_CMD (
    echo ERROR: Python introuvable. Installez Python 3 et reessayez.
    pause
    exit /b 1
)

rem Create virtual env if missing
if not exist "venv\Scripts\python.exe" (
    echo Creation de l'environnement virtuel...
    %PYTHON_CMD% -m venv venv
    if errorlevel 1 (
        echo ERROR: impossible de creer l'environnement virtuel.
        pause
        exit /b 1
    )
    set "NEED_REQUIREMENTS=1"
)

echo Activation de l'environnement virtuel...
call venv\Scripts\activate

if errorlevel 1 (
    echo ERROR: activation impossible.
    pause
    exit /b 1
)

rem Install requirements on first creation or when requested via flag file
if exist "venv\.needs_deps" set "NEED_REQUIREMENTS=1"

if defined NEED_REQUIREMENTS (
    echo Installation des dependances...
    python -m pip install --upgrade pip
    if exist requirements.txt (
        python -m pip install -r requirements.txt
    )
    if errorlevel 1 (
        echo ERROR: l'installation des dependances a echoue.
        pause
        exit /b 1
    )
    if exist "venv\.needs_deps" del /f /q "venv\.needs_deps" >nul 2>&1
)

echo Environnement pret.
echo.

echo Mode:
echo   1^) Normal
echo   2^) Debug
set /p MODE="Choice [1]: "
if "%MODE%"=="" set MODE=1

if "%MODE%"=="2" (
    set BOT_DEBUG=1
    echo Debug mode ON.
) else (
    set BOT_DEBUG=0
    echo Normal mode.
)

echo.
echo Starting main menu...
echo.

python main.py

echo.
echo Session finished. Press any key to exit.
pause >nul

endlocal
