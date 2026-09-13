"""Deterministic, balanced dataset generator for Maple Crescent Family Clinic.

Run from the project root:

    python scripts/generate_datasets.py

Regenerates data/production/*.csv. The output is deterministic (fixed RNG seed),
so two runs produce byte-identical files and the evaluation suites stay
reproducible.

Design rules
------------
1. The existing 372 future schedule rows are preserved byte-for-byte. The
   evaluation suites book specific schedule ids (1, 5, 75), so those surrogate
   keys must not move. New slots are appended with fresh ids.
2. History is generated backwards from the clinic's "today". Without past slots
   a `completed` or `no_show` appointment is impossible, which is why those two
   statuses were missing from the original dataset entirely.
3. Balance is enforced, then asserted. Every doctor, every service, every
   appointment status and every schedule status must appear, and the generator
   raises rather than writing a skewed file.
4. Clinic opening hours are respected: Mon-Fri 09:00-19:00 with a 13:00-14:00
   administrative break, Saturday 10:00-16:00, Sunday closed.
"""

from __future__ import annotations

import csv
import random
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "production"

CLINIC = "CLINIC-001"
TODAY = date(2026, 9, 13)          # clinic "now" for this synthetic dataset
SLOT_MINUTES = 30

RNG = random.Random(20260913)      # fixed seed => reproducible output

# Schedule ids 1..372 already exist and are referenced by the evaluation suites.
PRESERVED_SCHEDULE_ROWS = 372

# Slots that must stay bookable after seeding (asserted at the end).
MUST_STAY_AVAILABLE = {5, 75}
# Slot that must be consumed by an active appointment, so that the
# "requested time is not available" path is exercised by QA-011.
MUST_BE_BOOKED = 1


# ---------------------------------------------------------------------------
# Reference data (canonical - names, fees and specialties are asserted by tests)
# ---------------------------------------------------------------------------

DOCTORS = [
    # id, name, specialty, qualification, years, languages, room
    ("DR-001", "Dr. Amina Rahman", "General Practice & Family Medicine",
     "MBBS, FCPS (Family Medicine)", 14, "English;Urdu;Punjabi", "R-101"),
    ("DR-002", "Dr. Bilal Hassan", "Cardiology",
     "MBBS, FCPS (Cardiology)", 18, "English;Urdu", "R-102"),
    ("DR-003", "Dr. Sara Malik", "Dermatology",
     "MBBS, MCPS (Dermatology)", 9, "English;Urdu", "R-103"),
    ("DR-004", "Dr. Hamza Qureshi", "Pediatrics",
     "MBBS, FCPS (Paediatrics)", 11, "English;Urdu;Pashto", "R-104"),
    ("DR-005", "Dr. Nadia Ahmed", "General Practice & Preventive Care",
     "MBBS, MPH", 7, "English;Urdu;Sindhi", "R-105"),
]

SERVICES = [
    # id, name, minutes, fee, category, description, follow_up_days
    ("SERVICE-001", "General Physician Consultation", 30, 2000, "consultation",
     "First assessment with a general physician.", 14),
    ("SERVICE-002", "Follow-up Consultation", 20, 1200, "follow_up",
     "Review visit for an existing treatment plan.", 30),
    ("SERVICE-003", "Family Medicine Consultation", 30, 2000, "consultation",
     "Whole-family primary care consultation.", 21),
    ("SERVICE-004", "Cardiology Consultation", 30, 3500, "specialist",
     "Specialist cardiac assessment.", 30),
    ("SERVICE-005", "Dermatology Consultation", 30, 3000, "specialist",
     "Specialist skin, hair and nail assessment.", 30),
    ("SERVICE-006", "Pediatric Consultation", 30, 2500, "specialist",
     "Consultation for infants, children and adolescents.", 21),
    ("SERVICE-007", "Preventive Health Consultation", 30, 2000, "preventive",
     "Lifestyle, risk and vaccination review.", 180),
    ("SERVICE-008", "Health Screening Consultation", 30, 2200, "preventive",
     "Routine screening and baseline checks.", 365),
    ("SERVICE-009", "Chronic Care Follow-up", 20, 1500, "follow_up",
     "Ongoing review for a long-term condition.", 60),
]

