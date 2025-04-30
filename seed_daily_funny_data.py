"""
seed_daily_funny_data.py

This script seeds dummy data for a set of "funny" users across the past 30 days.
Each day each user will have a random 'done' count between 0 and 7 against a fixed goal of 7.

Usage:
  - Ensure DATABASE_URL is set in your environment (or uses your local fallback).
  - Run:
      python seed_daily_funny_data.py
"""
import asyncio
import random
from datetime import date, timedelta
from db import get_db_connection

# Configuration
DAYS_BACK = 30            # number of days to seed (including today)
GOAL_PER_DAY = 7          # fixed daily goal for all users
USER_PROFILES = [
    (7001, 'kevin_minion', 'Kevin (Minion)'),               # mischievous yellow hero
    (7002, 'ace_ventura', 'Ace Ventura'),                  # pet detective extraordinaire
    (7003, 'lloyd_christmas', 'Lloyd Christmas'),         # lovable goofball
    (7004, 'the_dude', 'The Dude'),                       # laid-back bowling legend
    (7005, 'sheldon_cooper', 'Sheldon Cooper'),           # brilliant but quirky physicist
    (7006, 'brick_tamland', 'Brick Tamland'),             # anchorman with odd insights
    (7007, 'jack_sparrow', 'Captain Jack Sparrow'),       # eccentric pirate captain
    (7008, 'buddy_elf', 'Buddy the Elf'),                 # cheerful holiday fanatic
    (7009, 'borat_sagdiyev', 'Borat Sagdiyev'),           # over-the-top reporter
    (7010, 'mr_bean', 'Mr. Bean')                         # silent comedic genius
]

async def seed_funny_data():
    conn = await get_db_connection()

    # 1) Ensure users exist
    await conn.executemany(
        "INSERT INTO users(user_id, username, first_name) VALUES ($1, $2, $3) ON CONFLICT(user_id) DO NOTHING;",
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
    print(f"✅ Seeded {len(USER_PROFILES)} users and {len(records)} daily records for past {DAYS_BACK} days.")

if __name__ == '__main__':
    asyncio.run(seed_funny_data())
