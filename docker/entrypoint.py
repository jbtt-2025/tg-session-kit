import asyncio
import logging
import os
import re
from urllib.parse import quote_plus
from urllib.request import urlopen

from telethon import TelegramClient, events, errors
from telethon.sessions import StringSession

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION = os.environ["TG_SESSION"]

MODE = os.getenv("TG_MODE", "heartbeat")
INTERVAL_SECONDS = int(os.getenv("TG_INTERVAL_SECONDS", str(24 * 3600)))
JITTER_SECONDS = int(os.getenv("TG_JITTER_SECONDS", "300"))

NOTIFY_BOT_TOKEN = os.getenv("TG_NOTIFY_BOT_TOKEN")
NOTIFY_CHAT_ID = os.getenv("TG_NOTIFY_CHAT_ID")

# --- 新增：健壮性参数 ---
HEARTBEAT_TIMEOUT = int(os.getenv("TG_HEARTBEAT_TIMEOUT", "30"))  # 单次start/get_me超时
DISCONNECT_TIMEOUT = int(os.getenv("TG_DISCONNECT_TIMEOUT", "10"))
MAX_CONSECUTIVE_FAILS = int(os.getenv("TG_MAX_CONSECUTIVE_FAILS", "5"))  # 连续失败熔断
IGNORE_STORM_HITS_TO_EXIT = int(os.getenv("TG_IGNORE_STORM_HITS_TO_EXIT", "2"))  # 命中几次日志就退出
BASE_BACKOFF = int(os.getenv("TG_BASE_BACKOFF", "10"))  # 失败后退避起始秒数
MAX_BACKOFF = int(os.getenv("TG_MAX_BACKOFF", "300"))   # 失败后退避上限

CODE_RE = re.compile(r"\b(\d{5,6})\b")

# --- Telethon 日志熔断（关键！很多“死循环刷屏”是日志而不是异常） ---
_ignored_storm_hits = 0


class TelethonFuseHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        global _ignored_storm_hits
        msg = record.getMessage()
        if ("very new message" in msg) or ("Too many messages had to be ignored" in msg):
            _ignored_storm_hits += 1
            if _ignored_storm_hits >= IGNORE_STORM_HITS_TO_EXIT:
                raise SystemExit("Telethon ignored-too-many-updates (clock drift likely). Exiting for restart.")


def install_telethon_fuse():
    logger = logging.getLogger("telethon")
    logger.setLevel(logging.INFO)
    logger.addHandler(TelethonFuseHandler())


def _notify_enabled() -> bool:
    return bool(NOTIFY_BOT_TOKEN and NOTIFY_CHAT_ID)


async def send_notification(status: str, reason: str):
    if not _notify_enabled():
        return
    text = f"{NOTIFY_CHAT_ID} 保活{status} {reason}"
    url = (
        f"https://api.telegram.org/bot{NOTIFY_BOT_TOKEN}/sendMessage"
        f"?chat_id={NOTIFY_CHAT_ID}&text={quote_plus(text)}"
    )
    try:
        await asyncio.to_thread(urlopen, url)
    except Exception:
        pass


def _new_client() -> TelegramClient:
    # 每轮新建 client，避免状态脏
    return TelegramClient(StringSession(SESSION), API_ID, API_HASH)


async def _safe_disconnect(client: TelegramClient):
    try:
        await asyncio.wait_for(client.disconnect(), timeout=DISCONNECT_TIMEOUT)
    except Exception:
        pass


async def _one_heartbeat():
    client = _new_client()
    try:
        # start/get_me 可能会卡：统一加超时
        await asyncio.wait_for(client.start(), timeout=HEARTBEAT_TIMEOUT)
        await asyncio.wait_for(client.get_me(), timeout=HEARTBEAT_TIMEOUT)
    finally:
        await _safe_disconnect(client)


async def heartbeat_loop():
    consecutive_fails = 0
    backoff = BASE_BACKOFF

    while True:
        try:
            await _one_heartbeat()
            consecutive_fails = 0
            backoff = BASE_BACKOFF
            await send_notification("成功", "ok")

        except errors.FloodWaitError as exc:
            consecutive_fails += 1
            await send_notification("失败", f"floodwait {int(exc.seconds)}s")
            await asyncio.sleep(int(exc.seconds) + 5)

        except (asyncio.TimeoutError,) as exc:
            consecutive_fails += 1
            await send_notification("失败", f"timeout>{HEARTBEAT_TIMEOUT}s")

        except (errors.SecurityError,) as exc:
            # 有些安全类问题会抛异常；更多时候会走日志熔断
            consecutive_fails += 1
            await send_notification("失败", f"security_error: {exc}")

        except SystemExit:
            # TelethonFuseHandler 会 raise SystemExit
            await send_notification("失败", "ignored-too-many-updates -> exit for restart")
            raise

        except Exception as exc:
            consecutive_fails += 1
            await send_notification("失败", f"error: {exc}")

        if consecutive_fails >= MAX_CONSECUTIVE_FAILS:
            await send_notification("失败", f"too many fails({consecutive_fails}) -> exit for restart")
            raise SystemExit(2)

        # 失败退避（避免疯狂重连/刷屏）
        if consecutive_fails > 0:
            await asyncio.sleep(backoff)
            backoff = min(int(backoff * 2), MAX_BACKOFF)

        interval = INTERVAL_SECONDS
        if JITTER_SECONDS > 0:
            interval += int.from_bytes(os.urandom(2), "big") % JITTER_SECONDS
        await asyncio.sleep(interval)


async def pull_code_once():
    client = _new_client()
    try:
        await asyncio.wait_for(client.start(), timeout=HEARTBEAT_TIMEOUT)
        async for msg in client.iter_messages(777000, limit=5):
            text = msg.raw_text or ""
            m = CODE_RE.search(text)
            if m:
                print(m.group(1))
                return
        print("NO_CODE_FOUND")
    finally:
        await _safe_disconnect(client)


async def listen_code():
    client = _new_client()
    await asyncio.wait_for(client.start(), timeout=HEARTBEAT_TIMEOUT)

    @client.on(events.NewMessage(from_users=777000))
    async def handler(event):
        m = CODE_RE.search(event.raw_text or "")
        if m:
            print(m.group(1))
            await _safe_disconnect(client)

    print("waiting...")
    await client.run_until_disconnected()


async def main():
    install_telethon_fuse()

    if MODE == "heartbeat":
        await heartbeat_loop()
    elif MODE == "pull_code_once":
        await pull_code_once()
    elif MODE == "listen_code":
        await listen_code()
    else:
        raise SystemExit(f"Unknown TG_MODE: {MODE}")


if __name__ == "__main__":
    asyncio.run(main())
