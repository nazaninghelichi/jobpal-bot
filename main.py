import logging
import sqlite3
from datetime import date, time as dtime
from keep_alive import keep_alive
keep_alive()
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

from goal_command import (
    get_setgoal_handler,
    get_logjobs_handler,
    progress,
    init_daily_track_table
)
from username_command import get_setname_handler
from leaderboard_command import leaderboard as leaderboard_actual
from config import TELEGRAM_BOT_TOKEN
from reminders import register_reminders  # new reminder registrations

logger = logging.getLogger(__name__)

# === Combined DB Initialization ===

def init_db():
    """
    Create all required tables in a single DB call, including migrating schema for reminders.
    """
    init_daily_track_table()

    conn = sqlite3.connect("jobpal.db")
    c = conn.cursor()
    # user_preferences table with reminders_enabled flag
    c.execute(
        '''
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER PRIMARY KEY,
            reminders_enabled INTEGER DEFAULT 1
        )
        '''
    )
    # users meta table with handle + first_name
    c.execute(
        '''
        CREATE TABLE IF NOT EXISTS users (
            user_id      INTEGER PRIMARY KEY,
            username     TEXT DEFAULT '',
            first_name   TEXT DEFAULT '',
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            found_job    BOOLEAN DEFAULT FALSE
        )
        '''
    )
    try:
        c.execute("ALTER TABLE users ADD COLUMN first_name TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

# === Keyboards ===
HOME_KB = ReplyKeyboardMarkup([
    ['🏠 Home']
], resize_keyboard=True)

# === Core Handlers ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    conn = sqlite3.connect("jobpal.db")
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
        (user_id, '', user.first_name or '')
    )
    c.execute(
        "UPDATE users SET first_name = ? WHERE user_id = ?",
        (user.first_name or '', user_id)
    )
    conn.commit()
    c.execute(
        "SELECT COALESCE(NULLIF(username, ''), first_name) FROM users WHERE user_id = ?",
        (user_id,)
    )
    row = c.fetchone()
    display_name = row[0] if row and row[0] else 'there'
    conn.close()

    conn = sqlite3.connect("jobpal.db")
    c = conn.cursor()
    today = date.today().isoformat()
    c.execute(
        "SELECT goal FROM daily_track WHERE user_id = ? AND date = ?",
        (user_id, today)
    )
    row = c.fetchone()
    conn.close()
    has_goal = bool(row and row[0] > 0)

    tip = ""
    if not has_goal:
        tip = "\n\n⚠️ _Tip: Set your daily goal using_ `/setgoal` _to unlock full tracking._"

    main_kb = ReplyKeyboardMarkup([
        ['/logjobs', '/setgoal'],
        ['/leaderboard', '/progress'],
        ['/settings']
    ], resize_keyboard=True)

    await update.message.reply_text(
        f"👋 Welcome back, {display_name}!\n\nHere’s what you can do:\n"
        "• `/logjobs` — Log your applications\n"
        "• `/setgoal` — Set or change your daily goal\n"
        "• `/leaderboard` — See today’s top applicants\n"
        "• `/progress` — See your weekly progress\n"
        "• `/settings` — Configure name, reminders, and more"
        + tip,
        reply_markup=main_kb,
        parse_mode="Markdown"
    )
    logger.info(f"/start triggered by {display_name} ({user_id})")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ *Help*\nUse /settings to view options, or tap 🏠 Home to return to main menu.",
        reply_markup=HOME_KB,
        parse_mode="Markdown"
    )

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💬 *About This Bot*\n\n"
        "I’m also job hunting right now, so I understand how frustrating it can feel.\n\n"
        "This bot helps us track progress and stay consistent — in a fun, supportive way.\n\n"
        "Wishing *you* (and *me*) the best of luck! 🍀\n\n"
        "📩 Feedback: calpal.agent@gmail.com",
        reply_markup=HOME_KB,
        parse_mode="Markdown"
    )

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings_kb = ReplyKeyboardMarkup([
        ['/setname', '/reminders'],
        ['/about', '/help'],
        ['🏠 Home']
    ], resize_keyboard=True)
    await update.message.reply_text(
        "⚙️ *Settings*\n\n"
        "• `/setname` — Change your display name\n"
        "• `/reminders` — Toggle reminders on or off\n"
        "• `/about` — About this bot\n"
        "• `/help` — Show help info\n",
        reply_markup=settings_kb,
        parse_mode="Markdown"
    )

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await leaderboard_actual(update, context)
    await update.message.reply_text(
        "🏠 Tap Home to return to the main menu.",
        reply_markup=HOME_KB
    )

async def progress_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await progress(update, context)
    await update.message.reply_text(
        "🏠 Tap Home to return to the main menu.",
        reply_markup=HOME_KB
    )

# === Main Entry ===

def main():
    logger.info("🔥 Running JobPal…")
    init_db()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Home button handler
    app.add_handler(MessageHandler(filters.Regex(r"^🏠 Home$"), start))

    # Reminder toggle
    async def toggle_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.callback_query:
            user_id = update.callback_query.from_user.id
            await update.callback_query.answer()
        else:
            user_id = update.effective_user.id

        conn = sqlite3.connect("jobpal.db")
        c = conn.cursor()
        c.execute(
            "SELECT reminders_enabled FROM user_preferences WHERE user_id = ?",
            (user_id,)
        )
        row = c.fetchone()
        new_state = 0 if (row and row[0] == 1) else 1
        c.execute(
            "INSERT OR REPLACE INTO user_preferences (user_id, reminders_enabled) VALUES (?, ?)",
            (user_id, new_state)
        )
        conn.commit()
        conn.close()

        status = "ON" if new_state == 1 else "OFF"
        text = (
            f"🔔 Reminders are now *{status}*." +
            " I will send you reminders at 09:00, 15:00, and 21:00 daily "
            "(last at 21:00 because the leaderboard closes at 22:00)."
        )
        btn_label = "Turn OFF" if new_state == 1 else "Turn ON"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(btn_label, callback_data="toggle_reminders")]
        ])

        if update.callback_query:
            await update.callback_query.edit_message_text(
                text, parse_mode="Markdown", reply_markup=keyboard
            )
        else:
            await update.message.reply_text(
                text, parse_mode="Markdown", reply_markup=keyboard
            )

    # Register handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("reminders", toggle_reminders))
    app.add_handler(CallbackQueryHandler(toggle_reminders, pattern="^toggle_reminders$"))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("progress", progress_handler))
    app.add_handler(get_setgoal_handler())
    app.add_handler(get_logjobs_handler())
    app.add_handler(get_setname_handler())
    app.add_handler(CallbackQueryHandler(start, pattern="^cancel$"))

    # Schedule cat-themed reminders
    jq = app.job_queue
    register_reminders(jq)

    logger.info("🤖 JobPal is live! Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