DOCTOR_SERVICES = {
    "DR-001": ["SERVICE-001", "SERVICE-002", "SERVICE-003",
               "SERVICE-007", "SERVICE-008", "SERVICE-009"],
    "DR-002": ["SERVICE-004", "SERVICE-002", "SERVICE-007", "SERVICE-009"],
    "DR-003": ["SERVICE-005", "SERVICE-002", "SERVICE-007"],
    "DR-004": ["SERVICE-006", "SERVICE-002", "SERVICE-007"],
    "DR-005": ["SERVICE-001", "SERVICE-002", "SERVICE-003",
               "SERVICE-007", "SERVICE-008", "SERVICE-009"],
}

SERVICE_MINUTES = {s[0]: s[2] for s in SERVICES}

# Patients P-001..P-012 already exist and P-001 / P-012 are referenced by the
# evaluation suites, so their identity is fixed. Later patients are generated.
SEED_PATIENTS = [
    ("P-001", "Ayesha Siddiqui", "+92 300 1000001", "ayesha.siddiqui@example.com", "female"),
    ("P-002", "Usman Tariq", "+92 300 1000002", "usman.tariq@example.com", "male"),
    ("P-003", "Hina Aslam", "+92 300 1000003", "hina.aslam@example.com", "female"),
    ("P-004", "Faisal Mehmood", "+92 300 1000004", "faisal.mehmood@example.com", "male"),
    ("P-005", "Rabia Noor", "+92 300 1000005", "rabia.noor@example.com", "female"),
    ("P-006", "Kashif Iqbal", "+92 300 1000006", "kashif.iqbal@example.com", "male"),
    ("P-007", "Sana Javed", "+92 300 1000007", "sana.javed@example.com", "female"),
    ("P-008", "Imran Shah", "+92 300 1000008", "imran.shah@example.com", "male"),
    ("P-009", "Nimra Baig", "+92 300 1000009", "nimra.baig@example.com", "female"),
    ("P-010", "Adnan Raza", "+92 300 1000010", "adnan.raza@example.com", "male"),
    ("P-011", "Mehwish Anwar", "+92 300 1000011", "mehwish.anwar@example.com", "female"),
    ("P-012", "Zeeshan Akram", "+92 300 1000012", "zeeshan.akram@example.com", "male"),
]

FEMALE_NAMES = [
    "Areeba Khan", "Maryam Farooq", "Sadia Rehman", "Komal Bashir", "Iqra Nawaz",
    "Fatima Zahra", "Laiba Hussain", "Anum Shafiq", "Saba Riaz", "Momina Ali",
    "Bushra Latif", "Kiran Yousaf", "Nida Sultan", "Warda Kamal", "Hafsa Munir",
    "Tooba Ashraf", "Rida Saleem", "Mahnoor Abbas", "Eman Waseem", "Zainab Haider",
    "Shazia Parveen", "Amna Rauf", "Sidra Qamar", "Noor Fatima",
]

MALE_NAMES = [
    "Hassan Raza", "Bilal Ahmed", "Danish Iqbal", "Owais Malik", "Taimur Khan",
    "Saad Nasir", "Fahad Zaman", "Rehan Aziz", "Salman Butt", "Arsalan Gul",
    "Haris Sheikh", "Junaid Akhtar", "Waleed Chaudhry", "Talha Saeed", "Umair Sohail",
    "Shahzaib Qadir", "Asad Mahmood", "Noman Ijaz", "Zohaib Rashid", "Ammar Hayat",
    "Bilawal Khalid", "Mudassir Ali", "Rizwan Aslam", "Kamran Dar",
]

CITIES = ["Lahore", "Lahore", "Lahore", "Kasur", "Sheikhupura", "Gujranwala", "Faisalabad"]
LANGUAGES = ["English", "Urdu", "Roman Urdu", "Urdu", "English"]
BOOKING_CHANNELS = ["walk_in", "phone", "ai_receptionist", "web", "referral"]
PAYMENT_METHODS = ["cash", "debit_card", "credit_card", "bank_transfer"]
CANCELLATION_REASONS = [
    "patient_request", "patient_unwell", "schedule_conflict",
    "doctor_unavailable", "rescheduled_by_patient",
]


