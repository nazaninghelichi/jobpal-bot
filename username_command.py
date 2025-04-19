from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, ConversationHandler, ContextTypes, filters
import sqlite3
import logging

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Conversation states
NAME = range(1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.warning("🚀 /start command HIT")  # Diagnostic log
    print("🚀 /start command HIT")  # Diagnostic print
    user_id = update.effective_user.id
    username = None
    conn = None
    try:
        conn = sqlite3.connect("jobpal.db")
        c = conn.cursor()
        c.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if row:
            username = row[0]
    except Exception as e:
        logger.error(f"Error checking existing user {user_id}: {e}")
    finally:
        if conn:
            conn.close()

    if username:
        logger.info(f"Existing user {user_id} ({username}) started the bot.")
        welcome_text = f"💪 Welcome back, {username}! Let's crush those job goals!"
        keyboard = [
            [ InlineKeyboardButton("✍️ Log Apps", callback_data="main_menu_logjobs"),
              InlineKeyboardButton("🎯 Set Goal", callback_data="main_menu_setgoal")],
            [ InlineKeyboardButton("📊 View Progress", callback_data="main_menu_progress"),
              InlineKeyboardButton("🏆 Today's Board", callback_data="main_menu_leaderboard_today")],
            [ InlineKeyboardButton("🤔 Ask Coach AI", callback_data="main_menu_ask"),
              InlineKeyboardButton("🤝 My Buddy", callback_data="main_menu_mybuddy")],
            [ InlineKeyboardButton("❓ Help/All Commands", callback_data="main_menu_help") ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
        return ConversationHandler.END
    else:
        logger.info(f"New user {user_id} started the bot.")
        await update.message.reply_text("👋 *Welcome to JobPal!*", parse_mode="Markdown")

        intro_msg = (
            "We built this app to help job seekers stay focused, motivated, and a little more joyful during the grind. 💼✨\n\n"
            "*Here's how it works:*\n"
            "• Set a daily goal for how many jobs you'll apply to.\n"
            "• After each app, fill in a square — it's oddly satisfying. ✅⬜️⬜️\n"
            "• Each night, we send out a leaderboard with fun surprises! 🎁\n\n"
            "⚡ First things first — pick a fun username!\n"
            "_(No real names — think JobWarrior, CareerHunter, TechTitan...)_"
        )
        await update.message.reply_text(intro_msg, parse_mode="Markdown")
        await update.message.reply_text("👉 What should I call you?")
        return NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.message.text.strip() if update.message and update.message.text else ""

    logger.debug(f"Received name attempt: '{name}' from user: {user_id}")

    if not name:
        await update.message.reply_text("❌ FOCUS! Give me a real name to work with!")
        return NAME

    conn = None
    try:
        conn = sqlite3.connect("jobpal.db")
        c = conn.cursor()
        c.execute("REPLACE INTO users (user_id, username) VALUES (?, ?)", (user_id, name))
        conn.commit()
        logger.info(f"Saved name '{name}' for new user {user_id}")
    except Exception as e:
        logger.error(f"Database error saving name for user {user_id}: {e}", exc_info=True)
        await update.message.reply_text("❌ Database error saving name. Try /start again later.")
        return ConversationHandler.END
    finally:
        if conn:
            conn.close()

    welcome_msg = f"""
🔥 WELCOME TO THE TEAM, {name}! 🔥

Your job search bootcamp starts NOW! Here's the basic plan:

🎯 Set Daily Goals (`/setgoal`)
✍️ Log Your Applications (`/logjobs`)
📊 Track Your Progress (`/progress`)
🤔 Ask the AI Coach (`/ask`)
🤝 Find an Accountability Buddy (`/mybuddy`)

Use the buttons below for quick access or type `/help` for all commands.
Let's get to work! 💪
"""
    keyboard = [
        [ InlineKeyboardButton("✍️ Log Apps", callback_data="main_menu_logjobs"),
          InlineKeyboardButton("🎯 Set Goal", callback_data="main_menu_setgoal")],
        [ InlineKeyboardButton("📊 View Progress", callback_data="main_menu_progress"),
          InlineKeyboardButton("🏆 Today's Board", callback_data="main_menu_leaderboard_today")],
        [ InlineKeyboardButton("🤔 Ask Coach AI", callback_data="main_menu_ask"),
          InlineKeyboardButton("🤝 My Buddy", callback_data="main_menu_mybuddy")],
        [ InlineKeyboardButton("❓ Help/All Commands", callback_data="main_menu_help") ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_msg, reply_markup=reply_markup)
    logger.debug(f"Welcome message with menu sent to new user {user_id}")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Mission aborted. Use /start when you're ready!")
    return ConversationHandler.END

def get_setname_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={ NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)] },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="setname_conversation",
        allow_reentry=True
    )
