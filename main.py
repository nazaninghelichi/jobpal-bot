import logging
import os
import asyncio
from datetime import date
from keep_alive import keep_alive
keep_alive()
from dotenv import load_dotenv
load_dotenv()

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
import telegram.ext

from goal_command import get_setgoal_handler, get_logjobs_handler, progress
from username_command import get_setname_handler
from leaderboard_command import leaderboard as leaderboard_actual
from config import TELEGRAM_BOT_TOKEN
from reminders import register_reminders
from db import get_pg_conn, init_db_pg

# === Logging Configuration ===
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
# Enable DEBUG logging for handler dispatch
telegram.ext.logger.setLevel(logging.DEBUG)

# === Keyboards ===
HOME_KB = ReplyKeyboardMarkup([['🏠 Home']], resize_keyboard=True)

# === Core Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    conn = await get_pg_conn()
    # Upsert user record
    await conn.execute(
        "INSERT INTO users(user_id, username, first_name) VALUES($1, $2, $3) "
        "ON CONFLICT (user_id) DO UPDATE SET first_name = EXCLUDED.first_name",
        user_id, '', user.first_name or ''
    )
    row = await conn.fetchrow(
        "SELECT COALESCE(NULLIF(username, ''), first_name) AS display_name "
        "FROM users WHERE user_id = $1",
        user_id
    )
    display_name = row['display_name'] if row and row['display_name'] else 'there'

    # Check if today's goal is set
    today = date.today().isoformat()
    row2 = await conn.fetchrow(
        "SELECT goal FROM daily_track WHERE user_id = $1 AND date = $2",
        user_id, today
    )
    has_goal = bool(row2 and row2['goal'] > 0)
    await conn.close()

    tip = ''
    if not has_goal:
        tip = '\n\n⚠️ _Tip: Set your daily goal using_ `/setgoal` _to unlock full tracking._'

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

async def toggle_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id if update.callback_query else update.effective_user.id
    if update.callback_query:
        await update.callback_query.answer()

    conn = await get_pg_conn()
    row = await conn.fetchrow(
        "SELECT reminders_enabled FROM user_preferences WHERE user_id = $1",
        user_id
    )
    new_state = not bool(row and row['reminders_enabled'])
    await conn.execute(
        "INSERT INTO user_preferences(user_id, reminders_enabled) VALUES($1,$2) "
        "ON CONFLICT (user_id) DO UPDATE SET reminders_enabled = EXCLUDED.reminders_enabled",
        user_id, new_state
    )
    await conn.close()

    status = "ON" if new_state else "OFF"
    text = (
        f"🔔 Reminders are now *{status}*."
        " I will send you reminders at 09:00, 15:00, and 21:00 daily"
        " (last at 21:00 because the leaderboard closes at 22:00)."
    )
    btn_label = "Turn OFF" if new_state else "Turn ON"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(btn_label, callback_data="toggle_reminders")]])

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

async def testdb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        conn = await get_pg_conn()
        rows = await conn.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
        )
        names = ", ".join(r['table_name'] for r in rows)
        await update.message.reply_text(f"✅ Connected! Tables: {names}")
        await conn.close()
    except Exception as e:
        await update.message.reply_text(f"❌ Connection failed: {e}")

# === Bot Setup and Run ===
def main():
    logger.info("🔥 Running JobPal…")
    # Initialize DB schema
    asyncio.get_event_loop().run_until_complete(init_db_pg())

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # --- Conversation handlers (highest priority) ---
    app.add_handler(get_setgoal_handler(), group=0)
    app.add_handler(get_logjobs_handler(), group=0)
    app.add_handler(get_setname_handler(), group=0)

    # --- Core command handlers ---
    app.add_handler(MessageHandler(filters.Regex(r"^🏠 Home$"), start))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("reminders", toggle_reminders))
    app.add_handler(CallbackQueryHandler(toggle_reminders, pattern="^toggle_reminders$"))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("progress", progress_handler))
    app.add_handler(CommandHandler("testdb", testdb))

    # Schedule reminders
    register_reminders(app.job_queue)

    logger.info("🤖 JobPal is live! Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