# ---------------------------------------------------------------------------
# Clinic calendar
# ---------------------------------------------------------------------------

def working_slots(day: date) -> list[tuple[datetime, datetime]]:
    """Opening-hours slots for a given day. Sunday returns nothing."""
    weekday = day.weekday()          # Mon=0 .. Sun=6
    if weekday == 6:
        return []
    if weekday == 5:                 # Saturday 10:00-16:00
        windows = [(10, 0, 16, 0)]
    else:                            # Mon-Fri 09:00-19:00, break 13:00-14:00
        windows = [(9, 0, 13, 0), (14, 0, 19, 0)]

    slots = []
    for sh, sm, eh, em in windows:
        cursor = datetime(day.year, day.month, day.day, sh, sm)
        end = datetime(day.year, day.month, day.day, eh, em)
        while cursor + timedelta(minutes=SLOT_MINUTES) <= end:
            slots.append((cursor, cursor + timedelta(minutes=SLOT_MINUTES)))
            cursor += timedelta(minutes=SLOT_MINUTES)
    return slots


def read_existing_schedules() -> list[dict]:
    with (DATA / "doctor_schedules.csv").open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def build_patients() -> list[dict]:
    rows = []
    for pid, name, phone, email, gender in SEED_PATIENTS:
        rows.append({"patient_id": pid, "full_name": name, "phone": phone,
                     "email": email, "gender": gender})

    pool = [(n, "female") for n in FEMALE_NAMES] + [(n, "male") for n in MALE_NAMES]
    RNG.shuffle(pool)
    for index, (name, gender) in enumerate(pool, start=len(SEED_PATIENTS) + 1):
        handle = name.lower().replace(" ", ".")
        rows.append({
            "patient_id": f"P-{index:03d}",
            "full_name": name,
            "phone": f"+92 300 {1000000 + index:07d}",
            "email": f"{handle}@example.com",
            "gender": gender,
        })

    out = []
    for row in rows:
        gender = row["gender"]
        # Balanced adult age spread, 18-79.
        age = 18 + (len(out) * 7) % 62
        dob = date(TODAY.year - age, 1 + (len(out) * 5) % 12, 1 + (len(out) * 11) % 28)
        out.append({
            "patient_id": row["patient_id"],
            "clinic_id": CLINIC,
            "full_name": row["full_name"],
            "phone": row["phone"],
            "email": row["email"],
            "active": "true",
            "gender": gender,
            "date_of_birth": dob.isoformat(),
            "preferred_language": LANGUAGES[len(out) % len(LANGUAGES)],
            "city": CITIES[len(out) % len(CITIES)],
            "registered_on": (TODAY - timedelta(days=30 + (len(out) * 13) % 900)).isoformat(),
        })
    return out


