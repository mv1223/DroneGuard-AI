@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.11+ and enable Add to PATH.
  pause
  exit /b 1
)
if not exist venv (
  python -m venv venv
  if errorlevel 1 exit /b 1
)
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed.
  pause
  exit /b 1
)
if not exist .env copy .env.example .env
echo Setup completed.
pause
