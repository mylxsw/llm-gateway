"""Commercial credential resources, registered only when billing is enabled."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentApiKey
from app.common.errors import AppError
from app.services.commercial import translate
from squirrel_commercial.core import BillingError
from squirrel_commercial.credits import snapshot

router = APIRouter()


class CreditsResponse(BaseModel):
    balance: str
    reserved: str
    available: str
    debt: str
    monthly_limit: str | None
    month_settled: str
    month_reserved: str


@router.get('/v1/credits', response_model=CreditsResponse)
async def get_credits(api_key: CurrentApiKey):
    if not api_key.key_value.startswith('sha256:'):
        raise AppError('Commercial key required', code='commercial_key_required', status_code=403)
    from app.db.session import engine
    try:
        return await snapshot(engine, api_key.id)
    except BillingError as exc:
        raise translate(exc) from exc
