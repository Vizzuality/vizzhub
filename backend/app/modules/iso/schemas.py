from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel


class ReviewStatus(str, Enum):
    DRAFT = "draft"
    COMPLETED = "completed"
    SIGNED = "signed"


class SubjectType(str, Enum):
    USER = "user"
    GROUP = "group"


class ChangeType(str, Enum):
    NEW_USER = "new_user"
    REMOVED_USER = "removed_user"
    ROLE_CHANGE = "role_change"
    NEW_EXTERNAL = "new_external"
    GROUP_MEMBERSHIP_CHANGE = "group_membership_change"


class ActionTaken(str, Enum):
    ACCEPTED = "accepted"
    REMOVED = "removed"
    CORRECTED = "corrected"
    EXCEPTION = "exception"


class AccessSnapshotResponse(BaseModel):
    id: UUID
    provider: str
    captured_at: datetime
    captured_by: UUID | None = None
    data_version: str
    source_metadata: dict
    data: dict
    summary: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class AccessSnapshotSummary(BaseModel):
    id: UUID
    provider: str
    captured_at: datetime
    captured_by: UUID | None = None
    data_version: str
    summary: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class AccessReviewResponse(BaseModel):
    id: UUID
    snapshot_id: UUID
    previous_snapshot_id: UUID | None = None
    reviewer_id: UUID | None = None
    status: str
    scope: str
    diff_summary: dict | None = None
    notes: str | None = None
    signed_by: UUID | None = None
    signed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AccessReviewUpdate(BaseModel):
    notes: str | None = None
    reviewer_id: UUID | None = None


class AccessReviewActionResponse(BaseModel):
    id: UUID
    review_id: UUID
    subject_type: str
    subject_id: str
    subject_label: str | None = None
    change_type: str
    previous_value: dict | None = None
    current_value: dict | None = None
    action_taken: str | None = None
    justification: str | None = None
    approved_by: UUID | None = None
    exception_until: date | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AccessReviewActionUpdate(BaseModel):
    action_taken: ActionTaken | None = None
    justification: str | None = None
    approved_by: UUID | None = None
    exception_until: date | None = None


class AccessReviewDetailResponse(AccessReviewResponse):
    actions: list[AccessReviewActionResponse] = []
