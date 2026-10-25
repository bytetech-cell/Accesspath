@echo off
REM ACCESSPATH one-time setup for Windows (uses venv, no Docker)
cd /d "%~dp0backend"
echo [1/4] Creating virtual environment...
python -m venv venv || (echo Python not found. Install Python 3.10+ from python.org & pause & exit /b 1)
call venv\Scripts\activate.bat
echo [2/4] Installing Python packages...
python -m pip install --upgrade pip
pip install -r requirements.txt || (pause & exit /b 1)
echo [3/4] Downloading Chromium for Playwright...
python -m playwright install chromium || (pause & exit /b 1)
echo [4/4] Creating .env ...
if not exist .env copy .env.example .env >nul
echo.
echo Setup done! Put your TINYFISH_API_KEY in backend\.env, then double-click run_windows.bat
pause
