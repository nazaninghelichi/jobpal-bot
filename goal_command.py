import logging
import sqlite3
import requests
from datetime import date, datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
)
from config import GIPHY_API_KEY

logger = logging.getLogger(__name__)

# Conversation states
AWAIT_GOAL, LOGGING = range(2)

# Button config
BUTTON_PREFIX = "setgoal_"
BUTTON_STEPS = [5, 10, 15]
LOG_PREFIX = "logjob_"
LOG_DONE = "done"

# =========================================
# Database Setup Helpers
# =========================================

def init_daily_track_table():
    conn = sqlite3.connect("jobpal.db")
    c = conn.cursor()
    c.execute(
        "CREATE TABLE IF NOT EXISTS daily_track (user_id INTEGER, date TEXT, goal INTEGER DEFAULT 0, done INTEGER DEFAULT 0, PRIMARY KEY(user_id, date))"
    )
    conn.commit()
    conn.close()


def get_or_create_today(user_id: int) -> tuple[int, int]:
    today = date.today().isoformat()
    init_daily_track_table()
    conn = sqlite3.connect("jobpal.db")
    c = conn.cursor()
    c.execute(
        "SELECT goal, done FROM daily_track WHERE user_id=? AND date=?",
        (user_id, today)
    )
    row = c.fetchone()
    if row:
        goal, done = row
    else:
        c.execute(
            "SELECT goal FROM daily_track WHERE user_id=? ORDER BY date DESC LIMIT 1",
            (user_id,)
        )
        last = c.fetchone()
        goal = last[0] if last else 0
        done = 0
        c.execute(
            "INSERT INTO daily_track (user_id, date, goal, done) VALUES (?, ?, ?, ?)",
            (user_id, today, goal, done)
        )
        conn.commit()
    conn.close()
    return goal, done


def set_goal(user_id: int, new_goal: int):
    today = date.today().isoformat()
    init_daily_track_table()
    conn = sqlite3.connect("jobpal.db")
    c = conn.cursor()
    c.execute(
        "SELECT done FROM daily_track WHERE user_id=? AND date=?",
        (user_id, today)
    )
    row = c.fetchone()
    done = row[0] if row else 0
    c.execute(
        "INSERT OR REPLACE INTO daily_track (user_id, date, goal, done) VALUES (?, ?, ?, ?)",
        (user_id, today, new_goal, done)
    )
    conn.commit()
    conn.close()


def fetch_count(user_id: int) -> int:
    _, done = get_or_create_today(user_id)
    return done


def update_count(user_id: int, new_done: int):
    today = date.today().isoformat()
    init_daily_track_table()
    conn = sqlite3.connect("jobpal.db")
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO daily_track (user_id, date, goal, done) VALUES (?, ?, COALESCE((SELECT goal FROM daily_track WHERE user_id=? AND date=?), 0), ?)",
        (user_id, today, user_id, today, new_done)
    )
    conn.commit()
    conn.close()

# =========================================
# /setgoal Conversation
# =========================================

async def start_setgoal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    goal, _ = get_or_create_today(user_id)
    keyboard = [
        [InlineKeyboardButton(str(step), callback_data=f"{BUTTON_PREFIX}{step}") for step in BUTTON_STEPS],
        [InlineKeyboardButton("🏠 Home", callback_data="cancel")]
    ]
    text = f"🔢 Your current daily goal is *{goal}*\n\nChoose a new one:"
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return AWAIT_GOAL


async def handle_setgoal_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    if data == "cancel":
        await q.edit_message_text("❌ Goal setting cancelled.")
        return ConversationHandler.END
    new_goal = int(data.replace(BUTTON_PREFIX, ""))
    set_goal(q.from_user.id, new_goal)
    await q.edit_message_text(f"✅ Daily goal set to *{new_goal}*!", parse_mode="Markdown")
    return ConversationHandler.END


