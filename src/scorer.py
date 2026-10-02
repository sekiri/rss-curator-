import logging
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from src.config import DB_PATH, SIMILARITY_THRESHOLD
from src.db import get_unscored_articles, update_article_score, update_feed_stats
from src.embedder import embed_batch, get_user_profile_vector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def score_articles(
    db_path: Path | str = DB_PATH,
    threshold: float = SIMILARITY_THRESHOLD,
    batch_size: int = 64,
) -> Dict[str, int]:
    """
    未評価の記事（similarity_score IS NULL）を取得し、
    ユーザー関心ベクトルとのコサイン類似度を計算して判定・保存する。
    """
    user_vector = get_user_profile_vector(db_path=db_path)
    if user_vector is None:
        logger.warning("No user profile vector available. Please ensure bookmarks exist.")
        return {"processed": 0, "curated": 0}

    unscored = get_unscored_articles(db_path=db_path)
    if not unscored:
        logger.info("No unscored articles found.")
        return {"processed": 0, "curated": 0}

    logger.info(f"Scoring {len(unscored)} unscored articles (threshold={threshold})...")

    total_processed = 0
    total_curated = 0

    # バッチ単位で処理
    for i in range(0, len(unscored), batch_size):
        batch = unscored[i : i + batch_size]
        texts = []
        for row in batch:
            title = row["title"] or ""
            snippet = row["content_snippet"] or ""
            text = f"{title} {snippet}".strip()
            # 空文字対策
            if not text:
                text = "empty article"
            texts.append(text)

        # 一括ベクトル化（embed_batchはL2正規化済み）
        art_vectors = embed_batch(texts)  # (B, D)

        # コサイン類似度: normalized なので 内積で計算
        scores = np.dot(art_vectors, user_vector)  # shape: (B,)

        for row, score in zip(batch, scores):
            article_id = row["id"]
            feed_id = row["feed_id"]
            score_val = float(score)
            is_curated = score_val >= threshold

            # 記事テーブルの更新
            update_article_score(
                article_id=article_id,
                score=score_val,
                is_curated=is_curated,
                db_path=db_path,
            )

            # 採用記事の場合は該当フィードのhit_countを加算
            if is_curated:
                update_feed_stats(feed_id=feed_id, hit_increment=1, db_path=db_path)
                total_curated += 1

            total_processed += 1

    logger.info(f"Scoring finished. Processed: {total_processed}, Curated: {total_curated}")
    return {
        "processed": total_processed,
        "curated": total_curated,
    }
