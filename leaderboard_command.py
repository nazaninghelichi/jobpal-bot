from telegram import Update
from telegram.ext import CommandHandler, CallbackContext, ContextTypes
import sqlite3
from datetime import datetime, timedelta, date
import random
import logging

logger = logging.getLogger(__name__)

funny_names = [
    "Mysterious Logger 🕵️‍♀️",
    "Anonymous Alpaca 🦙",
    "No-Name Ninja 🧤",
    "Nameless Narwhal 🐋",
    "Unknown Unicorn 🦄",
    "Froggy Ghost 🐸👻",
    "Secret Squirrel 🐿️",
    "Shadow Sloth 🦥",
]


def get_todays_top_users(limit=5) -> list[tuple[str, int]]:
    """Fetches top users and their counts specifically for today."""
    today_str = date.today().strftime("%Y-%m-%d")
    top_users_data = []
    conn = None
    try:
        conn = sqlite3.connect("jobpal.db")
        c = conn.cursor()
        c.execute("""
            SELECT p.user_id, u.username, SUM(p.count_applied) as total
            FROM user_progress p
            LEFT JOIN users u ON p.user_id = u.user_id
            WHERE p.date = ? AND p.count_applied > 0
            GROUP BY p.user_id
            ORDER BY total DESC
            LIMIT ?
        """, (today_str, limit))
        rows = c.fetchall()

        for user_id, username, total in rows:
            display_name = f"{username or random.choice(funny_names)}"
            top_users_data.append((display_name, total))

    except Exception as e:
        logger.error(f"Error fetching today's top users: {e}", exc_info=True)
        # Return empty list on error
    finally:
        if conn:
            conn.close()
    return top_users_data


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows weekly or daily leaderboard (no poem)."""
    period = "week"
    if context.args and context.args[0].lower() == "today":
        period = "day"

    conn = sqlite3.connect("jobpal.db")
    c = conn.cursor()

    if period == "day":
        start_date = date.today().strftime("%Y-%m-%d")
        label = "🏅 **Top Job Loggers Today ({start_date}):**\n\n"
        rows_data = get_todays_top_users(limit=10)
        rows = [(name, count) for name, count in rows_data]
    else:
        start_of_week = datetime.now() - timedelta(days=datetime.now().weekday())
        start_date = start_of_week.strftime("%Y-%m-%d")
        label = "🏆 **This Week's Top Loggers (Since {start_date}):**\n\n"
        c.execute("""
            SELECT p.user_id, u.username, SUM(p.count_applied) as total
            FROM user_progress p
            LEFT JOIN users u ON p.user_id = u.user_id
            WHERE p.date >= ? AND p.count_applied > 0
            GROUP BY p.user_id
            ORDER BY total DESC
            LIMIT 10
        """, (start_date,))
        raw_rows = c.fetchall()
        rows = []
        for user_id, username, total in raw_rows:
            display_name = f"{username or random.choice(funny_names)}"
            rows.append((display_name, total))

    leaderboard_text = label
    if not rows:
        leaderboard_text += "The board is empty! Log some jobs to get started!"
    else:
        medals = ["🥇", "🥈", "🥉"]
        for i, (display_name, total) in enumerate(rows):
            rank = medals[i] if i < len(medals) else f"{i+1}."
            leaderboard_text += f"{rank} **{display_name}** — **{total}** apps\n"

    c.execute("SELECT SUM(count_applied) FROM user_progress WHERE date >= ?", (start_date,))
    total_all = c.fetchone()[0] or 0
    leaderboard_text += f"\n\n🎯 Total apps logged ({period}): **{total_all}**"

    conn.close()
    await update.message.reply_text(leaderboard_text, parse_mode="Markdown")


def get_leaderboard_handler():
    return CommandHandler("leaderboard", leaderboard)
