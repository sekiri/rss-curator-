import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer

from src.config import (
    BOOKMARKS_PATH,
    DB_PATH,
    EMBEDDING_MODEL_NAME,
    TIME_DECAY_HALF_LIFE_DAYS,
)
from src.db import get_bookmarks, init_db, upsert_bookmark

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# シングルトンモデルキャッシュ
_MODEL_INSTANCE: Optional[SentenceTransformer] = None


def get_model(model_name: str = EMBEDDING_MODEL_NAME) -> SentenceTransformer:
    """SentenceTransformerモデルを取得（初回のみロード・キャッシュ）。"""
    global _MODEL_INSTANCE
    if _MODEL_INSTANCE is None:
        logger.info(f"Loading embedding model: {model_name}...")
        _MODEL_INSTANCE = SentenceTransformer(model_name)
        logger.info(f"Model {model_name} loaded successfully.")
    return _MODEL_INSTANCE


def vector_to_blob(vec: np.ndarray) -> bytes:
    """numpy配列（float32）をバイナリ（BLOB）に変換する。"""
    return vec.astype(np.float32).tobytes()


def blob_to_vector(blob: bytes) -> np.ndarray:
    """バイナリ（BLOB）をnumpy配列（float32）に復元する。"""
    return np.frombuffer(blob, dtype=np.float32)


def normalize_vector(vec: np.ndarray) -> np.ndarray:
    """ベクトルをL2正規化する。ノルムが0の場合はそのまま返す。"""
    norm = np.linalg.norm(vec)
    if norm > 0:
        return vec / norm
    return vec


def embed_text(text: str, model_name: str = EMBEDDING_MODEL_NAME) -> np.ndarray:
    """
    単一テキストをベクトル化し、L2正規化された1次元numpy配列を返す。
    """
    model = get_model(model_name)
    vec = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
    return vec.astype(np.float32)


def embed_batch(texts: List[str], model_name: str = EMBEDDING_MODEL_NAME) -> np.ndarray:
    """
    複数テキストを一括ベクトル化し、L2正規化された2次元numpy配列を返す。
    """
    if not texts:
        return np.empty((0, 0), dtype=np.float32)
    model = get_model(model_name)
    vecs = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    return vecs.astype(np.float32)


def parse_bookmarks_file(bookmarks_path: Path | str = BOOKMARKS_PATH) -> List[str]:
    """
    bookmarks.txt を読み込み、各行のテキストリストを返す。
    空行やコメント行（#始まり）は除外する。
    """
    path = Path(bookmarks_path)
    if not path.exists():
        logger.warning(f"Bookmarks file not found: {path}")
        return []

    lines = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                lines.append(stripped)
    return lines


def sync_bookmarks(
    bookmarks_path: Path | str = BOOKMARKS_PATH,
    db_path: Path | str = DB_PATH,
    model_name: str = EMBEDDING_MODEL_NAME,
) -> int:
    """
    bookmarks.txt を読み込み、新規追加されたテキストのベクトルを計算してDBにキャッシュする。
    既存のキャッシュ済みブックマークは再計算をスキップする。
    新規登録されたブックマーク数を返す。
    """
    init_db(db_path)
    entries = parse_bookmarks_file(bookmarks_path)
    if not entries:
        logger.info(f"No bookmark entries found in {bookmarks_path}")
        return 0

    existing_rows = get_bookmarks(db_path)
    existing_texts = {row["text"]: row["embedding"] for row in existing_rows}

    new_entries = [entry for entry in entries if entry not in existing_texts or existing_texts[entry] is None]

    if not new_entries:
        logger.info("All bookmarks are already cached and up to date.")
        return 0

    logger.info(f"Computing embeddings for {len(new_entries)} new bookmarks...")
    embeddings = embed_batch(new_entries, model_name=model_name)

    now_str = datetime.now().isoformat()
    for text, emb in zip(new_entries, embeddings):
        blob = vector_to_blob(emb)
        upsert_bookmark(text=text, embedding=blob, added_at=now_str, db_path=db_path)

    logger.info(f"Successfully cached embeddings for {len(new_entries)} bookmarks.")
    return len(new_entries)


def parse_datetime_safe(dt_str: str) -> datetime:
    """日付文字列を安全にパースしてawareまたはnaiveなdatetimeにする。"""
    try:
        from dateutil.parser import parse as parse_date
        dt = parse_date(dt_str)
        if dt.tzinfo is not None:
            # UTCに統一してnaive化
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return datetime.now(timezone.utc).replace(tzinfo=None)


def get_user_profile_vector(
    db_path: Path | str = DB_PATH,
    half_life_days: float = TIME_DECAY_HALF_LIFE_DAYS,
) -> Optional[np.ndarray]:
    """
    DB内のブックマーク群から時間減衰（Time Decay）を適用した統合ユーザー関心ベクトルを算出する。
    重み: w_i = 2^(-(経過日数 / half_life_days))
    統合ベクトル: V_user = normalize(sum(w_i * v_i))
    ブックマークが存在しない場合は None を返す。
    """
    rows = get_bookmarks(db_path)
    if not rows:
        logger.warning("No bookmarks in database. Cannot create user profile vector.")
        return None

    vectors: List[np.ndarray] = []
    weights: List[float] = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for row in rows:
        embedding_blob = row["embedding"]
        if not embedding_blob:
            continue
        vec = blob_to_vector(embedding_blob)

        # 時間減衰の計算
        added_at_str = row["added_at"]
        added_at = parse_datetime_safe(added_at_str)
        delta_days = max(0.0, (now - added_at).total_seconds() / 86400.0)

        # 半減期減衰モデル: 2^(-delta_days / half_life_days)
        weight = math.pow(2.0, -delta_days / max(half_life_days, 1e-5))

        vectors.append(vec)
        weights.append(weight)

    if not vectors:
        return None

    # 重み付き加算
    stacked_vectors = np.stack(vectors, axis=0)  # (N, D)
    weights_arr = np.array(weights, dtype=np.float32)[:, np.newaxis]  # (N, 1)

    combined_vec = np.sum(stacked_vectors * weights_arr, axis=0)
    return normalize_vector(combined_vec)
