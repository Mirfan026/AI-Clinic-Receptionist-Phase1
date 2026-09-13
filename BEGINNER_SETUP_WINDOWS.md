# Beginner setup: VS Code + Windows

## 1. Install the prerequisites
Install:
- Python 3.11+ (Python 3.13 is also supported by the tested environment)
- VS Code
- Git for Windows

During Python installation, enable **Add Python to PATH**.

## 2. Open the project in VS Code
1. Extract the project ZIP to a normal folder, for example `E:\ai_rep\AI-Clinic-Receptionist-Phase1-Final-VSCode`.
2. Open VS Code.
3. Choose **File -> Open Folder**.
4. Select the extracted project folder.
5. In VS Code choose **Terminal -> New Terminal**.

## 3. Create the virtual environment and install everything
The easiest method is:

```powershell
.\setup_windows.bat
```

If Windows blocks the batch file, run the commands manually:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
$env:DATABASE_URL="sqlite:///./storage/clinic.db"
python -m app.database.init_db
python scripts/seed_database.py
python scripts/validate_database.py
```

## 4. Run the tests

```powershell
pytest -q
```

Expected baseline from the latest validated package: **68 passed**.

Warnings about `datetime.utcnow()` are deprecation warnings, not test failures.

## 5. Start the Streamlit demo

```powershell
.\run_demo.bat
```

Or:

```powershell
python -m streamlit run streamlit_app.py
```

Streamlit will print a local address. Open it in your browser.

## 6. Demo checklist
Try these in order:
1. `What are the clinic opening hours?`
2. `Who is the dermatologist?`
3. `What services do you offer?`
4. `Is DR-001 SERVICE-001 available on 2026-09-14 at 11:00?`
5. Start a booking with a patient ID.
6. Continue the booking by entering the returned `schedule_id`.
7. Try Urdu: `کلینک کے اوقات کیا ہیں؟`
8. Try Roman Urdu: `clinic ke timings kya hain?`
9. Try mixed language: `Clinic ke timings کیا ہیں؟`
10. Try an unsupported question such as parking or pharmacy.
11. Try a medical request; the system should refuse diagnosis/prescription advice.
12. Try a prompt injection; the system should not reveal internal instructions.

## 7. Important rule
Never edit the database directly to make the chatbot book an appointment. The intended path is:

```text
Agent -> check_availability() -> book_appointment() -> Database
```

RAG is only for static clinic information. It is **not** the source of live availability.
