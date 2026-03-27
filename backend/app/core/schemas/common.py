"""Common API schemas shared across modules."""

from pydantic import BaseModel


class PaginatedResponse[T](BaseModel):
    """Generic paginated response envelope."""

    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int
