"""Pydantic schemas for mood tracking."""

from pydantic import BaseModel, Field


class AnonymousFeedbackCreate(BaseModel):
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2020, le=2100)
    text: str = Field(min_length=1, max_length=2000)


class NamedFeedbackItem(BaseModel):
    user_name: str
    mood: int | None = None
    text: str | None = None


class MoodsResponse(BaseModel):
    mood_distribution: dict[int, int]
    total_reports: int
    total_responses: int
    average_mood: float | None = None
    anonymous_feedback: list[str]
    named_feedback: list[NamedFeedbackItem]
