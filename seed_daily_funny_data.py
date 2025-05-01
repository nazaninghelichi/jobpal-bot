#!/usr/bin/env python3
"""
seed_daily_funny_data.py

This script seeds dummy data for a set of cat-themed "fake" users for **today** only.
Each user will now get a random daily goal (between GOAL_MIN and GOAL_MAX).
"""

import os
from dotenv import load_dotenv

# 1) Load env and pick the right DATABASE_URL
load_dotenv()
rail = os.getenv("RAILWAY_DATABASE_URL")
prod = os.getenv("DATABASE_URL")
dev  = os.getenv("DEV_DATABASE_URL")
chosen = rail or prod or dev
if not chosen:
    raise RuntimeError("No DATABASE_URL/RAILWAY_DATABASE_URL/DEV_DATABASE_URL set!")
os.environ["DATABASE_URL"] = chosen
print("→ Seeding into:", chosen)

# 2) Now import your asyncpg connector
import asyncio
import random
from datetime import date
from db import get_pg_conn, init_db_pg

# --- Seeder config ---
# Goals will be random between these bounds
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
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id) DO NOTHING;
        """,
        USER_PROFILES
    )

    today_iso = date.today().isoformat()
    records = []
    for uid, _, _ in USER_PROFILES:
        # Random goal between GOAL_MIN and GOAL_MAX
        goal = random.randint(GOAL_MIN, GOAL_MAX)
        # Random done count (0–15) as before
        done = max(0, min(15, int(random.gauss(4, 3))))
        records.append((uid, today_iso, goal, done))

    await conn.executemany(
        """
        INSERT INTO daily_track(user_id, date, goal, done)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id, date)
        DO UPDATE SET goal = EXCLUDED.goal, done = EXCLUDED.done;
        """,
        records
    )

    # Sanity check
    rows = await conn.fetch("SELECT * FROM daily_track WHERE date = $1", today_iso)
    print(f"👉 Found {len(rows)} rows for {today_iso}")
    await conn.close()

    print(f"✅ Seeded {len(USER_PROFILES)} users. Goals ranged from "
          f"{min(r[2] for r in records)} to {max(r[2] for r in records)}.")

if __name__ == "__main__":
    asyncio.run(seed_funny_data())
