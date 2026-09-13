from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.models import Clinic, Doctor, Service, Patient, DoctorService, DoctorSchedule
from .schemas import ToolError, ToolResult

def ok(data):
    return ToolResult(success=True, data=data).model_dump(mode="json")

def fail(code, message, *, retryable=False, details=None):
    return ToolResult(
        success=False,
        error=ToolError(code=code, message=message, retryable=retryable, details=details or {})
    ).model_dump(mode="json")

def validate_model(model, payload):
    try:
        return model.model_validate(payload), None
    except ValidationError as e:
        return None, fail("INVALID_INPUT", "Tool input validation failed.", details={"fields": e.errors()})

def clinic_exists(session: Session, clinic_id: str):
    return session.scalar(select(Clinic).where(Clinic.clinic_id == clinic_id))

def doctor_for_clinic(session, clinic_id, doctor_id):
    return session.scalar(select(Doctor).where(
        Doctor.clinic_id == clinic_id, Doctor.doctor_id == doctor_id, Doctor.active.is_(True)
    ))

def service_for_clinic(session, clinic_id, service_id):
    return session.scalar(select(Service).where(
        Service.clinic_id == clinic_id, Service.service_id == service_id, Service.active.is_(True)
    ))

def patient_for_clinic(session, clinic_id, patient_id):
    return session.scalar(select(Patient).where(
        Patient.clinic_id == clinic_id, Patient.patient_id == patient_id, Patient.active.is_(True)
    ))

def doctor_service_exists(session, clinic_id, doctor_id, service_id):
    return session.scalar(select(DoctorService.doctor_id).where(
        DoctorService.clinic_id == clinic_id,
        DoctorService.doctor_id == doctor_id,
        DoctorService.service_id == service_id,
        DoctorService.active.is_(True)
    )) is not None

def validate_clinic(session, clinic_id):
    if not clinic_exists(session, clinic_id):
        return fail("CLINIC_NOT_FOUND", "Clinic does not exist.", details={"clinic_id": clinic_id})
    return None
