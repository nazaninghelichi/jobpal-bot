#!/usr/bin/env python3
"""
seed_daily_funny_data.py

This script seeds dummy data for a set of "funny" cat-themed users across the past 30 days.
Each day each user will have a random 'done' count between 0 and 7 against a fixed goal of 7.

Usage:
  - Ensure your `.env` has DEV_DATABASE_URL or DATABASE_URL set correctly.
  - Run:
      python seed_daily_funny_data.py
"""

import asyncio
import random
from datetime import date, timedelta
from db import get_pg_conn, init_db_pg

# Configuration
DAYS_BACK = 30            # number of days to seed (including today)
GOAL_PER_DAY = 7          # fixed daily goal for all users
USER_PROFILES = [
    (7001, 'whiskers_wonder', 'Whiskers the Wonder'),
    (7002, 'sir_pounce', 'Sir Pounce'),
    (7003, 'captain_meow', 'Captain Meow'),
    (7004, 'fuzzball_fia', 'Fuzzball Fia'),
    (7005, 'mr_snuggles', 'Mr. Snuggles'),
    (7006, 'queen_clawdia', 'Queen Clawdia'),
    (7007, 'baron_whiskerpaws', 'Baron Whiskerpaws'),
    (7008, 'princess_purrfect', 'Princess Purrfect'),
    (7009, 'doodle_paw', 'Doodle Paw'),
    (7010, 'lord_meowington', 'Lord Meowington'),
]

async def seed_funny_data():
    # Ensure tables exist
    await init_db_pg()

    conn = await get_pg_conn()
    # 1) Ensure users exist
    await conn.executemany(
        "INSERT INTO users(user_id, username, first_name) VALUES ($1, $2, $3) "
        "ON CONFLICT(user_id) DO NOTHING;",
        USER_PROFILES
    )

    # 2) Seed daily_track for past DAYS_BACK days
    today = date.today()
    records = []
    for day_offset in range(DAYS_BACK + 1):
        d = (today - timedelta(days=day_offset)).isoformat()
        for user_id, _, _ in USER_PROFILES:
            done = random.randint(0, GOAL_PER_DAY)
            records.append((user_id, d, GOAL_PER_DAY, done))

    await conn.executemany(
        "INSERT INTO daily_track(user_id, date, goal, done) VALUES ($1, $2, $3, $4) "
        "ON CONFLICT (user_id, date) DO UPDATE SET done = EXCLUDED.done;",
        records
    )

    await conn.close()
    print(f"✅ Seeded {len(USER_PROFILES)} cat-themed users and {len(records)} daily records for past {DAYS_BACK} days.")

if __name__ == '__main__':
    asyncio.run(seed_funny_data())
