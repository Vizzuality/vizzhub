"""Custom exceptions for Project Scorecard."""

from fastapi import HTTPException, status


class ProjectNotFoundError(HTTPException):
    def __init__(self, project_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )


class MetricsNotFoundError(HTTPException):
    def __init__(self, project_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metrics not found for project: {project_id}",
        )


class ConfigurationError(HTTPException):
    def __init__(self, message: str):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Configuration error: {message}",
        )


class CollectorError(HTTPException):
    def __init__(self, source: str, message: str):
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to collect from {source}: {message}",
        )


class ValidationError(HTTPException):
    def __init__(self, message: str):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=message,
        )
