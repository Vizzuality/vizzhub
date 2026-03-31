"""ISO Docs API dependencies."""

from typing import Annotated

from fastapi import Depends

from app.core.auth import TokenData
from app.core.permissions.actions import Action
from app.core.permissions.dependencies import require_permission

IsoDocsEditor = Annotated[TokenData, Depends(require_permission(Action.ISO_DOCS_EDIT))]


def is_iso_docs_editor(user: TokenData) -> bool:
    return "*" in user.permissions or Action.ISO_DOCS_EDIT in user.permissions
