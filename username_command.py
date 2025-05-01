import logging
from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
from db import get_pg_conn  # your asyncpg connector

logger = logging.getLogger(__name__)

# single state
NAME = 1

async def start_setname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("🚀 /setname command received")
    user_id = update.effective_user.id

    conn = await get_pg_conn()
    try:
        row = await conn.fetchrow(
            "SELECT username FROM users WHERE user_id = $1",
            user_id
        )
        current_name = row["username"] if row and row["username"] else None
    finally:
        await conn.close()

    if current_name:
        await update.message.reply_text(
            f"🔄 Your current display name is *{current_name}*.\n"
            "What would you like to change it to?",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "✍️ What would you like to call yourself?",
            parse_mode="Markdown"
        )
    return NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("❌ Please provide a valid name.")
        return NAME

    conn = await get_pg_conn()
    try:
        # upsert into your Postgres users table
        await conn.execute(
            """
            INSERT INTO users (user_id, username, first_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id)
              DO UPDATE SET username = EXCLUDED.username
            """,
            user_id, name, update.effective_user.first_name or ""
        )
    except Exception as e:
        logger.error(f"Database error saving name: {e}")
        await update.message.reply_text(
            "❌ Something went wrong saving your name, please try again later."
        )
        return ConversationHandler.END
    finally:
        await conn.close()

    await update.message.reply_text(
        f"🎉 Your display name has been updated to *{name}*!",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Name change canceled.")
    return ConversationHandler.END

def get_setname_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("setname", start_setname)],
        states={
            NAME: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), receive_name)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
