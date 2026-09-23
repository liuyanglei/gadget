"""Collect complete Chinese text from official public finance sources."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "news.json"
LISTING_URL = "https://wap.miit.gov.cn/RRSdy/index.html"
ARTICLE_ORIGIN = "https://www.miit.gov.cn"
MAX_ARTICLES = 60
LISTING_LIMIT = 45
MIN_CONTENT_LENGTH = 180
TIMEOUT_SECONDS = 20
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

CATEGORY_KEYWORDS = {
    "A股": ("上市公司", "证券", "股票", "资本市场", "融资"),
    "港股": ("香港", "港股", "联交所"),
    "黄金": ("黄金", "贵金属"),
    "原油": ("原油", "石油", "成品油", "油价"),
    "基金": ("基金", "公募", "私募", "资产管理"),
}

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def normalized_text(value: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def classify(title: str, content: str) -> str:
    haystack = f"{title} {content[:1000]}"
    scores = {
        category: sum(1 for keyword in keywords if keyword in haystack)
        for category, keywords in CATEGORY_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] else "宏观经济"


def parse_datetime(value: str) -> datetime:
    value = value.strip()
    for pattern in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def discover_article_urls(session: requests.Session) -> list[str]:
    response = session.get(LISTING_URL, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()
    for anchor in soup.select('a[href*="/art/"]'):
        href = str(anchor.get("href") or "")
        if not href.endswith(".html"):
            continue
        url = urljoin(ARTICLE_ORIGIN, href)
        if url not in seen:
            seen.add(url)
            urls.append(url)
        if len(urls) >= LISTING_LIMIT:
            break
    return urls


def extract_article(session: requests.Session, url: str) -> dict[str, str] | None:
    response = session.get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")
    content_node = soup.select_one("#con_con")
    title_node = soup.select_one("#con_title")
    if not content_node or not title_node:
        return None

    title = normalized_text(title_node.get_text(" ", strip=True))
    content = normalized_text(content_node.get_text("\n", strip=True))
    if not title or len(content) < MIN_CONTENT_LENGTH:
        return None

    date_meta = soup.select_one('meta[name="PubDate"]')
    source_meta = soup.select_one('meta[name="ContentSource"]')
    published = parse_datetime(str(date_meta.get("content") if date_meta else ""))
    source_detail = normalized_text(str(source_meta.get("content") if source_meta else ""))
    source = f"工业和信息化部 · {source_detail}" if source_detail else "工业和信息化部"
    fingerprint = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return {
        "id": fingerprint,
        "title": title,
        "published_at": published.isoformat().replace("+00:00", "Z"),
        "content": content,
        "source": source,
        "category": classify(title, content),
    }


def load_previous_full_text() -> list[dict[str, str]]:
    try:
        payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
        articles = payload.get("articles", []) if isinstance(payload, dict) else []
        return [item for item in articles if len(item.get("content", "")) >= MIN_CONTENT_LENGTH]
    except (OSError, json.JSONDecodeError, AttributeError):
        return []


def main() -> None:
    session = requests.Session()
    session.headers.update(HEADERS)
    collected: list[dict[str, str]] = []

    try:
        urls = discover_article_urls(session)
        logging.info("Discovered %d official Chinese articles", len(urls))
    except requests.RequestException as exc:
        logging.warning("Could not load official listing: %s", exc)
        urls = []

    for url in urls:
        try:
            article = extract_article(session, url)
            if article:
                collected.append(article)
        except requests.RequestException as exc:
            logging.warning("Skipping %s: %s", url, exc)

    combined = collected + load_previous_full_text()
    unique: dict[str, dict[str, str]] = {}
    for item in combined:
        title_key = re.sub(r"\W+", "", item.get("title", "").lower())
        if title_key and item.get("content") and title_key not in unique:
            unique[title_key] = item
    articles = sorted(unique.values(), key=lambda item: item["published_at"], reverse=True)[:MAX_ARTICLES]
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "successful_sources": 1 if collected else 0,
        "content_mode": "official_full_text_zh",
        "articles": articles,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logging.info("Wrote %d complete Chinese articles to %s", len(articles), OUTPUT)


if __name__ == "__main__":
    main()
