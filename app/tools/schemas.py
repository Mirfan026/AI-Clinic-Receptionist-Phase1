from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

class ToolError(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: dict = Field(default_factory=dict)

class ToolResult(BaseModel):
    success: bool
    data: dict | list | None = None
    error: ToolError | None = None

class ClinicRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clinic_id: str = Field(min_length=1, max_length=50)

class AvailabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clinic_id: str = Field(min_length=1, max_length=50)
    doctor_id: str = Field(min_length=1, max_length=50)
    service_id: str = Field(min_length=1, max_length=50)
    start_at: datetime
    end_at: datetime | None = None
    limit: int = Field(default=20, ge=1, le=100)

    @field_validator("end_at")
    @classmethod
    def end_after_start(cls, v, info):
        if v is not None and "start_at" in info.data and v <= info.data["start_at"]:
            raise ValueError("end_at must be after start_at")
        return v

class BookingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    appointment_id: str = Field(min_length=1, max_length=50)
    clinic_id: str = Field(min_length=1, max_length=50)
    doctor_id: str = Field(min_length=1, max_length=50)
    service_id: str = Field(min_length=1, max_length=50)
    patient_id: str = Field(min_length=1, max_length=50)
    schedule_id: int = Field(gt=0)
    notes: str | None = Field(default=None, max_length=1000)
