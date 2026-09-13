from datetime import date as _date, datetime
from enum import Enum
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class AppointmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class Clinic(TimestampMixin, Base):
    __tablename__ = "clinics"
    clinic_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Karachi")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    doctors = relationship("Doctor", back_populates="clinic")
    services = relationship("Service", back_populates="clinic")
    patients = relationship("Patient", back_populates="clinic")
    schedules = relationship("DoctorSchedule", back_populates="clinic")
    appointments = relationship("Appointment", back_populates="clinic")
    __table_args__ = (Index("ix_clinics_tenant_active", "tenant_id", "active"),)

class Doctor(TimestampMixin, Base):
    __tablename__ = "doctors"
    doctor_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinics.clinic_id", ondelete="RESTRICT"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    specialty: Mapped[str] = mapped_column(String(200), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Profile attributes. Descriptive only - the agent never infers clinical
    # suitability from these, and get_doctors() does not expose them.
    qualification: Mapped[str | None] = mapped_column(String(200), nullable=True)
    years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    languages: Mapped[str | None] = mapped_column(String(200), nullable=True)
    room_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    clinic = relationship("Clinic", back_populates="doctors")
    doctor_services = relationship("DoctorService", back_populates="doctor", cascade="all, delete-orphan")
    schedules = relationship("DoctorSchedule", back_populates="doctor", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="doctor")
    __table_args__ = (Index("ix_doctors_clinic_active", "clinic_id", "active"),)

class Service(TimestampMixin, Base):
    __tablename__ = "services"
    service_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinics.clinic_id", ondelete="RESTRICT"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    fee_pkr: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clinic = relationship("Clinic", back_populates="services")
    doctor_services = relationship("DoctorService", back_populates="service", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="service")
    __table_args__ = (
        CheckConstraint("duration_minutes > 0", name="ck_services_duration_positive"),
        CheckConstraint("fee_pkr >= 0", name="ck_services_fee_nonnegative"),
        UniqueConstraint("clinic_id", "name", name="uq_services_clinic_name"),
        Index("ix_services_clinic_active", "clinic_id", "active"),
    )

class DoctorService(TimestampMixin, Base):
    __tablename__ = "doctor_services"
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.doctor_id", ondelete="CASCADE"), primary_key=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.service_id", ondelete="CASCADE"), primary_key=True)
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinics.clinic_id", ondelete="RESTRICT"), nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    doctor = relationship("Doctor", back_populates="doctor_services")
    service = relationship("Service", back_populates="doctor_services")
    clinic = relationship("Clinic")
    __table_args__ = (Index("ix_doctor_services_clinic_service", "clinic_id", "service_id"),)

class DoctorSchedule(TimestampMixin, Base):
    __tablename__ = "doctor_schedules"
    schedule_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinics.clinic_id", ondelete="RESTRICT"), nullable=False, index=True)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.doctor_id", ondelete="CASCADE"), nullable=False, index=True)
    slot_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    slot_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    slot_type: Mapped[str] = mapped_column(String(30), nullable=False, default="standard")
    clinic = relationship("Clinic", back_populates="schedules")
    doctor = relationship("Doctor", back_populates="schedules")
    __table_args__ = (
        CheckConstraint("slot_end > slot_start", name="ck_schedule_valid_time"),
        CheckConstraint("status IN ('available','booked','blocked')", name="ck_schedule_status"),
        CheckConstraint("slot_type IN ('standard','admin_block','admin_break','emergency_reserve')", name="ck_schedule_slot_type"),
        UniqueConstraint("doctor_id", "slot_start", name="uq_doctor_schedule_slot"),
        Index("ix_schedule_availability", "clinic_id", "doctor_id", "slot_start", "status"),
    )

class Patient(TimestampMixin, Base):
    __tablename__ = "patients"
    patient_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinics.clinic_id", ondelete="RESTRICT"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_of_birth: Mapped[_date | None] = mapped_column(Date, nullable=True)
    preferred_language: Mapped[str | None] = mapped_column(String(30), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    registered_on: Mapped[_date | None] = mapped_column(Date, nullable=True)
    clinic = relationship("Clinic", back_populates="patients")
    appointments = relationship("Appointment", back_populates="patient")
    __table_args__ = (Index("ix_patients_clinic_phone", "clinic_id", "phone"),)

class Appointment(TimestampMixin, Base):
    __tablename__ = "appointments"
    appointment_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinics.clinic_id", ondelete="RESTRICT"), nullable=False, index=True)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.doctor_id", ondelete="RESTRICT"), nullable=False, index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.service_id", ondelete="RESTRICT"), nullable=False, index=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.patient_id", ondelete="RESTRICT"), nullable=False, index=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("doctor_schedules.schedule_id", ondelete="RESTRICT"), nullable=False, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="scheduled")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    booking_channel: Mapped[str | None] = mapped_column(String(30), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    payment_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    clinic = relationship("Clinic", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")
    service = relationship("Service", back_populates="appointments")
    patient = relationship("Patient", back_populates="appointments")
    schedule = relationship("DoctorSchedule", foreign_keys=[schedule_id])
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_appointment_valid_time"),
        CheckConstraint("status IN ('scheduled','confirmed','completed','cancelled','no_show')", name="ck_appointment_status"),
        Index("uq_active_doctor_schedule", "doctor_id", "schedule_id", unique=True,
              sqlite_where=text("status IN ('scheduled','confirmed')"),
              postgresql_where=text("status IN ('scheduled','confirmed')")),
        Index("ix_appointments_clinic_start", "clinic_id", "starts_at"),
        Index("ix_appointments_patient_status", "patient_id", "status"),
    )
