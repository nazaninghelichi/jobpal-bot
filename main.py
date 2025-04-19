import logging
import sqlite3
import asyncio
import requests
from datetime import date, datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler,
    CallbackQueryHandler, BaseHandler
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import TELEGRAM_BOT_TOKEN, OPENROUTER_API_KEY

# === Custom modules ===
from username_command import get_setname_handler
from goal_command import (
    get_setgoal_handler, get_logjobs_handler,
    progress, summary, my_buddy,
    init_goal_and_progress_tables, logjobs_start, setgoal_start_simplified,
)
from leaderboard_command import leaderboard, get_leaderboard_handler, get_todays_top_users

try:
    from ask_command import init_question_db, get_ask_handler, ask_start
except ImportError:
    init_question_db, get_ask_handler, ask_start = lambda: None, lambda: None, None

try:
    from buddy_command import init_buddy_system_table, get_invite_buddy_handler, my_buddy, invite_buddy_start, unbuddy
except ImportError:
    init_buddy_system_table, get_invite_buddy_handler, my_buddy, invite_buddy_start, unbuddy = [None] * 5

try:
    from reminder_command import init_reminders_table, get_reminder_handler
except ImportError:
    init_reminders_table, get_reminder_handler = lambda: None, lambda: None

try:
    from coach_command import get_coachsummary_handler
except ImportError:
    get_coachsummary_handler = lambda: []

try:
    from badge_command import show_badges, init_badges_table, get_badge_handler, get_mybadges_handler
except ImportError:
    show_badges, init_badges_table, get_badge_handler, get_mybadges_handler = None, None, None, None

