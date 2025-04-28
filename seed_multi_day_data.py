"""
seed_multi_day_data.py

This script seeds dummy data for multiple days across a set of users.
It will:
 1. Ensure 23 dummy users exist (IDs 1001–1023).
 2. For each of the past N days (default 30), insert or update a
    daily_track entry with a fixed goal and random done count (0–5).

Usage:
 1. Set your DATABASE_URL in the environment (no need to push this script).
    e.g.
      export DATABASE_URL="postgres://user:pass@localhost:5432/railway"
 2. Run:
      python seed_multi_day_data.py

Adjust DAYS_BACK and USER_COUNT as needed.
"""
import asyncio
import random
from datetime import date, timedelta
from db import get_db_connection

# Configuration
DAYS_BACK = 30        # number of days before today to seed (inclusive)
USER_START_ID = 1001  # first dummy user ID
USER_COUNT = 23       # total number of dummy users to create
GOAL_PER_DAY = 5      # fixed daily goal

async def seed_data():
    conn = await get_db_connection()

    # 1) Create dummy users
    user_inserts = [
        (USER_START_ID + i, f'user{i+1}', f'User{i+1}')
        for i in range(USER_COUNT)
    ]
    await conn.executemany(
        """
        INSERT INTO users(user_id, username, first_name)
        VALUES($1, $2, $3)
        ON CONFLICT(user_id) DO NOTHING;
        """,
        user_inserts
    )

    # 2) Seed daily_track for each day and user
    today = date.today()
    records = []
    for offset in range(DAYS_BACK + 1):
        d = (today - timedelta(days=offset)).isoformat()
        for i in range(USER_COUNT):
            uid = USER_START_ID + i
            done = random.randint(0, GOAL_PER_DAY)
            records.append((uid, d, GOAL_PER_DAY, done))

    # Bulk upsert daily_track
    await conn.executemany(
        """
        INSERT INTO daily_track(user_id, date, goal, done)
        VALUES($1, $2, $3, $4)
        ON CONFLICT (user_id, date)
        DO UPDATE SET done = EXCLUDED.done;
        """,
        records
    )

    await conn.close()
    print(f"✅ Seeded {USER_COUNT} users and {len(records)} daily records for past {DAYS_BACK} days.")

if __name__ == '__main__':
    asyncio.run(seed_data())
