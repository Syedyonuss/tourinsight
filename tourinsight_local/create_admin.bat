@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run run_windows.bat once to create the virtual environment and install packages.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
python scripts\create_admin.py
pause
