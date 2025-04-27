import asyncpg
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Fetch the Supabase database URL
DATABASE_URL = os.getenv("DATABASE_URL")

# Create an async database connection
async def get_db_connection():
    conn = await asyncpg.connect(DATABASE_URL)
    return conn
