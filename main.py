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
    ContextTypes,
    MessageHandler,
    filters
)

from goal_command import (
    get_setgoal_handler,
    get_logjobs_handler,
    progress
)
from username_command import get_setname_handler
from leaderboard_command import leaderboard as leaderboard_actual
from config import TELEGRAM_BOT_TOKEN
from reminders import register_reminders
from db import get_pg_conn, init_db_pg

logger = logging.getLogger(__name__)

# === Keyboards ===
HOME_KB = ReplyKeyboardMarkup([['🏠 Home']], resize_keyboard=True)

# === Core Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... existing start handler code ...
    pass  # keep your existing logic here

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... existing help handler code ...
    pass

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... existing about handler code ...
    pass

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... existing settings handler code ...
    pass

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... existing leaderboard handler code ...
    pass

async def progress_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... existing progress handler code ...
    pass

async def toggle_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... existing toggle_reminders logic ...
    pass

async def testdb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... existing testdb logic ...
    pass

# === Bot Setup and Run ===
async def app_main():
    # 1) Initialize your DB schema
    await init_db_pg()

    # 2) Create the bot application
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # 3) Register handlers
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
    app.add_handler(get_setgoal_handler())
    app.add_handler(get_logjobs_handler())
    app.add_handler(get_setname_handler())
    app.add_handler(CallbackQueryHandler(start, pattern="^cancel$"))

    # 4) Schedule reminders
    register_reminders(app.job_queue)

    logger.info("🤖 JobPal is live! Press Ctrl+C to stop.")

    # 5) Start polling
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("🔥 Running JobPal…")
    asyncio.run(app_main())
