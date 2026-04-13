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
