from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from datetime import datetime
import sqlite3
import requests
from config import OPENROUTER_API_KEY

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# === Reminder Command ===
async def dailyreminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = datetime.now()
    weekday = today.strftime("%A")
    today_str = today.strftime("%Y-%m-%d")

    # Connect to DB
    conn = sqlite3.connect("jobpal.db")
    c = conn.cursor()

    # Fetch goal
    c.execute("SELECT goal_count FROM user_goals WHERE user_id = ? AND weekday = ?", (user_id, weekday))
    row = c.fetchone()
    goal = row[0] if row else 0

    # Fetch progress
    c.execute("SELECT count_applied FROM user_progress WHERE user_id = ? AND date = ?", (user_id, today_str))
    row = c.fetchone()
    applied = row[0] if row else 0

    conn.close()

    # Get Coach AI Message
    coach_msg = await generate_coach_message(weekday, goal, applied)

    reply = (
        f"📍 *Reminder — {weekday}*\n"
        f"Goal: {goal} | Logged: {applied}\n\n"
        f"🧠 Coach says:\n{coach_msg}"
    )
    await update.message.reply_text(reply, parse_mode="Markdown")

# === Coach Message (LLM) ===
async def generate_coach_message(day: str, goal: int, applied: int) -> str:
    prompt = f"""
You're a cold, direct coach. The user has a job application goal.

Today is {day}. Goal: {goal} job applications. Logged so far: {applied}.

Respond in 1–2 blunt sentences. Don’t add fluff, emojis, or encouragement unless they've earned it.
If they’ve done nothing: call them out. If they’ve done something: acknowledge but push for more.
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "system", "content": "You are a no-nonsense productivity coach."},
            {"role": "user", "content": prompt.strip()}
        ]
    }

    try:
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        return res.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("[Coach Message Error]", e)
        return "Couldn't fetch your coach message today."

# === Export Handler ===
def get_reminder_handler():
    return CommandHandler("dailyreminder", dailyreminder)
