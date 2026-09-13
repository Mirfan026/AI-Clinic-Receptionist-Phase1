import os
from datetime import datetime, timedelta
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.database.models import Base, Clinic, Doctor, Service, DoctorService, DoctorSchedule, Patient
from app.database import connection
from app.tools.doctors import get_doctors
from app.tools.services import get_services
from app.tools.availability import check_availability
from app.tools.booking import book_appointment

@pytest.fixture()
def db(tmp_path, monkeypatch):
    db_file = tmp_path / "tools.db"
    url = f"sqlite:///{db_file}"
    engine = create_engine(url, future=True)
    @event.listens_for(engine, "connect")
    def fk(conn, rec): conn.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    Session = sessionmaker(engine, future=True, expire_on_commit=False)
    with Session() as s:
        s.add_all([
            Clinic(clinic_id="C1",tenant_id="T1",name="Test Clinic",address="A",phone="1",email="a@example.com"),
            Doctor(doctor_id="D1",clinic_id="C1",full_name="Dr One",specialty="General"),
            Doctor(doctor_id="D2",clinic_id="C1",full_name="Dr Two",specialty="Cardiology"),
            Service(service_id="S1",clinic_id="C1",name="Consult",duration_minutes=30,fee_pkr=1000),
            Service(service_id="S2",clinic_id="C1",name="Other",duration_minutes=30,fee_pkr=1000),
            Patient(patient_id="P1",clinic_id="C1",full_name="Patient",phone="123"),
            DoctorService(doctor_id="D1",service_id="S1",clinic_id="C1"),
            DoctorSchedule(schedule_id=1,clinic_id="C1",doctor_id="D1",slot_start=datetime(2026,9,14,9),slot_end=datetime(2026,9,14,9,30)),
            DoctorSchedule(schedule_id=2,clinic_id="C1",doctor_id="D1",slot_start=datetime(2026,9,14,10),slot_end=datetime(2026,9,14,10,30)),
        ])
        s.commit()
    monkeypatch.setattr(connection, "get_engine", lambda: engine)
    yield

def test_get_doctors(db):
    r=get_doctors({"clinic_id":"C1"})
    assert r["success"] and r["data"]["count"]==2

def test_get_services(db):
    r=get_services({"clinic_id":"C1"})
    assert r["success"] and r["data"]["count"]==2

def test_invalid_extra_input_rejected(db):
    r=get_doctors({"clinic_id":"C1","sql":"DROP TABLE doctors"})
    assert not r["success"] and r["error"]["code"]=="INVALID_INPUT"

def test_availability_success(db):
    r=check_availability({"clinic_id":"C1","doctor_id":"D1","service_id":"S1","start_at":"2026-09-14T08:00:00","end_at":"2026-09-14T11:00:00"})
    assert r["success"]
    assert [x["schedule_id"] for x in r["data"]["slots"]]==[1,2]

def test_availability_rejects_wrong_doctor_service(db):
    r=check_availability({"clinic_id":"C1","doctor_id":"D2","service_id":"S1","start_at":"2026-09-14T08:00:00"})
    assert not r["success"] and r["error"]["code"]=="DOCTOR_SERVICE_MISMATCH"

def test_availability_never_invents_slot(db):
    r=check_availability({"clinic_id":"C1","doctor_id":"D1","service_id":"S1","start_at":"2026-09-15T08:00:00","end_at":"2026-09-15T20:00:00"})
    assert r["success"] and r["data"]["count"]==0

def test_booking_success(db):
    r=book_appointment({"appointment_id":"A1","clinic_id":"C1","doctor_id":"D1","service_id":"S1","patient_id":"P1","schedule_id":1})
    assert r["success"]
    assert r["data"]["status"]=="confirmed"

def test_booking_rejects_taken_slot(db):
    first=book_appointment({"appointment_id":"A1","clinic_id":"C1","doctor_id":"D1","service_id":"S1","patient_id":"P1","schedule_id":1})
    second=book_appointment({"appointment_id":"A2","clinic_id":"C1","doctor_id":"D1","service_id":"S1","patient_id":"P1","schedule_id":1})
    assert first["success"]
    assert not second["success"] and second["error"]["code"]=="SLOT_UNAVAILABLE"

def test_booking_rejects_wrong_service(db):
    r=book_appointment({"appointment_id":"A1","clinic_id":"C1","doctor_id":"D1","service_id":"S2","patient_id":"P1","schedule_id":1})
    assert not r["success"] and r["error"]["code"]=="DOCTOR_SERVICE_MISMATCH"

def test_booking_rejects_wrong_clinic(db):
    r=book_appointment({"appointment_id":"A1","clinic_id":"NOPE","doctor_id":"D1","service_id":"S1","patient_id":"P1","schedule_id":1})
    assert not r["success"] and r["error"]["code"]=="CLINIC_NOT_FOUND"

def test_booking_requires_existing_slot(db):
    r=book_appointment({"appointment_id":"A1","clinic_id":"C1","doctor_id":"D1","service_id":"S1","patient_id":"P1","schedule_id":999})
    assert not r["success"] and r["error"]["code"]=="SLOT_NOT_FOUND"
