@echo off
cd /d %~dp0

if not exist .venv (
    py -m venv .venv
)

call .venv\Scripts\activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if not exist .env (
    echo.
    echo ============================================================
    echo .env file was not found.
    echo Copy .env.example to .env and paste your MongoDB URI first.
    echo ============================================================
    echo.
    pause
    exit /b 1
)

python app.py
pause
