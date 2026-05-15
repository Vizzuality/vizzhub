"""Shared SQL expression helpers used across modules."""

from __future__ import annotations

from sqlalchemy.sql import func


def user_display_name_expr(user_alias):
    """SQL expression resolving to the best display name for a UserDB alias.

    Fallback chain: ``first_name last_name`` > ``name`` > ``email``.
    Returns NULL for each rung when the underlying column is NULL or empty.
    """
    return func.coalesce(
        func.nullif(
            func.concat_ws(
                " ",
                func.nullif(user_alias.first_name, ""),
                func.nullif(user_alias.last_name, ""),
            ),
            "",
        ),
        user_alias.name,
        user_alias.email,
    )


def format_user_display_name(
    first_name: str | None,
    last_name: str | None,
    name: str | None = None,
    email: str | None = None,
) -> str:
    """Python mirror of ``user_display_name_expr``.

    Fallback chain: ``first_name last_name`` > ``first_name`` > ``last_name``
    > ``name`` > email local-part > ``"Unknown"``.
    """
    if first_name and last_name:
        return f"{first_name} {last_name}"
    if first_name:
        return first_name
    if last_name:
        return last_name
    if name:
        return name
    if email:
        return email.split("@")[0]
    return "Unknown"
