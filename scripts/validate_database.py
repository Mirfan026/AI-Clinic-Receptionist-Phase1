"""Structural validation of the seeded clinic database.

Checks invariants rather than hard-coded row counts, so the dataset can be
regenerated or grown without the validator needing an edit every time. Counts
that genuinely must not drift (one clinic, five doctors, nine services) are
still asserted exactly.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select
from app.database.connection import get_engine, get_session_factory
from app.database.models import (
    Appointment, Clinic, Doctor, DoctorSchedule, DoctorService, Patient, Service,
)

ACTIVE_STATUSES = ["scheduled", "confirmed"]
APPOINTMENT_STATUSES = {"scheduled", "confirmed", "completed", "cancelled", "no_show"}
SCHEDULE_STATUSES = {"available", "booked", "blocked"}


def validate():
    session_factory = get_session_factory(get_engine())
    errors = []

    with session_factory() as s:
        counts = {
            "clinics": s.scalar(select(func.count()).select_from(Clinic)),
            "doctors": s.scalar(select(func.count()).select_from(Doctor)),
            "services": s.scalar(select(func.count()).select_from(Service)),
            "doctor_services": s.scalar(select(func.count()).select_from(DoctorService)),
            "schedules": s.scalar(select(func.count()).select_from(DoctorSchedule)),
            "patients": s.scalar(select(func.count()).select_from(Patient)),
            "appointments": s.scalar(select(func.count()).select_from(Appointment)),
        }

        # Fixed reference data.
        for name, expected in (("clinics", 1), ("doctors", 5), ("services", 9)):
            if counts[name] != expected:
                errors.append(f"{name}: expected {expected}, got {counts[name]}")

        # Everything else only needs to be non-trivial.
        for name, minimum in (("doctor_services", 20), ("schedules", 300),
                              ("patients", 12), ("appointments", 20)):
            if counts[name] < minimum:
                errors.append(f"{name}: expected at least {minimum}, got {counts[name]}")

        # No two active appointments may hold the same slot.
        duplicates = s.execute(
            select(Appointment.doctor_id, Appointment.schedule_id, func.count())
            .where(Appointment.status.in_(ACTIVE_STATUSES))
            .group_by(Appointment.doctor_id, Appointment.schedule_id)
            .having(func.count() > 1)
        ).all()
        if duplicates:
            errors.append(f"Active double bookings: {duplicates}")

        # Every appointment must sit on its own schedule slot, same doctor.
        mismatched = s.execute(
            select(func.count())
            .select_from(Appointment)
            .join(DoctorSchedule, DoctorSchedule.schedule_id == Appointment.schedule_id)
            .where(DoctorSchedule.doctor_id != Appointment.doctor_id)
        ).scalar()
        if mismatched:
            errors.append(f"{mismatched} appointment(s) reference another doctor's slot")

        # Every appointment's doctor must actually provide the booked service.
        unlinked = s.execute(
            select(func.count()).select_from(Appointment)
            .outerjoin(DoctorService, (DoctorService.doctor_id == Appointment.doctor_id)
                       & (DoctorService.service_id == Appointment.service_id))
            .where(DoctorService.doctor_id.is_(None))
        ).scalar()
        if unlinked:
            errors.append(f"{unlinked} appointment(s) use a service the doctor does not provide")

        # Status vocabularies.
        for model, column, allowed, label in (
            (Appointment, Appointment.status, APPOINTMENT_STATUSES, "appointment"),
            (DoctorSchedule, DoctorSchedule.status, SCHEDULE_STATUSES, "schedule"),
        ):
            seen = {row[0] for row in s.execute(select(column).distinct())}
            invalid = seen - allowed
            if invalid:
                errors.append(f"invalid {label} status values: {sorted(invalid)}")
            missing = allowed - seen
            if missing:
                errors.append(f"{label} statuses never exercised by the dataset: {sorted(missing)}")

        # Coverage: the dataset should exercise every doctor and every service.
        idle_doctors = s.execute(
            select(Doctor.doctor_id).outerjoin(
                Appointment, Appointment.doctor_id == Doctor.doctor_id
            ).where(Appointment.appointment_id.is_(None))
        ).all()
        if idle_doctors:
            errors.append(f"doctors with no appointments: {[d[0] for d in idle_doctors]}")

        idle_services = s.execute(
            select(Service.service_id).outerjoin(
                Appointment, Appointment.service_id == Service.service_id
            ).where(Appointment.appointment_id.is_(None))
        ).all()
        if idle_services:
            errors.append(f"services with no appointments: {[x[0] for x in idle_services]}")

        # Opening hours: no bookable slot on a Sunday or in the admin break.
        bad_slots = [
            row.schedule_id
            for row in s.execute(
                select(DoctorSchedule.schedule_id, DoctorSchedule.slot_start)
                .where(DoctorSchedule.status != "blocked")
            )
            if row.slot_start.weekday() == 6
            or (row.slot_start.weekday() < 5 and 13 <= row.slot_start.hour < 14)
        ]
        if bad_slots:
            errors.append(f"{len(bad_slots)} bookable slot(s) outside clinic hours, e.g. {bad_slots[:5]}")

    if errors:
        raise SystemExit("VALIDATION FAILED\n" + "\n".join(errors))

    print("Database validation passed.")
    for name, value in counts.items():
        print(f"  {name}: {value}")


if __name__ == "__main__":
    validate()
