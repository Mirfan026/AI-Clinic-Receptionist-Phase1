from datetime import datetime
import pytest
from sqlalchemy import create_engine,event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from app.database.models import Base,Clinic,Doctor,Service,DoctorService,DoctorSchedule,Patient,Appointment
from app.database.repositories import book_appointment,doctor_can_provide_service

@pytest.fixture()
def session():
    e=create_engine("sqlite:///:memory:",future=True)
    @event.listens_for(e,"connect")
    def fk(dbapi_connection,record): dbapi_connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(e); S=sessionmaker(e,future=True)
    with S() as s:
        s.add_all([
            Clinic(clinic_id="C1",tenant_id="T1",name="Test",address="A",phone="1",email="a@example.com"),
            Doctor(doctor_id="D1",clinic_id="C1",full_name="Dr Test",specialty="General"),
            Service(service_id="S1",clinic_id="C1",name="Consultation",duration_minutes=30,fee_pkr=1000),
            Patient(patient_id="P1",clinic_id="C1",full_name="Patient",phone="123"),
            DoctorSchedule(schedule_id=1,clinic_id="C1",doctor_id="D1",slot_start=datetime(2026,9,14,9),slot_end=datetime(2026,9,14,9,30)),
            DoctorService(doctor_id="D1",service_id="S1",clinic_id="C1")
        ])
        s.commit(); yield s

def test_foreign_keys(session):
    session.add(Doctor(doctor_id="D2",clinic_id="NOPE",full_name="Bad",specialty="X"))
    with pytest.raises(IntegrityError): session.commit()

def test_doctor_service(session):
    assert doctor_can_provide_service(session,"C1","D1","S1")
    assert not doctor_can_provide_service(session,"C1","D1","NOPE")

def test_booking_marks_slot_booked(session):
    a=book_appointment(session,appointment_id="A1",clinic_id="C1",doctor_id="D1",service_id="S1",patient_id="P1",schedule_id=1)
    session.commit()
    assert a.status=="confirmed"
    assert session.get(DoctorSchedule,1).status=="booked"

def test_double_booking_rejected(session):
    book_appointment(session,appointment_id="A1",clinic_id="C1",doctor_id="D1",service_id="S1",patient_id="P1",schedule_id=1)
    session.commit()
    with pytest.raises(ValueError,match="not available"):
        book_appointment(session,appointment_id="A2",clinic_id="C1",doctor_id="D1",service_id="S1",patient_id="P1",schedule_id=1)

def test_invalid_doctor_service(session):
    session.add(Service(service_id="S2",clinic_id="C1",name="Other",duration_minutes=30,fee_pkr=1000)); session.commit()
    with pytest.raises(ValueError,match="not configured"):
        book_appointment(session,appointment_id="A2",clinic_id="C1",doctor_id="D1",service_id="S2",patient_id="P1",schedule_id=1)

def test_status_constraint(session):
    session.add(Appointment(appointment_id="BAD",clinic_id="C1",doctor_id="D1",service_id="S1",patient_id="P1",schedule_id=1,starts_at=datetime(2026,9,14,9),ends_at=datetime(2026,9,14,9,30),status="bad"))
    with pytest.raises(IntegrityError): session.commit()
