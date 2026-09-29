from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import SearchRequest, SearchResponse
from app.services.search import vector_search

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def semantic_search(
    data: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    results = await vector_search(
        db, data.query, current_user.id, data.folder_id, data.limit
    )
    return SearchResponse(query=data.query, results=results, total=len(results))
