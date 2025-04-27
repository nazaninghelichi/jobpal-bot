from dotenv import load_dotenv
import os
from supabase import create_client

# Load environment variables from .env file
load_dotenv()

# Get Supabase URL and KEY
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Test function to insert fake data
def test_insert():
    data = {
        "user_id": 123456,        # example Telegram user ID
        "username": "TestUser",   # example username
        "date": "2025-04-26",     # example date
        "goal": 5,
        "done": 2
    }
    response = supabase.table("daily_track").insert(data).execute()
    print(response)

if __name__ == "__main__":
    test_insert()
