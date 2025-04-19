import sqlite3
import logging
from datetime import date # Keep date if needed for fetching logic
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from badge_utils import get_badges, format_badge_summary

logger = logging.getLogger(__name__)

# Removed BADGE_DEFINITIONS and BADGES_BY_ID as the new format uses a dictionary directly

# --- Function to fetch earned badges for a user ---
# Needs to return a list of tuples: [(badge_name, awarded_date), ...]
def get_earned_badges(user_id: int) -> list[tuple[str, str]]:
    """
    Fetches earned badges and their award dates for a user.
    ** REPLACE THIS WITH YOUR ACTUAL LOGIC **
    This likely involves querying a 'user_badges' table like:
    SELECT badge_name, awarded_at FROM user_badges WHERE user_id = ? ORDER BY awarded_at
    Returns: List of tuples, e.g., [("🚀 First Log!", "2023-10-27"), ("🔥 Lil' Flame", "2023-10-29")]
    """
    logger.debug(f"Fetching badges for user {user_id} (using placeholder logic!)")
    # Placeholder Example - REPLACE THIS QUERY
    earned_badges_list = []
    conn = None
    try:
        conn = sqlite3.connect("jobpal.db")
        c = conn.cursor()
        # This is just an EXAMPLE structure, adapt to your actual table if you have one
        c.execute("""
            SELECT badge_name, date(awarded_at)
            FROM user_badges
            WHERE user_id = ?
            ORDER BY awarded_at ASC
            """, (user_id,))
        earned_badges_list = c.fetchall()
        if not earned_badges_list: # Add some example badges if table is empty/doesn't exist for testing
             # Remove this block once you have real badge awarding logic
             logger.warning(f"No badges found for {user_id} in DB, adding placeholder examples.")
             earned_badges_list = [("🚀 First Log!", "2023-10-26"), ("🔥 Lil' Flame", "2023-10-28")]

    except sqlite3.OperationalError:
         logger.warning("`user_badges` table might not exist. Using placeholder badge data.")
         # Example data if table doesn't exist - Remove for production
         earned_badges_list = [("🚀 First Log!", "2023-10-26"), ("🔥 Lil' Flame", "2023-10-28")]
    except Exception as e:
        logger.error(f"Error fetching badges for user {user_id}: {e}", exc_info=True)
    finally:
        if conn: conn.close()
    logger.debug(f"User {user_id} fetched badges: {earned_badges_list}")
    return earned_badges_list


# --- NEW Badge Formatting Function ---
def format_badge_summary(badges: list[tuple[str, str]]):
    """Formats the list of earned badges for display."""
    if not badges:
        return "🏅 *No badges earned yet.*\nKeep applying, tracking, and pushing forward!"

    # Descriptions keyed by the EXACT badge name stored in the database/returned list
    badge_descriptions = {
        "🚀 First Log!": "Logged your very first application!",
        "💼 Momentum Maker": "Logged 20+ total applications.", # Check calculation logic elsewhere
        "🔥 Lil' Flame": "Logged 3 days in a row. 🔥", # Check calculation logic elsewhere
        "🐯 Tiger Week": "Hit all your weekday goals!", # Check calculation logic elsewhere
        "🎯 Target Acquired": "Set your first daily goal",
        "⚔️ Application Warrior": "Logged 100+ total applications",
        # Add descriptions for ALL possible badges from your awarding logic
    }

    lines = ["🏅 **Your Badges Earned:**\n"]
    for badge_name, awarded_date in badges:
        # Use the emoji/name directly from the fetched data
        emoji_and_name = badge_name
        description = badge_descriptions.get(badge_name, "Keep up the great work!") # Default description
        # Format date if needed (assuming it's YYYY-MM-DD)
        try:
            formatted_date = date.fromisoformat(awarded_date).strftime("%b %d, %Y")
        except (ValueError, TypeError):
             formatted_date = awarded_date # Use as is if format is wrong

        lines.append(f"{emoji_and_name} — _{description}_\n🗓️ Awarded on {formatted_date}\n") # Add newline after date

    lines.append("\n💡 More badges coming soon. Keep it up!")
    return "\n".join(lines)


# --- Updated Badge Display Command ---
async def show_badges(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the user's earned badges using the new format."""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} requested badges.")

    # Get the list of earned badges: e.g., [("🚀 First Log!", "2023-10-27"), ...]
    earned_badges = get_earned_badges(user_id)

    # Format the message using the new helper
    message = format_badge_summary(earned_badges)

    await update.message.reply_text(message, parse_mode="Markdown")

# --- Handler Getter ---
def get_badge_handler():
    """Gets the CommandHandler for /badges."""
    return CommandHandler("badges", show_badges)

# Remember to create a user_badges table or implement the actual logic
# in get_earned_badges and the badge awarding function (check_all_badges)
def init_badges_table():
    conn = sqlite3.connect("jobpal.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_badges (
            user_id INTEGER,
            badge TEXT,
            date_awarded TEXT
        )
    """)
    conn.commit()
    conn.close()
