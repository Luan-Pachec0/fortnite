import asyncio
import logging
import os
from playwright.async_api import async_playwright, BrowserContext
from playwright_stealth import stealth_async

logger = logging.getLogger(__name__)

_playwright = None
_browser_context: BrowserContext = None
_semaphore = asyncio.Semaphore(3)

async def init_browser():
    global _playwright, _browser_context
    logger.info("Inicializando Browser Pool...")
    _playwright = await async_playwright().start()
    
    profile_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".browser_profile")
    os.makedirs(profile_dir, exist_ok=True)

    _browser_context = await _playwright.chromium.launch_persistent_context(
        user_data_dir=profile_dir,
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--disable-dev-shm-usage",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-popup-blocking",
            "--disable-extensions",
            "--disable-component-update",
            "--disable-ipc-flooding-protection",
            "--window-size=1366,768"
        ],
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        viewport={"width": 1366, "height": 768},
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
        color_scheme="dark",
        ignore_https_errors=True,
    )
    logger.info("Browser Context persistente carregado com sucesso (pronto para abas concorrentes).")

async def close_browser():
    global _playwright, _browser_context
    if _browser_context:
        await _browser_context.close()
    if _playwright:
        await _playwright.stop()
    logger.info("Browser Pool desligado.")

async def get_page_with_stealth():
    page = await _browser_context.new_page()
    await stealth_async(page)
    return page

def get_semaphore():
    return _semaphore
