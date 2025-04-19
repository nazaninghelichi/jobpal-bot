# clear_webhook.py

import asyncio
from telegram import Bot
from config import TELEGRAM_BOT_TOKEN

async def clear():
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Webhook cleared.")

asyncio.run(clear())
