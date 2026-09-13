# Phase 1 Appointment Database — SQLite

## Boundary
The DB layer stores structured operational truth. It contains **no LLM, prompt, RAG, or agent logic**.

`Agent -> Tools -> Services/Repositories -> Database`

## Tables
`clinics`, `doctors`, `services`, `doctor_services`, `doctor_schedules`, `patients`, `appointments`

## Key protections
- PKs on every entity; composite PK on `doctor_services`.
- Foreign keys with SQLite `PRAGMA foreign_keys=ON`.
- Check constraints for positive durations, valid time ranges, valid statuses, and non-negative fees.
- Clinic-scoped indexes.
- `doctor_id + schedule_id` unique partial index for active appointments.
- Booking transaction checks slot state and validates clinic/doctor/service/patient relationships.
- Cancelled appointments do not consume the active unique index.

## Setup
From the project root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-db.txt
$env:DATABASE_URL="sqlite:///./storage/clinic.db"
python -m app.database.init_db
python scripts/seed_database.py
python scripts/validate_database.py
pytest -q
python scripts/sample_queries.py
```

Linux/macOS activation:
```bash
source .venv/bin/activate
export DATABASE_URL="sqlite:///./storage/clinic.db"
```

## Approved seed
Maple Crescent Family Clinic:
- 1 clinic
- 5 doctors
- 9 services
- 22 doctor-service relationships
- 372 schedule slots
- 12 synthetic patients
- 24 appointments: 21 active + 3 cancelled

## PostgreSQL migration path
SQLAlchemy models are intentionally database-portable. For SaaS:
1. Move `DATABASE_URL` to PostgreSQL.
2. Add Alembic migrations.
3. Keep `tenant_id` and clinic scoping.
4. Keep transactional booking and the active appointment uniqueness constraint.
5. Add tenant/user/auth/audit tables later.

SQLite is appropriate for the Phase 1 hackathon; PostgreSQL is the production SaaS target for concurrent workloads.

## Beginner first run (Windows + VS Code)

1. Open this folder in VS Code.
2. Open **Terminal -> New Terminal**.
3. Run `setup_windows.bat` once.
4. Run `pytest -q` to confirm the regression suite.
5. Run `run_demo.bat` to start the Streamlit application.
6. Read `BEGINNER_SETUP_WINDOWS.md` for the full walkthrough.
7. Read `GITHUB_BEGINNER_GUIDE.md` to publish the project to GitHub.

For the canonical Phase 1 package, use the latest QA-integrated files and do not merge older milestone ZIPs manually. See `PHASE1_FILE_MAP.md`.
