from sqlalchemy import select
from app.database.connection import get_session_factory
from app.database.models import DoctorSchedule
from .schemas import AvailabilityRequest
from .common import ok, fail, validate_model, validate_clinic, doctor_for_clinic, service_for_clinic, doctor_service_exists

def check_availability(payload):
    req, error = validate_model(AvailabilityRequest, payload)
    if error: return error
    Session = get_session_factory()
    with Session() as session:
        error = validate_clinic(session, req.clinic_id)
        if error: return error
        if not doctor_for_clinic(session, req.clinic_id, req.doctor_id):
            return fail("DOCTOR_NOT_FOUND", "Doctor is not active in this clinic.",
                        details={"doctor_id": req.doctor_id, "clinic_id": req.clinic_id})
        service = service_for_clinic(session, req.clinic_id, req.service_id)
        if not service:
            return fail("SERVICE_NOT_FOUND", "Service is not active in this clinic.",
                        details={"service_id": req.service_id, "clinic_id": req.clinic_id})
        if not doctor_service_exists(session, req.clinic_id, req.doctor_id, req.service_id):
            return fail("DOCTOR_SERVICE_MISMATCH", "Doctor is not configured to provide this service.",
                        details={"doctor_id": req.doctor_id, "service_id": req.service_id})

        end = req.end_at
        if end is None:
            from datetime import timedelta
            end = req.start_at + timedelta(days=14)

        if end <= req.start_at:
            return fail("INVALID_TIME_RANGE", "Requested end time must be after start time.")

        # Only DB schedule rows with status=available are authoritative.
        slots = session.scalars(select(DoctorSchedule).where(
            DoctorSchedule.clinic_id == req.clinic_id,
            DoctorSchedule.doctor_id == req.doctor_id,
            DoctorSchedule.status == "available",
            DoctorSchedule.slot_start >= req.start_at,
            DoctorSchedule.slot_start < end
        ).order_by(DoctorSchedule.slot_start).limit(req.limit)).all()

        return ok({
            "clinic_id": req.clinic_id,
            "doctor_id": req.doctor_id,
            "service_id": req.service_id,
            "requested_window": {"start_at": req.start_at.isoformat(), "end_at": end.isoformat()},
            "count": len(slots),
            "slots": [{
                "schedule_id": s.schedule_id,
                "start_at": s.slot_start.isoformat(),
                "end_at": s.slot_end.isoformat(),
                "status": s.status
            } for s in slots]
        })
