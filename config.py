import os

from dotenv import load_dotenv

load_dotenv()


def _env(name: str) -> str:
    # Чистим BOM (﻿) и пробелы — секреты, заведённые разными
    # инструментами, иногда приносят их с собой.
    return os.environ[name].lstrip("﻿").strip()


# Все значимые параметры берутся из окружения (локально — .env,
# в CI — Secrets), в коде ничего конкретного не хранится.
BOT_TOKEN: str = _env("TG_BOT_TOKEN")
CHANNEL: str = _env("SOURCE")
OWNER_CHAT_ID: int = int(_env("CHAT_ID"))
KEYWORDS: list[str] = [
    w.strip().lower() for w in _env("TERMS").split(",") if w.strip()
]

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "").strip()
