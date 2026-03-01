import aiosqlite
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fortnite_cache.db")
CACHE_EXPIRATION_MINUTES = 30

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS player_stats (
                username TEXT PRIMARY KEY,
                data TEXT,
                updated_at TIMESTAMP
            )
        ''')
        await db.commit()

async def get_cached_stats(username: str) -> Optional[dict]:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute('SELECT data, updated_at FROM player_stats WHERE username = ?', (username,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    data_str, updated_at_str = row
                    updated_at = datetime.fromisoformat(updated_at_str)
                    
                    if datetime.now(timezone.utc) - updated_at < timedelta(minutes=CACHE_EXPIRATION_MINUTES):
                        logger.info(f"[{username}] Resposta servida direto do Cache (SQLite).")
                        return json.loads(data_str)
                    else:
                        logger.info(f"[{username}] Cache expirado.")
                        return None
    except Exception as e:
        logger.error(f"Erro ao ler do cache SQLite: {e}")
    return None

async def set_cached_stats(username: str, data: dict):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            updated_at = datetime.now(timezone.utc).isoformat()
            data_str = json.dumps(data)
            await db.execute('''
                INSERT INTO player_stats (username, data, updated_at) 
                VALUES (?, ?, ?) 
                ON CONFLICT(username) DO UPDATE SET 
                    data=excluded.data, 
                    updated_at=excluded.updated_at
            ''', (username, data_str, updated_at))
            await db.commit()
    except Exception as e:
        logger.error(f"Erro ao salvar no cache SQLite: {e}")
