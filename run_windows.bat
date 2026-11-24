@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title TourInsight - Local Tourism Intelligence Platform

echo.
echo  ================================================================
echo       TOURINSIGHT - KARNATAKA TOURISM INTELLIGENCE
echo       Local website + FastAPI backend + SQLite database
echo  ================================================================
echo.

set "PYTHON=python"
where py >nul 2>nul
if %errorlevel%==0 set "PYTHON=py"
where %PYTHON% >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install Python 3.10 or newer from https://www.python.org/downloads/
    echo During installation, enable "Add Python to PATH".
    pause
    exit /b 1
)

%PYTHON% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
    echo TourInsight requires Python 3.10 or newer.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Creating the project virtual environment...
    %PYTHON% -m venv .venv
    if errorlevel 1 goto failed
)
call ".venv\Scripts\activate.bat"

if not exist ".env" (
    echo [2/4] Creating local configuration and secure session secret...
    python -c "import secrets; print('SESSION_SECRET='+secrets.token_urlsafe(48))" > .env
    echo HOST=127.0.0.1>>.env
    echo COOKIE_SECURE=false>>.env
)

for /f %%P in ('python scripts\select_port.py') do set "PORT=%%P"
if not defined PORT (
    echo No free local port was found in the range 8501-8510.
    echo Close another TourInsight server and try again.
    pause
    exit /b 1
)

echo [3/4] Installing / checking required packages. First run needs internet access...
python -m pip install --upgrade pip
if errorlevel 1 goto failed
python -m pip install -r requirements.txt
if errorlevel 1 goto failed

echo.
echo [4/4] Starting TourInsight...
echo.
echo  Website:  http://127.0.0.1:%PORT%
echo  API docs: http://127.0.0.1:%PORT%/docs
echo.
echo  The browser opens after the API and database are ready.
echo  Keep this terminal window open while using the website.
echo  Press CTRL+C to stop the server.
echo.
start "TourInsight browser" /B python scripts\open_browser_when_ready.py http://127.0.0.1:%PORT%
python -m uvicorn backend.main:APP --host 127.0.0.1 --port %PORT%
if errorlevel 1 goto failed
exit /b 0

:failed
echo.
echo TourInsight could not start. Read the error above.
echo Common causes: Python version, package installation or antivirus blocking localhost.
echo Check that you extracted the full ZIP folder before running this file.
pause
exit /b 1
