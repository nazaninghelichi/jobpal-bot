"""
seed_dummy_data.py

This script will insert dummy users and daily_track rows into your Postgres
database (local or Railway) using your existing async DB connector.

Usage:
  Ensure your environment variables are set (DATABASE_URL, TELEGRAM_BOT_TOKEN if needed).
  Then run:
      python seed_dummy_data.py
"""
import asyncio
from db import get_db_connection

async def seed():
    conn = await get_db_connection()
    # Create dummy users
    await conn.execute("""
        INSERT INTO users(user_id, username, first_name) VALUES
          (1001, 'alice123', 'Alice'),
          (1002, 'bob_the_builder', 'Bob'),
          (1003, NULL, 'Charlie'),
          (1004, 'dana99', 'Dana'),
          (1005, 'eve_5', 'Eve')
        ON CONFLICT (user_id) DO NOTHING;
    """)
    # Create dummy daily_track entries for today
    await conn.execute("""
        INSERT INTO daily_track(user_id, date, goal, done) VALUES
          (1001, CURRENT_DATE, 5, 3),
          (1002, CURRENT_DATE, 5, 5),
          (1003, CURRENT_DATE, 5, 7),
          (1004, CURRENT_DATE, 5, 2),
          (1005, CURRENT_DATE, 5, 1)
        ON CONFLICT (user_id, date) DO UPDATE SET done = EXCLUDED.done;
    """)
    await conn.close()
    print("✅ Dummy data seeded successfully.")

if __name__ == '__main__':
    asyncio.run(seed())
