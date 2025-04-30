import os
import asyncpg
from dotenv import load_dotenv

# Load environment variables (DEV_DATABASE_URL, DATABASE_URL, PG* vars) from .env in local dev
# In production (e.g. Railway), DATABASE_URL or PG* vars will be injected automatically
load_dotenv()

# Build the connection URL with this priority:
# 1. DEV_DATABASE_URL (for local development)
# 2. DATABASE_URL (Railway or other prod env var)
# 3. Individual PG* vars (PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE)
# 4. Fallback to a default localhost
DATABASE_URL = (
    os.getenv("DEV_DATABASE_URL")
    or os.getenv("DATABASE_URL")
    or (
        f"postgresql://{os.getenv('PGUSER')}:{os.getenv('PGPASSWORD')}"
        f"@{os.getenv('PGHOST')}:{os.getenv('PGPORT')}"
        f"/{os.getenv('PGDATABASE')}"
    )
    or "postgresql://postgres:secret@localhost:5432/railway"
)

async def get_pg_conn():
    """
    Return a new asyncpg connection to the Postgres database based on DATABASE_URL.
    """
    return await asyncpg.connect(DATABASE_URL)

# Alias for backward compatibility
get_db_connection = get_pg_conn

async def init_db_pg():
    """
    Initialize the Postgres schema: users, daily_track, and user_preferences tables.
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
