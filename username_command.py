from telegram import Update
from telegram.ext import (
    CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)
import sqlite3
import logging

# === Logging ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Conversation states ===
NAME = range(1)

# === /setname handler ===
async def start_setname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("🚀 /setname command received")
    user_id = update.effective_user.id
    current_name = None
    conn = sqlite3.connect("jobpal.db")
    try:
        c = conn.cursor()
        c.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if row:
            current_name = row[0]
    except Exception as e:
        logger.error(f"Error fetching name for {user_id}: {e}")
    finally:
        conn.close()

    if current_name:
        await update.message.reply_text(
            f"🔄 Your current display name is *{current_name}*\."
            "\nWhat would you like to change it to?", parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "✍️ What would you like to call yourself?", parse_mode="Markdown"
        )
    return NAME

# === Receive new username ===
async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.message.text.strip()

    logger.debug(f"Received name attempt: '{name}' from user {user_id}")

    if not name:
        await update.message.reply_text("❌ Please provide a valid name.")
        return NAME

    conn = sqlite3.connect("jobpal.db")
    try:
        c = conn.cursor()
        # Ensure row exists
        c.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
            (user_id, name)
        )
        # Update username
        c.execute("UPDATE users SET username = ? WHERE user_id = ?", (name, user_id))
        conn.commit()
        logger.info(f"✅ Saved name '{name}' for user {user_id}")
    except Exception as e:
        logger.error(f"Database error saving name: {e}")
        await update.message.reply_text(
            "❌ Something went wrong saving your name, please try again later."
        )
        return ConversationHandler.END
    finally:
        conn.close()

    await update.message.reply_text(
        f"🎉 Your display name has been updated to *{name}*!", parse_mode="Markdown"
    )
    return ConversationHandler.END

# === Cancel command ===
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Name change canceled.")
    return ConversationHandler.END

# === Handler export ===
def get_setname_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("setname", start_setname)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="setname_conversation",
        allow_reentry=True
    )
