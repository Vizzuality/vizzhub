"""Pydantic schemas for mood tracking."""

from pydantic import BaseModel, Field


class AnonymousFeedbackCreate(BaseModel):
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2020, le=2100)
    text: str = Field(min_length=1, max_length=2000)


class AnonymousFeedbackItem(BaseModel):
    id: str
    text: str


class NamedFeedbackItem(BaseModel):
    report_id: str
    user_name: str
    mood: int | None = None
    text: str | None = None


class MoodsResponse(BaseModel):
    mood_distribution: dict[int, int]
    total_reports: int
    total_responses: int
    average_mood: float | None = None
    anonymous_feedback: list[AnonymousFeedbackItem]
    named_feedback: list[NamedFeedbackItem]


class TrendMonth(BaseModel):
    month: int
    year: int
    label: str
    average_mood: float | None = None
    total_responses: int = 0
    total_reports: int = 0
    anonymous_feedback: list[AnonymousFeedbackItem] = []
    named_feedback: list[NamedFeedbackItem] = []


class MoodsTrendResponse(BaseModel):
    months: list[TrendMonth]
