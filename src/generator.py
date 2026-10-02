import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dateutil import parser as date_parser
import rfeed

from src.config import (
    CURATED_DAYS_LIMIT,
    DB_PATH,
    FEED_DESCRIPTION,
    FEED_LINK,
    FEED_TITLE,
    MAX_CURATED_ITEMS,
    OUTPUT_FEED_PATH,
)
from src.db import get_curated_articles

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def parse_datetime_for_rfeed(date_str: Optional[str]) -> datetime:
    """日付文字列をdatetimeオブジェクトに変換する。失敗した場合は現在時刻を返す。"""
    if not date_str:
        return datetime.now(timezone.utc)
    try:
        dt = date_parser.parse(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.now(timezone.utc)


def generate_rss_feed(
    db_path: Path | str = DB_PATH,
    output_path: Path | str = OUTPUT_FEED_PATH,
    days_limit: int = CURATED_DAYS_LIMIT,
    max_items: int = MAX_CURATED_ITEMS,
    feed_title: str = FEED_TITLE,
    feed_link: str = FEED_LINK,
    feed_description: str = FEED_DESCRIPTION,
) -> Path:
    """
    DB内の採用記事（is_curated = 1）を抽出し、RSS 2.0 XMLファイルを生成して保存する。
    生成されたファイルのPathを返す。
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    articles = get_curated_articles(
        days_limit=days_limit,
        max_items=max_items,
        db_path=db_path,
    )
    logger.info(f"Generating RSS feed with {len(articles)} curated articles...")

    rss_items = []
    for art in articles:
        pub_dt = parse_datetime_for_rfeed(art["published_at"])
        score = art["similarity_score"]
        score_prefix = f"[Relevance: {score:.2f}] " if score is not None else ""
        description = f"{score_prefix}{art['content_snippet'] or ''}"

        item = rfeed.Item(
            title=art["title"] or "Untitled Article",
            link=art["link"] or "",
            description=description,
            guid=rfeed.Guid(art["guid"]),
            pubDate=pub_dt,
        )
        rss_items.append(item)

    feed = rfeed.Feed(
        title=feed_title,
        link=feed_link,
        description=feed_description,
        language="ja-JP",
        lastBuildDate=datetime.now(timezone.utc),
        items=rss_items,
    )

    xml_content = feed.rss()
    out.write_text(xml_content, encoding="utf-8")
    logger.info(f"Curated feed successfully written to {out} ({len(rss_items)} items).")
    return out
