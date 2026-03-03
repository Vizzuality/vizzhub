"""Metrics-related enumerations."""

from enum import Enum


class StrategicImpact(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    TRANSFORMATIONAL = "transformational"


class SnapshotType(str, Enum):
    """Snapshot types for metrics records.

    PUNCTUAL: Data for a single month only (month start to month end)
    CUMULATIVE: Data from project start to month end
    """

    PUNCTUAL = "punctual"
    CUMULATIVE = "cumulative"


class ComplaintStatus(str, Enum):
    YES = "yes"
    NO = "no"
    NA = "-"
