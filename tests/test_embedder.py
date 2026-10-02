import os
import tempfile
from pathlib import Path
import numpy as np

from src.embedder import (
    embed_batch,
    embed_text,
    get_user_profile_vector,
    sync_bookmarks,
)
from src.db import init_db, get_bookmarks

def test_embedder_and_bookmarks():
    temp_dir = tempfile.gettempdir()
    test_db = Path(temp_dir) / "test_embedder.db"
    test_bms = Path(temp_dir) / "test_bookmarks.txt"

    if test_db.exists():
        os.remove(test_db)

    print("--- 1. Testing embed_text & embed_batch ---")
    v1 = embed_text("LLM agents and autonomous systems")
    assert len(v1.shape) == 1, "Vector must be 1D"
    norm1 = np.linalg.norm(v1)
    assert abs(norm1 - 1.0) < 1e-4, f"Vector must be L2 normalized, got norm={norm1}"

    batch_vecs = embed_batch(["Python asyncio programming", "Machine learning embeddings"])
    assert batch_vecs.shape[0] == 2, "Batch shape mismatch"
    assert abs(np.linalg.norm(batch_vecs[0]) - 1.0) < 1e-4

    print("--- 2. Testing sync_bookmarks ---")
    content = """# My reading list
Machine Learning and Deep Learning advances
Python performance tuning and profiling
"""
    test_bms.write_text(content, encoding="utf-8")

    added_count = sync_bookmarks(bookmarks_path=test_bms, db_path=test_db)
    assert added_count == 2, f"Expected 2 bookmarks cached, got {added_count}"

    # 2回目の同期（差分なしのため0件）
    second_sync = sync_bookmarks(bookmarks_path=test_bms, db_path=test_db)
    assert second_sync == 0, f"Expected 0 bookmarks on second sync, got {second_sync}"

    rows = get_bookmarks(db_path=test_db)
    assert len(rows) == 2, "Expected 2 rows in DB"
    assert rows[0]["embedding"] is not None

    print("--- 3. Testing get_user_profile_vector ---")
    user_vec = get_user_profile_vector(db_path=test_db, half_life_days=30)
    assert user_vec is not None, "User profile vector should not be None"
    user_norm = np.linalg.norm(user_vec)
    assert abs(user_norm - 1.0) < 1e-4, f"User profile vector must be normalized, got {user_norm}"

    print("EMBEDDER & BOOKMARK SYNC VERIFICATION PASSED!")

if __name__ == "__main__":
    test_embedder_and_bookmarks()
