"""Scheduled task: fetch a source, match terms, dispatch new items."""

import re
import sys
import json
import asyncio
from pathlib import Path

import httpx

import scraper
from config import CHANNEL, KEYWORDS, BOT_TOKEN, OWNER_CHAT_ID

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

STATE = Path(__file__).parent / "state.json"


def load_last() -> int:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8")).get("last_post_id", 0)
    return 0


def save_last(post_id: int):
    STATE.write_text(
        json.dumps({"last_post_id": post_id}), encoding="utf-8"
    )


# Каждый term трактуется как ОСНОВА слова: матчим от границы слова и дальше
# любые буквы, чтобы ловить падежи (Тула → Туле, Тулу; Химки → Химках) и не
# цеплять слово изнутри (стул, артикул и т.п. не дадут ложное «тул»).
def matched_keywords(text: str) -> list[str]:
    found: list[str] = []
    for stem in KEYWORDS:
        for m in re.finditer(r"\b" + re.escape(stem) + r"\w*", text, re.IGNORECASE):
            word = m.group(0)
            if word not in found:
                found.append(word)
    return found


def format_message(post: scraper.Post, found: list[str]) -> str:
    body = post.text or "(пост без текста)"
    if len(body) > 3500:
        body = body[:3500] + "…"
    return (
        f"📍 <b>{', '.join(found)}</b>\n\n"
        f"{body}\n\n"
        f'<a href="{post.link}">Открыть пост</a>'
    )


async def send(client: httpx.AsyncClient, html: str):
    r = await client.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": OWNER_CHAT_ID,
            "text": html,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
    )
    r.raise_for_status()


async def main():
    last = load_last()
    posts = await scraper.fetch_posts(CHANNEL)
    if not posts:
        print("No posts fetched")
        return

    # First run: just record the current head, don't dispatch backlog.
    if last == 0:
        save_last(posts[-1].id)
        print(f"baseline {posts[-1].id}")
        return

    new_posts = [p for p in posts if p.id > last]
    if not new_posts:
        print("Nothing new")
        return

    async with httpx.AsyncClient(timeout=20) as client:
        for post in new_posts:
            found = matched_keywords(post.text)
            if found:
                await send(client, format_message(post, found))
                print(f"dispatched {post.id}")

    save_last(new_posts[-1].id)
    print(f"processed up to {new_posts[-1].id}")


if __name__ == "__main__":
    asyncio.run(main())
