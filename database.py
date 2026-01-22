"""
Database module for managing PostgreSQL database operations.
"""
import asyncpg
import asyncio
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
            # Create verified_users table
            # tg_id используем BIGINT, так как ID телеграма большие
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS verified_users (
                    tg_id BIGINT PRIMARY KEY,
                    pocket_id TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create cache_ids table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_ids (
                    pocket_id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    async def close(self):
        """Close the database connection pool."""
        if self.pool:
            await self.pool.close()

    async def is_user_verified(self, tg_id: int) -> bool:
        """Check if user is verified."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM verified_users WHERE tg_id = $1", tg_id
            )
            return row is not None

    async def get_user_pocket_id(self, tg_id: int) -> Optional[str]:
        """Get user's Pocket Option ID."""
        async with self.pool.acquire() as conn:
            val = await conn.fetchval(
                "SELECT pocket_id FROM verified_users WHERE tg_id = $1", tg_id
            )
            return val

    async def verify_user(self, tg_id: int, pocket_id: str) -> bool:
        """Bind telegram_id to pocket_id."""
        try:
            async with self.pool.acquire() as conn:
                # В Postgres используем ON CONFLICT для 'INSERT OR REPLACE'
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
        """Check if Pocket Option ID exists in cache."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM cache_ids WHERE pocket_id = $1", pocket_id
            )
            return row is not None

    async def add_to_cache(self, pocket_id: str) -> bool:
        """Add Pocket Option ID to cache."""
        try:
            async with self.pool.acquire() as conn:
                # В Postgres используем ON CONFLICT DO NOTHING для 'INSERT OR IGNORE'
                await conn.execute("""
                    INSERT INTO cache_ids (pocket_id) 
                    VALUES ($1)
                    ON CONFLICT (pocket_id) DO NOTHING
                """, pocket_id)
                return True
        except Exception as e:
            print(f"Error adding to cache: {e}")
            return False
