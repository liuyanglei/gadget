"""Collect public finance RSS feeds and build data/news.json."""

from __future__ import annotations

import hashlib
import html
import json
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import feedparser
import requests

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "news.json"
MAX_ARTICLES = 120
PER_SOURCE_LIMIT = 35
TIMEOUT_SECONDS = 20

# Google News exposes standards-compliant public RSS results for sites that no
# longer maintain a stable native feed. CNBC keeps its own public RSS feed.
FEEDS = [
    {
        "source": "新浪财经",
        "url": "https://news.google.com/rss/search?q=site%3Afinance.sina.com.cn%20%E8%B4%A2%E7%BB%8F&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
    },
    {
        "source": "东方财富",
        "url": "https://news.google.com/rss/search?q=site%3Aeastmoney.com%20%E8%B4%A2%E7%BB%8F&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
    },
    {
        "source": "Reuters",
        "url": "https://news.google.com/rss/search?q=site%3Areuters.com%20business%20markets&hl=en-US&gl=US&ceid=US:en",
    },
    {
        "source": "CNBC",
        "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    },
]

CATEGORY_KEYWORDS = {
    "A股": ("a股", "沪指", "深成指", "创业板", "科创板", "上证", "深证", "沪深", "a-share"),
    "港股": ("港股", "恒生", "恒指", "h股", "hang seng", "hong kong"),
    "美股": ("美股", "纳斯达克", "道琼斯", "标普", "华尔街", "nasdaq", "dow", "s&p", "wall street"),
    "黄金": ("黄金", "金价", "贵金属", "gold", "bullion"),
    "原油": ("原油", "油价", "石油", "oil", "crude", "opec"),
    "基金": ("基金", "etf", "公募", "私募", "fund"),
}

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def clean_text(value: Any, limit: int = 260) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else f"{text[: limit - 1].rstrip()}…"


def parse_datetime(entry: Any) -> datetime:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        value = entry.get(key)
        if value:
            return datetime(*value[:6], tzinfo=timezone.utc)
    for key in ("published", "updated", "created"):
        value = entry.get(key)
        if not value:
            continue
        try:
            parsed = parsedate_to_datetime(value)
            return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError):
            continue
    return datetime.now(timezone.utc)


def classify(title: str, summary: str) -> str:
    haystack = f"{title} {summary}".lower()
    scores = {
        category: sum(1 for keyword in keywords if keyword in haystack)
        for category, keywords in CATEGORY_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] else "宏观经济"


def fetch_feed(feed: dict[str, str]) -> list[dict[str, str]]:
    logging.info("Fetching %s", feed["source"])
    response = requests.get(
        feed["url"],
        timeout=TIMEOUT_SECONDS,
        headers={"User-Agent": "FinancialObserverRSS/1.0 (+https://github.com/liuyanglei/gadget)"},
    )
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"invalid RSS: {parsed.bozo_exception}")

    articles = []
    for entry in parsed.entries[:PER_SOURCE_LIMIT]:
        title = clean_text(entry.get("title"), 180)
        url = str(entry.get("link") or "").strip()
        if not title or not url.startswith(("http://", "https://")):
            continue
        summary = clean_text(entry.get("summary") or entry.get("description"))
        published = parse_datetime(entry)
        fingerprint = hashlib.sha1(f"{title}|{url}".encode("utf-8")).hexdigest()[:16]
        articles.append(
            {
                "id": fingerprint,
                "title": title,
                "url": url,
                "published_at": published.isoformat().replace("+00:00", "Z"),
                "summary": summary,
                "source": feed["source"],
                "category": classify(title, summary),
            }
        )
    return articles


def load_previous() -> list[dict[str, str]]:
    try:
        payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
        return payload.get("articles", []) if isinstance(payload, dict) else payload
    except (OSError, json.JSONDecodeError, AttributeError):
        return []


def main() -> None:
    collected: list[dict[str, str]] = []
    successful_sources = 0
    for feed in FEEDS:
        try:
            items = fetch_feed(feed)
            collected.extend(items)
            successful_sources += 1
            logging.info("Collected %d items from %s", len(items), feed["source"])
        except (requests.RequestException, ValueError) as exc:
            logging.warning("Skipping %s: %s", feed["source"], exc)

    # Preserve recent history while replacing duplicate titles with fresh items.
    combined = collected + load_previous()
    unique: dict[str, dict[str, str]] = {}
    for article in combined:
        key = re.sub(r"\W+", "", article.get("title", "").lower())
        if key and key not in unique:
            unique[key] = article

    articles = sorted(unique.values(), key=lambda item: item.get("published_at", ""), reverse=True)[:MAX_ARTICLES]
    if not articles:
        raise RuntimeError("No articles collected and no previous data available")

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "successful_sources": successful_sources,
        "articles": articles,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logging.info("Wrote %d articles to %s", len(articles), OUTPUT)


if __name__ == "__main__":
    main()
