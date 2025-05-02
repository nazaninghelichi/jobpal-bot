import os
import asyncio
from datetime import date
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application
from db import get_pg_conn
import httpx
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# --- Configuration ---
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
GIPHY_KEY = os.getenv("GIPHY_API_KEY", "")
GIPHY_ENDPOINT = "https://api.giphy.com/v1/gifs/random"

# --- Helper Functions ---
async def fetch_leaderboard_positions() -> tuple[tuple[int, int], tuple[int, int]]:
    conn = await get_pg_conn()
    today = date.today().isoformat()
    rows = await conn.fetch(
        "SELECT user_id, done FROM daily_track WHERE date = $1 ORDER BY done DESC",
        today
    )
    await conn.close()
    if not rows:
        return (None, 0), (None, 0)
    return (rows[0]['user_id'], rows[0]['done']), (rows[-1]['user_id'], rows[-1]['done'])

async def get_cat_gif_url() -> str:
    if not GIPHY_KEY:
        return "https://media.giphy.com/media/JIX9t2j0ZTN9S/giphy.gif"
    params = {"api_key": GIPHY_KEY, "tag": "space cat", "rating": "G"}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(GIPHY_ENDPOINT, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {}).get("images", {}).get("original", {}).get("url", "")
        except Exception as e:
            logger.error(f"Giphy API error: {e}")
            return "https://media.giphy.com/media/JIX9t2j0ZTN9S/giphy.gif"

async def call_openrouter(prompt: str) -> str:
    if not OPENROUTER_KEY:
        raise RuntimeError("No OpenRouter API key configured.")
    headers = {"Authorization": f"Bearer {OPENROUTER_KEY}"}
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "You are a cold, elite headhunter with a sharp tongue and high standards."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 300
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(OPENROUTER_ENDPOINT, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data['choices'][0]['message']['content'].strip()

async def call_ollama(prompt: str) -> str:
    async with httpx.AsyncClient() as client:
        payload = {"model": OLLAMA_MODEL, "prompt": prompt, "max_tokens": 200}
        url = f"{OLLAMA_URL}/completions"
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get('choices', [])[0].get('text', '').strip()

async def build_wrapup_message(top: tuple[int, int], least: tuple[int, int], chat_names: dict[int, str]) -> str:
    top_id, top_count = top
    least_id, least_count = least
    top_name = chat_names.get(top_id, str(top_id))
    least_name = chat_names.get(least_id, str(least_id))
    top_goal, least_goal = 10, 10

    prompt = f"""Generate a wrap-up in 6 lines:
1. Say 'Ladies and gentlemen,'
2. Celebrate top performer: {top_name} nailed {top_count}/{top_goal} applications. Add a sharp, witty compliment.
3. Roast lowest performer: {least_name} only managed {least_count}/{least_goal}. Add a clever jab that's motivating.
4–6. Based on these performance bars, give 3 different practical tips — no fluff:
[▉▉▉▉▁▁▁▁▁▁] 0–33%
[▉▉▉▉▉▉▉▁▁▁] 34–67%
[▉▉▉▉▉▉▉▉▉▁] 67–100%
7. Close with: 'One percent better tomorrow.'"""

    if OPENROUTER_KEY:
        try:
            logger.info("Trying OpenRouter for wrapup message...")
            llm_msg = await call_openrouter(prompt)
            gif_url = await get_cat_gif_url()
            return f"{llm_msg}\n![cat GIF]({gif_url})"
        except Exception as e:
            logger.error(f"OpenRouter error: {e}")

    if OLLAMA_MODEL:
        try:
            logger.info("Trying Ollama for wrapup message...")
            llm_msg = await call_ollama(prompt)
            gif_url = await get_cat_gif_url()
            return f"{llm_msg}\n![cat GIF]({gif_url})"
        except Exception as e:
            logger.error(f"Ollama error: {e}")

    logger.info("Using static fallback for wrapup message.")
    gif_url = await get_cat_gif_url()
    return (
        f"Ladies and gentlemen,\n"
        f"Top performer: {top_name} nailed {top_count}/{top_goal} applications (you’re single-handedly keeping recruiters in business).\n"
        f"Lowest performer: {least_name} only managed {least_count}/{least_goal} apps—my office plant has more follow-ups than you (and it’s photosynthesizing).\n\n"
        "Performance & tips:\n"
        "[▉▉▉▉▁▁▁▁▁▁] 0–33%: schedule two 30-min sprints at 9 AM and 1 PM—treat it like a pop quiz you can’t skip.\n"
        "[▉▉▉▉▉▉▉▁▁▁] 34–67%: tackle your toughest listing first thing in the morning—like ripping off a band-aid.\n"
        "[▉▉▉▉▉▉▉▉▉▁] 67–100%: send a laser-focused follow-up to two hiring managers—quality over quantity.\n\n"
        "One percent better tomorrow.\n"
        f"![cat GIF]({gif_url})"
    )

async def send_wrapup(application: Application, chat_ids: list[int], chat_names: dict[int, str]):
    top, least = await fetch_leaderboard_positions()
    text = await build_wrapup_message(top, least, chat_names)
    for chat_id in chat_ids:
        await application.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")

def schedule_daily_wrapup(app: Application, chat_ids: list[int], chat_names: dict[int, str]):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        lambda: asyncio.create_task(send_wrapup(app, chat_ids, chat_names)),
        trigger="cron", hour=22, minute=0, timezone="America/Toronto"
    )
    scheduler.start()

if __name__ == "__main__":
    sample_top = (12345, 9)
    sample_least = (67890, 2)
    sample_names = {12345: "Alice", 67890: "Bob"}
    message = asyncio.run(build_wrapup_message(sample_top, sample_least, sample_names))
    print(message)
