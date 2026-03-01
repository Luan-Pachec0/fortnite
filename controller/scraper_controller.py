import asyncio
import traceback
import urllib.parse
import time
import random
import re
from datetime import datetime, timezone
from typing import List
from concurrent.futures import ThreadPoolExecutor

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth

import logging

from models.schemas import (
    Metadados,
    OverviewInfo,
    EstatisticasGerais,
    EstatisticasPeriodo,
    EstatisticasModo,
    RankInfo,
    PartidaRecente,
    DadosJogador,
    RespostaScraping,
)

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)


def _safe_int(val: str) -> int:
    try:
        return int(val.replace(",", "").replace(".", "").strip())
    except (ValueError, AttributeError):
        return 0


def _safe_float(val: str) -> float:
    try:
        return float(val.replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0.0


def _extrair_sync(username: str, context) -> RespostaScraping:
    """Extrai TODAS as estatísticas de um único jogador."""
    timestamp = datetime.now(timezone.utc).isoformat()

    usuario_url = urllib.parse.quote(username.strip())
    url = f"https://fortnitetracker.com/profile/all/{usuario_url}"

    page = context.new_page()
    Stealth().apply_stealth_sync(page)

    try:
        logger.info(f"[{username}] Acessando perfil...")
        page.goto(url, wait_until="domcontentloaded", timeout=120_000)

        # ── Captcha / Cloudflare ────────────────────────────────────
        titulo = page.title()
        if "Just a moment" in titulo:
            logger.info(f"[{username}] Cloudflare detectado. Aguardando até 5 minutos para resolução...")
            try:
                page.wait_for_selector(".profile-stat--giant", timeout=300_000)
                logger.info(f"[{username}] Desafio Cloudflare resolvido com sucesso!")
            except PlaywrightTimeoutError:
                logger.warning(f"[{username}] Não conseguiu passar do Cloudflare a tempo.")
                return RespostaScraping(
                    metadados=Metadados(data_extracao=timestamp, status_requisicao="Erro - Captcha Detectado")
                )

        # ── Perfil privado ──────────────────────────────────────────
        if page.locator(".private-profile").count() > 0:
            logger.warning(f"[{username}] Perfil privado.")
            return RespostaScraping(
                metadados=Metadados(data_extracao=timestamp, status_requisicao="Privado")
            )

        # ── Aguardar renderização das stats ─────────────────────────
        try:
            page.wait_for_selector(".profile-stat--giant", timeout=60_000)
        except PlaywrightTimeoutError:
            logger.warning(f"[{username}] Timeout ao carregar estatísticas.")
            return RespostaScraping(
                metadados=Metadados(data_extracao=timestamp, status_requisicao="Erro de tempo limite")
            )
        
        logger.info(f"[{username}] Página carregada. Extraindo TODAS as estatísticas...")

        # Delay humano — simula tempo de leitura antes de interagir
        time.sleep(random.uniform(1.0, 3.0))

        # ════════════════════════════════════════════════════════════
        # 1. OVERVIEW INFO (Tempo de jogo + Nível do Passe)
        # ════════════════════════════════════════════════════════════
        overview_raw = page.evaluate('''() => {
            const header = document.querySelector('.trn-card__header');
            if (!header) return { play_time: 'N/A', battle_pass: 'N/A' };
            const text = header.innerText;
            const ptMatch = text.match(/(\\d+[,.]?\\d*h\\s*\\d+m)\\s*Play Time/i);
            const bpMatch = text.match(/(\\d+)\\s*Battle Pass Level/i);
            return {
                play_time: ptMatch ? ptMatch[1] : 'N/A',
                battle_pass: bpMatch ? bpMatch[1] : 'N/A'
            };
        }''')
        overview_info = OverviewInfo(
            tempo_de_jogo=overview_raw.get("play_time", "N/A"),
            nivel_passe_de_batalha=overview_raw.get("battle_pass", "N/A"),
        )

        # ════════════════════════════════════════════════════════════
        # 2. ESTATÍSTICAS GERAIS (Lifetime Overview - Giant Stats)
        # ════════════════════════════════════════════════════════════
        giant_raw = page.evaluate('''() => {
            const stats = {};
            document.querySelectorAll('.profile-stat.profile-stat--giant').forEach(el => {
                const label = el.querySelector('.profile-stat__label');
                const value = el.querySelector('.profile-stat__value');
                if (label && value) {
                    stats[label.getAttribute('title') || label.innerText.trim()] = value.innerText.trim();
                }
            });
            // Placement distribution
            const placementEl = document.querySelector('.profile-placement-distribution');
            if (placementEl) {
                const text = placementEl.innerText;
                const tm = text.match(/Total Matches\\s+([\\d,]+)/i);
                const t35 = text.match(/Top 3\\/5\\/10\\s+([\\d,]+)/i);
                const t612 = text.match(/Top 6\\/12\\/25\\s+([\\d,]+)/i);
                if (tm) stats['Total Matches'] = tm[1];
                if (t35) stats['Top 3/5/10'] = t35[1];
                if (t612) stats['Top 6/12/25'] = t612[1];
            }
            return stats;
        }''')

        estatisticas_gerais = EstatisticasGerais(
            vitorias=_safe_int(giant_raw.get("Wins", "0")),
            kd_ratio=_safe_float(giant_raw.get("K/D", "0")),
            porcentagem_vitoria=giant_raw.get("Win %", "0%"),
            total_kills=_safe_int(giant_raw.get("Kills", "0")),
            partidas_jogadas=_safe_int(giant_raw.get("Total Matches", "0")),
            top_3_5_10=_safe_int(giant_raw.get("Top 3/5/10", "0")),
            top_6_12_25=_safe_int(giant_raw.get("Top 6/12/25", "0")),
        )

        # ════════════════════════════════════════════════════════════
        # 3. LAST 7 DAYS / LAST 30 DAYS
        # ════════════════════════════════════════════════════════════
        periodos_raw = page.evaluate('''() => {
            const periods = [];
            document.querySelectorAll('.profile-last-stats__period, .profile-last-stats').forEach(periodEl => {
                const titleEl = periodEl.querySelector('h3, .profile-last-stats__title');
                if (!titleEl) return;
                const title = titleEl.innerText.trim();
                if (!title.includes('Last')) return;

                const stats = {};
                periodEl.querySelectorAll('.profile-stat').forEach(statEl => {
                    const label = statEl.querySelector('.profile-stat__label');
                    const value = statEl.querySelector('.profile-stat__value');
                    if (label && value) {
                        stats[label.getAttribute('title') || label.innerText.trim()] = value.innerText.trim();
                    }
                });

                // Matches count from title
                const matchesMatch = title.match(/(\\d+)\\s*Matches/i);
                stats['__matches'] = matchesMatch ? matchesMatch[1] : '0';
                stats['__period'] = title;

                periods.push(stats);
            });
            return periods;
        }''')

        # Fallback: parse from the big overview text
        if not periodos_raw:
            periodos_raw = page.evaluate('''() => {
                const periods = [];
                const overviewCard = document.querySelector('.profile-overview');
                if (!overviewCard) return periods;
                const text = overviewCard.innerText;
                
                // Last 7 Days
                const last7Match = text.match(/Last 7 Days\\n(\\d+) Matches\\n([\\s\\S]*?)(?=Last 30 Days|$)/);
                if (last7Match) {
                    const block = last7Match[2];
                    const stats = { '__period': 'Last 7 Days', '__matches': last7Match[1] };
                    const lines = block.split('\\n').filter(l => l.trim());
                    for (let i = 0; i < lines.length - 1; i += 2) {
                        stats[lines[i].trim()] = lines[i+1].trim();
                    }
                    periods.push(stats);
                }
                
                // Last 30 Days
                const last30Match = text.match(/Last 30 Days\\n(\\d+) Matches\\n([\\s\\S]*?)(?=View Ranked|$)/);
                if (last30Match) {
                    const block = last30Match[2];
                    const stats = { '__period': 'Last 30 Days', '__matches': last30Match[1] };
                    const lines = block.split('\\n').filter(l => l.trim());
                    for (let i = 0; i < lines.length - 1; i += 2) {
                        stats[lines[i].trim()] = lines[i+1].trim();
                    }
                    periods.push(stats);
                }
                
                return periods;
            }''')

        estatisticas_periodo = []
        for p_raw in periodos_raw:
            estatisticas_periodo.append(EstatisticasPeriodo(
                periodo=p_raw.get("__period", ""),
                partidas=_safe_int(p_raw.get("__matches", "0")),
                porcentagem_vitoria=p_raw.get("Win %", "0%"),
                vitorias=_safe_int(p_raw.get("Wins", "0")),
                kd_ratio=_safe_float(p_raw.get("K/D", "0")),
                kills=_safe_int(p_raw.get("Kills", "0")),
                top_3_5_10=_safe_int(p_raw.get("Top 3/5/10", "0")),
                top_6_12_25=_safe_int(p_raw.get("Top 6/12/25", "0")),
            ))

        # ════════════════════════════════════════════════════════════
        # 4. PER-MODE STATS (Solo, Duos, Trios, Squads, LTM)
        # ════════════════════════════════════════════════════════════
        modos_raw = page.evaluate('''() => {
            const modes = [];
            
            document.querySelectorAll('.profile-playlist').forEach(playlist => {
                const modeData = {};
                
                const headerEl = playlist.querySelector('.trn-card__header h2, .profile-playlist__header');
                if (headerEl) {
                    modeData.modo_raw = headerEl.innerText.trim();
                }
                
                const matchesEl = playlist.querySelector('.profile-playlist__matches');
                modeData.partidas_raw = matchesEl ? matchesEl.innerText.trim() : '0';
                
                const ratingEl = playlist.querySelector('.profile-playlist__rating');
                modeData.rating_raw = ratingEl ? ratingEl.innerText.trim() : '';
                
                playlist.querySelectorAll('.profile-stat').forEach(statEl => {
                    const label = statEl.querySelector('.profile-stat__label');
                    const value = statEl.querySelector('.profile-stat__value');
                    if (label && value) {
                        const key = label.getAttribute('title') || label.innerText.trim();
                        modeData[key] = value.innerText.trim();
                    }
                });
                
                if (modeData.modo_raw) modes.push(modeData);
            });
            
            return modes;
        }''')

        estatisticas_por_modo = []
        for m in modos_raw:
            # Parse modo from raw text (first line)
            modo_raw = m.get("modo_raw", "")
            modo = modo_raw.split("\n")[0].strip() if modo_raw else ""
            
            # Parse partidas
            partidas_raw = m.get("partidas_raw", "0").replace(" Matches", "")
            
            # Parse tracker rating from raw text
            rating_raw = m.get("rating_raw", "")
            import re as _re
            rating_match = _re.search(r'(\d[\d,]*)', rating_raw)
            tracker_rating = rating_match.group(1) if rating_match else "N/A"
            
            # Determine top position labels dynamically
            top_keys = [k for k in m.keys() if k.startswith("Top")]
            top1_nome = top_keys[0] if len(top_keys) >= 1 else "N/A"
            top1_val = m.get(top1_nome, "0") if top1_nome != "N/A" else "0"
            top2_nome = top_keys[1] if len(top_keys) >= 2 else "N/A"
            top2_val = m.get(top2_nome, "0") if top2_nome != "N/A" else "0"

            estatisticas_por_modo.append(EstatisticasModo(
                modo=modo,
                partidas=_safe_int(partidas_raw),
                tracker_rating=tracker_rating,
                vitorias=_safe_int(m.get("Wins", "0")),
                porcentagem_vitoria=m.get("Win %", "0%"),
                kills=_safe_int(m.get("Kills", "0")),
                kd_ratio=_safe_float(m.get("K/D", "0")),
                top_posicao_1_nome=top1_nome,
                top_posicao_1=top1_val,
                top_posicao_2_nome=top2_nome,
                top_posicao_2=top2_val,
            ))

        # ════════════════════════════════════════════════════════════
        # 5. RANKS
        # ════════════════════════════════════════════════════════════
        ranks_raw = page.evaluate('''() => {
            const ranks = [];
            document.querySelectorAll('.profile-ranks__title').forEach(titleEl => {
                const modo = titleEl.innerText.trim();
                const contentEl = titleEl.nextElementSibling;
                
                let atual = 'Unrated';
                let melhor = 'N/A';
                
                if (contentEl && contentEl.classList.contains('profile-ranks__content')) {
                    const rankSections = contentEl.children;
                    if (rankSections.length >= 1) {
                        const currentNameEl = rankSections[0].querySelector('.profile-rank__name');
                        if (currentNameEl) atual = currentNameEl.innerText.trim();
                    }
                    if (rankSections.length >= 2) {
                        const bestNameEl = rankSections[1].querySelector('.profile-rank__name');
                        if (bestNameEl) melhor = bestNameEl.innerText.trim();
                    }
                }
                if (!ranks.find(r => r.modo === modo)) {
                    ranks.push({ modo, atual, melhor });
                }
            });
            return ranks;
        }''')

        ranks = [
            RankInfo(modo=r["modo"], rank_atual=r["atual"], melhor_rank=r["melhor"])
            for r in ranks_raw
        ]

        # ════════════════════════════════════════════════════════════
        # 6. RECENT MATCHES (sessões agrupadas por dia)
        # ════════════════════════════════════════════════════════════
        matches_raw = page.evaluate('''() => {
            const sessions = [];
            document.querySelectorAll('.profile-session').forEach(session => {
                const summaryEl = session.querySelector('.profile-session__summary');
                if (!summaryEl) return;
                
                const matches = [];
                session.querySelectorAll('.profile-match-row').forEach(row => {
                    const match = {};
                    
                    const resultEl = row.querySelector('.profile-match-row__result--desktop');
                    if (resultEl) match.resultado = resultEl.innerText.trim();
                    
                    const detailEl = row.querySelector('.profile-match-row__details');
                    if (detailEl) match.descricao = detailEl.innerText.trim();
                    
                    const rankEl = row.querySelector('.profile-match-row__rank');
                    if (rankEl) match.tracker_rating_raw = rankEl.innerText.trim();
                    
                    const statsEl = row.querySelector('.profile-match-row__stats');
                    if (statsEl) match.stats_raw = statsEl.innerText.trim();
                    
                    if (Object.keys(match).length > 0) matches.push(match);
                });
                
                sessions.push({
                    header: summaryEl.innerText.trim(),
                    matches: matches
                });
            });
            return sessions;
        }''')

        partidas_recentes = []
        for s in matches_raw:
            detalhes = []
            for m in s.get("matches", []):
                parsed = {}
                if m.get("resultado"):
                    parsed["resultado"] = m["resultado"]
                if m.get("descricao"):
                    parsed["descricao"] = m["descricao"]
                if m.get("tracker_rating_raw"):
                    parsed["tracker_rating"] = m["tracker_rating_raw"]
                # Parse stats_raw: "Kills\n18\nOutlived\n249\nScore\n3,146"
                stats_raw = m.get("stats_raw", "")
                if stats_raw:
                    lines = stats_raw.split("\n")
                    for i in range(0, len(lines) - 1, 2):
                        parsed[lines[i].strip()] = lines[i + 1].strip()
                detalhes.append(parsed)
            partidas_recentes.append(PartidaRecente(
                data=s.get("header", ""),
                detalhes=detalhes,
            ))

        # ── Plataformas ─────────────────────────────────────────────
        plataformas = page.evaluate('''() => {
            const chips = [];
            document.querySelectorAll('.profile-header__platforms .platform-chip, .profile-header__platform').forEach(el => {
                chips.push(el.innerText.trim());
            });
            return chips.length > 0 ? chips : ['Epic'];
        }''')

        dados = DadosJogador(
            nome_usuario=username,
            plataformas_detectadas=plataformas,
            overview=overview_info,
            estatisticas_gerais=estatisticas_gerais,
            estatisticas_periodo=estatisticas_periodo,
            estatisticas_por_modo=estatisticas_por_modo,
            ranks=ranks,
            partidas_recentes=partidas_recentes,
        )

        return RespostaScraping(
            metadados=Metadados(data_extracao=timestamp, status_requisicao="sucesso"),
            dados_jogador=dados,
        )

    except PlaywrightTimeoutError:
        logger.error(f"[{username}] Timeout ao carregar página/dados.")
        return RespostaScraping(
            metadados=Metadados(data_extracao=timestamp, status_requisicao="Erro de tempo limite")
        )
    except Exception as e:
        logger.error(f"[{username}] Erro inesperado:\n{traceback.format_exc()}")
        return RespostaScraping(
            metadados=Metadados(data_extracao=timestamp, status_requisicao="Erro Desconhecido")
        )
    finally:
        page.close()


def _buscar_um_sync(username: str) -> RespostaScraping:
    """Abre o Playwright em modo síncrono, extraindo dados de UM jogador, e fecha."""
    logger.info(f"Iniciando Browser Chromium para -> {username}")

    # ── Persistent profile dir (mantém cookies do Cloudflare) ────
    import os
    profile_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".browser_profile")
    os.makedirs(profile_dir, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
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
            ],
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            color_scheme="dark",
            ignore_https_errors=True,
        )

        try:
            # Pequeno delay humano aleatório antes de navegar
            time.sleep(random.uniform(1.0, 2.5))
            resultado = _extrair_sync(username, browser)
            return resultado
        except Exception as e:
            logger.error(f"Erro ao processar jogador {username}: {e}")
            return RespostaScraping(
                metadados=Metadados(
                    data_extracao=datetime.now(timezone.utc).isoformat(),
                    status_requisicao="Erro de Execução"
                )
            )
        finally:
            browser.close()


async def buscar_jogador(username: str) -> RespostaScraping:
    """Wrapper assíncrono — executa o scraping síncrono de UM jogador em uma thread separada."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _buscar_um_sync, username)
