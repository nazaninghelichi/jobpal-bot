import os, ssl, asyncio
import aiohttp
import certifi

# Try to import a key from your config module; otherwise use env var
try:
    from config import GIPHY_API_KEY  # noqa: F401
except ImportError:
    GIPHY_API_KEY = os.getenv("GIPHY_API_KEY", "")

if not GIPHY_API_KEY:
    print("⚠️  No GIPHY_API_KEY found. Set it in config.py or as an env var.")

# SSL context that trusts certifi’s CA bundle
ssl_context = ssl.create_default_context(cafile=certifi.where())

async def get_random_gif(tag: str = "cat", verify_ssl: bool = True) -> str:
    """Return a random GIF URL for the given tag (or an empty string on failure)."""
    url = (
        f"https://api.giphy.com/v1/gifs/random?api_key={GIPHY_API_KEY}" \
        f"&tag={tag}&rating=g"
    )

    connector = aiohttp.TCPConnector(ssl=ssl_context if verify_ssl else False)
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.get(url) as resp:
            data = await resp.json()
            # data["data"] can be a dict or list depending on success or error
            item = data["data"][0] if isinstance(data["data"], list) else data["data"]
            return (
                item.get("images", {})
                    .get("original", {})
                    .get("url", "")
            )

async def main():
    gif_url = await get_random_gif(tag="cat", verify_ssl=False)  # skip SSL for this test
    if gif_url:
        print("GIF URL:", gif_url)
        if "giphy.com" in gif_url:
            print("✅ Giphy API call succeeded!")
        else:
            print("⚠️  Response did not include a Giphy URL (check API key / quota)")
    else:
        print("⚠️  No GIF returned. Check API key, SSL, or rate limits.")

if __name__ == "__main__":
    asyncio.run(main())
