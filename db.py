import os
from dotenv import load_dotenv
import asyncpg

# Load environment variables (.env) in local development
# In production (Railway), DATABASE_URL or PG* vars will be injected automatically
load_dotenv()

# Build DATABASE_URL with this priority:
# 1. DATABASE_URL (production)
# 2. DEV_DATABASE_URL (local development)
# 3. Individual PG* vars (PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE)
# 4. Fallback to localhost default
prod_url = os.getenv("DATABASE_URL", "").strip()
dev_url = os.getenv("DEV_DATABASE_URL", "").strip()
pg_host = os.getenv("PGHOST")
pg_port = os.getenv("PGPORT")
pg_user = os.getenv("PGUSER")
pg_password = os.getenv("PGPASSWORD")
pg_database = os.getenv("PGDATABASE")

if prod_url:
    DATABASE_URL = prod_url
elif dev_url:
    DATABASE_URL = dev_url
elif pg_host and pg_port and pg_user and pg_password and pg_database:
    DATABASE_URL = (
        f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_database}"
    )
else:
    # Last-resort localhost fallback
    DATABASE_URL = "postgresql://postgres:secret@localhost:5432/railway"

async def get_pg_conn():
    """
    Return a new asyncpg connection to the Postgres database.
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
