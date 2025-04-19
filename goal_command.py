import logging
import sqlite3
import asyncio
import random # <-- Import random for GIFs
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from ui_helpers import get_log_increment_keyboard, build_emoji_progress_bar

# Attempt to import token, handle if missing
try:
    from config import TELEGRAM_BOT_TOKEN
except ImportError:
    TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_PLACEHOLDER" # Replace or ensure config.py exists
    print("Warning: config.py not found or TELEGRAM_BOT_TOKEN not defined.")

# --- ADD IMPORT FOR BADGE CHECKING ---
try:
    from badge_utils import check_all_badges # Assuming this function exists here
except ImportError:
    check_all_badges = None # Define as None if module/function doesn't exist
    print("Warning: badge_utils.py or check_all_badges not found. Badge awarding disabled.")
# ------------------------------------

logger = logging.getLogger(__name__)

# --- Constants ---
# States for NEW LogJobs Conversation
LOG_SELECT_DAY, LOG_INCREMENTING, LOG_AWAIT_BATCH_NUMBER = range(3)
# States for Simplified SetGoal Conversation
AWAIT_GOAL_CHOICE, AWAIT_CUSTOM_NUMBER = range(3, 5) # Reuse range is okay if conversations don't overlap deeply

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAYS_MON_FRI = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

# --- Funny Cat GIFs ---
# Replace with REAL direct GIF URLs from Giphy, Tenor, etc. (ending in .gif ideally)
FUNNY_CAT_GIF_URLS = [
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNWlobW5jeDI3enNqZDYxZm4zZjcwN2R4dWt6Z3Z4cnRuczR0YmsydCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3o72F6XD7Z1lGl6M9O/giphy.gif", # Cat typing
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbDI0MmhvdmF5amRkZ3c3OWFkOHRnYjk0NTU5Z2ZiN3VqNnF6bmZiZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/WJjS2OPdz9MpG/giphy.gif", # Cat high five
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3J1bHdxanVrcW84YmRkOTNxYmMzZnZwZzVwZnlxbjVpcjlkMHVsYSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/l4FGpP4lxGGgK5CBW/giphy.gif", # Cat dancing
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExYThwMmxvNGZwZGo0bmw4bWR0cGN5Zm55eTk2eWhpY3ZzNnFwZjB2ZSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/u9kJh2j4z6Q1O/giphy.gif", # Cat DJ
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcnZ0dWFxMnJpNWR2aGsyNGZsa3pwd3h5M3lqNmV0NTVqZjZ6aTR0diZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/ICOgUNjpvO0PC/giphy.gif", # Cat working hard
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExZ2h5ZWV4dG03aW1uMjhsdWg0NnZ2Z2N1ZzNxZ2h2ZWVpdmM2aHZiMiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/11Dl LUXkaeQ6S4/giphy.gif", # Cat thumbs up
]


