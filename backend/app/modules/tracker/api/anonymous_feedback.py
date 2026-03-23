"""Anonymous feedback endpoint — no traceability by design."""

from fastapi import APIRouter

from app.core.api.deps import CurrentUser, DBSession
from app.modules.tracker.models.anonymous_feedback import AnonymousFeedbackDB
from app.modules.tracker.schemas.mood import AnonymousFeedbackCreate

router = APIRouter()


@router.post("", status_code=201)
async def create_anonymous_feedback(
    data: AnonymousFeedbackCreate,
    db: DBSession,
    user: CurrentUser,
) -> dict:
    feedback = AnonymousFeedbackDB(
        month=data.month,
        year=data.year,
        text=data.text,
    )
    db.add(feedback)
    await db.commit()
    return {"status": "ok"}
