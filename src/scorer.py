import logging
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from src.config import DB_PATH, SIMILARITY_THRESHOLD
from src.db import (
    get_unscored_articles,
    recalculate_feed_hit_counts,
    update_article_score,
)
from src.embedder import embed_batch, get_bookmark_embeddings_and_weights

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def score_articles(
    db_path: Path | str = DB_PATH,
    threshold: float = SIMILARITY_THRESHOLD,
    batch_size: int = 64,
    rescore_all: bool = False,
) -> Dict[str, int]:
    """
    対象記事を取得し、各ブックマークトピックとの最大類似度（時間減衰重み付き）を計算して判定・保存する。
    rescore_all=True の場合は既にスコアが付与されている記事も含めて全件再計算する。
    """
    bm_vectors, bm_weights = get_bookmark_embeddings_and_weights(db_path=db_path)
    if bm_vectors is None or bm_weights is None or len(bm_vectors) == 0:
        logger.warning("No bookmark vectors available. Please ensure bookmarks exist.")
        return {"processed": 0, "curated": 0}

    articles_to_score = get_unscored_articles(rescore_all=rescore_all, db_path=db_path)
    if not articles_to_score:
        logger.info("No articles to score.")
        return {"processed": 0, "curated": 0}

    mode_str = "all" if rescore_all else "unscored"
    logger.info(f"Scoring {len(articles_to_score)} {mode_str} articles (threshold={threshold})...")

    total_processed = 0
    total_curated = 0

    # バッチ単位で処理
    for i in range(0, len(articles_to_score), batch_size):
        batch = articles_to_score[i : i + batch_size]
        texts = []
        for row in batch:
            title = row["title"] or ""
            snippet = row["content_snippet"] or ""
            text = f"{title} {snippet}".strip()
            if not text:
                text = "empty article"
            texts.append(text)

        # 一括ベクトル化（embed_batchはL2正規化済み） (B, D)
        art_vectors = embed_batch(texts)

        # 各ブックマークとのコサイン類似度行列 (B, N)
        sim_matrix = np.dot(art_vectors, bm_vectors.T)

        # 時間減衰重みを考慮した実効スコア (B, N)
        # 各ブックマークトピックの鮮度に応じた重みを適用
        effective_sims = sim_matrix * bm_weights[np.newaxis, :]

        # ユーザーが最も関心を持つトピックとの最大類似度を採用 (B,)
        scores = np.max(effective_sims, axis=1)

        for row, score in zip(batch, scores):
            article_id = row["id"]
            score_val = float(score)
            is_curated = score_val >= threshold

            update_article_score(
                article_id=article_id,
                score=score_val,
                is_curated=is_curated,
                db_path=db_path,
            )

            if is_curated:
                total_curated += 1

            total_processed += 1

    # フィードのhit_countを実態に合わせて再集計・更新
    recalculate_feed_hit_counts(db_path=db_path)

    logger.info(f"Scoring finished. Processed: {total_processed}, Curated: {total_curated}")
    return {
        "processed": total_processed,
        "curated": total_curated,
    }
