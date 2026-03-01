from fastapi import APIRouter, Query

from models.schemas import RespostaScraping
from controller.scraper_controller import buscar_jogador
router = APIRouter()


@router.get("/api/v1/fortnite/stats", response_model=RespostaScraping)
async def obter_stats(username: str = Query(..., description="Nome do usuário no Fortnite Tracker")):
    """
    Rota para buscar os stats de um jogador específico utilizando RPA / Scraping.
    Exemplo de uso: /api/v1/fortnite/stats?username=034%20Moreira
    """
    resultado = await buscar_jogador(username)
    return resultado
