@echo off
cd /d "%~dp0backend"
if not exist venv\Scripts\activate.bat (echo Run setup_windows.bat first & pause & exit /b 1)
call venv\Scripts\activate.bat
start "" http://127.0.0.1:8000
python run.py
pause
