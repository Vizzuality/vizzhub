"""Playbook API dependencies."""

from typing import Annotated

from fastapi import Depends

from app.core.auth import TokenData
from app.core.permissions.actions import Action
from app.core.permissions.dependencies import require_permission

PlaybookEditor = Annotated[TokenData, Depends(require_permission(Action.PLAYBOOK_EDIT))]
