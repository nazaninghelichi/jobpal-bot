import sqlite3
import logging
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)

# =======================================
# Helper Functions for Badge Logic
# =======================================

def get_total_apps(user_id: int) -> int:
    """Gets the total number of applications logged by the user."""
    conn = None
    try:
        conn = sqlite3.connect("jobpal.db")
        c = conn.cursor()
        c.execute("SELECT SUM(count_applied) FROM user_progress WHERE user_id = ?", (user_id,))
        total = c.fetchone()
        conn.close()
        return total[0] if total and total[0] is not None else 0
    except Exception as e:
        logger.error(f"Error getting total apps for user {user_id}: {e}", exc_info=True)
        if conn: conn.close()
        return 0

def get_streak_days(user_id: int) -> int:
    """Calculates the current consecutive day streak of logging applications."""
    conn = None
    streak = 0
    try:
        conn = sqlite3.connect("jobpal.db")
        c = conn.cursor()
        # Check days backwards until a gap is found
        for i in range(90): # Check up to 90 days back reasonably
            check_date = (date.today() - timedelta(days=i)).strftime("%Y-%m-%d")
            c.execute("SELECT 1 FROM user_progress WHERE user_id = ? AND date = ? AND count_applied > 0 LIMIT 1", (user_id, check_date))
            if c.fetchone():
                streak += 1
            else:
                break # Gap found, streak ends
        conn.close()
    except Exception as e:
        logger.error(f"Error calculating streak for user {user_id}: {e}", exc_info=True)
        if conn: conn.close()
    return streak

def get_weekday_goals_met_this_week(user_id: int) -> int:
    """Calculates how many weekday goals were met in the current week."""
    # This is complex, placeholder implementation
    # Needs to fetch goals Mon-Fri and progress Mon-Fri for current week
    logger.warning(f"Weekly goal met check logic not fully implemented for user {user_id}")
    # Placeholder: return a sample number
    return 3 # Example: User met goal on 3 weekdays

# =======================================
# Condition Check Functions (Implement Real Logic!)
# =======================================
# These functions determine if a user QUALIFIES for a badge RIGHT NOW

def is_first_log(user_id: int) -> bool:
    return get_total_apps(user_id) > 0

def has_logged_20_total(user_id: int) -> bool:
    return get_total_apps(user_id) >= 20

def has_3_day_streak(user_id: int) -> bool:
    # Use the helper, check if it's 3 or more
    return get_streak_days(user_id) >= 3

def hit_weekly_goal(user_id: int) -> bool:
    # Needs real implementation based on comparing progress and goals for week
    # Example check using placeholder helper:
    return get_weekday_goals_met_this_week(user_id) >= 5

# =======================================
# Badge Definitions & Awarding Logic
# =======================================

# New structure including check and progress functions
BADGE_DEFINITIONS = [
    {
        "name": "🚀 First Log!",
        "desc": "Logged your very first application!",
        "check": is_first_log, # Function reference
        "progress": lambda user_id: "✅ Earned!" if is_first_log(user_id) else "0 / 1 Log" # Lambda function
    },
    {
        "name": "💼 Momentum Maker",
        "desc": "Logged 20+ total applications.",
        "check": has_logged_20_total,
        "progress": lambda user_id: f"{get_total_apps(user_id)} / 20 Apps"
    },
    {
        "name": "🔥 Lil' Flame",
        "desc": "Logged 3 days in a row. 🔥",
        "check": has_3_day_streak,
        "progress": lambda user_id: f"{get_streak_days(user_id)} / 3 Day Streak"
    },
    {
        "name": "🐯 Tiger Week",
        "desc": "Hit all your weekday goals!",
        "check": hit_weekly_goal,
        "progress": lambda user_id: f"{get_weekday_goals_met_this_week(user_id)} / 5 Weekdays Goal Met" # Use helper
    },
    # Add more badges following this structure
]

