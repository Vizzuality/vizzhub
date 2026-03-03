"""Embedded Pydantic models for metrics structures stored as JSON."""

from datetime import date

from pydantic import BaseModel, Field

from .enums import ComplaintStatus


class Milestone(BaseModel):
    """Individual milestone data."""

    name: str
    planned_date: date
    actual_date: date | None = None


class TestMaturity(BaseModel):
    """Test maturity ratings (0-5 scale)."""

    e2e: int | None = Field(default=None, ge=0, le=5)
    unit: int | None = Field(default=None, ge=0, le=5)
    accessibility: int | None = Field(default=None, ge=0, le=5)
    security: int | None = Field(default=None, ge=0, le=5)
    frontend: int | None = Field(default=None, ge=0, le=5)


class ArchitectureChecklist(BaseModel):
    """Architecture documentation checklist."""

    docs_up_to_date: bool = False
    iac_implemented: bool = False
    adrs_maintained: bool = False
    diagrams_updated: bool = False


class PMSatisfaction(BaseModel):
    """PM estimation of client satisfaction."""

    delivery_complaints: ComplaintStatus = ComplaintStatus.NA
    design_complaints: ComplaintStatus = ComplaintStatus.NA
    overall_estimation: int | None = Field(default=None, ge=1, le=5)


class ClientSurvey(BaseModel):
    """End-of-project client satisfaction survey (1-5 scale)."""

    understanding: int | None = Field(default=None, ge=1, le=5)
    proactivity: int | None = Field(default=None, ge=1, le=5)
    communication: int | None = Field(default=None, ge=1, le=5)
    delivery_time: int | None = Field(default=None, ge=1, le=5)
    response_time: int | None = Field(default=None, ge=1, le=5)
    quality: int | None = Field(default=None, ge=1, le=5)
    expectations: int | None = Field(default=None, ge=1, le=5)
    recommend: int | None = Field(default=None, ge=1, le=5)
