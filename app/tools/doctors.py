from sqlalchemy import select
from app.database.connection import get_session_factory
from app.database.models import Doctor
from .schemas import ClinicRequest
from .common import ok, fail, validate_model, validate_clinic

def get_doctors(payload):
    req, error = validate_model(ClinicRequest, payload)
    if error: return error
    Session = get_session_factory()
    with Session() as session:
        error = validate_clinic(session, req.clinic_id)
        if error: return error
        doctors = session.scalars(select(Doctor).where(
            Doctor.clinic_id == req.clinic_id, Doctor.active.is_(True)
        ).order_by(Doctor.full_name)).all()
        return ok({
            "clinic_id": req.clinic_id,
            "count": len(doctors),
            "doctors": [{
                "doctor_id": d.doctor_id,
                "name": d.full_name,
                "specialty": d.specialty,
                "active": d.active
            } for d in doctors]
        })
