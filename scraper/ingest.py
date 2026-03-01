import os
import logging
from typing import Dict, Any, Optional
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.warning("Variáveis de ambiente do Supabase não configuradas (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)")

# Inicializa cliente apenas se as chaves existirem
supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        logger.error(f"Erro ao inicializar Supabase Client: {e}")

def get_players_to_scrape() -> list[dict]:
    """Busca a lista de jogadores ativos no Supabase."""
    if not supabase:
        logger.error("Supabase client não inicializado.")
        return []
        
    try:
        response = supabase.table("players").select("id, username").eq("is_active", True).execute()
        return response.data
    except Exception as e:
        logger.error(f"Erro ao buscar jogadores: {e}")
        return []

def save_snapshot(player_id: str, status: str) -> Optional[str]:
    """Salva um novo snapshot e retorna o ID gerado."""
    if not supabase:
        return None
        
    try:
        response = supabase.table("snapshots").insert({
            "player_id": player_id,
            "status": status
        }).execute()
        if response.data:
            return response.data[0]["id"]
    except Exception as e:
        logger.error(f"Erro ao criar snapshot: {e}")
    return None

def ingest_player_data(player_id: str, data: Dict[str, Any]) -> bool:
    """Insere todos os dados retornados pelo scraper nas tabelas normalizadas."""
    if not supabase:
        logger.error("Supabase client não inicializado.")
        return False

    status = data["metadados"]["status_requisicao"]
    if status != "sucesso" or not data.get("dados_jogador"):
        # Salva apenas o snapshot com o status de erro
        save_snapshot(player_id, status)
        return False

    try:
        # 1. Snapshot
        snapshot_id = save_snapshot(player_id, "sucesso")
        if not snapshot_id:
            raise Exception("Falha ao obter ID do snapshot recém-criado")

        jogador = data["dados_jogador"]

        # Atualiza plataformas (opcional, já que a constraint unique é no username e não estamos no ON CONFLICT de insert aqui, mas útil)
        if jogador.get("plataformas_detectadas"):
             supabase.table("players").update({"platforms": jogador["plataformas_detectadas"]}).eq("id", player_id).execute()

        # 2. Overview Stats
        if jogador.get("overview") and jogador.get("estatisticas_gerais"):
            ov = jogador["overview"]
            ger = jogador["estatisticas_gerais"]
            supabase.table("overview_stats").insert({
                "snapshot_id": snapshot_id,
                "play_time": ov.get("tempo_de_jogo", "N/A"),
                "battle_pass_level": ov.get("nivel_passe_de_batalha", "N/A"),
                "wins": ger.get("vitorias", 0),
                "kd_ratio": ger.get("kd_ratio", 0.0),
                "win_percentage": ger.get("porcentagem_vitoria", "0%"),
                "total_kills": ger.get("total_kills", 0),
                "total_matches": ger.get("partidas_jogadas", 0),
                "top_3_5_10": ger.get("top_3_5_10", 0),
                "top_6_12_25": ger.get("top_6_12_25", 0)
            }).execute()

        # 3. Period Stats
        for ps in jogador.get("estatisticas_periodo", []):
            supabase.table("period_stats").insert({
                "snapshot_id": snapshot_id,
                "period_name": ps.get("periodo", ""),
                "matches": ps.get("partidas", 0),
                "win_percentage": ps.get("porcentagem_vitoria", "0%"),
                "wins": ps.get("vitorias", 0),
                "kd_ratio": ps.get("kd_ratio", 0.0),
                "kills": ps.get("kills", 0),
                "top_3_5_10": ps.get("top_3_5_10", 0),
                "top_6_12_25": ps.get("top_6_12_25", 0)
            }).execute()

        # 4. Mode Stats
        for ms in jogador.get("estatisticas_por_modo", []):
            supabase.table("mode_stats").insert({
                "snapshot_id": snapshot_id,
                "mode_name": ms.get("modo", ""),
                "matches": ms.get("partidas", 0),
                "tracker_rating": ms.get("tracker_rating", "N/A"),
                "wins": ms.get("vitorias", 0),
                "win_percentage": ms.get("porcentagem_vitoria", "0%"),
                "kills": ms.get("kills", 0),
                "kd_ratio": ms.get("kd_ratio", 0.0),
                "top_position_1_name": ms.get("top_posicao_1_nome", "N/A"),
                "top_position_1": ms.get("top_posicao_1", "N/A"),
                "top_position_2_name": ms.get("top_posicao_2_nome", "N/A"),
                "top_position_2": ms.get("top_posicao_2", "N/A")
            }).execute()

        # 5. Rank Info
        for ri in jogador.get("ranks", []):
            supabase.table("rank_info").insert({
                "snapshot_id": snapshot_id,
                "mode_name": ri.get("modo", ""),
                "current_rank": ri.get("rank_atual", "Unrated"),
                "best_rank": ri.get("melhor_rank", "N/A")
            }).execute()

        # 6. Recent Matches
        for rm in jogador.get("partidas_recentes", []):
            supabase.table("recent_matches").insert({
                "snapshot_id": snapshot_id,
                "session_header": rm.get("data", ""),
                "match_details": rm.get("detalhes", [])
            }).execute()

        logger.info(f"Ingestão concluída para snapshot {snapshot_id}")
        return True

    except Exception as e:
        logger.error(f"Erro durante a ingestão dos dados no Supabase: {e}")
        return False
