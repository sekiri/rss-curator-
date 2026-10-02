import logging
from pathlib import Path
from typing import List

from src.config import DB_PATH, PRUNE_MIN_FETCHED, PRUNE_MIN_HIT_RATE
from src.db import get_feeds, update_feed_status

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def prune_feeds(
    db_path: Path | str = DB_PATH,
    min_fetched: int = PRUNE_MIN_FETCHED,
    min_hit_rate: float = PRUNE_MIN_HIT_RATE,
) -> List[int]:
    """
    低エンゲージメントなアクティブフィードを検出し、ステータスを 'dormant' に変更する。
    条件: total_fetched >= min_fetched (デフォルト50) かつ (hit_count / total_fetched) < min_hit_rate (デフォルト0.02)
    休眠化されたフィードIDのリストを返す。
    """
    active_feeds = get_feeds(status="active", db_path=db_path)
    dormant_feed_ids: List[int] = []

    for feed in active_feeds:
        total_fetched = feed["total_fetched"] or 0
        hit_count = feed["hit_count"] or 0

        if total_fetched >= min_fetched:
            hit_rate = hit_count / total_fetched
            if hit_rate < min_hit_rate:
                logger.info(
                    f"Pruning feed ID {feed['id']} ('{feed['title']}'): "
                    f"hit_rate={hit_rate:.4f} ({hit_count}/{total_fetched}) < {min_hit_rate:.4f}. Status set to 'dormant'."
                )
                update_feed_status(feed["id"], status="dormant", db_path=db_path)
                dormant_feed_ids.append(feed["id"])

    logger.info(f"Feed pruning completed. {len(dormant_feed_ids)} feed(s) moved to dormant status.")
    return dormant_feed_ids
