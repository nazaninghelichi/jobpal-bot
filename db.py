import os
from dotenv import load_dotenv
import asyncpg

# Load .env for local development (dotenv is optional in production)
load_dotenv()

# Build DATABASE_URL with priority:
# 1. RAILWAY_DATABASE_URL (injected by Railway)
# 2. DATABASE_URL (standard)
# 3. DEV_DATABASE_URL (local development)
# 4. Individual PG* vars (PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE)
# 5. Fallback to localhost default
railway_url = os.getenv("RAILWAY_DATABASE_URL", "").strip()
prod_url    = os.getenv("DATABASE_URL", "").strip()
dev_url     = os.getenv("DEV_DATABASE_URL", "").strip()
pg_host     = os.getenv("PGHOST")
pg_port     = os.getenv("PGPORT")
pg_user     = os.getenv("PGUSER")
pg_password = os.getenv("PGPASSWORD")
pg_database = os.getenv("PGDATABASE")

if railway_url:
    DATABASE_URL = railway_url
elif prod_url:
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
    Initialize the Postgres schema: users, daily_track, user_preferences, and wrapup_logs tables.
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

    # Create wrapup_logs table
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wrapup_logs (
          id         SERIAL PRIMARY KEY,
          date       DATE NOT NULL,
          user_id    BIGINT,
          content    TEXT NOT NULL,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    await conn.close()

async def save_wrapup_log(content: str, date_, user_id=None):
    conn = await get_pg_conn()
    await conn.execute(
        """
        INSERT INTO wrapup_logs (date, user_id, content)
        VALUES ($1, $2, $3)
        """,
        date_, user_id, content
    )
    await conn.close()

from datetime import date, timedelta

async def get_user_profiles() -> dict[int, dict]:
    conn = await get_pg_conn()
    today = date.today()
    user_profiles = {}

    rows = await conn.fetch(
        "SELECT user_id, goal, done FROM daily_track WHERE date = $1",
        today.isoformat()
    )

    for row in rows:
        user_id = row["user_id"]
        goal = row["goal"]
        done = row["done"]

        streak = 0
        for offset in range(1, 8):
            d = today - timedelta(days=offset)
            record = await conn.fetchrow(
                "SELECT done FROM daily_track WHERE user_id = $1 AND date = $2",
                user_id, d.isoformat()
            )
            if record and record["done"] > 0:
                streak += 1
            else:
                break

        trait = "focused finisher" if done == goal else "resilient grinder" if done > 0 else "chill dreamer"

        user_profiles[user_id] = {
            "goal": goal,
            "done": done,
            "streak": streak,
            "trait": trait
        }

    await conn.close()
    return user_profiles
