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

rem Check virtual env
if not exist "venv\Scripts\activate" (
    echo ERROR: virtual environment not found.
    echo Create it with:  py -m venv venv
    echo Then install deps:  venv\Scripts\activate ^& pip install -r requirements.txt
    pause
    exit /b 1
)

echo Activating virtual env...
call venv\Scripts\activate

if errorlevel 1 (
    echo ERROR: cannot activate virtual env.
    pause
    exit /b 1
)

echo Virtual env active.
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
