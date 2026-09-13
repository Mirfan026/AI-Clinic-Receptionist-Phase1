from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Appointment, AppointmentStatus, Doctor, DoctorSchedule, DoctorService, Patient, Service

def get_doctors(session: Session, clinic_id: str):
    return list(session.scalars(select(Doctor).where(Doctor.clinic_id == clinic_id, Doctor.active.is_(True)).order_by(Doctor.full_name)))

def get_services(session: Session, clinic_id: str):
    return list(session.scalars(select(Service).where(Service.clinic_id == clinic_id, Service.active.is_(True)).order_by(Service.name)))

def get_available_slots(session: Session, clinic_id: str, doctor_id: str):
    return list(session.scalars(select(DoctorSchedule).where(
        DoctorSchedule.clinic_id == clinic_id,
        DoctorSchedule.doctor_id == doctor_id,
        DoctorSchedule.status == "available"
    ).order_by(DoctorSchedule.slot_start)))

def doctor_can_provide_service(session: Session, clinic_id: str, doctor_id: str, service_id: str) -> bool:
    return session.scalar(select(DoctorService.doctor_id).where(
        DoctorService.clinic_id == clinic_id,
        DoctorService.doctor_id == doctor_id,
        DoctorService.service_id == service_id,
        DoctorService.active.is_(True)
    )) is not None

def book_appointment(session: Session, *, appointment_id, clinic_id, doctor_id, service_id, patient_id, schedule_id, notes=None):
    slot = session.get(DoctorSchedule, schedule_id)
    if not slot:
        raise ValueError("Schedule slot does not exist.")
    if slot.clinic_id != clinic_id or slot.doctor_id != doctor_id:
        raise ValueError("Schedule does not belong to requested clinic/doctor.")
    if slot.status != "available":
        raise ValueError("Schedule slot is not available.")

    doctor = session.get(Doctor, doctor_id)
    service = session.get(Service, service_id)
    patient = session.get(Patient, patient_id)
    if not doctor or doctor.clinic_id != clinic_id:
        raise ValueError("Invalid doctor for clinic.")
    if not service or service.clinic_id != clinic_id:
        raise ValueError("Invalid service for clinic.")
    if not patient or patient.clinic_id != clinic_id:
        raise ValueError("Invalid patient for clinic.")
    if not doctor_can_provide_service(session, clinic_id, doctor_id, service_id):
        raise ValueError("Doctor is not configured to provide this service.")

    appt = Appointment(
        appointment_id=appointment_id, clinic_id=clinic_id, doctor_id=doctor_id,
        service_id=service_id, patient_id=patient_id, schedule_id=schedule_id,
        starts_at=slot.slot_start, ends_at=slot.slot_end,
        status=AppointmentStatus.CONFIRMED.value, notes=notes
    )
    session.add(appt)
    slot.status = "booked"
    session.flush()
    return appt
