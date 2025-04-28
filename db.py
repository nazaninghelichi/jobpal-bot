# db.py

import os
import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL")

async def get_pg_conn():
    return await asyncpg.connect(DATABASE_URL, ssl="require")

async def init_db_pg():
    conn = await get_pg_conn()
    # Create users table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
          user_id    BIGINT PRIMARY KEY,
          username   TEXT,
          first_name TEXT
        );
    """)
    # Create daily_track table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_track (
          user_id BIGINT,
          date    TEXT,
          goal    INTEGER DEFAULT 0,
          done    INTEGER DEFAULT 0,
          PRIMARY KEY(user_id, date)
        );
    """)
    # Create user_preferences table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
          user_id           BIGINT PRIMARY KEY,
          reminders_enabled BOOLEAN    DEFAULT TRUE
        );
    """)
    await conn.close()
