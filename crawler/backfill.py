"""Backfill complete documents from official Chinese financial sources.

Run locally with ``python crawler/backfill.py``. Checkpoints are written after
each source, so an interrupted backfill can be resumed safely.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from spider import (
    CHINA_TZ, HEADERS, MIN_CONTENT_LENGTH, OUTPUT, SSE_DISCOVERY_LIMIT,
    article_id, category_for, discover_sse, download, extract_attachment,
    extract_sse, is_publishable, load_category_limits, load_previous,
    normalized_text,
)

STATS_INDEX = "https://www.stats.gov.cn/sj/zxfb/"
CSRC_ORIGIN = "https://www.csrc.gov.cn"
CSRC_REGULATORY_CHANNEL = "625e0ed8a45842c28751458bfcacb422"
CSRC_POLICY_INDEXES = (
    "https://www.csrc.gov.cn/csrc/c100039/",
    "https://www.csrc.gov.cn/csrc/c100028/",
)
MOF_POLICY_INDEX = "https://www.mof.gov.cn/zhengwuxinxi/zhengcejiedu/"
ATTACHMENT_SUFFIXES = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
REGULATORY_TERMS = re.compile(r"证券|期货|基金|债券|上市公司|监管|处罚|警示|整改|注销|行政许可|信息披露|发行|交易所|财务造假")
POLICY_TERMS = re.compile(r"政策|解读|规定|办法|规则|指引|意见|通知|修订|改革|发布|印发|实施")


def get_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS | {"Referer": CSRC_ORIGIN + "/"})
    return session


def listing_stats(session: requests.Session, pages: int = 67) -> list[dict[str, str]]:
    found = {}
    for number in range(pages):
        url = urljoin(STATS_INDEX, "index.html" if number == 0 else f"index_{number}.html")
        response = session.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content.decode("utf-8", errors="replace"), "html.parser")
        for anchor in soup.select('a[href*="/t20"]'):
            href = str(anchor.get("href") or "")
            item_url = urljoin(url, href)
            if not re.search(r"/sj/zxfb/20\d{4}/t20\d{6}_\d+\.html$", item_url):
                continue
            title = normalized_text(str(anchor.get("title") or anchor.get_text(" ", strip=True)))
            if title:
                found[item_url] = {"id": article_id(item_url), "url": item_url, "title": title}
        logging.info("NBS index %d: %d unique documents", number, len(found))
        if len(found) >= 700:
            break
    return list(found.values())


def listing_csrc_regulatory(session: requests.Session, pages: int = 55) -> list[dict[str, str]]:
    found = {}
    for page in range(1, pages + 1):
        url = (f"{CSRC_ORIGIN}/searchList/{CSRC_REGULATORY_CHANNEL}"
               f"?_isAgg=true&_isJson=true&_pageSize=18&_template=index&_rangeTimeGte=&_channelName=&page={page}")
        response = session.get(url, timeout=30)
        response.raise_for_status()
        items = response.json().get("data", {}).get("results", [])
        if not isinstance(items, list) or not items:
            break
        for item in items:
            title = normalized_text(str(item.get("title") or ""))
            item_url = urljoin(CSRC_ORIGIN, str(item.get("url") or ""))
            if title and REGULATORY_TERMS.search(title) and item_url.startswith(CSRC_ORIGIN + "/"):
                found[item_url] = {"id": article_id(item_url), "url": item_url, "title": title}
        logging.info("CSRC regulatory index %d: %d candidate documents", page, len(found))
        if len(found) >= 850:
            break
    return list(found.values())


def listing_csrc_policy(session: requests.Session, pages: int = 20) -> list[dict[str, str]]:
    found = {}
    for base in CSRC_POLICY_INDEXES:
        for page in range(1, pages + 1):
            url = urljoin(base, "common_list.shtml" if page == 1 else f"common_list_{page}.shtml")
            response = session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content.decode("utf-8", errors="replace"), "html.parser")
            for anchor in soup.select('a[href*="/content.shtml"]'):
                title = normalized_text(anchor.get_text(" ", strip=True))
                item_url = urljoin(CSRC_ORIGIN, str(anchor.get("href") or ""))
                if title and POLICY_TERMS.search(title) and item_url.startswith(CSRC_ORIGIN + "/"):
                    found[item_url] = {"id": article_id(item_url), "url": item_url, "title": title}
            logging.info("CSRC policy index %s page %d: %d candidates", base.rstrip("/").split("/")[-1], page, len(found))
    return list(found.values())


def listing_mof_policy(session: requests.Session, pages: int = 20) -> list[dict[str, str]]:
    found = {}
    for number in range(pages):
        url = urljoin(MOF_POLICY_INDEX, "index.htm" if number == 0 else f"index_{number}.htm")
        response = session.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content.decode("utf-8", errors="replace"), "html.parser")
        for anchor in soup.select('a[href*="/t20"]'):
            title = normalized_text(str(anchor.get("title") or anchor.get_text(" ", strip=True)))
            item_url = urljoin(url, str(anchor.get("href") or "")).replace("http://", "https://", 1)
            if title and item_url.endswith(".htm") and item_url.split("/")[2].endswith("mof.gov.cn"):
                found[item_url] = {"id": article_id(item_url), "url": item_url, "title": title}
        logging.info("MOF policy index %d: %d unique documents", number, len(found))
    return list(found.values())


def extract_official(entry: dict[str, str], source: str, category: str) -> dict[str, object] | None:
    session = get_session()
    url = entry["url"]
    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content.decode("utf-8", errors="replace"), "html.parser")
        if source == "国家统计局":
            node = soup.select_one(".mobile-news-content")
        elif source == "中华人民共和国财政部":
            node = soup.select_one(".my_doccontent, .TRS_Editor, #zoom")
        else:
            node = soup.select_one(".detail-news")
        if node is None:
            return None
        for unwanted in node.select("script,style"):
            unwanted.decompose()
        parts = [normalized_text(node.get_text("\n", strip=True))]
        attachments = 0
        for anchor in node.select("a[href]"):
            attachment_url = urljoin(url, str(anchor.get("href") or ""))
            suffix = urlparse(attachment_url).path.lower().rsplit(".", 1)[-1]
            if "." + suffix not in ATTACHMENT_SUFFIXES:
                continue
            extracted = extract_attachment(download(session, attachment_url, url), attachment_url)
            if not extracted:
                return None
            parts.append("附件：" + normalized_text(anchor.get_text(" ", strip=True)) + "\n" + extracted[0])
            attachments += 1
        content = normalized_text("\n\n".join(parts))
        if len(content) < MIN_CONTENT_LENGTH:
            return None
        date_meta = soup.select_one('meta[name="PubDate"]')
        published = str(date_meta.get("content") or "") if date_meta else ""
        published = published.replace("/", "-")
        if not published:
            match = re.search(r"/t(20\d{6})_", url)
            published = datetime.strptime(match.group(1), "%Y%m%d").strftime("%Y-%m-%d") if match else ""
        try:
            date = datetime.fromisoformat(published).replace(tzinfo=CHINA_TZ).isoformat()
        except ValueError:
            return None
        article = {"id": entry["id"], "title": entry["title"], "published_at": date,
                   "content": content, "source": source, "category": category,
                   "attachment_stats": {"attachments": attachments}}
        return article if is_publishable(article) else None
    except Exception as exc:
        logging.warning("Skipping %s: %s", url, exc)
        return None


def save_articles(additions: list[dict[str, object]], previous_ids: set[str]) -> dict[str, int]:
    payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    articles_by_id = {str(item["id"]): item for item in load_previous()}
    for item in additions:
        articles_by_id[str(item["id"])] = item
    limits = load_category_limits()
    counts = {category: 0 for category in limits}
    articles = []
    for article in sorted(articles_by_id.values(), key=lambda item: str(item["published_at"]), reverse=True):
        category = str(article["category"])
        if counts[category] < limits[category]:
            articles.append(article)
            counts[category] += 1
    payload["articles"] = articles
    payload["category_limits"] = limits
    payload["new_articles"] = len({str(item["id"]) for item in articles} - previous_ids)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload["backfilled_at"] = payload["updated_at"]
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logging.info("Saved %d articles; category counts: %s", len(articles), counts)
    return counts


def collect_official(source: str, category: str, entries: list[dict[str, str]], workers: int = 8) -> int:
    current = load_previous()
    seen = {str(item["id"]) for item in current}
    limit = load_category_limits()[category]
    needed = max(0, min(500, limit) - sum(item["category"] == category for item in current))
    if needed == 0:
        return 0
    fresh = [entry for entry in entries if entry["id"] not in seen]
    found = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for offset in range(0, len(fresh), workers * 5):
            batch = fresh[offset:offset + workers * 5]
            futures = [executor.submit(extract_official, entry, source, category) for entry in batch]
            for future in as_completed(futures):
                article = future.result()
                if article:
                    found.append(article)
            logging.info("%s: extracted %d of %d needed", category, len(found), needed)
            if found and offset and offset % (workers * 5 * 10) == 0:
                save_articles(found, seen)
            if len(found) >= needed:
                break
    if found:
        save_articles(found, seen)
    return len(found)


def collect_sse_history(days: int = 240, workers: int = 8) -> None:
    current = load_previous()
    seen = {str(item["id"]) for item in current}
    counts = {category: sum(item["category"] == category for item in current) for category in ("分红派息", "公司报告")}
    session = get_session()
    today = datetime.now(CHINA_TZ).date()
    found = []
    attempted = set()
    for offset in range(8, days + 8):
        if all(counts[category] >= 500 for category in counts):
            break
        day = (today - timedelta(days=offset)).isoformat()
        try:
            entries = discover_sse(session, day, day)
        except (requests.RequestException, ValueError) as exc:
            logging.warning("SSE discovery failed on %s: %s", day, exc)
            continue
        targets = [entry for entry in entries if entry["category"] in counts and counts[entry["category"]] < 500
                   and entry["id"] not in seen and entry["id"] not in attempted]
        attempted.update(entry["id"] for entry in targets)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(extract_sse, entry) for entry in targets]
            for future in as_completed(futures):
                article = future.result()
                if article and is_publishable(article):
                    found.append(article)
                    counts[str(article["category"])] += 1
        logging.info("SSE %s: %d candidates, dividends=%d, reports=%d", day, len(targets), counts["分红派息"], counts["公司报告"])
        if found and (offset % 7 == 0 or all(counts[category] >= 500 for category in counts)):
            save_articles(found, seen)
            seen.update(str(article["id"]) for article in found)
            found = []
    if found:
        save_articles(found, seen)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=("all", "stats", "regulatory", "policy", "mof", "sse"), default="all")
    parser.add_argument("--sse-days", type=int, default=240)
    args = parser.parse_args()
    session = get_session()
    if args.source in {"all", "stats"}:
        collect_official("国家统计局", "宏观数据", listing_stats(session))
    if args.source in {"all", "regulatory"}:
        collect_official("中国证监会", "监管动态", listing_csrc_regulatory(session))
    if args.source in {"all", "policy"}:
        collect_official("中国证监会", "政策解读", listing_csrc_policy(session))
    if args.source in {"all", "mof"}:
        collect_official("中华人民共和国财政部", "政策解读", listing_mof_policy(session))
    if args.source in {"all", "sse"}:
        collect_sse_history(args.sse_days)


if __name__ == "__main__":
    main()