def build_schedules(existing: list[dict]) -> list[dict]:
    """Preserve existing rows verbatim, then append history and future weeks."""
    rows = []
    taken: set[tuple[str, str]] = set()
    repaired = 0

    for row in existing[:PRESERVED_SCHEDULE_ROWS]:
        start = datetime.fromisoformat(row["slot_start"])
        status, slot_type = row["status"], "standard"
        # Pre-existing defect: the original dataset offered bookable slots during
        # the 13:00-14:00 administrative break that clinic_timings.md documents.
        # The surrogate ids are referenced by the evaluation suites, so the rows
        # are blocked rather than deleted - the id survives, the contradiction
        # does not.
        if start.weekday() < 5 and 13 <= start.hour < 14:
            status, slot_type = "blocked", "admin_break"
            repaired += 1
        rows.append({
            "schedule_id": row["schedule_id"],
            "clinic_id": row["clinic_id"],
            "doctor_id": row["doctor_id"],
            "slot_start": row["slot_start"],
            "slot_end": row["slot_end"],
            "status": status,
            "slot_type": slot_type,
        })
        taken.add((row["doctor_id"], row["slot_start"]))

    if repaired:
        print(f"  repaired {repaired} slot(s) that fell inside the admin break")

    next_id = max(int(r["schedule_id"]) for r in rows) + 1
    doctor_ids = [d[0] for d in DOCTORS]

    def add_range(start: date, end: date, per_day: int, historical: bool):
        nonlocal next_id
        day = start
        while day <= end:
            slots = working_slots(day)
            if slots:
                for offset, doctor_id in enumerate(doctor_ids):
                    # Rotate the starting offset per doctor so the clinic is not
                    # uniformly busy at the same hour every day.
                    chosen = slots[offset % max(1, len(slots) - per_day):][:per_day]
                    for slot_start, slot_end in chosen:
                        key = (doctor_id, slot_start.strftime("%Y-%m-%d %H:%M:%S"))
                        if key in taken:
                            continue
                        taken.add(key)
                        if historical:
                            status, slot_type = "available", "standard"
                        elif next_id % 29 == 0:
                            status, slot_type = "blocked", "admin_block"
                        elif next_id % 17 == 0:
                            status, slot_type = "available", "emergency_reserve"
                        else:
                            status, slot_type = "available", "standard"
                        rows.append({
                            "schedule_id": str(next_id),
                            "clinic_id": CLINIC,
                            "doctor_id": doctor_id,
                            "slot_start": slot_start.strftime("%Y-%m-%d %H:%M:%S"),
                            "slot_end": slot_end.strftime("%Y-%m-%d %H:%M:%S"),
                            "status": status,
                            "slot_type": slot_type,
                        })
                        next_id += 1
            day += timedelta(days=1)

    # Four weeks of history so completed / no_show appointments are possible.
    add_range(TODAY - timedelta(days=28), TODAY - timedelta(days=1), per_day=8, historical=True)
    # Two further weeks of forward capacity beyond the original range.
    add_range(date(2026, 9, 28), date(2026, 10, 10), per_day=10, historical=False)
    return rows


def build_appointments(schedules: list[dict], patients: list[dict]) -> list[dict]:
    """Balanced across doctors, services, statuses and patients."""
    by_doctor_past: dict[str, list[dict]] = defaultdict(list)
    by_doctor_future: dict[str, list[dict]] = defaultdict(list)

    for row in schedules:
        if row["status"] != "available":
            continue
        schedule_id = int(row["schedule_id"])
        if schedule_id in MUST_STAY_AVAILABLE:
            continue
        start = datetime.fromisoformat(row["slot_start"])
        bucket = by_doctor_past if start.date() < TODAY else by_doctor_future
        bucket[row["doctor_id"]].append(row)

    for bucket in (by_doctor_past, by_doctor_future):
        for rows in bucket.values():
            rows.sort(key=lambda r: r["slot_start"])

    past_statuses = [("completed", 10), ("no_show", 10), ("cancelled", 5)]
    future_statuses = [("scheduled", 10), ("confirmed", 10), ("cancelled", 5)]

    patient_ids = [p["patient_id"] for p in patients]
    appointments = []
    counter = 0
    patient_cursor = 0
    service_usage: Counter[str] = Counter()

    # Anchor: schedule 1 must be consumed so QA-011 exercises the
    # "requested time is not available" path.
    anchor = next(r for r in schedules if int(r["schedule_id"]) == MUST_BE_BOOKED)
    used_schedules = {MUST_BE_BOOKED}

    def pick_service(doctor_id: str) -> str:
        """Least-used eligible service.

        Plain round-robin per doctor looks balanced per doctor but skews the
        clinic totals badly: SERVICE-002 and SERVICE-007 are offered by all five
        doctors, so they accumulate five times the volume of a single-doctor
        specialty. Choosing the globally least-used eligible service spreads
        demand as evenly as the doctor-service graph allows.
        """
        options = DOCTOR_SERVICES[doctor_id]
        return min(options, key=lambda s: (service_usage[s], s))

    def emit(schedule_row, doctor_id, status):
        nonlocal counter, patient_cursor
        counter += 1
        service_id = pick_service(doctor_id)
        service_usage[service_id] += 1
        start = datetime.fromisoformat(schedule_row["slot_start"])
        end = start + timedelta(minutes=SERVICE_MINUTES[service_id])
        patient_id = patient_ids[patient_cursor % len(patient_ids)]
        patient_cursor += 1
        appointments.append({
            "appointment_id": f"A-{counter:03d}",
            "clinic_id": CLINIC,
            "doctor_id": doctor_id,
            "service_id": service_id,
            "patient_id": patient_id,
            "schedule_id": schedule_row["schedule_id"],
            "starts_at": start.strftime("%Y-%m-%d %H:%M:%S"),
            "ends_at": end.strftime("%Y-%m-%d %H:%M:%S"),
            "status": status,
            "notes": "",
            "booking_channel": BOOKING_CHANNELS[counter % len(BOOKING_CHANNELS)],
            "payment_method": (
                "" if status in {"cancelled", "no_show", "scheduled"}
                else PAYMENT_METHODS[counter % len(PAYMENT_METHODS)]
            ),
            "payment_status": (
                "paid" if status == "completed"
                else "waived" if status == "no_show"
                else "refunded" if status == "cancelled"
                else "pending"
            ),
            "cancellation_reason": (
                CANCELLATION_REASONS[counter % len(CANCELLATION_REASONS)]
                if status == "cancelled" else ""
            ),
        })

    emit(anchor, anchor["doctor_id"], "confirmed")

    for doctor_id, _n, _s, _q, _y, _l, _r in DOCTORS:
        past_pool = [r for r in by_doctor_past[doctor_id]
                     if int(r["schedule_id"]) not in used_schedules]
        future_pool = [r for r in by_doctor_future[doctor_id]
                       if int(r["schedule_id"]) not in used_schedules]

        for status, quota in past_statuses:
            for _ in range(quota):
                if not past_pool:
                    raise SystemExit(f"Not enough historical slots for {doctor_id}")
                row = past_pool.pop(0)
                used_schedules.add(int(row["schedule_id"]))
                emit(row, doctor_id, status)

        for status, quota in future_statuses:
            for _ in range(quota):
                if not future_pool:
                    raise SystemExit(f"Not enough future slots for {doctor_id}")
                row = future_pool.pop(0)
                used_schedules.add(int(row["schedule_id"]))
                emit(row, doctor_id, status)

    return appointments


