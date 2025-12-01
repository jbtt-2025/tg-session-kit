# tg-telethon-session-kit

A small, practical Telethon-based kit to:

1) **Login once locally** and generate a **StringSession** (session token)
2) Run a **headless Docker heartbeat** on a VPS to keep that session alive
3) **Pull / listen for login codes** from `777000` using the live session

> **Threat model note**: This kit assumes you *do not encrypt* the session string. Treat it like a root password: anyone who gets it owns the account. 2FA does **not** protect you if the session leaks.

---

## Project structure

```
tg-telethon-session-kit/
  README.md
  requirements.txt
  .env.example
  scripts/
    login_local.py
    pull_code_once.py
    listen_code.py
  docker/
    Dockerfile
    entrypoint.py
```

---

## requirements.txt

```txt
telethon==1.42.0
```

---

## .env.example

```bash
# Required
TG_API_ID=123456
TG_API_HASH=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TG_SESSION=PASTE_STRING_SESSION_HERE

# Optional heartbeat settings
TG_MODE=heartbeat        # heartbeat | pull_code_once | listen_code
TG_INTERVAL_SECONDS=1209600  # 14 days default
TG_JITTER_SECONDS=300        # 5 min jitter default
```

---

## scripts/login_local.py

> Run this **locally on a trusted machine**. It is interactive.
> It prints your StringSession.

```python
from telethon import TelegramClient
from telethon.sessions import StringSession

api_id = int(input("api_id: ").strip())
api_hash = input("api_hash: ").strip()

client = TelegramClient(StringSession(), api_id, api_hash)
client.start()  # prompts for phone, code, and 2FA password if enabled

session_str = client.session.save()
print("\n✅ StringSession (store safely):\n")
print(session_str)

client.disconnect()
```

Usage:

```bash
python scripts/login_local.py
```

---

## scripts/pull_code_once.py

> After you trigger login on a new device, run this to pull the latest code from `777000`.

```python
import re, os, asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION  = os.environ["TG_SESSION"]

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

asyncio.run(main())
```

Usage:

```bash
export TG_API_ID=... TG_API_HASH=... TG_SESSION=...
python scripts/pull_code_once.py
```

---

## scripts/listen_code.py

> Alternative: wait for the next incoming login code.

```python
import re, os, asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION  = os.environ["TG_SESSION"]

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

asyncio.run(main())
```

Usage:

```bash
export TG_API_ID=... TG_API_HASH=... TG_SESSION=...
python scripts/listen_code.py
```

---

## docker/Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY docker/entrypoint.py ./entrypoint.py

CMD ["python", "entrypoint.py"]
```

---

## docker/entrypoint.py

> One container, three modes controlled by `TG_MODE`.
> Default mode: `heartbeat`.

```python
import os, re, asyncio
from telethon import TelegramClient, events, errors
from telethon.sessions import StringSession

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION  = os.environ["TG_SESSION"]

MODE = os.getenv("TG_MODE", "heartbeat")
INTERVAL_SECONDS = int(os.getenv("TG_INTERVAL_SECONDS", str(14*24*3600)))
JITTER_SECONDS = int(os.getenv("TG_JITTER_SECONDS", "300"))

CODE_RE = re.compile(r"\b(\d{5,6})\b")

async def heartbeat_loop(client: TelegramClient):
    while True:
        try:
            await client.start()
            await client.get_me()  # light, read-only heartbeat

        except errors.FloodWaitError as e:
            await asyncio.sleep(int(e.seconds) + 5)

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
```

---

## Build & run (VPS)

```bash
# build
docker build -t tg-session-kit:latest .

# heartbeat (default)
docker run -d --name tg-heartbeat \
  --restart unless-stopped \
  -e TG_API_ID=123456 \
  -e TG_API_HASH="..." \
  -e TG_SESSION="..." \
  -e TG_MODE=heartbeat \
  -e TG_INTERVAL_SECONDS=$((14*24*3600)) \
  -e TG_JITTER_SECONDS=300 \
  tg-session-kit:latest

# pull latest login code once (run-and-exit)
docker run --rm \
  -e TG_API_ID=123456 \
  -e TG_API_HASH="..." \
  -e TG_SESSION="..." \
  -e TG_MODE=pull_code_once \
  tg-session-kit:latest

# listen for next login code (run until it prints a code)
docker run --rm \
  -e TG_API_ID=123456 \
  -e TG_API_HASH="..." \
  -e TG_SESSION="..." \
  -e TG_MODE=listen_code \
  tg-session-kit:latest
```

---

## Operational rules (don’t skip)

1. **One session string = one machine at a time.** Never run the same `TG_SESSION` concurrently on two hosts.
2. Use a **stable VPS IP**.
3. Heartbeat should be **days/weeks** interval, not minutes/hours.
4. Treat `TG_SESSION` as a root key. Keep it out of logs, repos, screenshots.

---

If you want, I can add a `systemd timer` version (container exits each run) to make it even more “cron-like”.
