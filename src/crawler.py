import html
import logging
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import feedparser
import requests
from dateutil import parser as date_parser

from src.config import DB_PATH
from src.db import get_feeds, insert_article, update_feed_stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

USER_AGENT = "rss-curator/0.1.0 (Autonomous Personal RSS Engine; +https://github.com/example/rss-curator)"
REQUEST_TIMEOUT = 20


def clean_html(raw_html: str) -> str:
    """HTMLタグを除去し、HTMLエンティティをアンエスケープしてプレーンテキストにする。"""
    if not raw_html:
        return ""
    # script/styleタグとその中身を削除
    clean_text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
    # タグ全般を空白に置換
    clean_text = re.sub(r"<[^>]+>", " ", clean_text)
    # HTMLエンティティのデコード
    clean_text = html.unescape(clean_text)
    # 連続する空白・改行の正規化
    clean_text = re.sub(r"\s+", " ", clean_text).strip()
    return clean_text


def parse_published_date(entry: dict) -> Optional[str]:
    """エントリから公開日時を抽出し、ISO 8601形式の文字列で返す。"""
    date_fields = ["published", "updated", "created", "pubDate"]
    for field in date_fields:
        val = entry.get(field)
        if val:
            try:
                dt = date_parser.parse(val)
                if dt.tzinfo is not None:
                    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                return dt.isoformat()
            except Exception:
                continue

    # parsed tupleがある場合
    for tuple_field in ["published_parsed", "updated_parsed"]:
        tp = entry.get(tuple_field)
        if tp:
            try:
                dt = datetime(*tp[:6])
                return dt.isoformat()
            except Exception:
                continue

    return None


def extract_content_snippet(entry: dict, max_length: int = 1000) -> str:
    """記事の本文または要約スニペットを抽出・整形する。"""
    # 候補順: summary / description / content
    raw_content = ""
    if entry.get("summary"):
        raw_content = entry["summary"]
    elif entry.get("description"):
        raw_content = entry["description"]
    elif entry.get("content"):
        contents = entry["content"]
        if isinstance(contents, list) and len(contents) > 0:
            raw_content = contents[0].get("value", "")

    cleaned = clean_html(raw_content)
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length] + "..."
    return cleaned


def fetch_feed(feed_id: int, feed_url: str, db_path: Path | str = DB_PATH) -> int:
    """
    指定されたフィードURLから記事を取得し、未評価状態でDBに保存する。
    新しく追加された記事数を返す。
    """
    logger.info(f"Fetching feed ID {feed_id}: {feed_url}")
    try:
        response = requests.get(
            feed_url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
    except Exception as e:
        logger.error(f"Failed to fetch feed {feed_url}: {e}")
        return 0

    if parsed.bozo and not parsed.entries:
        logger.warning(f"Feed {feed_url} parsed with error: {parsed.bozo_exception}")
        return 0

    new_articles_count = 0
    now_iso = datetime.now().isoformat()

    for entry in parsed.entries:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        guid = entry.get("id") or link or title
        if not guid:
            continue

        published_at = parse_published_date(entry) or now_iso
        snippet = extract_content_snippet(entry)

        # 重複チェック付きで挿入
        inserted = insert_article(
            feed_id=feed_id,
            guid=guid,
            title=title,
            link=link,
            published_at=published_at,
            content_snippet=snippet,
            db_path=db_path,
        )
        if inserted:
            new_articles_count += 1

    # フィード統計情報の更新（フェッチ数、最終フェッチ日時）
    update_feed_stats(
        feed_id=feed_id,
        fetched_increment=new_articles_count,
        last_fetched_at=now_iso,
        db_path=db_path,
    )

    logger.info(f"Feed ID {feed_id}: {new_articles_count} new articles inserted (out of {len(parsed.entries)} parsed).")
    return new_articles_count


def crawl_all(
    db_path: Path | str = DB_PATH,
    dormant_fetch_rate: float = 0.1,
) -> Dict[str, int]:
    """
    DB内の全フィードを巡回する。
    - active フィード: 毎回巡回
    - dormant フィード: dormant_fetch_rate (10%) の確率で巡回
    - disabled フィード: 巡回しない
    """
    active_feeds = get_feeds(status="active", db_path=db_path)
    dormant_feeds = get_feeds(status="dormant", db_path=db_path)

    target_feeds = list(active_feeds)
    for feed in dormant_feeds:
        if random.random() < dormant_fetch_rate:
            target_feeds.append(feed)

    total_feeds = len(target_feeds)
    total_new_articles = 0

    logger.info(f"Starting crawl for {total_feeds} feeds ({len(active_feeds)} active, selected {len(target_feeds) - len(active_feeds)} dormant)...")

    for feed in target_feeds:
        new_count = fetch_feed(feed_id=feed["id"], feed_url=feed["url"], db_path=db_path)
        total_new_articles += new_count

    logger.info(f"Crawl finished. Processed {total_feeds} feeds, inserted {total_new_articles} new articles.")
    return {
        "feeds_processed": total_feeds,
        "new_articles": total_new_articles,
    }
