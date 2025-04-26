import logging
import sqlite3
import requests
from datetime import time, date

from telegram import Update
from telegram.ext import ContextTypes
from config import GIPHY_API_KEY

logger = logging.getLogger(__name__)

# Helper to fetch display name and counts
def _get_user_info(user_id: int):
    conn = sqlite3.connect("jobpal.db")
    c = conn.cursor()
    # Display name
    c.execute(
        "SELECT COALESCE(NULLIF(username, ''), first_name) FROM users WHERE user_id = ?",
        (user_id,)
    )
    row = c.fetchone()
    display_name = row[0] if row and row[0] else 'there'
    # Today's goal and done
    today = date.today().isoformat()
    c.execute(
        "SELECT goal, done FROM daily_track WHERE user_id = ? AND date = ?",
        (user_id, today)
    )
    row = c.fetchone() or (0, 0)
    goal, done = row
    conn.close()
    return display_name, goal, done

# Helper to fetch a random GIF from Giphy
def _get_random_gif(tag: str):
    try:
        resp = requests.get(
            "https://api.giphy.com/v1/gifs/random",
            params={"api_key": GIPHY_API_KEY, "tag": tag, "rating": "pg"},
            timeout=5
        )
        data = resp.json().get("data", {})
        return data.get("images", {}).get("original", {}).get("url")
    except Exception as e:
        logger.warning(f"Giphy API error for tag '{tag}': {e}")
        return None

# === Reminder Handlers ===

async def morning_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Send morning reminder at 09:00."""
    job = context.job
    user_id = job.chat_id
    display_name, goal, _ = _get_user_info(user_id)

    text = f"😺 Good meowrning, {display_name}! {goal} applications on today’s menu."
    await context.bot.send_message(chat_id=user_id, text=text)
    gif_url = _get_random_gif("cat morning")
    if gif_url:
        await context.bot.send_animation(chat_id=user_id, animation=gif_url)

async def afternoon_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Send afternoon reminder at 15:00."""
    job = context.job
    user_id = job.chat_id
    display_name, goal, done = _get_user_info(user_id)

    text = f"🐱 How’s the hunt? {done} logged so far—keep the momentum!"
    await context.bot.send_message(chat_id=user_id, text=text)
    gif_url = _get_random_gif("cat hunting")
    if gif_url:
        await context.bot.send_animation(chat_id=user_id, animation=gif_url)

async def evening_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Send evening reminder at 21:00."""
    job = context.job
    user_id = job.chat_id
    display_name, goal, done = _get_user_info(user_id)

    text = f"🌠 Final catcall—submit before 22:00 to make the leaderboard."
    await context.bot.send_message(chat_id=user_id, text=text)
    gif_url = _get_random_gif("cat night")
    if gif_url:
        await context.bot.send_animation(chat_id=user_id, animation=gif_url)

# === Registration ===

def register_reminders(job_queue):
    # Schedule daily reminders
    job_queue.run_daily(morning_reminder, time=time(hour=9, minute=0))
    job_queue.run_daily(afternoon_reminder, time=time(hour=15, minute=0))
    job_queue.run_daily(evening_reminder, time=time(hour=21, minute=0))