def award_badge_if_needed(user_id: int, badge_name: str, trigger_check_func) -> str | None:
    """Awards badge if condition met and not already awarded. Returns badge name if awarded."""
    # (Keep the implementation provided in the previous step, which returns badge_name or None)
    try:
        should_award = trigger_check_func()
        if not should_award: return None
    except Exception as e: logger.error(f"Err check badge '{badge_name}' user {user_id}: {e}"); return None
    conn = None
    try:
        conn = sqlite3.connect("jobpal.db"); c = conn.cursor()
        # Ensure user_badges table exists
        c.execute("""CREATE TABLE IF NOT EXISTS user_badges (
                        user_id INTEGER, badge_name TEXT, awarded_at TIMESTAMP,
                        PRIMARY KEY (user_id, badge_name))""")
        c.execute("SELECT 1 FROM user_badges WHERE user_id = ? AND badge_name = ?", (user_id, badge_name))
        if c.fetchone(): return None # Already awarded
        award_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO user_badges (user_id, badge_name, awarded_at) VALUES (?, ?, ?)", (user_id, badge_name, award_date))
        conn.commit(); logger.info(f"AWARDED badge '{badge_name}' to user {user_id}"); return badge_name
    except Exception as e: logger.error(f"DB err award badge '{badge_name}' user {user_id}: {e}"); return None
    finally:
        if conn: conn.close()


def check_all_badges(user_id: int) -> list[str]:
    """Checks all badge conditions, awards new ones, returns list of NEWLY awarded."""
    logger.debug(f"Running check_all_badges for user {user_id}")
    newly_awarded_badges = []
    # Use the check function defined within BADGE_DEFINITIONS
    for badge_def in BADGE_DEFINITIONS:
        badge_name = badge_def["name"]
        condition_func = badge_def["check"] # Get the function reference
        awarded_badge = award_badge_if_needed(user_id, badge_name, lambda: condition_func(user_id)) # Pass lambda calling the func
        if awarded_badge:
            newly_awarded_badges.append(awarded_badge)
    if newly_awarded_badges: logger.info(f"User {user_id} earned new badges: {newly_awarded_badges}")
    return newly_awarded_badges


# =======================================
# Badge Summary Logic for /mybadges
# =======================================

def get_badges(user_id: int) -> list[tuple[str, str]]:
    """Fetches all earned badges and formatted award dates for a user."""
    conn = None; earned_badges_list = []
    try:
        conn = sqlite3.connect("jobpal.db"); c = conn.cursor()
        # Ensure user_badges table exists before querying
        c.execute("""CREATE TABLE IF NOT EXISTS user_badges (
                        user_id INTEGER, badge_name TEXT, awarded_at TIMESTAMP,
                        PRIMARY KEY (user_id, badge_name))""")
        c.execute("SELECT badge_name, awarded_at FROM user_badges WHERE user_id = ? ORDER BY awarded_at ASC", (user_id,))
        raw_badges = c.fetchall()
        for name, awarded_at_ts in raw_badges:
            try: # Format the date nicely
                dt_obj = datetime.strptime(awarded_at_ts, "%Y-%m-%d %H:%M:%S")
                formatted_date = dt_obj.strftime("%b %d, %Y")
            except (TypeError, ValueError): formatted_date = "Unknown Date"
            earned_badges_list.append((name, formatted_date))
    except Exception as e: logger.error(f"Error fetching earned badges for user {user_id}: {e}")
    finally:
        if conn: conn.close()
    return earned_badges_list

def get_all_badges_summary(user_id: int) -> str:
    """Generates the formatted string showing earned & locked badges with progress."""
    earned_dict = dict(get_badges(user_id))  # Create dict for quick lookup: {badge_name: date_str}
    lines = ["🏅 **Your Badge Progress:**\n"]

    for badge in BADGE_DEFINITIONS:
        name = badge["name"]
        desc = badge["desc"]
        progress_func = badge["progress"] # Get the lambda function

        if name in earned_dict:
            earned_date = earned_dict[name]
            # Show Earned Badge
            lines.append(f"✅ {name} — _{desc}_\n🗓️ Earned on {earned_date}\n")
        else:
            # Show Locked Badge with Progress
            try:
                # Call the lambda function to get progress string
                progress_str = progress_func(user_id)
            except Exception as e:
                logger.error(f"Error getting progress for badge '{name}', user {user_id}: {e}")
                progress_str = "Error calculating"
            lines.append(f"🔒 {name} — _{desc}_\n📈 Progress: {progress_str}\n")

    if not earned_dict and len(BADGE_DEFINITIONS) > 0: # If no badges earned yet
        lines.append("\nKeep working towards your first badge!")
    elif len(earned_dict) == len(BADGE_DEFINITIONS): # All badges earned
         lines.append("\n🏆 You've collected all the badges! Amazing!")

    return "\n".join(lines)
