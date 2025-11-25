from telethon import TelegramClient
from telethon.sessions import StringSession


def main():
    api_id = int(input("api_id: ").strip())
    api_hash = input("api_hash: ").strip()

    client = TelegramClient(StringSession(), api_id, api_hash)
    client.start()  # prompts for phone, code, and 2FA password if enabled

    session_str = client.session.save()
    print("\n✅ StringSession (store safely):\n")
    print(session_str)

    client.disconnect()


if __name__ == "__main__":
    main()
