@echo off
if not exist .venv\Scripts\python.exe (
    echo Virtual environment not found.
    echo Please run setup_windows.bat first.
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat
python -m streamlit run streamlit_app.py
