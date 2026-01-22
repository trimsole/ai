"""
Database module for managing PostgreSQL database operations.
"""
import asyncpg
import asyncio
import datetime  # Добавлено для работы с датами
from typing import Optional

class Database:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.pool: Optional[asyncpg.Pool] = None

    async def init_db(self):
        """Initialize database connection and tables."""
        # Создаем пул соединений
        self.pool = await asyncpg.create_pool(self.db_url)
        
        async with self.pool.acquire() as conn:
            # Таблица пользователей
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS verified_users (
                    tg_id BIGINT PRIMARY KEY,
                    pocket_id TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица кэша
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_ids (
                    pocket_id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # --- МИГРАЦИЯ: Добавляем колонки для лимитов, если их нет ---
            try:
                await conn.execute("ALTER TABLE verified_users ADD COLUMN IF NOT EXISTS daily_usage INTEGER DEFAULT 0")
                await conn.execute("ALTER TABLE verified_users ADD COLUMN IF NOT EXISTS last_usage_date DATE DEFAULT CURRENT_DATE")
            except Exception as e:
                print(f"Migration warning (might be ok): {e}")

    async def close(self):
        """Close the database connection pool."""
        if self.pool:
            await self.pool.close()

    # --- НОВАЯ ФУНКЦИЯ ДЛЯ ПРОВЕРКИ ЛИМИТОВ ---
    async def check_limit(self, tg_id: int, limit: int = 5) -> dict:
        """
        Проверяет, можно ли пользователю сделать анализ.
        Возвращает словарь: {'allowed': bool, 'remaining': int, 'error': str}
        """
        today = datetime.date.today()

        async with self.pool.acquire() as conn:
            # 1. Получаем данные пользователя
            row = await conn.fetchrow(
                "SELECT daily_usage, last_usage_date FROM verified_users WHERE tg_id = $1", 
                tg_id
            )
            
            # Если пользователя нет в базе (не прошел верификацию в боте)
            if not row:
                return {'allowed': False, 'remaining': 0, 'error': 'User not found'}

            current_usage = row['daily_usage']
            last_date = row['last_usage_date']

            # 2. Если дата в базе старая (вчера и раньше) — сбрасываем счетчик
            if last_date < today:
                await conn.execute(
                    "UPDATE verified_users SET daily_usage = 1, last_usage_date = $1 WHERE tg_id = $2",
                    today, tg_id
                )
                return {'allowed': True, 'remaining': limit - 1}

            # 3. Если дата сегодняшняя, проверяем лимит
            if current_usage < limit:
                # Лимит есть, увеличиваем счетчик
                await conn.execute(
                    "UPDATE verified_users SET daily_usage = daily_usage + 1 WHERE tg_id = $1",
                    tg_id
                )
                return {'allowed': True, 'remaining': limit - (current_usage + 1)}
            
            # 4. Лимит исчерпан
            return {'allowed': False, 'remaining': 0, 'error': 'Limit reached'}

    # ... Остальные старые методы без изменений ...
    async def is_user_verified(self, tg_id: int) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT 1 FROM verified_users WHERE tg_id = $1", tg_id)
            return row is not None

    async def get_user_pocket_id(self, tg_id: int) -> Optional[str]:
        async with self.pool.acquire() as conn:
            val = await conn.fetchval("SELECT pocket_id FROM verified_users WHERE tg_id = $1", tg_id)
            return val

    async def verify_user(self, tg_id: int, pocket_id: str) -> bool:
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO verified_users (tg_id, pocket_id) 
                    VALUES ($1, $2)
                    ON CONFLICT (tg_id) 
                    DO UPDATE SET pocket_id = $2
                """, tg_id, pocket_id)
                return True
        except Exception as e:
            print(f"Error verifying user: {e}")
            return False

    async def is_id_in_cache(self, pocket_id: str) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT 1 FROM cache_ids WHERE pocket_id = $1", pocket_id)
            return row is not None

    async def add_to_cache(self, pocket_id: str) -> bool:
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO cache_ids (pocket_id) 
                    VALUES ($1)
                    ON CONFLICT (pocket_id) DO NOTHING
                """, pocket_id)
                return True
        except Exception as e:
            print(f"Error adding to cache: {e}")
            return False
