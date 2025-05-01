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
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "")  # e.g., "llama2"
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
    """
    Fetch a random cat-themed GIF URL from Giphy. Falls back to a static placeholder if API fails or key missing.
    """
    if not GIPHY_KEY:
        return "https://media.giphy.com/media/JIX9t2j0ZTN9S/giphy.gif"  # default cat gif
    params = {"api_key": GIPHY_KEY, "tag": "cat", "rating": "G"}
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
            {"role": "system", "content": "You are a supportive but selfish career consultant and elite headhunter."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 200
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

async def build_wrapup_message(
    top: tuple[int, int], least: tuple[int, int], chat_names: dict[int, str]
) -> str:
    top_id, top_count = top
    least_id, least_count = least
    top_name = chat_names.get(top_id, str(top_id))
    least_name = chat_names.get(least_id, str(least_id))

    prompt = (
        "Generate a 5-line closing message for tonight's 10 PM leaderboard as if you are the world's top career headhunter, "
        "driven by your client's success but competitive for results. Steps:\n"
        f"1) 'Ladies and gentlemen, time’s up!'\n"
        f"2) Praise {top_name} for achieving {top_count} applications.\n"
        f"3) Gently tease {least_name} for logging only {least_count} applications.\n"
        "4) Share one razor-sharp, insider tip only an elite career headhunter would give.\n"
        "5) Conclude with: 'Just 1% better every day!'."
    )

    # Attempt LLMs
    # 1) OpenRouter
    if OPENROUTER_KEY:
        try:
            logger.info("Trying OpenRouter for wrapup message...")
            llm_msg = await call_openrouter(prompt)
            gif_url = await get_cat_gif_url()
            return f"{llm_msg}\n![cat GIF]({gif_url})"
        except Exception as e:
            logger.error(f"OpenRouter error: {e}")
    # 2) Ollama
    if OLLAMA_MODEL:
        try:
            logger.info("Trying Ollama for wrapup message...")
            llm_msg = await call_ollama(prompt)
            gif_url = await get_cat_gif_url()
            return f"{llm_msg}\n![cat GIF]({gif_url})"
        except Exception as e:
            logger.error(f"Ollama error: {e}")

    # Static fallback
    logger.info("Using static fallback for wrapup message.")
    gif_url = await get_cat_gif_url()
    return (
        f"Ladies and gentlemen, time’s up!\n"
        f"{top_name} topped the board with {top_count} applications — exceptional drive.\n"
        f"And {least_name}, you logged just {least_count} today — we need sharper focus.\n"
        f"Tip for tomorrow: Identify the decision-maker at your top choice company and send a personalized, insight-driven note — stand out in their inbox.\n"
        f"Just 1% better every day!\n"
        f"![cat GIF]({gif_url})"
    )

async def send_wrapup(
    application: Application, chat_ids: list[int], chat_names: dict[int, str]
):
    top, least = await fetch_leaderboard_positions()
    text = await build_wrapup_message(top, least, chat_names)
    for chat_id in chat_ids:
        await application.bot.send_message(chat_id=chat_id, text=text)

# --- Scheduling ---
def schedule_daily_wrapup(
    app: Application, chat_ids: list[int], chat_names: dict[int, str]
):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        lambda: asyncio.create_task(send_wrapup(app, chat_ids, chat_names)),
        trigger="cron", hour=22, minute=0, timezone="America/Toronto"
    )
    scheduler.start()

# --- CLI for Testing ---
if __name__ == "__main__":
    sample_top = (12345, 7)
    sample_least = (67890, 2)
    sample_names = {12345: "Alice", 67890: "Bob"}
    message = asyncio.run(build_wrapup_message(sample_top, sample_least, sample_names))
    print(message)
