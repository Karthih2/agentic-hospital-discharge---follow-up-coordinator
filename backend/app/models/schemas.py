from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Lang = Literal["en", "ta", "hi", "te", "kn", "ml"]
Level = Literal["full", "appointments", "reminders"]
TaskType = Literal["appointment", "test", "referral", "medicine", "care_instruction", "date", "warning_sign"]


class Strict(BaseModel):
    model_config = {"extra": "forbid"}


class RegisterIn(Strict):
    name: str = Field(min_length=1, max_length=100)
    login: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    language: Lang = "en"
    role: Literal["patient", "family"] = "patient"  # doctor and management accounts are provisioned


class LoginIn(Strict):
    login: str = Field(max_length=100)
    password: str = Field(max_length=128)


class LanguageIn(Strict):
    language: Lang


class FlagIn(Strict):
    note: str | None = Field(default=None, max_length=500)


class MedicineIn(Strict):
    name: str | None = Field(default=None, max_length=120)
    dose: str | None = Field(default=None, max_length=60)
    route: str | None = Field(default=None, max_length=60)
    timing: str | None = Field(default=None, max_length=80)
    duration: str | None = Field(default=None, max_length=60)
    special: str | None = Field(default=None, max_length=200)


class ManualTaskIn(Strict):
    type: TaskType
    title: str = Field(min_length=1, max_length=200)
    due_date: date | None = None
    due_time: str | None = Field(default=None, max_length=20)
    location: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=30)
    doctor_name: str | None = Field(default=None, max_length=100)
    specialty: str | None = Field(default=None, max_length=60)
    medicine: MedicineIn | None = None
    instruction: str | None = Field(default=None, max_length=500)
    supersedes: str | None = None  # id of the task this corrects


class ProviderSelectIn(Strict):
    provider_id: str


class ResolveIn(Strict):
    outcome: Literal["confirmed", "corrected"]
    corrected_values: "CorrectedValues | None" = None


class CorrectedValues(Strict):
    title: str | None = Field(default=None, max_length=200)
    due_date: date | None = None
    due_time: str | None = Field(default=None, max_length=20)
    location: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=30)
    doctor_name: str | None = Field(default=None, max_length=100)
    specialty: str | None = Field(default=None, max_length=60)
    instruction: str | None = Field(default=None, max_length=500)
    medicine: MedicineIn | None = None


ResolveIn.model_rebuild()


class AssignIn(Strict):
    doctor_id: str


class AvailabilityIn(Strict):
    available: bool
    unavailable_until: str | None = None  # ISO datetime


class FallbackIn(Strict):
    next_doctor_id: str | None = None


class ReminderIn(Strict):
    enabled: bool


class HubIn(Strict):
    name: str = Field(min_length=2, max_length=80)


class InvitePatientIn(Strict):
    patient_code: str = Field(min_length=5, max_length=16, pattern=r"^PAT-\d{4,8}$")


class AddViewerIn(Strict):
    login: str = Field(min_length=3, max_length=100)


class AnswerInviteIn(Strict):
    level: Level = "full"


class ConsentIn(Strict):
    level: Level
