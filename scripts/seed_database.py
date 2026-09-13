import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import csv
from datetime import date, datetime
from pathlib import Path
from sqlalchemy import select
from app.database.connection import get_engine, get_session_factory, initialize_database
from app.database.models import Clinic, Doctor, Service, DoctorService, DoctorSchedule, Patient, Appointment

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"/"production"

def opt(row, key):
    """CSV blanks mean 'not applicable', which is NULL - not an empty string."""
    value = (row.get(key) or "").strip()
    return value or None

def opt_int(row, key):
    value = opt(row, key)
    return int(value) if value is not None else None

def opt_date(row, key):
    value = opt(row, key)
    return date.fromisoformat(value) if value is not None else None

def read(name):
    with (DATA/name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def seed():
    engine=get_engine()
    initialize_database(engine)
    Session=get_session_factory(engine)
    with Session.begin() as s:
        if s.scalar(select(Clinic).where(Clinic.clinic_id=="CLINIC-001")):
            print("Seed already present; skipping.")
            return
        s.add_all([Clinic(clinic_id=r["clinic_id"],tenant_id=r["tenant_id"],name=r["name"],address=r["address"],phone=r["phone"],email=r["email"],timezone=r["timezone"],active=r["active"]=="true") for r in read("clinics.csv")])
        s.add_all([Doctor(doctor_id=r["doctor_id"],clinic_id=r["clinic_id"],full_name=r["full_name"],specialty=r["specialty"],active=r["active"]=="true",qualification=opt(r,"qualification"),years_experience=opt_int(r,"years_experience"),languages=opt(r,"languages"),room_number=opt(r,"room_number")) for r in read("doctors.csv")])
        s.add_all([Service(service_id=r["service_id"],clinic_id=r["clinic_id"],name=r["name"],duration_minutes=int(r["duration_minutes"]),fee_pkr=float(r["fee_pkr"]),active=r["active"]=="true",category=opt(r,"category"),description=opt(r,"description"),follow_up_days=opt_int(r,"follow_up_days")) for r in read("services.csv")])
        s.add_all([DoctorService(doctor_id=r["doctor_id"],service_id=r["service_id"],clinic_id=r["clinic_id"],active=r["active"]=="true") for r in read("doctor_services.csv")])
        s.add_all([DoctorSchedule(schedule_id=int(r["schedule_id"]),clinic_id=r["clinic_id"],doctor_id=r["doctor_id"],slot_start=datetime.fromisoformat(r["slot_start"]),slot_end=datetime.fromisoformat(r["slot_end"]),status=r["status"],slot_type=(opt(r,"slot_type") or "standard")) for r in read("doctor_schedules.csv")])
        s.add_all([Patient(patient_id=r["patient_id"],clinic_id=r["clinic_id"],full_name=r["full_name"],phone=r["phone"],email=r["email"],active=True,gender=opt(r,"gender"),date_of_birth=opt_date(r,"date_of_birth"),preferred_language=opt(r,"preferred_language"),city=opt(r,"city"),registered_on=opt_date(r,"registered_on")) for r in read("patients.csv")])
        s.flush()  # make schedule/patient rows visible to the following appointment inserts
        for r in read("appointments.csv"):
            s.add(Appointment(appointment_id=r["appointment_id"],clinic_id=r["clinic_id"],doctor_id=r["doctor_id"],service_id=r["service_id"],patient_id=r["patient_id"],schedule_id=int(r["schedule_id"]),starts_at=datetime.fromisoformat(r["starts_at"]),ends_at=datetime.fromisoformat(r["ends_at"]),status=r["status"],notes=opt(r,"notes"),booking_channel=opt(r,"booking_channel"),payment_method=opt(r,"payment_method"),payment_status=opt(r,"payment_status"),cancellation_reason=opt(r,"cancellation_reason")))
            schedule = s.get(DoctorSchedule, int(r["schedule_id"]))
            if r["status"] in {"scheduled","confirmed"}:
                schedule.status = "booked"
            elif r["status"] in {"cancelled", "no_show"} and schedule.status != "booked":
                schedule.status = "available"
    print("Seed complete.")
if __name__=="__main__": seed()
