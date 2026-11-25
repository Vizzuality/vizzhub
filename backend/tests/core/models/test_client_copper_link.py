"""A Copper company can be linked to at most one client."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.models.client import ClientDB


@pytest.mark.asyncio
async def test_two_clients_cannot_share_a_copper_company(db_session):
    db_session.add(ClientDB(name="World Bank Group", slug="wbg-1", copper_company_id=649763))
    await db_session.flush()
    db_session.add(ClientDB(name="World Bank Group", slug="wbg-2", copper_company_id=649763))
    with pytest.raises(IntegrityError):
        await db_session.flush()
