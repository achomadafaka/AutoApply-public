from fastapi import APIRouter

from ..ai import check_ollama
from ..schemas import AIHealthOut


router = APIRouter(tags=["ai"])


@router.get("/ai/health", response_model=AIHealthOut)
async def ai_health() -> AIHealthOut:
    return AIHealthOut(**check_ollama())
