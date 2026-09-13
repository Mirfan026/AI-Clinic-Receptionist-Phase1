# Datasets

Synthetic operational data for Maple Crescent Family Clinic (CLINIC-001).

Regenerate with:

```bash
python scripts/generate_datasets.py   # writes data/production/*.csv
rm storage/clinic.db                  # the seeder skips an existing clinic
python scripts/seed_database.py
python scripts/validate_database.py
```

The generator uses a fixed RNG seed, so two runs produce byte-identical files
and the evaluation suites stay reproducible.

## Layering

| Path | Role |
|---|---|
| `data/source_dataset/` | Raw provenance. Never edited. |
| `data/production/` | Curated, balanced, generated. Seeded into SQLite. |
| `storage/clinic.db` | Build artifact. Not committed. |

## Volume

| Table | Before | Now |
|---|---:|---:|
| clinics | 1 | 1 |
| doctors | 5 | 5 |
| services | 9 | 9 |
| doctor_services | 22 | 22 |
| patients | 12 | **60** |
| doctor_schedules | 372 | **1,932** |
| appointments | 24 | **251** |

Date coverage moved from 2026-09-14 → 09-26 (future only) to
**2026-08-17 → 2026-10-10**, i.e. four weeks of history plus six weeks forward.

## Balance

Enforced by the generator and asserted before any file is written.

| Dimension | Result |
|---|---|
| Appointments per doctor | 50–51 across all five |
| Appointment status | 50–51 each across all five statuses |
| Per doctor × status | exactly 10 of each |
| Patient gender | 30 female / 30 male |
| Preferred language | English 24, Urdu 24, Roman Urdu 12 |
| Services used | all 9, range 19–37 |
| Schedule status | available / blocked / booked all present |

Service counts cannot be made fully uniform. SERVICE-004, -005 and -006 are
each offered by exactly one doctor, while SERVICE-002 and -007 are offered by
all five, so the doctor–service graph caps how evenly demand can spread. The
generator picks the globally least-used eligible service, which narrowed the
spread from 15–76 to 19–37.

## Why history was added

The original dataset contained only future slots. That makes `completed` and
`no_show` logically impossible, which is why both statuses were absent and why
no revenue, attendance or utilisation question could be answered from the data
at all. Four weeks of history fixed that:

```
Realised revenue (completed appointments): PKR 127,600
Slot utilisation: 1,779 available / 100 booked / 53 blocked
```

## Feature columns

Columns added in this revision are marked **new**. All are nullable, and none
are exposed by `get_doctors()` or `get_services()` — the tool contracts are
unchanged.

**doctors** — `doctor_id`, `clinic_id`, `full_name`, `specialty`, `active`,
**`qualification`**, **`years_experience`**, **`languages`**, **`room_number`**

**services** — `service_id`, `clinic_id`, `name`, `duration_minutes`,
`fee_pkr`, `active`, **`category`**, **`description`**, **`follow_up_days`**

**patients** — `patient_id`, `clinic_id`, `full_name`, `phone`, `email`,
`active`, **`gender`**, **`date_of_birth`**, **`preferred_language`**,
**`city`**, **`registered_on`**

**doctor_schedules** — `schedule_id`, `clinic_id`, `doctor_id`, `slot_start`,
`slot_end`, `status`, **`slot_type`**

**appointments** — `appointment_id`, `clinic_id`, `doctor_id`, `service_id`,
`patient_id`, `schedule_id`, `starts_at`, `ends_at`, `status`, `notes`,
**`booking_channel`**, **`payment_method`**, **`payment_status`**,
**`cancellation_reason`**

`slot_type` values: `standard`, `admin_break`, `admin_block`,
`emergency_reserve`.

### Which features the app actually uses

Be clear about this when presenting. The agent currently reads **none** of the
new columns — they are groundwork, not live behaviour. They exist so that the
admin dashboard and any Phase 2 analytics have something real to work with.

The two with the clearest Phase 2 path are `preferred_language` (could set the
reply language for a known patient instead of detecting it per message) and
`payment_status` (front-desk outstanding-balance view). Adding a column is
cheap; wiring it into the agent is a behaviour change that needs its own
evaluation cases.

## Invariants the generator asserts

It raises rather than writing a bad file:

- Schedule ids 1, 5 and 75 keep the state the evaluation suites depend on
  (1 booked, 5 and 75 available)
- Every appointment's doctor actually provides the booked service
- Every appointment sits on its own doctor's slot, with matching start time
- At most one active appointment per slot, mirroring `uq_active_doctor_schedule`
- `(doctor_id, slot_start)` unique, mirroring `uq_doctor_schedule_slot`
- No bookable slot on a Sunday or inside the 13:00–14:00 admin break
- Every doctor, every service and every status appears
- Doctor load spread ≤ 2, gender spread ≤ 4

## A defect this work uncovered

The original `doctor_schedules.csv` offered **32 bookable slots inside the
13:00–14:00 administrative break** that `clinic_timings.md` documents. The
database contradicted the knowledge base: the receptionist would have offered
appointments during a period it correctly told users the clinic was closed.

Those rows are now `status='blocked'`, `slot_type='admin_break'`. They are
blocked rather than deleted because their surrogate ids are referenced by the
evaluation suites — the id survives, the contradiction does not.
`scripts/validate_database.py` now fails if any bookable slot falls outside
clinic hours, so this cannot silently return.
