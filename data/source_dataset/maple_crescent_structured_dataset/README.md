# Maple Crescent Family Clinic — Synthetic Structured Dataset

Fictional development/evaluation data only. No real patient data.

Coverage: 2026-09-14 through 2026-09-27 (14 calendar days).
The schedule file contains explicit 30-minute appointment slots. `doctor_schedules.status` is the operational availability source.

Files:
- clinics.csv
- doctors.csv
- services.csv
- doctor_services.csv
- doctor_schedules.csv
- patients.csv
- appointments.csv
- clinic_reference_data.json
- relational_schema.json
- dataset_summary.json

Core integrity rules:
1. Primary IDs are unique and non-null.
2. All rows are scoped to TENANT-001 / CLINIC-001.
3. Doctor-service relationships must reference the same clinic.
4. Every schedule slot must reference a valid doctor-service relationship.
5. Slots must fall within the doctor's configured working blocks.
6. Slots for the same doctor/date cannot overlap.
7. Every appointment must reference one existing slot and matching doctor/service/date/time.
8. Confirmed appointments consume a booked slot.
9. Cancelled appointments release their slot.
10. No active/confirmed appointment may double-book a doctor/slot.
11. Appointment dates are valid ISO dates within the generated schedule period.
12. Patient records are synthetic only.

Production architecture note:
RAG contains static clinic knowledge. Current availability and booking status belong to structured operational data and should be accessed through backend tools.
