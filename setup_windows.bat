@echo off
setlocal
if not exist .venv (
    echo Creating Python virtual environment...
    py -3 -m venv .venv
    if errorlevel 1 (
        echo Could not create .venv. Make sure Python is installed and available as py.
        pause
        exit /b 1
    )
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
set DATABASE_URL=sqlite:///./storage/clinic.db
python -m app.database.init_db
python scripts/seed_database.py
python scripts/validate_database.py
python -m pytest -q
if errorlevel 1 (
    echo Tests failed. Read the output above.
    pause
    exit /b 1
)
echo.
echo Setup complete. Start the app with run_demo.bat
pause
