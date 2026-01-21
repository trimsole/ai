"""
Database module for managing SQLite database operations.
"""
import sqlite3
import asyncio
from typing import Optional, Tuple
import aiosqlite


class Database:
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path

    async def init_db(self):
        """Initialize database tables."""
        async with aiosqlite.connect(self.db_path) as db:
            # Create verified_users table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS verified_users (
                    tg_id INTEGER PRIMARY KEY,
                    pocket_id TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create cache_ids table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS cache_ids (
                    pocket_id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.commit()

    async def is_user_verified(self, tg_id: int) -> bool:
        """Check if user is verified."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM verified_users WHERE tg_id = ?", (tg_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row is not None

    async def get_user_pocket_id(self, tg_id: int) -> Optional[str]:
        """Get user's Pocket Option ID."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT pocket_id FROM verified_users WHERE tg_id = ?", (tg_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def verify_user(self, tg_id: int, pocket_id: str) -> bool:
        """Bind telegram_id to pocket_id."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT OR REPLACE INTO verified_users (tg_id, pocket_id) VALUES (?, ?)",
                    (tg_id, pocket_id)
                )
                await db.commit()
                return True
        except Exception as e:
            print(f"Error verifying user: {e}")
            return False

    async def is_id_in_cache(self, pocket_id: str) -> bool:
        """Check if Pocket Option ID exists in cache."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM cache_ids WHERE pocket_id = ?", (pocket_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row is not None

    async def add_to_cache(self, pocket_id: str) -> bool:
        """Add Pocket Option ID to cache."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO cache_ids (pocket_id) VALUES (?)",
                    (pocket_id,)
                )
                await db.commit()
                return True
        except Exception as e:
            print(f"Error adding to cache: {e}")
            return False
