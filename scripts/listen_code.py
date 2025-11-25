import asyncio
import os
import re

from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION = os.environ["TG_SESSION"]

CODE_RE = re.compile(r"\b(\d{5,6})\b")


async def main():
    client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
    await client.start()

    @client.on(events.NewMessage(from_users=777000))
    async def handler(event):
        m = CODE_RE.search(event.raw_text or "")
        if m:
            print(m.group(1))
            await client.disconnect()

    print("waiting...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
