import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from app.database.connection import get_engine,get_session_factory
from app.database.models import Doctor,DoctorSchedule,Appointment
S=get_session_factory(get_engine())
with S() as s:
    print("Active doctors:")
    for d in s.scalars(select(Doctor).where(Doctor.clinic_id=="CLINIC-001",Doctor.active.is_(True)).order_by(Doctor.full_name)):
        print(d.doctor_id,d.full_name,d.specialty)
    print("\nAvailable slots for DR-001:")
    for x in s.scalars(select(DoctorSchedule).where(DoctorSchedule.clinic_id=="CLINIC-001",DoctorSchedule.doctor_id=="DR-001",DoctorSchedule.status=="available").order_by(DoctorSchedule.slot_start).limit(10)):
        print(x.schedule_id,x.slot_start,x.slot_end)
    print("\nAppointments:")
    for a in s.scalars(select(Appointment).where(Appointment.clinic_id=="CLINIC-001").order_by(Appointment.starts_at)):
        print(a.appointment_id,a.doctor_id,a.service_id,a.starts_at,a.status)
