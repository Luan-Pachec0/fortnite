from pydantic import BaseModel
from typing import List, Optional, Dict


class Metadados(BaseModel):
    data_extracao: str
    status_requisicao: str


class EstatisticasGerais(BaseModel):
    """Estatísticas gerais do Lifetime (Overview)."""
    vitorias: int = 0
    kd_ratio: float = 0.0
    porcentagem_vitoria: str = "0%"
    total_kills: int = 0
    partidas_jogadas: int = 0
    top_3_5_10: int = 0
    top_6_12_25: int = 0


class EstatisticasPeriodo(BaseModel):
    """Stats de um período específico (Last 7 Days, Last 30 Days)."""
    periodo: str  # "Last 7 Days" ou "Last 30 Days"
    partidas: int = 0
    porcentagem_vitoria: str = "0%"
    vitorias: int = 0
    kd_ratio: float = 0.0
    kills: int = 0
    top_3_5_10: int = 0
    top_6_12_25: int = 0


class EstatisticasModo(BaseModel):
    """Stats de um modo específico (Solo, Duos, Trios, Squads, LTM)."""
    modo: str
    partidas: int = 0
    tracker_rating: str = "N/A"
    vitorias: int = 0
    porcentagem_vitoria: str = "0%"
    kills: int = 0
    kd_ratio: float = 0.0
    top_posicao_1: str = "N/A"  # ex: "Top 10" → "188"
    top_posicao_1_nome: str = "N/A"
    top_posicao_2: str = "N/A"
    top_posicao_2_nome: str = "N/A"


class RankInfo(BaseModel):
    modo: str
    rank_atual: str = "Unrated"
    melhor_rank: str = "N/A"


class PartidaRecente(BaseModel):
    """Uma sessão de partidas recentes."""
    data: str = ""
    total_partidas_dia: str = ""
    vitorias_dia: str = ""
    detalhes: List[Dict[str, str]] = []


class OverviewInfo(BaseModel):
    """Informações do cabeçalho do overview."""
    tempo_de_jogo: str = "N/A"
    nivel_passe_de_batalha: str = "N/A"


class DadosJogador(BaseModel):
    nome_usuario: str
    plataformas_detectadas: List[str] = []
    overview: Optional[OverviewInfo] = None
    estatisticas_gerais: Optional[EstatisticasGerais] = None
    estatisticas_periodo: List[EstatisticasPeriodo] = []
    estatisticas_por_modo: List[EstatisticasModo] = []
    ranks: List[RankInfo] = []
    partidas_recentes: List[PartidaRecente] = []


class RespostaScraping(BaseModel):
    metadados: Metadados
    dados_jogador: Optional[DadosJogador] = None
