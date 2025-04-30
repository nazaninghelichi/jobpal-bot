#!/usr/bin/env python3
"""
seed_daily_funny_data.py

This script seeds dummy data for a set of cat-themed "fake" users for **today** only.
We generate one record per fake user, with a random 'done' count between 0 and 15 (mean ~4),
against a fixed daily goal of 7.
IDs in the 9000+ range mark these users as our internal fakes.

Usage:
  - Ensure your `.env` has DEV_DATABASE_URL or DATABASE_URL set correctly.
  - Run:
      python seed_daily_funny_data.py
"""

import asyncio
import random
from datetime import date
from db import get_pg_conn, init_db_pg

# Configuration
GOAL_PER_DAY = 7  # fixed daily goal for all users

# Six cat-themed fake users with IDs in the 9000s to mark them as fakes
USER_PROFILES = [
    (9001, 'whiskers_wonder', 'Whiskers the Wonder'),
    (9002, 'sir_pounce', 'Sir Pounce'),
    (9003, 'captain_meow', 'Captain Meow'),
    (9004, 'fuzzball_fia', 'Fuzzball Fia'),
    (9005, 'mr_snuggles', 'Mr. Snuggles'),
    (9006, 'princess_purrfect', 'Princess Purrfect'),
]

async def seed_funny_data():
    # Ensure tables exist
    await init_db_pg()

    conn = await get_pg_conn()
    # 1) Upsert fake users
    await conn.executemany(
        """
        INSERT INTO users(user_id, username, first_name)
        VALUES ($1, $2, $3)
        ON CONFLICT(user_id) DO NOTHING;
        """,
        USER_PROFILES
    )

    # 2) Seed today's daily_track
    today_iso = date.today().isoformat()
    records = []
    for user_id, _, _ in USER_PROFILES:
        # Random done between 0-15, mean ~4
        done = max(0, min(15, int(random.gauss(4, 3))))
        records.append((user_id, today_iso, GOAL_PER_DAY, done))

    await conn.executemany(
        """
        INSERT INTO daily_track(user_id, date, goal, done)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id, date)
        DO UPDATE SET done = EXCLUDED.done;
        """,
        records
    )

    await conn.close()
    print(f"✅ Seeded {len(USER_PROFILES)} fake users and {len(records)} records for today ({today_iso}).")

if __name__ == '__main__':
    asyncio.run(seed_funny_data())
