import asyncio
import os
import re

from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION = os.environ["TG_SESSION"]

CODE_RE = re.compile(r"\b(\d{5,6})\b")


async def main():
    client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
    await client.start()

    async for msg in client.iter_messages(777000, limit=5):
        text = msg.raw_text or ""
        m = CODE_RE.search(text)
        if m:
            print(m.group(1))
            await client.disconnect()
            return

    print("NO_CODE_FOUND")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
