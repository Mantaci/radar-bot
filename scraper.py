"""Fetch and parse a public web preview page into ordered items."""

from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


@dataclass
class Post:
    id: int
    text: str
    link: str


async def fetch_posts(channel: str) -> list[Post]:
    url = f"https://t.me/s/{channel}"
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": UA}) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    posts: list[Post] = []

    for bubble in soup.select(".tgme_widget_message"):
        data_post = bubble.get("data-post")  # вид "radar_moscoww/12345"
        if not data_post or "/" not in data_post:
            continue
        try:
            post_id = int(data_post.split("/")[-1])
        except ValueError:
            continue

        text_el = bubble.select_one(".tgme_widget_message_text")
        text = text_el.get_text("\n", strip=True) if text_el else ""

        posts.append(
            Post(
                id=post_id,
                text=text,
                link=f"https://t.me/{data_post}",
            )
        )

    posts.sort(key=lambda p: p.id)
    return posts
