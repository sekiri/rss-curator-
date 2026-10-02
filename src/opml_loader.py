import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.config import DB_PATH, SEEDS_OPML_PATH
from src.db import add_feed, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def parse_opml(file_path: Path | str) -> List[Dict[str, str]]:
    """
    OPMLファイルをパースして、フィード情報（url, title）のリストを返す。
    """
    path = Path(file_path)
    if not path.exists():
        logger.warning(f"OPML file not found: {path}")
        return []

    feeds = []
    try:
        tree = ET.parse(str(path))
        root = tree.getroot()

        # すべての outline 要素を再帰的に走査
        for outline in root.iter("outline"):
            xml_url = outline.get("xmlUrl") or outline.get("url")
            if xml_url:
                title = outline.get("title") or outline.get("text") or xml_url
                feeds.append({"url": xml_url.strip(), "title": title.strip()})

    except ET.ParseError as e:
        logger.error(f"Failed to parse OPML file {path}: {e}")
        raise

    return feeds


def import_opml(
    opml_path: Path | str = SEEDS_OPML_PATH,
    db_path: Path | str = DB_PATH,
) -> int:
    """
    OPMLファイルからフィードを読み込み、feedsテーブルに登録する。
    登録されたフィードの総数を返す。
    """
    init_db(db_path)
    feeds = parse_opml(opml_path)
    if not feeds:
        logger.info(f"No feeds found to import from {opml_path}")
        return 0

    registered_count = 0
    for feed in feeds:
        url = feed["url"]
        title = feed.get("title")
        feed_id = add_feed(url=url, title=title, db_path=db_path)
        if feed_id:
            registered_count += 1

    logger.info(f"Imported/Updated {registered_count} feeds from {opml_path}")
    return registered_count


if __name__ == "__main__":
    import sys

    target_opml = sys.argv[1] if len(sys.argv) > 1 else SEEDS_OPML_PATH
    import_opml(target_opml)