# ---------------------------------------------------------------------------
# Validation - the generator refuses to write a skewed or invalid dataset
# ---------------------------------------------------------------------------

def validate(patients, schedules, appointments):
    problems = []

    schedule_by_id = {int(r["schedule_id"]): r for r in schedules}

    # Referential integrity
    patient_ids = {p["patient_id"] for p in patients}
    for appointment in appointments:
        if appointment["patient_id"] not in patient_ids:
            problems.append(f"{appointment['appointment_id']}: unknown patient")
        if appointment["service_id"] not in DOCTOR_SERVICES[appointment["doctor_id"]]:
            problems.append(
                f"{appointment['appointment_id']}: "
                f"{appointment['doctor_id']} does not provide {appointment['service_id']}"
            )
        schedule = schedule_by_id.get(int(appointment["schedule_id"]))
        if schedule is None:
            problems.append(f"{appointment['appointment_id']}: unknown schedule")
            continue
        if schedule["doctor_id"] != appointment["doctor_id"]:
            problems.append(f"{appointment['appointment_id']}: schedule/doctor mismatch")
        if schedule["slot_start"] != appointment["starts_at"]:
            problems.append(f"{appointment['appointment_id']}: start time mismatch")

    # One active appointment per schedule (mirrors uq_active_doctor_schedule)
    active = Counter(
        int(a["schedule_id"]) for a in appointments
        if a["status"] in {"scheduled", "confirmed"}
    )
    for schedule_id, count in active.items():
        if count > 1:
            problems.append(f"schedule {schedule_id}: {count} active appointments")

    # Unique (doctor, slot_start)
    slot_keys = Counter((r["doctor_id"], r["slot_start"]) for r in schedules)
    for key, count in slot_keys.items():
        if count > 1:
            problems.append(f"duplicate slot {key}")

    # Evaluation anchors
    for schedule_id in MUST_STAY_AVAILABLE:
        if schedule_id in active:
            problems.append(f"anchor schedule {schedule_id} must stay available")
        if schedule_by_id[schedule_id]["status"] != "available":
            problems.append(f"anchor schedule {schedule_id} is not available")
    if MUST_BE_BOOKED not in active:
        problems.append(f"anchor schedule {MUST_BE_BOOKED} must be booked")

    # Opening hours
    for row in schedules:
        start = datetime.fromisoformat(row["slot_start"])
        if start.weekday() == 6:
            problems.append(f"schedule {row['schedule_id']} falls on a Sunday")
        if (start.weekday() < 5 and 13 <= start.hour < 14
                and row["status"] != "blocked"):
            problems.append(f"schedule {row['schedule_id']} is bookable during the admin break")

    # Balance
    doctor_counts = Counter(a["doctor_id"] for a in appointments)
    if len(doctor_counts) != len(DOCTORS):
        problems.append("not every doctor has appointments")
    if max(doctor_counts.values()) - min(doctor_counts.values()) > 2:
        problems.append(f"doctor load is skewed: {dict(doctor_counts)}")

    service_counts = Counter(a["service_id"] for a in appointments)
    if len(service_counts) != len(SERVICES):
        missing = {s[0] for s in SERVICES} - set(service_counts)
        problems.append(f"services never used: {sorted(missing)}")

    status_counts = Counter(a["status"] for a in appointments)
    if len(status_counts) != 5:
        problems.append(f"not all appointment statuses present: {dict(status_counts)}")

    gender_counts = Counter(p["gender"] for p in patients)
    if abs(gender_counts["female"] - gender_counts["male"]) > 4:
        problems.append(f"gender is skewed: {dict(gender_counts)}")

    schedule_statuses = Counter(r["status"] for r in schedules)
    if "blocked" not in schedule_statuses:
        problems.append("no blocked schedule slots generated")

    if problems:
        for problem in problems[:25]:
            print(f"  FAIL {problem}")
        raise SystemExit(f"Validation failed with {len(problems)} problem(s).")

    return {
        "patients": len(patients),
        "schedules": len(schedules),
        "appointments": len(appointments),
        "per_doctor": dict(sorted(doctor_counts.items())),
        "per_status": dict(sorted(status_counts.items())),
        "per_service": dict(sorted(service_counts.items())),
        "schedule_status": dict(sorted(schedule_statuses.items())),
        "gender": dict(sorted(gender_counts.items())),
    }