def get_setgoal_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("setgoal", start_setgoal)],
        states={
            AWAIT_GOAL: [
                CallbackQueryHandler(handle_setgoal_choice, pattern=f"^{BUTTON_PREFIX}"),
                CallbackQueryHandler(handle_setgoal_choice, pattern="^cancel$")
            ]
        },
        fallbacks=[]
    )

# =========================================
# /logjobs Conversation
# =========================================

def build_log_ui(done: int, goal: int) -> str:
    bar = "✅" * min(done, goal) + "⬜️" * max(0, goal - done)
    extra = f" +{done - goal} ✨" if done > goal else ""
    return f"📦 Today: {done}\n🎯 Goal: {goal}\n{bar}{extra}"


async def start_logjobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    goal, done = get_or_create_today(user_id)
    keyboard = [
        [InlineKeyboardButton("➕ Log one", callback_data=f"{LOG_PREFIX}inc")],
        [InlineKeyboardButton("🏁 Done Logging", callback_data=f"{LOG_PREFIX}{LOG_DONE}")],
        [InlineKeyboardButton("🏠 Home", callback_data="cancel")]
    ]
    await update.message.reply_text(
        build_log_ui(done, goal),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return LOGGING


async def log_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    action = q.data
    if action == f"{LOG_PREFIX}inc":
        done = fetch_count(user_id) + 1
        update_count(user_id, done)
        goal, _ = get_or_create_today(user_id)
        await q.edit_message_text(
            build_log_ui(done, goal),
            reply_markup=q.message.reply_markup
        )
        return LOGGING
    # Done logging
    done = fetch_count(user_id)
    await q.edit_message_text("🎉 Logged! Great work today.", reply_markup=None)
    # send hustle cat GIF
    try:
        resp = requests.get(
            "https://api.giphy.com/v1/gifs/random",
            params={"api_key": GIPHY_API_KEY, "tag": "hustle cat", "rating": "pg"},
            timeout=5
        )
        data = resp.json().get("data", {})
        gif_url = data.get("images", {}).get("original", {}).get("url")
    except Exception as e:
        logger.warning(f"Giphy API error: {e}")
        gif_url = None
    if gif_url:
        await context.bot.send_animation(chat_id=user_id, animation=gif_url)
    # Home button after GIF
    await context.bot.send_message(
        chat_id=user_id,
        text="",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="cancel")]])
    )
    return ConversationHandler.END


def get_logjobs_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("logjobs", start_logjobs)],
        states={LOGGING: [CallbackQueryHandler(log_button)]},
        fallbacks=[CallbackQueryHandler(log_button, pattern="^cancel$")]
    )

# =========================================
# /progress Command
# =========================================

async def progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = datetime.now().date()
    start_week = today - timedelta(days=today.weekday())
    week_dates = [(start_week + timedelta(days=i)).isoformat() for i in range(7)]
    init_daily_track_table()
    conn = sqlite3.connect("jobpal.db")
    c = conn.cursor()
    lines = []
    total_goal = total_done = streak = 0
    on_streak = True
    for d in week_dates:
        c.execute("SELECT goal, done FROM daily_track WHERE user_id=? AND date=?", (user_id, d))
        g, dn = c.fetchone() or (0, 0)
        total_goal += g
        total_done += dn
        if g and dn >= g and on_streak:
            streak += 1
        else:
            on_streak = False
        bar = "✅" * min(dn, g) + "⬜️" * max(0, g - dn)
        extra = f" +{dn - g} ✨" if dn > g else ""
        lines.append(f"{ ("✅" if dn>=g else "❌") } {datetime.fromisoformat(d).strftime('%A')}: {bar}{extra} ({dn}/{g})")
    conn.close()
    pct = round((total_done / total_goal * 100), 1) if total_goal else 0
    streak_line = f"\n🔥 Current streak: **{streak}** day(s)!" if streak else ""
    await update.message.reply_text(
        f"📊 **Weekly Progress**\n" + "\n".join(lines) + f"\n\n**Total:** {total_done}/{total_goal} ({pct}%)" + streak_line,
        parse_mode="Markdown"
    )