# === Logging ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === DB Init ===
def init_users_table():
    conn = sqlite3.connect("jobpal.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            found_job BOOLEAN DEFAULT FALSE
        )
    """)
    try:
        c.execute("ALTER TABLE users ADD COLUMN found_job BOOLEAN DEFAULT FALSE")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            logger.error(f"ALTER error: {e}")
    conn.commit()
    conn.close()

# === Menu ===
MAIN_MENU_CALLBACK_PREFIX = "main_menu_"

def get_main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✍️ Log Apps", callback_data="main_menu_logjobs"),
         InlineKeyboardButton("🎯 Set Goal", callback_data="main_menu_setgoal")],
        [InlineKeyboardButton("📊 View Progress", callback_data="main_menu_progress"),
         InlineKeyboardButton("🏆 Today's Board", callback_data="main_menu_leaderboard_today")],
        [InlineKeyboardButton("🤔 Ask Coach AI", callback_data="main_menu_ask"),
         InlineKeyboardButton("🤝 My Buddy", callback_data="main_menu_mybuddy")],
        [InlineKeyboardButton("🏆 Badges", callback_data="main_menu_badges"),
         InlineKeyboardButton("❓ Help / All Commands", callback_data="main_menu_help")]
    ])

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    command = query.data.replace(MAIN_MENU_CALLBACK_PREFIX, "")
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except:
        pass

    if command == "logjobs": await logjobs_start(update, context)
    elif command == "setgoal": await setgoal_start_simplified(update, context)
    elif command == "progress": await progress(update, context)
    elif command == "ask" and ask_start: await ask_start(update, context)
    elif command == "mybuddy" and my_buddy: await my_buddy(update, context)
    elif command == "mybuddy_change" and invite_buddy_start: await invite_buddy_start(update, context)
    elif command == "mybuddy_unbuddy" and unbuddy: await unbuddy(update, context)
    elif command == "badges" and show_badges: await show_badges(update, context)
    elif command == "leaderboard_today":
        context.args = ["today"]
        await leaderboard(update, context)
    elif command == "help": await help_command(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    intro = "🔥 *JobPal: Main Menu* 🔥\n\nSelect an option below:"
    await update.message.reply_text(intro, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")

# === Poem Generator ===
async def generate_poem_via_llm(name: str, count: int) -> str:
    prompt = f"Write a short 4-line poetic tribute to a job seeker named {name} who applied to {count} jobs today. Make it uplifting but not cheesy."
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "system", "content": "You're a motivational poet."},
            {"role": "user", "content": prompt}
        ]
    }
    try:
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        return res.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"LLM error: {e}")
        return f"{name} logged {count} jobs. 👏 Keep going!"

# === Nightly Summary ===
async def send_daily_summary_poem(app: Application):
    bot = app.bot
    top_users = get_todays_top_users(limit=5)
    today = date.today().strftime("%A, %b %d")
    intro = f"🎤 *Daily Standings ({today})* 🎤\n\nLet’s see who showed up today! 🏆\n"
    medals = ["🥇", "🥈", "🥉", "🎖️", "🎖️"]
    lb = [f"{medals[i]} **{u[0]}** — {u[1]} apps" for i, u in enumerate(top_users)]

    dedication = poem = ""
    if top_users:
        name, count = top_users[0]
        dedication = f"\n\n📜 *Your Commendation, {name}* 📜"
        poem = await generate_poem_via_llm(name, count)

    message = intro + "\n".join(lb) + dedication + "\n\n" + poem

    conn = sqlite3.connect("jobpal.db")
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = [row[0] for row in c.fetchall()]
    conn.close()

    for uid in users:
        try:
            await bot.send_message(chat_id=uid, text=message, parse_mode="Markdown")
            await asyncio.sleep(0.15)
        except Exception as e:
            logger.warning(f"Failed to send to {uid}: {e}")

# === Scheduled Reminders ===
async def send_reminder_text(app: Application, message: str, tag: str):
    bot = app.bot
    today = datetime.now().strftime("%A")
    conn = sqlite3.connect("jobpal.db")
    c = conn.cursor()
    c.execute("SELECT DISTINCT user_id FROM user_goals WHERE weekday = ?", (today,))
    users = [row[0] for row in c.fetchall()]
    conn.close()

    for uid in users:
        try:
            await bot.send_message(chat_id=uid, text=message, parse_mode="Markdown")
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.warning(f"[{tag}] reminder failed for {uid}: {e}")

# === MAIN ===
def main():
    print("🔥 Running main()...")
    init_users_table()
    init_question_db()
    init_goal_and_progress_tables()
    if init_buddy_system_table: init_buddy_system_table()
    init_reminders_table()
    if callable(init_badges_table): init_badges_table()
    else: logger.warning("⚠️ init_badges_table is None — skipping badge setup.")

    async def post_init(app: Application):
        scheduler = AsyncIOScheduler(timezone="UTC")
        scheduler.add_job(send_reminder_text, 'cron', hour=9, minute=0, args=[app, "☀️ Morning check-in! /logjobs 💼", "9am"])
        scheduler.add_job(send_reminder_text, 'cron', hour=15, minute=0, args=[app, "⏳ Midday check-in. Keep going! /logjobs", "3pm"])
        scheduler.add_job(send_reminder_text, 'cron', hour=21, minute=0, args=[app, "🏁 Final call before leaderboard! /logjobs", "9pm"])
        scheduler.add_job(send_daily_summary_poem, 'cron', hour=22, minute=0, args=[app])
        scheduler.start()
        logger.info("✅ Scheduler started.")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    app.add_handler(get_setname_handler())
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(get_setgoal_handler())
    app.add_handler(get_logjobs_handler())
    app.add_handler(CommandHandler("progress", progress))
    app.add_handler(CommandHandler("summary", summary))
    if my_buddy: app.add_handler(CommandHandler("mybuddy", my_buddy))
    if callable(get_invite_buddy_handler): app.add_handler(get_invite_buddy_handler())
    reminder_handler = get_reminder_handler()
    if isinstance(reminder_handler, BaseHandler): app.add_handler(reminder_handler)
    if callable(get_badge_handler): app.add_handler(get_badge_handler())
    if callable(get_mybadges_handler): app.add_handler(get_mybadges_handler())
    if unbuddy: app.add_handler(CommandHandler("unbuddy", unbuddy))
    if callable(get_ask_handler): app.add_handler(get_ask_handler())
    for h in get_coachsummary_handler(): app.add_handler(h)
    if callable(get_leaderboard_handler): app.add_handler(get_leaderboard_handler())
    app.add_handler(CallbackQueryHandler(handle_main_menu, pattern="^main_menu_"))

    print("🤖 JobPal is now running... Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