def write_csv(name, rows, fieldnames):
    path = DATA / name
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  wrote {name:26} {len(rows):5d} rows")


def main():
    existing = read_existing_schedules()
    patients = build_patients()
    schedules = build_schedules(existing)
    appointments = build_appointments(schedules, patients)

    summary = validate(patients, schedules, appointments)

    doctors = [{
        "doctor_id": d[0], "clinic_id": CLINIC, "full_name": d[1], "specialty": d[2],
        "active": "true", "qualification": d[3], "years_experience": d[4],
        "languages": d[5], "room_number": d[6],
    } for d in DOCTORS]

    services = [{
        "service_id": s[0], "clinic_id": CLINIC, "name": s[1],
        "duration_minutes": s[2], "fee_pkr": s[3], "active": "true",
        "category": s[4], "description": s[5], "follow_up_days": s[6],
    } for s in SERVICES]

    doctor_services = [{
        "doctor_id": doctor_id, "service_id": service_id,
        "clinic_id": CLINIC, "active": "true",
    } for doctor_id, service_ids in DOCTOR_SERVICES.items() for service_id in service_ids]

    print("Writing datasets:")
    write_csv("doctors.csv", doctors, list(doctors[0]))
    write_csv("services.csv", services, list(services[0]))
    write_csv("doctor_services.csv", doctor_services, list(doctor_services[0]))
    write_csv("patients.csv", patients, list(patients[0]))
    write_csv("doctor_schedules.csv", schedules, list(schedules[0]))
    write_csv("appointments.csv", appointments, list(appointments[0]))

    print("\nBalance summary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    print("\nAll invariants passed.")


if __name__ == "__main__":
    sys.exit(main())
