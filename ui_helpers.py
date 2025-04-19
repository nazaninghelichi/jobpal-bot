from telegram import InlineKeyboardButton, InlineKeyboardMarkup

MAIN_MENU_CALLBACK_PREFIX = "main_menu_"

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("✍️ Log Apps", callback_data=f"{MAIN_MENU_CALLBACK_PREFIX}logjobs"),
         InlineKeyboardButton("🎯 Set Goal", callback_data=f"{MAIN_MENU_CALLBACK_PREFIX}setgoal")],
        [InlineKeyboardButton("📊 View Progress", callback_data=f"{MAIN_MENU_CALLBACK_PREFIX}progress"),
         InlineKeyboardButton("🏆 Today's Board", callback_data=f"{MAIN_MENU_CALLBACK_PREFIX}leaderboard_today")],
        [InlineKeyboardButton("🤔 Ask Coach AI", callback_data=f"{MAIN_MENU_CALLBACK_PREFIX}ask"),
         InlineKeyboardButton("🤝 My Buddy", callback_data=f"{MAIN_MENU_CALLBACK_PREFIX}mybuddy")],
        [InlineKeyboardButton("🏆 Badges", callback_data=f"{MAIN_MENU_CALLBACK_PREFIX}badges"),
         InlineKeyboardButton("❓ Help/All Commands", callback_data=f"{MAIN_MENU_CALLBACK_PREFIX}help")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_log_increment_keyboard() -> InlineKeyboardMarkup:
    """Creates the keyboard used during the +/- logging process."""
    return InlineKeyboardMarkup([
        [ # Row 1: Increment/Decrement
            InlineKeyboardButton("➖ Remove 1", callback_data="log_inc_-1"),
            InlineKeyboardButton("➕ Add 1", callback_data="log_inc_+1")
        ],
        [ # Row 2: Switch to Batch Entry
            InlineKeyboardButton("✍️ Log Batch / Set Total", callback_data="log_switch_batch")
        ],
        [ # Row 3: Finish
            InlineKeyboardButton("✅ Done Logging", callback_data="log_done")
        ]
    ])

def build_emoji_progress_bar(done: int, goal: int) -> str:
    """Generates a progress bar string using filled/empty circle emojis."""
    if goal <= 0:
        # Handle case with no goal (or goal is 0)
        return f"{done} (no goal set)" # Return a specific string or just the count

    filled_emoji = '🔘' # Filled circle
    empty_emoji = '⚪' # Empty circle

    filled_count = min(done, goal)
    empty_count = max(0, goal - done)
    overflow_count = max(0, done - goal)

    # Build the bar string
    progress_bar = filled_emoji * filled_count + empty_emoji * empty_count

    # Add overflow indicator if needed
    overflow_text = f" +{overflow_count}" if overflow_count > 0 else ""

    # Combine bar with numeric representation
    return f"{progress_bar} ({done}/{goal}){overflow_text}"