# ======================================================================
# Section 1: Database Initialization
# ======================================================================
def init_goal_and_progress_tables():
    """Initialize the user_goals and user_progress tables."""
    conn = None
    try:
        conn = sqlite3.connect("jobpal.db")
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS user_goals (
                user_id INTEGER,
                weekday TEXT,
                goal_count INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, weekday)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS user_progress (
                user_id INTEGER,
                date TEXT, /* YYYY-MM-DD */
                count_applied INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, date)
            )
        """)
        conn.commit()
        logger.info("Goal and Progress tables initialization check complete.")
    except Exception as e:
        logger.error(f"Failed to initialize goal/progress tables: {e}", exc_info=True)
        raise # Re-raise critical init errors
    finally:
        if conn:
            conn.close()


# ======================================================================
# Section 2: Database Interaction & Shared Utilities
# ======================================================================
def save_goal(user_id, day, count):
    """Saves or updates the goal for a specific user and weekday."""
    conn = None
    try:
        conn = sqlite3.connect("jobpal.db")
        c = conn.cursor()
        c.execute("REPLACE INTO user_goals (user_id, weekday, goal_count) VALUES (?, ?, ?)",
                  (user_id, day, count))
        conn.commit()
        # logger.info(f"Saved goal for user {user_id}, day {day}, count {count}") # Reduce log noise
    except Exception as e:
        logger.error(f"Failed to save goal for user {user_id}, day {day}: {e}")
        raise
    finally:
        if conn:
            conn.close()

def get_date_from_selection(selection):
    """Calculates the YYYY-MM-DD date string based on 'today', 'yesterday', or weekday name."""
    today = datetime.now().date()
    if selection.lower() == "today":
        return today.strftime("%Y-%m-%d")
    elif selection.lower() == "yesterday":
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")
    elif selection in WEEKDAYS:
        today_weekday_idx = today.weekday()
        target_weekday_idx = WEEKDAYS.index(selection)
        days_ago = (today_weekday_idx - target_weekday_idx + 7) % 7
        target_date = today - timedelta(days=days_ago)
        return target_date.strftime("%Y-%m-%d")
    else:
        logger.warning(f"Unexpected selection in get_date_from_selection: {selection}. Defaulting to today.")
        return today.strftime("%Y-%m-%d")

async def notify_buddy(bot: Bot, user_id: int, user_name: str, date_str: str, count: int):
    """Sends a notification to the user's buddy (if one exists)."""
    conn = None
    try:
        conn = sqlite3.connect("jobpal.db")
        c = conn.cursor()
        c.execute("SELECT buddy_chat_id FROM buddies WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if row and row[0]:
            buddy_chat_id = row[0]
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                formatted_date = date_obj.strftime("%b %d")
            except ValueError:
                 formatted_date = date_str

            text = f"👯 Your buddy {user_name} just logged {count} application(s) for {formatted_date}! Keep each other motivated! 💪"
            await bot.send_message(chat_id=buddy_chat_id, text=text)
            logger.info(f"Sent progress notification for user {user_id} to buddy {buddy_chat_id}")
    except Exception as e:
        logger.error(f"[Buddy Notify Error] User {user_id}: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()


def save_progress(user_id, date_str, count, context: ContextTypes.DEFAULT_TYPE):
    """Saves progress, triggers badge check & notifications, triggers buddy notification."""
    conn = None
    user_name = f"User {user_id}"
    saved_successfully = False
    newly_earned_badges = [] # Initialize list to store new badges

    try:
        conn = sqlite3.connect("jobpal.db"); c = conn.cursor()
        c.execute("REPLACE INTO user_progress (user_id, date, count_applied) VALUES (?, ?, ?)", (user_id, date_str, count))
        try: # Get username
             c.execute("SELECT username FROM users WHERE user_id = ?", (user_id,)); user_row = c.fetchone();
             if user_row: user_name = user_row[0]
        except Exception: pass
        conn.commit()
        saved_successfully = True
        logger.info(f"Saved progress for user {user_id}, date {date_str}, count {count}")

        # --- Trigger Buddy Notification ---
        if count > 0:
            context.application.create_task( notify_buddy(context.bot, user_id, user_name, date_str, count), update=None )

        # --- Trigger Badge Check ---
        if saved_successfully and check_all_badges: # Only check if save worked and function exists
            try:
                # Call the check function, it returns a list of newly awarded badge names
                newly_earned_badges = check_all_badges(user_id)
            except Exception as badge_e:
                logger.error(f"Error running check_all_badges for user {user_id}: {badge_e}", exc_info=True)
        elif not check_all_badges:
             logger.debug("Badge checking skipped (check_all_badges not available).")

    except Exception as e:
        logger.error(f"Failed to save progress for user {user_id}, date {date_str}: {e}")
        raise # Re-raise the exception so calling function knows it failed

    finally:
        if conn:
            conn.close()

    # --- Send Notifications for Newly Earned Badges (outside try/finally) ---
    if newly_earned_badges:
        # Define descriptions here or import from badge_command/ui_helpers
        badge_descriptions = {
            "🚀 First Log!": "Logged your very first application!",
            "💼 Momentum Maker": "Logged 20+ total applications.",
            "🔥 Lil' Flame": "Logged 3 days in a row. 🔥",
            "🐯 Tiger Week": "Hit all your weekday goals!",
            # Add ALL possible badges here
        }
        for badge_name in newly_earned_badges:
            desc = badge_descriptions.get(badge_name, "You're awesome!") # Default desc
            badge_text = (
                f"🏅 **New Badge Unlocked!**\n\n"
                f"{badge_name}\n_{desc}_\n\n"
                f"🎉 Keep going — more badges await!"
            )
            # Schedule notification task
            context.application.create_task(
                context.bot.send_message(chat_id=user_id, text=badge_text, parse_mode="Markdown")
            )
            logger.info(f"Scheduled notification for new badge '{badge_name}' for user {user_id}")

def save_goals_for_weekdays(user_id, goal_number):
    """Helper function to save the same goal for Monday to Friday."""
    logger.info(f"Saving goal '{goal_number}' for weekdays for user {user_id}.")
    for day in WEEKDAYS_MON_FRI:
        try:
            save_goal(user_id, day, goal_number)
        except Exception as e:
            logger.error(f"Failed to save goal for user {user_id}, day {day}: {e}")
    logger.info(f"Finished saving goals for weekdays for user {user_id}.")

def generate_squares_string(count: int, goal: int) -> str:
    """Generates the string of filled/empty squares."""
    if goal <= 0: # No goal set
        return f"Logged: {count} 👍"

    filled = min(count, goal)
    empty = max(0, goal - filled)
    over = max(0, count - goal)

    squares = "✅" * filled + "⬜️" * empty
    if over > 0:
        squares += f" +{over} ✨"
    return squares

async def send_random_cat_gif(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Sends a random cat GIF if the list is populated."""
    if FUNNY_CAT_GIF_URLS:
        try:
            gif_url = random.choice(FUNNY_CAT_GIF_URLS)
            await context.bot.send_animation(chat_id=chat_id, animation=gif_url)
        except Exception as gif_e:
            logger.warning(f"Failed to send cat GIF to {chat_id}: {gif_e}")


# ======================================================================
# Section 3: NEW "Fill the Squares" LogJobs Conversation Functions
# ======================================================================

async def logjobs_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the NEW /logjobs conversation (select day)."""
    keyboard = [
        [InlineKeyboardButton("Today", callback_data="logday_today")],
        [InlineKeyboardButton("Yesterday", callback_data="logday_yesterday")],
        *[[InlineKeyboardButton(day[:3], callback_data=f"logday_{day}")] for day in WEEKDAYS] # Use short day names?
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📅 Which day are you logging applications for?", reply_markup=reply_markup)
    return LOG_SELECT_DAY

async def logjobs_day_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles day selection, fetches goal/progress, shows initial squares."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    day_name = query.data.replace("logday_", "") # E.g., "today", "yesterday", "Monday"
    date_str = get_date_from_selection(day_name) # Get YYYY-MM-DD
    actual_weekday = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A") # Get full weekday name for goal lookup

    logger.info(f"User {user_id} selected {day_name} ({date_str}, {actual_weekday}) for logging.")

    # Fetch goal and current progress
    conn = None
    goal = 0
    current_count = 0
    try:
        conn = sqlite3.connect("jobpal.db"); c = conn.cursor()
        # Get goal for the actual weekday name
        c.execute("SELECT goal_count FROM user_goals WHERE user_id = ? AND weekday = ?", (user_id, actual_weekday))
        goal_row = c.fetchone();
        if goal_row: goal = goal_row[0]
        # Get current progress for the specific date
        c.execute("SELECT count_applied FROM user_progress WHERE user_id = ? AND date = ?", (user_id, date_str))
        progress_row = c.fetchone();
        if progress_row: current_count = progress_row[0]
    except Exception as e:
        logger.error(f"Error fetching initial log data for user {user_id}, date {date_str}: {e}")
        await query.edit_message_text("❌ Error fetching data. Try /logjobs again.")
        return ConversationHandler.END
    finally:
        if conn: conn.close()

    # Store data for later steps
    context.user_data["log_day_name"] = day_name # How user referred to it
    context.user_data["log_date_str"] = date_str
    context.user_data["log_weekday_name"] = actual_weekday
    context.user_data["log_goal"] = goal
    context.user_data["log_current_count"] = current_count

    # Generate initial message
    squares = generate_squares_string(current_count, goal)
    message_text = (
        f"Logging for: **{day_name.capitalize()}** ({date_str})\n"
        f"Goal: {goal if goal > 0 else 'Not set'}\n"
        f"Progress: {squares} ({current_count}/{goal if goal > 0 else '∞'})"
    )

    reply_markup = get_log_increment_keyboard()

    await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode="Markdown")
    return LOG_INCREMENTING

async def logjobs_increment_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles '+1' or '-1' button press."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    # Retrieve data from context
    day_name = context.user_data.get("log_day_name", "???")
    date_str = context.user_data.get("log_date_str")
    goal = context.user_data.get("log_goal", 0)
    current_count = context.user_data.get("log_current_count", 0)

    if not date_str: # Safety check
        logger.error(f"log_date_str missing during increment for user {user_id}")
        await query.edit_message_text("❌ Error: Date context lost. Try /logjobs again.")
        return ConversationHandler.END

    # Determine increment amount
    increment = 0
    if query.data == "log_inc_+1": increment = 1
    elif query.data == "log_inc_-1": increment = -1

    new_count = max(0, current_count + increment) # Don't go below zero

    # Save the new progress
    try:
        save_progress(user_id, date_str, new_count, context)
        context.user_data["log_current_count"] = new_count # Update context
        logger.info(f"User {user_id} updated log for {date_str} to {new_count}")
    except Exception as e:
        logger.error(f"Error saving incremented progress for user {user_id}, date {date_str}: {e}")
        # Don't edit message on error, just inform user?
        await context.bot.send_message(chat_id=user_id, text="❌ Error saving update. Please try again.")
        return LOG_INCREMENTING # Stay in state

    # Generate updated message
    squares = generate_squares_string(new_count, goal)
    message_text = (
        f"Logging for: **{day_name.capitalize()}** ({date_str})\n"
        f"Goal: {goal if goal > 0 else 'Not set'}\n"
        f"Progress: {squares} ({new_count}/{goal if goal > 0 else '∞'})"
    )
    # Reuse the same keyboard layout
    reply_markup = get_log_increment_keyboard()

    # Edit the message
    try:
        await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception as edit_e: # Handle potential errors like message not modified
        logger.warning(f"Failed to edit message after increment for user {user_id}: {edit_e}")
        # Might happen if count didn't change (e.g., tried to remove from 0)

    # Send GIF only if count increased
    if increment > 0:
        await send_random_cat_gif(context, user_id)

    return LOG_INCREMENTING # Stay in this state

async def logjobs_switch_to_batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Switches to asking the user to type the total number."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    day_name = context.user_data.get("log_day_name", "the selected day")
    date_str = context.user_data.get("log_date_str", "???")

    logger.info(f"User {user_id} switching to batch log for {date_str}")
    await query.edit_message_text(
        f"✍️ OK, how many applications did you complete **in total** for {day_name.capitalize()} ({date_str})?"
        "\n(Type the total number)"
    )
    return LOG_AWAIT_BATCH_NUMBER

async def logjobs_receive_batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the typed batch number, saves, confirms, sends GIF."""
    user_id = update.effective_user.id
    day_name = context.user_data.get("log_day_name", "the selected day")
    date_str = context.user_data.get("log_date_str")

    if not date_str:
        logger.error(f"log_date_str missing during batch receive for user {user_id}")
        await update.message.reply_text("❌ Error: Date context lost. Try /logjobs again.")
        return ConversationHandler.END

    try:
        count = int(update.message.text.strip())
        if count < 0:
            await update.message.reply_text("❌ Please enter 0 or a positive number.")
            return LOG_AWAIT_BATCH_NUMBER

        logger.info(f"User {user_id} entered batch count {count} for {date_str}")
        save_progress(user_id, date_str, count, context)

        feedback = f"✅ Roger that! **{count}** applications logged for {day_name.capitalize()} ({date_str}). Keep it up! 🔥"
        await update.message.reply_text(feedback, parse_mode="Markdown")

        # Send GIF!
        await send_random_cat_gif(context, user_id)

        # Clean up user_data
        context.user_data.pop("log_day_name", None)
        context.user_data.pop("log_date_str", None)
        context.user_data.pop("log_weekday_name", None)
        context.user_data.pop("log_goal", None)
        context.user_data.pop("log_current_count", None)

        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text("❌ That's not a valid number. Please type the total count.")
        return LOG_AWAIT_BATCH_NUMBER
    except Exception as e:
        logger.error(f"Error saving batch log for user {user_id}: {e}", exc_info=True)
        await update.message.reply_text("❌ Error saving batch log. Try again or use /cancel.")
        return LOG_AWAIT_BATCH_NUMBER # Or END?

async def logjobs_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the 'Done Logging' button press."""
    query = update.callback_query
    await query.answer("Log session complete!")
    user_id = update.effective_user.id
    day_name = context.user_data.get("log_day_name", "the day")
    current_count = context.user_data.get("log_current_count", 0)

    logger.info(f"User {user_id} finished logging for {day_name}. Final count: {current_count}")
    # Edit message one last time to remove buttons
    await query.edit_message_text(f"✅ Logging complete for {day_name.capitalize()}! Final count: {current_count}.")

    # Clean up user_data
    context.user_data.pop("log_day_name", None)
    context.user_data.pop("log_date_str", None)
    context.user_data.pop("log_weekday_name", None)
    context.user_data.pop("log_goal", None)
    context.user_data.pop("log_current_count", None)

    return ConversationHandler.END


# ======================================================================
# Section 4: Simplified SetGoal Functions
# ======================================================================
async def setgoal_start_simplified(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the simplified /setgoal conversation."""
    logger.info(f"User {update.effective_user.id} started simplified /setgoal.")
    keyboard = [
        [
            InlineKeyboardButton("5", callback_data="setgoal_5"), InlineKeyboardButton("10", callback_data="setgoal_10"),
            InlineKeyboardButton("15", callback_data="setgoal_15"), InlineKeyboardButton("20", callback_data="setgoal_20"),
        ],
        [
            InlineKeyboardButton("✍️ Custom", callback_data="setgoal_custom"),
            InlineKeyboardButton("🗑️ Remove Goals", callback_data="setgoal_0"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎯 Set your **daily** application goal for weekdays (Mon-Fri).",
        reply_markup=reply_markup
    )
    return AWAIT_GOAL_CHOICE # Note: Uses state constant defined for setgoal

async def handle_goal_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles button presses for preset goals, custom, or remove."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    callback_data = query.data
    logger.info(f"User {user_id} chose goal option: {callback_data}")

    if callback_data == "setgoal_custom":
        await query.edit_message_text("✍️ OK, please type your custom **daily** goal number (for Mon-Fri):")
        return AWAIT_CUSTOM_NUMBER # Note: Uses state constant defined for setgoal
    else:
        try:
            goal_number = int(callback_data.split('_')[1])
            if goal_number < 0: raise ValueError("Goal cannot be negative")

            save_goals_for_weekdays(user_id, goal_number)

            confirmation_text = ""
            if goal_number == 0: confirmation_text = "🗑️ Roger that! Weekday goals (Mon-Fri) removed."
            else: confirmation_text = (f"✅ Solid copy! Daily goal for weekdays (Mon-Fri) set to **{goal_number}**.\n\n"
                                      f"🔔 Daily reminders active (9am & 3pm). Let's get after it! 💪")

            await query.edit_message_text(confirmation_text, parse_mode="Markdown")
            return ConversationHandler.END
        except (IndexError, ValueError, TypeError) as e:
            logger.error(f"Error parsing goal callback '{callback_data}' for user {user_id}: {e}")
            await query.edit_message_text("❌ Error processing choice. Try /setgoal again.")
            return ConversationHandler.END
        except Exception as e:
            logger.error(f"Error saving preset goal for user {user_id}: {e}", exc_info=True)
            await query.edit_message_text("❌ Error saving. Please try again.")
            return ConversationHandler.END

async def receive_custom_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the custom goal number typed by the user."""
    user_id = update.effective_user.id
    try:
        goal_number = int(update.message.text.strip())
        if goal_number < 0:
            await update.message.reply_text("❌ Goals must be 0 or positive. Try again.")
            return AWAIT_CUSTOM_NUMBER

        logger.info(f"User {user_id} entered custom goal: {goal_number}")
        save_goals_for_weekdays(user_id, goal_number)

        confirmation_text = ""
        if goal_number == 0: confirmation_text = "🗑️ Understood. Weekday goals (Mon-Fri) removed."
        else: confirmation_text = (f"✅ Custom goal acknowledged! Daily goal (Mon-Fri) set to **{goal_number}**.\n\n"
                                   f"🔔 Reminders active (9am & 3pm). Crush it! 💪")

        await update.message.reply_text(confirmation_text, parse_mode="Markdown")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ That doesn't look like a valid number. Enter a whole number (e.g., 5, 10, 0).")
        return AWAIT_CUSTOM_NUMBER
    except Exception as e:
        logger.error(f"Error saving custom goal for user {user_id}: {e}", exc_info=True)
        await update.message.reply_text("❌ Error saving custom goal. Try /setgoal again.")
        return ConversationHandler.END


# ---------- Cancel Handlers ----------
async def cancel_setgoal_simplified(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels the simplified setgoal conversation."""
    logger.info(f"User {update.effective_user.id} cancelled simplified setgoal.")
    reply_text = "❌ Goal setting cancelled."
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(reply_text)
    elif update.message:
         await update.message.reply_text(reply_text)
    return ConversationHandler.END

async def cancel_shared(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generic cancel handler for logjobs and potentially others."""
    logger.info(f"User {update.effective_user.id} triggered shared cancel.")
    reply_text = "❌ Operation cancelled."
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(reply_text)
    elif update.message:
         await update.message.reply_text(reply_text)
    # Clear relevant user_data keys if any were set by the cancelled conversation
    context.user_data.pop("log_date_str", None)
    context.user_data.pop("log_day_name", None)
    return ConversationHandler.END


# ======================================================================
# Section 5: Regular Command Functions
# ======================================================================
async def progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays weekly progress against goals using emoji bars."""
    user_id = update.effective_user.id
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    this_week_dates = [start_of_week + timedelta(days=i) for i in range(7)]
    weekday_date_map = {d.strftime("%A"): d.strftime("%Y-%m-%d") for d in this_week_dates}

    conn = None; goals = {}; progress_data = {}
    try:
        conn = sqlite3.connect("jobpal.db"); c = conn.cursor()
        c.execute("SELECT weekday, goal_count FROM user_goals WHERE user_id = ?", (user_id,)); goals = dict(c.fetchall())
        for weekday, date_str in weekday_date_map.items():
            c.execute("SELECT count_applied FROM user_progress WHERE user_id = ? AND date = ?", (user_id, date_str)); row = c.fetchone(); progress_data[weekday] = row[0] if row else 0
    except Exception as e:
        logger.error(f"Error fetching progress data user {user_id}: {e}"); await update.message.reply_text("❌ Error retrieving progress."); return
    finally:
        if conn: conn.close()

    lines = []; total_goal = total_done = 0; has_goals = False

    for weekday in WEEKDAYS: # Iterate through all 7 days for display
        goal = goals.get(weekday, 0)
        done = progress_data.get(weekday, 0)

        if weekday in WEEKDAYS_MON_FRI: total_goal += goal;
        if goal > 0: has_goals = True
        total_done += done

        status = "⏳"; # Default status if no goal and no progress
        if goal > 0: status = "✅" if done >= goal else "❌"
        elif done > 0: status = "👍" # Logged without goal

        bar = build_emoji_progress_bar(done, goal)
        lines.append(f"{status} {weekday}: {bar}")

    percent = round((total_done / total_goal * 100), 1) if total_goal > 0 else 0
    reply = f"📊 **Weekly Progress** ({start_of_week.strftime('%b %d')} - {this_week_dates[-1].strftime('%b %d')})\n" + "\n".join(lines)

    if not has_goals and total_done == 0:
        reply += "\n\n🎯 Set a daily goal (/setgoal) & log apps (/logjobs)!"
    elif total_done == 0 and has_goals:
         reply += "\n\nNo apps logged yet! 😬 Let's go!"
    elif total_goal == 0 and total_done > 0:
         reply += f"\n\n**Logged:** {total_done} 👍 (No weekday goals)"
    else:
        reply += f"\n\n**Total (vs Mon-Fri Goal):** {total_done} / {total_goal} ({percent}%) 🎯"

    await update.message.reply_text(reply, parse_mode="Markdown")

async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays a summary (currently same as progress)."""
    await progress(update, context)

async def my_buddy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the user's current buddy."""
    user_id = update.effective_user.id
    conn = None
    buddy_info = "You don't have a buddy yet."
    try:
        conn = sqlite3.connect("jobpal.db")
        c = conn.cursor()
        # Assuming buddy_username column exists
        c.execute("SELECT buddy_chat_id, buddy_username FROM buddies WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if row:
            buddy_username = row[1]
            buddy_info = f"👯 Your current buddy is: **{buddy_username or 'Not Set'}**"
            buddy_info += "\nUse /invitebuddy [@username] to invite or change."
        else:
             buddy_info = "❗ You don't have a buddy yet. Use /invitebuddy [@username] to add one!"
    except Exception as e:
        logger.error(f"Error fetching buddy for user {user_id}: {e}")
        buddy_info = "❌ Error fetching buddy information."
    finally:
        if conn:
            conn.close()
    await update.message.reply_text(buddy_info, parse_mode="Markdown")


# ======================================================================
# Section 4: Handler Getter Functions (Defined LAST)
# ======================================================================

def get_logjobs_handler():
    """Gets the NEW ConversationHandler for the 'fill the squares' logjobs flow."""
    return ConversationHandler(
        entry_points=[CommandHandler("logjobs", logjobs_start)],
        states={
            LOG_SELECT_DAY: [
                CallbackQueryHandler(logjobs_day_selected, pattern='^logday_')
            ],
            LOG_INCREMENTING: [
                CallbackQueryHandler(logjobs_increment_count, pattern='^log_inc_'),
                CallbackQueryHandler(logjobs_switch_to_batch, pattern='^log_switch_batch$'),
                CallbackQueryHandler(logjobs_done, pattern='^log_done$'), # Handle "Done" button
            ],
            LOG_AWAIT_BATCH_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, logjobs_receive_batch)
            ],
        },
        fallbacks=[
            # Add a generic cancel command or specific ones
            CommandHandler("cancel", logjobs_done) # Treat /cancel same as Done? Or make specific cancel handler
        ],
        name="logjobs_squares_conversation",
        persistent=False
    )

def get_setgoal_handler():
    """Gets the ConversationHandler for the simplified setgoal flow."""
    return ConversationHandler(
        entry_points=[CommandHandler("setgoal", setgoal_start_simplified)],
        states={
            AWAIT_GOAL_CHOICE: [CallbackQueryHandler(handle_goal_choice, pattern='^setgoal_')],
            AWAIT_CUSTOM_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_goal)],
        },
        fallbacks=[CommandHandler("cancel", cancel_setgoal_simplified)],
        name="setgoal_simplified_conversation",
        persistent=False
    )
