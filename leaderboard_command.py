from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
import sqlite3
from datetime import datetime, timedelta, date
import random, logging

logger = logging.getLogger(__name__)

funny_names = [
    "Mysterious Logger 🕵️‍♀️", "Anonymous Alpaca 🦙", "No-Name Ninja 🧤",
    "Nameless Narwhal 🐋", "Unknown Unicorn 🦄", "Froggy Ghost 🐸👻",
    "Secret Squirrel 🐿️", "Shadow Sloth 🦥",
]

def get_todays_top_users(limit=5):
    today = date.today().isoformat()
    conn = sqlite3.connect("jobpal.db")
    c = conn.cursor()
    c.execute("""
        SELECT dt.user_id,
               COALESCE(NULLIF(u.username, ''), u.first_name) AS display_name,
               dt.done AS total
          FROM daily_track dt
     LEFT JOIN users u ON dt.user_id = u.user_id
         WHERE dt.date = ?
           AND dt.done > 0
      ORDER BY total DESC
         LIMIT ?
    """, (today, limit))
    rows = c.fetchall()
    conn.close()

    # Ignore user_id; unpack display_name & total correctly
    result = []
    for _user_id, display_name, total in rows:
        name = display_name or random.choice(funny_names)
        result.append((name, total))
    return result

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_todays_top_users(limit=10)
    date_str = date.today().isoformat()
    text = f"🏅 **Top Loggers Today ({date_str}):**\n\n"

    if not rows:
        text += "No entries yet — get logging!"
    else:
        medals = ["🥇","🥈","🥉"]
        for i, (name, total) in enumerate(rows):
            rank = medals[i] if i < 3 else f"{i+1}."
            text += f"{rank} **{name}** — **{total}** apps\n"

    total_all = sum(t for _, t in rows)
    text += f"\n\n🎯 Total today: **{total_all}**"
    await update.message.reply_text(text, parse_mode="Markdown")
