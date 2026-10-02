import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from src.config import (
    BOOKMARKS_PATH,
    DB_PATH,
    OUTPUT_FEED_PATH,
    SEEDS_OPML_PATH,
    SIMILARITY_THRESHOLD,
)
from src.crawler import crawl_all
from src.db import get_feeds, init_db
from src.embedder import sync_bookmarks
from src.generator import generate_rss_feed
from src.opml_loader import import_opml
from src.pruner import prune_feeds
from src.scorer import score_articles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("rss-curator")


def push_to_github(commit_message: Optional[str] = None) -> bool:
    """docs/curated.xml および data/curator.db をステージング・コミットし、GitHub にプッシュする。"""
    import subprocess
    from datetime import datetime

    logger.info("--- Step 6: Pushing Updates to GitHub ---")
    try:
        # 変更があるか確認
        res = subprocess.run(
            ["git", "status", "--porcelain", "docs/curated.xml", "data/curator.db"],
            capture_output=True,
            text=True,
            check=True,
        )
        if not res.stdout.strip():
            logger.info("No changes detected in curated.xml or database. Push skipped.")
            return True

        if not commit_message:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            commit_message = f"Auto-update curated feed ({now_str})"

        logger.info("Staging docs/curated.xml and data/curator.db...")
        subprocess.run(["git", "add", "docs/curated.xml", "data/curator.db"], check=True)

        logger.info(f"Committing changes: {commit_message}")
        subprocess.run(["git", "commit", "-m", commit_message], check=True)

        logger.info("Pushing to origin main...")
        subprocess.run(["git", "push", "origin", "main"], check=True)

        logger.info("Successfully pushed updated feed to GitHub!")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Git operation failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during git push: {e}")
        return False


def run_pipeline(
    db_path: Path | str = DB_PATH,
    bookmarks_path: Path | str = BOOKMARKS_PATH,
    opml_path: Path | str = SEEDS_OPML_PATH,
    output_path: Path | str = OUTPUT_FEED_PATH,
    threshold: float = SIMILARITY_THRESHOLD,
    rescore_all: bool = False,
    push: bool = False,
) -> None:
    """フルパイプラインを実行する。"""
    logger.info("==========================================")
    logger.info("Starting Autonomous RSS Curation Pipeline")
    logger.info("==========================================")

    # 1. DB初期化
    init_db(db_path)

    # 2. OPML初期シード取り込み（feedsテーブルが空かつOPMLが存在する場合）
    opml_file = Path(opml_path)
    existing_feeds = get_feeds(db_path=db_path)
    if not existing_feeds and opml_file.exists():
        logger.info(f"Initial feed import from {opml_file}...")
        import_opml(opml_path=opml_file, db_path=db_path)

    # 3. ブックマーク同期とベクトルキャッシュ
    logger.info("--- Step 1: Syncing Bookmarks & User Profile ---")
    sync_bookmarks(bookmarks_path=bookmarks_path, db_path=db_path)

    # 4. フィード巡回
    logger.info("--- Step 2: Crawling Feeds for New Articles ---")
    crawl_res = crawl_all(db_path=db_path)
    logger.info(f"Crawled {crawl_res['feeds_processed']} feeds, fetched {crawl_res['new_articles']} new articles.")

    # 5. スコアリング
    logger.info(f"--- Step 3: Scoring Articles (Threshold={threshold}, Rescore All={rescore_all}) ---")
    score_res = score_articles(db_path=db_path, threshold=threshold, rescore_all=rescore_all)
    logger.info(f"Scored {score_res['processed']} articles, curated {score_res['curated']} articles.")

    # 6. フィード刈り取り（プルーニング）
    logger.info("--- Step 4: Pruning Low-Engagement Feeds ---")
    pruned = prune_feeds(db_path=db_path)
    if pruned:
        logger.info(f"Pruned feeds: {pruned}")
    else:
        logger.info("No feeds needed pruning.")

    # 7. RSS XML生成
    logger.info("--- Step 5: Generating Curated RSS XML ---")
    generated_path = generate_rss_feed(db_path=db_path, output_path=output_path)
    logger.info(f"Curated feed output: {generated_path}")

    # 8. GitHub へのプッシュ（指定された場合）
    if push:
        push_to_github()

    logger.info("==========================================")
    logger.info("Pipeline Execution Completed Successfully!")
    logger.info("==========================================")


def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous Personal RSS Curation Engine")
    parser.add_argument(
        "--import-opml",
        nargs="?",
        const=str(SEEDS_OPML_PATH),
        help=f"Import seeds from OPML file (default: {SEEDS_OPML_PATH})",
    )
    parser.add_argument(
        "--update-bookmarks",
        action="store_true",
        help="Update user profile embeddings from bookmarks.txt",
    )
    parser.add_argument(
        "--crawl",
        action="store_true",
        help="Fetch new articles from registered feeds",
    )
    parser.add_argument(
        "--score",
        action="store_true",
        help="Score unscored articles and curate matches",
    )
    parser.add_argument(
        "--rescore",
        action="store_true",
        help="Recalculate similarity scores for all existing articles",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=SIMILARITY_THRESHOLD,
        help=f"Similarity threshold for curation (default: {SIMILARITY_THRESHOLD})",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Prune underperforming feeds (mark as dormant)",
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate curated.xml RSS feed",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Commit and push updated feed to GitHub",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Run full end-to-end curation pipeline",
    )

    args = parser.parse_args()

    # 初期化
    init_db(DB_PATH)

    # いずれの特定フラグも指定されていない場合は --run と同等に扱う
    has_specific_flag = any(
        [
            args.import_opml is not None,
            args.update_bookmarks,
            args.crawl,
            args.score,
            args.rescore,
            args.prune,
            args.generate,
            args.push,
        ]
    )

    if args.run or not has_specific_flag:
        run_pipeline(threshold=args.threshold, rescore_all=args.rescore, push=args.push)
        return

    if args.import_opml:
        import_opml(opml_path=args.import_opml, db_path=DB_PATH)

    if args.update_bookmarks:
        sync_bookmarks(bookmarks_path=BOOKMARKS_PATH, db_path=DB_PATH)

    if args.crawl:
        crawl_all(db_path=DB_PATH)

    if args.rescore:
        score_articles(db_path=DB_PATH, threshold=args.threshold, rescore_all=True)

    if args.score:
        score_articles(db_path=DB_PATH, threshold=args.threshold, rescore_all=False)

    if args.prune:
        prune_feeds(db_path=DB_PATH)

    if args.generate:
        generate_rss_feed(db_path=DB_PATH, output_path=OUTPUT_FEED_PATH)

    if args.push:
        push_to_github()


if __name__ == "__main__":
    main()
