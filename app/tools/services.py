from sqlalchemy import select
from app.database.connection import get_session_factory
from app.database.models import Service
from .schemas import ClinicRequest
from .common import ok, validate_model, validate_clinic

def get_services(payload):
    req, error = validate_model(ClinicRequest, payload)
    if error: return error
    Session = get_session_factory()
    with Session() as session:
        error = validate_clinic(session, req.clinic_id)
        if error: return error
        services = session.scalars(select(Service).where(
            Service.clinic_id == req.clinic_id, Service.active.is_(True)
        ).order_by(Service.name)).all()
        return ok({
            "clinic_id": req.clinic_id,
            "count": len(services),
            "services": [{
                "service_id": s.service_id,
                "name": s.name,
                "duration_minutes": s.duration_minutes,
                "fee_pkr": float(s.fee_pkr),
                "active": s.active
            } for s in services]
        })
