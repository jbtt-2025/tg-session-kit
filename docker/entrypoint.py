import asyncio
import os
import re

from telethon import TelegramClient, events, errors
from telethon.sessions import StringSession

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION = os.environ["TG_SESSION"]

MODE = os.getenv("TG_MODE", "heartbeat")
INTERVAL_SECONDS = int(os.getenv("TG_INTERVAL_SECONDS", str(14 * 24 * 3600)))
JITTER_SECONDS = int(os.getenv("TG_JITTER_SECONDS", "300"))

CODE_RE = re.compile(r"\b(\d{5,6})\b")


async def heartbeat_loop(client: TelegramClient):
    while True:
        try:
            await client.start()
            await client.get_me()  # light, read-only heartbeat

        except errors.FloodWaitError as exc:
            await asyncio.sleep(int(exc.seconds) + 5)

        except Exception:
            await asyncio.sleep(60)

        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

        interval = INTERVAL_SECONDS
        if JITTER_SECONDS > 0:
            interval += int.from_bytes(os.urandom(2), "big") % JITTER_SECONDS
        await asyncio.sleep(interval)


async def pull_code_once(client: TelegramClient):
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


async def listen_code(client: TelegramClient):
    await client.start()

    @client.on(events.NewMessage(from_users=777000))
    async def handler(event):
        m = CODE_RE.search(event.raw_text or "")
        if m:
            print(m.group(1))
            await client.disconnect()

    print("waiting...")
    await client.run_until_disconnected()


async def main():
    client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)

    if MODE == "heartbeat":
        await heartbeat_loop(client)
    elif MODE == "pull_code_once":
        await pull_code_once(client)
    elif MODE == "listen_code":
        await listen_code(client)
    else:
        raise SystemExit(f"Unknown TG_MODE: {MODE}")


if __name__ == "__main__":
    asyncio.run(main())
