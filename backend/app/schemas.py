from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
Pin = Annotated[str, StringConstraints(pattern=r"^\d{4,6}$")]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Language = Literal["en", "te", "hi"]


class RegisterRequest(BaseModel):
    parent_name: Name
    child_name: Name
    grade: int = Field(ge=1, le=5)
    report_language: Language
    pin: Pin


class LoginRequest(BaseModel):
    user_id: Annotated[str, StringConstraints(max_length=20)]
    pin: Annotated[str, StringConstraints(max_length=12)]


class Profile(BaseModel):
    user_id: str
    parent_name: str
    child_name: str
    grade: int
    report_language: Language


class StartSessionRequest(BaseModel):
    lesson_id: Label


class LessonSession(BaseModel):
    id: UUID
    lesson_id: str
    current_step: int
    resumed: bool


class EventRequest(BaseModel):
    step: int = Field(ge=0)
    skill: Label
    question: Annotated[str, StringConstraints(min_length=1, max_length=1000)]
    answer: Annotated[str, StringConstraints(max_length=1000)]
    is_correct: bool


class StepRequest(BaseModel):
    step: int = Field(ge=0, le=100)


class CompleteRequest(BaseModel):
    summary: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1500)] = ""


class SkillMastery(BaseModel):
    skill: str
    score: float
    attempts: int


class SessionSummary(BaseModel):
    lesson_id: str
    summary: str
    completed_at: datetime


class Mistake(BaseModel):
    skill: str
    question: str
    answer: str


class OpenSession(BaseModel):
    id: UUID
    lesson_id: str
    current_step: int


class Progress(BaseModel):
    profile: Profile
    in_progress: OpenSession | None
    completed_lessons: list[str]
    mastery: list[SkillMastery]
    weak_skills: list[str]
    recent_summaries: list[SessionSummary]
    recent_mistakes: list[Mistake]
