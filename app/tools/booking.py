from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from app.database.connection import get_session_factory
from app.database.models import Appointment, DoctorSchedule, AppointmentStatus
from app.database.repositories import book_appointment as repository_book
from .schemas import BookingRequest
from .common import ok, fail, validate_model, validate_clinic, doctor_for_clinic, service_for_clinic, patient_for_clinic, doctor_service_exists

def book_appointment(payload):
    req, error = validate_model(BookingRequest, payload)
    if error: return error
    Session = get_session_factory()
    with Session() as session:
        error = validate_clinic(session, req.clinic_id)
        if error: return error

        if not doctor_for_clinic(session, req.clinic_id, req.doctor_id):
            return fail("DOCTOR_NOT_FOUND", "Doctor is not active in this clinic.",
                        details={"doctor_id": req.doctor_id})
        service = service_for_clinic(session, req.clinic_id, req.service_id)
        if not service:
            return fail("SERVICE_NOT_FOUND", "Service is not active in this clinic.",
                        details={"service_id": req.service_id})
        if not patient_for_clinic(session, req.clinic_id, req.patient_id):
            return fail("PATIENT_NOT_FOUND", "Patient is not active in this clinic.",
                        details={"patient_id": req.patient_id})
        if not doctor_service_exists(session, req.clinic_id, req.doctor_id, req.service_id):
            return fail("DOCTOR_SERVICE_MISMATCH", "Doctor is not configured to provide this service.",
                        details={"doctor_id": req.doctor_id, "service_id": req.service_id})

        slot = session.get(DoctorSchedule, req.schedule_id)
        if not slot or slot.clinic_id != req.clinic_id or slot.doctor_id != req.doctor_id:
            return fail("SLOT_NOT_FOUND", "Requested schedule slot does not belong to this clinic and doctor.",
                        details={"schedule_id": req.schedule_id})
        if slot.status != "available":
            return fail("SLOT_UNAVAILABLE", "Requested schedule slot is not available.",
                        retryable=True, details={"schedule_id": req.schedule_id, "status": slot.status})

        # Service duration must fit the actual scheduled slot.
        actual_minutes = int((slot.slot_end - slot.slot_start).total_seconds() // 60)
        if actual_minutes < service.duration_minutes:
            return fail("SLOT_TOO_SHORT", "Schedule slot is shorter than the requested service.",
                        details={"slot_minutes": actual_minutes, "service_minutes": service.duration_minutes})

        # Explicit working-hours validation: slot must be a real schedule row
        # and therefore already lies inside the clinic's configured doctor schedule.
        if slot.slot_end <= slot.slot_start:
            return fail("INVALID_SCHEDULE", "Schedule slot has an invalid time range.")

        existing_id = session.scalar(select(Appointment.appointment_id).where(
            Appointment.appointment_id == req.appointment_id
        ))
        if existing_id:
            return fail("APPOINTMENT_ID_EXISTS", "Appointment ID already exists.",
                        details={"appointment_id": req.appointment_id})

        try:
            appt = repository_book(
                session,
                appointment_id=req.appointment_id,
                clinic_id=req.clinic_id,
                doctor_id=req.doctor_id,
                service_id=req.service_id,
                patient_id=req.patient_id,
                schedule_id=req.schedule_id,
                notes=req.notes
            )
            session.commit()
            return ok({
                "appointment_id": appt.appointment_id,
                "clinic_id": appt.clinic_id,
                "doctor_id": appt.doctor_id,
                "service_id": appt.service_id,
                "patient_id": appt.patient_id,
                "schedule_id": appt.schedule_id,
                "start_at": appt.starts_at.isoformat(),
                "end_at": appt.ends_at.isoformat(),
                "status": appt.status
            })
        except IntegrityError:
            session.rollback()
            return fail("BOOKING_CONFLICT", "The slot was taken before this booking committed.",
                        retryable=True, details={"schedule_id": req.schedule_id})
        except ValueError as exc:
            session.rollback()
            return fail("BOOKING_REJECTED", str(exc))
