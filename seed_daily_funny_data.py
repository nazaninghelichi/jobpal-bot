#!/usr/bin/env python3
"""
seed_daily_funny_data.py

Seeds dummy cat-themed users into whichever DATABASE_URL you’ve set:
  • via RAILWAY_DATABASE_URL (when you run through `railway run`)
  • or DATABASE_URL
  • or DEV_DATABASE_URL

Will auto-skip loading dotenv if it’s not installed (so Railway containers won’t crash).
"""
import os
# Load .env locally if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Build DATABASE_URL with priority:
# 1. RAILWAY_DATABASE_URL (injected by Railway)
# 2. DATABASE_URL (standard)
# 3. DEV_DATABASE_URL (local development)
# 4. Individual PG* vars (PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE)
# 5. Fallback to localhost default
railway_url = os.getenv("RAILWAY_DATABASE_URL", "").strip()
prod_url    = os.getenv("DATABASE_URL", "").strip()
dev_url     = os.getenv("DEV_DATABASE_URL", "").strip()
pg_host     = os.getenv("PGHOST", "localhost")
pg_port     = os.getenv("PGPORT", "5432")
pg_user     = os.getenv("PGUSER") or os.getenv("POSTGRES_USER")
pg_password = os.getenv("PGPASSWORD") or os.getenv("POSTGRES_PASSWORD")
pg_database = os.getenv("PGDATABASE") or os.getenv("POSTGRES_DB")

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
    DATABASE_URL = "postgresql://postgres:secret@localhost:5432/railway"

print(f"→ Seeding into: {DATABASE_URL}")

import asyncio
import random
from datetime import date
from db import get_pg_conn, init_db_pg

# --- Seeder config ---
GOAL_MIN = 5
GOAL_MAX = 12
USER_PROFILES = [
    (9001, 'whiskers_wonder',   'Whiskers the Wonder'),
    (9002, 'sir_pounce',        'Sir Pounce'),
    (9003, 'captain_meow',      'Captain Meow'),
    (9004, 'fuzzball_fia',      'Fuzzball Fia'),
    (9005, 'mr_snuggles',       'Mr. Snuggles'),
    (9006, 'princess_purrfect', 'Princess Purrfect'),
]

async def seed_funny_data():
    # Ensure tables exist
    await init_db_pg()
    conn = await get_pg_conn()

    # Upsert fake users
    await conn.executemany(
        """
        INSERT INTO users(user_id, username, first_name)
        VALUES ($1,$2,$3)
        ON CONFLICT (user_id) DO NOTHING;
        """,
        USER_PROFILES
    )

    # Seed today's daily_track
    today_iso = date.today().isoformat()
    records = []
    for uid, _, _ in USER_PROFILES:
        goal = random.randint(GOAL_MIN, GOAL_MAX)
        done = max(0, min(15, int(random.gauss(4, 3))))
        records.append((uid, today_iso, goal, done))

    await conn.executemany(
        """
        INSERT INTO daily_track(user_id, date, goal, done)
        VALUES ($1,$2,$3,$4)
        ON CONFLICT (user_id, date)
        DO UPDATE SET goal = EXCLUDED.goal, done = EXCLUDED.done;
        """,
        records
    )

    # Sanity check
    rows = await conn.fetch("SELECT * FROM daily_track WHERE date = $1", today_iso)
    print(f"👉 Found {len(rows)} rows for {today_iso}")

    await conn.close()
    print(f"✅ Seeded {len(USER_PROFILES)} users. Goals ranged {GOAL_MIN}–{GOAL_MAX}.")

if __name__ == "__main__":
    asyncio.run(seed_funny_data())
