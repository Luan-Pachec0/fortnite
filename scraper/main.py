import sys
import logging
from playwright.sync_api import sync_playwright
from scraper import scrape_player_sync
from ingest import get_players_to_scrape, ingest_player_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
)
logger = logging.getLogger(__name__)

def main():
    logger.info("Iniciando rotina de scraping...")
    
    players = get_players_to_scrape()
    if not players:
        logger.warning("Nenhum jogador ativo encontrado no Supabase.")
        sys.exit(0)
        
    logger.info(f"Encontrados {len(players)} jogadores para processar.")
    
    with sync_playwright() as p:
        # Modo Headless desativado para rodar localmente e evitar o bloqueio do Cloudflare
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-popup-blocking",
                "--disable-extensions",
                "--disable-component-update",
                "--disable-ipc-flooding-protection",
            ]
        )
        
        # Contexto simples temporário
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            color_scheme="dark",
            ignore_https_errors=True
        )
        
        for player in players:
            player_id = player["id"]
            username = player["username"]
            
            logger.info(f"=== Processando {username} ===")
            try:
                data = scrape_player_sync(username, context)
                sucesso = ingest_player_data(player_id, data)
                if sucesso:
                    logger.info(f"[{username}] Ingestão finalizada com sucesso.")
                else:
                    logger.warning(f"[{username}] Falha na ingestão ou status diferente de sucesso.")
            except Exception as e:
                logger.error(f"Erro ao processar {username}: {e}")
                
        browser.close()
        
    logger.info("Rotina de scraping concluída.")

if __name__ == "__main__":
    main()
