# db.py
import os, asyncpg

async def get_pg_conn():
    """Return a new asyncpg connection using the RAILWAY-provided DATABASE_URL."""
    return await asyncpg.connect(os.getenv("DATABASE_URL"))
