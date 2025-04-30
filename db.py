import os
import asyncpg

# Read the database URL from the environment, fall back to local Postgres for dev
DATABASE_URL = os.getenv("DATABASE_URL") or "postgresql://postgres:secret@localhost:5432/railway"

async def get_pg_conn():
    """
    Returns a new asyncpg connection using DATABASE_URL.
    """
    return await asyncpg.connect(DATABASE_URL)

# Alias for backward compatibility with goal_command imports
get_db_connection = get_pg_conn

async def init_db_pg():
    """
    Initialize the Postgres schema with required tables.
    """
    conn = await get_pg_conn()
    # Create users table
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
          user_id    BIGINT PRIMARY KEY,
          username   TEXT,
          first_name TEXT
        );
        """
    )
    # Create daily_track table
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_track (
          user_id BIGINT,
          date    TEXT,
          goal    INTEGER DEFAULT 0,
          done    INTEGER DEFAULT 0,
          PRIMARY KEY(user_id, date)
        );
        """
    )
    # Create user_preferences table
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_preferences (
          user_id           BIGINT PRIMARY KEY,
          reminders_enabled BOOLEAN    DEFAULT TRUE
        );
        """
    )
    await conn.close()
